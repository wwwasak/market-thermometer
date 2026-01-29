"""
诊断ETF_NETFLOW_5D数据获取逻辑

检查三年数据脚本和GUI手动获取是否使用相同的逻辑
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
sys.path.insert(0, str(Path(__file__).parent))

from core.config import Config
from core.datasource import DataSourceManager

print("="*80)
print("ETF_NETFLOW_5D 数据获取逻辑诊断")
print("="*80)

# 1. 检查配置
print("\n[1] 检查配置文件")
print("-"*80)
config = Config()
cn_observers = config.get('indicators.CN.observers', [])

etf_config = None
for obs in cn_observers:
    if obs.get('code') == 'ETF_NETFLOW_5D':
        etf_config = obs
        break

if etf_config:
    print(f"找到ETF_NETFLOW_5D配置:")
    print(f"  - code: {etf_config.get('code')}")
    print(f"  - name: {etf_config.get('name')}")
    print(f"  - source: {etf_config.get('source')}")
    print(f"  - symbol: {etf_config.get('symbol')}")
    print(f"  - transform: {etf_config.get('transform')}")
    print(f"  - role: {etf_config.get('role')}")
else:
    print("[ERROR] 未找到ETF_NETFLOW_5D配置")
    sys.exit(1)

# 2. 检查数据源管理器
print("\n[2] 检查数据源管理器")
print("-"*80)
ds_manager = DataSourceManager()
print(f"DataSourceManager已初始化")
print(f"  - akshare_fetcher: {ds_manager.akshare_fetcher is not None}")

# 3. 测试获取少量数据
print("\n[3] 测试获取最近7天数据")
print("-"*80)
end_date = datetime.now()
start_date = end_date - timedelta(days=7)

try:
    print(f"调用 fetch_by_config() ...")
    print(f"  - start_date: {start_date.date()}")
    print(f"  - end_date: {end_date.date()}")
    
    data = ds_manager.fetch_by_config(etf_config, start_date, end_date)
    
    if data is not None and len(data) > 0:
        print(f"\n[OK] 成功获取数据")
        print(f"  - 数据类型: {type(data)}")
        print(f"  - 数据长度: {len(data)}")
        print(f"  - 日期范围: {data.index.min().date()} 至 {data.index.max().date()}")
        print(f"\n  最近5条数据:")
        print(data.tail(5).to_string())
        
        # 检查数据特征
        print(f"\n  数据统计:")
        print(f"  - 均值: {data.mean():.2f}")
        print(f"  - 标准差: {data.std():.2f}")
        print(f"  - 最小值: {data.min():.2f}")
        print(f"  - 最大值: {data.max():.2f}")
    else:
        print(f"[WARNING] 未获取到数据或数据为空")
        
except Exception as e:
    print(f"[ERROR] 获取失败: {e}")
    import traceback
    traceback.print_exc()

# 4. 检查_fetch_etf_flow方法的实现
print("\n[4] 检查_fetch_etf_flow实现")
print("-"*80)
import inspect
from core.datasource import AKShareFetcher

akshare_fetcher = AKShareFetcher()
method_source = inspect.getsource(akshare_fetcher._fetch_etf_flow)

# 查找关键信息
print("检查方法中的关键特征:")
if "fund_etf_hist_em" in method_source:
    print("  ✓ 使用 fund_etf_hist_em API")
else:
    print("  ✗ 未使用 fund_etf_hist_em API")

if "rolling(window=5" in method_source:
    print("  ✓ 包含5日滚动和计算")
else:
    print("  ✗ 未包含5日滚动和计算")

if "weight" in method_source:
    print("  ✓ 使用加权汇总")
else:
    print("  ✗ 未使用加权汇总")

if "sign(涨跌幅)" in method_source or "sign" in method_source.lower():
    print("  ✓ 使用涨跌幅方向")
else:
    print("  ✗ 未使用涨跌幅方向")

# 提取ETF列表
print("\n检查ETF列表:")
lines = method_source.split('\n')
in_etf_list = False
for line in lines:
    if 'a500_etf_list = [' in line.lower():
        in_etf_list = True
    if in_etf_list:
        if 'code' in line and 'name' in line:
            print(f"  {line.strip()}")
        if ']' in line and in_etf_list and 'weight' in lines[lines.index(line)-1]:
            break

print("\n"+"="*80)
print("诊断完成")
print("="*80)
print("\n结论:")
print("1. 三年数据脚本（fetch_3years_data_auto.py）使用 DataSourceManager.fetch_by_config()")
print("2. GUI手动获取也使用 DataSourceManager.fetch_by_config()")
print("3. 两者都会调用 AKShareFetcher._fetch_etf_flow()")
print("4. 逻辑应该是一致的")
print("\n如果数据不一致，可能原因：")
print("  - 不同时间获取的数据（数据源更新）")
print("  - 网络问题导致部分ETF获取失败")
print("  - 数据库中保存的是旧逻辑的历史数据")
