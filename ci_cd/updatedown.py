import ftplib
import os, sys
import subprocess
import traceback

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox

from UTIL.db_handler import getdb, closedb


def updatedown(filename: str, is_same_prefix: bool):
    """
    업데이트 확인 후 다운로드 (PyQt5 버전)
    :param filename: 파일명(폴더명)
    :param is_same_prefix: 맨 앞 문자가 같은지 여부 (True/False)
    """
    try:
        updatepath = rf"C:\P\{filename}"

        # 메시지 박스 생성
        msg = QMessageBox()
        msg.setWindowTitle("버전 업데이트")
        msg.setText("업데이트를 시작합니다.\n확인 클릭 후 잠시 기다려주세요")
        font = msg.font()
        font.setPointSize(11)
        msg.setFont(font)

        # 타이머 설정 (자동 닫힘)
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(msg.accept)
        timer.start(3000)

        msg.exec_()   # PyQt5는 exec_()

        # FTP 다운로드 함수
        def download(ftp, path, dest):
            try:
                ftp.cwd(path)
                if not os.path.exists(dest):
                    os.mkdir(dest)
                items = ftp.nlst()
                for item in items:
                    download(ftp, f"{path}/{item}", os.path.join(dest, item))
                ftp.cwd("..")
            except ftplib.error_perm:
                with open(dest, "wb") as f:
                    ftp.retrbinary(f"RETR {path}", f.write)

        if not os.path.exists(updatepath):
            os.mkdir(updatepath)

        # FTP 포인트
        ftp_server = "gwml.iptime.org"
        ftp_user = "hjftp"
        ftp_password = "ftp1379"

        # FTP 접속 및 다운로드
        with ftplib.FTP() as ftp:
            ftp.connect(host=ftp_server, port=21)
            ftp.encoding = "utf-8"
            ftp.login(user=ftp_user, passwd=ftp_password)
            download(ftp, "/exe/PY/PYUP", updatepath)

        # 실행 중인 프로세스 종료
        running_processes = subprocess.check_output(["tasklist"]).decode("utf-8", errors="ignore")
        for proc in ["PYUP.exe", "PYUPS.exe"]:
            if proc in running_processes:
                os.system(f"start /B taskkill /f /im {proc}")

        # 실행할 파일 선택
        exe_name = "PYUP.exe" if is_same_prefix else "PYUPS.exe"
        exe_path = os.path.join(updatepath, exe_name)

        print(f"[DEBUG] 실행 대상 경로: {exe_path}")

        if os.path.exists(exe_path):
            print(f"[DEBUG] 실행 시작: {exe_path}")
            subprocess.Popen(exe_path)
        else:
            print(f"[ERROR] 실행 파일이 존재하지 않음: {exe_name}")
            print(f"[ERROR] 찾으려던 경로: {updatepath}")

        sys.exit()

    except Exception:
        print(traceback.format_exc())


def check_version_and_update(PROGRAM_NAME, CURRENT_VERSION):
    """
    CVERPY 테이블 버전과 비교하여 업데이트 필요 시 수행 (PyQt5)
    """
    try:
        conn, cursor = getdb("GYUN_N")
        cursor.execute(f"SELECT {PROGRAM_NAME} FROM CVERPY")
        db_version = cursor.fetchone()[0]
        closedb(conn)

        print(f"[DEBUG] 현재 버전: {CURRENT_VERSION}, DB 버전: {db_version}")

        if CURRENT_VERSION != db_version:
            # prefix 비교 (예: A_0001 → A)
            is_same = CURRENT_VERSION.split("-")[0] == db_version.split("-")[0]
            updatedown(PROGRAM_NAME, is_same)

        else:
            print("[DEBUG] 버전 일치 → 업데이트 없음")

    except Exception as e:
        print(f"[ERROR] 버전 확인 실패: {e}")
