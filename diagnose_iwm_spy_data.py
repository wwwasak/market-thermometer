"""
IWM_SPY维度数据诊断脚本

功能：
1. 检查yfinance是否有最新的IWM和SPY数据
2. 查看数据库中IWM_SPY_REL20的最新日期
3. 诊断数据缺失的原因
"""

import yfinance as yf
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

def check_yfinance_data():
    """检查yfinance是否有最新的IWM和SPY数据"""
    print("=" * 80)
    print("【步骤1】检查yfinance数据源")
    print("=" * 80)
    
    tickers = ["IWM", "SPY"]
    end_date = datetime.now()
    start_date = end_date - timedelta(days=10)  # 获取最近10天
    
    for ticker in tickers:
        try:
            print(f"\n检查 {ticker}...")
            data = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), 
                             end=end_date.strftime('%Y-%m-%d'), progress=False)
            
            if data.empty:
                print(f"  ❌ {ticker} 无数据返回")
            else:
                latest_date = data.index[-1]
                print(f"  ✅ {ticker} 最新数据日期: {latest_date.strftime('%Y-%m-%d')}")
                print(f"     最近5天收盘价:")
                for date, row in data.tail(5).iterrows():
                    print(f"       {date.strftime('%Y-%m-%d')}: {row['Close']:.2f}")
                    
        except Exception as e:
            print(f"  ❌ {ticker} 获取数据出错: {e}")

def check_database_data():
    """检查数据库中的IWM_SPY数据"""
    print("\n" + "=" * 80)
    print("【步骤2】检查数据库中的维度数据")
    print("=" * 80)
    
    db_path = "data/market_thermo_3years_auto.db"
    
    if not Path(db_path).exists():
        print(f"  ❌ 数据库文件不存在: {db_path}")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        
        # 检查IWM_SPY_REL20维度
        print("\n检查 IWM_SPY_REL20 维度数据...")
        query = """
        SELECT date, value, score, z_score, lamp
        FROM dimension_scores
        WHERE dimension_code = 'IWM_SPY_REL20'
        ORDER BY date DESC
        LIMIT 10
        """
        df = pd.read_sql_query(query, conn)
        
        if df.empty:
            print("  ❌ 数据库中没有 IWM_SPY_REL20 数据")
        else:
            latest_date = df['date'].iloc[0]
            print(f"  ✅ 最新数据日期: {latest_date}")
            print(f"\n     最近10天数据:")
            print(df.to_string(index=False))
        
        # 检查原始数据表
        print("\n\n检查原始数据表 (IWM, SPY)...")
        for ticker in ['IWM', 'SPY']:
            query = f"""
            SELECT date, value
            FROM raw_data
            WHERE indicator_code = '{ticker}'
            ORDER BY date DESC
            LIMIT 5
            """
            df_raw = pd.read_sql_query(query, conn)
            
            if df_raw.empty:
                print(f"  ❌ {ticker} 无原始数据")
            else:
                latest_raw = df_raw['date'].iloc[0]
                print(f"  ✅ {ticker} 最新原始数据日期: {latest_raw}")
                print(f"     最近5天:")
                for _, row in df_raw.iterrows():
                    print(f"       {row['date']}: {row['value']:.2f}")
        
        conn.close()
        
    except Exception as e:
        print(f"  ❌ 查询数据库出错: {e}")

def check_weekend_issue():
    """检查是否是周末/假期导致的数据延迟"""
    print("\n" + "=" * 80)
    print("【步骤3】检查日期因素")
    print("=" * 80)
    
    today = datetime.now()
    weekday = today.weekday()  # 0=周一, 6=周日
    
    print(f"\n当前日期: {today.strftime('%Y-%m-%d %A')}")
    
    if weekday == 5:  # 周六
        print("  ℹ️  今天是周六，美股市场不交易")
        print("  ℹ️  最新数据应该是周五的")
    elif weekday == 6:  # 周日
        print("  ℹ️  今天是周日，美股市场不交易")
        print("  ℹ️  最新数据应该是周五的")
    else:
        print(f"  ℹ️  今天是工作日 (周{weekday + 1})")
        
    # 计算上一个交易日
    last_trading_day = today
    if weekday == 5:  # 周六
        last_trading_day = today - timedelta(days=1)
    elif weekday == 6:  # 周日
        last_trading_day = today - timedelta(days=2)
    
    print(f"  ℹ️  预期最新交易日: {last_trading_day.strftime('%Y-%m-%d %A')}")

def diagnose_data_gap():
    """诊断数据缺口"""
    print("\n" + "=" * 80)
    print("【步骤4】数据缺口诊断")
    print("=" * 80)
    
    db_path = "data/market_thermo_3years_auto.db"
    
    if not Path(db_path).exists():
        print(f"  ❌ 数据库文件不存在")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        
        # 获取IWM_SPY_REL20的数据日期范围
        query = """
        SELECT MIN(date) as first_date, MAX(date) as last_date, COUNT(*) as total_count
        FROM dimension_scores
        WHERE dimension_code = 'IWM_SPY_REL20'
        """
        df = pd.read_sql_query(query, conn)
        
        if not df.empty and df['first_date'][0]:
            print(f"\nIWM_SPY_REL20 数据概况:")
            print(f"  首条记录: {df['first_date'][0]}")
            print(f"  末条记录: {df['last_date'][0]}")
            print(f"  总记录数: {df['total_count'][0]}")
            
            # 计算距今天数
            last_date = datetime.strptime(df['last_date'][0], '%Y-%m-%d')
            days_ago = (datetime.now() - last_date).days
            print(f"  距今天数: {days_ago} 天")
            
            if days_ago > 3:
                print(f"\n  ⚠️  警告：数据已经 {days_ago} 天未更新！")
                print("  可能原因：")
                print("    1. 数据获取脚本未运行")
                print("    2. yfinance API问题")
                print("    3. 数据转换/计算出错")
            elif days_ago == 0:
                print("  ✅ 数据是最新的（今天）")
            elif days_ago <= 3:
                print("  ✅ 数据比较新（可能是周末/假期因素）")
        
        # 检查最近的数据更新记录
        query = """
        SELECT DISTINCT date
        FROM dimension_scores
        WHERE dimension_code = 'IWM_SPY_REL20'
        ORDER BY date DESC
        LIMIT 20
        """
        df_dates = pd.read_sql_query(query, conn)
        
        if not df_dates.empty:
            print(f"\n  最近20个有数据的日期:")
            for i, date in enumerate(df_dates['date'], 1):
                print(f"    {i:2d}. {date}")
        
        conn.close()
        
    except Exception as e:
        print(f"  ❌ 诊断出错: {e}")

def main():
    """主函数"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "IWM_SPY维度数据诊断工具" + " " * 34 + "║")
    print("╚" + "=" * 78 + "╝")
    print()
    
    # 步骤1：检查yfinance数据源
    check_yfinance_data()
    
    # 步骤2：检查数据库数据
    check_database_data()
    
    # 步骤3：检查日期因素
    check_weekend_issue()
    
    # 步骤4：诊断数据缺口
    diagnose_data_gap()
    
    print("\n" + "=" * 80)
    print("【诊断总结】")
    print("=" * 80)
    print("""
根据以上检查结果，可能的原因有：

1. 如果yfinance有最新数据，但数据库没有：
   → 需要运行数据更新脚本（fetch_3years_data_auto.py）

2. 如果yfinance也没有最新数据：
   → yfinance的数据延迟，通常在美股收盘后几小时才能获取当天数据
   → 可能是周末/假期，需要等待下一个交易日

3. 如果数据库有最近几天的数据（1-3天前）：
   → 可能是周末因素，这是正常的
   → 美股周末不交易，最新数据应该是周五的

4. 如果数据差距超过5个工作日：
   → 需要检查数据更新流程是否正常运行
   → 检查是否有错误日志
    """)
    
    print("\n💡 建议操作:")
    print("   1. 如果需要更新数据，运行: python fetch_3years_data_auto.py")
    print("   2. 查看错误日志文件: market_thermo.log")
    print("   3. 手动运行完整流水线: python run_full_pipeline.py")
    print()

if __name__ == "__main__":
    main()

