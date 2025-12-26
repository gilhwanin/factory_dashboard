VENDOR_CHOICES = ["코스온", "코스트코", "이마트", "홈플러스", "마켓컬리"]

# DB Names
DB_NAME = "GP"

# Table Constants (if needed)
# COL_PRODUCT, COL_PLAN, COL_TODAY_RES, COL_PREV_RES are used in table_helper.py
# based on viewing table_helper.py, these were imported from config.
# I need to find where they were defined in config.py.
# Wait, I saw config.py content earlier and it only had PRODUCT_LIST and VENDOR_CHOICES.
# It seems I missed some content in config.py or they were importing from main.py?
# Let me check table_helper.py imports again.
# "from config import COL_PRODUCT, COL_PLAN, COL_TODAY_RES, COL_PREV_RES"
# But config.py only had VENDOR_CHOICES in my last view (Step 70).
# Ah, I might have overwritten config.py in Step 70 with ONLY VENDOR_CHOICES.
# If so, table_helper.py is currently broken if it runs.
# But wait, COL_PRODUCT etc are defined in main.py lines 42-50.
# The user's code might have had them in config.py originally?
# Or maybe they are NOT in config.py and the import in table_helper.py is wrong/legacy.
# Let's check if table_helper.py is actually used or if I broke it.
# I should probably defining these constants in `UTIL/const.py` and use them.

COL_VENDOR = 0
COL_PRODUCT = 1
COL_DEADLINE = 2
COL_PKG = 3
COL_ORDER = 4
COL_FINAL_ORDER = 5
COL_DIFF = 6
COL_PREV_RES = 7
COL_PRODUCTION = 8
COL_PLAN = 9
COL_PLAN_KG = 10
COL_CUR_PROD = 11
COL_SHIPMENT_TIME = 12
COL_TODAY_RES = 13
COL_TRATE = 14
COL_WORK_STATUS = 15
