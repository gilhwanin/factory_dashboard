from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.widget import OrderDashboardWidget


class PaginationManager:
    def __init__(self, widget: OrderDashboardWidget):
        self.w = widget

    def setup_pagination_bar(self):
        """dashboard.ui의 pagination 프레임 초기화 및 시그널 연결"""
        self.w.ui.pagination.hide()
        self.w.ui.btn_left.clicked.connect(self.on_page_prev)
        self.w.ui.btn_right.clicked.connect(self.on_page_next)

    def update_pagination_ui(self):
        """페이지 수에 따라 pagination 프레임 표시/숨김 및 버튼 상태 업데이트"""
        if self.w.product_total_pages <= 1:
            self.w.ui.pagination.hide()
            return
        self.w.ui.pagination.show()
        if self.w._lotte_page_labels:
            cat = self.w._lotte_page_labels[self.w.product_page]
            self.w.ui.page_label.setText(
                f"{self.w.product_page + 1} / {self.w.product_total_pages} ({cat})"
            )
        else:
            self.w.ui.page_label.setText(
                f"{self.w.product_page + 1} / {self.w.product_total_pages}"
            )
        self.w.ui.btn_left.setEnabled(self.w.product_page > 0)
        self.w.ui.btn_right.setEnabled(
            self.w.product_page < self.w.product_total_pages - 1
        )

    def on_page_prev(self):
        if self.w.product_page > 0:
            self.w.product_page -= 1
            self.w.loader.load_product_tab()

    def on_page_next(self):
        if self.w.product_page < self.w.product_total_pages - 1:
            self.w.product_page += 1
            self.w.loader.load_product_tab()
