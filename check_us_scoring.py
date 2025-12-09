"""
检查US市场指标评分问题
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from storage.repository import Repository

def check_indicator(repo, code):
    """检查单个指标的数据和评分情况"""
    print(f"\n{'='*80}")
    print(f"指标: {code}")
    print(f"{'='*80}")
    
    meta = repo.get_series_meta_by_code(code)
    if not meta:
        print(f"  [ERROR] 未找到指标")
        return
    
    series_id = meta['id']
    data = repo.load_series_data(series_id=series_id, view='daily')
    
    if data is None or len(data) == 0:
        print(f"  [ERROR] 无数据")
        return
    
    print(f"\n基本信息:")
    print(f"  总记录数: {len(data)}")
    print(f"  日期范围: {data.index.min().date()} 至 {data.index.max().date()}")
    
    # 检查各个字段
    for col in ['value_raw', 'value_tr', 'z', 'score']:
        if col in data.columns:
            valid_count = data[col].notna().sum()
            valid_pct = valid_count / len(data) * 100
            print(f"  {col}: {valid_count}/{len(data)} 有效 ({valid_pct:.1f}%)")
            
            if valid_count > 0:
                print(f"    范围: {data[col].min():.4f} ~ {data[col].max():.4f}")
                
                # 检查是否全部为NaN或0
                if valid_count == 0:
                    print(f"    [ERROR] 全部为NaN!")
                elif (data[col].dropna() == 0).all():
                    print(f"    [WARN] 全部为0!")
                    
                # 显示最近5个非NaN值
                recent_valid = data[col].dropna().tail(5)
                if len(recent_valid) > 0:
                    print(f"    最近5个值:")
                    for idx, val in recent_valid.items():
                        print(f"      {idx.date()}: {val:.4f}")
            else:
                print(f"    [ERROR] 无有效数据!")
                
                # 如果value_tr无效，检查value_raw
                if col == 'value_tr' and 'value_raw' in data.columns:
                    raw_valid = data['value_raw'].notna().sum()
                    print(f"    value_raw有效数: {raw_valid}")
                    
                    if raw_valid > 0:
                        print(f"    [诊断] value_raw有数据，但value_tr全是NaN")
                        print(f"    可能原因: transform计算失败")
        else:
            print(f"  {col}: 列不存在")

def main():
    db_path = 'sqlite:///data/market_thermo_3years_auto.db'
    repo = Repository(database_url=db_path)
    
    print("="*80)
    print("US市场指标评分诊断")
    print("="*80)
    
    # 检查有问题的指标
    problem_indicators = [
        'RRP_D20',      # 0条评分
        'DFII10',       # 10条评分
        'DTWEXBGS',     # 30条评分
        'TGA_D20',      # 检查一下这个
    ]
    
    for code in problem_indicators:
        check_indicator(repo, code)
    
    # 对比一个正常的指标
    print(f"\n{'='*80}")
    print("对比：正常指标")
    print(f"{'='*80}")
    check_indicator(repo, 'VIX_LOG')

if __name__ == '__main__':
    main()

