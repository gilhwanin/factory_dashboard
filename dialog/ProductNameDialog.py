from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QMessageBox, QAbstractItemView, QComboBox,
    QLabel, QStyledItemDelegate, QSpinBox
)
from PyQt5.QtCore import Qt
from UTIL.db_handler import getdb, runquery, closedb

# 업체 목록
RETAILERS = ["코스트코", "이마트", "홈플러스", "마켓컬리"]


# -----------------------------
# 업체 콤보 델리게이트
# -----------------------------
class RetailerDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        combo = QComboBox(parent)
        combo.addItems(RETAILERS)
        return combo

    def setEditorData(self, editor, index):
        text = index.model().data(index, Qt.EditRole)
        if text:
            idx = editor.findText(text)
            if idx >= 0:
                editor.setCurrentIndex(idx)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.EditRole)


# -----------------------------
# 소비기한 SpinBox 델리게이트
# -----------------------------
class DeadlineDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        spin = QSpinBox(parent)
        spin.setRange(0, 9999)
        return spin

    def setEditorData(self, editor, index):
        try:
            editor.setValue(int(index.model().data(index, Qt.EditRole)))
        except:
            editor.setValue(0)

    def setModelData(self, editor, model, index):
        model.setData(index, str(editor.value()), Qt.EditRole)


# -----------------------------
# 메인 다이얼로그
# -----------------------------
class ProductNameDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("품명 관리")
        self.resize(900, 520)

        self._loading = False  # itemChanged 중복 저장 방지 플래그

        layout = QVBoxLayout(self)

        # -------------------------
        # 상단 업체 선택
        # -------------------------
        top = QHBoxLayout()
        top.addWidget(QLabel("업체 선택:"))
        self.combo_filter = QComboBox()
        self.combo_filter.addItems(RETAILERS)
        top.addWidget(self.combo_filter)
        top.addStretch()
        layout.addLayout(top)

        # -------------------------
        # 테이블
        # -------------------------
        self.table = QTableWidget()
        headers = ["업체", "기존 품명 (Before)", "변경 품명 (After)", "소비기한 (일)"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.table.setItemDelegateForColumn(0, RetailerDelegate(self.table))
        self.table.setItemDelegateForColumn(3, DeadlineDelegate(self.table))

        layout.addWidget(self.table)

        # -------------------------
        # 버튼
        # -------------------------
        btns = QHBoxLayout()
        self.btn_add = QPushButton("추가")
        self.btn_del = QPushButton("삭제")
        self.btn_close = QPushButton("닫기")

        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_del)
        btns.addStretch()
        btns.addWidget(self.btn_close)

        layout.addLayout(btns)

        # -------------------------
        # 이벤트 연결
        # -------------------------
        self.combo_filter.currentIndexChanged.connect(self.load_data)
        self.btn_add.clicked.connect(self.on_add)
        self.btn_del.clicked.connect(self.on_del)
        self.btn_close.clicked.connect(self.accept)

        self.table.itemChanged.connect(self.auto_save)

        # 최초 로드
        self.load_data()

    # -------------------------
    # 데이터 로드
    # -------------------------
    def load_data(self):
        self._loading = True
        self.table.setRowCount(0)

        conn, cur = getdb("GP")
        try:
            retailer = self.combo_filter.currentText()
            sql = """
                SELECT before_value, after_value, deadline, retailer
                FROM Dashboard_UNAME_MAP
                WHERE retailer = %s
            """
            df = runquery(cur, sql, [retailer])

            if df is not None and not df.empty:
                self.table.setRowCount(len(df))
                for i, row in df.iterrows():
                    self.table.setItem(i, 0, QTableWidgetItem(row["retailer"]))
                    self.table.setItem(i, 1, QTableWidgetItem(str(row["before_value"])))
                    self.table.setItem(i, 2, QTableWidgetItem(str(row["after_value"])))
                    self.table.setItem(
                        i, 3,
                        QTableWidgetItem(str(int(row["deadline"])) if row["deadline"] else "0")
                    )
        finally:
            closedb(conn)
            self._loading = False

    # -------------------------
    # 행 추가
    # -------------------------
    def on_add(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        retailer = self.combo_filter.currentText()

        self.table.setItem(row, 0, QTableWidgetItem(retailer))
        self.table.setItem(row, 1, QTableWidgetItem(""))
        self.table.setItem(row, 2, QTableWidgetItem(""))
        self.table.setItem(row, 3, QTableWidgetItem("0"))

    # -------------------------
    # 행 삭제
    # -------------------------
    def on_del(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self.auto_save()

    # -------------------------
    # 자동 저장 (핵심)
    # -------------------------
    def auto_save(self):
        if self._loading:
            return

        conn, cur = getdb("GP")
        try:
            retailer = self.combo_filter.currentText()

            # 1️⃣ 해당 업체 데이터 전체 삭제
            cur.execute(
                "DELETE FROM Dashboard_UNAME_MAP WHERE retailer = %s",
                (retailer,)
            )

            # 2️⃣ 현재 테이블 상태 그대로 INSERT
            for i in range(self.table.rowCount()):
                before_item = self.table.item(i, 1)
                after_item = self.table.item(i, 2)
                deadline_item = self.table.item(i, 3)  # ✅ 이 줄 추가

                if not before_item:
                    continue

                before_val = before_item.text().strip()
                after_val = after_item.text().strip() if after_item else ""

                # before_value만 필수
                if not before_val:
                    continue

                try:
                    deadline_val = int(deadline_item.text()) if deadline_item else 0
                except:
                    deadline_val = 0

                cur.execute(
                    """
                    INSERT INTO Dashboard_UNAME_MAP
                    (before_value, after_value, deadline, retailer)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (before_val, after_val, deadline_val, retailer)
                )

            conn.commit()

            # 메인 캐시 갱신
            if self.parent() and hasattr(self.parent(), "refresh_uname_map_cache"):
                self.parent().refresh_uname_map_cache()

        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "오류", f"자동 저장 실패:\n{e}")
        finally:
            closedb(conn)
