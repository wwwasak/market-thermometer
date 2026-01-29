"""
测试修复后的北向资金流向数据获取（包括成交额占比）
"""
import sys
from datetime import datetime, timedelta
from core.datasource import AKShareFetcher

print("="*60)
print("测试修复后的 NORTH_TURNOVER_SHARE 数据获取")
print("="*60)

# 创建AKShareFetcher实例
fetcher = AKShareFetcher()

# 测试获取最近7天的北向资金数据
end_date = datetime.now()
start_date = end_date - timedelta(days=7)

print(f"\n获取时间范围: {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}")
print("-"*60)

try:
    # 调用_fetch_north_flow方法
    result_df = fetcher._fetch_north_flow(
        start_date=start_date.strftime('%Y%m%d'),
        end_date=end_date.strftime('%Y%m%d')
    )
    
    print(f"\n获取结果:")
    print("-"*60)
    print(result_df.to_string())
    
    # 检查value_tr是否为0
    print(f"\n数据质量检查:")
    print("-"*60)
    zero_count = (result_df['value_tr'] == 0.0).sum()
    total_count = len(result_df)
    
    if zero_count == total_count:
        print(f"[ERROR] 所有 value_tr 都是 0！ ({zero_count}/{total_count})")
        print("这意味着备用方案也失败了，或者全市场成交额为0")
    elif zero_count > 0:
        print(f"[WARNING] 有 {zero_count}/{total_count} 条记录的 value_tr 为 0")
    else:
        print(f"[OK] 所有 value_tr 都有有效值！")
    
    # 显示统计信息
    print(f"\n统计信息:")
    print("-"*60)
    print(f"value_raw (北向成交额,亿元):")
    print(f"  最小值: {result_df['value_raw'].min():,.2f}")
    print(f"  最大值: {result_df['value_raw'].max():,.2f}")
    print(f"  平均值: {result_df['value_raw'].mean():,.2f}")
    print(f"\nvalue_tr (北向成交占比):")
    print(f"  最小值: {result_df['value_tr'].min():.6f}")
    print(f"  最大值: {result_df['value_tr'].max():.6f}")
    print(f"  平均值: {result_df['value_tr'].mean():.6f}")
    
    print("\n" + "="*60)
    if zero_count == 0:
        print("结果: [OK] 修复成功！NORTH_TURNOVER_SHARE 现在有有效的占比数据")
    else:
        print("结果: [FAIL] 仍有问题，需要进一步调查")
    print("="*60)
    
except Exception as e:
    print(f"\n[ERROR] 测试失败: {e}")
    import traceback
    traceback.print_exc()
    print("\n" + "="*60)
    print("结果: [FAIL] 测试过程中出现异常")
    print("="*60)
