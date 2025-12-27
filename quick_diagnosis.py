"""
快速诊断：检查GUI获取后的实际状态
"""

import sqlite3
import pandas as pd
from datetime import datetime

def check_current_state():
    print("=" * 80)
    print("GUI获取后的实际状态检查")
    print("=" * 80)
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    conn = sqlite3.connect('data/market_thermo_3years_auto.db')
    
    # 检查所有US主要指标的最新数据
    query = """
        SELECT 
            s.code,
            s.name,
            MAX(d.date) as latest_date,
            COUNT(CASE WHEN d.date = '2025-12-26' THEN 1 END) as has_dec26,
            COUNT(CASE WHEN d.date = '2025-12-26' AND d.value_tr IS NOT NULL THEN 1 END) as dec26_has_tr,
            COUNT(CASE WHEN d.date = '2025-12-26' AND d.score IS NOT NULL THEN 1 END) as dec26_has_score
        FROM series_meta s
        LEFT JOIN series_data d ON s.id = d.series_id AND d.view = 'daily'
        WHERE s.market = 'US'
        AND s.role = 'main'
        GROUP BY s.code, s.name
        ORDER BY s.code
    """
    
    df = pd.read_sql(query, conn)
    
    print("所有US主要指标状态:")
    print("-" * 80)
    print(f"{'指标':<25} {'最新日期':<12} {'有12-26':<8} {'有tr':<6} {'有score':<8}")
    print("-" * 80)
    
    for _, row in df.iterrows():
        code = row['code']
        latest = row['latest_date'] or 'N/A'
        has_26 = 'YES' if row['has_dec26'] > 0 else 'NO'
        has_tr = 'YES' if row['dec26_has_tr'] > 0 else 'NO' if row['has_dec26'] > 0 else 'N/A'
        has_score = 'YES' if row['dec26_has_score'] > 0 else 'NO' if row['has_dec26'] > 0 else 'N/A'
        
        print(f"{code:<25} {latest:<12} {has_26:<8} {has_tr:<6} {has_score:<8}")
    
    # 详细检查IWM_SPY_REL20
    print("\n" + "=" * 80)
    print("IWM_SPY_REL20 详细数据（最近5天）")
    print("=" * 80)
    
    iwm_query = """
        SELECT 
            d.date,
            d.value_raw,
            d.value_tr,
            d.z,
            d.score
        FROM series_data d
        JOIN series_meta m ON d.series_id = m.id
        WHERE m.code = 'IWM_SPY_REL20'
        AND d.view = 'daily'
        ORDER BY d.date DESC
        LIMIT 5
    """
    
    iwm_df = pd.read_sql(iwm_query, conn)
    
    if not iwm_df.empty:
        print("\n日期          value_raw    value_tr     z            score")
        print("-" * 80)
        for _, row in iwm_df.iterrows():
            date = row['date']
            v_raw = f"{row['value_raw']:.6f}" if pd.notna(row['value_raw']) else "None"
            v_tr = f"{row['value_tr']:.6f}" if pd.notna(row['value_tr']) else "None"
            z = f"{row['z']:.6f}" if pd.notna(row['z']) else "None"
            score = f"{row['score']:.2f}" if pd.notna(row['score']) else "None"
            print(f"{date:<12} {v_raw:<12} {v_tr:<12} {z:<12} {score}")
    else:
        print("[ERROR] 没有找到IWM_SPY_REL20数据")
    
    # 检查VIX_LOG
    print("\n" + "=" * 80)
    print("VIX_LOG 详细数据（最近5天）")
    print("=" * 80)
    
    vix_query = """
        SELECT 
            d.date,
            d.value_raw,
            d.value_tr,
            d.z,
            d.score
        FROM series_data d
        JOIN series_meta m ON d.series_id = m.id
        WHERE m.code = 'VIX_LOG'
        AND d.view = 'daily'
        ORDER BY d.date DESC
        LIMIT 5
    """
    
    vix_df = pd.read_sql(vix_query, conn)
    
    if not vix_df.empty:
        print("\n日期          value_raw    value_tr     z            score")
        print("-" * 80)
        for _, row in vix_df.iterrows():
            date = row['date']
            v_raw = f"{row['value_raw']:.6f}" if pd.notna(row['value_raw']) else "None"
            v_tr = f"{row['value_tr']:.6f}" if pd.notna(row['value_tr']) else "None"
            z = f"{row['z']:.6f}" if pd.notna(row['z']) else "None"
            score = f"{row['score']:.2f}" if pd.notna(row['score']) else "None"
            print(f"{date:<12} {v_raw:<12} {v_tr:<12} {z:<12} {score}")
    else:
        print("[ERROR] 没有找到VIX_LOG数据")
    
    # 检查最近的fetch_log
    print("\n" + "=" * 80)
    print("最近的获取日志")
    print("=" * 80)
    
    log_query = """
        SELECT 
            timestamp,
            action,
            status,
            message
        FROM fetch_log
        ORDER BY timestamp DESC
        LIMIT 5
    """
    
    log_df = pd.read_sql(log_query, conn)
    
    if not log_df.empty:
        for _, row in log_df.iterrows():
            print(f"\n[{row['timestamp']}] {row['action']}")
            print(f"  Status: {row['status']}")
            print(f"  Message: {row['message']}")
    else:
        print("没有找到获取日志")
    
    conn.close()
    
    print("\n" + "=" * 80)
    print("诊断总结")
    print("=" * 80)
    print("\n请查看上面的数据，确认：")
    print("1. IWM_SPY_REL20是否有12月26日的记录")
    print("2. 如果有记录，value_tr和score是否为None")
    print("3. VIX_LOG的状态如何")
    print("4. 最近的fetch_log显示什么")


if __name__ == "__main__":
    check_current_state()

