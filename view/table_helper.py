from PyQt5.QtWidgets import QTableWidget, QAbstractItemView, QTableWidgetItem, QHeaderView
from PyQt5.QtGui import QColor, QBrush
from PyQt5.QtCore import Qt
from config import COL_PRODUCT, COL_PLAN, COL_TODAY_RES, COL_PREV_RES

def setup_table_base(table: QTableWidget):
    """기본 테이블 스타일 및 설정"""
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

def create_base_item(text, pk, alignment, editable=False, foreground=None):
    """기본 테이블 아이템 생성"""
    item = QTableWidgetItem(str(text))
    item.setTextAlignment(alignment)
    
    if pk is not None:
        item.setData(Qt.UserRole, pk)
        
    flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
    if editable:
        flags |= Qt.ItemIsEditable
    item.setFlags(flags)
    
    if foreground:
        item.setForeground(QBrush(foreground))
        
    return item

def apply_column_visibility(table: QTableWidget, level: int):
    """권한(level)에 따른 컬럼 숨김/표시 처리"""
    # 기본적으로 모든 컬럼 표시 후
    for c in range(table.columnCount()):
        table.setColumnHidden(c, False)
        
    # 레벨에라 숨김 처리 로직 (필요 시 구현)
    # 현재 main.py의 _apply_column_visibility_rules 참조하여 이식 필요
    pass
