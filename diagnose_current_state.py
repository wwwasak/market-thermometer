"""
诊断当前数据库状态

检查：
1. IWM_SPY_REL20的最新数据
2. US市场各指标的评分情况
"""

import sqlite3
import pandas as pd
from datetime import datetime

def check_iwm_spy_latest():
    """检查IWM_SPY_REL20的最新数据"""
    print("=" * 80)
    print("检查1: IWM_SPY_REL20最新数据")
    print("=" * 80)
    
    conn = sqlite3.connect('data/market_thermo_3years_auto.db')
    
    # 查询最近10天的数据
    query = """
        SELECT s.code, d.date, d.value_raw, d.value_tr, d.z, d.score
        FROM series_data d
        JOIN series_meta s ON d.series_id = s.id
        WHERE s.code = 'IWM_SPY_REL20'
        AND s.market = 'US'
        ORDER BY d.date DESC
        LIMIT 10
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    if df.empty:
        print("[ERROR] 数据库中没有IWM_SPY_REL20数据！")
        return None
    
    print(f"\n最近10天的数据:")
    print(df.to_string(index=False))
    
    latest_date = df['date'].iloc[0]
    latest_value_tr = df['value_tr'].iloc[0]
    latest_score = df['score'].iloc[0]
    
    print(f"\n最新日期: {latest_date}")
    print(f"value_tr: {latest_value_tr}")
    print(f"score: {latest_score}")
    
    # 检查是否有NaN
    nan_count = df['value_tr'].isna().sum()
    score_nan_count = df['score'].isna().sum()
    
    if nan_count > 0:
        print(f"\n[WARN] 有 {nan_count} 条记录的value_tr为NaN")
    
    if score_nan_count > 0:
        print(f"[WARN] 有 {score_nan_count} 条记录的score为NaN")
    
    return latest_date


def check_us_indicators_scores():
    """检查US市场所有指标的评分情况"""
    print("\n" + "=" * 80)
    print("检查2: US市场各指标评分情况")
    print("=" * 80)
    
    conn = sqlite3.connect('data/market_thermo_3years_auto.db')
    
    # 获取US市场所有主要指标
    query = """
        SELECT 
            s.code,
            s.name,
            s.role,
            COUNT(d.id) as total_records,
            SUM(CASE WHEN d.score IS NOT NULL THEN 1 ELSE 0 END) as scored_records,
            MAX(d.date) as latest_date
        FROM series_meta s
        LEFT JOIN series_data d ON s.id = d.series_id AND d.view = 'daily'
        WHERE s.market = 'US'
        AND s.role IN ('main', 'soft', 'hard')
        GROUP BY s.code, s.name, s.role
        ORDER BY s.role, s.code
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    if df.empty:
        print("[ERROR] 没有找到US市场的指标！")
        return
    
    print(f"\nUS市场指标统计 (共{len(df)}个):")
    print("-" * 80)
    
    for idx, row in df.iterrows():
        code = row['code']
        name = row['name']
        role = row['role']
        total = row['total_records']
        scored = row['scored_records']
        latest = row['latest_date']
        
        if total > 0:
            score_rate = scored / total * 100
            status = "[OK]" if score_rate > 80 else "[WARN]" if score_rate > 0 else "[ERROR]"
        else:
            score_rate = 0
            status = "[ERROR]"
        
        print(f"{status} {code:<25} {role:<8} {scored:>4}/{total:<4} ({score_rate:>5.1f}%)  最新:{latest}")
    
    # 统计有问题的指标
    problem_indicators = df[df['scored_records'] == 0]
    if not problem_indicators.empty:
        print(f"\n[WARN] 以下 {len(problem_indicators)} 个指标完全没有评分:")
        for idx, row in problem_indicators.iterrows():
            print(f"  - {row['code']} ({row['name']})")
    
    low_score_indicators = df[(df['scored_records'] > 0) & (df['scored_records'] / df['total_records'] < 0.5)]
    if not low_score_indicators.empty:
        print(f"\n[WARN] 以下 {len(low_score_indicators)} 个指标评分不足50%:")
        for idx, row in low_score_indicators.iterrows():
            rate = row['scored_records'] / row['total_records'] * 100
            print(f"  - {row['code']}: {rate:.1f}% ({row['scored_records']}/{row['total_records']})")


def check_recent_fetch_log():
    """检查最近的数据获取日志"""
    print("\n" + "=" * 80)
    print("检查3: 最近的数据获取日志")
    print("=" * 80)
    
    conn = sqlite3.connect('data/market_thermo_3years_auto.db')
    
    query = """
        SELECT 
            timestamp,
            action,
            status,
            market,
            indicator_code,
            records_count,
            message
        FROM fetch_log
        ORDER BY timestamp DESC
        LIMIT 10
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    if df.empty:
        print("[INFO] 没有获取日志")
        return
    
    print(f"\n最近10条日志:")
    print("-" * 80)
    for idx, row in df.iterrows():
        timestamp = row['timestamp']
        action = row['action']
        status = row['status']
        market = row['market'] if pd.notna(row['market']) else 'N/A'
        records = row['records_count'] if pd.notna(row['records_count']) else 0
        
        status_symbol = "[OK]" if status == 'success' else "[ERROR]"
        print(f"{status_symbol} {timestamp} | {market} | {action} | {records}条记录")


def check_latest_data_dates():
    """检查各指标的最新数据日期"""
    print("\n" + "=" * 80)
    print("检查4: 各指标最新数据日期")
    print("=" * 80)
    
    conn = sqlite3.connect('data/market_thermo_3years_auto.db')
    
    query = """
        SELECT 
            s.market,
            s.code,
            MAX(d.date) as latest_date,
            COUNT(*) as total_records
        FROM series_meta s
        JOIN series_data d ON s.id = d.series_id
        WHERE d.view = 'daily'
        AND s.role = 'main'
        GROUP BY s.market, s.code
        ORDER BY s.market, latest_date DESC
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    
    if df.empty:
        print("[ERROR] 没有数据！")
        return
    
    print("\nUS市场主要指标最新日期:")
    us_df = df[df['market'] == 'US']
    for idx, row in us_df.iterrows():
        print(f"  {row['code']:<30} {row['latest_date']}  ({row['total_records']}条)")
    
    print("\nCN市场主要指标最新日期:")
    cn_df = df[df['market'] == 'CN']
    for idx, row in cn_df.iterrows():
        print(f"  {row['code']:<30} {row['latest_date']}  ({row['total_records']}条)")


def main():
    print("\n" + "=" * 80)
    print("数据库状态诊断")
    print("=" * 80)
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        # 检查1: IWM_SPY_REL20
        latest_date = check_iwm_spy_latest()
        
        # 检查2: US指标评分
        check_us_indicators_scores()
        
        # 检查3: 获取日志
        check_recent_fetch_log()
        
        # 检查4: 最新数据日期
        check_latest_data_dates()
        
        # 总结
        print("\n" + "=" * 80)
        print("诊断总结")
        print("=" * 80)
        
        if latest_date:
            from datetime import date
            latest = pd.to_datetime(latest_date).date()
            today = date.today()
            
            print(f"\n1. IWM_SPY_REL20最新数据:")
            print(f"   - 最新日期: {latest}")
            print(f"   - 今天日期: {today}")
            
            if latest == today:
                print(f"   [OK] 数据是最新的（今天）")
            elif (today - latest).days == 1 and today.weekday() >= 5:
                print(f"   [OK] 数据是最新的（今天是周末）")
            else:
                gap = (today - latest).days
                print(f"   [WARN] 数据落后 {gap} 天")
                print(f"   -> 建议: 点击GUI的'手动获取最新数据'")
        
        print(f"\n2. US指标评分:")
        print(f"   → 查看上面的统计表，检查哪些指标缺少评分")
        print(f"   → 如果很多指标score=0，需要点击'计算评分'")
        
        print(f"\n3. 建议操作:")
        print(f"   1) 点击'手动获取最新数据' → 更新原始数据")
        print(f"   2) 点击'计算评分' → 重新计算评分")
        print(f"   3) 再次运行此脚本检查结果")
        
    except Exception as e:
        print(f"\n[ERROR] 诊断失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

