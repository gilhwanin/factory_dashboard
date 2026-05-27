from __future__ import annotations

from math import ceil
from typing import TYPE_CHECKING

import pandas as pd
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QBrush, QColor

from UTIL.const import (
    DB_NAME, PAGE_SIZE,
    COL_VENDOR, COL_PRODUCT, COL_PKG,
    COL_ORDER, COL_FINAL_ORDER, COL_DIFF, COL_PREV_RES,
    COL_PRODUCTION, COL_PLAN, COL_PLAN_KG, COL_CUR_PROD,
    COL_SHIPMENT_TIME, COL_TODAY_RES, COL_TRATE, COL_WORK_STATUS,
)
from UTIL.db_handler import runquery, db_connection
from UTIL.util import fmt
from logic.cal_values import calc_trate_value

if TYPE_CHECKING:
    from core.widget import OrderDashboardWidget


class DataLoader:
    def __init__(self, widget: OrderDashboardWidget):
        self.w = widget

    # --------------------------------------------------
    # 제품 탭 로딩
    # --------------------------------------------------
    def load_product_tab(self):
        w = self.w
        table = w.ui.tableWidget1
        qdate: QDate = w.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")
        w.ui.label_retailer.setText(w.current_vendor)

        try:
            with db_connection(DB_NAME) as (conn, cur):
                sql = """
                    SELECT
                        A.PK, A.co, A.rname, A.uname, A.pkg,
                        A.order_qty, A.order_qty_after,
                        A.prev_residue, A.production_plan,
                        A.produced_qty, A.today_residue,
                        A.work_status,
                        B.deadline,
                        A.recent_chulgo
                    FROM ORDER_DASHBOARD A
                    LEFT JOIN Dashboard_UNAME_MAP B
                           ON A.uname = B.before_value
                          AND A.rname = B.retailer
                    WHERE CONVERT(DATE, A.sdate) = %s
                """
                params = [sdate_str]

                if not w.show_hidden:
                    sql += " AND (A.hide = 0 OR A.hide IS NULL)"

                if w.current_vendor == "코스트코":
                    sql += " AND A.rname IN ('코스트코', '코스온')"
                elif w.current_vendor == "홈플/컬리":
                    sql += " AND A.rname IN ('홈플러스', '마켓컬리')"
                else:
                    sql += " AND A.rname = %s"
                    params.append(w.current_vendor)

                sql += " ORDER BY A.RNAME DESC, A.PK"
                df = runquery(cur, sql, params)
        except (ConnectionError, Exception) as e:
            print(f"[_load_product_tab] DB 연결 실패: {e}")
            table.blockSignals(True)
            w.table_ui.setup_product_headers(table)
            table.setRowCount(0)
            table.blockSignals(False)
            return

        table.blockSignals(True)
        w.table_ui.setup_product_headers(table)
        table.setRowCount(0)

        if df is None or len(df) == 0:
            w.product_total_pages = 1
            w.product_page = 0
            w.pagination.update_pagination_ui()
            table.blockSignals(False)
            return

        df = pd.DataFrame(df)
        df.columns = [str(c).upper() for c in df.columns]

        # 페이지네이션 적용
        if w.current_vendor == "롯데":
            LOTTE_CATS = ["슈퍼", "마트", "맥스"]

            def _lotte_cat(uname):
                for cat in LOTTE_CATS:
                    if cat in str(uname):
                        return cat
                return "슈퍼"

            df["_LOTTE_CAT"] = df["UNAME"].apply(_lotte_cat)
            pages = [(cat, df[df["_LOTTE_CAT"] == cat].drop(columns=["_LOTTE_CAT"]))
                     for cat in LOTTE_CATS]
            pages = [(cat, p) for cat, p in pages if not p.empty]

            w.product_total_pages = max(1, len(pages))
            if w.product_page >= w.product_total_pages:
                w.product_page = w.product_total_pages - 1
            w._lotte_page_labels = [cat for cat, _ in pages]
            df_page = pages[w.product_page][1]
        else:
            w._lotte_page_labels = []
            total_rows = len(df)
            w.product_total_pages = max(1, ceil(total_rows / w.product_page_size))
            if w.product_page >= w.product_total_pages:
                w.product_page = w.product_total_pages - 1
            start = w.product_page * w.product_page_size
            end = min(start + w.product_page_size, total_rows)
            df_page = df.iloc[start:end]

        table.setRowCount(len(df_page))

        for row_idx, row in enumerate(df_page.itertuples(index=False)):
            pk = int(row.PK)
            co_val = str(row.CO).strip()

            rname = row.RNAME.strip() if row.RNAME else ""
            uname_raw = row.UNAME.strip() if row.UNAME else ""
            uname = w.uname_map_cache.get(uname_raw, uname_raw)

            pkg = float(row.PKG)
            order_qty = int(row.ORDER_QTY)
            order_qty_after = int(row.ORDER_QTY_AFTER)
            prev_residue = int(row.PREV_RESIDUE)
            produced_qty = int(row.PRODUCED_QTY)
            today_residue = int(row.TODAY_RESIDUE)
            production_plan = int(row.PRODUCTION_PLAN)

            # 최근출고 시각 포맷팅
            recent_chulgo_val = row.RECENT_CHULGO
            shipment_time_str = "-"
            if recent_chulgo_val:
                try:
                    s_val = str(recent_chulgo_val)
                    if len(s_val) >= 16:
                        shipment_time_str = s_val[11:16]
                except Exception:
                    pass

            # 계산 필드
            diff = order_qty_after - order_qty
            diff_display = "" if diff == 0 else str(diff)

            production_qty = max(order_qty_after - prev_residue, 0)
            plan_qty = production_plan
            plan_kg = plan_qty * pkg

            # 수율 계산
            trate_val = calc_trate_value(
                co=co_val,
                order_qty_after=order_qty_after,
                prev_residue=prev_residue,
                today_residue=today_residue,
                production_plan=production_plan,
                sdate_str=sdate_str,
            )
            if trate_val is None:
                trate_text = "-"
                trate_color = None
            else:
                trate_text = f"{trate_val:.1f}"
                trate_int = int(trate_val)
                trate_color = QColor("#cc0000") if (trate_int < 90 or trate_int >= 100) else None

            # 작업상태 자동 계산
            if plan_qty <= 0:
                work_status = "-"
            elif produced_qty > order_qty_after:
                work_status = "초과"
            elif produced_qty == order_qty_after:
                work_status = "완료"
            else:
                work_status = ""

            # 소비기한 계산
            deadline_val = ""
            if row.DEADLINE is not None and not pd.isna(row.DEADLINE):
                try:
                    days = int(float(row.DEADLINE))
                    calc_date = qdate.addDays(days - 1)
                    deadline_val = calc_date.toString("yy-MM-dd")
                except Exception:
                    deadline_val = ""

            values = [
                rname, uname, deadline_val, fmt(f"{pkg:.1f}"),
                fmt(order_qty), fmt(order_qty_after), fmt(diff_display),
                fmt(prev_residue), fmt(production_qty), fmt(plan_qty),
                fmt(round(plan_kg)), fmt(produced_qty), shipment_time_str,
                fmt(today_residue), trate_text, work_status,
            ]

            for col, text in enumerate(values):
                item = w.table_ui.create_product_item(text, pk, col)
                item.setData(Qt.UserRole + 10, co_val)

                if col == COL_TRATE and trate_color:
                    item.setForeground(QBrush(trate_color))

                table.setItem(row_idx, col, item)

        w.table_ui.apply_column_resize_rules()

        if not w._item_changed_connected["product"]:
            table.itemChanged.connect(w.writer.on_product_item_changed)
            w._item_changed_connected["product"] = True

        table.blockSignals(False)
        w.table_ui.apply_column_visibility_rules()

        # 최근출고(물류용) 모드
        is_logistics_mode = w.ui.ml_check.isChecked()
        table.setColumnHidden(COL_SHIPMENT_TIME, not is_logistics_mode)
        table.setColumnHidden(COL_TRATE, is_logistics_mode)

        # 페이지네이션 바 업데이트
        w.pagination.update_pagination_ui()

    # --------------------------------------------------
    # 원료 탭 로딩 (Raw / Sauce / Vege)
    # --------------------------------------------------
    def load_material_tab(self, tab_key: str):
        """Raw/Sauce/Vege 탭 공통 로딩"""
        w = self.w
        table = w._material_table(tab_key)
        db_table = w._material_db_table(tab_key)
        row_height = w._material_row_height(tab_key)
        sdate_str = w.ui.dateEdit.date().toString("yyyy-MM-dd")

        table.blockSignals(True)
        w.table_ui.setup_material_headers(table)
        table.setRowCount(0)

        try:
            with db_connection(DB_NAME) as (conn, cur):
                sql = f"""
                    SELECT PK, uname, co, stock, order_qty,
                           order_qty_after, prepro_qty, ipgo_qty
                    FROM {db_table}
                    WHERE CONVERT(DATE, sdate) = %s
                    ORDER BY uname, co, PK
                """
                df = runquery(cur, sql, [sdate_str])
        except (ConnectionError, Exception) as e:
            print(f"[_load_material_tab] DB 연결 실패: {e}")
            table.blockSignals(False)
            return

        if df is None or len(df) == 0:
            table.blockSignals(False)
            return

        df = pd.DataFrame(df)
        df.columns = [str(c).upper() for c in df.columns]
        table.setRowCount(len(df))

        for row_idx, row in enumerate(df.itertuples(index=False)):
            pk = int(row.PK)
            stock = int(row.STOCK)
            order_qty = int(row.ORDER_QTY)
            order_qty_after = int(row.ORDER_QTY_AFTER)
            prepro_qty = int(row.PREPRO_QTY)
            ipgo_qty = int(row.IPGO_QTY)

            expected_short = stock - order_qty_after - prepro_qty
            expected_stock = expected_short + ipgo_qty

            row_values = [
                str(row.UNAME).strip(),
                fmt(stock), fmt(order_qty), fmt(order_qty_after),
                fmt(prepro_qty), fmt(expected_short),
                fmt(ipgo_qty), fmt(expected_stock),
            ]

            for col_idx, value in enumerate(row_values):
                item = w.table_ui.create_material_item(value, pk, col_idx)
                table.setItem(row_idx, col_idx, item)

        table.verticalHeader().setDefaultSectionSize(row_height)
        w.table_ui.apply_column_resize_rules()

        if not w._item_changed_connected[tab_key]:
            handler = lambda item, k=tab_key: w.writer.on_material_item_changed(k, item)
            table.itemChanged.connect(handler)
            w._item_changed_connected[tab_key] = True

        table.blockSignals(False)

    # --------------------------------------------------
    # 단일 행 갱신
    # --------------------------------------------------
    def refresh_single_row(self, pk: int):
        w = self.w
        table = w.ui.tableWidget1
        qdate: QDate = w.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")

        with db_connection(DB_NAME) as (conn, cur):
            sql = """
                SELECT
                    PK, co, rname, uname, pkg,
                    order_qty, order_qty_after,
                    prev_residue, production_plan, produced_qty,
                    today_residue, recent_chulgo
                FROM ORDER_DASHBOARD
                WHERE PK = %s
            """
            df = runquery(cur, sql, [pk])

        if df is None or len(df) == 0:
            return

        r = pd.DataFrame(df)
        r.columns = [str(c).upper() for c in r.columns]
        r = r.iloc[0]

        co_val = str(r.get("CO", "") or "").strip()
        order_qty = r["ORDER_QTY"]
        order_qty_after = r["ORDER_QTY_AFTER"]
        prev_residue = r["PREV_RESIDUE"]
        today_residue = r["TODAY_RESIDUE"]
        production_plan = r["PRODUCTION_PLAN"]
        produced_qty = r["PRODUCED_QTY"]
        pkg = r["PKG"]

        production_qty = max(order_qty_after - prev_residue, 0)
        plan_kg = production_plan * pkg
        diff = order_qty_after - order_qty

        trate_val = calc_trate_value(
            co=co_val,
            order_qty_after=order_qty_after,
            prev_residue=prev_residue,
            today_residue=today_residue,
            production_plan=production_plan,
            sdate_str=sdate_str,
        )
        trate_text = "-" if trate_val is None else f"{trate_val:.1f}"

        if production_plan <= 0:
            work_status = "-"
        elif produced_qty > order_qty_after:
            work_status = "초과"
        elif produced_qty == order_qty_after:
            work_status = "완료"
        else:
            work_status = ""

        recent_chulgo_val = r.get("RECENT_CHULGO")
        shipment_time_str = "-"
        if recent_chulgo_val:
            s_val = str(recent_chulgo_val)
            if len(s_val) >= 16:
                shipment_time_str = s_val[11:16]

        values = {
            COL_VENDOR: r["RNAME"],
            COL_PRODUCT: r["UNAME"],
            COL_PKG: fmt(f"{pkg:.1f}"),
            COL_ORDER: fmt(order_qty),
            COL_FINAL_ORDER: fmt(order_qty_after),
            COL_DIFF: "" if diff == 0 else fmt(diff),
            COL_PREV_RES: fmt(prev_residue),
            COL_PRODUCTION: fmt(production_qty),
            COL_PLAN: fmt(production_plan),
            COL_PLAN_KG: fmt(f"{plan_kg:.1f}"),
            COL_CUR_PROD: fmt(produced_qty),
            COL_SHIPMENT_TIME: shipment_time_str,
            COL_TODAY_RES: fmt(today_residue),
            COL_TRATE: trate_text,
            COL_WORK_STATUS: work_status,
        }

        row_idx = -1
        for i in range(table.rowCount()):
            if table.item(i, 0) and table.item(i, 0).data(Qt.UserRole) == pk:
                row_idx = i
                break

        if row_idx == -1:
            return

        table.blockSignals(True)
        for col, text in values.items():
            item = w.table_ui.create_product_item(text, pk, col)
            table.setItem(row_idx, col, item)
        table.blockSignals(False)

    def refresh_single_material_row(self, tab_key: str, pk: int):
        """Raw/Sauce/Vege 단일 행 갱신 공통"""
        w = self.w
        table = w._material_table(tab_key)
        db_table = w._material_db_table(tab_key)

        with db_connection(DB_NAME) as (conn, cur):
            sql = f"""
                SELECT PK, uname, stock, order_qty, order_qty_after,
                       prepro_qty, ipgo_qty
                FROM {db_table}
                WHERE PK = %s
            """
            df = runquery(cur, sql, [pk])

        if df is None or df.empty:
            return

        r = pd.DataFrame(df)
        r.columns = [str(c).upper() for c in r.columns]
        r = r.iloc[0]

        stock = int(r["STOCK"])
        order_qty = int(r["ORDER_QTY"])
        order_qty_after = int(r["ORDER_QTY_AFTER"])
        prepro_qty = int(r["PREPRO_QTY"])
        ipgo_qty = int(r["IPGO_QTY"])

        expected_short = stock - order_qty_after - prepro_qty
        expected_stock = expected_short + ipgo_qty

        values = [
            r["UNAME"], fmt(stock), fmt(order_qty), fmt(order_qty_after),
            fmt(prepro_qty), fmt(expected_short), fmt(ipgo_qty), fmt(expected_stock),
        ]

        row_idx = -1
        for i in range(table.rowCount()):
            if table.item(i, 0) and table.item(i, 0).data(Qt.UserRole) == pk:
                row_idx = i
                break

        if row_idx == -1:
            return

        table.blockSignals(True)
        for col, v in enumerate(values):
            item = w.table_ui.create_material_item(str(v), pk, col)
            table.setItem(row_idx, col, item)
        table.blockSignals(False)
