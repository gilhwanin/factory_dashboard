from UTIL.db_handler import getdb, runquery, closedb
from UTIL.const import DB_NAME

def fetch_default_products():
    """
    DASHBOARD_DEFAULT_PRODUCTS 테이블에서 (co, retailer) 리스트를 조회하여 반환한다.
    반환 형식: [(co, retailer), ...]
    """
    conn, cur = getdb(DB_NAME)
    try:
        sql = "SELECT co, retailer FROM DASHBOARD_DEFAULT_PRODUCTS"
        df = runquery(cur, sql, [])
        results = []
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                results.append((str(row['co']).strip(), str(row['retailer']).strip()))
        return results
    finally:
        closedb(conn)

def add_default_product(co, retailer):
    """
    DASHBOARD_DEFAULT_PRODUCTS 테이블에 (co, retailer) 추가 (중복 무시)
    """
    conn, cur = getdb(DB_NAME)
    try:
        # 중복 체크
        check_sql = "SELECT 1 FROM DASHBOARD_DEFAULT_PRODUCTS WHERE co = %s AND retailer = %s"
        df = runquery(cur, check_sql, [co, retailer])
        if df is not None and not df.empty:
            return  # 이미 존재

        insert_sql = "INSERT INTO DASHBOARD_DEFAULT_PRODUCTS (co, retailer) VALUES (%s, %s)"
        runquery(cur, insert_sql, [co, retailer])
    finally:
        closedb(conn)

def remove_default_product(co, retailer):
    """
    DASHBOARD_DEFAULT_PRODUCTS 테이블에서 (co, retailer) 삭제
    """
    conn, cur = getdb(DB_NAME)
    try:
        sql = "DELETE FROM DASHBOARD_DEFAULT_PRODUCTS WHERE co = %s AND retailer = %s"
        runquery(cur, sql, [co, retailer])
    finally:
        closedb(conn)
