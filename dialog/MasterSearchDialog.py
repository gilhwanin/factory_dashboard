from PyQt5.QtWidgets import (

    QTableWidgetItem,
    QMessageBox,

    QTableWidget,
    QHeaderView,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QComboBox
)

from UTIL.db_handler import getdb, runquery, closedb
from UTIL.utils_qt import apply_table_style

VENDOR_CHOICES = ["코스온", "이마트", "홈플러스", "마켓컬리"]

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