from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QWidget,
    QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QMessageBox,
)
from PyQt5.QtCore import Qt

from UTIL.db_handler import getdb, runquery, closedb
from UTIL.utils_qt import apply_table_style
from dialog.MasterSearchDialog import MasterSearchDialog


class SameProductDialog(QDialog):
    """
    작업품목병합 관리 다이얼로그
    - 같은 제품(중량만 다른)을 그룹으로 묶어 관리
    - GP.same_product 테이블에 저장
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("작업품목병합 관리")
        self.resize(850, 500)

        self._groups = {}           # {group_id: [(co, uname), ...]}
        self._current_group_id = None

        self._ensure_table()
        self._build_ui()
        self._load_all_groups()

    # =========================================================
    # 테이블 자동 생성
    # =========================================================
    @staticmethod
    def _ensure_table():
        conn, cur = getdb("GP")
        if conn is None:
            return
        try:
            runquery(cur, """
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'same_product')
                BEGIN
                    CREATE TABLE same_product (
                        PK         INT IDENTITY(1,1) PRIMARY KEY,
                        group_id   INT          NOT NULL,
                        co         VARCHAR(50)  NOT NULL,
                        uname      VARCHAR(200) NULL,
                        created_at DATETIME     DEFAULT GETDATE(),
                        CONSTRAINT UQ_same_product_co UNIQUE (co)
                    );
                    CREATE INDEX IX_same_product_group_id
                        ON same_product (group_id);
                END
            """)
            conn.commit()
        except Exception as e:
            print(f"[SameProductDialog] 테이블 생성 오류: {e}")
        finally:
            closedb(conn)

    # =========================================================
    # UI 구성
    # =========================================================
    def _build_ui(self):
        main_layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal, self)

        # ---------- 왼쪽: 그룹 목록 ----------
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)

        left_lay.addWidget(QLabel("그룹 목록"))

        self.list_groups = QListWidget()
        left_lay.addWidget(self.list_groups)

        left_btn = QHBoxLayout()
        self.btn_add_group = QPushButton("그룹 추가")
        self.btn_del_group = QPushButton("그룹 삭제")
        left_btn.addWidget(self.btn_add_group)
        left_btn.addWidget(self.btn_del_group)
        left_lay.addLayout(left_btn)

        splitter.addWidget(left)

        # ---------- 오른쪽: 그룹 상세 ----------
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)

        self.label_detail = QLabel("그룹 상세")
        right_lay.addWidget(self.label_detail)

        self.table_detail = QTableWidget(0, 2)
        self.table_detail.setHorizontalHeaderLabels(["CO", "상품명"])
        header = self.table_detail.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setDefaultSectionSize(80)
        header.setMinimumSectionSize(60)
        self.table_detail.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_detail.setEditTriggers(QTableWidget.NoEditTriggers)
        apply_table_style(self.table_detail)
        right_lay.addWidget(self.table_detail)

        right_btn = QHBoxLayout()
        self.btn_add_item = QPushButton("품목 추가")
        self.btn_remove_item = QPushButton("품목 제거")
        right_btn.addWidget(self.btn_add_item)
        right_btn.addWidget(self.btn_remove_item)
        right_lay.addLayout(right_btn)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter)

        # ---------- 하단 ----------
        bottom = QHBoxLayout()
        bottom.addStretch()
        self.btn_close = QPushButton("닫기")
        bottom.addWidget(self.btn_close)
        main_layout.addLayout(bottom)

        # ---------- 시그널 ----------
        self.list_groups.currentRowChanged.connect(self._on_group_selected)
        self.btn_add_group.clicked.connect(self._on_add_group)
        self.btn_del_group.clicked.connect(self._on_del_group)
        self.btn_add_item.clicked.connect(self._on_add_item)
        self.btn_remove_item.clicked.connect(self._on_remove_item)
        self.btn_close.clicked.connect(self.accept)

    # =========================================================
    # 데이터 로드
    # =========================================================
    def _load_all_groups(self):
        self._groups = {}
        conn, cur = getdb("GP")
        if conn is None:
            self._refresh_group_list()
            return
        try:
            df = runquery(cur, """
                SELECT group_id, co, uname
                FROM same_product
                ORDER BY group_id, co
            """)
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    gid = int(row["group_id"])
                    co = str(row["co"]).strip()
                    uname = str(row["uname"]).strip() if row["uname"] else ""
                    self._groups.setdefault(gid, []).append((co, uname))
        finally:
            closedb(conn)

        self._refresh_group_list()

    def _get_next_group_id(self):
        conn, cur = getdb("GP")
        if conn is None:
            return 1
        try:
            df = runquery(cur, """
                SELECT ISNULL(MAX(group_id), 0) + 1 AS next_id
                FROM same_product
            """)
            if df is not None and not df.empty:
                return int(df.iloc[0]["next_id"])
            return 1
        finally:
            closedb(conn)

    # =========================================================
    # UI 갱신
    # =========================================================
    def _refresh_group_list(self):
        prev_gid = self._current_group_id
        self.list_groups.clear()

        select_row = 0
        for idx, gid in enumerate(sorted(self._groups.keys())):
            items = self._groups[gid]
            if items:
                first_name = items[0][1] or items[0][0]
                if len(items) > 1:
                    label = f"그룹 {gid}: {first_name} 외 {len(items)-1}건"
                else:
                    label = f"그룹 {gid}: {first_name}"
            else:
                label = f"그룹 {gid}: (비어있음)"

            li = QListWidgetItem(label)
            li.setData(Qt.UserRole, gid)
            self.list_groups.addItem(li)

            if gid == prev_gid:
                select_row = idx

        if self.list_groups.count() > 0:
            self.list_groups.setCurrentRow(select_row)
        else:
            self.table_detail.setRowCount(0)
            self._current_group_id = None

    def _on_group_selected(self, row):
        if row < 0:
            self.table_detail.setRowCount(0)
            self._current_group_id = None
            self.label_detail.setText("그룹 상세")
            return

        item = self.list_groups.item(row)
        gid = item.data(Qt.UserRole)
        self._current_group_id = gid
        self.label_detail.setText(f"그룹 {gid} 상세")

        self.table_detail.setRowCount(0)
        for co, uname in self._groups.get(gid, []):
            r = self.table_detail.rowCount()
            self.table_detail.insertRow(r)
            self.table_detail.setItem(r, 0, QTableWidgetItem(co))
            self.table_detail.setItem(r, 1, QTableWidgetItem(uname))

    # =========================================================
    # 핸들러
    # =========================================================
    def _on_add_group(self):
        """새 그룹 생성 (MasterSearchDialog로 첫 품목 선택)"""
        dlg = MasterSearchDialog(self, show_vendor=False)
        if dlg.exec_() != QDialog.Accepted or not dlg.selected_co:
            return

        co = dlg.selected_co
        uname = dlg.selected_uname or ""

        if self._co_exists(co):
            QMessageBox.warning(
                self, "안내",
                f"CO [{co}]은(는) 이미 다른 그룹에 포함되어 있습니다.",
            )
            return

        new_gid = self._get_next_group_id()
        conn, cur = getdb("GP")
        if conn is None:
            return
        try:
            runquery(cur, """
                INSERT INTO same_product (group_id, co, uname)
                VALUES (%s, %s, %s)
            """, [new_gid, co, uname])
            conn.commit()
        finally:
            closedb(conn)

        self._current_group_id = new_gid
        self._load_all_groups()

    def _on_del_group(self):
        """선택 그룹 전체 삭제"""
        if self._current_group_id is None:
            QMessageBox.information(self, "안내", "삭제할 그룹을 선택하세요.")
            return

        reply = QMessageBox.question(
            self, "확인",
            f"그룹 {self._current_group_id}을(를) 삭제하시겠습니까?\n"
            f"포함된 모든 품목이 해제됩니다.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        conn, cur = getdb("GP")
        if conn is None:
            return
        try:
            runquery(cur, """
                DELETE FROM same_product WHERE group_id = %s
            """, [self._current_group_id])
            conn.commit()
        finally:
            closedb(conn)

        self._current_group_id = None
        self._load_all_groups()

    def _on_add_item(self):
        """현재 그룹에 품목 추가"""
        if self._current_group_id is None:
            QMessageBox.information(
                self, "안내", "품목을 추가할 그룹을 먼저 선택하세요.",
            )
            return

        dlg = MasterSearchDialog(self, show_vendor=False)
        if dlg.exec_() != QDialog.Accepted or not dlg.selected_co:
            return

        co = dlg.selected_co
        uname = dlg.selected_uname or ""

        if self._co_exists(co):
            QMessageBox.warning(
                self, "안내",
                f"CO [{co}]은(는) 이미 다른 그룹에 포함되어 있습니다.",
            )
            return

        conn, cur = getdb("GP")
        if conn is None:
            return
        try:
            runquery(cur, """
                INSERT INTO same_product (group_id, co, uname)
                VALUES (%s, %s, %s)
            """, [self._current_group_id, co, uname])
            conn.commit()
        finally:
            closedb(conn)

        self._load_all_groups()

    def _on_remove_item(self):
        """선택 품목 제거"""
        rows = sorted(
            {idx.row() for idx in self.table_detail.selectedIndexes()},
            reverse=True,
        )
        if not rows:
            QMessageBox.information(self, "안내", "제거할 품목을 선택하세요.")
            return

        conn, cur = getdb("GP")
        if conn is None:
            return
        try:
            for r in rows:
                co = self.table_detail.item(r, 0).text()
                runquery(cur, """
                    DELETE FROM same_product WHERE co = %s
                """, [co])
            conn.commit()
        finally:
            closedb(conn)

        self._load_all_groups()

    # =========================================================
    # 유틸
    # =========================================================
    def _co_exists(self, co):
        """이미 어떤 그룹에든 포함된 CO인지 확인"""
        for members in self._groups.values():
            for existing_co, _ in members:
                if existing_co == co:
                    return True
        return False
