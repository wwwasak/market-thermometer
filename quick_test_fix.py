"""
快速测试：删除12月26日数据并重新获取
"""

import sqlite3
from datetime import datetime

def quick_test():
    print("=" * 80)
    print("快速测试：删除并重新获取12月26日数据")
    print("=" * 80)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    db_path = 'data/market_thermo_3years_auto.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 删除12月26日的US数据
    print("步骤1: 删除12月26日的US数据...")
    cursor.execute("""
        DELETE FROM series_data
        WHERE series_id IN (
            SELECT id FROM series_meta WHERE market = 'US'
        )
        AND date = '2025-12-26'
        AND view = 'daily'
    """)
    
    deleted = cursor.rowcount
    conn.commit()
    print(f"[OK] 删除了 {deleted} 条记录\n")
    
    conn.close()
    
    print("=" * 80)
    print("现在请执行以下操作:")
    print("=" * 80)
    print("\n1. 打开 app.py (python app.py)")
    print("2. 选择 US 市场")
    print("3. 点击'手动获取最新数据'")
    print("4. 观察控制台输出，确认看到：")
    print("   - IWM_SPY_REL20: 新数据计算得到XX个relret20值")
    print("   - 增量模式（多ticker），使用计算的XX个新值")
    print("\n5. 获取完成后，运行: python quick_diagnosis.py")
    print("   检查IWM_SPY_REL20是否有12月26日的数据")
    print("\n6. 如果有数据，点击'计算评分'")
    print("\n7. 查看图表和评分表")
    
    print("\n" + "=" * 80)
    print("提示：如果还是没有12月26日数据，可能是yfinance本身没有")
    print("      可以运行: python check_iwm_spy_extended.py 验证yfinance")
    print("=" * 80)


if __name__ == "__main__":
    quick_test()

