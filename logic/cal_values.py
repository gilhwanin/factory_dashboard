# dashboard_helpers.py
# -----------------------------------------------------
# OrderDashboardWidget 에서 #7. DB 조회/계산 헬퍼 함수 분리 버전
# -----------------------------------------------------

from datetime import datetime
import pandas as pd

# 🔥 기존 프로젝트에서 이미 존재한다고 가정
from UTIL.db_handler import getdb, runquery, closedb
DB_NAME = "GP"
# -----------------------------------------------------
# 홈플러스 발주량 조회
# -----------------------------------------------------
def get_homeplus_order_qty(co: str, sdate_str: str) -> int:
    conn, cur = getdb("GWCHUL")
    try:
        sql = """
            SELECT ISNULL(SUM(PAN), 0) AS sum_pan
            FROM PAN
            WHERE CO = %s
              AND CONVERT(DATE, PDATE) = %s
        """
        df = runquery(cur, sql, [co, sdate_str])
    finally:
        closedb(conn)

    if df is None or df.empty:
        return 0

    try:
        return int(df.iloc[0, 0] or 0)
    except:
        return 0



# -----------------------------------------------------
# 이마트 발주량 조회
# -----------------------------------------------------
def get_emart_order_qty(tco: str, sdate_str: str) -> int:
    conn, cur = getdb("GFOOD_B")
    try:
        sql_key = """
            SELECT TOP 1 CO
            FROM MMASTER
            WHERE TCO = %s
        """
        df_key = runquery(cur, sql_key, [tco])
        if df_key is None or df_key.empty:
            return 0

        real_co = str(df_key.iloc[0]["CO"]).strip()
        if not real_co:
            return 0

        sql = """
            SELECT SUM(PANKG) AS sum_pan
            FROM MPAN
            WHERE CO = %s
              AND CONVERT(DATE, SDATE) = %s
        """
        df = runquery(cur, sql, [real_co, sdate_str])
    finally:
        closedb(conn)

    if df is None or df.empty:
        return 0

    try:
        return int(df.iloc[0, 0] or 0)
    except:
        return 0



# -----------------------------------------------------
# 마켓컬리 발주량 조회
# -----------------------------------------------------
def get_kurly_order_qty(tco: str, sdate_str: str) -> int:
    conn, cur = getdb("GFOOD_B")
    try:
        sql_key = """
            SELECT TOP 1 CO
            FROM MMASTER
            WHERE TCO = %s
        """
        df_key = runquery(cur, sql_key, [tco])
        if df_key is None or df_key.empty:
            return 0

        real_co = str(df_key.iloc[0]["CO"]).strip()
        if not real_co:
            return 0

        sql = """
            SELECT SUM(PANKG) AS sum_pan
            FROM MPAN
            WHERE CO = %s
              AND CONVERT(DATE, SDATE) = %s
        """
        df = runquery(cur, sql, [real_co, sdate_str])
    finally:
        closedb(conn)

    if df is None or df.empty:
        return 0

    try:
        return int(df.iloc[0, 0] or 0)
    except:
        return 0



# -----------------------------------------------------
# 코스온 발주량 조회
# -----------------------------------------------------
def get_coson_order_qty(base_co: str, sdate_str: str) -> int:
    conn, cur = getdb("GWCHUL")
    try:
        # MASTER 에서 TCO3 조회
        sql_master = """
            SELECT TOP 1 TCO3
            FROM MASTER
            WHERE CO = %s
        """
        df_key = runquery(cur, sql_master, [base_co])
        if df_key is None or df_key.empty:
            return 0

        tco3 = str(df_key.iloc[0]["TCO3"]).strip()
        if not tco3:
            return 0

        # COSONC 조회
        sql_coson = """
            SELECT TOP 1 FINAL_QTY
            FROM COSONC
            WHERE LCODE = %s
              AND CONVERT(DATE, LDATE) = %s
        """
        df = runquery(cur, sql_coson, [tco3, sdate_str])
    finally:
        closedb(conn)

    if df is None or df.empty:
        return 0

    try:
        return int(df.iloc[0, 0] or 0)
    except:
        return 0


# -----------------------------------------------------
# 이마트 MASTER용 CO 변환
# -----------------------------------------------------
def get_emart_master_co(base_co: str) -> str:
    conn, cur = getdb("GFOOD_B")
    try:
        sql = """
            SELECT TOP 1 TCO
            FROM MMASTER
            WHERE CO = %s
        """
        df = runquery(cur, sql, [base_co])
    finally:
        closedb(conn)

    if df is None or df.empty:
        return base_co

    try:
        return str(df.iloc[0]["TCO"]).strip()
    except:
        return base_co


# -----------------------------------------------------
# PACSU 조회
# -----------------------------------------------------
def get_pacsu_by_co(co: str) -> int:
    try:
        conn, cur = getdb("GFOOD_B")
    except:
        return 1

    try:
        sql = """
            SELECT TOP 1 PACSU
            FROM MASTER
            WHERE CO = %s
        """
        df = runquery(cur, sql, [co])
    finally:
        closedb(conn)

    if df is None or df.empty:
        return 1

    val = df.iloc[0]["PACSU"]
    try:
        pacsu = int(val)
        return pacsu if pacsu > 0 else 1
    except:
        return 1


# -----------------------------------------------------
# 생산량(팩수) 조회
# -----------------------------------------------------
def get_produced_qty_packs(co: str, sdate_str: str, pacsu: int) -> int:
    try:
        conn, cur = getdb("GFOOD_B")
    except:
        return 0

    try:
        sql = """
            SELECT ISNULL(SUM(PAN),0) AS sum_pan
            FROM PAN
            WHERE CH = 'C'
              AND JNAME = '공장(양념육)'
              AND CO = %s
              AND CONVERT(DATE, PDATE) = %s
        """
        df = runquery(cur, sql, [co, sdate_str])
    finally:
        closedb(conn)

    if df is None or df.empty:
        return 0

    try:
        box_sum = int(df.iloc[0][0] or 0)
    except:
        box_sum = 0

    return box_sum * (pacsu if pacsu > 0 else 1)


# -----------------------------------------------------
# prev_residue 조회
# -----------------------------------------------------
def get_prev_residue_from_today(co: str) -> int:
    conn, cur = getdb("GP")  # 🔥 사용 "GP" 알아서 맞춰주세요
    try:
        sql = """
            SELECT TOP 1 today_residue
            FROM ORDER_DASHBOARD
            WHERE co = %s
            ORDER BY PK DESC
        """
        df = runquery(cur, sql, [co])
    finally:
        closedb(conn)

    if df is None or df.empty:
        return 0

    try:
        return int(df.iloc[0][0] or 0)
    except:
        return 0


# -----------------------------------------------------
# PAN 기반 재고(box) 조회
# -----------------------------------------------------
def get_stock_from_pan(bco: str, sdate_str: str) -> int:
    conn, cur = getdb("GFOOD_B")
    try:
        sql = """
            SELECT SUM(A.IPGO) - SUM(A.PAN) as stock_box
            FROM PAN A
            WHERE A.CH <> 'M'
              AND A.CO = %s
              AND A.PDATE <= CONVERT(smalldatetime, %s)
              AND A.JNAME <> ''
              AND A.JUM = '지점'
              AND A.DE = 'N'
            GROUP BY A.JNAME
        """
        df = runquery(cur, sql, [bco, sdate_str])
    finally:
        closedb(conn)

    if df is None or df.empty:
        return 0

    total = 0
    for v in df.iloc[:, 0]:
        try:
            val = int(v)
            if val > 0:
                total += val
        except:
            pass

    return total


# -----------------------------------------------------
# 레시피 기반 PLAN_KG 계산
# -----------------------------------------------------
def calc_plan_kg_by_recipe(df_order, recipe_keyword: str):
    """
    ORDER_DASHBOARD 기반 원료/소스용 PLAN_KG 계산
    """
    if df_order is None or df_order.empty:
        return None

    df_order = df_order.copy()
    df_order.columns = [c.upper() for c in df_order.columns]
    df_order["CO"] = df_order["CO"].astype(str).str.strip()

    co_list = df_order["CO"].unique().tolist()
    if not co_list:
        return None

    placeholders = ",".join(["%s"] * len(co_list))

    conn, cur = getdb("GFOOD_B")
    try:
        sql = f"""
            SELECT CO, BCO, BUNAME, SA
            FROM RECIPE
            WHERE CO IN ({placeholders})
              AND BUNAME LIKE %s
        """
        params = co_list + [f"%{recipe_keyword}%"]
        df_recipe = runquery(cur, sql, params)
    finally:
        closedb(conn)

    if df_recipe is None or df_recipe.empty:
        return None

    df_recipe.columns = [c.upper() for c in df_recipe.columns]
    df_recipe["CO"] = df_recipe["CO"].astype(str).str.strip()
    df_recipe["BCO"] = df_recipe["BCO"].astype(str).str.strip()
    df_recipe["SA"] = df_recipe["SA"].fillna(1).astype(float)

    df = df_order.merge(df_recipe, on="CO", how="inner")
    if df.empty:
        return None

    for col in ("ORDER_QTY_AFTER", "PRE_PRODUCTION_QTY", "PREV_RESIDUE", "PKG"):
        if col not in df.columns:
            df[col] = 0

    df["ORDER_QTY_AFTER"] = df["ORDER_QTY_AFTER"].fillna(0).astype(float)
    df["PRE_PRODUCTION_QTY"] = df["PRE_PRODUCTION_QTY"].fillna(0).astype(float)
    df["PREV_RESIDUE"] = df["PREV_RESIDUE"].fillna(0).astype(float)
    df["PKG"] = df["PKG"].fillna(0).astype(float)

    df["PLAN_PACKS"] = (
        df["ORDER_QTY_AFTER"]
        + df["PRE_PRODUCTION_QTY"]
        - df["PREV_RESIDUE"]
    )

    # KG 계산
    df["PLAN_KG"] = df["PLAN_PACKS"] * df["PKG"] * df["SA"] / 100

    df = df[df["PLAN_KG"] > 0]
    if df.empty:
        return None

    grouped = df.groupby(["BCO", "BUNAME"], as_index=False)["PLAN_KG"].sum()
    return grouped


# -----------------------------------------------------
# 벤더별 최종 발주팩 계산 공통 함수
# -----------------------------------------------------
def calc_order_qty_packs(base_co: str, vendor: str, sdate_str: str, pacsu: int) -> int:

    vendor = (vendor or "").strip()

    if pacsu is None or pacsu <= 0:
        pacsu = 1

    if vendor == "홈플러스":
        box_qty = get_homeplus_order_qty(base_co, sdate_str)
        return box_qty * pacsu

    if vendor == "이마트":
        packs = get_emart_order_qty(base_co, sdate_str)
        return packs * pacsu

    if vendor == "마켓컬리":
        return get_kurly_order_qty(base_co, sdate_str)

    if vendor == "코스온":
        return get_coson_order_qty(base_co, sdate_str)

    return 0


def recalc_dashboard_raw_keep_manual(qdate):
    if isinstance(qdate, str):
        sdate_str = qdate
        sdate_dt = datetime.strptime(qdate, "%Y-%m-%d")
    else:
        sdate_str = qdate.toString("yyyy-MM-dd")
        sdate_dt = datetime(qdate.year(), qdate.month(), qdate.day(), 0, 0, 0)
    now = datetime.now()

    # ORDER_DASHBOARD 조회
    conn, cur = getdb(DB_NAME)
    try:
        sql = """
            SELECT co, order_qty_after, pre_production_qty, prev_residue, pkg
            FROM ORDER_DASHBOARD
            WHERE CONVERT(DATE, sdate) = %s
        """
        df_order = runquery(cur, sql, [sdate_str])
    finally:
        closedb(conn)

    if df_order is None or df_order.empty:
        return

    df_order.columns = [c.upper() for c in df_order.columns]
    df_order["CO"] = df_order["CO"].astype(str).str.strip()

    # 레시피 기반 PLAN_KG
    grouped = calc_plan_kg_by_recipe(df_order, "(정선)")
    if grouped is None or grouped.empty:
        return

    valid_keys = {
        (str(r.BCO).strip(), str(r.BUNAME).strip())
        for r in grouped.itertuples(index=False)
    }

    # 기존 RAW 조회
    conn, cur = getdb(DB_NAME)
    try:
        sql = """
            SELECT PK, uname, co
            FROM DASHBOARD_RAW
            WHERE CONVERT(DATE, sdate) = %s
        """
        df_exist = runquery(cur, sql, [sdate_str])
    finally:
        closedb(conn)

    exist_map = {}
    if df_exist is not None and not df_exist.empty:
        df_exist.columns = [c.upper() for c in df_exist.columns]
        for r in df_exist.itertuples(index=False):
            exist_map[(str(r.CO).strip(), str(r.UNAME).strip())] = r

    # DELETE rows not needed
    delete_keys = set(exist_map.keys()) - valid_keys
    if delete_keys:
        conn, cur = getdb(DB_NAME)
        try:
            for co, uname in delete_keys:
                runquery(
                    cur,
                    """
                    DELETE FROM DASHBOARD_RAW
                    WHERE CO=%s AND UNAME=%s
                      AND CONVERT(DATE, sdate)=%s
                    """,
                    [co, uname, sdate_str],
                )
        finally:
            closedb(conn)

    # UPDATE / INSERT
    conn, cur = getdb(DB_NAME)
    try:
        for r in grouped.itertuples(index=False):
            bco = str(r.BCO).strip()
            buname = str(r.BUNAME).strip()
            qty_int = int(round(float(r.PLAN_KG or 0)))

            key = (bco, buname)
            exist = exist_map.get(key)

            if exist:
                sql_up = """
                    UPDATE DASHBOARD_RAW
                    SET order_qty_after = %s
                    WHERE PK = %s
                """
                runquery(cur, sql_up, [qty_int, exist.PK])

            else:
                stock_val = get_stock_from_pan(bco, sdate_str)
                sql_in = """
                    INSERT INTO DASHBOARD_RAW (
                        uname, co, sdate, created_time,
                        stock, order_qty, order_qty_after,
                        prepro_qty, ipgo_qty
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """
                runquery(
                    cur,
                    sql_in,
                    [
                        buname, bco, sdate_dt, now,
                        stock_val, qty_int, qty_int,
                        0, 0,
                    ],
                )
    finally:
        closedb(conn)



def recalc_dashboard_sauce_keep_manual(qdate):
    if isinstance(qdate, str):
        sdate_str = qdate
        sdate_dt = datetime.strptime(qdate, "%Y-%m-%d")
    else:
        sdate_str = qdate.toString("yyyy-MM-dd")
        sdate_dt = datetime(qdate.year(), qdate.month(), qdate.day(), 0, 0, 0)
    now = datetime.now()

    conn, cur = getdb(DB_NAME)
    try:
        sql = """
            SELECT co, order_qty_after, pre_production_qty,
                   prev_residue, pkg
            FROM ORDER_DASHBOARD
            WHERE CONVERT(DATE, sdate) = %s
        """
        df_order = runquery(cur, sql, [sdate_str])
    finally:
        closedb(conn)

    if df_order is None or df_order.empty:
        return

    df_order.columns = [c.upper() for c in df_order.columns]
    df_order["CO"] = df_order["CO"].astype(str).str.strip()

    grouped = calc_plan_kg_by_recipe(df_order, "소스")
    if grouped is None or grouped.empty:
        return

    valid_keys = {
        (str(r.BCO).strip(), str(r.BUNAME).strip())
        for r in grouped.itertuples(index=False)
    }

    conn, cur = getdb(DB_NAME)
    try:
        sql = """
            SELECT PK, uname, co
            FROM DASHBOARD_SAUCE
            WHERE CONVERT(DATE, sdate) = %s
        """
        df_exist = runquery(cur, sql, [sdate_str])
    finally:
        closedb(conn)

    exist_map = {}
    if df_exist is not None and not df_exist.empty:
        df_exist.columns = [c.upper() for c in df_exist.columns]
        for r in df_exist.itertuples(index=False):
            exist_map[(str(r.CO).strip(), str(r.UNAME).strip())] = r

    # DELETE
    delete_keys = set(exist_map.keys()) - valid_keys
    if delete_keys:
        conn, cur = getdb(DB_NAME)
        try:
            for co, uname in delete_keys:
                runquery(
                    cur,
                    """
                    DELETE FROM DASHBOARD_SAUCE
                    WHERE CO=%s AND UNAME=%s
                      AND CONVERT(DATE, sdate)=%s
                    """,
                    [co, uname, sdate_str],
                )
        finally:
            closedb(conn)

    # UPDATE / INSERT
    conn, cur = getdb(DB_NAME)
    try:
        for r in grouped.itertuples(index=False):
            bco = str(r.BCO).strip()
            buname = str(r.BUNAME).strip()
            qty_int = int(round(float(r.PLAN_KG or 0)))

            key = (bco, buname)
            exist = exist_map.get(key)

            if exist:
                sql_up = """
                    UPDATE DASHBOARD_SAUCE
                    SET order_qty_after = %s
                    WHERE PK = %s
                """
                runquery(cur, sql_up, [qty_int, exist.PK])
            else:
                stock_val = get_stock_from_pan(bco, sdate_str)
                sql_in = """
                    INSERT INTO DASHBOARD_SAUCE (
                        uname, co, sdate, created_time,
                        stock, order_qty, order_qty_after,
                        prepro_qty, ipgo_qty
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """
                runquery(
                    cur,
                    sql_in,
                    [
                        buname, bco, sdate_dt, now,
                        stock_val, qty_int, qty_int,
                        0, 0,
                    ],
                )
    finally:
        closedb(conn)



def recalc_dashboard_vege_keep_manual(qdate):
    if isinstance(qdate, str):
        sdate_str = qdate
        sdate_dt = datetime.strptime(qdate, "%Y-%m-%d")
    else:
        sdate_str = qdate.toString("yyyy-MM-dd")
        sdate_dt = datetime(qdate.year(), qdate.month(), qdate.day(), 0, 0, 0)
    now = datetime.now()

    VEGE_BCO_LIST = ["720192", "700122", "720094"]

    conn, cur = getdb(DB_NAME)
    try:
        sql = """
            SELECT co, order_qty_after, pre_production_qty,
                   prev_residue, pkg
            FROM ORDER_DASHBOARD
            WHERE CONVERT(DATE, sdate) = %s
        """
        df_order = runquery(cur, sql, [sdate_str])
    finally:
        closedb(conn)

    if df_order is None or df_order.empty:
        return

    df_order.columns = [c.upper() for c in df_order.columns]
    df_order["CO"] = df_order["CO"].astype(str).str.strip()

    co_list = df_order["CO"].unique().tolist()
    if not co_list:
        return

    # RECIPE 조회 (야채만)
    conn, cur = getdb("GFOOD_B")
    try:
        sql = f"""
            SELECT CO, BCO, BUNAME, SA
            FROM RECIPE
            WHERE BCO IN ({','.join(['%s']*len(VEGE_BCO_LIST))})
              AND CO IN ({','.join(['%s']*len(co_list))})
        """
        params = VEGE_BCO_LIST + co_list
        df_recipe = runquery(cur, sql, params)
    finally:
        closedb(conn)

    if df_recipe is None or df_recipe.empty:
        return

    df_recipe.columns = [c.upper() for c in df_recipe.columns]
    df_recipe["CO"] = df_recipe["CO"].astype(str)
    df_recipe["BCO"] = df_recipe["BCO"].astype(str)

    df = df_order.merge(df_recipe, on="CO", how="inner")
    if df.empty:
        return

    df["PLAN_KG"] = (
        df["ORDER_QTY_AFTER"].fillna(0).astype(float)
        + df["PRE_PRODUCTION_QTY"].fillna(0).astype(float)
        - df["PREV_RESIDUE"].fillna(0).astype(float)
    ) * df["PKG"].fillna(0).astype(float)

    df = df[df["PLAN_KG"] > 0]
    if df.empty:
        return

    df["VEGE_KG"] = df["PLAN_KG"] * df["SA"].fillna(0).astype(float)
    df = df[df["VEGE_KG"] > 0]
    if df.empty:
        return

    grouped = df.groupby(["BCO", "BUNAME"], as_index=False)["VEGE_KG"].sum()

    valid_keys = {(str(r["BCO"]).strip(), str(r["BUNAME"]).strip())
                  for _, r in grouped.iterrows()}

    # 기존 VEGE 조회
    conn, cur = getdb(DB_NAME)
    try:
        sql = """
            SELECT PK, uname, co
            FROM DASHBOARD_VEGE
            WHERE CONVERT(DATE, sdate) = %s
        """
        df_exist = runquery(cur, sql, [sdate_str])
    finally:
        closedb(conn)

    exist_map = {}
    if df_exist is not None and not df_exist.empty:
        df_exist.columns = [c.upper() for c in df_exist.columns]
        for r in df_exist.itertuples(index=False):
            exist_map[(str(r.CO).strip(), str(r.UNAME).strip())] = r

    # DELETE
    delete_keys = set(exist_map.keys()) - valid_keys
    if delete_keys:
        conn, cur = getdb(DB_NAME)
        try:
            for co, uname in delete_keys:
                runquery(
                    cur,
                    """
                    DELETE FROM DASHBOARD_VEGE
                    WHERE CO=%s AND UNAME=%s
                      AND CONVERT(DATE, sdate)=%s
                    """,
                    [co, uname, sdate_str],
                )
        finally:
            closedb(conn)

    # INSERT / UPDATE
    conn, cur = getdb(DB_NAME)
    try:
        for _, r in grouped.iterrows():
            bco = str(r["BCO"]).strip()
            buname = str(r["BUNAME"]).strip()
            qty_int = int(round(float(r["VEGE_KG"] or 0)))

            key = (bco, buname)
            exist = exist_map.get(key)

            if exist:
                sql = """
                    UPDATE DASHBOARD_VEGE
                    SET order_qty_after = %s
                    WHERE PK = %s
                """
                runquery(cur, sql, [qty_int, exist.PK])
            else:
                stock_val = get_stock_from_pan(bco, sdate_str)
                sql = """
                    INSERT INTO DASHBOARD_VEGE (
                        uname, co, sdate, created_time,
                        stock, order_qty, order_qty_after,
                        prepro_qty, ipgo_qty
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """
                runquery(
                    cur,
                    sql,
                    [
                        buname, bco, sdate_dt, now,
                        stock_val, qty_int, qty_int,
                        0, 0,
                    ],
                )
    finally:
        closedb(conn)

