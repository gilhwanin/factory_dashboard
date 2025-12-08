import sys
from datetime import datetime

import pandas as pd
from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QTableWidgetItem,
    QMessageBox,
    QAbstractItemView,
    QTableWidget,
    QHeaderView,
    QDialog,
    QFileDialog,
    QInputDialog,
    QLineEdit,
)
from PyQt5.QtGui import QBrush, QColor, QFont

from UTIL.db_handler import getdb, runquery, closedb
from ci_cd.updatedown import check_version_and_update
from UTIL.util import fmt
from logic.cal_values import *
from config import PRODUCT_LIST, VENDOR_CHOICES

from UI.dashboard import Ui_Form

from dialog.DashboardLogDialog import DashboardLogDialog
from dialog.ProductListDialog import ProductListDialog
from dialog.ProductNameDialog import ProductNameDialog

CURRENT_VERSION = "a-0011"
PROGRAM_NAME = "factory_dashboard"

DB_NAME = "GP"
CURRENT_LEVEL = 0   # 로그인 전 0
CURRENT_USER = None  # 선택


# ---------------------------------------------------------
# 컬럼 인덱스
# ---------------------------------------------------------
COL_VENDOR = 0
COL_PRODUCT = 1
COL_PKG = 2
COL_ORDER = 3
COL_FINAL_ORDER = 4
COL_DIFF = 5
COL_PREV_RES = 6
COL_PRODUCTION = 7
COL_PLAN = 8
COL_PLAN_KG = 9
COL_CUR_PROD = 10
COL_TODAY_RES = 11
COL_TRATE = 12
COL_WORK_STATUS = 13

class OrderDashboardWidget(QWidget):

    #1. 초기화 & 기본 기능
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Form()
        self.ui.setupUi(self)

        # 🔹 제품 리스트 상태 (프로그램 실행 동안 유지)
        self.product_list = list(PRODUCT_LIST)

        self._fullscreen_mode = False
        self.ui.control_frame.hide()

        # 날짜 설정
        self.ui.dateEdit.setDate(QDate.currentDate())
        self.ui.dateText.setText(self.ui.dateEdit.date().toString("yyyy-MM-dd"))

        # 변경 이벤트 플래그
        self._product_table_item_changed_connected = False
        self._raw_table_item_changed_connected = False
        self._sauce_table_item_changed_connected = False
        self._vege_table_item_changed_connected = False

        # 🔹 품명 매핑 캐시
        self.uname_map_cache = {}
        self.refresh_uname_map_cache()

        # 테이블 스타일 적용
        self._setup_table_base(self.ui.tableWidget1)
        self._setup_table_base(self.ui.tableWidget2)
        self._setup_table_base(self.ui.tableWidget3)
        self._setup_table_base(self.ui.tableWidget4)

        # -----------------------------
        # 버튼 / 시그널 연결 (명시적)
        # -----------------------------
        self.ui.btn_view.clicked.connect(self.on_click_toggle_fullscreen)
        self.ui.btn_prev.clicked.connect(self.on_click_prev_date)
        self.ui.btn_next.clicked.connect(self.on_click_next_date)

        self.ui.btn_product.clicked.connect(self.on_click_tab_product)
        self.ui.btn_raw.clicked.connect(self.on_click_tab_raw)
        self.ui.btn_sauce.clicked.connect(self.on_click_tab_sauce)
        self.ui.btn_vege.clicked.connect(self.on_click_tab_vege)

        self.ui.btn_add.clicked.connect(self.on_click_add_dummy_rows)
        self.ui.btn_del.clicked.connect(self.on_click_delete_rows)
        self.ui.btn_del_row.clicked.connect(self.on_click_delete_selected_products)
        self.ui.btn_update.clicked.connect(self.on_click_update_order_qty_after)
        self.ui.btn_log.clicked.connect(self.on_click_show_log_dialog)
        self.ui.btn_excel.clicked.connect(self.on_click_export_excel)
        self.ui.btn_admin.clicked.connect(self.on_click_toggle_admin)
        self.ui.btn_complete.clicked.connect(self.on_click_complete_product)
        self.ui.btn_custom.clicked.connect(self.on_click_custom)

        # 생산량(Prodcued) 실적 업데이트 버튼
        self.ui.btn_update_product.clicked.connect(self.on_click_update_product)

        # 탭 전환
        self.ui.tabWidget.currentChanged.connect(self.on_tab_changed)

        # 날짜 변경 이벤트
        # dateEdit 은 QDateEdit 로 고정되어 있으니 조건 제거
        self.ui.dateEdit.dateChanged.connect(self.on_date_changed)

        # 최초 로딩
        self._load_product_tab()
        self._apply_column_visibility_rules()

    #2. UI 상태 관련 함수
    def on_click_toggle_fullscreen(self):
        # toggle 값 반전
        self._fullscreen_mode = not self._fullscreen_mode

        if self._fullscreen_mode:
            # 🔵 전체화면 ON
            self.showFullScreen()

            # 🔵 control_frame 숨김
            self.ui.view_frame.hide()
            self.ui.control_frame.hide()

        else:
            # 🔵 전체화면 OFF (기본창 크기로 복구)
            self.showNormal()

            # 🔵 control_frame 다시 보이기
            self.ui.view_frame.show()
            if CURRENT_LEVEL >= 2:
                self.ui.control_frame.show()
            else:
                self.ui.control_frame.hide()

        # 레이아웃 전체 다시 배치
        self.layout().update()

    def _ask_admin_login(self):
        """
        DASHBOARD_ID 테이블에서 비밀번호만으로 사용자 검증.
        pw는 UNIQUE 조건이므로 하나의 계정만 매칭됨.
        """
        pw, ok = QInputDialog.getText(
            self,
            "관리자 로그인",
            "비밀번호를 입력하세요:",
            QLineEdit.Password
        )

        if not ok:
            return False

        conn, cur = getdb("GP")
        try:
            sql = """
                SELECT name, level
                FROM DASHBOARD_ID
                WHERE pw = %s
            """
            df = runquery(cur, sql, [pw])
        finally:
            closedb(conn)

        # 로그인 실패
        if df is None or df.empty:
            QMessageBox.warning(self, "로그인 실패", "일치하는 계정이 없습니다.")
            return False

        # 결과 1건
        name = str(df.iloc[0]["name"]).strip()
        level = int(df.iloc[0]["level"])

        # 글로벌 저장
        global CURRENT_LEVEL, CURRENT_USER
        CURRENT_LEVEL = level
        CURRENT_USER = name

        return True

    def on_click_toggle_admin(self):
        global CURRENT_LEVEL, CURRENT_USER

        # 이미 관리자면 OFF
        if CURRENT_LEVEL >= 1:
            CURRENT_LEVEL = 0
            CURRENT_USER = ""
            self.ui.control_frame.hide()
            self._apply_column_visibility_rules()
            self.ui.btn_admin.setText("관리자")

            # 로그인 해제 시 전체 테이블 새로고침
            self._load_product_tab()
            self._load_raw_tab()
            self._load_sauce_tab()
            self._load_vege_tab()
            return

        # 로그인 시도
        if self._ask_admin_login():
            if CURRENT_LEVEL >= 2:
                self.ui.control_frame.show()
            else:
                self.ui.control_frame.hide()

            self._apply_column_visibility_rules()
            self.ui.btn_admin.setText(f"관리자: {CURRENT_USER}")

            # 로그인 성공 시 전체 테이블 새로고침
            self._load_product_tab()
            self._load_raw_tab()
            self._load_sauce_tab()
            self._load_vege_tab()

    def on_click_custom(self):
        """품명 관리 다이얼로그 오픈"""
        dlg = ProductNameDialog(self)
        dlg.exec_()

    def refresh_uname_map_cache(self):
        """Dashboard_UNAME_MAP 테이블에서 매핑 정보 로드하여 캐시 갱신"""
        self.uname_map_cache = {}
        conn, cur = getdb(DB_NAME)
        try:
            # 테이블이 없을 수도 있으므로 try-except 처리
            sql = "SELECT before_value, after_value FROM Dashboard_UNAME_MAP"
            df = runquery(cur, sql)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    bf = str(row['before_value']).strip()
                    af = str(row['after_value']).strip()
                    self.uname_map_cache[bf] = af
        except Exception as e:
            print(f"매핑 캐시 로드 실패 (테이블이 없거나 오류): {e}")
        finally:
            closedb(conn)

        # 캐시 갱신 후 테이블 리로드
        if hasattr(self, 'ui'): # 초기화 중일 수 있음
            self._load_product_tab()


    #3. 탭 / 날짜 이동
    def on_click_prev_date(self):
        old = self.ui.dateEdit.date()
        new = old.addDays(-1)
        self.ui.dateEdit.setDate(new)  # dateChanged 시그널 자동 발생 → 테이블 자동 갱신됨

    def on_click_next_date(self):
        old = self.ui.dateEdit.date()
        new = old.addDays(1)
        self.ui.dateEdit.setDate(new)  # dateChanged 시그널 자동 발생 → 테이블 자동 갱신됨

    def on_date_changed(self):
        # 날짜 텍스트 갱신
        qdate = self.ui.dateEdit.date()
        date_str = qdate.toString("yyyy-MM-dd")
        self.ui.dateText.setText(date_str)

        # 탭별 데이터 로딩
        idx = self.ui.tabWidget.currentIndex()
        if idx == 0:
            self._load_product_tab()
        elif idx == 1:
            self._load_raw_tab()
        elif idx == 2:
            self._load_sauce_tab()
        elif idx == 3:
            self._load_vege_tab()

    def on_click_tab_product(self):
        self.ui.tabWidget.setCurrentIndex(0)

    def on_click_tab_raw(self):
        self.ui.tabWidget.setCurrentIndex(1)

    def on_click_tab_sauce(self):
        self.ui.tabWidget.setCurrentIndex(2)

    def on_click_tab_vege(self):
        self.ui.tabWidget.setCurrentIndex(3)

    def on_tab_changed(self, idx: int):
        if idx == 0:
            self._load_product_tab()
        elif idx == 1:
            self._load_raw_tab()
        elif idx == 2:
            self._load_sauce_tab()
        elif idx == 3:
            self._load_vege_tab()


    #4. 테이블 UI 설정 관련
    def _setup_table_base(self, table: QTableWidget):
        table.setAlternatingRowColors(True)
        table.setShowGrid(True)
        table.setEditTriggers(QAbstractItemView.DoubleClicked)

        table.setStyleSheet("""
               QTableWidget {
                   font-size: 18px;
                   alternate-background-color: #f6f7fb;
                   gridline-color: #c0c0c0;
               }
               QHeaderView::section {
                   font-size: 18px;
                   font-weight: bold;
                   color: black;
                   padding: 5px;
                   border: 1px solid #a0a0a0;
               }
               QTableWidget::item {
                   height: 32px;
               }
           """)

    def _setup_product_headers(self, table):
        headers = [
            "업체명",
            "품명",
            "팩중량",
            "발주량",
            "최종발주량",
            "팩 차이",
            "전일 잔피",
            "생산 팩수",
            "생산계획",
            "팩수 to kg",
            "데크출고량",
            "당일 잔피",
            "수율",
            "작업상태",
        ]

        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)

        header_normal = QColor("#8fbcd4")
        header_edit = QColor("#ffdd99")
        header_live = QColor("#b7d9ff")

        for col in range(len(headers)):
            item = table.horizontalHeaderItem(col)
            if not item:
                continue

            elif col in (COL_CUR_PROD,):
                item.setBackground(QBrush(header_live))
            else:
                item.setBackground(QBrush(header_normal))


    def _setup_raw_headers(self, table: QTableWidget):
        headers = [
            "품명",  # 0 uname
            "재고량",  # 1 stock
            "예상발주량",  # 2 order_qty_after(기존 order_qty_after 사용)
            "최종발주량",  # 3 order_qty_after (새 컬럼)
            "선 생산량",  # 4 prepro_qty
            "예상부족량",  # 5 계산
            "입고예정량",  # 6 ipgo_qty
            "예상재고",  # 7 계산
        ]

        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)

        header_normal = QColor("#8fbcd4")
        header_edit = QColor("#ffdd99")

        for col in range(len(headers)):
            item = table.horizontalHeaderItem(col)
            if not item:
                continue

            # 편집 가능 컬럼: 선 생산량(4) + 입고예정량(6)
            if col in (4, 6):
                item.setBackground(QBrush(header_edit))
            else:
                item.setBackground(QBrush(header_normal))

    def _setup_sauce_headers(self, table: QTableWidget):
        headers = [
            "품명",  # 0 uname
            "재고량",  # 1 stock
            "예상발주량",  # 2 order_qty
            "최종발주량",  # 3 order_qty_after (동일 값)
            "선 생산량",  # 4 prepro_qty
            "예상부족량",  # 5 계산
            "입고예정량",  # 6 ipgo_qty
            "예상재고",  # 7 계산
        ]

        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)

        header_normal = QColor("#8fbcd4")
        header_edit = QColor("#ffdd99")

        for col in range(len(headers)):
            item = table.horizontalHeaderItem(col)
            if not item:
                continue

            # 편집 컬럼: 선 생산량(4), 입고예정량(6)
            if col in (4, 6):
                item.setBackground(QBrush(header_edit))
            else:
                item.setBackground(QBrush(header_normal))

    def _setup_vege_headers(self, table: QTableWidget):
        headers = [
            "품명",
            "재고량",
            "예상발주량",
            "최종발주량",
            "선 생산량",
            "예상부족량",
            "입고예정량",
            "예상재고",
        ]

        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)

        header_normal = QColor("#8fbcd4")
        header_edit = QColor("#ffdd99")

        for col in range(len(headers)):
            item = table.horizontalHeaderItem(col)
            if not item:
                continue

            # 편집 컬럼: 선 생산량, 입고예정량
            if col in (4, 6):
                item.setBackground(QBrush(header_edit))
            else:
                item.setBackground(QBrush(header_normal))

    def _create_cell(
            self,
            text: str,
            pk: int,
            alignment: Qt.AlignmentFlag,
            *,
            editable: bool = False,
            underline: bool = False,
            foreground: QColor | None = None,
    ) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setData(Qt.UserRole, pk)

        font = QFont()
        font.setPointSize(18)
        font.setUnderline(underline)
        item.setFont(font)

        item.setTextAlignment(alignment)

        # 🔸 LEVEL 2 이상만 실제 편집 가능
        base_flags = item.flags()

        if editable and CURRENT_LEVEL >= 2:
            # 편집 가능
            item.setFlags(base_flags | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item.setForeground(QBrush(QColor("#777777")))
        else:
            # 읽기 전용
            item.setFlags(base_flags & ~Qt.ItemIsEditable)

        if foreground is not None:
            item.setForeground(QBrush(foreground))

        return item

    def _create_product_item(self, text: str, pk: int, col: int):
        # 정렬
        if col == COL_WORK_STATUS:
            alignment = Qt.AlignCenter
        elif col in (COL_VENDOR, COL_PRODUCT):
            alignment = Qt.AlignLeft | Qt.AlignVCenter
        else:
            alignment = Qt.AlignRight | Qt.AlignVCenter

        # 밑줄 (발주량/최종발주량)
        underline = col in (COL_ORDER, COL_FINAL_ORDER)

        # 🔸 컬럼 기준 “편집 대상 여부”만 결정
        editable_cols = {COL_PLAN, COL_TODAY_RES, COL_PREV_RES}
        editable = col in editable_cols

        # 글자 색상 (현재 생산량 등)
        foreground = QColor("#0066cc") if col in (COL_CUR_PROD,) else None

        return self._create_cell(
            text=text,
            pk=pk,
            alignment=alignment,
            editable=editable,  # 실제 편집 가능 여부는 _create_cell에서 LEVEL 체크
            underline=underline,
            foreground=foreground,
        )

    def _create_raw_item(self, text: str, pk: int, col: int):
        # 정렬 규칙
        alignment = Qt.AlignLeft | Qt.AlignVCenter if col == 0 else Qt.AlignRight | Qt.AlignVCenter

        # 🔸 편집 대상 컬럼: 재고(1), 선 생산량(4), 입고예정량(6)
        editable = col in (1, 4, 6)

        # 강조 색상 (예상부족량이 음수면 빨간색) ← 현재 col == 4로 되어있는데
        # 실제 부족량 컬럼 인덱스에 맞게 조정해도 됨.
        foreground = None
        if col == 5:  # 예상부족량 컬럼이 5번이면 이렇게
            try:
                if int(str(text).replace(",", "")) < 0:
                    foreground = QColor("#cc0000")
            except:
                pass

        item = self._create_cell(
            text=text,
            pk=pk,
            alignment=alignment,
            editable=editable,  # 실제 편집 가능 여부는 _create_cell에서 LEVEL 체크
            underline=False,
            foreground=foreground,
        )

        return item

    def _apply_column_resize_rules(self):
        table = None

        idx = self.ui.tabWidget.currentIndex()
        if idx == 0:
            table = self.ui.tableWidget1
        elif idx == 1:
            table = self.ui.tableWidget2
        elif idx == 2:
            table = self.ui.tableWidget3
        elif idx == 3:
            table = self.ui.tableWidget4
        else:
            return

        header = table.horizontalHeader()
        col_count = table.columnCount()

        # 0) 레이아웃 재계산 클리어
        table.resizeColumnsToContents()

        # 1) 품명 컬럼 찾기
        target_col = None
        for col in range(col_count):
            item = table.horizontalHeaderItem(col)
            if item and item.text().strip() == "품명":
                target_col = col
                break

        if target_col is None:
            return

        # 2) 모든 열 Stretch
        for c in range(col_count):
            header.setSectionResizeMode(c, QHeaderView.Stretch)

        # 3) 품명만 Fixed + 최소/최대 폭 고정
        header.setSectionResizeMode(target_col, QHeaderView.Fixed)
        table.setColumnWidth(target_col, 480)

        # 최소/최대 고정
        table.horizontalHeader().setMinimumSectionSize(10)
        table.setColumnWidth(target_col, 480)

    def _apply_column_visibility_rules(self):
        table = self.ui.tableWidget1

        # 관리자 레벨 2 이상만 보여야 하는 컬럼
        admin_only_cols = [
            COL_VENDOR, COL_PKG, COL_PREV_RES, COL_PRODUCTION,
            COL_PLAN_KG, COL_TODAY_RES
        ]


        for col in admin_only_cols:
            table.setColumnHidden(col, CURRENT_LEVEL < 2)

    #5. 데이터 로딩
    def _load_product_tab(self):
        table = self.ui.tableWidget1
        qdate: QDate = self.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")

        # 🔹 업체명 → 품명 → PK 순 정렬
        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                SELECT
                    PK, co, rname, uname, pkg,
                    order_qty, order_qty_after,
                    prev_residue, production_plan,
                    produced_qty, today_residue,
                    work_status
                FROM ORDER_DASHBOARD
                WHERE CONVERT(DATE, sdate) = %s
                ORDER BY PK
            """
            df = runquery(cur, sql, [sdate_str])
        finally:
            closedb(conn)

        table.blockSignals(True)

        # 공통 베이스 + 제품 헤더
        self._setup_product_headers(table)
        table.setRowCount(0)

        if df is None or len(df) == 0:
            table.blockSignals(False)
            return

        df = pd.DataFrame(df)
        df.columns = [str(c).upper() for c in df.columns]

        table.setRowCount(len(df))

        for row_idx, row in enumerate(df.itertuples(index=False)):
            pk = int(row.PK)
            co_val = str(row.CO).strip()  # 🔥 DB에서 가져온 CO

            rname = row.RNAME.strip() if row.RNAME else ""
            uname_raw = row.UNAME.strip() if row.UNAME else ""
            # 🔹 매핑 적용
            uname = self.uname_map_cache.get(uname_raw, uname_raw)

            pkg = float(row.PKG)
            order_qty = int(row.ORDER_QTY)
            order_qty_after = int(row.ORDER_QTY_AFTER)
            prev_residue = int(row.PREV_RESIDUE)
            produced_qty = int(row.PRODUCED_QTY)
            today_residue = int(row.TODAY_RESIDUE)
            production_plan = int(row.PRODUCTION_PLAN)

            # 계산 필드
            diff = order_qty_after - order_qty
            diff_display = "" if diff == 0 else str(diff)
            production_qty = max(order_qty_after - prev_residue, 0)
            plan_qty = production_plan
            plan_kg = plan_qty * pkg
            # 🔵 수율(trate) 계산
            if production_plan > 0:
                trate_value = (order_qty_after - prev_residue + today_residue) * 100 / production_plan
                trate_text = f"{trate_value:.2f}"
            else:
                trate_text = "-"

            # 🔵 작업상태 자동 계산
            if plan_qty <= 0 :
                work_status = "-"
            elif produced_qty > order_qty_after:
                work_status = "초과"
            elif produced_qty == order_qty_after:
                work_status = "완료"
            else:
                work_status = ""

            values = [
                rname,
                uname,
                fmt(f"{pkg:.1f}"),
                fmt(order_qty),
                fmt(order_qty_after),
                fmt(diff_display),
                fmt(prev_residue),
                fmt(production_qty),
                fmt(plan_qty),
                fmt(f"{plan_kg:.1f}"),
                fmt(produced_qty),
                fmt(today_residue),
                trate_text,  # 14번: COL_TRATE
                work_status  # 15번: COL_WORK_STATUS
            ]

            # 🔥 테이블 셀 생성 + CO/UserRole 저장
            for col, text in enumerate(values):
                item = self._create_product_item(text, pk, col)
                item.setData(Qt.UserRole + 10, co_val)  # ← CO 저장 (표시는 안 함)
                table.setItem(row_idx, col, item)

        table.verticalHeader().setDefaultSectionSize(46)
        self._apply_column_resize_rules()

        if not self._product_table_item_changed_connected:
            table.itemChanged.connect(self._on_product_item_changed)
            self._product_table_item_changed_connected = True

        table.blockSignals(False)
        self._apply_column_visibility_rules()

    def _load_raw_tab(self):
        table = self.ui.tableWidget2
        qdate = self.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")

        table.blockSignals(True)

        # 헤더 구성
        self._setup_raw_headers(table)
        table.setRowCount(0)

        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                SELECT
                    PK,
                    uname,
                    co,
                    stock,
                    order_qty,
                    order_qty_after,
                    prepro_qty,
                    ipgo_qty
                FROM DASHBOARD_RAW
                WHERE CONVERT(DATE, sdate) = %s
                ORDER BY uname, co, PK
            """
            df = runquery(cur, sql, [sdate_str])
        finally:
            closedb(conn)

        if df is None or len(df) == 0:
            table.blockSignals(False)
            return

        df = pd.DataFrame(df)
        df.columns = [str(c).upper() for c in df.columns]

        table.setRowCount(len(df))

        for row_idx, row in enumerate(df.itertuples(index=False)):
            pk = int(row.PK)
            uname = str(row.UNAME).strip()
            stock = int(row.STOCK)
            order_qty = int(row.ORDER_QTY)
            order_qty_after = int(row.ORDER_QTY_AFTER)
            prepro_qty = int(row.PREPRO_QTY)
            ipgo_qty = int(row.IPGO_QTY)

            # 계산 필드
            expected_short = stock - order_qty_after - prepro_qty
            expected_stock = expected_short + ipgo_qty

            row_values = [
                uname,  # 0 품명
                fmt(stock),  # 1 재고량
                fmt(order_qty),  # 2 예상발주량
                fmt(order_qty_after),  # 3 최종발주량(동일 값)
                fmt(prepro_qty),  # 4 선 생산량
                fmt(expected_short),  # 5 예상부족량
                fmt(ipgo_qty),  # 6 입고예정량
                fmt(expected_stock),  # 7 예상재고
            ]

            for col_idx, value in enumerate(row_values):
                item = self._create_raw_item(value, pk, col_idx)
                table.setItem(row_idx, col_idx, item)

        table.verticalHeader().setDefaultSectionSize(46)
        self._apply_column_resize_rules()

        if not self._raw_table_item_changed_connected:
            table.itemChanged.connect(self._on_raw_item_changed)
            self._raw_table_item_changed_connected = True

        table.blockSignals(False)

    def _load_sauce_tab(self):
        table = self.ui.tableWidget3
        qdate = self.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")

        table.blockSignals(True)

        # 헤더 구성
        self._setup_sauce_headers(table)
        table.setRowCount(0)

        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                SELECT
                    PK,
                    uname,
                    co,
                    stock,
                    order_qty,
                    order_qty_after,
                    prepro_qty,
                    ipgo_qty
                FROM DASHBOARD_SAUCE
                WHERE CONVERT(DATE, sdate) = %s
                ORDER BY uname, co, PK
            """
            df = runquery(cur, sql, [sdate_str])
        finally:
            closedb(conn)

        if df is None or len(df) == 0:
            table.blockSignals(False)
            return

        df = pd.DataFrame(df)
        df.columns = [str(c).upper() for c in df.columns]

        table.setRowCount(len(df))

        for row_idx, row in enumerate(df.itertuples(index=False)):
            pk = int(row.PK)
            uname = str(row.UNAME).strip()
            stock = int(row.STOCK)
            order_qty = int(row.ORDER_QTY)
            order_qty_after = int(row.ORDER_QTY_AFTER)
            prepro_qty = int(row.PREPRO_QTY)
            ipgo_qty = int(row.IPGO_QTY)

            expected_short = stock - order_qty_after - prepro_qty
            expected_stock = expected_short + ipgo_qty

            row_values = [
                uname,  # 0
                fmt(stock),  # 1
                fmt(order_qty),  # 2 예상발주량
                fmt(order_qty_after),  # 3 최종발주량
                fmt(prepro_qty),  # 4
                fmt(expected_short),  # 5
                fmt(ipgo_qty),  # 6
                fmt(expected_stock),  # 7
            ]

            for col_idx, value in enumerate(row_values):
                item = self._create_raw_item(value, pk, col_idx)
                table.setItem(row_idx, col_idx, item)

        table.verticalHeader().setDefaultSectionSize(46)
        self._apply_column_resize_rules()

        if not self._sauce_table_item_changed_connected:
            table.itemChanged.connect(self._on_sauce_item_changed)
            self._sauce_table_item_changed_connected = True

        table.blockSignals(False)

    def _load_vege_tab(self):
        table = self.ui.tableWidget4
        qdate = self.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")

        table.blockSignals(True)

        # 헤더 구성
        self._setup_vege_headers(table)
        table.setRowCount(0)

        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                SELECT
                    PK,
                    uname,
                    co,
                    stock,
                    order_qty,
                    order_qty_after,
                    prepro_qty,
                    ipgo_qty
                FROM DASHBOARD_VEGE
                WHERE CONVERT(DATE, sdate) = %s
                ORDER BY uname, co, PK
            """
            df = runquery(cur, sql, [sdate_str])
        finally:
            closedb(conn)

        if df is None or len(df) == 0:
            table.blockSignals(False)
            return

        df = pd.DataFrame(df)
        df.columns = [str(c).upper() for c in df.columns]

        table.setRowCount(len(df))

        for row_idx, row in enumerate(df.itertuples(index=False)):
            pk = int(row.PK)
            uname = str(row.UNAME).strip()
            stock = int(row.STOCK)
            order_qty = int(row.ORDER_QTY)
            order_qty_after = int(row.ORDER_QTY_AFTER)
            prepro_qty = int(row.PREPRO_QTY)
            ipgo_qty = int(row.IPGO_QTY)

            expected_short = stock - order_qty_after - prepro_qty
            expected_stock = expected_short + ipgo_qty

            row_values = [
                uname,
                fmt(stock),
                fmt(order_qty),
                fmt(order_qty_after),
                fmt(prepro_qty),
                fmt(expected_short),
                fmt(ipgo_qty),
                fmt(expected_stock),
            ]

            for col_idx, value in enumerate(row_values):
                item = self._create_raw_item(value, pk, col_idx)
                table.setItem(row_idx, col_idx, item)

        table.verticalHeader().setDefaultSectionSize(46)
        self._apply_column_resize_rules()

        if not hasattr(self, "_vege_table_item_changed_connected"):
            table.itemChanged.connect(self._on_vege_item_changed)
            self._vege_table_item_changed_connected = True

        table.blockSignals(False)

    def _refresh_single_row(self, pk: int):
        table = self.ui.tableWidget1

        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                SELECT
                    PK, rname, uname, pkg,
                    order_qty, order_qty_after,
                    prev_residue, production_plan, produced_qty,
                    today_residue
                FROM ORDER_DASHBOARD
                WHERE PK = %s
            """
            df = runquery(cur, sql, [pk])
        finally:
            closedb(conn)

        if df is None or len(df) == 0:
            return

        r = pd.DataFrame(df)
        r.columns = [str(c).upper() for c in r.columns]
        r = r.iloc[0]

        # -------------------------
        # 계산값 정의
        # -------------------------
        order_qty = r["ORDER_QTY"]
        order_qty_after = r["ORDER_QTY_AFTER"]
        prev_residue = r["PREV_RESIDUE"]
        today_residue = r["TODAY_RESIDUE"]
        production_plan = r["PRODUCTION_PLAN"]
        produced_qty = r["PRODUCED_QTY"]
        pkg = r["PKG"]

        # 생산량 = (최종발주량 - 전일잔피)
        production_qty = max(order_qty_after - prev_residue, 0)

        # PLAN_KG
        plan_kg = production_plan * pkg

        # 차이(DIFF)
        diff = order_qty_after - order_qty

        # -------------------------
        # 🔥 trate 계산 (수율)
        # (최종발주량 - 전일잔피 + 당일잔피) * 100 / 생산계획
        # -------------------------
        if production_plan > 0:
            trate_value = (order_qty_after - prev_residue + today_residue) * 100 / production_plan
            trate_text = f"{trate_value:.2f}"
        else:
            trate_text = "-"

        # -------------------------
        # 🔥 work_status 자동 계산
        # -------------------------
        if production_plan <= 0 :
            work_status = "-"
        elif produced_qty > order_qty_after:
            work_status = "초과"
        elif produced_qty == order_qty_after:
            work_status = "완료"
        else:
            work_status = ""

        # -------------------------
        # 테이블 적용값 구성
        # -------------------------
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
            COL_TODAY_RES: fmt(today_residue),
            COL_TRATE: trate_text,
            COL_WORK_STATUS: work_status,
        }

        # -------------------------
        # 테이블 특정 row 찾기
        # -------------------------
        row_idx = -1
        for i in range(table.rowCount()):
            if table.item(i, 0) and table.item(i, 0).data(Qt.UserRole) == pk:
                row_idx = i
                break

        if row_idx == -1:
            return

        # -------------------------
        # 값 반영
        # -------------------------
        table.blockSignals(True)
        for col, text in values.items():
            item = self._create_product_item(text, pk, col)
            table.setItem(row_idx, col, item)
        table.blockSignals(False)

    def _refresh_single_raw_row(self, pk: int):
        table = self.ui.tableWidget2

        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                SELECT
                    PK, uname, stock,
                    order_qty, order_qty_after,
                    prepro_qty, ipgo_qty
                FROM DASHBOARD_RAW
                WHERE PK = %s
            """
            df = runquery(cur, sql, [pk])
        finally:
            closedb(conn)

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
            r["UNAME"],
            fmt(stock),
            fmt(order_qty),
            fmt(order_qty_after),
            fmt(prepro_qty),
            fmt(expected_short),
            fmt(ipgo_qty),
            fmt(expected_stock),
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
            item = self._create_raw_item(str(v), pk, col)
            table.setItem(row_idx, col, item)
        table.blockSignals(False)

    def _refresh_single_sauce_row(self, pk: int):
        table = self.ui.tableWidget3

        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                SELECT
                    PK, uname, stock,
                    order_qty, order_qty_after,
                    prepro_qty, ipgo_qty
                FROM DASHBOARD_SAUCE
                WHERE PK = %s
            """
            df = runquery(cur, sql, [pk])
        finally:
            closedb(conn)

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
            r["UNAME"],
            fmt(stock),
            fmt(order_qty),
            fmt(order_qty_after),
            fmt(prepro_qty),
            fmt(expected_short),
            fmt(ipgo_qty),
            fmt(expected_stock),
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
            item = self._create_raw_item(str(v), pk, col)
            table.setItem(row_idx, col, item)
        table.blockSignals(False)

    def _refresh_single_vege_row(self, pk: int):
        table = self.ui.tableWidget4

        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                SELECT
                    PK, uname, stock,
                    order_qty, order_qty_after,
                    prepro_qty, ipgo_qty
                FROM DASHBOARD_VEGE
                WHERE PK = %s
            """
            df = runquery(cur, sql, [pk])
        finally:
            closedb(conn)

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
            r["UNAME"],
            fmt(stock),
            fmt(order_qty),
            fmt(order_qty_after),
            fmt(prepro_qty),
            fmt(expected_short),
            fmt(ipgo_qty),
            fmt(expected_stock),
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
            item = self._create_raw_item(str(v), pk, col)
            table.setItem(row_idx, col, item)
        table.blockSignals(False)

    #6. 테이블 수정 이벤트 처리
    def _on_product_item_changed(self, item: QTableWidgetItem):
        col = item.column()

        # 생산계획(COL_PLAN) 또는 당일잔피(COL_TODAY_RES)만 처리
        if col not in (COL_PLAN, COL_TODAY_RES, COL_PREV_RES):
            return

        pk = item.data(Qt.UserRole)
        if pk is None:
            return

        raw_text = item.text()
        text = raw_text.replace(",", "").strip()

        try:
            new_val = int(text) if text else 0
            if new_val < 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "오류", "0 이상 정수만 입력 가능합니다.")
            self.ui.tableWidget1.blockSignals(True)
            item.setText(fmt(0))
            self.ui.tableWidget1.blockSignals(False)
            new_val = 0

        if col == COL_PLAN:
            field_name = "production_plan"
        elif col == COL_TODAY_RES:
            field_name = "today_residue"
        elif col == COL_PREV_RES:
            field_name = "prev_residue"
        else:
            return

        conn, cur = getdb(DB_NAME)
        try:
            sql = f"UPDATE ORDER_DASHBOARD SET {field_name} = %s WHERE PK = %s"
            runquery(cur, sql, [new_val, pk])
        finally:
            closedb(conn)

        self._refresh_single_row(pk)

    def _on_raw_item_changed(self, item: QTableWidgetItem):
        col = item.column()
        # 편집 가능: stock(1), prepro(4), ipgo(6)
        if col not in (1, 4, 6):
            return

        table = self.ui.tableWidget2
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
            except:
                return 0

        stock = get_int(1)
        prepro = get_int(4)
        incoming = get_int(6)

        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                        UPDATE DASHBOARD_RAW
                        SET stock = %s,
                            prepro_qty = %s,
                            ipgo_qty = %s
                        WHERE PK = %s
                    """
            runquery(cur, sql, [stock, prepro, incoming, pk])
        finally:
            closedb(conn)

        self._refresh_single_raw_row(pk)

    def _on_sauce_item_changed(self, item: QTableWidgetItem):
        col = item.column()
        # 편집 가능: stock(1), prepro(4), ipgo(6)
        if col not in (1, 4, 6):
            return

        table = self.ui.tableWidget3
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
            except:
                return 0

        stock = get_int(1)
        prepro = get_int(4)
        incoming = get_int(6)

        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                UPDATE DASHBOARD_SAUCE
                SET stock = %s,
                    prepro_qty = %s,
                    ipgo_qty = %s
                WHERE PK = %s
            """
            runquery(cur, sql, [stock, prepro, incoming, pk])
        finally:
            closedb(conn)

        self._refresh_single_sauce_row(pk)

    def _on_vege_item_changed(self, item: QTableWidgetItem):
        col = item.column()
        # stock(1), prepro(4), ipgo(6)만 편집 가능
        if col not in (1, 4, 6):
            return

        table = self.ui.tableWidget4
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
            except:
                return 0

        stock = get_int(1)
        prepro = get_int(4)
        incoming = get_int(6)

        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                UPDATE DASHBOARD_VEGE
                SET stock = %s,
                    prepro_qty = %s,
                    ipgo_qty = %s
                WHERE PK = %s
            """
            runquery(cur, sql, [stock, prepro, incoming, pk])
        finally:
            closedb(conn)

        # UI 단일 행 갱신
        self._refresh_single_vege_row(pk)

    #8. 대시보드 데이터 가공
    def _dashboard_raw_from_dashboard(self):
        qdate = self.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")
        sdate_dt = datetime(qdate.year(), qdate.month(), qdate.day(), 0, 0, 0)
        now = datetime.now()

        # STEP 1) ORDER_DASHBOARD 조회
        conn, cur = getdb(DB_NAME)
        try:
            sql_order = """
                SELECT
                    co,
                    order_qty_after,
                    production_plan,
                    prev_residue,
                    pkg
                FROM ORDER_DASHBOARD
                WHERE CONVERT(DATE, sdate) = %s
            """
            df_order = runquery(cur, sql_order, [sdate_str])
        finally:
            closedb(conn)

        if df_order is None or df_order.empty:
            conn_d, cur_d = getdb(DB_NAME)
            try:
                runquery(cur_d,
                         "DELETE FROM DASHBOARD_RAW WHERE CONVERT(DATE, sdate) = %s",
                         [sdate_str])
            finally:
                closedb(conn_d)
            return

        df_order.columns = [c.upper() for c in df_order.columns]
        df_order["CO"] = df_order["CO"].astype(str).str.strip()

        # STEP 2) 레시피 기반 PLAN_KG 집계
        grouped = calc_plan_kg_by_recipe(df_order, "(정선)", ['502811'])

        if grouped is None or grouped.empty:
            conn_d, cur_d = getdb(DB_NAME)
            try:
                runquery(cur_d,
                         "DELETE FROM DASHBOARD_RAW WHERE CONVERT(DATE, sdate) = %s",
                         [sdate_str])
            finally:
                closedb(conn_d)
            return

        # STEP 3) 기존 RAW 삭제
        conn_d, cur_d = getdb(DB_NAME)
        try:
            runquery(cur_d,
                     "DELETE FROM DASHBOARD_RAW WHERE CONVERT(DATE, sdate) = %s",
                     [sdate_str])
        finally:
            closedb(conn_d)

        # STEP 4) INSERT rows 생성
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
                "uname": buname,
                "co": bco,
                "sdate": sdate_dt,
                "created_time": now,
                "stock": stock_val,
                "order_qty": qty_int,
                "order_qty_after": qty_int,
                "prepro_qty": 0,
                "ipgo_qty": 0,
            })

        if not rows:
            return

        self._insert_dashboard_raw_rows(rows)

    def _dashboard_sauce_from_dashboard(self):
        qdate = self.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")
        sdate_dt = datetime(qdate.year(), qdate.month(), qdate.day(), 0, 0, 0)
        now = datetime.now()

        # STEP 1) ORDER_DASHBOARD 조회
        conn, cur = getdb(DB_NAME)
        try:
            sql_order = """
                SELECT
                    co,
                    order_qty_after,
                    production_plan,
                    prev_residue,
                    pkg
                FROM ORDER_DASHBOARD
                WHERE CONVERT(DATE, sdate) = %s
            """
            df_order = runquery(cur, sql_order, [sdate_str])
        finally:
            closedb(conn)

        if df_order is None or df_order.empty:
            conn_d, cur_d = getdb(DB_NAME)
            try:
                runquery(cur_d,
                         "DELETE FROM DASHBOARD_SAUCE WHERE CONVERT(DATE, sdate) = %s",
                         [sdate_str])
            finally:
                closedb(conn_d)
            return

        df_order.columns = [c.upper() for c in df_order.columns]
        df_order["CO"] = df_order["CO"].astype(str).str.strip()

        # STEP 2) 소스 PLAN_KG
        grouped = calc_plan_kg_by_recipe(df_order, "소스", ['600901'])

        if grouped is None or grouped.empty:
            conn_d, cur_d = getdb(DB_NAME)
            try:
                runquery(cur_d,
                         "DELETE FROM DASHBOARD_SAUCE WHERE CONVERT(DATE, sdate) = %s",
                         [sdate_str])
            finally:
                closedb(conn_d)
            return

        # STEP 3) 기존 데이터 삭제
        conn_d, cur_d = getdb(DB_NAME)
        try:
            runquery(cur_d,
                     "DELETE FROM DASHBOARD_SAUCE WHERE CONVERT(DATE, sdate) = %s",
                     [sdate_str])
        finally:
            closedb(conn_d)

        # STEP 4) INSERT
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
                "uname": buname,
                "co": bco,
                "sdate": sdate_dt,
                "created_time": now,
                "stock": stock_val,
                "order_qty": qty_int,
                "order_qty_after": qty_int,
                "prepro_qty": 0,
                "ipgo_qty": 0,
            })

        if rows:
            self._insert_dashboard_sauce_rows(rows)

    def _dashboard_vege_from_dashboard(self):
        qdate = self.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")
        sdate_dt = datetime(qdate.year(), qdate.month(), qdate.day(), 0, 0, 0)
        now = datetime.now()

        VEGE_BCO_LIST = ["720192", "700122", "720094", "710665"]

        # STEP 1) ORDER_DASHBOARD 조회
        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                SELECT
                    co, order_qty_after,
                    production_plan,
                    prev_residue, pkg
                FROM ORDER_DASHBOARD
                WHERE CONVERT(DATE, sdate) = %s
            """
            df_order = runquery(cur, sql, [sdate_str])
        finally:
            closedb(conn)

        if df_order is None or df_order.empty:
            conn_d, cur_d = getdb(DB_NAME)
            try:
                runquery(cur_d,
                         "DELETE FROM DASHBOARD_VEGE WHERE CONVERT(DATE, sdate) = %s",
                         [sdate_str])
            finally:
                closedb(conn_d)
            return

        df_order.columns = [c.upper() for c in df_order.columns]
        df_order["CO"] = df_order["CO"].astype(str).str.strip()

        co_list = df_order["CO"].unique().tolist()
        if not co_list:
            return

        # STEP 2) RECIPE 조회
        conn, cur = getdb("GFOOD_B")
        try:
            sql = f"""
                SELECT CO, BCO, BUNAME, SA
                FROM RECIPE
                WHERE BCO IN ({','.join(['%s'] * len(VEGE_BCO_LIST))})
                  AND CO IN ({','.join(['%s'] * len(co_list))})
            """
            params = VEGE_BCO_LIST + co_list
            df_recipe = runquery(cur, sql, params)
        finally:
            closedb(conn)

        if df_recipe is None or df_recipe.empty:
            conn_d, cur_d = getdb(DB_NAME)
            try:
                runquery(cur_d,
                         "DELETE FROM DASHBOARD_VEGE WHERE CONVERT(DATE, sdate) = %s",
                         [sdate_str])
            finally:
                closedb(conn_d)
            return

        df_recipe.columns = [c.upper() for c in df_recipe.columns]
        df_recipe["CO"] = df_recipe["CO"].astype(str).str.strip()
        df_recipe["BCO"] = df_recipe["BCO"].astype(str).str.strip()

        # STEP 3) JOIN
        df = df_order.merge(df_recipe, on="CO", how="inner")
        if df.empty:
            return

        # STEP 4) PLAN_KG
        df["PLAN_KG"] = df["PRODUCTION_PLAN"].fillna(0).astype(float) * df["PKG"].fillna(0).astype(float)
        df = df[df["PLAN_KG"] > 0]
        if df.empty:
            return

        # STEP 5) VEGE_KG
        df["VEGE_KG"] = df["PLAN_KG"] * df["SA"].fillna(0).astype(float)
        df = df[df["VEGE_KG"] > 0]
        if df.empty:
            return

        # STEP 6) 그룹핑
        grouped = df.groupby(["BCO", "BUNAME"], as_index=False)["VEGE_KG"].sum()

        # 기존 VEGE 삭제
        conn_d, cur_d = getdb(DB_NAME)
        try:
            runquery(cur_d,
                     "DELETE FROM DASHBOARD_VEGE WHERE CONVERT(DATE, sdate) = %s",
                     [sdate_str])
        finally:
            closedb(conn_d)

        # INSERT 준비
        rows = []
        for _, r in grouped.iterrows():
            qty_int = int(round(float(r["VEGE_KG"] or 0)))
            if qty_int <= 0:
                continue

            stock_val = get_stock_from_pan(str(r["BCO"]), sdate_str)

            rows.append({
                "uname": r["BUNAME"],
                "co": r["BCO"],
                "sdate": sdate_dt,
                "created_time": now,
                "stock": stock_val,
                "order_qty": qty_int,
                "order_qty_after": qty_int,
                "prepro_qty": 0,
                "ipgo_qty": 0,
            })

        if rows:
            self._insert_dashboard_vege_rows(rows)

    #9. DB Insert/Update/Delete
    def on_click_add_dummy_rows(self):
        # 1) 제품 리스트 관리창 먼저 띄우기
        dlg = ProductListDialog(self, self.product_list)
        if dlg.exec_() != QDialog.Accepted:
            # 취소 누르면 아무 것도 안 함
            return

        # 다이얼로그에서 확정된 리스트 갱신 (프로그램 켜져 있는 동안 유지)
        self.product_list = dlg.get_product_list()

        if not self.product_list:
            QMessageBox.information(self, "안내", "PRODUCT_LIST가 비어 있습니다.")
            return

        # 2) 기존 로직 수행 (PRODUCT_LIST → self.product_list 로 변경)
        qdate: QDate = self.ui.dateEdit.date()
        sdate_dt = datetime(qdate.year(), qdate.month(), qdate.day(), 0, 0, 0)
        sdate_str = qdate.toString("yyyy-MM-dd")
        now = datetime.now()

        rows = []

        conn_master, cur_master = getdb("GFOOD_B")
        try:
            for base_co, vendor in self.product_list:
                base_co = str(base_co).strip()
                if not base_co:
                    continue

                master_co = base_co

                df_master = runquery(
                    cur_master,
                    """
                    SELECT TOP 1 CO, UNAME, PACKG, PACSU
                    FROM MASTER
                    WHERE CO = %s
                    """,
                    [master_co],
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
                    except:
                        try:
                            pkg = float(str(packg_raw).replace("KG", "").replace("kg", "").strip())
                        except:
                            pkg = 0.0

                pacsu_raw = m.get("PACSU", 1)
                try:
                    pacsu = int(pacsu_raw if pacsu_raw not in (None, "") else 1)
                except:
                    pacsu = 1
                if pacsu <= 0:
                    pacsu = 1

                prev_residue = get_prev_residue_from_today(base_co)

                # 🔹 벤더별 발주 팩 수 공통 계산
                order_qty_packs = calc_order_qty_packs(
                    base_co=base_co,
                    vendor=vendor,
                    sdate_str=sdate_str,
                    pacsu=pacsu,
                )

                produced_qty = get_produced_qty_packs(base_co, sdate_str, pacsu)

                rows.append({
                    "bigo": "",
                    "sdate": sdate_dt,
                    "created_time": now,
                    "id": "인길환",
                    "rname": vendor,
                    "uname": uname,
                    "co": base_co,
                    "pkg": pkg,
                    "order_qty": order_qty_packs,
                    "order_qty_after": order_qty_packs,
                    "prev_residue": prev_residue,
                    "production_plan": 0,
                    "produced_qty": produced_qty,
                    "today_residue": 0,
                })

        finally:
            closedb(conn_master)

        if not rows:
            QMessageBox.information(self, "안내", "INSERT할 데이터가 없습니다.")
            return

        try:
            self._insert_dashboard_rows(rows)
            self._dashboard_raw_from_dashboard()
            self._dashboard_sauce_from_dashboard()
            self._dashboard_vege_from_dashboard()

            QMessageBox.information(
                self,
                "완료",
                f"제품 {len(rows)}행, 원료/소스/야채 대시보드 재생성 완료."
            )
            if hasattr(self.ui, "tabWidget") and self.ui.tabWidget.currentIndex() == 0:
                self._load_product_tab()

        except Exception as e:
            QMessageBox.critical(self, "에러", str(e))

    def _insert_dashboard_rows(self, rows):
        conn, cur = getdb(DB_NAME)
        try:
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
        finally:
            closedb(conn)

    def _insert_dashboard_raw_rows(self, rows):
        """
        DASHBOARD_RAW 테이블에 원료(정선) 데이터를 INSERT.
        rows: {
            "uname", "co", "sdate", "created_time",
            "stock", "order_qty", "order_qty_after",
            "prepro_qty", "ipgo_qty"
        } 딕셔너리 리스트
        """
        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                INSERT INTO DASHBOARD_RAW (
                    uname, co, sdate, created_time,
                    stock, order_qty, order_qty_after,
                    prepro_qty, ipgo_qty
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """
            for r in rows:
                params = [
                    r["uname"], r["co"], r["sdate"], r["created_time"],
                    r["stock"], r["order_qty"], r["order_qty_after"],
                    r["prepro_qty"], r["ipgo_qty"],
                ]
                runquery(cur, sql, params)
        finally:
            closedb(conn)

    def _insert_dashboard_sauce_rows(self, rows):
        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                INSERT INTO DASHBOARD_SAUCE (
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
        finally:
            closedb(conn)

    def _insert_dashboard_vege_rows(self, rows):
        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                INSERT INTO DASHBOARD_VEGE (
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
        finally:
            closedb(conn)

    def on_click_show_log_dialog(self):
        dlg = DashboardLogDialog(self)
        dlg.exec_()

    def on_click_delete_selected_products(self):
        """
        제품 탭(tableWidget1)에서 선택한 제품만 삭제.
        삭제 기준을 PK → UNAME(제품명)으로 변경.
        ORDER_DASHBOARD에서 해당 날짜(sdate) 기준 같은 UNAME을 삭제.
        """
        table = self.ui.tableWidget1
        selected_rows = sorted({idx.row() for idx in table.selectedIndexes()})

        if not selected_rows:
            QMessageBox.information(self, "안내", "삭제할 제품을 선택하세요.")
            return

        # 🔥 UNAME은 1번 컬럼
        UNAME_COL = 1

        # 선택된 UNAME 목록
        uname_list = []
        for r in selected_rows:
            item = table.item(r, UNAME_COL)
            if item:
                uname_list.append(item.text().strip())

        if not uname_list:
            QMessageBox.warning(self, "오류", "선택한 행에서 제품명(UNAME)을 찾을 수 없습니다.")
            return

        # 중복제거
        uname_list = list(set(uname_list))

        reply = QMessageBox.question(
            self,
            "삭제 확인",
            f"선택한 {len(uname_list)}개의 제품을 삭제하시겠습니까?\n"
            f"(ORDER_DASHBOARD 삭제 + RAW/SAUCE/VEGE 재집계)",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        # 현재 날짜
        qdate = self.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")

        # 🔥 ORDER_DASHBOARD 삭제 (UNAME 기준)
        conn, cur = getdb(DB_NAME)
        try:
            placeholders = ", ".join(["%s"] * len(uname_list))
            sql = f"""
                DELETE FROM ORDER_DASHBOARD
                WHERE CONVERT(DATE, sdate) = %s
                  AND UNAME IN ({placeholders})
            """
            params = [sdate_str] + uname_list
            runquery(cur, sql, params)
        finally:
            closedb(conn)

        # 🔁 RAW/SAUCE/VEGE 재집계
        try:
            recalc_dashboard_raw_keep_manual(sdate_str)
            recalc_dashboard_sauce_keep_manual(sdate_str)
            recalc_dashboard_vege_keep_manual(sdate_str)
        except Exception as e:
            QMessageBox.critical(self, "재집계 오류", str(e))
            return

        QMessageBox.information(self, "완료", "선택한 제품이 삭제되었으며 재집계가 완료되었습니다.")

        # 새로고침
        self._load_product_tab()

    def on_click_delete_rows(self):
        qdate = self.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")

        reply = QMessageBox.question(
            self,
            "삭제 확인",
            f"{sdate_str} 데이터 전체를 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        conn, cur = getdb(DB_NAME)
        try:
            sqls = [
                "DELETE FROM ORDER_DASHBOARD WHERE CONVERT(DATE, sdate) = %s",
                "DELETE FROM DASHBOARD_RAW     WHERE CONVERT(DATE, sdate) = %s",
                "DELETE FROM DASHBOARD_SAUCE   WHERE CONVERT(DATE, sdate) = %s",
                "DELETE FROM DASHBOARD_VEGE    WHERE CONVERT(DATE, sdate) = %s"
            ]

            for sql in sqls:
                runquery(cur, sql, [sdate_str])

        finally:
            closedb(conn)

        QMessageBox.information(self, "완료", f"{sdate_str} 자료 삭제 완료!")

        # UI 초기화
        self.ui.tableWidget1.setRowCount(0)
        self.ui.tableWidget2.setRowCount(0)
        self.ui.tableWidget3.setRowCount(0)
        self.ui.tableWidget4.setRowCount(0)

    # -----------------------------------------------------
    # 생산량(produced_qty) 재계산 & UPDATE
    # -----------------------------------------------------
    def on_click_update_product(self):
        """
        btn_update_product 클릭 시,
        현재 dateEdit 기준으로 ORDER_DASHBOARD.produced_qty 갱신.

        기준:
          (GFOOD_B..PAN)
          CH = 'C'
          AND JNAME = '공장(양념육)'
          AND CO = dashboard.CO
          AND PDATE = dateEdit 날짜
        → PAN 합(박스) × PACSU = 생산 팩 수
        """
        try:
            qdate: QDate = self.ui.dateEdit.date()
            sdate_str = qdate.toString("yyyy-MM-dd")

            # 1) 해당 날짜의 CO 리스트 조회
            try:
                conn, cur = getdb(DB_NAME)
            except Exception as e:
                QMessageBox.critical(self, "DB 오류", f"{DB_NAME} 연결 실패:\n{e}")
                return

            try:
                sql = """
                    SELECT DISTINCT co
                    FROM ORDER_DASHBOARD
                    WHERE CONVERT(DATE, sdate) = %s
                """
                df = runquery(cur, sql, [sdate_str])
            except Exception as e:
                closedb(conn)
                QMessageBox.critical(self, "DB 오류", f"ORDER_DASHBOARD 조회 실패:\n{e}")
                return
            finally:
                try:
                    closedb(conn)
                except Exception as e:
                    print(f"[WARN] {DB_NAME} 연결 종료 실패: {e}")

            if df is None or len(df) == 0:
                QMessageBox.information(self, "안내", f"{sdate_str} 기준 데이터가 없습니다.")
                return

            df = pd.DataFrame(df)
            co_col = df.columns[0]

            # 2) UPDATE 루프
            try:
                conn_u, cur_u = getdb(DB_NAME)
            except Exception as e:
                QMessageBox.critical(self, "DB 오류", f"{DB_NAME} 연결 실패(UPDATE):\n{e}")
                return

            updated_cnt = 0
            try:
                for co_val in df[co_col]:
                    co_str = str(co_val).strip()
                    if not co_str:
                        continue

                    # PACSU 조회
                    try:
                        pacsu = get_pacsu_by_co(co_str)
                    except Exception as e:
                        print(f"[ERROR] get_pacsu_by_co({co_str}) 예외: {e}")
                        pacsu = 1

                    # 생산 팩 수 계산
                    produced_qty = get_produced_qty_packs(co_str, sdate_str, pacsu)

                    # produced_qty 업데이트
                    try:
                        runquery(
                            cur_u,
                            """
                            UPDATE ORDER_DASHBOARD
                            SET produced_qty = %s
                            WHERE CONVERT(DATE, sdate) = %s
                              AND co = %s
                            """,
                            [produced_qty, sdate_str, co_str],
                        )
                        updated_cnt += 1
                    except Exception as e:
                        print(f"[ERROR] produced_qty UPDATE 실패 co={co_str}: {e}")
                        # 한 행 실패해도 나머지는 계속 진행
                        continue
            finally:
                try:
                    closedb(conn_u)
                except Exception as e:
                    print(f"[WARN] {DB_NAME} 연결 종료 실패(UPDATE): {e}")

            QMessageBox.information(
                self,
                "완료",
                f"{sdate_str} 기준 {updated_cnt}개 품목의 생산 팩수(produced_qty)를 갱신했습니다.",
            )
            self._load_product_tab()

        except Exception as e:
            # Qt 이벤트 루프까지 예외 안 올라가도록 최종 방어
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "예외 발생", f"생산량 갱신 중 예외가 발생했습니다.\n{e}")

    # -----------------------------------------------------
    # DASHBOARD_LOG INSERT
    # -----------------------------------------------------
    def _insert_dashboard_log(
        self,
        cur,
        sdate_str: str,
        co: str,
        vendor: str,
        qty_before: int,
        qty_after: int,
    ):
        """
        DASHBOARD_LOG에 변경 이력 기록.
        """
        now = datetime.now()
        sql = """
            INSERT INTO DASHBOARD_LOG (
                update_time, id, sdate, co, vendor, qty_before, qty_after
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        params = [
            now,
            "인길환",
            sdate_str,
            co,
            vendor,
            qty_before,
            qty_after,
        ]
        runquery(cur, sql, params)

    # -----------------------------------------------------
    # 발주량 재계산 & UPDATE
    # -----------------------------------------------------
    def on_click_update_order_qty_after(self):
        """
        선택 날짜의 모든 제품에 대해 '최종 발주량(order_qty_after)'을 재계산하여 UPDATE.
        - 홈플러스: 박스 수 × PACSU → 팩 수
        - 이마트: 팩 수 × PACSU → 최종 팩 수
        - 마켓컬리: 박스 수 (PACSU 적용 X)
        업데이트 후 DASHBOARD_LOG 기록.
        """
        qdate: QDate = self.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")

        if not PRODUCT_LIST:
            QMessageBox.information(self, "안내", "PRODUCT_LIST가 비어 있습니다.")
            return

        conn, cur = getdb(DB_NAME)
        try:
            for base_co, vendor in PRODUCT_LIST:
                base_co = str(base_co).strip()

                # PACSU 조회 (박스 → 팩 환산기)
                pacsu = get_pacsu_by_co(base_co)
                if pacsu is None or pacsu <= 0:
                    pacsu = 1

                # 🔹 벤더별 발주 팩 수 공통 계산 (코스온 포함)
                new_qty_packs = int(
                    calc_order_qty_packs(
                        base_co=base_co,
                        vendor=vendor,
                        sdate_str=sdate_str,
                        pacsu=pacsu,
                    )
                )

                # ─────────────────────────────────────────────
                # 2) 기존 order_qty_after 조회
                # ─────────────────────────────────────────────
                df_before = runquery(
                    cur,
                    """
                    SELECT ISNULL(SUM(order_qty_after), 0) AS qty
                    FROM ORDER_DASHBOARD
                    WHERE CONVERT(DATE, sdate) = %s
                      AND co = %s
                    """,
                    [sdate_str, base_co]
                )

                qty_before = int(df_before.iloc[0]["qty"]) if (df_before is not None and not df_before.empty) else 0

                # ─────────────────────────────────────────────
                # 3) UPDATE
                # ─────────────────────────────────────────────
                runquery(
                    cur,
                    """
                    UPDATE ORDER_DASHBOARD
                    SET order_qty_after = %s
                    WHERE CONVERT(DATE, sdate) = %s
                      AND co = %s
                    """,
                    [new_qty_packs, sdate_str, base_co]
                )

                # ─────────────────────────────────────────────
                # 4) 로그 INSERT
                # ─────────────────────────────────────────────
                self._insert_dashboard_log(
                    cur,
                    sdate_str=sdate_str,
                    co=base_co,
                    vendor=vendor,
                    qty_before=qty_before,
                    qty_after=new_qty_packs,
                )

        finally:
            closedb(conn)

        recalc_dashboard_raw_keep_manual(sdate_str)
        recalc_dashboard_sauce_keep_manual(sdate_str)
        recalc_dashboard_vege_keep_manual(sdate_str)

        QMessageBox.information(
            self,
            "완료",
            "모든 제품의 최종 발주량(order_qty_after)이 재계산되었고,\n"
            "원료/소스/야채 대시보드도 최신 기준으로 반영되었습니다."
        )

        # 제품 탭 갱신
        self._load_product_tab()

    def on_click_complete_product(self):
        """
        제품 탭에서 선택한 행의 work_state 값을 '완료'로 업데이트하고,
        테이블을 즉시 반영한다.
        """
        table = self.ui.tableWidget1

        # 선택된 행 확인
        selected_rows = sorted({idx.row() for idx in table.selectedIndexes()})
        if not selected_rows:
            QMessageBox.information(self, "안내", "완료 처리할 제품 행을 선택하세요.")
            return

        # 여러개 선택 가능 → 하나씩 처리
        qdate = self.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")

        conn, cur = getdb(DB_NAME)

        try:
            for row in selected_rows:
                item = table.item(row, 0)  # PK 저장된 첫 컬럼
                if not item:
                    continue

                pk = item.data(Qt.UserRole)
                if not pk:
                    continue

                # ─────────────── UPDATE 실행 ───────────────
                runquery(
                    cur,
                    """
                    UPDATE ORDER_DASHBOARD
                    SET work_status = '완료'
                    WHERE PK = %s
                    """,
                    [pk],
                )

                # ─────────────── UI 반영 ───────────────
                # 구성상 work_state 컬럼이 마지막(예: COL_WORK_STATE)
                work_state_col = COL_WORK_STATUS  # 14번
                item_ws = table.item(row, work_state_col)
                if item_ws:
                    table.blockSignals(True)
                    item_ws.setText("완료")
                    table.blockSignals(False)

                # 정확하게 다시 계산하려면:
                self._refresh_single_row(pk)

        finally:
            closedb(conn)

        QMessageBox.information(self, "완료", "선택된 제품의 작업 상태가 '완료'로 변경되었습니다.")


    def on_click_export_excel(self):
        """
        tableWidget1~4 내용을 각각 시트로 생성하여 하나의 Excel 파일로 출력.
        시트명: 제품 / 원료 / 소스 / 야채
        동일한 서식 적용.
        """
        import pandas as pd
        from datetime import datetime
        import os
        from openpyxl.utils import get_column_letter
        from openpyxl.styles import Font, Alignment, Border, Side

        self._load_product_tab()
        self._load_raw_tab()
        self._load_sauce_tab()
        self._load_vege_tab()

        # ⬇️ 시트 이름과 tableWidget 매핑
        sheet_map = [
            ("제품", self.ui.tableWidget1),
            ("원료", self.ui.tableWidget2),
            ("소스", self.ui.tableWidget3),
            ("야채", self.ui.tableWidget4),
        ]

        # 데이터 있는 테이블이 하나라도 있는지 확인
        has_data = any(t.rowCount() > 0 and t.columnCount() > 0 for _, t in sheet_map)
        if not has_data:
            QMessageBox.information(self, "안내", "엑셀로 내보낼 데이터가 없습니다.")
            return

        # 저장 파일명 기본값
        today_str = datetime.now().strftime("%Y%m%d_%H%M")
        default_name = f"발주현황_{today_str}.xlsx"

        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        default_path = os.path.join(desktop, default_name)

        path, _ = QFileDialog.getSaveFileName(
            self,
            "전체 발주현황 엑셀 저장",
            default_path,
            "Excel Files (*.xlsx);;All Files (*)",
        )
        if not path:
            return

        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        # ---------------------------------------
        # 파일 생성
        # ---------------------------------------
        try:
            with pd.ExcelWriter(path, engine="openpyxl") as writer:

                for sheet_name, table in sheet_map:
                    row_count = table.rowCount()
                    col_count = table.columnCount()

                    if row_count == 0 or col_count == 0:
                        continue  # 데이터 없으면 스킵

                    # 1) 헤더 추출
                    headers = []
                    for c in range(col_count):
                        header_item = table.horizontalHeaderItem(c)
                        headers.append(header_item.text() if header_item else f"열{c + 1}")

                    # 2) 데이터 추출
                    data = []
                    for r in range(row_count):
                        row_vals = []
                        for c in range(col_count):
                            item = table.item(r, c)
                            row_vals.append(item.text() if item else "")
                        data.append(row_vals)

                    # 3) DataFrame → Excel 저장
                    df = pd.DataFrame(data, columns=headers)
                    df.to_excel(writer, sheet_name=sheet_name, index=False)

                    # 4) 스타일 적용
                    wb = writer.book
                    ws = wb[sheet_name]

                    header_font = Font(bold=True)
                    header_align = Alignment(horizontal="center", vertical="center")
                    left_align = Alignment(horizontal="left", vertical="center")
                    right_align = Alignment(horizontal="right", vertical="center")
                    thin = Side(border_style="thin", color="000000")
                    border = Border(left=thin, right=thin, top=thin, bottom=thin)

                    # (A) 헤더 스타일 + 열 너비 자동
                    for col_idx, col_name in enumerate(headers, start=1):
                        cell = ws.cell(row=1, column=col_idx)
                        cell.font = header_font
                        cell.alignment = header_align
                        cell.border = border

                        max_len = len(str(col_name))
                        col_series = df[col_name].astype(str)
                        if not col_series.empty:
                            max_len = max(max_len, col_series.map(len).max())
                        ws.column_dimensions[get_column_letter(col_idx)].width = max_len + 2

                    # (B) 데이터 스타일 (1,2번 열은 왼쪽 / 나머지는 오른쪽)
                    for row_idx in range(2, ws.max_row + 1):
                        for col_idx in range(1, ws.max_column + 1):
                            cell = ws.cell(row=row_idx, column=col_idx)
                            cell.border = border
                            if col_idx in (1, 2):
                                cell.alignment = left_align
                            else:
                                cell.alignment = right_align

            QMessageBox.information(self, "완료", f"엑셀 파일이 저장되었습니다.\n{path}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "오류", f"엑셀 저장 중 오류가 발생했습니다.\n{e}")


# ---------------------------------------------------------
# 실행
# ---------------------------------------------------------
if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        check_version_and_update(PROGRAM_NAME, CURRENT_VERSION)
        w = OrderDashboardWidget()
        w.showMaximized()
        sys.exit(app.exec_())
    except Exception:
        import traceback

        print("\n===== 실행 중 오류 발생 =====")
        print(traceback.format_exc())
        input("\n엔터를 누르면 닫힙니다...")
