"""
IWM_SPY 维度数据调试脚本

该脚本用于诊断IWM_SPY_REL20维度为什么没有最新数据
检查项：
1. yfinance是否能获取到最新的IWM和SPY数据
2. 数据库中存储的最新数据日期
3. 数据处理过程中的时间窗口问题
"""

import yfinance as yf
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import numpy as np

def check_yfinance_latest_data():
    """
    检查yfinance是否能获取到最新的IWM和SPY数据
    """
    print("=" * 80)
    print("第一步：检查yfinance数据源")
    print("=" * 80)
    
    # 获取最近30天的数据
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    print(f"\n请求时间范围: {start_date.date()} 至 {end_date.date()}")
    print(f"当前日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 获取IWM数据
    print("\n>>> 获取IWM数据...")
    try:
        iwm = yf.download("IWM", start=start_date, end=end_date, progress=False)
        if not iwm.empty:
            print(f"[OK] IWM数据获取成功")
            print(f"  - 数据行数: {len(iwm)}")
            print(f"  - 最新日期: {iwm.index[-1].strftime('%Y-%m-%d')}")
            latest_close = float(iwm['Close'].iloc[-1])
            print(f"  - 最新收盘价: {latest_close:.2f}")
            print(f"\n最近5天数据:")
            print(iwm[['Close']].tail(5))
        else:
            print("[ERROR] IWM数据为空")
    except Exception as e:
        print(f"[ERROR] IWM数据获取失败: {e}")
        import traceback
        traceback.print_exc()
        iwm = pd.DataFrame()
    
    # 获取SPY数据
    print("\n>>> 获取SPY数据...")
    try:
        spy = yf.download("SPY", start=start_date, end=end_date, progress=False)
        if not spy.empty:
            print(f"[OK] SPY数据获取成功")
            print(f"  - 数据行数: {len(spy)}")
            print(f"  - 最新日期: {spy.index[-1].strftime('%Y-%m-%d')}")
            latest_close = float(spy['Close'].iloc[-1])
            print(f"  - 最新收盘价: {latest_close:.2f}")
            print(f"\n最近5天数据:")
            print(spy[['Close']].tail(5))
        else:
            print("[ERROR] SPY数据为空")
    except Exception as e:
        print(f"[ERROR] SPY数据获取失败: {e}")
        import traceback
        traceback.print_exc()
        spy = pd.DataFrame()
    
    return iwm, spy


def check_database_data(db_path="data/market_thermo_3years_auto.db"):
    """
    检查数据库中存储的IWM_SPY数据
    """
    print("\n" + "=" * 80)
    print("第二步：检查数据库中的IWM_SPY_REL20数据")
    print("=" * 80)
    
    try:
        conn = sqlite3.connect(db_path)
        
        # 检查表是否存在
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='indicators'
        """)
        
        if not cursor.fetchone():
            print(f"[ERROR] 数据库中不存在indicators表")
            conn.close()
            return None
        
        # 查询IWM_SPY_REL20的最新数据
        query = """
            SELECT date, value, score, lamp 
            FROM indicators 
            WHERE code = 'IWM_SPY_REL20' 
            ORDER BY date DESC 
            LIMIT 20
        """
        
        df = pd.read_sql(query, conn)
        conn.close()
        
        if df.empty:
            print("[ERROR] 数据库中没有IWM_SPY_REL20数据")
            return None
        
        print(f"[OK] 找到IWM_SPY_REL20数据")
        print(f"  - 总记录数: {len(df)}")
        print(f"  - 最新日期: {df['date'].iloc[0]}")
        
        print(f"\n最近20天数据:")
        print(df.to_string(index=False))
        
        return df
        
    except Exception as e:
        print(f"✗ 数据库查询失败: {e}")
        return None


def calculate_rel20_manually(iwm, spy):
    """
    手动计算IWM/SPY的20日相对收益
    """
    print("\n" + "=" * 80)
    print("第三步：手动计算IWM/SPY 20日相对收益")
    print("=" * 80)
    
    if iwm.empty or spy.empty:
        print("[ERROR] 缺少IWM或SPY数据，无法计算")
        return None
    
    try:
        # 提取Close列并合并数据
        # yfinance返回的DataFrame可能有多级列名
        if isinstance(iwm.columns, pd.MultiIndex):
            iwm_close = iwm[('Close', 'IWM')] if ('Close', 'IWM') in iwm.columns else iwm['Close'].iloc[:, 0]
        else:
            iwm_close = iwm['Close']
        
        if isinstance(spy.columns, pd.MultiIndex):
            spy_close = spy[('Close', 'SPY')] if ('Close', 'SPY') in spy.columns else spy['Close'].iloc[:, 0]
        else:
            spy_close = spy['Close']
        
        df = pd.DataFrame({
            'IWM': iwm_close.values,
            'SPY': spy_close.values
        }, index=iwm_close.index).dropna()
        
        print(f"\n合并后的数据行数: {len(df)}")
        print(f"日期范围: {df.index[0].strftime('%Y-%m-%d')} 至 {df.index[-1].strftime('%Y-%m-%d')}")
        
        # 计算20日相对收益
        # relret20 = (IWM_t / IWM_t-20) / (SPY_t / SPY_t-20) - 1
        df['IWM_ret20'] = df['IWM'] / df['IWM'].shift(20) - 1
        df['SPY_ret20'] = df['SPY'] / df['SPY'].shift(20) - 1
        df['REL20'] = ((1 + df['IWM_ret20']) / (1 + df['SPY_ret20']) - 1) * 100  # 转换为百分比
        
        print(f"\n最近10天的20日相对收益计算结果:")
        result = df[['IWM', 'SPY', 'IWM_ret20', 'SPY_ret20', 'REL20']].tail(10)
        print(result.to_string())
        
        # 检查是否有足够的历史数据计算到最新日期
        valid_data = df.dropna(subset=['REL20'])
        if not valid_data.empty:
            print(f"\n[OK] 能够计算相对收益的最新日期: {valid_data.index[-1].strftime('%Y-%m-%d')}")
            print(f"  - 最新REL20值: {valid_data['REL20'].iloc[-1]:.4f}%")
        else:
            print("\n[ERROR] 没有足够的历史数据计算20日相对收益")
        
        return df
        
    except Exception as e:
        print(f"[ERROR] 计算失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def analyze_time_window_issue(iwm, spy, db_data):
    """
    分析时间窗口问题
    """
    print("\n" + "=" * 80)
    print("第四步：分析时间窗口和数据延迟问题")
    print("=" * 80)
    
    today = datetime.now().date()
    print(f"\n今天日期: {today}")
    
    # 检查yfinance数据的最新日期
    if not iwm.empty and not spy.empty:
        iwm_latest = iwm.index[-1].date()
        spy_latest = spy.index[-1].date()
        
        print(f"\nyfinance数据:")
        print(f"  - IWM最新日期: {iwm_latest}")
        print(f"  - SPY最新日期: {spy_latest}")
        print(f"  - 距今天: {(today - iwm_latest).days} 天")
        
        # 分析是否是周末或节假日
        if (today - iwm_latest).days > 0:
            if today.weekday() >= 5:  # 周六或周日
                print(f"  [INFO] 今天是周末，市场不开盘")
            elif (today - iwm_latest).days == 1:
                print(f"  [INFO] yfinance数据延迟1天（可能是盘中或数据未更新）")
            else:
                print(f"  [WARNING] yfinance数据延迟{(today - iwm_latest).days}天（可能是节假日或数据源问题）")
    
    # 检查数据库数据的最新日期
    if db_data is not None and not db_data.empty:
        db_latest = pd.to_datetime(db_data['date'].iloc[0]).date()
        
        print(f"\n数据库数据:")
        print(f"  - IWM_SPY_REL20最新日期: {db_latest}")
        print(f"  - 距今天: {(today - db_latest).days} 天")
        
        # 计算20日窗口需求
        print(f"\n时间窗口分析:")
        print(f"  - REL20计算需要20个交易日的历史数据")
        print(f"  - 因此最新可计算日期 = 最新交易日")
        
        if not iwm.empty:
            iwm_latest = iwm.index[-1].date()
            expected_latest = iwm_latest  # REL20的最新日期应该等于价格数据的最新日期
            
            print(f"  - 价格数据最新日期: {iwm_latest}")
            print(f"  - 理论上REL20最新日期: {expected_latest}")
            print(f"  - 实际数据库最新日期: {db_latest}")
            
            if db_latest < expected_latest:
                gap = (expected_latest - db_latest).days
                print(f"  [WARNING] 数据库落后 {gap} 天")
                print(f"  -> 可能原因:")
                print(f"    1. 数据库未更新到最新")
                print(f"    2. 数据获取或计算流程中出现问题")
                print(f"    3. 周末/节假日导致的正常延迟")
            else:
                print(f"  [OK] 数据库是最新的")


def main():
    """
    主函数
    """
    print("\n" + "=" * 80)
    print("IWM_SPY_REL20 维度数据诊断")
    print("=" * 80)
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 第一步：检查yfinance数据
    iwm, spy = check_yfinance_latest_data()
    
    # 第二步：检查数据库数据
    db_data = check_database_data()
    
    # 第三步：手动计算相对收益
    if not iwm.empty and not spy.empty:
        rel20_data = calculate_rel20_manually(iwm, spy)
    else:
        rel20_data = None
    
    # 第四步：分析时间窗口问题
    analyze_time_window_issue(iwm, spy, db_data)
    
    # 总结
    print("\n" + "=" * 80)
    print("诊断总结")
    print("=" * 80)
    
    if not iwm.empty and not spy.empty:
        print("[OK] yfinance能够获取IWM和SPY数据")
        print(f"  最新数据日期: {iwm.index[-1].strftime('%Y-%m-%d')}")
    else:
        print("[ERROR] yfinance无法获取数据")
    
    if db_data is not None and not db_data.empty:
        print(f"[OK] 数据库有IWM_SPY_REL20数据")
        print(f"  最新数据日期: {db_data['date'].iloc[0]}")
    else:
        print("[ERROR] 数据库没有数据")
    
    if not iwm.empty and not spy.empty and db_data is not None:
        iwm_latest = iwm.index[-1].date()
        db_latest = pd.to_datetime(db_data['date'].iloc[0]).date()
        
        if db_latest < iwm_latest:
            print(f"\n[WARNING] 问题确认: 数据库落后{(iwm_latest - db_latest).days}天")
            print(f"   建议运行数据更新流程以获取最新数据")
        else:
            print(f"\n[OK] 数据是最新的，没有发现问题")


if __name__ == "__main__":
    main()
