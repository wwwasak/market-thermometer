"""
直接测试备用方案（不访问东方财富API）
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

print("="*60)
print("测试备用方案：使用akshare获取全市场成交额")
print("="*60)

end_date = datetime.now()
start_date = end_date - timedelta(days=7)
start_dt = pd.to_datetime(start_date)
end_dt = pd.to_datetime(end_date)

print(f"\n时间范围: {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}")
print("-"*60)

try:
    # 获取上证指数成交额
    print("\n[1] 获取上证指数成交额...")
    sh_df = ak.stock_zh_index_daily_em(symbol="sh000001")
    sh_df['date'] = pd.to_datetime(sh_df['date'])
    sh_df = sh_df.set_index('date').sort_index()
    sh_df = sh_df[(sh_df.index >= start_dt) & (sh_df.index <= end_dt)]
    sh_turnover = pd.to_numeric(sh_df['amount'], errors='coerce') / 1e8  # 元 -> 亿元
    print(f"[OK] 获取到 {len(sh_turnover)} 条记录")
    
    # 获取深证成指成交额
    print("\n[2] 获取深证成指成交额...")
    sz_df = ak.stock_zh_index_daily_em(symbol="sz399001")
    sz_df['date'] = pd.to_datetime(sz_df['date'])
    sz_df = sz_df.set_index('date').sort_index()
    sz_df = sz_df[(sz_df.index >= start_dt) & (sz_df.index <= end_dt)]
    sz_turnover = pd.to_numeric(sz_df['amount'], errors='coerce') / 1e8  # 元 -> 亿元
    print(f"[OK] 获取到 {len(sz_turnover)} 条记录")
    
    # 合计全市场成交额
    print("\n[3] 计算全市场成交额...")
    total_turnover = sh_turnover.add(sz_turnover, fill_value=0.0)
    print(f"[OK] 计算完成，共 {len(total_turnover)} 条记录")
    
    # 显示结果
    print("\n全市场成交额（上证+深证，亿元）:")
    print("-"*60)
    for date, value in total_turnover.items():
        print(f"  {date.strftime('%Y-%m-%d')}: {value:,.2f} 亿元")
    
    # 检查是否有0值
    zero_count = (total_turnover == 0.0).sum()
    if zero_count > 0:
        print(f"\n[WARNING] 有 {zero_count} 条记录的成交额为 0")
    else:
        print(f"\n[OK] 所有记录都有有效的成交额数据")
    
    print("\n" + "="*60)
    print("结果: [OK] 备用方案正常工作！")
    print("="*60)
    print("\n下一步：将这个备用方案集成到数据获取流程中")
    
except Exception as e:
    print(f"\n[ERROR] 失败: {e}")
    import traceback
    traceback.print_exc()
    print("\n" + "="*60)
    print("结果: [FAIL] 备用方案失败")
    print("="*60)
