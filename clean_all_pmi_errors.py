"""
清理所有PMI错误数据（包括12月和1月）
"""
import sqlite3

DB_PATH = "data/market_thermo_3years_auto.db"

print("=" * 80)
print("清理所有PMI错误数据")
print("=" * 80)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 删除2025-12和2026-01的所有数据
print("\n删除2025-12和2026-01的PMI数据...")

cursor.execute("""
    DELETE FROM series_data
    WHERE series_id = (
        SELECT id FROM series_meta 
        WHERE code = 'PMI_NEWORDER_YOY_STD' AND market = 'CN'
    )
    AND date >= '2025-12-01'
""")

deleted = cursor.rowcount
conn.commit()

print(f"[SUCCESS] 已删除 {deleted} 条数据")

# 验证
cursor.execute("""
    SELECT MAX(date) as max_date
    FROM series_data d
    JOIN series_meta m ON d.series_id = m.id
    WHERE m.code = 'PMI_NEWORDER_YOY_STD' 
    AND m.market = 'CN'
""")

max_date = cursor.fetchone()[0]
print(f"\n最新数据日期: {max_date}")

if max_date and max_date < '2025-12-01':
    print("[OK] 错误数据已清理")
else:
    print("[WARN] 仍有12月或1月的数据")

conn.close()

print("\n" + "=" * 80)
print("下一步:")
print("=" * 80)
print("1. 关闭GUI（如果正在运行）")
print("2. 重启GUI: python app.py")
print("3. 在GUI中点击'手动获取最新数据'")
print("4. 验证: python verify_pmi_final.py")
print("=" * 80)

