import pandas as pd
from UTIL.db_handler import getdb, runquery, closedb


def get_item_summary_by_date(target_date: str, code_list=None):
    """
    COS_B 기반, C06 기준 품목(C10)별 총 C17 집계
    + C29 리스트 필터 추가
    """
    if code_list is None:
        code_list = []

    conn, cur = getdb("GWCHUL")

    try:
        # ------------------------------
        # C29 조건 생성
        # ------------------------------
        code_filter_sql = ""
        params = [target_date]

        if len(code_list) > 0:
            placeholders = ",".join(["%s"] * len(code_list))
            code_filter_sql = f" AND A.C29 IN ({placeholders}) "
            params += code_list

        # ------------------------------
        # 최종 SQL
        # ------------------------------
        sql = f"""
            SELECT 
                A.C10 AS item_name,
                SUM(CONVERT(int, A.C17)) AS total_pack,  
                B.PS AS ps_unit
            FROM COS_B A
                LEFT JOIN COS_M B ON A.C11 = B.CCO
                LEFT JOIN MASTER C ON B.JICO = C.CO
            WHERE A.C06 = %s
              {code_filter_sql}
            GROUP BY A.C10, B.PS
            ORDER BY A.C10
        """

        df = runquery(cur, sql, params)

    finally:
        closedb(conn)

    if df is None or df.empty:
        print("데이터 없음")
        return pd.DataFrame()

    # numeric 변환
    df["ps_unit"] = pd.to_numeric(df["ps_unit"], errors="coerce").fillna(0).astype(int)
    df["total_pack"] = pd.to_numeric(df["total_pack"], errors="coerce").fillna(0).astype(int)

    # BOX 계산
    df["TOTAL_BOX"] = df.apply(
        lambda row: int(row["total_pack"] / row["ps_unit"]) if row["ps_unit"] > 0 else 0,
        axis=1
    )

    return df

codes = ["501998"]
df = get_item_summary_by_date("2025-12-05", codes)
print(df)
