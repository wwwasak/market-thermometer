"""
修复12月26日的数据问题

步骤：
1. 删除12月26日所有指标的错误数据
2. 提供重新获取的指引
"""

import sqlite3
from datetime import date, datetime

def main():
    print("=" * 80)
    print("修复12月26日数据")
    print("=" * 80)
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    db_path = 'data/market_thermo_3years_auto.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 查看12月26日有多少条记录
        cursor.execute("""
            SELECT COUNT(*) FROM series_data
            WHERE date = '2025-12-26'
        """)
        count_before = cursor.fetchone()[0]
        
        print(f"删除前：12月26日共有 {count_before} 条记录")
        
        if count_before == 0:
            print("\n[INFO] 12月26日没有数据，无需删除")
            conn.close()
            return
        
        # 显示将要删除的数据
        cursor.execute("""
            SELECT s.code, s.market, d.value_raw, d.value_tr, d.score
            FROM series_data d
            JOIN series_meta s ON d.series_id = s.id
            WHERE d.date = '2025-12-26'
            ORDER BY s.market, s.code
        """)
        
        records = cursor.fetchall()
        print(f"\n将要删除的记录:")
        print("-" * 80)
        for code, market, value_raw, value_tr, score in records:
            v_raw = f"{value_raw:.6f}" if value_raw is not None else "NaN"
            v_tr = f"{value_tr:.6f}" if value_tr is not None else "NaN"
            sc = f"{score:.2f}" if score is not None else "NaN"
            print(f"{market} | {code:<30} | raw:{v_raw} | tr:{v_tr} | score:{sc}")
        
        # 确认删除
        print("\n" + "=" * 80)
        response = input("确认删除这些记录？(y/n): ")
        
        if response.lower() != 'y':
            print("已取消")
            conn.close()
            return
        
        # 执行删除
        cursor.execute("""
            DELETE FROM series_data
            WHERE date = '2025-12-26'
            AND view = 'daily'
        """)
        
        deleted = cursor.rowcount
        conn.commit()
        
        print(f"\n[OK] 已删除 {deleted} 条记录")
        
        # 验证删除
        cursor.execute("""
            SELECT COUNT(*) FROM series_data
            WHERE date = '2025-12-26'
        """)
        count_after = cursor.fetchone()[0]
        
        print(f"删除后：12月26日剩余 {count_after} 条记录")
        
        conn.close()
        
        # 提供后续操作指引
        print("\n" + "=" * 80)
        print("删除成功！接下来请执行:")
        print("=" * 80)
        print("\n1. 启动GUI:")
        print("   python app.py")
        print("\n2. 点击'手动获取最新数据'按钮")
        print("   → 会重新获取12月26日及之前的数据")
        print("   → 使用增量模式，自动补充历史数据")
        print("   → 应该能正确计算value_tr")
        print("\n3. 点击'计算评分'按钮")
        print("   → 重新计算所有指标的z-score和score")
        print("   → 也会计算观察者指标（HY_OAS_JUMP, VIX_EXTREME等）")
        print("\n4. 验证结果:")
        print("   python diagnose_current_state.py")
        print("   → 检查12月26日的value_tr是否有值")
        print("   → 检查观察者指标是否有评分")
        
    except Exception as e:
        print(f"\n[ERROR] 操作失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

