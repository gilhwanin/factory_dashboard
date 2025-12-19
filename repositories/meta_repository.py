from UTIL.db_handler import getdb, runquery, closedb

class MetaRepository:
    def __init__(self):
        # 마스터/레시피 등은 GFOOD_B, ID/Map 등은 GP 사용
        pass

    def _execute(self, db_name, sql, params=None):
        conn, cur = getdb(db_name)
        try:
            return runquery(cur, sql, params)
        finally:
            closedb(conn)

    def get_user_by_password(self, password):
        sql = "SELECT name, level FROM DASHBOARD_ID WHERE pw = %s"
        df = self._execute("GP", sql, [password])
        return df

    def get_uname_mapping(self):
        sql = "SELECT before_value, after_value FROM Dashboard_UNAME_MAP"
        return self._execute("GP", sql)

    def get_master_info(self, co):
        sql = "SELECT TOP 1 CO, UNAME, PACKG, PACSU FROM MASTER WHERE CO = %s"
        return self._execute("GFOOD_B", sql, [co])

    def get_recipe_by_bco_list(self, vege_bco_list, co_list):
        if not vege_bco_list or not co_list:
            return None
            
        sql = f"""
            SELECT CO, BCO, BUNAME, SA
            FROM RECIPE
            WHERE BCO IN ({','.join(['%s'] * len(vege_bco_list))})
              AND CO IN ({','.join(['%s'] * len(co_list))})
        """
        params = vege_bco_list + co_list
        return self._execute("GFOOD_B", sql, params)
