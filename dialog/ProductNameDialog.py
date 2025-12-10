from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QMessageBox, QAbstractItemView
)
from PyQt5.QtCore import Qt
from UTIL.db_handler import getdb, runquery, closedb

class ProductNameDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("품명 관리")
        self.resize(600, 400)
        
        self.layout = QVBoxLayout(self)
        
        # 테이블 설정
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["기존 품명 (Before)", "변경 품명 (After)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.layout.addWidget(self.table)
        
        # 버튼 설정
        btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("추가")
        self.btn_del = QPushButton("삭제")
        self.btn_save = QPushButton("저장")
        self.btn_close = QPushButton("닫기")
        
        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_del)
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_close)
        self.layout.addLayout(btn_layout)
        
        # 이벤트 연결
        self.btn_add.clicked.connect(self.on_add)
        self.btn_del.clicked.connect(self.on_del)
        self.btn_save.clicked.connect(self.on_save)
        self.btn_close.clicked.connect(self.accept)
        
        # 데이터 로드
        self.load_data()
        
    def load_data(self):
        self.table.setRowCount(0)
        conn, cur = getdb("GP")
        try:
            sql = "SELECT before_value, after_value FROM Dashboard_UNAME_MAP"
            df = runquery(cur, sql)
            
            if df is not None and not df.empty:
                self.table.setRowCount(len(df))
                for i, row in df.iterrows():
                    self.table.setItem(i, 0, QTableWidgetItem(str(row['before_value'])))
                    self.table.setItem(i, 1, QTableWidgetItem(str(row['after_value'])))
        except Exception as e:
            QMessageBox.critical(self, "오류", f"데이터 로드 중 오류 발생: {e}")
        finally:
            closedb(conn)
            
    def on_add(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(""))
        self.table.setItem(row, 1, QTableWidgetItem(""))
        
    def on_del(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)
            
    def on_save(self):
        conn, cur = getdb("GP")
        try:
            # 기존 데이터 삭제 후 재입력 방식 (간단한 구현)
            # 주의: 실제 운영 환경에서는 ID 기반 UPDATE/DELETE가 더 안전함
            # 여기서는 요구사항에 맞춰 전체 갱신으로 처리하거나, 변경분만 처리해야 함.
            # 사용자 요구사항: "INSERT, UPDATE, DELETE할 수 있어야한다."
            # 간단하게 전체 삭제 후 다시 넣는 방식이 가장 확실하긴 함 (데이터 양이 적다면).
            # 하지만 안전하게 트랜잭션 처리.
            
            cur.execute("DELETE FROM Dashboard_UNAME_MAP")
            
            rows = self.table.rowCount()
            for i in range(rows):
                before_item = self.table.item(i, 0)
                after_item = self.table.item(i, 1)
                
                if before_item and after_item:
                    before_val = before_item.text().strip()
                    after_val = after_item.text().strip()
                    
                    if before_val and after_val:
                        sql = "INSERT INTO Dashboard_UNAME_MAP (before_value, after_value) VALUES (%s, %s)"
                        cur.execute(sql, (before_val, after_val))
            
            conn.commit()
            QMessageBox.information(self, "저장", "저장되었습니다.")
            
            # 메인 윈도우 캐시 갱신 요청
            if self.parent():
                if hasattr(self.parent(), 'refresh_uname_map_cache'):
                    self.parent().refresh_uname_map_cache()
                    
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, "오류", f"저장 중 오류 발생: {e}")
        finally:
            closedb(conn)
