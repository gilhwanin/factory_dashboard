import ftplib
import os
import shutil
import subprocess
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from UTIL.db_handler import *


def upload_file(ftp, local_file_path, remote_file_path):
    """
    FTP 서버에 파일을 업로드합니다.
    :param ftp: FTP 연결 객체
    :param local_file_path: 로컬 파일 경로
    :param remote_file_path: FTP 서버의 업로드 경로
    """
    try:
        with open(local_file_path, "rb") as file:
            ftp.storbinary(f"STOR {remote_file_path}", file)
        # print(f"파일 업로드 완료: {remote_file_path}")
    except Exception as e:
        print(f"파일 업로드 실패: {remote_file_path} - {e}")


def delete_ftp_folder(ftp, folder):
    """
    FTP 서버의 폴더를 재귀적으로 삭제합니다.
    :param ftp: FTP 연결 객체
    :param folder: 삭제할 FTP 폴더 경로
    """
    try:
        ftp.cwd(folder)
    except ftplib.error_perm:
        # 폴더가 없으면 바로 반환
        return

    try:
        items = ftp.nlst()
    except ftplib.error_perm as e:
        print(f"nlst 명령어 실패: {folder} - {e}")
        items = []

    for item in items:
        # 파일 혹은 폴더인지 확인
        try:
            ftp.cwd(item)  # 폴더라면 cwd 성공
            ftp.cwd("..")  # 원래 폴더로 돌아감
            delete_ftp_folder(ftp, f"{folder}/{item}")
        except ftplib.error_perm:
            try:
                ftp.delete(f"{folder}/{item}")
                # print(f"파일 삭제 완료: {folder}/{item}")
            except Exception as e:
                pass
                # print(f"파일 삭제 실패: {folder}/{item} - {e}")
    try:
        ftp.rmd(folder)
        # print(f"폴더 삭제 완료: {folder}")
    except Exception as e:
        pass
        # print(f"폴더 삭제 실패: {folder} - {e}")


def ensure_ftp_folder(ftp, folder):
    """
    FTP 서버에 폴더가 존재하지 않으면 생성합니다.
    :param ftp: FTP 연결 객체
    :param folder: 생성할 FTP 폴더 경로
    """
    try:
        ftp.cwd(folder)
    except ftplib.error_perm:
        parent, new_folder = os.path.split(folder.rstrip("/"))
        if parent and parent != folder:
            ensure_ftp_folder(ftp, parent)
        try:
            ftp.mkd(new_folder)
            print(f"FTP 폴더 생성 완료: {folder}")
        except Exception as e:
            print(f"FTP 폴더 생성 실패: {folder} - {e}")


def exeup(PNAME: str, VERSION: str):
    """
    PyInstaller를 사용하여 실행 파일을 빌드하고, 압축 후 FTP 서버에 업로드합니다.
    :param PNAME: 프로그램 이름
    :param VERSION: 프로그램 버전
    """
    try:
        print("PyInstaller 빌드 시작...")
        spec_file = rf"C:\Users\250327\PycharmProjects\{PNAME}\main.spec"
        working_dir = os.path.dirname(spec_file)
        dist_folder = os.path.join(working_dir, "dist")
        target_folder = os.path.join(dist_folder, 'main')

        print(working_dir)
        print(dist_folder)
        print(target_folder)

        # 기존 빌드 폴더 삭제
        if os.path.exists(dist_folder):
            shutil.rmtree(dist_folder, ignore_errors=True)
            print(f"폴더 삭제 완료: {dist_folder}")

        # PyInstaller 실행
        process = subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--clean", "-y", spec_file],
            cwd=working_dir,
            env={**os.environ, "PYI_SKIP_ISOLATION": "1"},  # ✅ 핵심 한 줄
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        if process.returncode != 0:
            print("실행 파일 생성 중 오류 발생!")
            print("PyInstaller 오류 로그:")
            print(process.stderr)
            return False

        print("PyInstaller 빌드 완료!")

        # 리소스 폴더 복사
        source_folder = rf"C:\Users\250327\PycharmProjects\{PNAME}\resource"
        destination_folder = os.path.join(target_folder, "resource")
        if os.path.exists(source_folder):
            shutil.copytree(source_folder, destination_folder, dirs_exist_ok=True)
            print(f"{source_folder} 폴더가 {destination_folder}로 복사되었습니다.")
        else:
            print(f"리소스 폴더가 존재하지 않습니다: {source_folder}")

        # GWONE 폴더 압축
        zip_base = os.path.join(dist_folder, PNAME)
        zip_path = zip_base + ".zip"
        shutil.make_archive(zip_base, 'zip', target_folder)
        print(f"{PNAME} 폴더 압축 완료: {zip_path}")

        # FTP 연결 및 파일 업로드
        ftp_server = "gwml.iptime.org"
        ftp_user = "hjftp"
        ftp_password = "ftp1379"
        ftp_path = f"/exe/PY/{PNAME}"

        with ftplib.FTP(ftp_server) as ftp:
            ftp.login(ftp_user, ftp_password)
            print("FTP 로그인 성공")

            # 기존 FTP 폴더 삭제 후 새로 생성
            delete_ftp_folder(ftp, ftp_path)
            ensure_ftp_folder(ftp, ftp_path)

            # 개별 파일 업로드
            for root, _, files in os.walk(target_folder):
                rel_path = os.path.relpath(root, start=target_folder)
                ftp_rel_path = f"{ftp_path}/{rel_path}".replace("\\", "/")
                try:
                    ftp.cwd(ftp_rel_path)
                except ftplib.error_perm:
                    try:
                        ftp.mkd(ftp_rel_path)
                        # print(f"FTP 폴더 생성 완료: {ftp_rel_path}")
                        ftp.cwd(ftp_rel_path)
                    except Exception as e:
                        print(f"FTP 폴더 생성 실패: {ftp_rel_path} - {e}")
                        continue

                for file in files:
                    local_file = os.path.join(root, file)
                    remote_file = f"{ftp_rel_path}/{file}"
                    upload_file(ftp, local_file, remote_file)

            # 압축 파일 업로드
            upload_file(ftp, zip_path, f"{ftp_path}/{PNAME}.zip")

        print("\n파일 업로드가 완료되었습니다.")

        # 데이터베이스 업데이트
        conn, cursor = getdb("GYUN_N")
        runquery(cursor, f"UPDATE CVERPY SET {PNAME} = %s", (VERSION,))
        closedb(conn)
        print(f"{VERSION}으로 업데이트가 완료되었습니다.")

    except Exception:
        print("전체 프로세스 중 예외 발생:")
        print(traceback.format_exc())

exeup("factory_dashboard", "a-0018")