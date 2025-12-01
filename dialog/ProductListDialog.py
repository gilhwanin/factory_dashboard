from PyQt5.QtWidgets import (
    QTableWidgetItem,
    QMessageBox,
    QTableWidget,
    QHeaderView,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
)

from UTIL.db_handler import getdb, runquery, closedb
from UTIL.utils_qt import apply_table_style
from dialog.MasterSearchDialog import MasterSearchDialog

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