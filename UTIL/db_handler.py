# db_handler_secure_embedded.py
# pip install cryptography pymssql pandas
import base64
import time
import traceback
from datetime import datetime
from functools import wraps
from typing import Mapping, Any, Tuple
from typing import Optional

import pandas as pd
import pymssql
from cryptography.fernet import Fernet

# ======================================================
# 🔐 하드코딩된 암호문(Env) 복호화 로더 (Base64 인코딩된 암호문을 사용)
# ======================================================
ENCRYPTED_ENV_B64 = "Z0FBQUFBQnBPTmVoLTh0Y3RhVXo0N212SVVaRThYWmNyUDd4dE5Zd2R0UzQxMzdxNjhyUnNzTFJkSE11WXo0TXNYQThJV0ViSFZXMXllNkV1RTloSktYYzJzOFltNjdxWFVnLVczeFg0bWQzSUYzQ1VEc19oQ3NSbENsWVdhaGZ1QUFoNzVjZTY0RmpRdzBFZ3ZySTJSOTQ3MExJbC16VWkxYmJSZkUzaFFJd2h5am9XdTN1cGxQcThGRUVudzVIdFRYLTUybDEydWt2VFpBRU1iRml4bFlubTRTMmwtamFwb3dXN1BoUnEtSVhkM1pXUUZhVjFyNU9zR3ZHb0RXb1FCSUtBX1gyZV9BdHJqSnBzN2JyeDQ4eFV4R3RMd1lRaDYxVW5abXhvbHBSNWlla0ljWlNiWnd3dWE2dzRrVk8xbGE3THJROFBaYVppSXFSSFAxdmNuNnR1bWVObXE2WGdhZ2FBOGhPeWgtSWlYelpXbXRFTnFoTFJVNlk2dW1lcGJQVkNWYVdtNDZDdVE4bmJ5SzRsSERrY0xWMWlxT3VvX01Ncko3UVduQngxRUVWdXNDWEpsOEdsbGVkNmdlWFRNNVhwM1d4SFFyWXVEanVfSnRzb1BVcmVrUlZTa2dGQjF0UnpuZ0ZIemp6NnA0NDFLcG8xQTZXUm9YcXJtVzRubUFfQnRUcTlGZ01KYVp6YzRnWk54bDl3blJab3NfMm9ERkdMeWc0dEdWdlJheldVWGI3cGJ4Ymw5WXdyMHRDeDJtVEQyckVnTVU0V3hrU1M0bV9GNGVDUWdKeUM0dWlXZEx0VjZMM2JEQkhFSU9WUjhEcUphTlQ0YkNiTWd1MmxRMF9JQlhwX2NCV0JxVUMwc201cDNxbFhkZjVwT3Zxb0gtYjFpOG5fX3Z4UUJjMDhMa0JHMXJNY1c3V0t2RHNyOHpqUVFsSGFnb0liSlJDQnJ6NjZ0T0tsMXRneG5ONnlVQmw3VHF1Z0VsUi1mYXFwTTBkZXBwaEpHcmlGdndEd3ZfMzZvQ044SzhSV3BYU1p6ckUybGZJU0RzZE8tendwcEtYVGlieE9wMEhia09UblZtM2YwaldrV1YxdzVkSWlFbXRRNzZwWGUwWjcwbVVORmI3Zk12cFN1SGxjVVVGYTRNVEtxdU1hMjZudmVFUkJ6MlhXUFlmemRQY3lSdEl2NmdjeUpLUmlHZWNibzJUWG9PRFMwYkIwbkZ0X3d3bEpzc21kRm42Y1pBYlNxb2ZpTlNjUFIwSkctbzc2ZmNqSEswU05xT0l1dWFpSlJsSHVGLUFscmRueUtiTHI5cXhhU1VmUjJjVEZjX0tNWWpqbjMwd1VjYW85bDM2em9nWXdVNUt3U2EyQVN3WkExRHJkV3c5X3AzX2ljRzctZDdPQldwTDJRWE1hbklVajVtODJ3anB0VEhCMTczRGN5bndzYnJTOXE5dlkwTlFUNGtCd2R0LUpfUTcxWDF5NzAzVnVRWnQ4SUhQSjJQYWdhTEhtZlZCUkhndXF5blVKV09laTAzdm96NnR2ODVaWmhOYTNHVmlkc3JzaWQzVExPV0lSVEZ5WUMyS1JuaWQwQXJCQXM3WmZoRWwxQVRoMWdvNHhQaUFPNTBJVTQ5QWlQSFhzZkVZVDBWRFNpTHAwa3o5NkpUTHZvaGhhcS1mR2EtUjNiczlsSFN0b3JSalBwdDJnVDRTOGM0LXVZZVRjOF91MmR1Ull3N0pwQ3hJaW4xb0gwRWNHeUphNDhkZmx5NGU4Skp5cGN4QTlWYVVRcGllSTF6NTF4YllOWDRkcUhUckxJSDZvaHlZZHRfb2RfWXQ3Yy1RTnZJeHVLRDBlOTlCX0tNQVhMRkd2ekd6Z1FVemd1b29BUzVvS1p3UHQyNnUyYnRrakFoVXp1R0dJZFdLd1NmRktmdGIzUVpUSWRjNTZqakNxUDNlVlpfcnlCS0p2Q3NlaEpWcDU1M3o0WnpIVjBWYlRNUDF0SUFrckZVTXNmVUI1N0Z5RTl1TW1rY21JaDZtSzI3OWk3enEwSWY4N1VrdVhENFpnRjFBaGJpZldWZnRxNF9EUnJ2UHFDRFJSeFQ1bElSZnpUVGgzYkxQa19XaEFpVFdNUVlWZTdwUkpsNlZpTF84RV9FTVdQcXYtdFdqeVdCaGpFRjFmaGlNNWx0WjBMQWxueG1vbUl5WUQ0QnJQRFhQb0dxRlpBa3pCSFNzYXUzOE13bWNxWjBpZ3o5a09Cc19JdVJZOGxVdVZVa0s5V3lxMDVFR2N4UlJuNTIyc0E3RUtodk9fYktFUkFHQWptdlpPNlJUeFo0QzdneWhVLUw3QWNRZ1hOTEN6ZkIyOWtaTlFicG1pWjFyaFlkRkZpNzFjWVFWQ0p3LVA1ZTFmNDVEaDBuRTRnbUtpSjdDWGdIbDJ5Q2E2UzdKSVVEVXdGdWRxN2tUQmpKeTljS3B5VExJOE5QMzVVbUpQQ0ZWTG00ZHU0MktEMmE2QjlDclh2SVNKMGdyeW53WVN6a0UycHUzVjJ6eVhOdzJ3LTI1d1NacWFrd05YTERWYmZEdE1sQ1R0VkFXQUtERVNHVGhyTWw2WHRGb3BVNTFEZmxjRUxYMUgxOTJaNXZxOE9sUE5MbkNCbW5fdnotdmliNFFWZ0ZFSmE2RzRITUJudE5CSHpMdHhlemJIR25PRGpYc2VtQXlMOWRjaDZ6OHlXRU9uc1NDby01VV9XX3Y0SVVkMERRZnRzOUVXX1ZDNVdXa3VibUlnRUcyeXRKSW9fSDVPbXAyZV9LWmJ4X01YYjNGOEZEenRsRG11ZU1WVkNNbjB2dHY1OE5ELU4xa2FoUW52V0NmNkhxeE93bGlVM0tHeGZvUnhtWmprZFE2am85UUxRbXpQZ2I2UEFkeTZMWU5kQ242bGtnY0U3UllYVFhubU1HcHlCblV4V3kzWGc9PQ=="

# Fernet 키 (기존 코드에서 사용한 키를 그대로 사용합니다)
# 만약 키를 환경변수로 관리할 수 있다면 os.getenv()로 가져오도록 바꾸세요.
KEY = b"1Vg4VCYbCOBXM9Z9QFNTIu8CorMPc3JTELUSZvaLOHI="  # Base64 bytes (예시)


def load_env_from_embedded(encrypted_env_b64: str = ENCRYPTED_ENV_B64, key: bytes = KEY) -> dict:
    """
    코드 내부에 하드코딩된 Base64 암호문(encrypted_env_b64)을 복호화해서 dict로 반환.
    - encrypted_env_b64: gwkey.env.enc 파일 내용을 base64로 인코딩한 문자열
    - key: Fernet 키 (bytes)
    """
    if not encrypted_env_b64 or encrypted_env_b64.startswith("REPLACE_WITH"):
        raise RuntimeError("암호화된 env 문자열(ENCRYPTED_ENV_B64)을 코드에 넣어주세요.")

    try:
        # 1) Base64 -> raw encrypted bytes
        encrypted_bytes = base64.b64decode(encrypted_env_b64.encode("utf-8"))

        # 2) Fernet 복호화
        f = Fernet(key)
        decrypted_text = f.decrypt(encrypted_bytes).decode("utf-8")

        # 3) env 형식 파싱 (KEY=VALUE 형태)
        env = {}
        for line in decrypted_text.splitlines():
            if not line.strip() or line.strip().startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
        return env
    except Exception:
        print("[DECRYPT ERROR]")
        print(traceback.format_exc())
        raise


# ======================================================
# 1️⃣ DB 연결 (ENCRYPTED ENV EMBEDDED 버전)
# ======================================================
def getdb(db_name: str) -> Tuple[Optional[pymssql.Connection], Optional[pymssql.Cursor]]:
    """
    하드코딩된 암호문을 복호화해 DB 접속 정보를 읽고 pymssql로 연결.
    사용법: conn, cur = getdb("GYUN_N")
    """
    try:
        env = load_env_from_embedded()
        server = env.get(f"{db_name}_SERVER")
        user = env.get(f"{db_name}_USER")
        password = env.get(f"{db_name}_PASSWORD")
        database = env.get(f"{db_name}_DATABASE")

        if not all([server, user, password, database]):
            raise ValueError(f"⚠️ {db_name} 관련 환경변수가 부족합니다. env에서 확인하세요.")

        conn = pymssql.connect(
            server=server,
            user=user,
            password=password,
            database=database,
            charset="UTF-8"
        )
        cursor = conn.cursor()
        return conn, cursor

    except Exception:
        print("[DB CONNECTION ERROR]")
        print(traceback.format_exc())
        return None, None


# ======================================================
# 2️⃣ DB 종료
# ======================================================
def closedb(conn: pymssql.Connection) -> None:
    try:
        if conn:
            conn.close()
    except pymssql.Error as e:
        print(f"[DB CLOSE ERROR] {e}")


# ======================================================
# 3️⃣ 쿼리 실행
# ======================================================
def runquery(cursor: object, query: str, params: Optional[tuple] = None) -> Optional[pd.DataFrame]:
    """SQL 실행 후 SELECT면 DataFrame 반환, 그 외 쿼리는 커밋만 수행"""

    @timeit
    def dfencoding_auto(df: pd.DataFrame) -> pd.DataFrame:
        """문자열 컬럼 EUC-KR 복원 시도"""
        def decode_if_needed(val):
            if isinstance(val, str):
                try:
                    return val.encode("latin1", errors="replace").decode("euc-kr", errors="replace")
                except Exception:
                    return val
            return val

        for col in df.select_dtypes(include="object").columns:
            df[col] = df[col].apply(decode_if_needed)
        return df

    try:
        cursor.execute(query, params or ())
        if query.strip().upper().startswith("SELECT"):
            rows = cursor.fetchall()
            if not rows:
                return pd.DataFrame()
            columns = [col[0] for col in cursor.description]
            df = pd.DataFrame(rows, columns=columns)
            return dfencoding_auto(df)
        else:
            cursor.connection.commit()
            # print("[INFO] Query committed successfully.")
    except pymssql.DatabaseError as db_err:
        print(f"[DB ERROR] {db_err}")
        print(traceback.format_exc())
        raise
    except Exception:
        print(f"[EXCEPTION] {traceback.format_exc()}")
        raise
    return None



def timeit(func):
    @wraps(func)
    def _wrap(*args, **kwargs):
        t0 = time.perf_counter()
        out = func(*args, **kwargs)
        dt_s = time.perf_counter() - t0   # 초 단위
        if dt_s >= 1.0:
            print(f"[{func.__name__}] {dt_s:.3f} s")
        return out
    return _wrap

# ======================================================
# ✅ 테스트 실행
# ======================================================
if __name__ == "__main__":
    # 테스트용: ENCRYPTED_ENV_B64가 설정되어 있어야 함
    conn, cur = getdb("GYUN_N")
    if conn:
        print("✅ DB 연결 성공")

        # 🔹 JEN 테이블 최근 10개 출력
        query = """
            SELECT TOP 10 *
            FROM JEN
            ORDER BY JDATE DESC
        """
        df = runquery(cur, query)
        print(df)

        closedb(conn)
    else:
        print("❌ DB 연결 실패")

