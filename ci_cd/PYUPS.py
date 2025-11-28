import ftplib
import os
import subprocess
import time
import sys
import traceback

# 현재 실행 중인 파일 경로 확인
current_path = os.path.abspath(sys.argv[0])  # 실행 파일 경로
parent_directory = os.path.dirname(current_path)  # 부모 폴더 경로
parent_folder_name = os.path.basename(parent_directory)  # 폴더 이름 (예: GWONE)

# 종료할 프로세스 이름 (예: GWONE.exe)
file_name = f"{parent_folder_name}.exe"

# FTP 서버 정보
ftp_server = "gwml.iptime.org"
ftp_user = "hjftp"
ftp_password = "ftp1379"

# 다운로드할 폴더 경로
ftp_remote_folder = f"/exe/PY/{parent_folder_name}/"
local_folder = f"C:\\P\\{parent_folder_name}"
local_resource_folder = os.path.join(local_folder, "resource")

# ✅ 파일 다운로드 진행률 표시 함수
def download_with_progress(ftp, remote_filename, local_filename, total_size, progress):
    try:
        ftp.voidcmd("TYPE I")
        file_size = ftp.size(remote_filename)
        downloaded_size = 0

        with open(local_filename, "wb") as local_file:
            def callback(data):
                nonlocal downloaded_size
                local_file.write(data)
                downloaded_size += len(data)
                progress[0] += len(data)

                # 진행률이 100% 이상이 되지 않도록 조정
                percent = min((progress[0] / total_size) * 100, 100)
                print(f"\r📂 `resource` 폴더 다운로드 진행 중: [{percent:.2f}% 완료]", end="", flush=True)

            ftp.retrbinary(f"RETR {remote_filename}", callback)

    except Exception as e:
        print(f"\n❌ 다운로드 중 오류 발생: {e}")


# ✅ `resource` 폴더의 전체 크기 계산
def calculate_folder_size(ftp, remote_folder):
    total_size = 0
    try:
        ftp.cwd(remote_folder)
        items = ftp.nlst()
    except ftplib.error_perm:
        return 0

    for item in items:
        if item in [".", ".."]:
            continue

        remote_item_path = f"{remote_folder}/{item}"

        try:
            ftp.cwd(remote_item_path)
            ftp.cwd("..")
            total_size += calculate_folder_size(ftp, remote_item_path)
        except ftplib.error_perm:
            try:
                ftp.voidcmd("TYPE I")
                total_size += ftp.size(remote_item_path)
            except Exception:
                continue

    return total_size


# ✅ `resource` 폴더 다운로드 (재귀)
def download_ftp_folder(ftp, remote_folder, local_folder, total_size, progress, is_first_call=False):
    try:
        ftp.cwd(remote_folder)
        items = ftp.nlst()
    except ftplib.error_perm:
        print(f"\n⚠️ 접근 실패 또는 폴더 없음: {remote_folder}")
        return

    # if is_first_call:
    #     print(f"📂 `resource` 폴더 다운로드 진행 중...", end="", flush=True)  # 최초 호출 시 한 번만 출력

    for item in items:
        if item in [".", ".."]:
            continue

        local_item_path = os.path.join(local_folder, item)
        remote_item_path = f"{remote_folder}/{item}"

        try:
            ftp.cwd(remote_item_path)
            ftp.cwd("..")
            if not os.path.exists(local_item_path):
                os.makedirs(local_item_path, exist_ok=True)
            download_ftp_folder(ftp, remote_item_path, local_item_path, total_size, progress,
                                False)  # is_first_call=False
        except ftplib.error_perm:
            download_with_progress(ftp, remote_item_path, local_item_path, total_size, progress)


# 1️⃣ 실행 중인 프로세스 종료
try:
    running_processes = subprocess.check_output(['tasklist']).decode('utf-8', errors='ignore')
    if file_name in running_processes:
        print("소규모 업데이트 → PYUPS.exe 실행")

        print(f"{file_name} 실행 중 → 강제 종료")
        os.system(f'taskkill /f /im {file_name}')
        time.sleep(3)
    else:
        print(f"{file_name} 종료 확인")
except Exception as e:
    print(traceback.format_exc())
    print(f"프로세스 확인 중 오류 발생: {e}")
    time.sleep(5)

# 2️⃣ 다운로드 폴더 확인 및 생성
for folder in [local_folder, local_resource_folder]:
    if not os.path.exists(folder):
        try:
            os.makedirs(folder, exist_ok=True)
            print(f"폴더 생성 완료: {folder}")
        except Exception as e:
            print(f"폴더 생성 중 오류 발생: {e}")
            time.sleep(5)
            sys.exit(1)

# 3️⃣ FTP에서 `resource` 폴더 및 `{parent_folder_name}.exe`만 다운로드
try:
    with ftplib.FTP(ftp_server) as ftp:
        ftp.set_pasv(True)
        ftp.login(ftp_user, ftp_password)
        print("✅ FTP 로그인 성공")

        # 다운로드할 폴더로 이동
        ftp.cwd(ftp_remote_folder)

        # 폴더 내 파일 및 디렉토리 목록 가져오기
        files = ftp.nlst()

        if not files:
            print("📢 다운로드할 파일이 없습니다.")
            sys.exit(0)

        # ✅ 실행 파일 다운로드 (`GWONE.exe`)
        exe_file = f"{parent_folder_name}.exe"
        if exe_file in files:
            local_exe_path = os.path.join(local_folder, exe_file)
            print(f"📥 실행 파일 다운로드 시작: {exe_file}")
            download_with_progress(ftp, exe_file, local_exe_path, ftp.size(exe_file), [0])

        # ✅ `resource` 폴더 다운로드 (진행률 메시지 한 번만 출력)
        if "resource" in files:
            total_size = calculate_folder_size(ftp, f"{ftp_remote_folder}/resource")
            if total_size > 0:
                progress = [0]
                download_ftp_folder(ftp, f"{ftp_remote_folder}/resource", local_resource_folder, total_size, progress,
                                    is_first_call=True)

                # 다운로드 진행률을 100%로 맞추고 최종 완료 메시지 출력
                print(f"\r📂 `resource` 폴더 다운로드 진행 중: [100.00% 완료]", end="", flush=True)
                print(f"\n📂 `resource` 폴더 다운로드 완료: {local_resource_folder}")  # 다운로드 완료 메시지
            else:
                print("⚠️ `resource` 폴더가 비어 있습니다.")
        else:
            print("⚠️ `resource` 폴더가 존재하지 않습니다.")

except Exception as e:
    print(f"\n❌ FTP 다운로드 중 오류 발생: {e}")
    time.sleep(5)
    sys.exit(1)

# 4️⃣ 프로그램 실행
try:
    exe_path = os.path.join(local_folder, f"{parent_folder_name}.exe")
    if os.path.exists(exe_path):
        subprocess.Popen(exe_path)
    else:
        print(f"❌ 실행 파일을 찾을 수 없습니다: {exe_path}")
except Exception as e:
    print(f"\n❌ 파일 실행 중 오류 발생: {e}")
    time.sleep(5)
    sys.exit(1)
