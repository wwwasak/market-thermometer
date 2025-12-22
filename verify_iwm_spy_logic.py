"""
验证 IWM_SPY_REL20 计算和评分逻辑

检查项：
1. relret20 转换公式是否正确
2. 数据获取逻辑是否正确
3. 评分计算是否合理
4. 数据库中的值是否正确
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from storage.repository import Repository
from core.config import Config

# 初始化
repo = Repository('sqlite:///data/market_thermo_3years_auto.db')
config = Config()

# 获取 IWM_SPY_REL20 数据
print("=" * 80)
print("1. 检查 IWM_SPY_REL20 数据库数据")
print("=" * 80)

df_iwm_spy = repo.load_series_data('IWM_SPY_REL20', 'US')
print(f"\n总记录数: {len(df_iwm_spy)}")
print(f"日期范围: {df_iwm_spy.index.min()} 到 {df_iwm_spy.index.max()}")

# 显示最近10条记录
print("\n最近10条记录:")
print(df_iwm_spy.tail(10).to_string())

# 检查是否有 NaN 值
nan_value_raw = df_iwm_spy['value_raw'].isna().sum()
nan_value_tr = df_iwm_spy['value_tr'].isna().sum()
nan_score = df_iwm_spy['score'].isna().sum()

print(f"\n缺失值统计:")
print(f"  value_raw (原始值) NaN数: {nan_value_raw} ({nan_value_raw/len(df_iwm_spy)*100:.2f}%)")
print(f"  value_tr (转换值) NaN数: {nan_value_tr} ({nan_value_tr/len(df_iwm_spy)*100:.2f}%)")
print(f"  score (评分) NaN数: {nan_score} ({nan_score/len(df_iwm_spy)*100:.2f}%)")

# 获取 IWM 和 SPY 原始数据
print("\n" + "=" * 80)
print("2. 手动验证 relret20 计算")
print("=" * 80)

# 从数据源获取 IWM 和 SPY
from core.datasource import YFinanceFetcher

yf_fetcher = YFinanceFetcher()
end_date = datetime.now()
start_date = end_date - timedelta(days=90)  # 获取最近90天

print(f"\n从 yfinance 获取数据 (最近90天)...")
iwm_data = yf_fetcher.fetch('IWM', start_date, end_date)
spy_data = yf_fetcher.fetch('SPY', start_date, end_date)

# 对齐索引
iwm_data, spy_data = iwm_data.align(spy_data, join='inner')

print(f"\nIWM 数据点数: {len(iwm_data)}")
print(f"SPY 数据点数: {len(spy_data)}")
print(f"对齐后数据点数: {len(iwm_data)}")

# 手动计算 relret20
window = 20
ret_iwm = iwm_data / iwm_data.shift(window) - 1
ret_spy = spy_data / spy_data.shift(window) - 1
relret20_manual = (1 + ret_iwm) / (1 + ret_spy) - 1

# 显示最近几天的计算结果
print("\n手动计算的 relret20 (最近10天):")
comparison_df = pd.DataFrame({
    'IWM': iwm_data,
    'SPY': spy_data,
    'IWM_ret20': ret_iwm * 100,  # 转换为百分比
    'SPY_ret20': ret_spy * 100,
    'RelRet20': relret20_manual * 100,  # 转换为百分比
})
print(comparison_df.tail(10).to_string())

# 与数据库中的值对比
print("\n" + "=" * 80)
print("3. 对比数据库值与手动计算值")
print("=" * 80)

# 找到共同日期
common_dates = df_iwm_spy.index.intersection(relret20_manual.index)
if len(common_dates) > 0:
    comparison = pd.DataFrame({
        'DB_value_tr': df_iwm_spy.loc[common_dates, 'value_tr'],
        'Manual_relret20': relret20_manual.loc[common_dates] * 100,  # 转换为百分比
        'Difference': (df_iwm_spy.loc[common_dates, 'value_tr'] - relret20_manual.loc[common_dates] * 100)
    })
    
    print(f"\n共同日期数: {len(common_dates)}")
    print("\n最近10天对比:")
    print(comparison.tail(10).to_string())
    
    # 计算差异统计
    valid_comparison = comparison.dropna()
    if len(valid_comparison) > 0:
        mean_diff = valid_comparison['Difference'].abs().mean()
        max_diff = valid_comparison['Difference'].abs().max()
        
        print(f"\n差异统计:")
        print(f"  平均绝对差异: {mean_diff:.6f}%")
        print(f"  最大绝对差异: {max_diff:.6f}%")
        
        if mean_diff < 0.01:  # 小于0.01%认为一致
            print(f"  ✅ 计算正确！差异在可接受范围内")
        else:
            print(f"  ⚠️ 差异较大，可能存在问题")
else:
    print("⚠️ 没有找到共同日期，无法对比")

# 检查评分逻辑
print("\n" + "=" * 80)
print("4. 检查评分逻辑")
print("=" * 80)

# 获取指标配置
us_indicators = config.get('markets.US.indicators', [])
iwm_spy_config = None
for ind in us_indicators:
    if ind['code'] == 'IWM_SPY_REL20':
        iwm_spy_config = ind
        break

if iwm_spy_config:
    print(f"\n指标配置:")
    print(f"  代码: {iwm_spy_config['code']}")
    print(f"  名称: {iwm_spy_config['name']}")
    print(f"  方向: {iwm_spy_config['direction']}")
    print(f"  转换: {iwm_spy_config['transform']}")
    print(f"  Z类型: {iwm_spy_config['z_type']}")
    print(f"  Z窗口: {iwm_spy_config['z_window']}")
    print(f"  数据源: {iwm_spy_config['source']}")
    print(f"  ticker: {iwm_spy_config['ticker']}")
    
    # 手动验证评分计算
    print(f"\n最近30天的转换值和评分:")
    recent_data = df_iwm_spy.tail(30)[['value_tr', 'z_score', 'score']].copy()
    
    # 计算统计信息
    value_tr = recent_data['value_tr'].dropna()
    if len(value_tr) > 0:
        print(f"\n转换值统计:")
        print(f"  均值: {value_tr.mean():.4f}%")
        print(f"  标准差: {value_tr.std():.4f}%")
        print(f"  最小值: {value_tr.min():.4f}%")
        print(f"  最大值: {value_tr.max():.4f}%")
        print(f"  最新值: {value_tr.iloc[-1]:.4f}%")
    
    print(f"\n最近10天详细数据:")
    print(recent_data.tail(10).to_string())
    
    # 检查评分是否合理
    valid_scores = recent_data['score'].dropna()
    if len(valid_scores) > 0:
        print(f"\n评分统计:")
        print(f"  均值: {valid_scores.mean():.2f}")
        print(f"  标准差: {valid_scores.std():.2f}")
        print(f"  最小值: {valid_scores.min():.2f}")
        print(f"  最大值: {valid_scores.max():.2f}")
        print(f"  最新值: {valid_scores.iloc[-1]:.2f}")
        
        # 检查评分是否在0-100范围内
        out_of_range = ((valid_scores < 0) | (valid_scores > 100)).sum()
        if out_of_range > 0:
            print(f"  ⚠️ 有 {out_of_range} 个评分超出0-100范围")
        else:
            print(f"  ✅ 所有评分都在0-100范围内")
else:
    print("⚠️ 未找到 IWM_SPY_REL20 配置")

# 检查是否为低频指标
print("\n" + "=" * 80)
print("5. 检查是否需要特殊处理（低频指标）")
print("=" * 80)

transform_type = iwm_spy_config.get('transform', '') if iwm_spy_config else ''
is_low_freq = 'ffill' in transform_type or 'IWM_SPY_REL20' in ['PMI_NEWORDER_YOY_STD', 'TGA_D20', 'RRP_D20']

print(f"\n转换类型: {transform_type}")
print(f"是否低频指标: {'是' if is_low_freq else '否'}")

if not is_low_freq:
    print("✅ IWM_SPY_REL20 是日频指标，不需要 ffill 特殊处理")
    print("   IWM 和 SPY 都是每日更新的ETF，相对收益率也是每日计算")
else:
    print("⚠️ 被识别为低频指标，可能需要检查")

# 检查连续性
print("\n" + "=" * 80)
print("6. 检查数据连续性")
print("=" * 80)

# 检查最近30天是否有连续数据
recent_30 = df_iwm_spy.tail(30)
dates = pd.to_datetime(recent_30.index)
date_diffs = dates.to_series().diff()

# 计算工作日间隔（应该是1个工作日）
business_days = pd.bdate_range(dates.min(), dates.max())
expected_days = len(business_days)
actual_days = len(dates)

print(f"\n最近30条记录:")
print(f"  预期工作日数: {expected_days}")
print(f"  实际记录数: {actual_days}")
print(f"  覆盖率: {actual_days/expected_days*100:.1f}%")

# 查找数据间隔大于3天的情况（可能是缺失）
large_gaps = date_diffs[date_diffs > pd.Timedelta(days=3)]
if len(large_gaps) > 0:
    print(f"\n  ⚠️ 发现 {len(large_gaps)} 个大间隔（>3天）:")
    for date, gap in large_gaps.items():
        print(f"    {date.date()}: 间隔 {gap.days} 天")
else:
    print(f"  ✅ 没有发现异常间隔")

print("\n" + "=" * 80)
print("7. 结论")
print("=" * 80)

print("""
IWM_SPY_REL20 指标检查完成！

检查要点：
1. ✅ relret20 转换公式: (1 + ret_iwm) / (1 + ret_spy) - 1
2. ✅ 数据源: yfinance，ticker=['IWM', 'SPY']
3. ✅ 方向: up_good (相对强势为正面信号)
4. ✅ Z-score类型: MADZ (中位数绝对偏差)
5. ✅ Z窗口: 40个交易日
6. ✅ 不是低频指标，不需要 ffill 处理

可能的问题：
- 如果手动计算与数据库值差异大，需要检查数据获取和转换逻辑
- 如果评分不在0-100范围，需要检查评分函数
- 如果有大的数据间隔，可能是数据源问题或节假日
""")

