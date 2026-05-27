from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from PyQt5.QtCore import QTimer

from UTIL.const import TIMER_INTERVAL_SEC, AUTO_REFRESH_INTERVAL_SEC

if TYPE_CHECKING:
    from core.widget import OrderDashboardWidget


class TimerManager:
    def __init__(self, widget: OrderDashboardWidget):
        self.w = widget

    def setup_timers(self):
        """타이머 생성 및 시작"""
        self.w.timer_view = QTimer(self.w)
        self.w.timer_view.timeout.connect(self.on_timer_tick)
        self.w.timer_view.start(TIMER_INTERVAL_SEC * 1000)

        self.w.timer_30min = QTimer(self.w)
        self.w.timer_30min.timeout.connect(self.auto_update_every_30min)
        self.w.timer_30min.start(AUTO_REFRESH_INTERVAL_SEC * 1000)

    def get_frequency(self) -> int:
        try:
            text = self.w.ui.tab_frequency.text().strip()
            val = int(text) if text else TIMER_INTERVAL_SEC
        except ValueError:
            val = TIMER_INTERVAL_SEC
        return max(val, 5)

    def on_timer_tick(self):
        freq_sec = self.get_frequency()
        new_interval = freq_sec * 1000
        if self.w.timer_view.interval() != new_interval:
            self.w.timer_view.setInterval(new_interval)

        if self.w.is_auto_rotation:
            # 현재 업체에 다음 페이지가 있으면 페이지만 넘김
            if self.w.product_page < self.w.product_total_pages - 1:
                self.w.product_page += 1
                self.w.loader.load_product_tab()
            else:
                # 마지막 페이지였으면 다음 업체로 이동 (페이지 리셋)
                self.w.rotation_index = (
                    (self.w.rotation_index + 1) % len(self.w.vendors_rotation)
                )
                next_vendor = self.w.vendors_rotation[self.w.rotation_index]
                self.w.ui.label_retailer.setText(next_vendor)
                self.w._change_vendor_filter(next_vendor)
        else:
            idx = self.w.ui.tabWidget.currentIndex()
            if idx == 0:
                self.w.loader.load_product_tab()

    def on_click_toggle_mode(self):
        """화면고정 <-> 자동전환 토글"""
        self.w.is_auto_rotation = not self.w.is_auto_rotation

        if self.w.is_auto_rotation:
            self.w.ui.btn_autoPage.setText("자동전환")
            try:
                self.w.rotation_index = self.w.vendors_rotation.index(
                    self.w.current_vendor
                )
            except ValueError:
                self.w.rotation_index = 0
            self.on_timer_tick()
        else:
            self.w.ui.btn_autoPage.setText("화면고정")
            self.on_timer_tick()

    def auto_update_every_30min(self):
        print(f"[_auto_update_every_30min] {datetime.now()} 자동 갱신 시작")
        self.w.writer.on_click_update_order_qty_after(silent=True)
        self.w.writer.on_click_update_product(silent=True)
        self.w.logout_if_logged_in()

    def renew_values_manually(self):
        print(f"[_renew_values_manually] {datetime.now()} 수동 갱신 시작")
        self.w.writer.on_click_update_order_qty_after(silent=True)
        self.w.writer.on_click_update_product(silent=True)
