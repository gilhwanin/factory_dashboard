# secure_env.py
# 요구: pip install cryptography
from cryptography.fernet import Fernet
import os, base64

###############################################
# 1️⃣ Fernet 키 생성
###############################################
def generate_key() -> bytes:
    """
    Fernet 키를 새로 생성하고 bytes로 반환합니다.
    복사해서 안전한 곳(환경변수 등)에 저장하세요.
    """
    key = Fernet.generate_key()
    print("🔑 생성된 키 (base64):", key.decode())
    return key


###############################################
# 2️⃣ .env 파일 암호화 → .env.enc 생성
###############################################
def encrypt_env_file(key: bytes,
                     in_env_path: str = ".env",
                     out_enc_path: str = "gwkey.env.enc") -> None:
    """
    in_env_path 파일을 주어진 key로 암호화하여 out_enc_path로 저장합니다.
    key: bytes 형태 (ex. b"xxxx==")
    """
    f = Fernet(key)
    with open(in_env_path, "rb") as fin:
        token = f.encrypt(fin.read())
    with open(out_enc_path, "wb") as fout:
        fout.write(token)
    print(f"✅ 암호화 완료 → {out_enc_path}")


###############################################
# 3️⃣ 하드코딩 키로 복호화
###############################################
def load_env_hardcoded(key: bytes,
                       enc_path: str = "gwkey.env.enc") -> dict:
    """
    enc_path 파일을 하드코딩된 key로 복호화하여 dict 반환
    """
    f = Fernet(key)
    with open(enc_path, "rb") as fin:
        data = f.decrypt(fin.read()).decode("utf-8")

    env = {}
    for line in data.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


###############################################
# 4️⃣ 환경변수 키로 복호화
###############################################
def load_env_from_envvar(enc_path: str = "gwkey.env.enc",
                         env_var_name: str = "GW_FERNET_KEY") -> dict:
    """
    OS 환경변수(env_var_name)에서 키를 읽어 복호화 후 dict 반환
    """
    key_str = os.getenv(env_var_name)
    if not key_str:
        raise RuntimeError(f"❌ 환경변수 {env_var_name}가 설정되어 있지 않습니다.")
    key = key_str.encode()

    f = Fernet(key)
    with open(enc_path, "rb") as fin:
        data = f.decrypt(fin.read()).decode("utf-8")

    env = {}
    for line in data.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return env


###############################################
# ✅ 사용 예시 (테스트용)
###############################################
if __name__ == "__main__":
    pass
    # 1. 키 생성
    # generate_key()

    # 2. 암호화 (한 번만)
    key_bytes = b"1Vg4VCYbCOBXM9Z9QFNTIu8CorMPc3JTELUSZvaLOHI="
    # encrypt_env_file(key_bytes, in_env_path="inenv.env", out_enc_path="gwkey.env.enc")

    # 3. BASE64 인코딩 (env 내용 하드코딩하기 위함)
    s = base64.b64encode(open("gwkey.env.enc", "rb").read()).decode()
    print(s)  # 이 출력을 ENCRYPTED_ENV_B64에 넣으세요.

# .env 양식 아래에 넣고 암호화 돌리면 됩니다. (2번)  하고 나온거를 3번으로 인코딩하고 넣으면 됨.
# # HJFOOD Database Configuration
# HJFOOD_SERVER=
# HJFOOD_USER=
# HJFOOD_PASSWORD=
# HJFOOD_DATABASE=HJFOOD
#
# # MEATSTORE Database Configuration
# MEATSTORE_SERVER=
# MEATSTORE_USER=
# MEATSTORE_PASSWORD=
# MEATSTORE_DATABASE=MEATSTORE
#
# # GYUN_N Database Configuration
# GYUN_N_SERVER=
# GYUN_N_USER=
# GYUN_N_PASSWORD=
# GYUN_N_DATABASE=GYUN_N
#
# # GWCHUL Database Configuration
# GWCHUL_SERVER=
# GWCHUL_USER=
# GWCHUL_PASSWORD=
# GWCHUL_DATABASE=GWCHUL
#
# # WR_HWP Database Configuration
# WR_HWP_SERVER=
# WR_HWP_USER=
# WR_HWP_PASSWORD=
# WR_HWP_DATABASE=WR_HWP
#
# # WR_HWP Database Configuration
# UTONG_SERVER=
# UTONG_USER=
# UTONG_PASSWORD=
# UTONG_DATABASE=UTONG
#
# # GFOOD_B Database Configuration
# GFOOD_B_SERVER=
# GFOOD_B_USER=
# GFOOD_B_PASSWORD=
# GFOOD_B_DATABASE=GFOOD_B
#
# # GWFOOD Database Configuration
# GWFOOD_SERVER=
# GWFOOD_USER=
# GWFOOD_PASSWORD=
# GWFOOD_DATABASE=GWFOOD
#
# # GFOOD_SF Database Configuration
# GFOOD_SF_SERVER=
# GFOOD_SF_USER=
# GFOOD_SF_PASSWORD=
# GFOOD_SF_DATABASE=GFOOD_SF
#
# # HDHOME Database Configuration
# HDHOME_SERVER=
# HDHOME_USER=
# HDHOME_PASSWORD=
# HDHOME_DATABASE=HDHOME
#
# # GWHWP Database Configuration
# GWHWP_SERVER=
# GWHWP_USER=
# GWHWP_PASSWORD=
# GWHWP_DATABASE=GWHWP
