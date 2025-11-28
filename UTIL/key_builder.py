# secure_env.py
# 요구: pip install cryptography
from cryptography.fernet import Fernet
import os

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
                     in_env_path: str = "inenv.env",
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
    # 키 생성
    # generate_key()

    # 암호화 (한 번만)
    # key_bytes = b"Yu-4JtPitClfWOrHGCBhLXs5Y3lTUjnIjl-cp94dCic=="
    # encrypt_env_file(key_bytes, in_env_path="inenv.env", out_enc_path="gwkey.env.enc")

    # 복호화 (하드코딩)
    # env = load_env_hardcoded(key_bytes)
    # print(env)

    # 복호화 (환경변수 방식)
    # env = load_env_from_envvar("gwkey.env.enc", "GW_FERNET_KEY")
    # print(env)
