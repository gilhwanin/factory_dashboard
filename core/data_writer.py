from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pandas as pd
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from UTIL.const import (
    DB_NAME,
    COL_PRODUCT, COL_PLAN, COL_TODAY_RES, COL_PREV_RES, COL_WORK_STATUS,
)
from UTIL.db_handler import getdb, runquery, closedb, db_connection
from UTIL.util import fmt
from logic.cal_values import (
    calc_order_qty_packs,
    get_pacsu_by_co,
    get_produced_qty_packs,
    calc_plan_kg_by_recipe,
    get_stock_from_pan,
    get_prev_residue_from_today,
    recalc_dashboard_raw_keep_manual,
    recalc_dashboard_sauce_keep_manual,
    recalc_dashboard_vege_keep_manual,
)
from dialog.DashboardLogDialog import DashboardLogDialog
from dialog.ProductListDialog import ProductListDialog

if TYPE_CHECKING:
    from core.widget import OrderDashboardWidget


class DataWriter:
    def __init__(self, widget: OrderDashboardWidget):
        self.w = widget

    # --------------------------------------------------
    # 테이블 수정 이벤트 처리
    # --------------------------------------------------
    def on_product_item_changed(self, item: QTableWidgetItem):
        w = self.w
        col = item.column()
        if col not in (COL_PLAN, COL_TODAY_RES, COL_PREV_RES):
            return

        pk = item.data(Qt.UserRole)
        if pk is None:
            return

        text = item.text().replace(",", "").strip()
        try:
            new_val = int(text) if text else 0
            if new_val < 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(w, "오류", "0 이상 정수만 입력 가능합니다.")
            w.ui.tableWidget1.blockSignals(True)
            item.setText(fmt(0))
            w.ui.tableWidget1.blockSignals(False)
            new_val = 0

        field_map = {
            COL_PLAN: "production_plan",
            COL_TODAY_RES: "today_residue",
            COL_PREV_RES: "prev_residue",
        }
        field_name = field_map.get(col)
        if not field_name:
            return

        with db_connection(DB_NAME) as (conn, cur):
            # 변경 전 값 조회
            old_val = 0
            try:
                df_old = runquery(cur, f"SELECT {field_name} FROM ORDER_DASHBOARD WHERE PK = %s", [pk])
                if df_old is not None and not df_old.empty:
                    old_val = int(df_old.iloc[0, 0] or 0)
            except Exception:
                pass

            sql = f"UPDATE ORDER_DASHBOARD SET {field_name} = %s WHERE PK = %s"
            runquery(cur, sql, [new_val, pk])

            # 로그 기록
            if old_val != new_val:
                row = item.row()
                u_item = w.ui.tableWidget1.item(row, COL_PRODUCT)
                uname = u_item.text() if u_item else "-"

                label_map = {
                    "production_plan": "생산계획",
                    "today_residue": "당일잔피",
                    "prev_residue": "전일잔피",
                }
                lbl = label_map.get(field_name, field_name)
                content = f"{lbl} {old_val} -> {new_val}"
                DashboardLogDialog.log_change(
                    w.current_user, w.ui.dateEdit.date(), uname, content, ""
                )

        w.loader.refresh_single_row(pk)

    def on_material_item_changed(self, tab_key: str, item: QTableWidgetItem):
        """Raw/Sauce/Vege 아이템 변경 공통 핸들러"""
        w = self.w
        col = item.column()
        if col not in (1, 4, 6):
            return

        table = w._material_table(tab_key)
        db_table = w._material_db_table(tab_key)
        row = item.row()
        pk = item.data(Qt.UserRole)
        if pk is None:
            return

        def get_int(c):
            v = table.item(row, c)
            if not v:
                return 0
            try:
                return int(str(v.text()).replace(",", ""))
            except Exception:
                return 0

        stock = get_int(1)
        prepro = get_int(4)
        incoming = get_int(6)

        with db_connection(DB_NAME) as (conn, cur):
            # 로그용: 변경 전 값 조회
            old_vals = {}
            try:
                df_old = runquery(
                    cur, f"SELECT stock, prepro_qty, ipgo_qty FROM {db_table} WHERE PK = %s", [pk]
                )
                if df_old is not None and not df_old.empty:
                    old_vals["stock"] = int(df_old.iloc[0][0] or 0)
                    old_vals["prepro_qty"] = int(df_old.iloc[0][1] or 0)
                    old_vals["ipgo_qty"] = int(df_old.iloc[0][2] or 0)
            except Exception:
                pass

            sql = f"""
                UPDATE {db_table}
                SET stock = %s, prepro_qty = %s, ipgo_qty = %s
                WHERE PK = %s
            """
            runquery(cur, sql, [stock, prepro, incoming, pk])

            # 로그 기록
            changed_content = []
            if old_vals.get("stock", -999) != stock:
                changed_content.append(f"재고 {old_vals.get('stock')}->{stock}")
            if old_vals.get("prepro_qty", -999) != prepro:
                changed_content.append(f"선생산 {old_vals.get('prepro_qty')}->{prepro}")
            if old_vals.get("ipgo_qty", -999) != incoming:
                changed_content.append(f"입고 {old_vals.get('ipgo_qty')}->{incoming}")

            if changed_content:
                u_item = table.item(row, 0)
                uname = u_item.text() if u_item else "-"
                content = ", ".join(changed_content)
                DashboardLogDialog.log_change(
                    w.current_user, w.ui.dateEdit.date(), uname, content, ""
                )

        w.loader.refresh_single_material_row(tab_key, pk)

    # --------------------------------------------------
    # 대시보드 데이터 가공
    # --------------------------------------------------
    def generate_material_dashboard(self, db_table: str, recipe_keyword: str, bco_list: list):
        """Raw/Sauce 대시보드 공통 생성 로직"""
        w = self.w
        qdate = w.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")
        sdate_dt = datetime(qdate.year(), qdate.month(), qdate.day(), 0, 0, 0)
        now = datetime.now()

        with db_connection(DB_NAME) as (conn, cur):
            sql_order = """
                SELECT co, order_qty_after, production_plan, prev_residue, pkg
                FROM ORDER_DASHBOARD
                WHERE CONVERT(DATE, sdate) = %s
            """
            df_order = runquery(cur, sql_order, [sdate_str])

        if df_order is None or df_order.empty:
            with db_connection(DB_NAME) as (conn, cur):
                runquery(cur, f"DELETE FROM {db_table} WHERE CONVERT(DATE, sdate) = %s", [sdate_str])
            return

        df_order.columns = [c.upper() for c in df_order.columns]
        df_order["CO"] = df_order["CO"].astype(str).str.strip()

        grouped = calc_plan_kg_by_recipe(df_order, recipe_keyword, bco_list)

        if grouped is None or grouped.empty:
            with db_connection(DB_NAME) as (conn, cur):
                runquery(cur, f"DELETE FROM {db_table} WHERE CONVERT(DATE, sdate) = %s", [sdate_str])
            return

        with db_connection(DB_NAME) as (conn, cur):
            runquery(cur, f"DELETE FROM {db_table} WHERE CONVERT(DATE, sdate) = %s", [sdate_str])

        rows = []
        for _, r in grouped.iterrows():
            bco = str(r["BCO"]).strip()
            buname = str(r["BUNAME"]).strip()
            plan_kg_sum = float(r["PLAN_KG"] or 0)
            qty_int = int(round(plan_kg_sum))

            if qty_int <= 0:
                continue

            stock_val = get_stock_from_pan(bco, sdate_str)
            rows.append({
                "uname": buname, "co": bco, "sdate": sdate_dt,
                "created_time": now, "stock": stock_val,
                "order_qty": qty_int, "order_qty_after": qty_int,
                "prepro_qty": 0, "ipgo_qty": 0,
            })

        if rows:
            self._insert_material_rows(db_table, rows)

    def dashboard_vege_from_dashboard(self):
        w = self.w
        qdate = w.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")
        sdate_dt = datetime(qdate.year(), qdate.month(), qdate.day(), 0, 0, 0)
        now = datetime.now()

        VEGE_BCO_LIST = ["720192", "700122", "720094", "710665"]

        with db_connection(DB_NAME) as (conn, cur):
            sql = """
                SELECT co, order_qty_after, production_plan, prev_residue, pkg
                FROM ORDER_DASHBOARD
                WHERE CONVERT(DATE, sdate) = %s
            """
            df_order = runquery(cur, sql, [sdate_str])

        if df_order is None or df_order.empty:
            with db_connection(DB_NAME) as (conn, cur):
                runquery(cur, "DELETE FROM DASHBOARD_VEGE WHERE CONVERT(DATE, sdate) = %s", [sdate_str])
            return

        df_order.columns = [c.upper() for c in df_order.columns]
        df_order["CO"] = df_order["CO"].astype(str).str.strip()

        co_list = df_order["CO"].unique().tolist()
        if not co_list:
            return

        with db_connection("GFOOD_B") as (conn, cur):
            sql = f"""
                SELECT CO, BCO, BUNAME, SA
                FROM RECIPE
                WHERE BCO IN ({','.join(['%s'] * len(VEGE_BCO_LIST))})
                  AND CO IN ({','.join(['%s'] * len(co_list))})
            """
            df_recipe = runquery(cur, sql, VEGE_BCO_LIST + co_list)

        if df_recipe is None or df_recipe.empty:
            with db_connection(DB_NAME) as (conn, cur):
                runquery(cur, "DELETE FROM DASHBOARD_VEGE WHERE CONVERT(DATE, sdate) = %s", [sdate_str])
            return

        df_recipe.columns = [c.upper() for c in df_recipe.columns]
        df_recipe["CO"] = df_recipe["CO"].astype(str).str.strip()
        df_recipe["BCO"] = df_recipe["BCO"].astype(str).str.strip()

        df = df_order.merge(df_recipe, on="CO", how="inner")
        if df.empty:
            return

        df["PLAN_KG"] = df["PRODUCTION_PLAN"].fillna(0).astype(float) * df["PKG"].fillna(0).astype(float)
        df = df[df["PLAN_KG"] > 0]
        if df.empty:
            return

        df["VEGE_KG"] = df["PLAN_KG"] * df["SA"].fillna(0).astype(float)
        df = df[df["VEGE_KG"] > 0]
        if df.empty:
            return

        grouped = df.groupby(["BCO", "BUNAME"], as_index=False)["VEGE_KG"].sum()

        with db_connection(DB_NAME) as (conn, cur):
            runquery(cur, "DELETE FROM DASHBOARD_VEGE WHERE CONVERT(DATE, sdate) = %s", [sdate_str])

        rows = []
        for _, r in grouped.iterrows():
            qty_int = int(round(float(r["VEGE_KG"] or 0)))
            if qty_int <= 0:
                continue

            stock_val = get_stock_from_pan(str(r["BCO"]), sdate_str)
            rows.append({
                "uname": r["BUNAME"], "co": r["BCO"], "sdate": sdate_dt,
                "created_time": now, "stock": stock_val,
                "order_qty": qty_int, "order_qty_after": qty_int,
                "prepro_qty": 0, "ipgo_qty": 0,
            })

        if rows:
            self._insert_material_rows("DASHBOARD_VEGE", rows)

    # --------------------------------------------------
    # DB Insert/Update/Delete
    # --------------------------------------------------
    def _insert_dashboard_rows(self, rows):
        with db_connection(DB_NAME) as (conn, cur):
            sql = """
                INSERT INTO ORDER_DASHBOARD (
                    bigo, sdate, created_time, id,
                    rname, uname, co, pkg,
                    order_qty, order_qty_after, prev_residue, production_plan,
                    produced_qty, today_residue
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """
            for r in rows:
                params = [
                    r["bigo"], r["sdate"], r["created_time"], r["id"],
                    r["rname"], r["uname"], r["co"], r["pkg"],
                    r["order_qty"], r["order_qty_after"], r["prev_residue"],
                    r["production_plan"], r["produced_qty"], r["today_residue"],
                ]
                runquery(cur, sql, params)

    def _insert_material_rows(self, db_table: str, rows: list):
        """Raw/Sauce/Vege INSERT 공통"""
        with db_connection(DB_NAME) as (conn, cur):
            sql = f"""
                INSERT INTO {db_table} (
                    uname, co, sdate, created_time,
                    stock, order_qty, order_qty_after,
                    prepro_qty, ipgo_qty
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """
            for r in rows:
                runquery(cur, sql, [
                    r["uname"], r["co"], r["sdate"], r["created_time"],
                    r["stock"], r["order_qty"], r["order_qty_after"],
                    r["prepro_qty"], r["ipgo_qty"],
                ])

    def on_click_add_dummy_rows(self):
        w = self.w
        dlg = ProductListDialog(w)
        if dlg.exec_() != QDialog.Accepted:
            return

        w.product_list = dlg.get_product_list()

        if not w.product_list:
            QMessageBox.information(w, "안내", "PRODUCT_LIST가 비어 있습니다.")
            return

        qdate: QDate = w.ui.dateEdit.date()
        sdate_dt = datetime(qdate.year(), qdate.month(), qdate.day(), 0, 0, 0)
        sdate_str = qdate.toString("yyyy-MM-dd")
        now = datetime.now()

        rows = []

        with db_connection("GFOOD_B") as (conn_master, cur_master):
            for base_co, vendor in w.product_list:
                base_co = str(base_co).strip()
                if not base_co:
                    continue

                df_master = runquery(
                    cur_master,
                    "SELECT TOP 1 CO, UNAME, PACKG, PACSU FROM MASTER WHERE CO = %s",
                    [base_co],
                )

                if df_master is None or df_master.empty:
                    print(f"[SKIP:MASTER NOT FOUND] vendor={vendor}  base_co={base_co}")
                    continue

                m = df_master.iloc[0]
                uname = str(m.get("UNAME", "")).strip()

                packg_raw = m.get("PACKG", None)
                pkg = 0.0
                if packg_raw is not None:
                    try:
                        pkg = float(packg_raw)
                    except Exception:
                        try:
                            pkg = float(str(packg_raw).replace("KG", "").replace("kg", "").strip())
                        except Exception:
                            pkg = 0.0

                pacsu_raw = m.get("PACSU", 1)
                try:
                    pacsu = int(pacsu_raw if pacsu_raw not in (None, "") else 1)
                except Exception:
                    pacsu = 1
                if pacsu <= 0:
                    pacsu = 1

                prev_residue = get_prev_residue_from_today(base_co)

                order_qty_packs = calc_order_qty_packs(
                    base_co=base_co, vendor=vendor,
                    sdate_str=sdate_str, pacsu=pacsu,
                )

                produced_qty_val, produced_time = get_produced_qty_packs(base_co, sdate_str, pacsu)

                rows.append({
                    "bigo": "", "sdate": sdate_dt, "created_time": now,
                    "id": "인길환", "rname": vendor, "uname": uname,
                    "co": base_co, "pkg": pkg,
                    "order_qty": order_qty_packs, "order_qty_after": order_qty_packs,
                    "prev_residue": prev_residue, "production_plan": 0,
                    "produced_qty": produced_qty_val, "today_residue": 0,
                })

        if not rows:
            QMessageBox.information(w, "안내", "INSERT할 데이터가 없습니다.")
            return

        try:
            self._insert_dashboard_rows(rows)
            self.generate_material_dashboard("DASHBOARD_RAW", "(정선)", ['502811'])
            self.generate_material_dashboard("DASHBOARD_SAUCE", "소스", ['600901'])
            self.dashboard_vege_from_dashboard()

            QMessageBox.information(
                w, "완료",
                f"제품 {len(rows)}행, 원료/소스/야채 대시보드 재생성 완료."
            )
            DashboardLogDialog.log_action(
                w.current_user, w.ui.dateEdit.date(),
                f"표 생성(dummy rows) {len(rows)}행"
            )
            if hasattr(w.ui, "tabWidget") and w.ui.tabWidget.currentIndex() == 0:
                w.loader.load_product_tab()

        except Exception as e:
            QMessageBox.critical(w, "에러", str(e))

    def on_click_delete_selected_products(self):
        """선택한 제품만 삭제 + RAW/SAUCE/VEGE 재집계"""
        w = self.w
        table = w.ui.tableWidget1
        selected_rows = sorted({idx.row() for idx in table.selectedIndexes()})

        if not selected_rows:
            QMessageBox.information(w, "안내", "삭제할 제품을 선택하세요.")
            return

        UNAME_COL = 1
        uname_after_list = []
        for r in selected_rows:
            item = table.item(r, UNAME_COL)
            if item:
                uname_after_list.append(item.text().strip())

        if not uname_after_list:
            QMessageBox.warning(w, "오류", "선택한 행에서 제품명(UNAME)을 찾을 수 없습니다.")
            return

        uname_after_list = list(set(uname_after_list))

        # Dashboard_UNAME_MAP 조회하여 after → before 매핑
        with db_connection(DB_NAME) as (conn, cur):
            sql = "SELECT before_value, after_value FROM Dashboard_UNAME_MAP"
            df_map = runquery(cur, sql)

        mapping = {}
        if df_map is not None and not df_map.empty:
            for _, row in df_map.iterrows():
                bf = str(row["before_value"]).strip()
                af = str(row["after_value"]).strip()
                mapping[af] = bf

        uname_final_list = list(set(
            mapping.get(af, af) for af in uname_after_list
        ))

        reply = QMessageBox.question(
            w, "삭제 확인",
            f"선택한 {len(uname_after_list)}개의 제품을 삭제하시겠습니까?\n"
            f"(ORDER_DASHBOARD 삭제 + RAW/SAUCE/VEGE 재집계)",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        qdate = w.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")

        with db_connection(DB_NAME) as (conn, cur):
            placeholders = ", ".join(["%s"] * len(uname_final_list))
            sql = f"""
                DELETE FROM ORDER_DASHBOARD
                WHERE CONVERT(DATE, sdate) = %s
                  AND UNAME IN ({placeholders})
            """
            runquery(cur, sql, [sdate_str] + uname_final_list)

        try:
            recalc_dashboard_raw_keep_manual(sdate_str)
            recalc_dashboard_sauce_keep_manual(sdate_str)
            recalc_dashboard_vege_keep_manual(sdate_str)
        except Exception as e:
            QMessageBox.critical(w, "재집계 오류", str(e))
            return

        QMessageBox.information(w, "완료", "선택한 제품이 삭제되었으며 재집계가 완료되었습니다.")
        DashboardLogDialog.log_action(
            w.current_user, w.ui.dateEdit.date(),
            f"선택 행 삭제 ({len(uname_final_list)}건)"
        )
        w.loader.load_product_tab()

    def on_click_delete_rows(self):
        w = self.w
        qdate = w.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")

        reply = QMessageBox.question(
            w, "삭제 확인",
            f"{sdate_str} 데이터 전체를 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        with db_connection(DB_NAME) as (conn, cur):
            for tbl in ["ORDER_DASHBOARD", "DASHBOARD_RAW", "DASHBOARD_SAUCE", "DASHBOARD_VEGE"]:
                runquery(cur, f"DELETE FROM {tbl} WHERE CONVERT(DATE, sdate) = %s", [sdate_str])

        QMessageBox.information(w, "완료", f"{sdate_str} 자료 삭제 완료!")
        DashboardLogDialog.log_action(w.current_user, qdate, f"표 삭제 ({sdate_str})")

        for table in w._all_tables():
            table.setRowCount(0)

    # --------------------------------------------------
    # 생산량(produced_qty) 재계산 & UPDATE
    # --------------------------------------------------
    def on_click_update_product(self, checked=False, *, silent=False):
        w = self.w
        try:
            qdate: QDate = w.ui.dateEdit.date()
            sdate_str = qdate.toString("yyyy-MM-dd")

            try:
                conn, cur = getdb(DB_NAME)
            except Exception as e:
                msg = f"{DB_NAME} 연결 실패:\n{e}"
                if not silent:
                    QMessageBox.critical(w, "DB 오류", msg)
                else:
                    print(f"[ERROR] {msg}")
                return

            try:
                sql = "SELECT DISTINCT co FROM ORDER_DASHBOARD WHERE CONVERT(DATE, sdate) = %s"
                df = runquery(cur, sql, [sdate_str])
            finally:
                closedb(conn)

            if df is None or len(df) == 0:
                if not silent:
                    QMessageBox.information(w, "안내", f"{sdate_str} 기준 데이터가 없습니다.")
                return

            df = pd.DataFrame(df)
            co_col = df.columns[0]

            try:
                conn_u, cur_u = getdb(DB_NAME)
            except Exception as e:
                msg = f"{DB_NAME} 연결 실패(UPDATE):\n{e}"
                if not silent:
                    QMessageBox.critical(w, "DB 오류", msg)
                return

            updated_cnt = 0
            try:
                for co_val in df[co_col]:
                    co_str = str(co_val).strip()
                    if not co_str:
                        continue

                    try:
                        pacsu = get_pacsu_by_co(co_str)
                    except Exception as e:
                        print(f"[ERROR] get_pacsu_by_co({co_str}) 예외: {e}")
                        pacsu = 1

                    produced_qty, recent_time_val = get_produced_qty_packs(co_str, sdate_str, pacsu)

                    try:
                        runquery(
                            cur_u,
                            """
                            UPDATE ORDER_DASHBOARD
                            SET produced_qty = %s, recent_chulgo = %s
                            WHERE CONVERT(DATE, sdate) = %s AND co = %s
                            """,
                            [produced_qty, recent_time_val, sdate_str, co_str],
                        )
                        updated_cnt += 1
                    except Exception as e:
                        print(f"[ERROR] produced_qty UPDATE 실패 co={co_str}: {e}")
                        continue
            finally:
                closedb(conn_u)

            msg = f"{sdate_str} 기준 {updated_cnt}개 품목의 생산 팩수(produced_qty)를 갱신했습니다."
            if not silent:
                QMessageBox.information(w, "완료", msg)
            else:
                print(f"[INFO] {msg}")
            w.loader.load_product_tab()

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(w, "예외 발생", f"생산량 갱신 중 예외가 발생했습니다.\n{e}")

    # --------------------------------------------------
    # 발주량 재계산 & UPDATE
    # --------------------------------------------------
    def on_click_update_order_qty_after(self, checked=False, *, silent=False):
        w = self.w
        qdate: QDate = w.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")

        if not w.product_list:
            if not silent:
                QMessageBox.information(w, "안내", "PRODUCT_LIST가 비어 있습니다.")
            return

        with db_connection(DB_NAME) as (conn, cur):
            for base_co, vendor in w.product_list:
                base_co = str(base_co).strip()

                pacsu = get_pacsu_by_co(base_co)
                if pacsu is None or pacsu <= 0:
                    pacsu = 1

                new_qty_packs = int(
                    calc_order_qty_packs(
                        base_co=base_co, vendor=vendor,
                        sdate_str=sdate_str, pacsu=pacsu,
                    )
                )

                runquery(cur, """
                    UPDATE ORDER_DASHBOARD
                    SET order_qty_after = %s
                    WHERE CONVERT(DATE, sdate) = %s AND co = %s
                """, [new_qty_packs, sdate_str, base_co])

        recalc_dashboard_raw_keep_manual(sdate_str)
        recalc_dashboard_sauce_keep_manual(sdate_str)
        recalc_dashboard_vege_keep_manual(sdate_str)

        msg = ("모든 제품의 최종 발주량(order_qty_after)이 재계산되었고,\n"
               "원료/소스/야채 대시보드도 최신 기준으로 반영되었습니다.")
        if not silent:
            QMessageBox.information(w, "완료", msg)
        else:
            print(f"[INFO] {msg.replace(chr(10), ' ')}")

        w.loader.load_product_tab()

    def on_click_complete_product(self):
        w = self.w
        table = w.ui.tableWidget1

        selected_rows = sorted({idx.row() for idx in table.selectedIndexes()})
        if not selected_rows:
            QMessageBox.information(w, "안내", "완료 처리할 제품 행을 선택하세요.")
            return

        with db_connection(DB_NAME) as (conn, cur):
            for row in selected_rows:
                item = table.item(row, 0)
                if not item:
                    continue

                pk = item.data(Qt.UserRole)
                if not pk:
                    continue

                runquery(
                    cur,
                    "UPDATE ORDER_DASHBOARD SET work_status = '완료' WHERE PK = %s",
                    [pk],
                )

                item_ws = table.item(row, COL_WORK_STATUS)
                if item_ws:
                    table.blockSignals(True)
                    item_ws.setText("완료")
                    table.blockSignals(False)

                w.loader.refresh_single_row(pk)

        QMessageBox.information(w, "완료", "선택된 제품의 작업 상태가 '완료'로 변경되었습니다.")

    def on_click_hide_row(self):
        """선택된 제품행의 hide 필드를 0/1 토글"""
        w = self.w
        table = w.ui.tableWidget1
        selected_rows = sorted({idx.row() for idx in table.selectedIndexes()})

        if not selected_rows:
            QMessageBox.information(w, "안내", "숨김 처리할 제품을 선택하세요.")
            return

        with db_connection(DB_NAME) as (conn, cur):
            for row in selected_rows:
                item = table.item(row, 0)
                if not item:
                    continue

                pk = item.data(Qt.UserRole)
                if not pk:
                    continue

                df = runquery(cur, "SELECT hide FROM ORDER_DASHBOARD WHERE PK = %s", [pk])
                if df is None or df.empty:
                    continue

                cur_val = df.iloc[0]["hide"]
                new_val = 1 if cur_val is None else (0 if int(cur_val) == 1 else 1)
                runquery(cur, "UPDATE ORDER_DASHBOARD SET hide = %s WHERE PK = %s", [new_val, pk])

            QMessageBox.information(w, "완료", "선택한 제품의 hide 값이 변경되었습니다.")

        w.loader.load_product_tab()

    # --------------------------------------------------
    # 생산일지 연동 (jen → pan INSERT)
    # --------------------------------------------------
    def on_click_sync_diary(self):
        w = self.w
        qdate: QDate = w.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")

        # 1) jen 조회 (GFOOD_B)
        try:
            conn_jen, cur_jen = getdb("GFOOD_B")
        except Exception as e:
            QMessageBox.warning(w, "오류", f"GFOOD_B DB 연결 실패:\n{e}")
            return

        try:
            df_jen = runquery(cur_jen, """
                SELECT tco, tuname, jnod, jno, lot
                FROM jen
                WHERE CONVERT(DATE, jdate) = %s
                  AND jnod LIKE 'N%%'
                  AND (tuname LIKE '%%이마트%%' OR tuname LIKE '%%롯데%%'
                       OR tuname LIKE '%%홈플%%' OR tuname LIKE '%%컬리%%')
                  AND tuname NOT LIKE '%%정선%%'
                ORDER BY jdate DESC
            """, [sdate_str])
        finally:
            closedb(conn_jen)

        if df_jen is None or df_jen.empty:
            QMessageBox.information(w, "안내", f"{sdate_str} 에 해당하는 jen 데이터가 없습니다.")
            return

        # 2) 업체별 집계 + 선택 대화상자
        df_jen["_vendor"] = df_jen["tuname"].apply(
            lambda t: self._detect_vendor(str(t).strip())
        )
        df_jen = df_jen[df_jen["_vendor"] != ""].copy()
        if df_jen.empty:
            QMessageBox.information(w, "안내", "업체를 판별할 수 없는 데이터만 있습니다.")
            return

        vendor_counts = df_jen["_vendor"].value_counts().to_dict()

        selected_vendors = self._show_vendor_select_dialog(w, vendor_counts)
        if selected_vendors is None:
            return
        if not selected_vendors:
            QMessageBox.information(w, "안내", "선택한 업체가 없습니다.")
            return

        df_jen = df_jen[df_jen["_vendor"].isin(selected_vendors)].copy()

        # 4) 중복 확인 (GFOOD_B.pan)
        try:
            conn_pan, cur_pan = getdb("GFOOD_B")
        except Exception as e:
            QMessageBox.warning(w, "오류", f"GFOOD_B DB 연결 실패:\n{e}")
            return

        try:
            # same_product 그룹 맵 로딩
            group_map = self._load_group_map()

            # 그룹에 관련된 모든 CO의 UNAME 일괄 조회
            all_cos = set()
            for _, row in df_jen.iterrows():
                tco = str(row["tco"]).strip()
                for co in group_map.get(tco, [tco]):
                    all_cos.add(co)
            gwchul_uname_map = self._fetch_gwchul_uname(list(all_cos))

            # 5) jen 각 행 → 그룹별 1:N → pan INSERT
            #    토요일 + 홈플/이마트/롯데인 경우: 토·일 분 각각 1행씩 INSERT
            SPLIT_VENDORS = {"홈플러스", "이마트", "롯데"}
            day_dates_split = None
            try:
                _dt = datetime.strptime(sdate_str, "%Y-%m-%d")
                if _dt.weekday() == 5:
                    _sun = (_dt + timedelta(days=1)).strftime("%Y-%m-%d")
                    day_dates_split = [[sdate_str], [_sun]]
            except Exception:
                pass

            inserted = 0
            for _, row in df_jen.iterrows():
                tco = str(row["tco"]).strip()
                vendor = row["_vendor"]
                jno = str(row.get("jno", "")).strip()
                jnod = str(row.get("jnod", "")).strip()

                target_cos = group_map.get(tco, [tco])

                # 분할 대상 업체 + 토요일이면 [토,일] 두 번, 그 외엔 한 번 (None=자동)
                if day_dates_split is not None and vendor in SPLIT_VENDORS:
                    overrides = day_dates_split
                else:
                    overrides = [None]

                for co in target_cos:
                    uname = gwchul_uname_map.get(co, co)
                    pacsu, packg = self._get_master_info(co)

                    for dates_override in overrides:
                        order_packs = int(calc_order_qty_packs(
                            base_co=co, vendor=vendor,
                            sdate_str=sdate_str, pacsu=pacsu,
                            dates_override=dates_override,
                        ))
                        ipgokg = round(order_packs * packg, 2)

                        if order_packs <= 0 or ipgokg <= 0:
                            continue

                        lot = self._generate_lot(cur_pan, co, sdate_str)

                        runquery(cur_pan, """
                            INSERT INTO pan (
                                CO, ICO, UNAME, IUNAME, BIGO, PDATE,
                                IPGO, IPGOKG, PAC,
                                PAN, REST, JANG,
                                RNAME, CH, CH2, DE, ID,
                                JNAME, JNO, JNOD, CJ, GUBUN, LOT, PUM, JUM,
                                CDATE
                            ) VALUES (
                                %s, %s, %s, %s, %s, %s,
                                %s, %s, %s,
                                %s, %s, %s,
                                %s, %s, %s, %s, %s,
                                %s, %s, %s, %s, %s, %s, %s, %s,
                                GETDATE()
                            )
                        """, [
                            co, co, uname, uname, uname, sdate_str,
                            0, ipgokg, order_packs,
                            0, 0, 0,
                            '작업', 'I', 'J', 'N', 'python-factory',
                            '공장(양념육)', jno, jnod, '생산품', 27, lot, '국내제조', '지점',
                        ])
                        inserted += 1

            conn_pan.commit()
        finally:
            closedb(conn_pan)

        QMessageBox.information(w, "완료",
            f"생산일지 연동 완료\n"
            f"jen 조회: {len(df_jen)}건 / pan INSERT: {inserted}건")

    # --------------------------------------------------
    # 생산품 삭제 (PAN 내역 다중선택 삭제)
    # --------------------------------------------------
    def on_click_delete_diary(self):
        w = self.w
        qdate: QDate = w.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")

        # 1) 조회 (ID 조건 제외, 나머지 동일)
        try:
            conn, cur = getdb("GFOOD_B")
        except Exception as e:
            QMessageBox.warning(w, "오류", f"GFOOD_B DB 연결 실패:\n{e}")
            return

        try:
            df = runquery(cur, """
                SELECT PKEY, CO, UNAME, PAC, IPGOKG, LOT, BIGO, ID, JNO, JNOD, PDATE
                FROM pan
                WHERE CH2 = 'J'
                  AND CH = 'I'
                  AND RNAME = '작업'
                  AND JNAME = '공장(양념육)'
                  AND CONVERT(DATE, PDATE) = %s
                ORDER BY UNAME, LOT
            """, [sdate_str])
        finally:
            closedb(conn)

        if df is None or df.empty:
            QMessageBox.information(w, "안내",
                f"{sdate_str} 에 해당하는 생산품 PAN 내역이 없습니다.")
            return

        # 2) 다이얼로그 표시
        selected_pkeys = self._show_delete_diary_dialog(w, df, sdate_str)
        if not selected_pkeys:
            return

        # 3) 최종 확인
        reply = QMessageBox.question(
            w, "확인",
            f"선택한 {len(selected_pkeys)}건을 삭제합니다.\n진행하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # 4) DELETE 실행 (PKEY IN (...))
        try:
            conn, cur = getdb("GFOOD_B")
        except Exception as e:
            QMessageBox.warning(w, "오류", f"GFOOD_B DB 연결 실패:\n{e}")
            return

        try:
            placeholders = ",".join(["%s"] * len(selected_pkeys))
            runquery(cur, f"""
                DELETE FROM pan WHERE PKEY IN ({placeholders})
            """, selected_pkeys)
            conn.commit()
        finally:
            closedb(conn)

        QMessageBox.information(w, "완료",
            f"생산품 삭제 완료\nDELETE: {len(selected_pkeys)}건")

    @staticmethod
    def _show_delete_diary_dialog(parent, df, sdate_str):
        """PAN 내역 테이블 다이얼로그. 선택한 행의 PKEY 리스트 반환, 취소 시 빈 리스트."""
        dlg = QDialog(parent)
        dlg.setWindowTitle("생산품 삭제")
        dlg.resize(1150, 600)
        dlg.setStyleSheet("""
            QDialog { background: #fafafa; }
            QLabel#title { font-size: 14pt; font-weight: bold; color: #2b2a35; }
            QLabel#hint  { color: #6b6b6b; }
            QLabel#count { color: #5a1f1c; font-weight: bold; }
            QLineEdit {
                padding: 6px 10px;
                border: 1px solid #c9c9c9;
                border-radius: 6px;
                background: white;
            }
            QLineEdit:focus { border: 1px solid #6b8fb5; }
            QTableWidget {
                background: white;
                gridline-color: #e3e3e3;
                selection-background-color: #fde2e1;
                selection-color: #2b2a35;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 6px;
                border: none;
                border-right: 1px solid #d8d8d8;
                border-bottom: 1px solid #c9c9c9;
                font-weight: bold;
            }
            QPushButton {
                padding: 6px 16px;
                border-radius: 6px;
                font-weight: 500;
            }
        """)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(8)

        # 상단 — 제목 + 안내
        title = QLabel(f"{sdate_str} 생산품 PAN 내역")
        title.setObjectName("title")
        layout.addWidget(title)

        hint = QLabel("드래그 또는 Ctrl/Shift 클릭으로 다중선택할 수 있습니다.")
        hint.setObjectName("hint")
        layout.addWidget(hint)

        # 검색 + 카운트
        search_row = QHBoxLayout()
        search_row.setSpacing(8)
        search_row.addWidget(QLabel("품명 검색:"))
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("제품명 일부를 입력하세요")
        search_row.addWidget(search_edit, 1)

        count_label = QLabel()
        count_label.setObjectName("count")
        search_row.addWidget(count_label)
        layout.addLayout(search_row)

        # 테이블
        columns = ["PKEY", "UNAME", "CO", "PAC", "IPGOKG", "LOT", "BIGO", "ID", "JNO", "JNOD"]
        headers = ["PKEY", "제품명", "CO", "팩수", "입고KG", "LOT", "비고", "ID", "JNO", "JNOD"]

        table = QTableWidget(len(df), len(columns))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)

        # 숫자 정렬용으로 PAC, IPGOKG는 정렬 모드도 지원
        rows_data = []
        for i, (_, row) in enumerate(df.iterrows()):
            for j, col in enumerate(columns):
                val = row.get(col, "")
                if val is None:
                    val = ""
                item = QTableWidgetItem(str(val))
                if col in ("PAC", "IPGOKG"):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                table.setItem(i, j, item)
            rows_data.append(str(row.get("UNAME", "") or "").lower())

        table.setColumnHidden(0, True)  # PKEY 숨김
        table.setColumnHidden(columns.index("ID"), True)  # ID 숨김
        table.resizeColumnsToContents()

        header = table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # 제품명 stretch
        for col_idx in (2, 3, 4, 5):
            header.setSectionResizeMode(col_idx, QHeaderView.ResizeToContents)
        table.setSortingEnabled(False)

        layout.addWidget(table, 1)

        # 카운트 갱신 + 검색 필터
        def update_count():
            visible = sum(1 for r in range(table.rowCount()) if not table.isRowHidden(r))
            sel = len({idx.row() for idx in table.selectionModel().selectedRows()})
            count_label.setText(f"표시 {visible} / {len(df)}건  ·  선택 {sel}건")

        def on_search(text):
            kw = text.strip().lower()
            for r in range(table.rowCount()):
                hidden = bool(kw) and (kw not in rows_data[r])
                table.setRowHidden(r, hidden)
            update_count()

        search_edit.textChanged.connect(on_search)
        table.itemSelectionChanged.connect(update_count)
        update_count()

        # 하단 — 전체선택 + 확인/취소
        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        btn_select_visible = QPushButton("표시된 행 전체 선택")
        bottom.addWidget(btn_select_visible)
        bottom.addStretch(1)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        ok_btn = btn_box.button(QDialogButtonBox.Ok)
        cancel_btn = btn_box.button(QDialogButtonBox.Cancel)
        ok_btn.setText("삭제")
        cancel_btn.setText("취소")
        ok_btn.setStyleSheet("background: #d54a3f; color: white; border: 1px solid #ad3a30;")
        cancel_btn.setStyleSheet("background: #eaeaea; border: 1px solid #c9c9c9;")
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        bottom.addWidget(btn_box)
        layout.addLayout(bottom)

        def select_visible():
            table.clearSelection()
            sel_model = table.selectionModel()
            from PyQt5.QtCore import QItemSelection, QItemSelectionModel
            selection = QItemSelection()
            for r in range(table.rowCount()):
                if not table.isRowHidden(r):
                    idx_l = table.model().index(r, 0)
                    idx_r = table.model().index(r, table.columnCount() - 1)
                    selection.select(idx_l, idx_r)
            sel_model.select(selection, QItemSelectionModel.Select | QItemSelectionModel.Rows)

        btn_select_visible.clicked.connect(select_visible)

        if dlg.exec_() != QDialog.Accepted:
            return []

        pkeys = []
        for idx in table.selectionModel().selectedRows():
            pkey_item = table.item(idx.row(), 0)
            if pkey_item:
                try:
                    pkeys.append(int(pkey_item.text()))
                except Exception:
                    pass
        return pkeys

    @staticmethod
    def _show_vendor_select_dialog(parent, vendor_counts: dict):
        """업체 선택 체크박스 대화상자. 선택한 업체 리스트 반환, 취소 시 None."""
        dlg = QDialog(parent)
        dlg.setWindowTitle("업체 선택")
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel("연동할 업체를 선택하세요:"))

        checkboxes = {}
        for vendor, cnt in sorted(vendor_counts.items()):
            cb = QCheckBox(f"{vendor} ({cnt}건)")
            cb.setChecked(True)
            layout.addWidget(cb)
            checkboxes[vendor] = cb

        btn_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)

        if dlg.exec_() != QDialog.Accepted:
            return None

        return [v for v, cb in checkboxes.items() if cb.isChecked()]

    @staticmethod
    def _detect_vendor(tuname: str) -> str:
        if "이마트" in tuname:
            return "이마트"
        if "롯데" in tuname:
            return "롯데"
        if "홈플" in tuname:
            return "홈플러스"
        if "컬리" in tuname:
            return "마켓컬리"
        return ""

    @staticmethod
    def _load_group_map():
        """GP.same_product에서 {co: [그룹 내 모든 co]} 매핑 반환"""
        group_map = {}
        conn, cur = getdb("GP")
        if conn is None:
            return group_map
        try:
            df = runquery(cur, "SELECT group_id, co FROM same_product")
        finally:
            closedb(conn)

        if df is None or df.empty:
            return group_map

        from collections import defaultdict
        groups = defaultdict(list)
        for _, row in df.iterrows():
            groups[int(row["group_id"])].append(str(row["co"]).strip())

        for cos in groups.values():
            for co in cos:
                group_map[co] = cos

        return group_map

    @staticmethod
    def _fetch_gwchul_uname(co_list):
        """GWCHUL.MASTER에서 CO→UNAME 매핑 딕셔너리 반환"""
        if not co_list:
            return {}
        conn, cur = getdb("GWCHUL")
        if conn is None:
            return {}
        try:
            placeholders = ", ".join(["%s"] * len(co_list))
            df = runquery(cur, f"""
                SELECT CO, UNAME FROM MASTER
                WHERE CO IN ({placeholders})
            """, co_list)
        finally:
            closedb(conn)

        result = {}
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                result[str(row["CO"]).strip()] = str(row["UNAME"]).strip()
        return result

    @staticmethod
    def _generate_lot(cur_pan, co, sdate_str):
        """LOT 생성: {yyMMdd}{co6자리}{순번3자리}"""
        date_part = sdate_str.replace("-", "")[2:]  # 앞 2자리(세기) 제거
        co_part = co.strip()[:6].ljust(6, '0')
        df = runquery(cur_pan, """
            SELECT COUNT(*) AS cnt FROM pan
            WHERE CO = %s
              AND CONVERT(DATE, PDATE) = %s
              AND CH = 'I'
              AND CH2 = 'J'
        """, [co, sdate_str])
        seq = (int(df.iloc[0]["cnt"]) if df is not None and not df.empty else 0) + 1
        return f"{date_part}{co_part}{str(seq).zfill(3)}"

    @staticmethod
    def _get_master_info(co: str):
        pacsu = 1
        packg = 0.0
        try:
            conn, cur = getdb("GFOOD_B")
        except Exception:
            return pacsu, packg
        try:
            df = runquery(cur, """
                SELECT TOP 1 PACSU, PACKG FROM MASTER WHERE CO = %s
            """, [co])
        finally:
            closedb(conn)

        if df is None or df.empty:
            return pacsu, packg

        m = df.iloc[0]

        raw_pacsu = m.get("PACSU", 1)
        try:
            pacsu = int(raw_pacsu if raw_pacsu not in (None, "") else 1)
            if pacsu <= 0:
                pacsu = 1
        except Exception:
            pacsu = 1

        raw_packg = m.get("PACKG", None)
        if raw_packg is not None:
            try:
                packg = float(raw_packg)
            except Exception:
                try:
                    packg = float(str(raw_packg).replace("KG", "").replace("kg", "").strip())
                except Exception:
                    packg = 0.0

        return pacsu, packg
