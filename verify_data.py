"""
验证数据库中的数据
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from storage.repository import Repository

def verify():
    db_path = 'sqlite:///data/market_thermo_3years_auto.db'
    repo = Repository(database_url=db_path)
    
    print("=" * 80)
    print("验证数据库数据")
    print("=" * 80)
    
    # 检查CN市场的主要指标
    cn_indicators = [
        'CN_MARGIN_SLOPE',
        'CNH_PCT20',
        'NORTH_TURNOVER_SHARE',
        'CSI1000_OVER_300_REL20',
        'PMI_NEWORDER_YOY_STD',
        'CN_EPS_YIELD_MINUS_CGB10'
    ]
    
    print("\nCN市场主要指标数据:")
    print("-" * 80)
    
    for code in cn_indicators:
        meta = repo.get_series_meta_by_code(code)
        if not meta:
            print(f"  {code}: [未找到元数据]")
            continue
        
        series_id = meta['id']
        data = repo.load_series_data(series_id=series_id, view='daily')
        
        if data is None or len(data) == 0:
            print(f"  {code}: [无数据]")
        else:
            # 统计各列
            raw_count = data['value_raw'].notna().sum() if 'value_raw' in data.columns else 0
            tr_count = data['value_tr'].notna().sum() if 'value_tr' in data.columns else 0
            score_count = data['score'].notna().sum() if 'score' in data.columns else 0
            
            print(f"  {code}:")
            print(f"    总记录: {len(data)}, 日期: {data.index.min().date()} 至 {data.index.max().date()}")
            print(f"    value_raw: {raw_count}, value_tr: {tr_count}, score: {score_count}")
    
    # 检查综合评分
    print("\n" + "=" * 80)
    print("CN市场综合评分:")
    print("-" * 80)
    
    regimes = repo.load_regimes(market='CN', view='daily')
    
    if regimes is None or len(regimes) == 0:
        print("  [无综合评分数据]")
    else:
        valid_comp = regimes['composite_score'].notna().sum()
        print(f"  总记录: {len(regimes)}")
        print(f"  有效综合评分: {valid_comp}")
        
        if valid_comp > 0:
            comp_data = regimes[regimes['composite_score'].notna()]
            print(f"  日期范围: {comp_data.index.min().date()} 至 {comp_data.index.max().date()}")
            print(f"  评分范围: {comp_data['composite_score'].min():.2f} - {comp_data['composite_score'].max():.2f}")
            
            print(f"\n  最后10个综合评分:")
            for idx, row in comp_data.tail(10).iterrows():
                score = row['composite_score']
                print(f"    {idx.date()}: {score:.2f}")

if __name__ == '__main__':
    verify()

