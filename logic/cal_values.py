# dashboard_helpers.py
# -----------------------------------------------------
# OrderDashboardWidget 에서 #7. DB 조회/계산 헬퍼 함수 분리 버전
# -----------------------------------------------------

from datetime import datetime

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

import pandas as pd
from datetime import datetime, timedelta
from UTIL.db_handler import getdb, runquery, closedb


# ------------------------------
# 매핑 테이블
# ------------------------------
COSTCO_META = {
    "501998": {"type": "일반", "pack_weight": 0,   "day_adj": 1, "mon_adj": -1, "sun_prod": False},
    "520033": {"type": "일반", "pack_weight": 0,   "day_adj": 1, "mon_adj": -1, "sun_prod": False},
    "520427": {"type": "자율", "pack_weight": 2.6, "day_adj": 1, "mon_adj": 0,  "sun_prod": True},
    "520261": {"type": "자율", "pack_weight": 2.3, "day_adj": 0, "mon_adj": 0,  "sun_prod": True},
    "520513": {"type": "자율", "pack_weight": 2.3, "day_adj": 0, "mon_adj": 0,  "sun_prod": True},
}


def get_costco_order_qty(base_co: str, sdate_str: str) -> int:
    """
    Costco 발주량 계산 (DEBUG 버전)
    """

    print("\n==========[COSTCO DEBUG START]============")
    print(f"[INPUT] base_co = {base_co}, sdate_str = {sdate_str}")

    meta = COSTCO_META.get(base_co)
    print(f"[META] {meta}")

    if meta is None:
        print("[STOP] meta 없음 → 0 리턴")
        return 0

    # ------------------------------
    # 날짜 계산
    # ------------------------------
    sdate = datetime.strptime(sdate_str, "%Y-%m-%d")
    print(f"[DATE] 원본 입고일 = {sdate}")

    # 1) 기본 입고일 보정
    target_date = sdate + timedelta(days=meta["day_adj"])
    print(f"[DATE] 기본 보정(+{meta['day_adj']}) = {target_date}")

    # 2) 월요일 보정
    if target_date.weekday() == 0:  # Monday
        print(f"[DATE] 월요일 감지 → 월요일보정({meta['mon_adj']}) 적용")
        target_date += timedelta(days=meta["mon_adj"])

    print(f"[DATE] 최종 보정 날짜 = {target_date} (weekday={target_date.weekday()})")

    # 3) 일요일 생산 불가 처리
    if target_date.weekday() == 6:  # Sunday
        print("[DATE] 최종 조회일이 일요일임")
        if not meta["sun_prod"]:
            print("[STOP] 일요일 생산 불가 상품 → 발주량 = 0")
            return 0
        else:
            print("[INFO] 일요일 생산 허용 → 계속 진행")

    target_date_str = target_date.strftime("%Y-%m-%d")
    print(f"[DATE] 최종 조회일 문자열 = {target_date_str}")

    # ------------------------------
    # COS_B 조회
    # ------------------------------
    print("\n[DB] COS_B 조회 SQL 실행")
    conn, cur = getdb("GWCHUL")

    try:
        sql = """
            SELECT ISNULL(SUM(CONVERT(int, C17)), 0) AS sum_pack
            FROM COS_B
            WHERE REPLACE(RTRIM(LTRIM(C29)), ' ', '') = %s
              AND CONVERT(DATE, C06) = %s
        """
        print(f"[DB] SQL param = base_co={base_co}, C06={target_date_str}")
        df = runquery(cur, sql, [base_co, target_date_str])

    finally:
        closedb(conn)

    if df is None or df.empty:
        print("[DB] 조회 결과 없음(df empty) → 0")
        return 0

    total_pack = int(df.iloc[0, 0] or 0)
    print(f"[DB RESULT] sum_pack(raw) = {total_pack}")

    # ------------------------------
    # 자율 유형 처리
    # ------------------------------
    if meta["type"] == "자율":
        pw = meta["pack_weight"]
        print(f"[TYPE] 자율 유형. 팩중량 = {pw}")
        if pw > 0:
            final_qty = int(total_pack / pw)
            print(f"[CALC] total_pack / {pw} = {final_qty}")
            print("==========[COSTCO DEBUG END]============\n")
            return final_qty
        else:
            print("[ERROR] pack_weight = 0 이므로 나누기 불가 → original pack 사용")

    # ------------------------------
    # 일반 유형
    # ------------------------------
    print(f"[TYPE] 일반 유형. 발주량 = {total_pack}")
    print("==========[COSTCO DEBUG END]============\n")
    return total_pack




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
        box_sum = int(df.iloc[0, 0] or 0)
    except:
        box_sum = 0

    return box_sum * (pacsu if pacsu > 0 else 1)


# -----------------------------------------------------
# prev_residue 조회
# -----------------------------------------------------
def get_prev_residue_from_today(co: str) -> int:
    conn, cur = getdb("GP")
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
        return int(df.iloc[0, 0] or 0)
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
# 레시피 기반 PLAN_KG 계산 (PRODUCTION_PLAN 사용)
# -----------------------------------------------------
def calc_plan_kg_by_recipe(df_order, recipe_keyword: str, bco_list: list = None):
    """
    ORDER_DASHBOARD 기반 원료/소스용 PLAN_KG 계산
    PLAN_PACKS = PRODUCTION_PLAN

    bco_list: BCO가 이 리스트에 포함되면 OR 조건으로 RECIPE에서 조회됨
              (예: 원료/소스 외에 야채 등 별도 BCO 강제 포함)
    """

    if df_order is None or df_order.empty:
        print("[PLAN_KG] df_order is empty → return None")
        return None

    df_order = df_order.copy()
    df_order.columns = [c.upper() for c in df_order.columns]
    df_order["CO"] = df_order["CO"].astype(str).str.strip()

    print(f"[PLAN_KG] df_order rows = {len(df_order)}")
    print(f"[PLAN_KG] recipe_keyword = {recipe_keyword}")
    print(f"[PLAN_KG] bco_list = {bco_list}")

    co_list = df_order["CO"].unique().tolist()
    if not co_list:
        print("[PLAN_KG] no CO list → return None")
        return None

    placeholders = ",".join(["%s"] * len(co_list))

    # -----------------------------------------------------
    # 1) RECIPE 조회 조건 동적 구성
    # -----------------------------------------------------
    where_clause = f"BUNAME LIKE %s"

    params = co_list + [f"%{recipe_keyword}%"]

    # BCO 리스트 조건 추가
    if bco_list:
        bco_placeholders = ",".join(["%s"] * len(bco_list))
        where_clause = f"({where_clause} OR BCO IN ({bco_placeholders}))"
        params.extend(bco_list)

    # -----------------------------------------------------
    # 최종 SQL 구성
    # -----------------------------------------------------
    sql = f"""
        SELECT CO, BCO, BUNAME, SA
        FROM RECIPE
        WHERE CO IN ({placeholders})
          AND {where_clause}
    """

    conn, cur = getdb("GFOOD_B")
    try:
        df_recipe = runquery(cur, sql, params)
    finally:
        closedb(conn)

    print("[PLAN_KG] SQL params =", params)

    if df_recipe is None or df_recipe.empty:
        print("[PLAN_KG] df_recipe is empty → return None")
        return None

    df_recipe.columns = [c.upper() for c in df_recipe.columns]
    df_recipe["CO"] = df_recipe["CO"].astype(str).str.strip()
    df_recipe["BCO"] = df_recipe["BCO"].astype(str).str.strip()
    df_recipe["SA"] = df_recipe["SA"].fillna(1).astype(float)

    print(f"[PLAN_KG] RECIPE rows = {len(df_recipe)}")

    # -----------------------------------------------------
    # 2) MERGE
    # -----------------------------------------------------
    df = df_order.merge(df_recipe, on="CO", how="inner")
    if df.empty:
        print("[PLAN_KG] merge result empty → return None")
        return None

    print(f"[PLAN_KG] merged rows = {len(df)}")

    # -----------------------------------------------------
    # 3) PLAN_PACKS = PRODUCTION_PLAN
    # -----------------------------------------------------
    if "PRODUCTION_PLAN" not in df.columns:
        df["PRODUCTION_PLAN"] = 0

    df["PRODUCTION_PLAN"] = df["PRODUCTION_PLAN"].fillna(0).astype(float)
    df["PKG"] = df["PKG"].fillna(0).astype(float)

    df["PLAN_PACKS"] = df["PRODUCTION_PLAN"]

    print("[PLAN_KG] PLAN_PACKS sample:", df["PLAN_PACKS"].head().tolist())

    # -----------------------------------------------------
    # 4) PLAN_KG 계산
    # -----------------------------------------------------
    df["PLAN_KG"] = df["PLAN_PACKS"] * df["PKG"] * df["SA"] / 100

    print("[PLAN_KG] PLAN_KG sample:", df["PLAN_KG"].head().tolist())

    df = df[df["PLAN_KG"] > 0]
    if df.empty:
        print("[PLAN_KG] PLAN_KG <= 0 for all rows → return None")
        return None

    # -----------------------------------------------------
    # 5) groupby
    # -----------------------------------------------------
    grouped = df.groupby(["BCO", "BUNAME"], as_index=False)["PLAN_KG"].sum()

    print(f"[PLAN_KG] grouped rows = {len(grouped)}")
    print("[PLAN_KG] grouped sample:")
    print(grouped.head())

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

    if vendor == "코스트코":
        return get_costco_order_qty(base_co, sdate_str)

    return 0


# -----------------------------------------------------
# RAW 재계산 (PRODUCTION_PLAN 사용)
# -----------------------------------------------------
def recalc_dashboard_raw_keep_manual(qdate):
    if isinstance(qdate, str):
        sdate_str = qdate
        sdate_dt = datetime.strptime(qdate, "%Y-%m-%d")
    else:
        sdate_str = qdate.toString("yyyy-MM-dd")
        sdate_dt = datetime(qdate.year(), qdate.month(), qdate.day(), 0, 0, 0)
    now = datetime.now()

    # ORDER_DASHBOARD 조회 (pre_production_qty → production_plan)
    conn, cur = getdb(DB_NAME)
    try:
        sql = """
            SELECT co, order_qty_after, production_plan, prev_residue, pkg
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


# -----------------------------------------------------
# SAUCE 재계산 (PRODUCTION_PLAN 사용)
# -----------------------------------------------------
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
            SELECT co, order_qty_after, production_plan,
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


# -----------------------------------------------------
# VEGE 재계산 (PRODUCTION_PLAN 사용)
# -----------------------------------------------------
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
            SELECT co, order_qty_after, production_plan,
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

    # PRE_PRODUCTION_QTY 대신 PRODUCTION_PLAN 사용
    for col in ("PRODUCTION_PLAN", "PKG"):
        if col not in df.columns:
            df[col] = 0

    df["PRODUCTION_PLAN"] = df["PRODUCTION_PLAN"].fillna(0).astype(float)
    df["PKG"] = df["PKG"].fillna(0).astype(float)

    # PLAN_KG = PRODUCTION_PLAN * PKG
    df["PLAN_KG"] = df["PRODUCTION_PLAN"] * df["PKG"]

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
