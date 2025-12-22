import sys
sys.stdout.reconfigure(encoding='utf-8')

from storage.repository import Repository
import pandas as pd

repo = Repository('sqlite:///data/market_thermo_3years_auto.db')

# 检查 IWM_SPY_REL20 数据
print("=" * 80)
print("检查 IWM_SPY_REL20 数据")
print("=" * 80)

df = repo.load_series_data('IWM_SPY_REL20', 'US')
print(f"\n数据记录数: {len(df)}")

if len(df) > 0:
    print(f"日期范围: {df.index.min()} 到 {df.index.max()}")
    print(f"\n列: {list(df.columns)}")
    print(f"\n最近10条记录:")
    pd.options.display.width = 200
    pd.options.display.max_columns = 10
    print(df.tail(10).to_string())
    
    # 统计
    print(f"\n数据统计:")
    print(df.describe().to_string())
else:
    print("\n⚠️ 数据库中没有 IWM_SPY_REL20 的数据！")
    print("\n可能原因:")
    print("1. 数据尚未获取")
    print("2. 获取过程中出错")
    print("3. 数据被删除")
    
    # 检查原始组件数据
    print("\n检查组件数据 (IWM 和 SPY):")
    
    # 尝试获取 IWM 数据
    try:
        from core.datasource import YFinanceFetcher
        from datetime import datetime, timedelta
        
        yf = YFinanceFetcher()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        print(f"\n尝试从 yfinance 获取最近30天数据...")
        iwm = yf.fetch('IWM', start_date, end_date)
        spy = yf.fetch('SPY', start_date, end_date)
        
        print(f"  IWM: {len(iwm)} 条记录")
        print(f"  SPY: {len(spy)} 条记录")
        
        if len(iwm) > 0 and len(spy) > 0:
            print(f"\n✅ yfinance 可以正常获取 IWM 和 SPY 数据")
            print(f"\n建议: 运行数据获取脚本来填充数据")
        else:
            print(f"\n⚠️ yfinance 无法获取数据")
    except Exception as e:
        print(f"\n❌ 测试获取数据时出错: {e}")

