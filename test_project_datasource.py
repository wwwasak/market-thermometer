"""
模拟项目代码的数据获取流程

测试datasource.py的YFinanceFetcher
"""

import sys
sys.path.insert(0, '.')

from datetime import datetime, timedelta
from core.datasource import DataSourceManager
import pandas as pd

print("=" * 80)
print("测试项目的数据获取流程")
print("=" * 80)
print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# 创建数据源管理器
dsm = DataSourceManager()

# 模拟IWM_SPY_REL20的配置
indicator_config = {
    'code': 'IWM_SPY_REL20',
    'name': 'IWM/SPY 20日相对收益',
    'source': 'yfinance',
    'ticker': ['IWM', 'SPY'],  # 注意：是列表
    'transform': 'relret20'
}

# 设置日期范围（模拟增量获取）
end_date = datetime.now()
start_date = end_date - timedelta(days=30)  # 最近30天

print("步骤1: 使用项目的DataSourceManager获取数据")
print("-" * 80)
print(f"配置: {indicator_config}")
print(f"日期范围: {start_date.date()} 至 {end_date.date()}\n")

try:
    # 使用项目代码获取数据
    data = dsm.fetch_by_config(indicator_config, start_date, end_date)
    
    print(f"[OK] 获取成功")
    print(f"    数据类型: {type(data)}")
    
    if isinstance(data, tuple):
        print(f"    tuple长度: {len(data)}")
        for i, s in enumerate(data):
            print(f"\n    Series {i}:")
            print(f"      长度: {len(s)}")
            print(f"      日期范围: {s.index[0]} 至 {s.index[-1]}")
            print(f"      最后3条:")
            print(s.tail(3))
            
            # 检查12月26日
            target_date = pd.Timestamp('2025-12-26')
            if target_date in s.index:
                print(f"      [OK] 有12月26日数据: {s.loc[target_date]}")
            else:
                print(f"      [ERROR] 没有12月26日数据")
                print(f"      最新日期: {s.index[-1]}")
    
    elif isinstance(data, pd.Series):
        print(f"    Series长度: {len(data)}")
        print(f"    日期范围: {data.index[0]} 至 {data.index[-1]}")
        print(f"    最后5条:")
        print(data.tail(5))
        
        # 检查12月26日
        target_date = pd.Timestamp('2025-12-26')
        if target_date in data.index:
            print(f"\n    [OK] 有12月26日数据: {data.loc[target_date]}")
        else:
            print(f"\n    [ERROR] 没有12月26日数据")
            print(f"    最新日期: {data.index[-1]}")
    
    else:
        print(f"    未知数据类型")
    
    # 步骤2: 如果是tuple，手动计算relret20看看
    if isinstance(data, tuple) and len(data) == 2:
        print("\n" + "=" * 80)
        print("步骤2: 手动计算relret20")
        print("-" * 80)
        
        iwm_series, spy_series = data
        
        # 对齐
        iwm_series, spy_series = iwm_series.align(spy_series, join='inner')
        
        print(f"对齐后长度: IWM={len(iwm_series)}, SPY={len(spy_series)}")
        
        # 计算relret20
        iwm_ret20 = iwm_series / iwm_series.shift(20) - 1
        spy_ret20 = spy_series / spy_series.shift(20) - 1
        relret20 = (1 + iwm_ret20) / (1 + spy_ret20) - 1
        
        print(f"relret20计算完成，长度: {len(relret20)}")
        print(f"最后5条:")
        print(relret20.tail(5))
        
        # 检查12月26日
        target_date = pd.Timestamp('2025-12-26')
        if target_date in relret20.index:
            val = relret20.loc[target_date]
            if pd.notna(val):
                print(f"\n[OK] 12月26日relret20: {val:.6f}")
            else:
                print(f"\n[ERROR] 12月26日relret20是NaN")
        else:
            print(f"\n[ERROR] relret20中没有12月26日")
            print(f"最新日期: {relret20.index[-1]}")
    
    print("\n" + "=" * 80)
    print("结论")
    print("=" * 80)
    
    if isinstance(data, tuple):
        print("\n项目代码返回的是tuple（两个Series）")
        print("这是正确的，因为配置中ticker是列表")
        
        # 检查两个Series是否都有12月26日
        has_26_0 = pd.Timestamp('2025-12-26') in data[0].index
        has_26_1 = pd.Timestamp('2025-12-26') in data[1].index
        
        if has_26_0 and has_26_1:
            print("\n✓ 两个Series都有12月26日数据")
            print("  问题可能在transform_data或save_data阶段")
        else:
            print(f"\n✗ Series缺少12月26日数据")
            print(f"  Series 0有12月26日: {has_26_0}")
            print(f"  Series 1有12月26日: {has_26_1}")
            print(f"  问题在数据获取阶段")
    
except Exception as e:
    print(f"\n[ERROR] 获取失败: {e}")
    import traceback
    traceback.print_exc()

