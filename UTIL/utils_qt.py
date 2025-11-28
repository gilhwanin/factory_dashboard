from PyQt5.QtWidgets import QApplication

def apply_table_style(table):
    table.setAlternatingRowColors(True)
    table.setStyleSheet("""
        QTableWidget {
            background-color: #ffffff;
            alternate-background-color: #f7f7f7;
            color: #333333;
            gridline-color: #dcdcdc;
            selection-background-color: #cce7ff;
            selection-color: #000000;
            border: 1px solid #cccccc;
        }
        QTableWidget::item {
            padding: 2px;
            border: none;
        }
        QTableWidget::item:selected {
            background-color: #cce7ff;
            color: #000000;
        }
        QHeaderView::section {
            background-color: #f0f0f0;
            color: #333333;
            padding: 2px;
            font-weight: bold;
            border: 1px solid #d0d0d0;
        }
        QTableCornerButton::section {
            background-color: #f0f0f0;
            border: 1px solid #d0d0d0;
        }
    """)
    table.resizeColumnsToContents()
    table.viewport().update()
    QApplication.processEvents()
