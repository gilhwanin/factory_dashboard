import ftplib
import zipfile
import os
import subprocess
import time
import sys
import traceback

# 현재 실행 중인 파일 경로 확인
current_path = os.path.abspath(sys.argv[0])  # 실행 파일 경로
parent_directory = os.path.dirname(current_path)  # 부모 폴더 경로
parent_folder_name = os.path.basename(parent_directory)  # 폴더 이름 (GWONE)

# 종료할 프로세스 이름 (GWONE.exe)
file_name = f"{parent_folder_name}.exe"

# FTP 서버 정보
ftp_server = "gwml.iptime.org"
ftp_user = "hjftp"
ftp_password = "ftp1379"

# 다운로드할 파일 정보
ftp_remote_folder = f"/exe/PY/{parent_folder_name}/"  # FTP 상의 폴더
local_folder = f"C:\\P\\{parent_folder_name}"  # 다운로드할 로컬 폴더
local_download_path = os.path.join(local_folder, f"{parent_folder_name}.zip")  # 저장할 파일 경로
ftp_target_file = f"{parent_folder_name}.zip"  # 다운로드할 ZIP 파일 이름
extract_to_folder = f"C:\P\{parent_folder_name}"  # 압축 해제할 폴더
#  1. 실행 중인 프로세스 확인 후 종료
try:
    running_processes = subprocess.check_output(['tasklist']).decode('utf-8', errors='ignore')

    if file_name in running_processes:
        print("대규모 업데이트 → PYUP.exe 실행")

        print(f"{file_name} 실행 중 → 강제 종료")
        os.system(f'taskkill /f /im {file_name}')
        time.sleep(3)  # 프로세스 종료 대기
    else:
        print(f"{file_name} 종료 확인")
except Exception as e:
    print(traceback.format_exc())
    print(f"프로세스 확인 중 오류 발생: {e}")
    time.sleep(5)

#  2. 다운로드 폴더 확인 및 생성
if not os.path.exists(local_folder):
    try:
        os.makedirs(local_folder, exist_ok=True)
        print(f"폴더 생성 완료: {local_folder}")
    except Exception as e:
        print(f"폴더 생성 중 오류 발생: {e}")
        time.sleep(5)
        sys.exit(1)

#  3. FTP에서 `GWONE.zip` 다운로드
try:
    with ftplib.FTP(ftp_server) as ftp:
        ftp.login(ftp_user, ftp_password)
        print("FTP 로그인 성공")

        # 다운로드할 폴더로 이동
        ftp.cwd(ftp_remote_folder)

        # ZIP 파일 다운로드
        with open(local_download_path, "wb") as local_file:
            ftp.retrbinary(f"RETR {ftp_target_file}", local_file.write)

        print(f"파일 다운로드 완료: {local_download_path}")

except Exception as e:
    print(f"FTP 다운로드 중 오류 발생: {e}")
    time.sleep(5)
    sys.exit(1)

#  3. ZIP 파일 압축 해제
try:
    with zipfile.ZipFile(local_download_path, "r") as zip_ref:
        zip_ref.extractall(extract_to_folder)

    print(f"압축 해제 완료: {extract_to_folder}")

    # 압축 파일 삭제 (선택 사항)
    os.remove(local_download_path)
    print(f"다운로드된 ZIP 파일 삭제 완료: {local_download_path}")

except Exception as e:
    print(f"압축 해제 중 오류 발생: {e}")
    time.sleep(5)
    sys.exit(1)


try:
    exe_path = os.path.join(local_folder, f"{parent_folder_name}.exe")
    if os.path.exists(exe_path):
        subprocess.Popen(exe_path)
    else:
        print("PYUP.exe not found in path:", local_folder)
except Exception as e:
    print(f"파일 실행 중 오류 발생: {e}")
    time.sleep(5)
    sys.exit(1)



