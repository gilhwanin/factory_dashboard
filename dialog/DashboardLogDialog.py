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
from PyQt5.QtGui import QFont

from UTIL.utils_qt import apply_table_style
from UTIL.db_handler import getdb, closedb, runquery

class DashboardLogDialog(QDialog):
    """
    GP..DASHBOARD_LOG를 날짜별로 조회하는 팝업 (UTIL.db_handler 기반)
    로그 기록(INSERT) 기능도 포함.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("발주 로그 조회")
        self.resize(1000, 600)

        # ---------------------------------------------------------
        # 🔥 상단 제어패널 크기 설정
        # ---------------------------------------------------------
        big_h = 34  # 높이 크게
        big_font = QFont()
        big_font.setPointSize(11)  # 폰트 크게

        # ---------------------------------------------------------
        # 전체 레이아웃
        # ---------------------------------------------------------
        layout = QVBoxLayout(self)

        # -------------------------------
        # 상단 날짜 + 조회 버튼
        # -------------------------------
        top_layout = QHBoxLayout()

        label = QLabel("날짜:")
        label.setFont(big_font)
        label.setFixedHeight(big_h)
        top_layout.addWidget(label)

        self.dateEdit = QDateEdit()
        self.dateEdit.setCalendarPopup(True)
        self.dateEdit.setDate(QDate.currentDate())
        self.dateEdit.setFont(big_font)
        self.dateEdit.setFixedHeight(big_h)
        self.dateEdit.setFixedWidth(120)
        top_layout.addWidget(self.dateEdit)

        self.btn_search = QPushButton("조회")
        self.btn_search.setFont(big_font)
        self.btn_search.setFixedHeight(big_h)
        top_layout.addWidget(self.btn_search)

        top_layout.addStretch()
        layout.addLayout(top_layout)

        # -------------------------------
        # 중앙 테이블
        # -------------------------------
        self.table = QTableWidget(self)
        headers = ["변경시각", "품명", "내용", "ID"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        # 테이블 스타일 적용
        apply_table_style(self.table)

        layout.addWidget(self.table)

        # -------------------------------
        # 하단 닫기 버튼
        # -------------------------------
        btn_close = QPushButton("닫기")
        btn_close.setFont(big_font)
        btn_close.setFixedHeight(big_h)
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close, alignment=Qt.AlignRight)

        # -------------------------------
        # 이벤트 연결
        # -------------------------------
        self.btn_search.clicked.connect(self.load_logs)
        self.dateEdit.dateChanged.connect(lambda _: self.load_logs())

        # -------------------------------
        # 초기 데이터 로드
        # -------------------------------
        self.load_logs()

    # ------------------------------------------------------
    # 로그 조회 함수
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
                    modified_time, 
                    user_id, 
                    sdate, 
                    uname, 
                    content, 
                    bigo
                FROM DASHBOARD_LOGS
                WHERE CONVERT(DATE, sdate) = %s
                ORDER BY modified_time DESC, PK DESC
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
            modified_time = row.MODIFIED_TIME
            user_id = str(row.USER_ID)
            sdate = row.SDATE
            uname = str(row.UNAME) if row.UNAME else ""
            content = str(row.CONTENT) if row.CONTENT else ""

            # 날짜/시간 포맷
            mod_time_str = self._to_datetime_str(modified_time)
            
            if hasattr(sdate, "strftime"):
                sdate_str2 = sdate.strftime("%Y-%m-%d")
            else:
                sdate_str2 = str(sdate)

            row_data = [
                mod_time_str,  # 변경시각
                uname,  # 품명
                content,  # 내용
                user_id,  # User ID (맨 마지막)
            ]

            for col, val in enumerate(row_data):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row_idx, col, item)
    
    # ------------------------------------------------------
    # 로그 기록(INSERT) 정적 메서드
    # ------------------------------------------------------
    @staticmethod
    def log_change(user_id, sdate, uname, content, bigo=""):
        """
        DASHBOARD_LOG 테이블에 로그를 남깁니다.
        modified_time은 파이썬 현재시간 사용.
        """
        now = datetime.datetime.now()
        
        conn, cur = getdb("GP")
        try:
            sql = """
                INSERT INTO DASHBOARD_LOGS (
                    modified_time, user_id, sdate, uname, content, bigo
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """
            # sdate가 QDate나 문자열일 수 있으므로 포맷 통일
            if hasattr(sdate, "toString"): # QDate
                 sdate_val = sdate.toString("yyyy-MM-dd")
            elif isinstance(sdate, datetime.date):
                 sdate_val = sdate.strftime("%Y-%m-%d")
            else:
                 sdate_val = str(sdate)

            runquery(cur, sql, [now, user_id, sdate_val, uname, content, bigo])
        except Exception as e:
            print(f"[LOG ERROR] {e}")
        finally:
            closedb(conn)

    @staticmethod
    def log_action(user_id, sdate, content):
        """
        테이블 생성, 전체 삭제 등 uname이나 구체적 수치가 없는 시스템성 액션 로그.
        """
        DashboardLogDialog.log_change(user_id, sdate, "", content, "")