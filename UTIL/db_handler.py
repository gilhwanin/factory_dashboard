import os, traceback
import pymssql
from dotenv import load_dotenv
from typing import Tuple, Optional
import pandas as pd
from UTIL.dfencoding import dfencoding_auto

# .env 파일 경로 지정
if os.getlogin() in ["imsi"]:
    env_path = r"C:\\Users\\LSH2\\Desktop\\PY\\GWMAKE\\FNAME\\GWONE\\resource\\.env"
else:
    env_path = r"C:\\P\\inenv.env"

load_dotenv(dotenv_path=env_path)

def getdb(db_name: str) -> Tuple[Optional[pymssql.Connection], Optional[pymssql.Cursor]]:
    try:
        server = os.getenv(f"{db_name}_SERVER")
        user = os.getenv(f"{db_name}_USER")
        password = os.getenv(f"{db_name}_PASSWORD")
        database = os.getenv(f"{db_name}_DATABASE")

        if not all([server, user, password, database]):
            raise ValueError(f"⚠️ {db_name}에 대한 환경 변수를 찾을 수 없습니다.")

        conn = pymssql.connect(
            server=server,
            user=user,
            password=password,
            database=database,
            charset='UTF-8'
        )
        cursor = conn.cursor()
        return conn, cursor

    except pymssql.DatabaseError as db_err:
        print(f"데이터베이스 연결 오류: {db_err}")
        print(traceback.format_exc())

    except Exception as e:
        print(f"알 수 없는 오류 발생: {traceback.format_exc()}")

    return None, None

def closedb(conn: pymssql.Connection) -> None:
    try:
        conn.close()
    except pymssql.Error as e:
        print(f"DB 연결 종료 오류: {e}")

def runquery(cursor: object, query: str, params: Optional[tuple] = None) -> Optional[pd.DataFrame]:
    """SQL 실행 후 SELECT면 DataFrame 반환, 그 외 쿼리는 커밋만 수행"""

    def dfencoding_auto(df: pd.DataFrame) -> pd.DataFrame:
        """문자열 컬럼을 EUC-KR로 복원 시도"""
        def decode_if_needed(val):
            if isinstance(val, str):
                try:
                    return val.encode("latin1", errors="replace").decode("euc-kr", errors="replace")
                except:
                    return val
            return val

        for col in df.select_dtypes(include='object').columns:
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

        cursor.connection.commit()
        print("[INFO] Query committed successfully.")

    except pymssql.DatabaseError as db_err:
        print(f"[DB ERROR] {db_err}")
        print(traceback.format_exc())
    except Exception:
        print(f"[EXCEPTION] {traceback.format_exc()}")
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

    # 사용예시 :
    # from db_handler import getdb, closedb, insert_record
    #
    # conn, cursor = getdb("HJFOOD")
    #
    # if cursor:
    #     insert_record(
    #         cursor,
    #         "mjen2",
    #         {
    #             "co": "A01",
    #             "uname": "홍길동",
    #             "pdate": "2025-05-18"
    #         }
    #     )
    #
    # or
    #
    # insert_record(
    #     cursor,
    #     "mjen2",
    #     {
    #         "co": "A01",
    #         "uname": "홍길동",
    #         "pdate": "2025-05-18"
    #     }
    # )
    #     closedb(conn)