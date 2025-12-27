"""
检查IWM_SPY_REL20在数据库中的存储格式
"""

import sqlite3
import pandas as pd

conn = sqlite3.connect('data/market_thermo_3years_auto.db')

# 查询IWM_SPY_REL20的最近几条数据
query = """
    SELECT 
        d.date,
        d.value_raw,
        d.value_tr,
        d.score
    FROM series_data d
    JOIN series_meta m ON d.series_id = m.id
    WHERE m.code = 'IWM_SPY_REL20'
    AND d.view = 'daily'
    ORDER BY d.date DESC
    LIMIT 10
"""

df = pd.read_sql(query, conn)
conn.close()

print("IWM_SPY_REL20 数据库存储格式:")
print("=" * 80)
print(df)
print("\n")
print("value_raw的类型和含义:")
print("-" * 80)
if not df.empty:
    v_raw = df['value_raw'].iloc[0]
    print(f"value_raw示例: {v_raw}")
    print(f"类型: {type(v_raw)}")
    print("\n说明: value_raw应该是REL20的计算结果(IWM 20日收益率 - SPY 20日收益率)")
    print("而不是IWM和SPY的原始价格")

