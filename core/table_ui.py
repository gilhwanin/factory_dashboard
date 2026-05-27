from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QBrush, QColor, QFont
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)

from UTIL.const import (
    COL_VENDOR, COL_PRODUCT, COL_DEADLINE, COL_PKG,
    COL_FINAL_ORDER, COL_CUR_PROD, COL_SHIPMENT_TIME,
    COL_PLAN, COL_PLAN_KG, COL_TODAY_RES, COL_PREV_RES,
    COL_PRODUCTION, COL_WORK_STATUS,
)

if TYPE_CHECKING:
    from core.widget import OrderDashboardWidget


class TableUIManager:
    def __init__(self, widget: OrderDashboardWidget):
        self.w = widget

    # --------------------------------------------------
    # 테이블 기본 스타일
    # --------------------------------------------------
    def setup_table_base(self, table: QTableWidget):
        table.setAlternatingRowColors(True)
        table.setShowGrid(True)
        table.setEditTriggers(QAbstractItemView.DoubleClicked)
        table.setStyleSheet("""
            QTableWidget {
                font-size: 20px;
                alternate-background-color: #f6f7fb;
                gridline-color: #c0c0c0;
            }
            QHeaderView::section {
                font-size: 20px;
                font-weight: bold;
                color: black;
                padding: 5px;
                border: 1px solid #a0a0a0;
            }
        """)
        table.verticalHeader().setDefaultSectionSize(60)
        table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)

    # --------------------------------------------------
    # 헤더 설정
    # --------------------------------------------------
    def setup_product_headers(self, table: QTableWidget):
        headers = [
            "업체명", "품명", "소비기한", "팩중량", "발주량",
            "최종발주", "팩 차이", "전일 잔피", "생산 팩수", "생산계획",
            "팩수 to kg", "데크출고", "최근출고", "당일 잔피", "수율", "작업상태",
        ]

        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)

        header_normal = QColor("#8fbcd4")
        header_live = QColor("#b7d9ff")

        for col in range(len(headers)):
            item = table.horizontalHeaderItem(col)
            if not item:
                continue
            if col in (COL_FINAL_ORDER, COL_CUR_PROD, COL_SHIPMENT_TIME):
                item.setBackground(QBrush(header_live))
            else:
                item.setBackground(QBrush(header_normal))

    def setup_material_headers(self, table: QTableWidget):
        """Raw/Sauce/Vege 공통 헤더"""
        headers = [
            "품명", "재고량", "예상발주량", "최종발주량",
            "선 생산량", "예상부족량", "입고예정량", "예상재고",
        ]

        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)

        header_normal = QColor("#8fbcd4")
        header_edit = QColor("#ffdd99")

        for col in range(len(headers)):
            item = table.horizontalHeaderItem(col)
            if not item:
                continue
            if col in (4, 6):
                item.setBackground(QBrush(header_edit))
            else:
                item.setBackground(QBrush(header_normal))

    # --------------------------------------------------
    # 셀 생성
    # --------------------------------------------------
    def create_cell(
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
        font.setPointSize(20 if self.w.current_level >= 1 else 24)
        font.setUnderline(underline)
        item.setFont(font)

        item.setTextAlignment(alignment)

        base_flags = item.flags()
        if editable and self.w.current_level >= 1:
            item.setFlags(base_flags | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item.setForeground(QBrush(QColor("#777777")))
        else:
            item.setFlags(base_flags & ~Qt.ItemIsEditable)

        if foreground is not None:
            item.setForeground(QBrush(foreground))

        return item

    def create_product_item(self, text: str, pk: int, col: int):
        if col in (COL_WORK_STATUS, COL_DEADLINE, COL_SHIPMENT_TIME):
            alignment = Qt.AlignCenter
        elif col in (COL_VENDOR, COL_PRODUCT):
            alignment = Qt.AlignLeft | Qt.AlignVCenter
        else:
            alignment = Qt.AlignRight | Qt.AlignVCenter

        editable = col in {COL_PLAN, COL_TODAY_RES, COL_PREV_RES}
        foreground = QColor("#0066cc") if col in (COL_FINAL_ORDER, COL_CUR_PROD) else None

        return self.create_cell(
            text=text, pk=pk, alignment=alignment,
            editable=editable, foreground=foreground,
        )

    def create_material_item(self, text: str, pk: int, col: int):
        """Raw/Sauce/Vege 공통 셀 생성"""
        alignment = Qt.AlignLeft | Qt.AlignVCenter if col == 0 else Qt.AlignRight | Qt.AlignVCenter
        editable = col in (1, 4, 6)

        foreground = None
        if col == 5:
            try:
                if int(str(text).replace(",", "")) < 0:
                    foreground = QColor("#cc0000")
            except Exception:
                pass

        return self.create_cell(
            text=text, pk=pk, alignment=alignment,
            editable=editable, foreground=foreground,
        )

    # --------------------------------------------------
    # 컬럼 리사이즈 / 가시성
    # --------------------------------------------------
    def apply_column_resize_rules(self):
        idx = self.w.ui.tabWidget.currentIndex()
        tables = {0: self.w.ui.tableWidget1, 1: self.w.ui.tableWidget2,
                  2: self.w.ui.tableWidget3, 3: self.w.ui.tableWidget4}
        table = tables.get(idx)
        if not table:
            return

        header = table.horizontalHeader()
        col_count = table.columnCount()

        table.resizeColumnsToContents()

        name_col = deadline_col = None
        for col in range(col_count):
            item = table.horizontalHeaderItem(col)
            if not item:
                continue
            text = item.text().strip()
            if text == "품명":
                name_col = col
            elif text == "소비기한":
                deadline_col = col

        for c in range(col_count):
            header.setSectionResizeMode(c, QHeaderView.Stretch)

        if name_col is not None:
            header.setSectionResizeMode(name_col, QHeaderView.Fixed)
            table.setColumnWidth(name_col, 540)

        if deadline_col is not None:
            header.setSectionResizeMode(deadline_col, QHeaderView.Fixed)
            table.setColumnWidth(deadline_col, 160)

        header.setMinimumSectionSize(10)

    def apply_column_visibility_rules(self):
        table = self.w.ui.tableWidget1

        admin_only_cols = [
            COL_VENDOR, COL_PKG, COL_PREV_RES, COL_PRODUCTION,
            COL_PLAN_KG, COL_TODAY_RES
        ]

        # 업체명은 무조건 숨김
        table.setColumnHidden(COL_VENDOR, True)

        for col in admin_only_cols:
            if col == COL_VENDOR:
                continue
            table.setColumnHidden(col, self.w.current_level < 1)
