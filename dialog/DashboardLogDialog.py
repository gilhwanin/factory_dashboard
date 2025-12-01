import pandas as pd
import datetime
from PyQt5.QtWidgets import (
    QTableWidgetItem,
    QMessageBox,
    QDateEdit,
    QTableWidget,
    QHeaderView,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel
)
from PyQt5.QtCore import Qt, QDate

from UTIL.utils_qt import apply_table_style
from UTIL.db_handler import getdb, closedb, runquery

class DashboardLogDialog(QDialog):
    """
    GP..DASHBOARD_LOG를 날짜별로 조회하는 팝업 (UTIL.db_handler 기반)
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("발주 로그 조회")
        self.resize(900, 500)

        # -------------------------------
        # 레이아웃 구성
        # -------------------------------
        layout = QVBoxLayout(self)

        # 상단 날짜 + 버튼
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("날짜:"))

        self.dateEdit = QDateEdit()
        self.dateEdit.setCalendarPopup(True)
        self.dateEdit.setDate(QDate.currentDate())
        top_layout.addWidget(self.dateEdit)
        self.btn_search = QPushButton("조회")
        top_layout.addWidget(self.btn_search)

        top_layout.addStretch()
        layout.addLayout(top_layout)

        # 중앙 테이블
        self.table = QTableWidget(self)
        headers = ["PK", "변경시각", "ID", "날짜", "CO", "업체", "변경전 → 변경후"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # 🔹 테이블 스타일 적용
        apply_table_style(self.table)

        layout.addWidget(self.table)

        # 하단 닫기 버튼
        btn_close = QPushButton("닫기")
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)

        # 이벤트 연결
        self.btn_search.clicked.connect(self.load_logs)
        self.dateEdit.dateChanged.connect(lambda _: self.load_logs())

        # 초기 데이터 로드
        self.load_logs()

    # ------------------------------------------------------
    # 로그 조회 함수 (UTIL.db_handler 기반)
    # ------------------------------------------------------
    @staticmethod
    def _to_datetime_str(val):
        if isinstance(val, (datetime.datetime, pd.Timestamp)):
            return val.strftime("%Y-%m-%d %H:%M:%S")
        return str(val)

    def load_logs(self):
        sdate_str = self.dateEdit.date().toString("yyyy-MM-dd")

        conn, cur = getdb("GP")
        try:
            sql = """
                SELECT 
                    PK, 
                    update_time, 
                    id, 
                    sdate, 
                    co, 
                    vendor, 
                    qty_before, 
                    qty_after
                FROM DASHBOARD_LOG
                WHERE CONVERT(DATE, sdate) = %s
                ORDER BY update_time DESC, PK DESC
            """
            df = runquery(cur, sql, [sdate_str])
        except Exception as e:
            QMessageBox.critical(self, "DB 오류", str(e))
            return
        finally:
            closedb(conn)

        self.table.setRowCount(0)

        # 결과 없을 때
        if df is None or len(df) == 0:
            QMessageBox.information(self, "안내", f"{sdate_str} 로그 데이터가 없습니다.")
            return

        df = pd.DataFrame(df)
        df.columns = [str(c).upper() for c in df.columns]
        self.table.setRowCount(len(df))

        # 테이블에 데이터 채우기
        for row_idx, row in enumerate(df.itertuples(index=False)):
            pk = str(row.PK)
            update_time = row.UPDATE_TIME
            log_id = str(row.ID)
            sdate = row.SDATE
            co = str(row.CO)
            vendor = str(row.VENDOR)
            before = int(row.QTY_BEFORE or 0)
            after = int(row.QTY_AFTER or 0)
            diff = after - before

            # 날짜/시간 포맷
            update_time_str = self._to_datetime_str(update_time)
            sdate_str2 = self._to_datetime_str(sdate)

            if hasattr(sdate, "strftime"):
                sdate_str2 = sdate.strftime("%Y-%m-%d")
            else:
                sdate_str2 = str(sdate)

            # 변경내용 문자열 구성
            change_text = f"{before} → {after}"
            if diff != 0:
                change_text += f" (Δ {diff})"

            row_data = [
                pk,
                update_time_str,
                log_id,
                sdate_str2,
                co,
                vendor,
                change_text,
            ]

            for col, val in enumerate(row_data):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row_idx, col, item)