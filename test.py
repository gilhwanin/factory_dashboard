# pan_rno_update_from_mwnum.py

from UTIL.db_handler import getdb, runquery, closedb


def fetch_pan_rows(cur):
    query = """
    SELECT PKEY, BIGO
    FROM PAN
    WHERE ddate = %s
      AND RNAME LIKE %s
      AND (RNO IS NULL OR RNO = '')
      AND BIGO NOT LIKE %s
    """
    params = ('2026-01-27', '%롯데마트%', '%증평%')
    df = runquery(cur, query, params)
    return df


def process_bigo(bigo: str) -> str:
    if not bigo:
        return ""
    return bigo.split('(')[0].strip()


def fetch_mwnum(cur, processed_bigo: str):
    query = """
    SELECT TOP 1 MWNUM
    FROM MWNUM
    WHERE BIGO = %s
    """
    df = runquery(cur, query, (processed_bigo,))
    if df.empty:
        return None
    return df.iloc[0]["MWNUM"]


def update_pan_rno(cur, pkey: int, mwnum: str):
    query = """
    UPDATE PAN
       SET RNO = %s
     WHERE PKEY = %s
    """
    runquery(cur, query, (mwnum, pkey))


def main():
    conn, cur = getdb("GYUN_N")
    if not conn:
        print("❌ DB 연결 실패")
        return

    try:
        print("✅ DB 연결 성공")

        pan_df = fetch_pan_rows(cur)

        if pan_df.empty:
            print("조회된 PAN 데이터 없음")
            return

        total = len(pan_df)
        updated = 0
        skipped = 0

        print("\n===== PAN → MWNUM 매칭 및 RNO 업데이트 시작 =====")

        for _, row in pan_df.iterrows():
            pkey = row["PKEY"]
            bigo = row["BIGO"]

            processed = process_bigo(bigo)
            mwnum = fetch_mwnum(cur, processed)

            if not mwnum:
                print(f"[SKIP] PKEY={pkey} | BIGO='{bigo}' → MWNUM 없음")
                skipped += 1
                continue

            update_pan_rno(cur, pkey, mwnum)
            print(f"[OK] PKEY={pkey} | BIGO='{bigo}' → RNO = {mwnum}")
            updated += 1

        print("\n===== 처리 완료 =====")
        print(f"총 대상 건수 : {total}")
        print(f"업데이트 완료 : {updated}")
        print(f"스킵(MWNUM 없음) : {skipped}")

    finally:
        closedb(conn)


if __name__ == "__main__":
    main()
