import oracledb


# -----------------------------------------
# 오라클 연결 함수
# -----------------------------------------
def get_oracle_connection():
    """
    Oracle DB 연결 객체 반환
    """
    oracledb.init_oracle_client(lib_dir=r"C:\P\oracle_client\instantclient_21_19")

    conn = oracledb.connect(
        user="fdp",
        password="fdp",
        dsn="gwhj.iptime.org:1521/xe"
    )
    return conn


# -----------------------------------------
# 원하는 SELECT 쿼리 결과만 반환하는 함수
# -----------------------------------------
def get_box_summary():
    """
    TABROWSTATIC_202511 기준 집계 결과 반환

    반환값 예:
    {
        "PACK": 120,
        "TOTAL_BOXES": 40,
        "BOX_WEIGHT": 85.41
    }
    """
    sql = """
        SELECT 
            COUNT(NWEIGHT) AS PACK,
            COUNT(DISTINCT NBOXSEQNO) AS TOTAL_BOXES,
            ROUND(SUM(NWEIGHT) / 1000, 2) AS BOX_WEIGHT
        FROM TABROWSTATIC_202511
        WHERE NRESERVE4 = 21
          AND NPRDDATE = '20251110'
          AND NWPMMAPHIDX1 = 0
          AND CSKUCODE LIKE '%677613%'
    """

    conn = get_oracle_connection()
    cur = conn.cursor()

    cur.execute(sql)
    row = cur.fetchone()

    cur.close()
    conn.close()

    return {
        "PACK": row[0],
        "TOTAL_BOXES": row[1],
        "BOX_WEIGHT": row[2]
    }
