from PyQt5.QtWidgets import (
    QTableWidgetItem,
    QMessageBox,
    QTableWidget,
    QHeaderView,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QGroupBox,
)

from UTIL.db_handler import getdb, runquery, closedb
from UTIL.utils_qt import apply_table_style
from dialog.MasterSearchDialog import MasterSearchDialog
from UTIL.const import VENDOR_CHOICES
from UTIL.db_product_handler import fetch_default_products, add_default_product, remove_default_product

class ProductListDialog(QDialog):
    """
    제품 대시보드 리스트 관리 창
    - 로컬 리스트 (현재 세션용): 자유롭게 추가/삭제/초기화
    - DB 기본값 (영구 저장용): 별도 버튼으로 DB에 추가/삭제
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("제품 리스트 관리")
        self.resize(800, 500)
        
        # 만약 비어 있으면 DB에서 로드 (최초 실행 시 등)
        self._product_list = fetch_default_products()

        main_layout = QVBoxLayout(self)

        # -------------------
        # 테이블
        # -------------------
        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["CO", "업체명", "상품명(UNAME)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        # 스타일 적용
        apply_table_style(self.table)
        main_layout.addWidget(self.table)

        # -------------------
        # 로컬 관리 버튼 (현재 리스트)
        # -------------------
        local_group = QGroupBox("현재 리스트 편집 (프로그램 종료 시 초기화됨)")
        local_layout = QHBoxLayout()
        
        self.btn_add = QPushButton("추가")
        self.btn_remove = QPushButton("삭제")
        self.btn_reset = QPushButton("기본리스트 초기화") # DB에서 재조회
        
        local_layout.addWidget(self.btn_add)
        local_layout.addWidget(self.btn_remove)
        local_layout.addWidget(self.btn_reset)
        local_layout.addStretch()
        local_group.setLayout(local_layout)
        
        main_layout.addWidget(local_group)

        # -------------------
        # DB 관리 버튼 (기본값)
        # -------------------
        db_group = QGroupBox("기본값 관리 (영구 저장 - DB)")
        db_layout = QHBoxLayout()
        
        self.btn_db_add = QPushButton("기본값에 추가")
        self.btn_db_remove = QPushButton("기본값에 삭제")
        
        db_layout.addWidget(self.btn_db_add)
        db_layout.addWidget(self.btn_db_remove)
        db_layout.addStretch()
        db_group.setLayout(db_layout)
        
        main_layout.addWidget(db_group)

        # -------------------
        # 하단 확인/취소
        # -------------------
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        self.btn_ok = QPushButton("적용")
        self.btn_cancel = QPushButton("취소")
        bottom_layout.addWidget(self.btn_ok)
        bottom_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(bottom_layout)

        # 시그널 연결
        self.btn_add.clicked.connect(self.on_add)
        self.btn_remove.clicked.connect(self.on_remove)
        self.btn_reset.clicked.connect(self.on_reset)
        
        self.btn_db_add.clicked.connect(self.on_db_add)
        self.btn_db_remove.clicked.connect(self.on_db_remove)
        
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
    # 테이블 리로드 (로컬 리스트 기준)
    # -----------------------------------------------------
    def _reload_table(self):
        self.table.setRowCount(0)

        cos = sorted({co for co, _ in self._product_list})
        uname_map = self._fetch_uname_map(cos)

        # 리스트 정렬
        sorted_list = sorted(self._product_list, key=lambda x: (x[1], x[0]))

        for co, vendor in sorted_list:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(co)))
            self.table.setItem(row, 1, QTableWidgetItem(str(vendor)))
            self.table.setItem(row, 2, QTableWidgetItem(uname_map.get(str(co), "")))

    # -----------------------------------------------------
    # 로컬 핸들러
    # -----------------------------------------------------
    def on_add(self):
        """[추가] MasterSearchDialog를 띄워 로컬 리스트에 품목 추가"""
        dlg = MasterSearchDialog(self)
        if dlg.exec_() == QDialog.Accepted and dlg.selected_co:
            key = (dlg.selected_co, dlg.selected_vendor)
            
            if key in self._product_list:
                QMessageBox.information(self, "안내", "현재 리스트에 이미 존재합니다.")
                return
            
            self._product_list.append(key)
            self._reload_table()

    def on_remove(self):
        """[삭제] 로컬 리스트에서 선택된 행 삭제"""
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()}, reverse=True)
        if not rows:
            QMessageBox.information(self, "안내", "삭제할 항목을 선택해주세요.")
            return

        for r in rows:
            co = self.table.item(r, 0).text()
            vendor = self.table.item(r, 1).text()
            if (co, vendor) in self._product_list:
                self._product_list.remove((co, vendor))
        
        self._reload_table()

    def on_reset(self):
        """[기본리스트 초기화] DB에서 재조회하여 로컬 리스트 초기화"""
        if QMessageBox.question(self, "확인", "DB 기본값으로 현재 리스트를 초기화하시겠습니까?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            self._product_list = fetch_default_products()
            self._reload_table()
            QMessageBox.information(self, "완료", "초기화되었습니다.")

    # -----------------------------------------------------
    # DB 핸들러
    # -----------------------------------------------------
    def on_db_add(self):
        """[기본값에 추가] MasterSearchDialog 띄워 DB에 추가"""
        dlg = MasterSearchDialog(self)
        if dlg.exec_() == QDialog.Accepted and dlg.selected_co:
            co = dlg.selected_co
            vendor = dlg.selected_vendor
            
            # DB 추가
            add_default_product(co, vendor)
            QMessageBox.information(self, "완료", f"DB 기본값에 추가되었습니다.\n({co}, {vendor})")
            
            # (옵션) 로컬 리스트에도 없으면 추가해줄까? 사용자가 원할 수 있음.
            # 요구사항엔 명시 안되어있지만 편의상 추가 여부를 물어보거나 자동 추가 등 가능.
            # 일단 요구사항대로 DB만 처리하고, 사용자가 리셋 누르면 반영되도록 둠.

    def on_db_remove(self):
        """[기본값에 삭제] 선택된 품목들을 DB에서 삭제"""
        rows = sorted({idx.row() for idx in self.table.selectedIndexes()})
        if not rows:
            QMessageBox.information(self, "안내", "DB에서 삭제할 항목을 선택해주세요.")
            return

        if QMessageBox.question(self, "확인", "선택한 항목을 DB(기본값)에서 영구 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.No:
            return

        # 현재 DB에 있는 목록 조회하여 비교
        current_db_list = fetch_default_products() # List of (co, retailer)
        
        success_count = 0
        not_found_count = 0
        
        for r in rows:
            co = self.table.item(r, 0).text()
            vendor = self.table.item(r, 1).text()
            
            if (co, vendor) in current_db_list:
                remove_default_product(co, vendor)
                success_count += 1
            else:
                not_found_count += 1
        
        msg = f"{success_count}건이 DB에서 삭제되었습니다."
        if not_found_count > 0:
            msg += f"\n\n[주의] {not_found_count}건은 DB에 존재하지 않아 삭제되지 않았습니다."
            QMessageBox.warning(self, "완료 (일부 실패)", msg)
        else:
            QMessageBox.information(self, "완료", msg)

    def get_product_list(self):
        return list(self._product_list)