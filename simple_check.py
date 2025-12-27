"""
简化测试：直接检查保存逻辑

重点检查transformed数据的索引是否包含12月26日
"""

import sqlite3
import pandas as pd
from datetime import datetime

# 检查1: yfinance现在能获取到什么
print("=" * 80)
print("检查1: yfinance当前数据")
print("=" * 80)

import yfinance as yf
end = datetime.now()
start = datetime(2025, 12, 20)

iwm = yf.download("IWM", start=start, end=end, progress=False)
spy = yf.download("SPY", start=start, end=end, progress=False)

print(f"\nIWM: {len(iwm)} 条, 最新: {iwm.index[-1].strftime('%Y-%m-%d')}")
print(f"SPY: {len(spy)} 条, 最新: {spy.index[-1].strftime('%Y-%m-%d')}")

has_dec26 = pd.Timestamp('2025-12-26') in iwm.index and pd.Timestamp('2025-12-26') in spy.index
print(f"\nyfinance有12月26日数据: {has_dec26}")

# 检查2: 数据库中的情况
print("\n" + "=" * 80)
print("检查2: 数据库中IWM_SPY_REL20的情况")
print("=" * 80)

conn = sqlite3.connect('data/market_thermo_3years_auto.db')

query = """
    SELECT date, value_raw, value_tr
    FROM series_data 
    WHERE series_id=(SELECT id FROM series_meta WHERE code='IWM_SPY_REL20')
    AND view='daily'
    AND date >= '2025-12-20'
    ORDER BY date DESC
"""

df = pd.read_sql(query, conn)
print(f"\n数据库中12月20日之后的记录:")
print(df)

if not df.empty:
    has_dec26_in_db = '2025-12-26' in df['date'].values
    print(f"\n数据库有12月26日记录: {has_dec26_in_db}")
    
    if has_dec26_in_db:
        dec26_row = df[df['date'] == '2025-12-26'].iloc[0]
        is_nan = pd.isna(dec26_row['value_raw'])
        print(f"12月26日value_raw是NaN: {is_nan}")

# 检查3: fetch_log
print("\n" + "=" * 80)
print("检查3: 最近的获取日志")
print("=" * 80)

log_query = """
    SELECT timestamp, action, message
    FROM fetch_log
    WHERE action IN ('fetch_all', 'save_raw_data')
    ORDER BY timestamp DESC
    LIMIT 5
"""

log_df = pd.read_sql(log_query, conn)
print("\n最近的日志:")
for _, row in log_df.iterrows():
    print(f"[{row['timestamp']}] {row['action']}: {row['message']}")

conn.close()

print("\n" + "=" * 80)
print("结论")
print("=" * 80)

if has_dec26:
    print("\n✓ yfinance有12月26日数据")
    
    if has_dec26_in_db:
        if is_nan:
            print("✗ 数据库有12月26日记录，但value_raw是NaN")
            print("\n问题: 保存逻辑有问题！")
            print("  - 可能是raw_series的索引对不上")
            print("  - 或者trans_series在保存时索引不对")
        else:
            print("✓ 数据库12月26日数据正常")
    else:
        print("✗ 数据库没有12月26日记录")
        print("\n问题: 获取或保存阶段跳过了12月26日")
else:
    print("\n✗ yfinance没有12月26日数据")
    print("  需要等待数据源更新")

