from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QMessageBox, QAbstractItemView, QComboBox,
    QLabel, QStyledItemDelegate, QSpinBox
)
from PyQt5.QtCore import Qt
from UTIL.db_handler import getdb, runquery, closedb

# 업체 목록 상수 (Dashboard 등과 통일성을 위해 config에서 가져오거나 상수로 정의)
RETAILERS = ["코스트코", "이마트", "홈플러스", "마켓컬리"]

class RetailerDelegate(QStyledItemDelegate):
    """테이블 내 '업체' 컬럼을 콤보박스로 편집하기 위한 델리게이트"""
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

class DeadlineDelegate(QStyledItemDelegate):
    """테이블 내 '소비기한' 컬럼을 정수(SpinBox)로 편집하기 위한 델리게이트"""
    def createEditor(self, parent, option, index):
        spin = QSpinBox(parent)
        spin.setRange(0, 9999) # 적절한 범위 설정
        return spin

    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.EditRole)
        try:
            val_int = int(value)
            editor.setValue(val_int)
        except:
            editor.setValue(0)

    def setModelData(self, editor, model, index):
        model.setData(index, str(editor.value()), Qt.EditRole)

class ProductNameDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("품명 관리")
        self.resize(800, 500)
        
        self.layout = QVBoxLayout(self)
        
        # 🟢 상단 필터 영역
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("업체 선택:"))
        self.combo_filter = QComboBox()
        self.combo_filter.addItem("전체")
        self.combo_filter.addItems(RETAILERS)
        filter_layout.addWidget(self.combo_filter)
        filter_layout.addStretch()
        self.layout.addLayout(filter_layout)

        # 🟢 테이블 설정
        self.table = QTableWidget()
        # 컬럼: 업체, 기존 품명(Before), 변경 품명(After), 소비기한(Deadline)
        self.cols = ["retailer", "before_value", "after_value", "deadline"]
        headers = ["업체", "기존 품명 (Before)", "변경 품명 (After)", "소비기한 (일)"]
        
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        # 델리게이트 설정
        self.table.setItemDelegateForColumn(0, RetailerDelegate(self.table))
        self.table.setItemDelegateForColumn(3, DeadlineDelegate(self.table))

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
        self.combo_filter.currentIndexChanged.connect(self.load_data) # 필터 변경 시 로드
        
        # 데이터 로드
        self.load_data()
        
    def load_data(self):
        self.table.setRowCount(0)
        conn, cur = getdb("GP")
        try:
            # 조회 쿼리 구성
            sql = "SELECT before_value, after_value, deadline, retailer FROM Dashboard_UNAME_MAP"
            params = []
            
            filter_retailer = self.combo_filter.currentText()
            if filter_retailer != "전체":
                sql += " WHERE retailer = %s"
                params.append(filter_retailer)
            
            df = runquery(cur, sql, params)
            
            if df is not None and not df.empty:
                self.table.setRowCount(len(df))
                for i, row in df.iterrows():
                    # 0: retailer
                    self.table.setItem(i, 0, QTableWidgetItem(str(row['retailer']) if row['retailer'] else ""))
                    # 1: before
                    self.table.setItem(i, 1, QTableWidgetItem(str(row['before_value'])))
                    # 2: after
                    self.table.setItem(i, 2, QTableWidgetItem(str(row['after_value'])))
                    # 3: deadline
                    # None이나 NaN 처리
                    deadline_val = str(int(row['deadline'])) if row['deadline'] is not None and str(row['deadline']).isdigit() else "0"
                    self.table.setItem(i, 3, QTableWidgetItem(deadline_val))
                    
        except Exception as e:
            QMessageBox.critical(self, "오류", f"데이터 로드 중 오류 발생: {e}")
        finally:
            closedb(conn)
            
    def on_add(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # 필터가 특정 업체로 되어있으면 그 업체를 기본값으로 설정
        current_filter = self.combo_filter.currentText()
        default_retailer = current_filter if current_filter != "전체" else "코스트코"
        
        self.table.setItem(row, 0, QTableWidgetItem(default_retailer))
        self.table.setItem(row, 1, QTableWidgetItem(""))
        self.table.setItem(row, 2, QTableWidgetItem(""))
        self.table.setItem(row, 3, QTableWidgetItem("0"))
        
    def on_del(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)
            
    def on_save(self):
        conn, cur = getdb("GP")
        try:
            filter_retailer = self.combo_filter.currentText()
            
            # 1. 삭제 전략: 필터링된 범위에 따라 삭제
            if filter_retailer == "전체":
                cur.execute("DELETE FROM Dashboard_UNAME_MAP") # 전체 삭제
            else:
                cur.execute("DELETE FROM Dashboard_UNAME_MAP WHERE retailer = %s", (filter_retailer,)) # 해당 업체만 삭제

            # 2. 현재 테이블에 있는 데이터 INSERT (필터링된 상태면 그 업체 데이터들만 있을 것임)
            # 만약 '전체' 보기 상태에서 일부만 삭제/추가했다면 전체가 다시 들어감.
            # 만약 '코스트코' 보기 상태라면 코스트코 데이터만 다시 들어감.
            
            rows = self.table.rowCount()
            for i in range(rows):
                retailer_item = self.table.item(i, 0)
                before_item = self.table.item(i, 1)
                after_item = self.table.item(i, 2)
                deadline_item = self.table.item(i, 3)
                
                if before_item and after_item:
                    retailer_val = retailer_item.text().strip() if retailer_item else ""
                    before_val = before_item.text().strip()
                    after_val = after_item.text().strip()
                    
                    deadline_text = deadline_item.text().strip() if deadline_item else "0"
                    try:
                        deadline_val = int(deadline_text)
                    except:
                        deadline_val = 0
                    
                    if not retailer_val:
                        # 업체명이 비어있으면 저장하지 않거나 기본값 처리? -> 여기서는 스킵 혹은 경고가 좋겠지만 일단 로직상 필수
                        continue

                    if before_val and after_val:
                        sql = """
                            INSERT INTO Dashboard_UNAME_MAP 
                            (before_value, after_value, deadline, retailer) 
                            VALUES (%s, %s, %s, %s)
                        """
                        cur.execute(sql, (before_val, after_val, deadline_val, retailer_val))
            
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
