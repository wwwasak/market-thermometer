"""
IWM_SPY_REL20 数据诊断最终报告

综合分析yfinance数据源和数据库数据，给出完整结论
"""

import yfinance as yf
import pandas as pd
import sqlite3
from datetime import datetime, timedelta

def main():
    print("=" * 80)
    print("IWM_SPY_REL20 维度数据完整诊断报告")
    print("=" * 80)
    print(f"报告时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # ===== 第一部分：yfinance数据源检查 =====
    print("【第一部分】yfinance数据源检查")
    print("-" * 80)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    try:
        iwm = yf.download("IWM", start=start_date, end=end_date, progress=False)
        spy = yf.download("SPY", start=start_date, end=end_date, progress=False)
        
        if not iwm.empty and not spy.empty:
            # 提取收盘价
            if isinstance(iwm.columns, pd.MultiIndex):
                iwm_close = iwm[('Close', 'IWM')] if ('Close', 'IWM') in iwm.columns else iwm['Close'].iloc[:, 0]
            else:
                iwm_close = iwm['Close']
            
            if isinstance(spy.columns, pd.MultiIndex):
                spy_close = spy[('Close', 'SPY')] if ('Close', 'SPY') in spy.columns else spy['Close'].iloc[:, 0]
            else:
                spy_close = spy['Close']
            
            # 合并并计算REL20
            df = pd.DataFrame({
                'IWM': iwm_close.values,
                'SPY': spy_close.values
            }, index=iwm_close.index).dropna()
            
            df['REL20'] = ((df['IWM'] / df['IWM'].shift(20)) / (df['SPY'] / df['SPY'].shift(20)) - 1) * 100
            valid_data = df.dropna(subset=['REL20'])
            
            if not valid_data.empty:
                yf_latest = valid_data.index[-1]
                yf_latest_value = valid_data['REL20'].iloc[-1]
                
                print(f"[OK] yfinance可以获取最新数据")
                print(f"  - 最新日期: {yf_latest.strftime('%Y-%m-%d')}")
                print(f"  - REL20值: {yf_latest_value:.4f}%")
                print(f"  - 数据行数: {len(valid_data)}行")
                
                today = datetime.now().date()
                gap = (today - yf_latest.date()).days
                
                if gap == 0:
                    print(f"  - 延迟情况: 无延迟（今天的数据）")
                elif gap == 1 and today.weekday() >= 5:
                    print(f"  - 延迟情况: 正常（今天是周末）")
                elif gap == 1:
                    print(f"  - 延迟情况: 1天（正常的数据更新延迟）")
                else:
                    print(f"  - 延迟情况: {gap}天（可能是节假日）")
                
                yf_success = True
            else:
                print("[ERROR] yfinance无法计算REL20")
                yf_success = False
                yf_latest = None
                yf_latest_value = None
        else:
            print("[ERROR] yfinance无法获取IWM或SPY数据")
            yf_success = False
            yf_latest = None
            yf_latest_value = None
            
    except Exception as e:
        print(f"[ERROR] yfinance数据检查失败: {e}")
        yf_success = False
        yf_latest = None
        yf_latest_value = None
    
    # ===== 第二部分：数据库数据检查 =====
    print(f"\n【第二部分】数据库数据检查")
    print("-" * 80)
    
    db_path = "data/market_thermo_3years_auto.db"
    
    try:
        conn = sqlite3.connect(db_path)
        
        # 获取IWM_SPY_REL20的series_id
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM series_meta WHERE code = 'IWM_SPY_REL20'")
        result = cursor.fetchone()
        
        if result:
            series_id = result[0]
            
            # 查询最新数据
            query = f"""
                SELECT date, value_raw, value_tr, z, score
                FROM series_data
                WHERE series_id = {series_id}
                ORDER BY date DESC
                LIMIT 10
            """
            
            db_data = pd.read_sql(query, conn)
            
            if not db_data.empty:
                db_latest = db_data['date'].iloc[0]
                db_latest_value = db_data['value_tr'].iloc[0]
                
                # 统计总数据量
                cursor.execute(f"""
                    SELECT COUNT(*), MIN(date), MAX(date)
                    FROM series_data
                    WHERE series_id = {series_id}
                """)
                count, min_date, max_date = cursor.fetchone()
                
                print(f"[OK] 数据库中有IWM_SPY_REL20数据")
                print(f"  - 最新日期: {db_latest}")
                print(f"  - value_tr值: {db_latest_value:.4f}" if db_latest_value else "  - value_tr值: None")
                print(f"  - 总数据量: {count}行")
                print(f"  - 日期范围: {min_date} 至 {max_date}")
                
                print(f"\n  最近10天数据:")
                print("  " + "-" * 70)
                for idx, row in db_data.iterrows():
                    value = row['value_tr'] if pd.notna(row['value_tr']) else row['value_raw']
                    score = row['score'] if pd.notna(row['score']) else 0
                    print(f"  {row['date']}  value: {value:>8.4f}  score: {score:>6.2f}")
                
                db_success = True
                db_latest = pd.to_datetime(db_latest).date()
            else:
                print("[ERROR] 数据库中没有IWM_SPY_REL20的series_data数据")
                db_success = False
                db_latest = None
        else:
            print("[ERROR] 数据库series_meta中没有IWM_SPY_REL20记录")
            db_success = False
            db_latest = None
        
        conn.close()
        
    except Exception as e:
        print(f"[ERROR] 数据库检查失败: {e}")
        import traceback
        traceback.print_exc()
        db_success = False
        db_latest = None
    
    # ===== 第三部分：对比分析 =====
    print(f"\n【第三部分】对比分析")
    print("-" * 80)
    
    if yf_success and db_success:
        yf_date = yf_latest.date()
        
        print(f"yfinance最新日期: {yf_date}")
        print(f"数据库最新日期:   {db_latest}")
        
        if db_latest == yf_date:
            print(f"\n[OK] 数据库与yfinance完全同步！")
        elif db_latest < yf_date:
            gap = (yf_date - db_latest).days
            print(f"\n[WARNING] 数据库落后 {gap} 天")
        else:
            gap = (db_latest - yf_date).days
            print(f"\n[OK] 数据库比yfinance还新 {gap} 天（可能是时区问题）")
    elif not yf_success:
        print("无法从yfinance获取数据，无法对比")
    elif not db_success:
        print("数据库中没有数据，无法对比")
    
    # ===== 第四部分：结论与建议 =====
    print(f"\n{'='*80}")
    print("【最终结论】")
    print("=" * 80)
    
    if not yf_success:
        print("\n1. yfinance数据源:")
        print("   [ERROR] 无法获取数据或计算REL20")
        print("   -> 可能原因: 网络问题、yfinance服务问题")
        print("   -> 建议: 检查网络连接，稍后重试")
    else:
        print("\n1. yfinance数据源:")
        print("   [OK] 可以正常获取最新数据")
        print(f"   [OK] 最新日期: {yf_latest.strftime('%Y-%m-%d')}")
    
    if not db_success:
        print("\n2. 数据库状态:")
        print("   [ERROR] 没有IWM_SPY_REL20数据")
        print("   -> 可能原因: 数据库未初始化或数据未正确存入")
        print("   -> 建议: 运行 fetch_3years_data_auto.py 初始化数据")
    else:
        print("\n2. 数据库状态:")
        print("   [OK] 有完整的IWM_SPY_REL20数据")
        print(f"   [OK] 最新日期: {db_latest}")
    
    if yf_success and db_success:
        print("\n3. 数据同步情况:")
        yf_date = yf_latest.date()
        if db_latest == yf_date:
            print("   [OK] 数据库已是最新，无需更新")
        elif db_latest < yf_date:
            gap = (yf_date - db_latest).days
            print(f"   [WARNING] 数据库落后{gap}天")
            print(f"   -> 建议: 运行数据更新流程获取最新数据")
        else:
            print("   [OK] 数据库数据已是最新")
    
    print("\n" + "=" * 80)
    print("报告结束")
    print("=" * 80)

if __name__ == "__main__":
    main()

