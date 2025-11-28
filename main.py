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
    QDateEdit,
    QDateTimeEdit,
    QTableWidget,
    QHeaderView,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFileDialog,
    QInputDialog,
    QLineEdit,
    QComboBox
)
from PyQt5.QtGui import QBrush, QColor, QFont

from UTIL.db_handler import getdb, runquery, closedb
from ci_cd.updatedown import check_version_and_update
from oracle import get_box_summary
from UTIL.utils_qt import apply_table_style

from UI.dashboard import Ui_Form

CURRENT_VERSION = "a-0010"
PROGRAM_NAME = "factory_dashboard"

DB_NAME = "GP"
IS_ADMIN = False

# 상품 리스트: (코드, 업체명)
PRODUCT_LIST = [
    ("511476", "코스온"),
    ("511379", "코스온"),
    ("511467", "코스온"),
    ("511418", "이마트"),
    ("502427", "이마트"),
    ("502341", "이마트"),
    ("520563", "이마트"),
    ("520651", "이마트"),
    ("520328", "이마트"),
    ("520712", "이마트"),
    ("520449", "홈플러스"),
    ("511540", "마켓컬리"),
    ("502415", "마켓컬리"),
]
VENDOR_CHOICES = ["코스온", "이마트", "홈플러스", "마켓컬리"]

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
COL_PRE_PROD = 8
COL_PLAN = 9
COL_PLAN_KG = 10
COL_CUR_PROD = 11
COL_REMAIN = 12
COL_TODAY_RES = 13


class OrderDashboardWidget(QWidget):

    #1. 초기화 & 기본 기능
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Form()
        self.ui.setupUi(self)

        # 🔹 프로그램이 켜져있는 동안 유지될 제품 리스트 상태
        self.product_list = list(PRODUCT_LIST)

        self._fullscreen_mode = False
        self.ui.control_frame.hide()

        # 날짜 오늘로 세팅
        self.ui.dateEdit.setDate(QDate.currentDate())
        if hasattr(self.ui, "dateText"):
            self.ui.dateText.setText(self.ui.dateEdit.date().toString("yyyy-MM-dd"))
        self._product_table_item_changed_connected = False
        self._raw_table_item_changed_connected = False
        self._sauce_table_item_changed_connected = False
        self._vege_table_item_changed_connected = False

        # 테이블 스타일 (공통 베이스 사용)
        if hasattr(self.ui, "tableWidget1"):
            self._setup_table_base(self.ui.tableWidget1)

        if hasattr(self.ui, "tableWidget2"):
            self._setup_table_base(self.ui.tableWidget2)

        if hasattr(self.ui, "tableWidget3"):
            self._setup_table_base(self.ui.tableWidget3)

        if hasattr(self.ui, "tableWidget4"):
            self._setup_table_base(self.ui.tableWidget4)
        # 버튼/시그널 연결
        self.ui.btn_view.clicked.connect(self.on_click_toggle_fullscreen)

        if hasattr(self.ui, "btn_imsi1"):
            self.ui.btn_imsi1.clicked.connect(self.oracle_test)

        if hasattr(self.ui, "btn_prev"):
            self.ui.btn_prev.clicked.connect(self.on_click_prev_date)

        if hasattr(self.ui, "btn_next"):
            self.ui.btn_next.clicked.connect(self.on_click_next_date)

        if hasattr(self.ui, "btn_product"):
            self.ui.btn_product.clicked.connect(self.on_click_tab_product)

        if hasattr(self.ui, "btn_raw"):
            self.ui.btn_raw.clicked.connect(self.on_click_tab_raw)

        if hasattr(self.ui, "btn_sauce"):
            self.ui.btn_sauce.clicked.connect(self.on_click_tab_sauce)

        if hasattr(self.ui, "btn_vege"):
            self.ui.btn_vege.clicked.connect(self.on_click_tab_vege)

        if hasattr(self.ui, "btn_add"):
            self.ui.btn_add.clicked.connect(self.on_click_add_dummy_rows)

        if hasattr(self.ui, "btn_del"):
            self.ui.btn_del.clicked.connect(self.on_click_delete_rows)

        if hasattr(self.ui, "btn_del_row"):
            self.ui.btn_del_row.clicked.connect(self.on_click_delete_selected_products)

        if hasattr(self.ui, "btn_update"):
            self.ui.btn_update.clicked.connect(self.on_click_update_order_qty_after)

        if hasattr(self.ui, "btn_log"):
            self.ui.btn_log.clicked.connect(self.on_click_show_log_dialog)

        if hasattr(self.ui, "btn_excel"):
            self.ui.btn_excel.clicked.connect(self.on_click_export_excel)

        if hasattr(self.ui, "btn_admin"):
            self.ui.btn_admin.clicked.connect(self.on_click_toggle_admin)

        # 🔹 신규: 생산량(produced_qty) 갱신 버튼
        if hasattr(self.ui, "btn_update_product"):
            self.ui.btn_update_product.clicked.connect(self.on_click_update_product)

        # 탭 이벤트
        if hasattr(self.ui, "tabWidget"):
            self.ui.tabWidget.currentChanged.connect(self.on_tab_changed)

        # 날짜 변경 이벤트
        if isinstance(self.ui.dateEdit, QDateEdit):
            self.ui.dateEdit.dateChanged.connect(self.on_date_changed)
        elif isinstance(self.ui.dateEdit, QDateTimeEdit):
            self.ui.dateEdit.dateTimeChanged.connect(lambda _: self.on_date_changed())

        # 최초 로딩
        self._load_product_tab()

    def oracle_test(self):
        print("oracle test")
        summary = get_box_summary()
        QMessageBox.information(
            self,
            "오라클 조회 결과",
            f"팩수: {summary['PACK']}\n총 박스수: {summary['TOTAL_BOXES']}\n박스 중량(kg): {summary['BOX_WEIGHT']}"
        )

    @staticmethod
    def _fmt(val) -> str:
        """
        숫자(int/float/str) → '1,234' 형식으로 포맷
        숫자가 아니면 그대로 문자열 반환
        """
        try:
            # 👉 먼저 실제 숫자인 경우 바로 처리
            if isinstance(val, int):
                return f"{val:,}"

            if isinstance(val, float):
                # 소수점이 있으면 자연스럽게 처리 / 정수면 소수 제거
                if val.is_integer():
                    return f"{int(val):,}"
                else:
                    return f"{val:,.1f}"

            # 👉 문자열인 경우 처리
            text = str(val).replace(",", "").strip()

            # 문자열이지만 int/float로 변환 가능할 때
            if "." in text:
                num = float(text)
                if num.is_integer():
                    return f"{int(num):,}"
                else:
                    return f"{num:,.1f}"
            else:
                num = int(text)
                return f"{num:,}"

        except:
            # 숫자로 볼 수 없는 경우 → 그대로 텍스트 반환
            return str(val)

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
            if IS_ADMIN:
                self.ui.control_frame.show()

        # 레이아웃 전체 다시 배치
        self.layout().update()

    def _ask_admin_password(self) -> bool:
        pw, ok = QInputDialog.getText(
            self,
            "관리자 인증",
            "관리자 비밀번호를 입력하세요:",
            QLineEdit.Password
        )

        if not ok:
            return False

        return pw == "1004"

    def on_click_toggle_admin(self):
        global IS_ADMIN

        if IS_ADMIN:
            IS_ADMIN = False
            self.ui.control_frame.hide()
            return

        if self._ask_admin_password():
            IS_ADMIN = True
            self.ui.control_frame.show()
        else:
            QMessageBox.warning(self, "인증 실패", "비밀번호가 올바르지 않습니다.")

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
        if not hasattr(self.ui, "tabWidget"):
            return

        # 🔥 1) dateText 갱신
        qdate = self.ui.dateEdit.date()
        date_str = qdate.toString("yyyy-MM-dd")
        if hasattr(self.ui, "dateText"):
            self.ui.dateText.setText(date_str)

        # 🔥 2) 기존 탭별 데이터 로딩
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

    def _setup_product_headers(self, table: QTableWidget):
        headers = [
            "업체명", "품명", "팩중량", "발주량", "최종발주량",
            "팩 차이", "전일 잔피", "생산 팩수", "선 생산",
            "생산계획", "팩수 to kg", "현재생산량", "남은생산량", "당일 잔피",
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

            if col == COL_PRE_PROD:
                item.setBackground(QBrush(header_edit))
            elif col in (COL_CUR_PROD, COL_REMAIN):
                item.setBackground(QBrush(header_live))
            else:
                item.setBackground(QBrush(header_normal))

        # -----------------------------------------------------
        # 헤더 설정 (원료 탭)
        # -----------------------------------------------------

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

        if editable:
            item.setFlags(item.flags() | Qt.ItemIsEditable)
            item.setForeground(QBrush(QColor("#777777")))
        else:
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)

        if foreground is not None:
            item.setForeground(QBrush(foreground))


        return item

        # -----------------------------------------------------
        # 제품 탭 셀 생성 (공통 셀 생성 재사용)
        # -----------------------------------------------------

    def _create_product_item(self, text: str, pk: int, col: int):
        # 정렬
        if col in (COL_VENDOR, COL_PRODUCT):
            alignment = Qt.AlignLeft | Qt.AlignVCenter
        else:
            alignment = Qt.AlignRight | Qt.AlignVCenter

        # 밑줄 (발주량/최종발주량)
        underline = col in (COL_ORDER, COL_FINAL_ORDER)

        # 편집 가능 컬럼
        editable_cols = {COL_PRE_PROD, COL_TODAY_RES}
        editable = col in editable_cols

        # 글자 색상 (현재 생산량/남은 생산량 등)
        foreground = QColor("#0066cc") if col in (COL_CUR_PROD, COL_REMAIN) else None

        return self._create_cell(
            text=text,
            pk=pk,
            alignment=alignment,
            editable=editable,
            underline=underline,
            foreground=foreground,
        )

    def _create_raw_item(self, text: str, pk: int, col: int):
        # 정렬 규칙
        alignment = Qt.AlignLeft | Qt.AlignVCenter if col == 0 else Qt.AlignRight | Qt.AlignVCenter

        editable = col in (1, 4, 6)

        # 강조 색상 (예상부족량이 음수면 빨간색)
        foreground = None
        if col == 4:  # 예상부족량
            try:
                if int(text) < 0:
                    foreground = QColor("#cc0000")  # 빨간
            except:
                pass

        item = self._create_cell(
            text=text,
            pk=pk,
            alignment=alignment,
            editable=editable,
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

    #5. 데이터 로딩
    def _load_product_tab(self):
        table = self.ui.tableWidget1

        if not hasattr(self.ui, "dateEdit"):
            return

        qdate: QDate = self.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")

        # 🔹 업체명 → 품명 → PK 순 정렬
        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                SELECT
                    PK, co, rname, uname, pkg,
                    order_qty, order_qty_after,
                    prev_residue, pre_production_qty,
                    produced_qty, remain_production_qty,
                    today_residue
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
        previous_rname = None

        for row_idx, row in enumerate(df.itertuples(index=False)):
            pk = int(row.PK)
            co_val = str(row.CO).strip()  # 🔥 DB에서 가져온 CO

            rname = row.RNAME.strip() if row.RNAME else ""
            uname = row.UNAME.strip() if row.UNAME else ""
            pkg = float(row.PKG)
            order_qty = int(row.ORDER_QTY)
            order_qty_after = int(row.ORDER_QTY_AFTER)
            prev_residue = int(row.PREV_RESIDUE)
            pre_production_qty = int(row.PRE_PRODUCTION_QTY)
            produced_qty = int(row.PRODUCED_QTY)
            today_residue = int(row.TODAY_RESIDUE)

            # 계산 필드
            diff = order_qty_after - order_qty
            diff_display = "" if diff == 0 else str(diff)
            production_qty = max(order_qty_after - prev_residue, 0)
            plan_qty = production_qty + pre_production_qty
            plan_kg = plan_qty * pkg
            remain_qty = plan_qty - produced_qty

            values = [
                rname,
                uname,
                self._fmt(f"{pkg:.1f}"),
                self._fmt(order_qty),
                self._fmt(order_qty_after),
                self._fmt(diff_display),
                self._fmt(prev_residue),
                self._fmt(production_qty),
                self._fmt(pre_production_qty),
                self._fmt(plan_qty),
                self._fmt(f"{plan_kg:.1f}"),
                self._fmt(produced_qty),
                self._fmt(remain_qty),
                self._fmt(today_residue),
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

    def _load_raw_tab(self):
        if not hasattr(self.ui, "tableWidget2"):
            return

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
                self._fmt(stock),  # 1 재고량
                self._fmt(order_qty),  # 2 예상발주량
                self._fmt(order_qty_after),  # 3 최종발주량(동일 값)
                self._fmt(prepro_qty),  # 4 선 생산량
                self._fmt(expected_short),  # 5 예상부족량
                self._fmt(ipgo_qty),  # 6 입고예정량
                self._fmt(expected_stock),  # 7 예상재고
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
        if not hasattr(self.ui, "tableWidget3"):
            return

        table = self.ui.tableWidget3

        if not hasattr(self.ui, "dateEdit"):
            return

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
                self._fmt(stock),  # 1
                self._fmt(order_qty),  # 2 예상발주량
                self._fmt(order_qty_after),  # 3 최종발주량
                self._fmt(prepro_qty),  # 4
                self._fmt(expected_short),  # 5
                self._fmt(ipgo_qty),  # 6
                self._fmt(expected_stock),  # 7
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
        if not hasattr(self.ui, "tableWidget4"):  # 너 UI에서 tableWidget4 = 야채 탭이라고 가정
            return

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
                self._fmt(stock),
                self._fmt(order_qty),
                self._fmt(order_qty_after),
                self._fmt(prepro_qty),
                self._fmt(expected_short),
                self._fmt(ipgo_qty),
                self._fmt(expected_stock),
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
                    prev_residue, pre_production_qty,
                    produced_qty, remain_production_qty,
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

        production_qty = max(r["ORDER_QTY_AFTER"] - r["PREV_RESIDUE"], 0)
        plan_qty = production_qty + r["PRE_PRODUCTION_QTY"]
        plan_kg = plan_qty * r["PKG"]
        remain_qty = plan_qty - r["PRODUCED_QTY"]
        diff = r["ORDER_QTY_AFTER"] - r["ORDER_QTY"]

        values = {
            COL_VENDOR: r["RNAME"],
            COL_PRODUCT: r["UNAME"],
            COL_PKG: self._fmt(f"{r['PKG']:.1f}"),
            COL_ORDER: self._fmt(r["ORDER_QTY"]),
            COL_FINAL_ORDER: self._fmt(r["ORDER_QTY_AFTER"]),
            COL_DIFF: "" if diff == 0 else self._fmt(diff),
            COL_PREV_RES: self._fmt(r["PREV_RESIDUE"]),
            COL_PRODUCTION: self._fmt(production_qty),
            COL_PRE_PROD: self._fmt(r["PRE_PRODUCTION_QTY"]),
            COL_PLAN: self._fmt(plan_qty),
            COL_PLAN_KG: self._fmt(f"{plan_kg:.1f}"),
            COL_CUR_PROD: self._fmt(r["PRODUCED_QTY"]),
            COL_REMAIN: self._fmt(remain_qty),
            COL_TODAY_RES: self._fmt(r["TODAY_RESIDUE"]),
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
            self._fmt(stock),
            self._fmt(order_qty),
            self._fmt(order_qty_after),
            self._fmt(prepro_qty),
            self._fmt(expected_short),
            self._fmt(ipgo_qty),
            self._fmt(expected_stock),
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
            self._fmt(stock),
            self._fmt(order_qty),
            self._fmt(order_qty_after),
            self._fmt(prepro_qty),
            self._fmt(expected_short),
            self._fmt(ipgo_qty),
            self._fmt(expected_stock),
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
            self._fmt(stock),
            self._fmt(order_qty),
            self._fmt(order_qty_after),
            self._fmt(prepro_qty),
            self._fmt(expected_short),
            self._fmt(ipgo_qty),
            self._fmt(expected_stock),
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

        # 선 생산(COL_PRE_PROD) 또는 당일 잔피(COL_TODAY_RES)만 처리
        if col not in (COL_PRE_PROD, COL_TODAY_RES):
            return

        pk = item.data(Qt.UserRole)
        if pk is None:
            return

        # 콤마 제거 후 정수 파싱
        raw_text = item.text()
        text = raw_text.replace(",", "").strip()

        try:
            new_val = int(text) if text else 0
            if new_val < 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "오류", "0 이상 정수만 입력 가능합니다.")
            self.ui.tableWidget1.blockSignals(True)
            item.setText(self._fmt(0))
            self.ui.tableWidget1.blockSignals(False)
            new_val = 0

        # 컬럼에 따라 업데이트 필드 결정
        if col == COL_PRE_PROD:
            field_name = "pre_production_qty"
        else:  # COL_TODAY_RES
            field_name = "today_residue"

        conn, cur = getdb(DB_NAME)
        try:
            sql = f"""
                UPDATE ORDER_DASHBOARD
                SET {field_name} = %s
                WHERE PK = %s
            """
            runquery(cur, sql, [new_val, pk])
        finally:
            closedb(conn)

        # 해당 행만 다시 계산해서 반영
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

    #7. DB 조회/계산 헬퍼 함수
    def _get_homeplus_order_qty(self, co: str, sdate_str: str) -> int:
        """
        GWCHUL..PAN에서 해당 CO, PDATE = 날짜인 행들의 PAN 합계(박스 수).
        """
        conn, cur = getdb("GWCHUL")
        try:
            sql = """
                SELECT ISNULL(SUM(PAN), 0) AS sum_pan
                FROM PAN
                WHERE CO = %s
                  AND CONVERT(DATE, PDATE) = %s
            """
            df = runquery(cur, sql, [co, sdate_str])
        finally:
            closedb(conn)

        if df is None or df.empty:
            return 0

        try:
            val = df.iloc[0][df.columns[0]]
            return int(val or 0)
        except Exception:
            return 0

    def _get_emart_order_qty(self, tco: str, sdate_str: str) -> int:
        conn, cur = getdb("GFOOD_B")
        try:
            # 1) TCO -> CO 매핑
            sql_mmaster = """
                SELECT TOP 1 CO
                FROM MMASTER
                WHERE TCO = %s
            """
            df_key = runquery(cur, sql_mmaster, [tco])

            if df_key is None or df_key.empty:
                return 0

            real_co = str(df_key.iloc[0]["CO"]).strip()
            if not real_co:
                return 0

            # 2) MPAN에서 PAN 합계
            sql_mpan = """
                SELECT SUM(PANKG) AS sum_pan
                FROM MPAN
                WHERE CO = %s
                  AND CONVERT(DATE, SDATE) = %s
            """
            df = runquery(cur, sql_mpan, [real_co, sdate_str])
        finally:
            closedb(conn)

        if df is None or df.empty:
            return 0

        try:
            val = df.iloc[0][df.columns[0]]
            return int(val or 0)
        except Exception:
            return 0

    def _get_kurly_order_qty(self, tco: str, sdate_str: str) -> int:
        conn, cur = getdb("GFOOD_B")
        try:
            sql_mmaster = """
                SELECT TOP 1 CO
                FROM MMASTER
                WHERE TCO = %s
            """
            df_key = runquery(cur, sql_mmaster, [tco])

            if df_key is None or df_key.empty:
                return 0

            real_co = str(df_key.iloc[0]["CO"]).strip()
            if not real_co:
                return 0

            sql_mpan = """
                SELECT SUM(PANKG) AS sum_pan
                FROM MPAN
                WHERE CO = %s
                AND CONVERT(DATE, SDATE) = %s
            """
            df = runquery(cur, sql_mpan, [real_co, sdate_str])
        finally:
            closedb(conn)

        if df is None or df.empty:
            return 0

        try:
            val = df.iloc[0][df.columns[0]]
            return int(val or 0)
        except Exception:
            return 0

    def _get_coson_order_qty(self, base_co: str, sdate_str: str) -> int:
        """
        코스온 발주량 조회 로직

        1) GWCHUL..MASTER 에서 CO = base_co 인 행의 TCO3 조회
        2) GWCHUL..COSONC 에서 LCODE = TCO3
           AND CONVERT(DATE, LDATE) = sdate_str 인 행의 FINAL_QTY 사용
        """
        conn, cur = getdb("GWCHUL")
        try:
            # 1) MASTER에서 TCO3 조회
            sql_master = """
                SELECT TOP 1 TCO3
                FROM MASTER
                WHERE CO = %s
            """
            df_key = runquery(cur, sql_master, [base_co])

            if df_key is None or df_key.empty:
                return 0

            tco3 = str(df_key.iloc[0]["TCO3"]).strip()
            if not tco3:
                return 0

            # 2) COSONC에서 FINAL_QTY 조회
            sql_coson = """
                SELECT TOP 1 FINAL_QTY
                FROM COSONC
                WHERE LCODE = %s
                  AND CONVERT(DATE, LDATE) = %s
            """
            df = runquery(cur, sql_coson, [tco3, sdate_str])
        finally:
            closedb(conn)

        if df is None or df.empty:
            return 0

        try:
            val = df.iloc[0]["FINAL_QTY"]
            return int(val or 0)
        except Exception:
            return 0

    # -----------------------------------------------------
    # (기존) 이마트 MASTER용 CO 변환 함수
    # -----------------------------------------------------
    def _get_emart_master_co(self, base_co: str) -> str:
        conn, cur = getdb("GFOOD_B")
        try:
            sql = """
                SELECT TOP 1 TCO
                FROM MMASTER
                WHERE CO = %s
            """
            df = runquery(cur, sql, [base_co])
        finally:
            closedb(conn)

        if df is None or df.empty:
            return base_co

        try:
            return str(df.iloc[0]["TCO"]).strip()
        except Exception:
            return base_co

    # -----------------------------------------------------
    # 생산량(팩수) 계산 헬퍼
    # -----------------------------------------------------
    def _get_produced_qty_packs(self, co: str, sdate_str: str, pacsu: int) -> int:
        """
        GFOOD_B..PAN에서
          CH = 'C'
          AND JNAME = '공장(양념육)'
          AND CO = co
          AND PDATE = sdate_str
        인 행들의 PAN 합(박스 단위)에 PACSU를 곱해 생산 팩 수 반환.
        """
        try:
            if pacsu is None or pacsu <= 0:
                pacsu = 1

            try:
                conn, cur = getdb("GFOOD_B")
            except Exception as e:
                print(f"[ERROR] getdb('GFOOD_B') 실패: {e}")
                return 0

            try:
                sql = """
                    SELECT ISNULL(SUM(PAN), 0) AS sum_pan
                    FROM PAN
                    WHERE CH = 'C'
                      AND JNAME = '공장(양념육)'
                      AND CO = %s
                      AND CONVERT(DATE, PDATE) = %s
                """
                df = runquery(cur, sql, [co, sdate_str])
            except Exception as e:
                print(f"[ERROR] runquery(GFOOD_B.PAN) 실패 co={co}, date={sdate_str}: {e}")
                return 0
            finally:
                try:
                    closedb(conn)
                except Exception as e:
                    print(f"[WARN] GFOOD_B 연결 종료 실패: {e}")

            if df is None or df.empty:
                return 0

            try:
                if "sum_pan" in df.columns:
                    raw_val = df.iloc[0]["sum_pan"]
                else:
                    raw_val = df.iloc[0][df.columns[0]]
                box_sum = int(raw_val or 0)
            except Exception as e:
                print(f"[ERROR] 생산량 sum_pan 파싱 실패 co={co}: {e}")
                box_sum = 0

            return box_sum * pacsu

        except Exception as e:
            print(f"[FATAL] _get_produced_qty_packs({co}, {sdate_str}) 예외: {e}")
            return 0

    # -----------------------------------------------------
    # PACSU 조회 헬퍼
    # -----------------------------------------------------
    def _get_pacsu_by_co(self, co: str) -> int:
        try:
            conn, cur = getdb("GFOOD_B")
        except Exception as e:
            print(f"[ERROR] DB 연결 실패(GFOOD_B): {e}")
            return 1

        try:
            sql = """
                SELECT TOP 1 PACSU
                FROM MASTER
                WHERE CO = %s
            """
            df = runquery(cur, sql, [co])
        except Exception as e:
            print(f"[ERROR] PACSU 조회 실패 co={co}: {e}")
            df = None
        finally:
            try:
                closedb(conn)
            except Exception:
                pass

        if df is None or df.empty:
            return 1

        try:
            pacsu_val = df.iloc[0]["PACSU"]
            pacsu = int(pacsu_val if pacsu_val not in (None, "") else 1)
            if pacsu <= 0:
                pacsu = 1
        except:
            pacsu = 1

        return pacsu

    # -----------------------------------------------------
    # prev_residue 조회
    # -----------------------------------------------------
    def _get_prev_residue_from_today(self, co: str) -> int:
        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                SELECT TOP 1 today_residue
                FROM ORDER_DASHBOARD
                WHERE co = %s
                ORDER BY PK DESC
            """
            df = runquery(cur, sql, [co])
        finally:
            closedb(conn)

        if df is None or df.empty:
            return 0

        try:
            val = df.iloc[0][df.columns[0]]
            return int(val or 0)
        except:
            return 0

    def _get_stock_from_pan(self, bco: str, sdate_str: str) -> int:
        conn, cur = getdb("GFOOD_B")
        try:
            sql = """
                SELECT 
                    SUM(A.IPGO) - SUM(A.PAN) as stock_box
                FROM PAN A
                WHERE A.CH <> 'M'
                  AND A.CO = %s
                  AND A.PDATE <= CONVERT(smalldatetime, %s)
                  AND A.JNAME <> ''
                  AND A.JUM = '지점'
                  AND A.DE = 'N'
                GROUP BY A.JNAME
            """
            df = runquery(cur, sql, [bco, sdate_str])
        finally:
            closedb(conn)

        if df is None or df.empty:
            return 0

        total = 0
        for v in df.iloc[:, 0]:
            try:
                if int(v) > 0:
                    total += int(v)
            except:
                continue

        return total

    def _calc_plan_kg_by_recipe(self, df_order, recipe_keyword: str):
        """
        ORDER_DASHBOARD 기반 원료/소스 PLAN_KG 계산
        기준: ORDER_QTY_AFTER
        PLAN_PACKS = order_qty_after + pre_production_qty - prev_residue
        PLAN_KG    = PLAN_PACKS * pkg * SA
        """
        if df_order is None or df_order.empty:
            return None

        df_order = df_order.copy()
        df_order.columns = [c.upper() for c in df_order.columns]
        df_order["CO"] = df_order["CO"].astype(str).str.strip()

        co_list = df_order["CO"].unique().tolist()
        if not co_list:
            return None

        placeholders = ",".join(["%s"] * len(co_list))

        conn, cur = getdb("GFOOD_B")
        try:
            sql_recipe = f"""
                SELECT CO, BCO, BUNAME, SA
                FROM RECIPE
                WHERE CO IN ({placeholders})
                  AND BUNAME LIKE %s
            """
            params = co_list + [f"%{recipe_keyword}%"]
            df_recipe = runquery(cur, sql_recipe, params)
        finally:
            closedb(conn)

        if df_recipe is None or df_recipe.empty:
            return None

        df_recipe.columns = [c.upper() for c in df_recipe.columns]
        df_recipe["CO"] = df_recipe["CO"].astype(str).str.strip()
        df_recipe["BCO"] = df_recipe["BCO"].astype(str).str.strip()
        df_recipe["SA"] = df_recipe["SA"].fillna(1).astype(float)

        df = df_order.merge(df_recipe, how="inner", on="CO")
        if df.empty:
            return None

        # 계산에 필요한 컬럼 기본값
        for col in ("ORDER_QTY_AFTER", "PRE_PRODUCTION_QTY", "PREV_RESIDUE", "PKG"):
            if col not in df.columns:
                df[col] = 0

        df["ORDER_QTY_AFTER"] = df["ORDER_QTY_AFTER"].fillna(0).astype(float)
        df["PRE_PRODUCTION_QTY"] = df["PRE_PRODUCTION_QTY"].fillna(0).astype(float)
        df["PREV_RESIDUE"] = df["PREV_RESIDUE"].fillna(0).astype(float)
        df["PKG"] = df["PKG"].fillna(0).astype(float)

        df["PLAN_PACKS"] = (
                df["ORDER_QTY_AFTER"]
                + df["PRE_PRODUCTION_QTY"]
                - df["PREV_RESIDUE"]
        )

        # 🔥 **핵심 변경 부분: SA 곱해서 원료 필요량 계산**
        df["PLAN_KG"] = df["PLAN_PACKS"] * df["PKG"] * df["SA"] / 100

        # 음수 제거
        df = df[df["PLAN_KG"] > 0]
        if df.empty:
            return None

        # BCO 기준 합계
        grouped = df.groupby(["BCO", "BUNAME"], as_index=False)["PLAN_KG"].sum()
        return grouped

    def _calc_order_qty_packs(
            self,
            base_co: str,
            vendor: str,
            sdate_str: str,
            pacsu: int,
    ) -> int:
        """
        벤더별 '최종 발주 팩 수' 공통 계산 함수

        - 홈플러스: PAN(box) × PACSU → 팩
        - 이마트  : MPAN(EA) × PACSU → 팩
        - 마켓컬리: 박스 수 그대로 (PACSU 미적용)
        - 코스온  : COSONC.FINAL_QTY 그대로 (PACSU 미적용)
        """
        vendor = (vendor or "").strip()

        if pacsu is None or pacsu <= 0:
            pacsu = 1

        if vendor == "홈플러스":
            box_qty = self._get_homeplus_order_qty(base_co, sdate_str)
            return box_qty * pacsu

        if vendor == "이마트":
            packs = self._get_emart_order_qty(base_co, sdate_str)
            return packs * pacsu

        if vendor == "마켓컬리":
            box_qty = self._get_kurly_order_qty(base_co, sdate_str)
            return box_qty

        if vendor == "코스온":
            # 요청: FINAL_QTY 그대로 order_qty / order_qty_after 에 사용
            return self._get_coson_order_qty(base_co, sdate_str)

        # 정의되지 않은 벤더
        return 0

    def _recalc_dashboard_raw_keep_manual(self):
        qdate = self.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")
        sdate_dt = datetime(qdate.year(), qdate.month(), qdate.day(), 0, 0, 0)
        now = datetime.now()

        # ORDER_DASHBOARD
        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                SELECT co, order_qty_after, pre_production_qty, prev_residue, pkg
                FROM ORDER_DASHBOARD
                WHERE CONVERT(DATE, sdate) = %s
            """
            df_order = runquery(cur, sql, [sdate_str])
        finally:
            closedb(conn)

        if df_order is None or df_order.empty:
            return

        df_order.columns = [c.upper() for c in df_order.columns]
        df_order["CO"] = df_order["CO"].astype(str).str.strip()

        grouped = self._calc_plan_kg_by_recipe(df_order, "(정선)")
        if grouped is None or grouped.empty:
            return

        valid_keys = {(str(r.BCO).strip(), str(r.BUNAME).strip()) for r in grouped.itertuples(index=False)}

        # 기존 RAW 조회
        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                SELECT PK, uname, co
                FROM DASHBOARD_RAW
                WHERE CONVERT(DATE, sdate) = %s
            """
            df_exist = runquery(cur, sql, [sdate_str])
        finally:
            closedb(conn)

        exist_map = {}
        if df_exist is not None and not df_exist.empty:
            df_exist.columns = [c.upper() for c in df_exist.columns]
            for r in df_exist.itertuples(index=False):
                exist_map[(str(r.CO).strip(), str(r.UNAME).strip())] = r

        # DELETE rows not required
        delete_keys = set(exist_map.keys()) - valid_keys
        if delete_keys:
            conn, cur = getdb(DB_NAME)
            try:
                for co, uname in delete_keys:
                    runquery(cur, """
                        DELETE FROM DASHBOARD_RAW
                        WHERE CO=%s AND UNAME=%s AND CONVERT(DATE, sdate)=%s
                    """, [co, uname, sdate_str])
            finally:
                closedb(conn)

        # UPDATE / INSERT
        conn, cur = getdb(DB_NAME)
        try:
            for r in grouped.itertuples(index=False):
                bco = str(r.BCO).strip()
                buname = str(r.BUNAME).strip()
                qty_int = int(round(float(r.PLAN_KG or 0)))

                key = (bco, buname)
                exist = exist_map.get(key)

                if exist:  # -------- UPDATE --------
                    sql_up = """
                        UPDATE DASHBOARD_RAW
                        SET order_qty_after = %s
                        WHERE PK = %s
                    """
                    runquery(cur, sql_up, [qty_int, exist.PK])
                    print("Updated DASHBOARD_RAW:", buname, bco, qty_int)
                else:  # -------- INSERT --------
                    stock_val = self._get_stock_from_pan(bco, sdate_str)
                    sql_in = """
                        INSERT INTO DASHBOARD_RAW (
                            uname, co, sdate, created_time,
                            stock, order_qty, order_qty_after,
                            prepro_qty, ipgo_qty
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """
                    runquery(cur, sql_in, [
                        buname, bco, sdate_dt, now,
                        stock_val, qty_int, qty_int,
                        0, 0
                    ])
                    print("Inserted DASHBOARD_RAW:", buname, bco, qty_int)
        finally:
            closedb(conn)

    def _recalc_dashboard_sauce_keep_manual(self):
        qdate = self.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")
        sdate_dt = datetime(qdate.year(), qdate.month(), qdate.day(), 0, 0, 0)
        now = datetime.now()

        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                SELECT co, order_qty_after, pre_production_qty,
                       prev_residue, pkg
                FROM ORDER_DASHBOARD
                WHERE CONVERT(DATE, sdate) = %s
            """
            df_order = runquery(cur, sql, [sdate_str])
        finally:
            closedb(conn)

        if df_order is None or df_order.empty:
            return

        df_order.columns = [c.upper() for c in df_order.columns]
        df_order["CO"] = df_order["CO"].astype(str).str.strip()

        grouped = self._calc_plan_kg_by_recipe(df_order, "소스")
        if grouped is None or grouped.empty:
            return

        valid_keys = {(str(r.BCO).strip(), str(r.BUNAME).strip()) for r in grouped.itertuples(index=False)}

        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                SELECT PK, uname, co
                FROM DASHBOARD_SAUCE
                WHERE CONVERT(DATE, sdate) = %s
            """
            df_exist = runquery(cur, sql, [sdate_str])
        finally:
            closedb(conn)

        exist_map = {}
        if df_exist is not None and not df_exist.empty:
            df_exist.columns = [c.upper() for c in df_exist.columns]
            for r in df_exist.itertuples(index=False):
                exist_map[(str(r.CO).strip(), str(r.UNAME).strip())] = r

        # DELETE
        delete_keys = set(exist_map.keys()) - valid_keys
        if delete_keys:
            conn, cur = getdb(DB_NAME)
            try:
                for co, uname in delete_keys:
                    runquery(cur, """
                        DELETE FROM DASHBOARD_SAUCE
                        WHERE CO=%s AND UNAME=%s AND CONVERT(DATE, sdate)=%s
                    """, [co, uname, sdate_str])
            finally:
                closedb(conn)

        # UPDATE / INSERT
        conn, cur = getdb(DB_NAME)
        try:
            for r in grouped.itertuples(index=False):
                bco = str(r.BCO).strip()
                buname = str(r.BUNAME).strip()
                qty_int = int(round(float(r.PLAN_KG or 0)))

                key = (bco, buname)
                exist = exist_map.get(key)

                if exist:
                    sql_up = """
                        UPDATE DASHBOARD_SAUCE
                        SET order_qty_after = %s
                        WHERE PK = %s
                    """
                    runquery(cur, sql_up, [qty_int, exist.PK])
                else:
                    stock_val = self._get_stock_from_pan(bco, sdate_str)
                    sql_in = """
                        INSERT INTO DASHBOARD_SAUCE (
                            uname, co, sdate, created_time,
                            stock, order_qty, order_qty_after,
                            prepro_qty, ipgo_qty
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """
                    runquery(cur, sql_in, [
                        buname, bco, sdate_dt, now,
                        stock_val, qty_int, qty_int,
                        0, 0
                    ])
        finally:
            closedb(conn)

    def _recalc_dashboard_vege_keep_manual(self):
        qdate = self.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")
        sdate_dt = datetime(qdate.year(), qdate.month(), qdate.day(), 0, 0, 0)
        now = datetime.now()

        VEGE_BCO_LIST = ["720192", "700122", "720094"]

        # ORDER_DASHBOARD
        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                SELECT co, order_qty_after, pre_production_qty,
                       prev_residue, pkg
                FROM ORDER_DASHBOARD
                WHERE CONVERT(DATE, sdate) = %s
            """
            df_order = runquery(cur, sql, [sdate_str])
        finally:
            closedb(conn)

        if df_order is None or df_order.empty:
            return

        df_order.columns = [c.upper() for c in df_order.columns]
        df_order["CO"] = df_order["CO"].astype(str).str.strip()

        co_list = df_order["CO"].unique().tolist()
        if not co_list:
            return

        # 레시피 조회
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
            return

        df_recipe.columns = [c.upper() for c in df_recipe.columns]
        df_recipe["CO"] = df_recipe["CO"].astype(str)
        df_recipe["BCO"] = df_recipe["BCO"].astype(str)

        df = df_order.merge(df_recipe, on="CO", how="inner")
        if df.empty:
            return

        df["PLAN_KG"] = (
                                df["ORDER_QTY_AFTER"].fillna(0).astype(float)
                                + df["PRE_PRODUCTION_QTY"].fillna(0).astype(float)
                                - df["PREV_RESIDUE"].fillna(0).astype(float)
                        ) * df["PKG"].fillna(0).astype(float)

        df = df[df["PLAN_KG"] > 0]
        if df.empty:
            return

        df["VEGE_KG"] = df["PLAN_KG"] * df["SA"].fillna(0).astype(float)
        df = df[df["VEGE_KG"] > 0]
        if df.empty:
            return

        grouped = df.groupby(["BCO", "BUNAME"], as_index=False)["VEGE_KG"].sum()

        valid_keys = {(str(r["BCO"]).strip(), str(r["BUNAME"]).strip()) for _, r in grouped.iterrows()}

        # 기존 VEGE 조회
        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                SELECT PK, uname, co
                FROM DASHBOARD_VEGE
                WHERE CONVERT(DATE, sdate) = %s
            """
            df_exist = runquery(cur, sql, [sdate_str])
        finally:
            closedb(conn)

        exist_map = {}
        if df_exist is not None and not df_exist.empty:
            df_exist.columns = [c.upper() for c in df_exist.columns]
            for r in df_exist.itertuples(index=False):
                exist_map[(str(r.CO).strip(), str(r.UNAME).strip())] = r

        delete_keys = set(exist_map.keys()) - valid_keys
        if delete_keys:
            conn, cur = getdb(DB_NAME)
            try:
                for co, uname in delete_keys:
                    runquery(cur, """
                        DELETE FROM DASHBOARD_VEGE
                        WHERE CO=%s AND UNAME=%s AND CONVERT(DATE, sdate)=%s
                    """, [co, uname, sdate_str])
            finally:
                closedb(conn)

        # UPDATE / INSERT
        conn, cur = getdb(DB_NAME)
        try:
            for _, r in grouped.iterrows():
                bco = str(r["BCO"]).strip()
                buname = str(r["BUNAME"]).strip()
                qty_int = int(round(float(r["VEGE_KG"] or 0)))

                key = (bco, buname)
                exist = exist_map.get(key)

                if exist:
                    sql = """
                        UPDATE DASHBOARD_VEGE
                        SET order_qty_after = %s
                        WHERE PK = %s
                    """
                    runquery(cur, sql, [qty_int, exist.PK])
                else:
                    stock_val = self._get_stock_from_pan(bco, sdate_str)
                    sql = """
                        INSERT INTO DASHBOARD_VEGE (
                            uname, co, sdate, created_time,
                            stock, order_qty, order_qty_after,
                            prepro_qty, ipgo_qty
                        )
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """
                    runquery(cur, sql, [
                        buname, bco, sdate_dt, now,
                        stock_val, qty_int, qty_int,
                        0, 0
                    ])
        finally:
            closedb(conn)

    #8. 대시보드 데이터 가공
    def _dashboard_raw_from_dashboard(self):
        """
        DASHBOARD_RAW 생성(덮어쓰기) 로직 — Dummy row 입력 후 사용하는 버전
        기준:
            PLAN_PACKS = order_qty_after + pre_production_qty - prev_residue
            PLAN_KG    = PLAN_PACKS × pkg
        레시피 기준: '(정선)'
        """
        print("========[RAW FROM DASHBOARD START]========")

        qdate = self.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")
        sdate_dt = datetime(qdate.year(), qdate.month(), qdate.day(), 0, 0, 0)
        now = datetime.now()

        print(f"[INFO] 기준일: {sdate_str}")

        # STEP 1) ORDER_DASHBOARD 조회
        conn, cur = getdb(DB_NAME)
        try:
            sql_order = """
                SELECT
                    co,
                    order_qty_after,
                    pre_production_qty,
                    prev_residue,
                    pkg
                FROM ORDER_DASHBOARD
                WHERE CONVERT(DATE, sdate) = %s
            """
            df_order = runquery(cur, sql_order, [sdate_str])
        finally:
            closedb(conn)

        print("\n[DEBUG] df_order 조회 결과:")
        print(df_order)

        if df_order is None or df_order.empty:
            print("[STOP] ORDER_DASHBOARD 없음 → DASHBOARD_RAW DELETE 후 종료")

            conn_d, cur_d = getdb(DB_NAME)
            try:
                runquery(cur_d,
                         "DELETE FROM DASHBOARD_RAW WHERE CONVERT(DATE, sdate) = %s",
                         [sdate_str])
            finally:
                closedb(conn_d)

            print("========[RAW FROM DASHBOARD END]========")
            return

        df_order.columns = [c.upper() for c in df_order.columns]
        df_order["CO"] = df_order["CO"].astype(str).str.strip()

        # STEP 2) 레시피 기반 PLAN_KG 집계 (정선)
        grouped = self._calc_plan_kg_by_recipe(df_order, "(정선)")

        print("\n[DEBUG] grouped 결과:")
        print(grouped)

        if grouped is None or grouped.empty:
            print("[STOP] grouped 0행 → DASHBOARD_RAW DELETE 후 종료")

            conn_d, cur_d = getdb(DB_NAME)
            try:
                runquery(cur_d,
                         "DELETE FROM DASHBOARD_RAW WHERE CONVERT(DATE, sdate) = %s",
                         [sdate_str])
            finally:
                closedb(conn_d)

            print("========[RAW FROM DASHBOARD END]========")
            return

        # STEP 3) 현재 RAW 완전 삭제 (새로 생성하는 버전)
        print("\n[DELETE] 기존 DASHBOARD_RAW 삭제")
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

            print(f"[ROW] BCO={bco}, BUNAME={buname}, PLAN_KG={plan_kg_sum}, qty_int={qty_int}")

            if qty_int <= 0:
                continue

            stock_val = self._get_stock_from_pan(bco, sdate_str)

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

        print(f"\n[DEBUG] INSERT 준비 row 수: {len(rows)}")

        if not rows:
            print("[STOP] INSERT할 row 없음 → 종료")
            print("========[RAW FROM DASHBOARD END]========")
            return

        # STEP 5) INSERT 실행
        self._insert_dashboard_raw_rows(rows)

        print("[DONE] RAW INSERT 완료")
        print("========[RAW FROM DASHBOARD END]========")

    def _dashboard_sauce_from_dashboard(self):
        """
        DASHBOARD_SAUCE 생성(덮어쓰기) 로직
        기준:
            PLAN_PACKS = order_qty_after + pre_production_qty - prev_residue
            PLAN_KG    = PLAN_PACKS × pkg
        레시피 키워드: '소스'
        """
        print("========[SAUCE FROM DASHBOARD START]========")

        qdate = self.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")
        sdate_dt = datetime(qdate.year(), qdate.month(), qdate.day(), 0, 0, 0)
        now = datetime.now()

        print(f"[INFO] 기준일: {sdate_str}")

        # STEP 1) ORDER_DASHBOARD 조회
        conn, cur = getdb(DB_NAME)
        try:
            sql_order = """
                SELECT
                    co,
                    order_qty_after,
                    pre_production_qty,
                    prev_residue,
                    pkg
                FROM ORDER_DASHBOARD
                WHERE CONVERT(DATE, sdate) = %s
            """
            df_order = runquery(cur, sql_order, [sdate_str])
        finally:
            closedb(conn)

        print("\n[DEBUG] df_order 조회 결과:")
        print(df_order)

        if df_order is None or df_order.empty:
            print("[STOP] ORDER_DASHBOARD 없음 → SAUCE 삭제 후 종료")

            conn_d, cur_d = getdb(DB_NAME)
            try:
                runquery(cur_d,
                         "DELETE FROM DASHBOARD_SAUCE WHERE CONVERT(DATE, sdate) = %s",
                         [sdate_str])
            finally:
                closedb(conn_d)

            print("========[SAUCE FROM DASHBOARD END]========")
            return

        df_order.columns = [c.upper() for c in df_order.columns]
        df_order["CO"] = df_order["CO"].astype(str).str.strip()

        # STEP 2) 레시피 기반 PLAN_KG (소스)
        grouped = self._calc_plan_kg_by_recipe(df_order, "소스")

        print("\n[DEBUG] grouped 결과:")
        print(grouped)

        if grouped is None or grouped.empty:
            print("[STOP] grouped 없음 → SAUCE 삭제 후 종료")

            conn_d, cur_d = getdb(DB_NAME)
            try:
                runquery(cur_d,
                         "DELETE FROM DASHBOARD_SAUCE WHERE CONVERT(DATE, sdate) = %s",
                         [sdate_str])
            finally:
                closedb(conn_d)

            print("========[SAUCE FROM DASHBOARD END]========")
            return

        # STEP 3) 기존 SAUCE 삭제 (덮어쓰기)
        print("[DELETE] 기존 DASHBOARD_SAUCE 삭제")

        conn_d, cur_d = getdb(DB_NAME)
        try:
            runquery(cur_d,
                     "DELETE FROM DASHBOARD_SAUCE WHERE CONVERT(DATE, sdate) = %s",
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

            print(f"[ROW] BCO={bco}, BUNAME={buname}, PLAN_KG={plan_kg_sum}, qty_int={qty_int}")

            if qty_int <= 0:
                continue

            stock_val = self._get_stock_from_pan(bco, sdate_str)

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

        print(f"\n[DEBUG] INSERT row 수: {len(rows)}")

        if not rows:
            print("[STOP] INSERT할 row 없음")
            print("========[SAUCE FROM DASHBOARD END]========")
            return

        self._insert_dashboard_sauce_rows(rows)

        print("[DONE] SAUCE INSERT 완료")
        print("========[SAUCE FROM DASHBOARD END]========")

    def _dashboard_vege_from_dashboard(self):
        """
        DASHBOARD_VEGE 생성(덮어쓰기) 로직
        기준:
            PLAN_PACKS = order_qty_after + pre_production_qty - prev_residue
            PLAN_KG    = PLAN_PACKS × pkg
            VEGE_KG    = PLAN_KG × SA
        VEGE_BCO_LIST: 고정 야채 품목
        """
        print("========[VEGE FROM DASHBOARD START]========")

        qdate = self.ui.dateEdit.date()
        sdate_str = qdate.toString("yyyy-MM-dd")
        sdate_dt = datetime(qdate.year(), qdate.month(), qdate.day(), 0, 0, 0)
        now = datetime.now()

        VEGE_BCO_LIST = ["720192", "700122", "720094"]

        print(f"[INFO] 기준일: {sdate_str}")
        print(f"[INFO] VEGE_BCO_LIST: {VEGE_BCO_LIST}")

        # STEP 1) ORDER_DASHBOARD 조회
        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                SELECT
                    co, order_qty_after,
                    pre_production_qty,
                    prev_residue, pkg
                FROM ORDER_DASHBOARD
                WHERE CONVERT(DATE, sdate) = %s
            """
            df_order = runquery(cur, sql, [sdate_str])
        finally:
            closedb(conn)

        print("\n[DEBUG] df_order:")
        print(df_order)

        if df_order is None or df_order.empty:
            print("[STOP] ORDER_DASHBOARD 없음 → VEGE 삭제")

            conn_d, cur_d = getdb(DB_NAME)
            try:
                runquery(cur_d,
                         "DELETE FROM DASHBOARD_VEGE WHERE CONVERT(DATE, sdate) = %s",
                         [sdate_str])
            finally:
                closedb(conn_d)
            print("========[VEGE FROM DASHBOARD END]========")
            return

        df_order.columns = [c.upper() for c in df_order.columns]
        df_order["CO"] = df_order["CO"].astype(str).str.strip()

        co_list = df_order["CO"].unique().tolist()
        print(f"\n[DEBUG] CO LIST = {co_list}")

        if not co_list:
            print("[STOP] CO 없음 → 종료")
            return

        # STEP 2) 야채 RECIPE 조회
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

        print("\n[DEBUG] df_recipe(야채):")
        print(df_recipe)

        if df_recipe is None or df_recipe.empty:
            print("[STOP] 야채 레시피 없음 → VEGE 삭제")

            conn_d, cur_d = getdb(DB_NAME)
            try:
                runquery(cur_d,
                         "DELETE FROM DASHBOARD_VEGE WHERE CONVERT(DATE, sdate) = %s",
                         [sdate_str])
            finally:
                closedb(conn_d)
            print("========[VEGE FROM DASHBOARD END]========")
            return

        df_recipe.columns = [c.upper() for c in df_recipe.columns]
        df_recipe["CO"] = df_recipe["CO"].astype(str).str.strip()
        df_recipe["BCO"] = df_recipe["BCO"].astype(str).str.strip()

        # STEP 3) JOIN
        df = df_order.merge(df_recipe, on="CO", how="inner")
        print("\n[DEBUG] JOIN 결과:")
        print(df)

        if df.empty:
            print("[STOP] 조인 결과 없음 → VEGE 삭제")
            return

        # STEP 4) PLAN_KG
        df["PLAN_KG"] = (
                                df["ORDER_QTY_AFTER"].fillna(0).astype(float)
                                + df["PRE_PRODUCTION_QTY"].fillna(0).astype(float)
                                - df["PREV_RESIDUE"].fillna(0).astype(float)
                        ) * df["PKG"].fillna(0).astype(float)

        print("\n[DEBUG] PLAN_KG:")
        print(df[["BCO", "BUNAME", "PLAN_KG"]])

        df = df[df["PLAN_KG"] > 0]
        if df.empty:
            print("[STOP] PLAN_KG 없음")
            return

        # STEP 5) VEGE_KG
        df["VEGE_KG"] = df["PLAN_KG"] * df["SA"].fillna(0).astype(float)

        print("\n[DEBUG] VEGE_KG:")
        print(df[["BCO", "BUNAME", "PLAN_KG", "SA", "VEGE_KG"]])

        df = df[df["VEGE_KG"] > 0]
        if df.empty:
            print("[STOP] VEGE_KG 없음")
            return

        # STEP 6) 그룹핑
        grouped = df.groupby(["BCO", "BUNAME"], as_index=False)["VEGE_KG"].sum()

        print("\n[DEBUG] grouped:")
        print(grouped)

        # STEP 7) 기존 제거
        conn_d, cur_d = getdb(DB_NAME)
        try:
            runquery(cur_d,
                     "DELETE FROM DASHBOARD_VEGE WHERE CONVERT(DATE, sdate) = %s",
                     [sdate_str])
        finally:
            closedb(conn_d)

        # STEP 8) INSERT 준비
        rows = []
        for _, r in grouped.iterrows():
            bco = r["BCO"]
            buname = r["BUNAME"]
            qty_int = int(round(float(r["VEGE_KG"] or 0)))

            print(f"[ROW] BCO={bco}, BUNAME={buname}, VEGE_KG={r['VEGE_KG']}, qty_int={qty_int}")

            if qty_int <= 0:
                continue

            stock_val = self._get_stock_from_pan(bco, sdate_str)

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

        print(f"\n[DEBUG] INSERT row 수 = {len(rows)}")

        if rows:
            self._insert_dashboard_vege_rows(rows)
            print("[DONE] VEGE INSERT 완료")
        else:
            print("[STOP] rows 없음")

        print("========[VEGE FROM DASHBOARD END]========")

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
        if not hasattr(self.ui, "dateEdit"):
            QMessageBox.warning(self, "오류", "dateEdit 위젯을 찾을 수 없습니다.")
            return

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

                prev_residue = self._get_prev_residue_from_today(base_co)

                # 🔹 벤더별 발주 팩 수 공통 계산
                order_qty_packs = self._calc_order_qty_packs(
                    base_co=base_co,
                    vendor=vendor,
                    sdate_str=sdate_str,
                    pacsu=pacsu,
                )

                produced_qty = self._get_produced_qty_packs(base_co, sdate_str, pacsu)

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
                    "pre_production_qty": 0,
                    "produced_qty": produced_qty,
                    "remain_production_qty": 0,
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
                    order_qty, order_qty_after, prev_residue, pre_production_qty,
                    produced_qty, remain_production_qty, today_residue
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """
            for r in rows:
                params = [
                    r["bigo"], r["sdate"], r["created_time"], r["id"],
                    r["rname"], r["uname"], r["co"], r["pkg"],
                    r["order_qty"], r["order_qty_after"], r["prev_residue"],
                    r["pre_production_qty"], r["produced_qty"],
                    r["remain_production_qty"], r["today_residue"],
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
            self._recalc_dashboard_raw_keep_manual()
            self._recalc_dashboard_sauce_keep_manual()
            self._recalc_dashboard_vege_keep_manual()
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
            if not hasattr(self.ui, "dateEdit"):
                QMessageBox.warning(self, "오류", "dateEdit 위젯을 찾을 수 없습니다.")
                return

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
                        pacsu = self._get_pacsu_by_co(co_str)
                    except Exception as e:
                        print(f"[ERROR] _get_pacsu_by_co({co_str}) 예외: {e}")
                        pacsu = 1

                    # 생산 팩 수 계산
                    produced_qty = self._get_produced_qty_packs(co_str, sdate_str, pacsu)

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
        if not hasattr(self.ui, "dateEdit"):
            QMessageBox.warning(self, "오류", "dateEdit 위젯을 찾을 수 없습니다.")
            return

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
                pacsu = self._get_pacsu_by_co(base_co)
                if pacsu is None or pacsu <= 0:
                    pacsu = 1

                # 🔹 벤더별 발주 팩 수 공통 계산 (코스온 포함)
                new_qty_packs = int(
                    self._calc_order_qty_packs(
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

        self._recalc_dashboard_raw_keep_manual()
        self._recalc_dashboard_sauce_keep_manual()
        self._recalc_dashboard_vege_keep_manual()

        QMessageBox.information(
            self,
            "완료",
            "모든 제품의 최종 발주량(order_qty_after)이 재계산되었고,\n"
            "원료/소스/야채 대시보드도 최신 기준으로 반영되었습니다."
        )

        # 제품 탭 갱신
        self._load_product_tab()

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


class DashboardLogDialog(QDialog):
    """
    GP..DASHBOARD_LOG를 날짜별로 조회하는 팝업 (UTIL.db_handler 기반)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("발주 로그 조회")
        self.resize(900, 500)

        # -------------------------------
        # 레이아웃 구성
        # -------------------------------
        layout = QVBoxLayout(self)

        # 상단 날짜 + 버튼
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("날짜:"))

        self.dateEdit = QDateEdit()
        self.dateEdit.setCalendarPopup(True)
        self.dateEdit.setDate(QDate.currentDate())
        top_layout.addWidget(self.dateEdit)

        self.btn_search = QPushButton("조회")
        top_layout.addWidget(self.btn_search)

        top_layout.addStretch()
        layout.addLayout(top_layout)

        # 중앙 테이블
        self.table = QTableWidget(self)
        headers = ["PK", "변경시각", "ID", "날짜", "CO", "업체", "변경전 → 변경후"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # 🔹 테이블 스타일 적용
        apply_table_style(self.table)

        layout.addWidget(self.table)

        # 하단 닫기 버튼
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)

        # 이벤트 연결
        self.btn_search.clicked.connect(self.load_logs)
        self.dateEdit.dateChanged.connect(lambda _: self.load_logs())

        # 초기 데이터 로드
        self.load_logs()

    # ------------------------------------------------------
    # 로그 조회 함수 (UTIL.db_handler 기반)
    # ------------------------------------------------------
    def load_logs(self):
        sdate_str = self.dateEdit.date().toString("yyyy-MM-dd")

        conn, cur = getdb(DB_NAME)
        try:
            sql = """
                SELECT 
                    PK, 
                    update_time, 
                    id, 
                    sdate, 
                    co, 
                    vendor, 
                    qty_before, 
                    qty_after
                FROM DASHBOARD_LOG
                WHERE CONVERT(DATE, sdate) = %s
                ORDER BY update_time DESC, PK DESC
            """
            df = runquery(cur, sql, [sdate_str])
        except Exception as e:
            QMessageBox.critical(self, "DB 오류", str(e))
            return
        finally:
            closedb(conn)

        self.table.setRowCount(0)

        # 결과 없을 때
        if df is None or len(df) == 0:
            QMessageBox.information(self, "안내", f"{sdate_str} 로그 데이터가 없습니다.")
            return

        df = pd.DataFrame(df)
        df.columns = [str(c).upper() for c in df.columns]
        self.table.setRowCount(len(df))

        # 테이블에 데이터 채우기
        for row_idx, row in enumerate(df.itertuples(index=False)):
            pk = str(row.PK)
            update_time = row.UPDATE_TIME
            log_id = str(row.ID)
            sdate = row.SDATE
            co = str(row.CO)
            vendor = str(row.VENDOR)
            before = int(row.QTY_BEFORE or 0)
            after = int(row.QTY_AFTER or 0)
            diff = after - before

            # 날짜/시간 포맷
            if isinstance(update_time, datetime):
                update_time_str = update_time.strftime("%Y-%m-%d %H:%M:%S")
            else:
                update_time_str = str(update_time)

            if hasattr(sdate, "strftime"):
                sdate_str2 = sdate.strftime("%Y-%m-%d")
            else:
                sdate_str2 = str(sdate)

            # 변경내용 문자열 구성
            change_text = f"{before} → {after}"
            if diff != 0:
                change_text += f" (Δ {diff})"

            row_data = [
                pk,
                update_time_str,
                log_id,
                sdate_str2,
                co,
                vendor,
                change_text,
            ]

            for col, val in enumerate(row_data):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row_idx, col, item)


class ProductListDialog(QDialog):
    """
    제품 대시보드에 사용할 PRODUCT_LIST를 관리하는 창.
    - 현재 리스트 표시 (CO, 업체명, UNAME)
    - 추가 / 삭제 / 기본값으로 되돌리기
    """

    def __init__(self, parent, product_list):
        super().__init__(parent)
        self.setWindowTitle("제품 리스트 관리")
        self.resize(700, 400)

        # 디폴트 / 현재 리스트
        self._default_list = list(PRODUCT_LIST)
        self._product_list = list(product_list)

        main_layout = QVBoxLayout(self)

        # -------------------
        # 테이블
        # -------------------
        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["CO", "업체명", "상품명(UNAME)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        # 🔹 테이블 스타일 적용
        apply_table_style(self.table)

        main_layout.addWidget(self.table)

        # -------------------
        # 버튼
        # -------------------
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("추가")
        self.btn_remove = QPushButton("삭제")
        self.btn_reset = QPushButton("기본값으로 되돌리기")

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_remove)
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

        # 확인/취소
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        self.btn_ok = QPushButton("확인")
        self.btn_cancel = QPushButton("취소")
        bottom_layout.addWidget(self.btn_ok)
        bottom_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(bottom_layout)

        # 시그널 연결
        self.btn_add.clicked.connect(self.on_add)
        self.btn_remove.clicked.connect(self.on_remove)
        self.btn_reset.clicked.connect(self.on_reset)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

        # 초기 데이터 로드
        self._reload_table()

    # -----------------------------------------------------
    # UNAME 매핑 조회
    # -----------------------------------------------------
    def _fetch_uname_map(self, cos):
        if not cos:
            return {}

        placeholders = ", ".join(["%s"] * len(cos))
        sql = f"""
            SELECT CO, UNAME
            FROM MASTER
            WHERE CO IN ({placeholders})
        """

        conn, cur = getdb("GWCHUL")
        try:
            df = runquery(cur, sql, cos)
        finally:
            closedb(conn)

        result = {}
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                co = str(row["CO"]).strip()
                uname = str(row["UNAME"]).strip()
                result[co] = uname
        return result

    # -----------------------------------------------------
    # 테이블 리로드
    # -----------------------------------------------------
    def _reload_table(self):
        self.table.setRowCount(0)

        cos = sorted({co for co, _ in self._product_list})
        uname_map = self._fetch_uname_map(cos)

        for co, vendor in self._product_list:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(co)))
            self.table.setItem(row, 1, QTableWidgetItem(str(vendor)))
            self.table.setItem(row, 2, QTableWidgetItem(uname_map.get(str(co), "")))

    # -----------------------------------------------------
    # 버튼 핸들러들
    # -----------------------------------------------------
    def on_add(self):
        dlg = MasterSearchDialog(self)
        if dlg.exec_() == QDialog.Accepted and dlg.selected_co:
            key = (dlg.selected_co, dlg.selected_vendor)
            if key in self._product_list:
                QMessageBox.information(self, "안내", "이미 존재하는 항목입니다.")
                return

            self._product_list.append(key)
            self._reload_table()

    def on_remove(self):
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        for r in rows:
            co = self.table.item(r, 0).text()
            vendor = self.table.item(r, 1).text()
            if (co, vendor) in self._product_list:
                self._product_list.remove((co, vendor))
            self.table.removeRow(r)

    def on_reset(self):
        self._product_list = list(self._default_list)
        self._reload_table()

    def get_product_list(self):
        return list(self._product_list)


class MasterSearchDialog(QDialog):
    """
    GWCHUL..MASTER 에서 CO/UNAME 검색 후 선택 → (CO, UNAME, 업체명)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MASTER 검색")
        self.resize(700, 400)

        self.selected_co = None
        self.selected_uname = None
        self.selected_vendor = None

        main_layout = QVBoxLayout(self)

        # ----------------------
        # 검색 영역
        # ----------------------
        top_layout = QHBoxLayout()
        self.combo_target = QComboBox()
        self.combo_target.addItems(["전체", "CO", "상품명"])

        self.edit_keyword = QLineEdit()
        self.edit_keyword.setPlaceholderText("CO 또는 상품명 입력")

        self.combo_vendor = QComboBox()
        self.combo_vendor.addItems(VENDOR_CHOICES)

        self.btn_search = QPushButton("검색")

        top_layout.addWidget(self.combo_target)
        top_layout.addWidget(self.edit_keyword)
        top_layout.addWidget(self.combo_vendor)
        top_layout.addWidget(self.btn_search)
        main_layout.addLayout(top_layout)

        # ----------------------
        # 테이블
        # ----------------------
        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels(["CO", "UNAME"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        # 🔹 테이블 스타일 적용
        apply_table_style(self.table)

        main_layout.addWidget(self.table)

        # ----------------------
        # 버튼 하단
        # ----------------------
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self.btn_add = QPushButton("선택 추가")
        self.btn_close = QPushButton("닫기")

        bottom_layout.addWidget(self.btn_add)
        bottom_layout.addWidget(self.btn_close)
        main_layout.addLayout(bottom_layout)

        # ----------------------
        # 이벤트
        # ----------------------
        self.btn_search.clicked.connect(self.on_search)
        self.btn_add.clicked.connect(self.on_add_clicked)
        self.btn_close.clicked.connect(self.reject)
        self.edit_keyword.returnPressed.connect(self.on_search)

    # -----------------------------------------------------
    def on_search(self):
        keyword = self.edit_keyword.text().strip()
        target = self.combo_target.currentText()

        where = []
        params = []

        if keyword:
            like = f"%{keyword}%"
            if target == "CO":
                where.append("CO LIKE %s")
                params.append(like)
            elif target == "상품명":
                where.append("UNAME LIKE %s")
                params.append(like)
            else:
                where.append("(CO LIKE %s OR UNAME LIKE %s)")
                params.extend([like, like])

        where_sql = "WHERE " + " AND ".join(where) if where else ""

        sql = f"""
            SELECT TOP 200 CO, UNAME
            FROM MASTER
            {where_sql}
            ORDER BY CO
        """

        conn, cur = getdb("GWCHUL")
        try:
            df = runquery(cur, sql, params)
        finally:
            closedb(conn)

        self.table.setRowCount(0)
        if df is None or df.empty:
            return

        for _, row in df.iterrows():
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(str(row["CO"]).strip()))
            self.table.setItem(r, 1, QTableWidgetItem(str(row["UNAME"]).strip()))

    # -----------------------------------------------------
    def on_add_clicked(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            QMessageBox.information(self, "안내", "추가할 항목을 선택하세요.")
            return

        row = selected[0].row()
        self.selected_co = self.table.item(row, 0).text()
        self.selected_uname = self.table.item(row, 1).text()
        self.selected_vendor = self.combo_vendor.currentText()
        self.accept()

        
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
