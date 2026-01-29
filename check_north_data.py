import sqlite3
import pandas as pd

# 检查数据库中的NORTH_TURNOVER_SHARE数据
conn = sqlite3.connect('data/market_thermo_3years_auto.db')

# 先检查所有表
print("=" * 60)
print("数据库中的所有表:")
print("=" * 60)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
for table in tables:
    print(f"  - {table[0]}")

# 检查series_data表结构
print("\n" + "=" * 60)
print("series_data表结构:")
print("=" * 60)
cursor.execute("PRAGMA table_info(series_data)")
columns = cursor.fetchall()
for col in columns:
    print(f"  {col[1]}: {col[2]}")

# 检查series_meta表结构
print("\n" + "=" * 60)
print("series_meta表结构:")
print("=" * 60)
cursor.execute("PRAGMA table_info(series_meta)")
meta_columns = cursor.fetchall()
for col in meta_columns:
    print(f"  {col[1]}: {col[2]}")

# 检查series_meta表看看有哪些series
print("\n" + "=" * 60)
print("所有CN市场的series:")
print("=" * 60)
cursor.execute("SELECT * FROM series_meta WHERE market='CN'")
series_list = cursor.fetchall()
for s in series_list:
    print(f"  {s}")

# 找到NORTH_TURNOVER_SHARE的series_id
print("\n" + "=" * 60)
print("查找NORTH_TURNOVER_SHARE:")
print("=" * 60)
cursor.execute("SELECT * FROM series_meta WHERE code LIKE '%NORTH%TURNOVER%'")
north_series = cursor.fetchall()
if north_series:
    for s in north_series:
        print(f"  Found: {s}")
else:
    print("  未找到相关series")
    
# NORTH_TURNOVER_SHARE的series_id是3
print("\n" + "=" * 60)
print("NORTH_TURNOVER_SHARE 最近30条 series_data (series_id=3):")
print("=" * 60)
df_raw = pd.read_sql('SELECT * FROM series_data WHERE series_id=3 ORDER BY date DESC LIMIT 30', conn)
print(df_raw.to_string())

# 检查有多少条数据值为0或接近0
print("\n" + "=" * 60)
print("NORTH_TURNOVER_SHARE value_raw=0的记录统计:")
print("=" * 60)
df_zero = pd.read_sql('SELECT COUNT(*) as count, MIN(date) as first_zero, MAX(date) as last_zero FROM series_data WHERE series_id=3 AND value_raw=0', conn)
print(df_zero.to_string())

# 检查最近一个月的数据
print("\n" + "=" * 60)
print("NORTH_TURNOVER_SHARE 2025年1月的数据:")
print("=" * 60)
df_jan = pd.read_sql('SELECT date, value_raw, value_tr FROM series_data WHERE series_id=3 AND date >= "2025-01-01" ORDER BY date DESC', conn)
print(df_jan.to_string())

# 检查2024年12月的数据（对比）
print("\n" + "=" * 60)
print("NORTH_TURNOVER_SHARE 2024年12月的数据（对比）:")
print("=" * 60)
df_dec = pd.read_sql('SELECT date, value_raw, value_tr FROM series_data WHERE series_id=3 AND date >= "2024-12-01" AND date < "2025-01-01" ORDER BY date DESC', conn)
print(df_dec.to_string())

# 查看最近何时有非0值
print("\n" + "=" * 60)
print("NORTH_TURNOVER_SHARE 最后一个非0值:")
print("=" * 60)
df_last_nonzero = pd.read_sql('SELECT date, value_raw, value_tr FROM series_data WHERE series_id=3 AND value_raw > 0 ORDER BY date DESC LIMIT 5', conn)
print(df_last_nonzero.to_string())

conn.close()
