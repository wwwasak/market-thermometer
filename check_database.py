"""
检查数据库中是否有数据
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from storage.repository import Repository

def check_db():
    db_path = 'sqlite:///data/market_thermo_3years_auto.db'
    repo = Repository(database_url=db_path)
    
    print("=" * 80)
    print("检查数据库")
    print("=" * 80)
    
    # 检查series_meta
    print("\n1. 检查指标元数据 (series_meta):")
    metas = repo.get_all_series_meta()
    if metas:
        print(f"   共 {len(metas)} 个指标")
        for meta in metas[:10]:
            print(f"   - {meta['code']}: {meta['name']}")
        if len(metas) > 10:
            print(f"   ... 还有 {len(metas)-10} 个")
    else:
        print("   [!] 没有指标元数据")
    
    # 检查series_data
    print("\n2. 检查时间序列数据 (series_data):")
    
    if metas:
        for meta in metas[:5]:  # 检查前5个
            code = meta['code']
            series_id = meta['id']
            
            data = repo.load_series_data(series_id=series_id, view='daily')
            
            if data is not None and len(data) > 0:
                print(f"   {code}: {len(data)} 条记录")
                
                # 检查各列
                has_raw = 'value_raw' in data.columns and data['value_raw'].notna().sum() > 0
                has_tr = 'value_tr' in data.columns and data['value_tr'].notna().sum() > 0
                has_score = 'score' in data.columns and data['score'].notna().sum() > 0
                
                print(f"      value_raw: {'✓' if has_raw else '✗'}")
                print(f"      value_tr:  {'✓' if has_tr else '✗'}")
                print(f"      score:     {'✓' if has_score else '✗'}")
            else:
                print(f"   {code}: [!] 没有数据")
    
    # 检查regimes
    print("\n3. 检查综合评分数据 (regimes):")
    for market in ['CN', 'US']:
        regimes = repo.load_regimes(market=market, view='daily')
        
        if regimes is not None and len(regimes) > 0:
            valid_comp = regimes['composite_score'].notna().sum()
            print(f"   {market}: {len(regimes)} 条记录, {valid_comp} 个有效综合评分")
            
            if valid_comp > 0:
                latest = regimes[regimes['composite_score'].notna()].iloc[-1]
                print(f"      最新: {latest.name.date()}, 评分: {latest['composite_score']:.2f}")
        else:
            print(f"   {market}: [!] 没有数据")

if __name__ == '__main__':
    check_db()

