"""
验证yfinance当前能获取到哪天的数据
"""

import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd

def check_yfinance_latest():
    print("=" * 80)
    print("检查yfinance当前最新数据")
    print("=" * 80)
    print(f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 获取最近10天数据
    end_date = datetime.now()
    start_date = end_date - timedelta(days=10)
    
    print(f"请求时间范围: {start_date.date()} 至 {end_date.date()}\n")
    
    # 检查IWM
    print("检查 IWM:")
    print("-" * 80)
    iwm = yf.download("IWM", start=start_date, end=end_date, progress=False)
    if not iwm.empty:
        latest_iwm = iwm.index[-1]
        print(f"[OK] 获取到 {len(iwm)} 条数据")
        print(f"    最新日期: {latest_iwm.strftime('%Y-%m-%d')}")
        print(f"    最近3天:")
        print(iwm[['Close']].tail(3))
    else:
        print("[ERROR] 未获取到IWM数据")
    
    # 检查SPY
    print("\n检查 SPY:")
    print("-" * 80)
    spy = yf.download("SPY", start=start_date, end=end_date, progress=False)
    if not spy.empty:
        latest_spy = spy.index[-1]
        print(f"[OK] 获取到 {len(spy)} 条数据")
        print(f"    最新日期: {latest_spy.strftime('%Y-%m-%d')}")
        print(f"    最近3天:")
        print(spy[['Close']].tail(3))
    else:
        print("[ERROR] 未获取到SPY数据")
    
    # 检查VIX
    print("\n检查 VIX:")
    print("-" * 80)
    vix = yf.download("^VIX", start=start_date, end=end_date, progress=False)
    if not vix.empty:
        latest_vix = vix.index[-1]
        print(f"[OK] 获取到 {len(vix)} 条数据")
        print(f"    最新日期: {latest_vix.strftime('%Y-%m-%d')}")
        print(f"    最近3天:")
        print(vix[['Close']].tail(3))
    else:
        print("[ERROR] 未获取到VIX数据")
    
    print("\n" + "=" * 80)
    print("结论")
    print("=" * 80)
    
    if not iwm.empty and not spy.empty:
        latest = min(latest_iwm, latest_spy)
        print(f"\n当前yfinance最新数据日期: {latest.strftime('%Y-%m-%d')}")
        
        # 检查是否有12月26日
        if latest >= pd.Timestamp('2025-12-26'):
            print("\n✓ yfinance已有12月26日（周四）数据")
        elif latest >= pd.Timestamp('2025-12-24'):
            print("\n✗ yfinance只有到12月24日（周二）")
            print("   12月25日（周三）是圣诞节，美股休市")
            print("   12月26日（周四）美股交易，但数据可能还未更新")
            print("\n可能原因:")
            print("  1. yfinance数据延迟（通常在收盘后数小时更新）")
            print("  2. 数据源问题")
            print("\n建议:")
            print("  - 等待几小时后再次获取")
            print("  - 或使用其他数据源")
        else:
            print(f"\n✗ yfinance数据过旧，只到 {latest.strftime('%Y-%m-%d')}")


if __name__ == "__main__":
    check_yfinance_latest()

