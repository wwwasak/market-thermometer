"""
直接检查数据库IWM_SPY_REL20的最新记录
"""

import sqlite3
import pandas as pd

conn = sqlite3.connect('data/market_thermo_3years_auto.db')

query = """
    SELECT date, value_raw, value_tr
    FROM series_data 
    WHERE series_id=(SELECT id FROM series_meta WHERE code='IWM_SPY_REL20')
    AND view='daily'
    ORDER BY date DESC
    LIMIT 10
"""

df = pd.read_sql(query, conn)
print("IWM_SPY_REL20 最近10条记录:")
print("=" * 60)
print(df)

print("\n最新记录详情:")
print("-" * 60)
latest = df.iloc[0]
print(f"日期: {latest['date']}")
print(f"value_raw: {latest['value_raw']}")
print(f"value_tr: {latest['value_tr']}")

conn.close()

