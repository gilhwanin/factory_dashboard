from __future__ import annotations

from PyQt5.QtCore import Qt, QDate
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QWidget,
    QTableWidget,
    QMessageBox,
    QInputDialog,
    QLineEdit,
    QShortcut,
)

from UI.dashboard import Ui_Form
from UTIL.const import (
    DB_NAME, PAGE_SIZE, DEFAULT_VENDOR, VENDORS_ROTATION,
)
from UTIL.db_handler import runquery, db_connection
from UTIL.db_product_handler import fetch_default_products
from dialog.DashboardLogDialog import DashboardLogDialog
from dialog.ProductNameDialog import ProductNameDialog
from dialog.SameProductDialog import SameProductDialog

from core.table_ui import TableUIManager
from core.pagination import PaginationManager
from core.data_loader import DataLoader
from core.data_writer import DataWriter
from core.timer_manager import TimerManager
from core.excel_export import export_excel


class OrderDashboardWidget(QWidget):

    # =====================================================
    # 1. 초기화
    # =====================================================
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Form()
        self.ui.setupUi(self)

        # 상태 변수
        self.current_level = 0
        self.current_user = ""
        try:
            self.product_list = fetch_default_products()
        except Exception:
            self.product_list = []

        # 페이지네이션 상태
        self.product_page = 0
        self.product_page_size = PAGE_SIZE
        self.product_total_pages = 1
        self._lotte_page_labels = []

        # 현재 선택된 업체
        self.current_vendor = DEFAULT_VENDOR
        self.ui.tab_frequency.setText("30")

        self._fullscreen_mode = False
        self.ui.control_frame.hide()
        self.show_hidden = False

        # 날짜 설정
        self.ui.dateEdit.setDate(QDate.currentDate())
        qdate = self.ui.dateEdit.date()
        date_str = qdate.toString("yyyy-MM-dd")
        weekday_str = qdate.toString("ddd")
        self.ui.dateText.setText(f"{date_str} ({weekday_str})")

        # 변경 이벤트 플래그
        self._item_changed_connected = {
            "product": False,
            "raw": False,
            "sauce": False,
            "vege": False,
        }

        # 매니저 초기화
        self.table_ui = TableUIManager(self)
        self.pagination = PaginationManager(self)
        self.loader = DataLoader(self)
        self.writer = DataWriter(self)
        self.timer = TimerManager(self)

        # 테이블 스타일 적용
        for table in self._all_tables():
            self.table_ui.setup_table_base(table)

        # 페이지네이션 바 생성
        self.pagination.setup_pagination_bar()

        # 품명 매핑 캐시
        self.uname_map_cache = {}
        self.refresh_uname_map_cache()

        # 타이머 설정 (화면 전환/갱신용)
        self.is_auto_rotation = False
        self.vendors_rotation = VENDORS_ROTATION
        self.rotation_index = 0
        self.timer.setup_timers()

        # 버튼 / 시그널 연결
        self.ui.btn_view.clicked.connect(self.on_click_toggle_fullscreen)
        self.ui.btn_prev.clicked.connect(self.on_click_prev_date)
        self.ui.btn_next.clicked.connect(self.on_click_next_date)

        self.ui.btn_product.clicked.connect(self.on_click_tab_product)
        self.ui.btn_raw.clicked.connect(self.on_click_tab_raw)
        self.ui.btn_sauce.clicked.connect(self.on_click_tab_sauce)
        self.ui.btn_vege.clicked.connect(self.on_click_tab_vege)

        # 업체 필터 버튼 연결
        self.ui.btn_costco.clicked.connect(self.on_click_filter_costco)
        self.ui.btn_emart.clicked.connect(self.on_click_filter_emart)
        self.ui.btn_homeplus.clicked.connect(self.on_click_filter_hk)
        self.ui.btn_lotte.clicked.connect(self.on_click_filter_lotte)

        self.ui.btn_add.clicked.connect(self.writer.on_click_add_dummy_rows)
        self.ui.btn_del.clicked.connect(self.writer.on_click_delete_rows)
        self.ui.btn_del_row.clicked.connect(self.writer.on_click_delete_selected_products)
        self.ui.btn_update.clicked.connect(self.writer.on_click_update_order_qty_after)
        self.ui.btn_update_product.clicked.connect(self.writer.on_click_update_product)
        self.ui.btn_sync_diary.clicked.connect(self.writer.on_click_sync_diary)
        self.ui.btn_delete_diary.clicked.connect(self.writer.on_click_delete_diary)
        self.ui.btn_log.clicked.connect(self.on_click_show_log_dialog)
        self.ui.btn_excel.clicked.connect(lambda: export_excel(self))
        self.ui.btn_admin.clicked.connect(self.on_click_toggle_admin)
        self.ui.btn_complete.clicked.connect(self.writer.on_click_complete_product)
        self.ui.btn_custom.clicked.connect(self.on_click_custom)
        self.ui.btn_same_product.clicked.connect(self.on_click_same_product)
        self.ui.btn_renew.clicked.connect(self.timer.renew_values_manually)

        QShortcut(QKeySequence("Ctrl+L"), self, activated=self.on_click_toggle_admin)

        self.ui.btn_hide_row.clicked.connect(self.writer.on_click_hide_row)
        self.ui.btn_show_hide.clicked.connect(self.on_click_toggle_show_hide)
        self.ui.ml_check.stateChanged.connect(self.loader.load_product_tab)

        # 화면 전환/고정 버튼
        self.ui.btn_autoPage.setText("화면고정")
        self.ui.btn_autoPage.clicked.connect(self.timer.on_click_toggle_mode)

        # 탭 전환
        self.ui.tabWidget.currentChanged.connect(self.on_tab_changed)

        # 날짜 변경 이벤트
        self.ui.dateEdit.dateChanged.connect(self.on_date_changed)

        # 최초 로딩
        self.loader.load_product_tab()
        self.table_ui.apply_column_visibility_rules()

    # ---------------------------------------------------------
    # 유틸리티 헬퍼
    # ---------------------------------------------------------
    def _all_tables(self):
        return [self.ui.tableWidget1, self.ui.tableWidget2,
                self.ui.tableWidget3, self.ui.tableWidget4]

    def _material_table(self, tab_key: str) -> QTableWidget:
        return {"raw": self.ui.tableWidget2,
                "sauce": self.ui.tableWidget3,
                "vege": self.ui.tableWidget4}[tab_key]

    def _material_db_table(self, tab_key: str) -> str:
        return {"raw": "DASHBOARD_RAW",
                "sauce": "DASHBOARD_SAUCE",
                "vege": "DASHBOARD_VEGE"}[tab_key]

    def _material_row_height(self, tab_key: str) -> int:
        return {"raw": 50, "sauce": 46, "vege": 46}[tab_key]

    def _tab_loader(self, idx: int):
        loaders = {
            0: self.loader.load_product_tab,
            1: lambda: self.loader.load_material_tab("raw"),
            2: lambda: self.loader.load_material_tab("sauce"),
            3: lambda: self.loader.load_material_tab("vege"),
        }
        loader = loaders.get(idx)
        if loader:
            loader()

    def _reload_all_tabs(self):
        self.loader.load_product_tab()
        self.loader.load_material_tab("raw")
        self.loader.load_material_tab("sauce")
        self.loader.load_material_tab("vege")

    # =====================================================
    # 2. UI 상태 관련 함수
    # =====================================================
    def on_click_toggle_fullscreen(self):
        self._fullscreen_mode = not self._fullscreen_mode

        if self._fullscreen_mode:
            self.showFullScreen()
            self.ui.view_frame.hide()
            self.ui.view_frame2.hide()
            self.ui.control_frame.hide()
        else:
            self.showNormal()
            self.ui.view_frame.show()
            self.ui.view_frame2.show()
            if self.current_level >= 2:
                self.ui.control_frame.show()
            else:
                self.ui.control_frame.hide()

        self.layout().update()

    def _ask_admin_login(self):
        """DASHBOARD_ID 테이블에서 비밀번호만으로 사용자 검증."""
        pw, ok = QInputDialog.getText(
            self, "관리자 로그인", "비밀번호를 입력하세요:", QLineEdit.Password
        )
        if not ok:
            return False

        try:
            with db_connection("GP") as (conn, cur):
                sql = "SELECT name, level FROM DASHBOARD_ID WHERE pw = %s"
                df = runquery(cur, sql, [pw])
        except (ConnectionError, Exception) as e:
            QMessageBox.warning(self, "로그인 실패", f"DB 연결 실패: {e}")
            return False

        if df is None or df.empty:
            QMessageBox.warning(self, "로그인 실패", "일치하는 계정이 없습니다.")
            return False

        self.current_user = str(df.iloc[0]["name"]).strip()
        self.current_level = int(df.iloc[0]["level"])
        return True

    def on_click_toggle_admin(self):
        # 이미 관리자면 OFF
        if self.current_level >= 1:
            self.current_level = 0
            self.current_user = ""
            self.ui.control_frame.hide()
            self.table_ui.apply_column_visibility_rules()
            self.ui.btn_admin.setText("관리자")
            self._reload_all_tabs()
            return

        # 로그인 시도
        if self._ask_admin_login():
            if self.current_level >= 2:
                self.ui.control_frame.show()
            else:
                self.ui.control_frame.hide()

            self.table_ui.apply_column_visibility_rules()
            self.ui.btn_admin.setText(f"관리자: {self.current_user}")
            self._reload_all_tabs()

    def on_click_custom(self):
        """품명 관리 다이얼로그 오픈"""
        dlg = ProductNameDialog(self)
        dlg.exec_()

    def on_click_same_product(self):
        """작업품목병합 다이얼로그 오픈"""
        dlg = SameProductDialog(self)
        dlg.exec_()

    def refresh_uname_map_cache(self):
        """Dashboard_UNAME_MAP 테이블에서 매핑 정보 로드하여 캐시 갱신"""
        self.uname_map_cache = {}
        try:
            with db_connection(DB_NAME) as (conn, cur):
                sql = "SELECT before_value, after_value FROM Dashboard_UNAME_MAP"
                df = runquery(cur, sql)
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        bf = str(row['before_value']).strip()
                        af = row['after_value']
                        if af is not None:
                            af = str(af).strip()
                            if af:
                                self.uname_map_cache[bf] = af
        except Exception as e:
            print(f"매핑 캐시 로드 실패: {e}")

        if hasattr(self, 'loader'):
            self.loader.load_product_tab()

    def logout_if_logged_in(self):
        if self.current_level >= 1:
            self.on_click_toggle_admin()

    def on_click_toggle_show_hide(self):
        self.show_hidden = not self.show_hidden
        self.ui.btn_show_hide.setText("숨김포함" if self.show_hidden else "숨김제외")
        self.loader.load_product_tab()

    def on_click_show_log_dialog(self):
        dlg = DashboardLogDialog(self)
        dlg.exec_()

    # =====================================================
    # 3. 탭 / 날짜 이동
    # =====================================================
    def on_click_prev_date(self):
        self.ui.dateEdit.setDate(self.ui.dateEdit.date().addDays(-1))

    def on_click_next_date(self):
        self.ui.dateEdit.setDate(self.ui.dateEdit.date().addDays(1))

    def on_date_changed(self):
        self.product_page = 0
        qdate = self.ui.dateEdit.date()
        date_str = qdate.toString("yyyy-MM-dd")
        weekday_str = qdate.toString("ddd")
        self.ui.dateText.setText(f"{date_str} ({weekday_str})")
        self._tab_loader(self.ui.tabWidget.currentIndex())

    def on_click_tab_product(self):
        self.ui.tabWidget.setCurrentIndex(0)

    def on_click_tab_raw(self):
        self.ui.tabWidget.setCurrentIndex(1)

    def on_click_tab_sauce(self):
        self.ui.tabWidget.setCurrentIndex(2)

    def on_click_tab_vege(self):
        self.ui.tabWidget.setCurrentIndex(3)

    def on_tab_changed(self, idx: int):
        self._tab_loader(idx)

    # =====================================================
    # 업체 필터링 (제품 탭)
    # =====================================================
    def _change_vendor_filter(self, vendor_name: str):
        self.current_vendor = vendor_name
        self.product_page = 0
        self.loader.load_product_tab()

    def on_click_filter_costco(self):
        self._change_vendor_filter("코스트코")

    def on_click_filter_emart(self):
        self._change_vendor_filter("이마트")

    def on_click_filter_hk(self):
        self._change_vendor_filter("홈플/컬리")

    def on_click_filter_lotte(self):
        self._change_vendor_filter("롯데")
