"""
扩展的IWM_SPY数据检查
获取更长的历史数据来验证计算
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def main():
    print("=" * 80)
    print("获取3个月的IWM和SPY数据进行完整测试")
    print("=" * 80)
    
    # 获取3个月的数据以确保有足够的20日窗口
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    print(f"\n请求时间范围: {start_date.date()} 至 {end_date.date()}")
    
    # 获取数据
    print("\n>>> 获取IWM数据...")
    iwm = yf.download("IWM", start=start_date, end=end_date, progress=False)
    print(f"[OK] 获取到 {len(iwm)} 条IWM数据")
    print(f"    日期范围: {iwm.index[0].strftime('%Y-%m-%d')} 至 {iwm.index[-1].strftime('%Y-%m-%d')}")
    
    print("\n>>> 获取SPY数据...")
    spy = yf.download("SPY", start=start_date, end=end_date, progress=False)
    print(f"[OK] 获取到 {len(spy)} 条SPY数据")
    print(f"    日期范围: {spy.index[0].strftime('%Y-%m-%d')} 至 {spy.index[-1].strftime('%Y-%m-%d')}")
    
    # 合并数据
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
    
    # 计算20日相对收益
    df['IWM_ret20'] = df['IWM'] / df['IWM'].shift(20) - 1
    df['SPY_ret20'] = df['SPY'] / df['SPY'].shift(20) - 1
    df['REL20'] = ((1 + df['IWM_ret20']) / (1 + df['SPY_ret20']) - 1) * 100
    
    # 找到有效数据
    valid_data = df.dropna(subset=['REL20'])
    
    if not valid_data.empty:
        print(f"\n[OK] 成功计算REL20")
        print(f"    有效数据行数: {len(valid_data)}")
        print(f"    最早日期: {valid_data.index[0].strftime('%Y-%m-%d')}")
        print(f"    最新日期: {valid_data.index[-1].strftime('%Y-%m-%d')}")
        print(f"    最新REL20值: {valid_data['REL20'].iloc[-1]:.4f}%")
        
        print(f"\n最近10个交易日的REL20数据:")
        recent = valid_data[['IWM', 'SPY', 'IWM_ret20', 'SPY_ret20', 'REL20']].tail(10)
        print(recent.to_string())
        
        # 检查12月26日是否有数据
        target_date = pd.Timestamp('2025-12-26')
        if target_date in valid_data.index:
            print(f"\n[OK] 12月26日有REL20数据")
            print(f"    值: {valid_data.loc[target_date, 'REL20']:.4f}%")
        else:
            print(f"\n[WARNING] 12月26日没有REL20数据")
            print(f"    数据最新到: {valid_data.index[-1].strftime('%Y-%m-%d')}")
    else:
        print("[ERROR] 无法计算REL20")
    
    # 现在检查数据库
    print("\n" + "=" * 80)
    print("检查数据库中的数据")
    print("=" * 80)
    
    import sqlite3
    db_path = "data/market_thermo_3years_auto.db"
    
    try:
        conn = sqlite3.connect(db_path)
        
        # 检查表是否存在
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table'
        """)
        tables = cursor.fetchall()
        print(f"\n数据库中的表: {[t[0] for t in tables]}")
        
        if ('indicators',) in tables:
            # 查询IWM_SPY_REL20数据
            query = """
                SELECT date, value, score, lamp 
                FROM indicators 
                WHERE code = 'IWM_SPY_REL20' 
                ORDER BY date DESC 
                LIMIT 10
            """
            
            db_data = pd.read_sql(query, conn)
            
            if not db_data.empty:
                print(f"\n[OK] 数据库中有IWM_SPY_REL20数据")
                print(f"    最新日期: {db_data['date'].iloc[0]}")
                print(f"\n最近10条数据:")
                print(db_data.to_string(index=False))
            else:
                print(f"\n[WARNING] 数据库中没有IWM_SPY_REL20数据")
        else:
            print("\n[INFO] 数据库中没有indicators表（可能还未初始化）")
        
        conn.close()
        
    except Exception as e:
        print(f"[ERROR] 数据库查询失败: {e}")
    
    # 总结
    print("\n" + "=" * 80)
    print("结论")
    print("=" * 80)
    
    if not valid_data.empty:
        latest_yf = valid_data.index[-1].strftime('%Y-%m-%d')
        print(f"\n1. yfinance数据源:")
        print(f"   - 能够获取到最新数据: {latest_yf}")
        print(f"   - REL20最新值: {valid_data['REL20'].iloc[-1]:.4f}%")
        
        today = datetime.now().date()
        yf_date = valid_data.index[-1].date()
        gap = (today - yf_date).days
        
        if gap == 0:
            print(f"   - [OK] 数据是今天的，非常及时")
        elif gap == 1 and today.weekday() >= 5:
            print(f"   - [OK] 今天是周末，数据延迟1天是正常的")
        elif gap == 1:
            print(f"   - [INFO] 数据延迟1天（可能是盘中或yfinance更新延迟）")
        else:
            print(f"   - [WARNING] 数据延迟{gap}天（可能是节假日或数据源问题）")
        
        print(f"\n2. 如果数据库中没有最新的12月26日数据:")
        print(f"   - 原因: 数据库可能没有运行最新的数据更新流程")
        print(f"   - 解决: 运行 fetch_3years_data_auto.py 更新数据")
        
    else:
        print("\n[ERROR] yfinance无法计算REL20，这不应该发生")

if __name__ == "__main__":
    main()

