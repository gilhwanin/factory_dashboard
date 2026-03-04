import base64
import time
import traceback
from contextlib import contextmanager
from functools import wraps
from typing import Tuple, Optional

import pandas as pd
import pymssql
from cryptography.fernet import Fernet

# ======================================================
# 암호문(Env) 복호화 로더
# ======================================================
ENCRYPTED_ENV_B64 = "Z0FBQUFBQnBPTmVoLTh0Y3RhVXo0N212SVVaRThYWmNyUDd4dE5Zd2R0UzQxMzdxNjhyUnNzTFJkSE11WXo0TXNYQThJV0ViSFZXMXllNkV1RTloSktYYzJzOFltNjdxWFVnLVczeFg0bWQzSUYzQ1VEc19oQ3NSbENsWVdhaGZ1QUFoNzVjZTY0RmpRdzBFZ3ZySTJSOTQ3MExJbC16VWkxYmJSZkUzaFFJd2h5am9XdTN1cGxQcThGRUVudzVIdFRYLTUybDEydWt2VFpBRU1iRml4bFlubTRTMmwtamFwb3dXN1BoUnEtSVhkM1pXUUZhVjFyNU9zR3ZHb0RXb1FCSUtBX1gyZV9BdHJqSnBzN2JyeDQ4eFV4R3RMd1lRaDYxVW5abXhvbHBSNWlla0ljWlNiWnd3dWE2dzRrVk8xbGE3THJROFBaYVppSXFSSFAxdmNuNnR1bWVObXE2WGdhZ2FBOGhPeWgtSWlYelpXbXRFTnFoTFJVNlk2dW1lcGJQVkNWYVdtNDZDdVE4bmJ5SzRsSERrY0xWMWlxT3VvX01Ncko3UVduQngxRUVWdXNDWEpsOEdsbGVkNmdlWFRNNVhwM1d4SFFyWXVEanVfSnRzb1BVcmVrUlZTa2dGQjF0UnpuZ0ZIemp6NnA0NDFLcG8xQTZXUm9YcXJtVzRubUFfQnRUcTlGZ01KYVp6YzRnWk54bDl3blJab3NfMm9ERkdMeWc0dEdWdlJheldVWGI3cGJ4Ymw5WXdyMHRDeDJtVEQyckVnTVU0V3hrU1M0bV9GNGVDUWdKeUM0dWlXZEx0VjZMM2JEQkhFSU9WUjhEcUphTlQ0YkNiTWd1MmxRMF9JQlhwX2NCV0JxVUMwc201cDNxbFhkZjVwT3Zxb0gtYjFpOG5fX3Z4UUJjMDhMa0JHMXJNY1c3V0t2RHNyOHpqUVFsSGFnb0liSlJDQnJ6NjZ0T0tsMXRneG5ONnlVQmw3VHF1Z0VsUi1mYXFwTTBkZXBwaEpHcmlGdndEd3ZfMzZvQ044SzhSV3BYU1p6ckUybGZJU0RzZE8tendwcEtYVGlieE9wMEhia09UblZtM2YwaldrV1YxdzVkSWlFbXRRNzZwWGUwWjcwbVVORmI3Zk12cFN1SGxjVVVGYTRNVEtxdU1hMjZudmVFUkJ6MlhXUFlmemRQY3lSdEl2NmdjeUpLUmlHZWNibzJUWG9PRFMwYkIwbkZ0X3d3bEpzc21kRm42Y1pBYlNxb2ZpTlNjUFIwSkctbzc2ZmNqSEswU05xT0l1dWFpSlJsSHVGLUFscmRueUtiTHI5cXhhU1VmUjJjVEZjX0tNWWpqbjMwd1VjYW85bDM2em9nWXdVNUt3U2EyQVN3WkExRHJkV3c5X3AzX2ljRzctZDdPQldwTDJRWE1hbklVajVtODJ3anB0VEhCMTczRGN5bndzYnJTOXE5dlkwTlFUNGtCd2R0LUpfUTcxWDF5NzAzVnVRWnQ4SUhQSjJQYWdhTEhtZlZCUkhndXF5blVKV09laTAzdm96NnR2ODVaWmhOYTNHVmlkc3JzaWQzVExPV0lSVEZ5WUMyS1JuaWQwQXJCQXM3WmZoRWwxQVRoMWdvNHhQaUFPNTBJVTQ5QWlQSFhzZkVZVDBWRFNpTHAwa3o5NkpUTHZvaGhhcS1mR2EtUjNiczlsSFN0b3JSalBwdDJnVDRTOGM0LXVZZVRjOF91MmR1Ull3N0pwQ3hJaW4xb0gwRWNHeUphNDhkZmx5NGU4Skp5cGN4QTlWYVVRcGllSTF6NTF4YllOWDRkcUhUckxJSDZvaHlZZHRfb2RfWXQ3Yy1RTnZJeHVLRDBlOTlCX0tNQVhMRkd2ekd6Z1FVemd1b29BUzVvS1p3UHQyNnUyYnRrakFoVXp1R0dJZFdLd1NmRktmdGIzUVpUSWRjNTZqakNxUDNlVlpfcnlCS0p2Q3NlaEpWcDU1M3o0WnpIVjBWYlRNUDF0SUFrckZVTXNmVUI1N0Z5RTl1TW1rY21JaDZtSzI3OWk3enEwSWY4N1VrdVhENFpnRjFBaGJpZldWZnRxNF9EUnJ2UHFDRFJSeFQ1bElSZnpUVGgzYkxQa19XaEFpVFdNUVlWZTdwUkpsNlZpTF84RV9FTVdQcXYtdFdqeVdCaGpFRjFmaGlNNWx0WjBMQWxueG1vbUl5WUQ0QnJQRFhQb0dxRlpBa3pCSFNzYXUzOE13bWNxWjBpZ3o5a09Cc19JdVJZOGxVdVZVa0s5V3lxMDVFR2N4UlJuNTIyc0E3RUtodk9fYktFUkFHQWptdlpPNlJUeFo0QzdneWhVLUw3QWNRZ1hOTEN6ZkIyOWtaTlFicG1pWjFyaFlkRkZpNzFjWVFWQ0p3LVA1ZTFmNDVEaDBuRTRnbUtpSjdDWGdIbDJ5Q2E2UzdKSVVEVXdGdWRxN2tUQmpKeTljS3B5VExJOE5QMzVVbUpQQ0ZWTG00ZHU0MktEMmE2QjlDclh2SVNKMGdyeW53WVN6a0UycHUzVjJ6eVhOdzJ3LTI1d1NacWFrd05YTERWYmZEdE1sQ1R0VkFXQUtERVNHVGhyTWw2WHRGb3BVNTFEZmxjRUxYMUgxOTJaNXZxOE9sUE5MbkNCbW5fdnotdmliNFFWZ0ZFSmE2RzRITUJudE5CSHpMdHhlemJIR25PRGpYc2VtQXlMOWRjaDZ6OHlXRU9uc1NDby01VV9XX3Y0SVVkMERRZnRzOUVXX1ZDNVdXa3VibUlnRUcyeXRKSW9fSDVPbXAyZV9LWmJ4X01YYjNGOEZEenRsRG11ZU1WVkNNbjB2dHY1OE5ELU4xa2FoUW52V0NmNkhxeE93bGlVM0tHeGZvUnhtWmprZFE2am85UUxRbXpQZ2I2UEFkeTZMWU5kQ242bGtnY0U3UllYVFhubU1HcHlCblV4V3kzWGc9PQ=="

KEY = b"1Vg4VCYbCOBXM9Z9QFNTIu8CorMPc3JTELUSZvaLOHI="


def timeit(func):
    @wraps(func)
    def _wrap(*args, **kwargs):
        t0 = time.perf_counter()
        out = func(*args, **kwargs)
        dt_s = time.perf_counter() - t0
        if dt_s >= 1.0:
            print(f"[{func.__name__}] {dt_s:.3f} s")
        return out
    return _wrap


def load_env_from_embedded(encrypted_env_b64: str = ENCRYPTED_ENV_B64, key: bytes = KEY) -> dict:
    if not encrypted_env_b64 or encrypted_env_b64.startswith("REPLACE_WITH"):
        raise RuntimeError("암호화된 env 문자열(ENCRYPTED_ENV_B64)을 코드에 넣어주세요.")

    try:
        encrypted_bytes = base64.b64decode(encrypted_env_b64.encode("utf-8"))
        f = Fernet(key)
        decrypted_text = f.decrypt(encrypted_bytes).decode("utf-8")

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


def getdb(db_name: str) -> Tuple[Optional[pymssql.Connection], Optional[pymssql.Cursor]]:
    try:
        env = load_env_from_embedded()
        server = env.get(f"{db_name}_SERVER")
        user = env.get(f"{db_name}_USER")
        password = env.get(f"{db_name}_PASSWORD")
        database = env.get(f"{db_name}_DATABASE")

        if not all([server, user, password, database]):
            raise ValueError(f"{db_name} 관련 환경변수가 부족합니다.")

        conn = pymssql.connect(
            server=server, user=user, password=password,
            database=database, charset="UTF-8",
        )
        return conn, conn.cursor()

    except Exception:
        print("[DB CONNECTION ERROR]")
        print(traceback.format_exc())
        return None, None


def closedb(conn: pymssql.Connection) -> None:
    try:
        if conn:
            conn.close()
    except pymssql.Error as e:
        print(f"[DB CLOSE ERROR] {e}")


@contextmanager
def db_connection(db_name: str):
    """Context manager for DB connections. Raises ConnectionError on failure."""
    conn, cur = getdb(db_name)
    if conn is None or cur is None:
        raise ConnectionError(f"DB 연결 실패: {db_name}")
    try:
        yield conn, cur
    finally:
        closedb(conn)


def runquery(cursor: object, query: str, params: Optional[tuple] = None) -> Optional[pd.DataFrame]:
    """SQL 실행 후 SELECT면 DataFrame 반환, 그 외 쿼리는 커밋만 수행"""

    @timeit
    def dfencoding_auto(df: pd.DataFrame) -> pd.DataFrame:
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
    except pymssql.DatabaseError as db_err:
        print(f"[DB ERROR] {db_err}")
        print(traceback.format_exc())
        raise
    except Exception:
        print(f"[EXCEPTION] {traceback.format_exc()}")
        raise
    return None


def insert_record(cursor: object, table_name: str, data: dict):
    if not data:
        raise ValueError("빈 데이터는 INSERT할 수 없습니다.")

    fields = ", ".join(data.keys())
    placeholders = ", ".join(["%s"] * len(data))
    values = tuple(data.values())

    query = f"""
        INSERT INTO {table_name} ({fields})
        OUTPUT INSERTED.*
        VALUES ({placeholders})
    """
    cursor.execute(query, values)
    row = cursor.fetchone()
    cursor.connection.commit()

    return row[0] if row else None


if __name__ == "__main__":
    conn, cur = getdb("GYUN_N")
    if conn:
        print("DB 연결 성공")
        df = runquery(cur, "SELECT TOP 10 * FROM JEN ORDER BY JDATE DESC")
        print(df)
        closedb(conn)
    else:
        print("DB 연결 실패")
