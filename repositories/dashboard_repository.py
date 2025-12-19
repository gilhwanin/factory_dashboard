from datetime import datetime
from UTIL.db_handler import getdb, runquery, closedb
from config import DB_NAME

class DashboardRepository:
    def __init__(self):
        self.db_name = DB_NAME

    def _execute(self, sql, params=None):
        conn, cur = getdb(self.db_name)
        try:
            return runquery(cur, sql, params)
        finally:
            closedb(conn)
            
    def _execute_with_conn(self, conn, cur, sql, params=None):
        return runquery(cur, sql, params)

    def get_order_dashboard(self, sdate_str):
        sql = """
            SELECT
                PK, rname, uname, pkg,
                order_qty, order_qty_after,
                prev_residue, production_plan, produced_qty,
                today_residue, work_status, hide
            FROM ORDER_DASHBOARD
            WHERE CONVERT(DATE, sdate) = %s
            ORDER BY rname, uname, PK
        """
        return self._execute(sql, [sdate_str])

    def get_dashboard_raw(self, sdate_str):
        sql = """
            SELECT
                PK, uname, co, stock,
                order_qty, order_qty_after,
                prepro_qty, ipgo_qty
            FROM DASHBOARD_RAW
            WHERE CONVERT(DATE, sdate) = %s
            ORDER BY uname, co, PK
        """
        return self._execute(sql, [sdate_str])

    def get_dashboard_sauce(self, sdate_str):
        sql = """
            SELECT
                PK, uname, co, stock,
                order_qty, order_qty_after,
                prepro_qty, ipgo_qty
            FROM DASHBOARD_SAUCE
            WHERE CONVERT(DATE, sdate) = %s
            ORDER BY uname, co, PK
        """
        return self._execute(sql, [sdate_str])

    def get_dashboard_vege(self, sdate_str):
        sql = """
            SELECT
                PK, uname, co, stock,
                order_qty, order_qty_after,
                prepro_qty, ipgo_qty
            FROM DASHBOARD_VEGE
            WHERE CONVERT(DATE, sdate) = %s
            ORDER BY uname, co, PK
        """
        return self._execute(sql, [sdate_str])

    def update_order_dashboard_field(self, pk, field, value):
        valid_fields = ["production_plan", "today_residue", "prev_residue", "order_qty_after", "work_status", "produced_qty", "hide"]
        if field not in valid_fields:
            raise ValueError(f"Invalid field: {field}")
        
        sql = f"UPDATE ORDER_DASHBOARD SET {field} = %s WHERE PK = %s"
        return self._execute(sql, [value, pk])

    def update_sub_dashboard_field(self, table_name, pk, stock, prepro, ipgo):
        if table_name not in ["DASHBOARD_RAW", "DASHBOARD_SAUCE", "DASHBOARD_VEGE"]:
             raise ValueError(f"Invalid table: {table_name}")
             
        sql = f"""
            UPDATE {table_name}
            SET stock = %s, prepro_qty = %s, ipgo_qty = %s
            WHERE PK = %s
        """
        return self._execute(sql, [stock, prepro, ipgo, pk])

    def delete_all_dashboard_data(self, sdate_str):
        sqls = [
            "DELETE FROM ORDER_DASHBOARD WHERE CONVERT(DATE, sdate) = %s",
            "DELETE FROM DASHBOARD_RAW     WHERE CONVERT(DATE, sdate) = %s",
            "DELETE FROM DASHBOARD_SAUCE   WHERE CONVERT(DATE, sdate) = %s",
            "DELETE FROM DASHBOARD_VEGE    WHERE CONVERT(DATE, sdate) = %s"
        ]
        
        conn, cur = getdb(self.db_name)
        try:
            for sql in sqls:
                runquery(cur, sql, [sdate_str])
        finally:
            closedb(conn)

    def delete_order_dashboard_rows(self, sdate_str, uname_list):
        if not uname_list:
            return
        placeholders = ", ".join(["%s"] * len(uname_list))
        sql = f"""
            DELETE FROM ORDER_DASHBOARD
            WHERE CONVERT(DATE, sdate) = %s
              AND UNAME IN ({placeholders})
        """
        params = [sdate_str] + uname_list
        return self._execute(sql, params)

    def insert_order_dashboard(self, rows):
        if not rows: return
        sql = """
            INSERT INTO ORDER_DASHBOARD (
                bigo, sdate, created_time, id,
                rname, uname, co, pkg,
                order_qty, order_qty_after, prev_residue, production_plan,
                produced_qty, today_residue
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        conn, cur = getdb(self.db_name)
        try:
            for r in rows:
                params = [
                    r["bigo"], r["sdate"], r["created_time"], r["id"],
                    r["rname"], r["uname"], r["co"], r["pkg"],
                    r["order_qty"], r["order_qty_after"], r["prev_residue"],
                    r["production_plan"], r["produced_qty"], r["today_residue"],
                ]
                runquery(cur, sql, params)
        finally:
            closedb(conn)

