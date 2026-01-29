"""
测试不同的akshare API来获取市场成交额
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

print("="*60)
print("测试1: stock_zh_index_hist_csindex (中证指数)")
print("="*60)
try:
    # 尝试使用中证全指（000985）来估算全市场
    df = ak.stock_zh_index_hist_csindex(symbol="000985", start_date="20260120", end_date="20260127")
    print(f"[OK] 获取到 {len(df)} 条记录")
    print(f"列名: {list(df.columns)}")
    if len(df) > 0:
        print(f"\n最近3条数据:")
        print(df.tail(3).to_string())
except Exception as e:
    print(f"[FAIL] 失败: {e}")

print("\n" + "="*60)
print("测试2: stock_zh_index_daily_em (东财指数数据)")
print("="*60)
try:
    # 使用东财接口获取上证指数
    df = ak.stock_zh_index_daily_em(symbol="sh000001")
    print(f"[OK] 获取到 {len(df)} 条记录")
    print(f"列名: {list(df.columns)}")
    if len(df) > 0:
        print(f"\n最近3条数据:")
        print(df.tail(3).to_string())
except Exception as e:
    print(f"[FAIL] 失败: {e}")

print("\n" + "="*60)
print("测试3: index_zh_a_hist (新浪财经指数历史)")
print("="*60)
try:
    # 使用新浪接口获取上证指数
    df = ak.index_zh_a_hist(symbol="000001", period="daily", start_date="20260120", end_date="20260127")
    print(f"[OK] 获取到 {len(df)} 条记录")
    print(f"列名: {list(df.columns)}")
    if len(df) > 0:
        print(f"\n最近3条数据:")
        print(df.tail(3).to_string())
except Exception as e:
    print(f"[FAIL] 失败: {e}")

print("\n" + "="*60)
print("测试4: stock_zh_a_hist_163 (网易财经)")
print("="*60)
try:
    # 尝试获取上证指数的成交额
    df = ak.stock_zh_index_hist_163(symbol="000001", start_date="20260120", end_date="20260127")
    print(f"[OK] 获取到 {len(df)} 条记录")
    print(f"列名: {list(df.columns)}")
    if len(df) > 0:
        print(f"\n最近3条数据:")
        print(df.tail(3).to_string())
except Exception as e:
    print(f"[FAIL] 失败: {e}")

print("\n" + "="*60)
print("总结")
print("="*60)
print("查找能够提供成交额(amount/turnover/成交额)字段的API")
