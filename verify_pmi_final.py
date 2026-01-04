"""
验证PMI数据修复是否成功
"""
import sqlite3
import pandas as pd

DB_PATH = "data/market_thermo_3years_auto.db"

print("=" * 80)
print("验证PMI数据修复结果")
print("=" * 80)

conn = sqlite3.connect(DB_PATH)

# 1. 检查最新数据
query = """
    SELECT date, value_raw, value_tr
    FROM series_data d
    JOIN series_meta m ON d.series_id = m.id
    WHERE m.code = 'PMI_NEWORDER_YOY_STD' 
    AND m.market = 'CN'
    AND view = 'daily'
    ORDER BY date DESC
    LIMIT 5
"""

latest = pd.read_sql(query, conn, parse_dates=['date'])

print("\n最新5条数据:")
print("-" * 80)
print(latest.to_string(index=False))

# 2. 检查月度数据
latest['year_month'] = latest['date'].dt.to_period('M')
latest_month = latest['year_month'].iloc[0]

print(f"\n最新月份: {latest_month}")

# 3. 检查转换值
latest_tr = latest['value_tr'].iloc[0]
print(f"最新转换值: {latest_tr:.4f}")

# 4. 验证结果
print("\n" + "=" * 80)
print("验证结果:")
print("=" * 80)

success = True

if latest_month == '2025-12':
    print("[OK] 最新数据是2025-12")
elif latest_month == '2026-01':
    print("[WARN] 最新数据是2026-01，说明又生成了错误数据")
    print("     请确认GUI已重启")
    success = False
else:
    print(f"[INFO] 最新数据是 {latest_month}")

if abs(latest_tr - 1.392) < 0.01:
    print("[WARN] 转换值仍是1.392，说明同比计算仍然错误")
    print("     可能原因：")
    print("     1. GUI没有重启，还在使用旧代码")
    print("     2. 数据库中仍有错误的历史数据")
    success = False
elif abs(latest_tr) < 0.5:
    print(f"[OK] 转换值是 {latest_tr:.4f}，同比计算应该是正确的")
    print("    (2025-12: 50.1 vs 2024-12: 50.1 = 0.0，标准化后接近0)")
else:
    print(f"[INFO] 转换值是 {latest_tr:.4f}")

# 5. 检查是否有2026-01数据
cursor = conn.cursor()
cursor.execute("""
    SELECT COUNT(*) as count
    FROM series_data d
    JOIN series_meta m ON d.series_id = m.id
    WHERE m.code = 'PMI_NEWORDER_YOY_STD' 
    AND m.market = 'CN'
    AND date >= '2026-01-01'
""")

count_2026 = cursor.fetchone()[0]

if count_2026 > 0:
    print(f"\n[WARN] 发现 {count_2026} 条2026-01的数据")
    print("     GUI获取时又生成了错误数据")
    print("     请确认：")
    print("     1. GUI是否已重启？")
    print("     2. core/datasource.py的修改是否已保存？")
    success = False
else:
    print("\n[OK] 没有2026-01的数据")

conn.close()

print("\n" + "=" * 80)
if success:
    print("修复成功！✓")
    print("\n现在PMI数据应该:")
    print("  - 最新到2025-12")
    print("  - 同比使用2024-12对比")
    print("  - 转换值正确")
else:
    print("修复尚未完全成功")
    print("\n请执行以下步骤:")
    print("  1. 确认GUI已关闭")
    print("  2. 运行: python clean_all_pmi_errors.py")
    print("  3. 重启GUI: python app.py")
    print("  4. 在GUI中重新获取数据")
    print("  5. 再次验证: python verify_pmi_final.py")
print("=" * 80)

