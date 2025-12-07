"""
测试评分数据显示

验证评分计算和数据加载是否正常
"""

import pandas as pd
from storage.repository import Repository
from core.config import Config

def test_score_data():
    """测试评分数据"""
    print("="*70)
    print("测试评分数据加载")
    print("="*70)
    
    database_url = "sqlite:///data/market_thermo_3years_auto.db"
    repository = Repository(database_url)
    config = Config()
    
    # 测试CN市场
    for market in ['CN', 'US']:
        print(f"\n{'='*70}")
        print(f"测试 {market} 市场")
        print(f"{'='*70}")
        
        # 获取主要指标配置
        main_indicators = config.get(f"indicators.{market}.main", [])
        print(f"\n主要指标数量: {len(main_indicators)}")
        
        # 检查每个指标的数据
        for ind in main_indicators:
            code = ind['code']
            name = ind.get('name', code)
            
            # 加载数据
            df = repository.load_series_data_by_code(code, view='daily')
            
            if df is not None and not df.empty:
                # 检查是否有评分数据
                has_score = 'score' in df.columns
                has_z = 'z' in df.columns
                
                if has_score:
                    score_count = df['score'].notna().sum()
                    latest_score = df['score'].dropna().iloc[-1] if score_count > 0 else None
                else:
                    score_count = 0
                    latest_score = None
                
                print(f"\n{code} ({name}):")
                print(f"  总记录数: {len(df)}")
                print(f"  有评分数据: {'是' if has_score else '否'}")
                print(f"  评分记录数: {score_count}")
                if latest_score is not None:
                    print(f"  最新评分: {latest_score:.1f}")
                else:
                    print(f"  最新评分: N/A")
                
                if has_z:
                    z_count = df['z'].notna().sum()
                    print(f"  Z分数记录数: {z_count}")
                
                # 显示最后几条数据
                if has_score and score_count > 0:
                    print(f"\n  最近3条数据:")
                    recent = df[['value_raw', 'value_tr', 'z', 'score']].tail(3)
                    for idx, row in recent.iterrows():
                        raw_val = f"{row['value_raw']:.2f}" if pd.notna(row['value_raw']) else 'N/A'
                        z_val = f"{row['z']:.2f}" if pd.notna(row['z']) else 'N/A'
                        score_val = f"{row['score']:.1f}" if pd.notna(row['score']) else 'N/A'
                        print(f"    {idx.date()}: raw={raw_val}, z={z_val}, score={score_val}")
            else:
                print(f"\n{code}: 无数据")
        
        # 检查综合评分
        print(f"\n{'='*70}")
        print("检查综合评分数据")
        print(f"{'='*70}")
        
        regimes_df = repository.load_regimes(market=market, view='daily')
        
        if regimes_df is not None and not regimes_df.empty:
            print(f"Regime记录数: {len(regimes_df)}")
            print(f"列名: {list(regimes_df.columns)}")
            
            if 'composite_score' in regimes_df.columns:
                comp_scores = regimes_df['composite_score'].dropna()
                if len(comp_scores) > 0:
                    print(f"综合评分记录数: {len(comp_scores)}")
                    print(f"最新综合评分: {comp_scores.iloc[-1]:.1f}")
                    print(f"评分范围: {comp_scores.min():.1f} - {comp_scores.max():.1f}")
                    
                    print(f"\n最近5条综合评分:")
                    recent_regimes = regimes_df.tail(5)
                    for _, row in recent_regimes.iterrows():
                        date_val = row.get('date', 'N/A')
                        score = row.get('composite_score', None)
                        regime = row.get('regime', 'N/A')
                        lamp = row.get('lamp_final', 'N/A')
                        
                        if score is not None and pd.notna(score):
                            score_str = f"{score:.1f}"
                        else:
                            score_str = "N/A"
                        
                        print(f"  {date_val}: score={score_str}, regime={regime}, lamp={lamp}")
                else:
                    print("[WARN] 综合评分列存在但全部为空")
            else:
                print("[WARN] 没有 composite_score 列")
        else:
            print(f"[WARN] 没有找到 {market} 市场的regime数据")


if __name__ == '__main__':
    try:
        test_score_data()
        print("\n" + "="*70)
        print("测试完成！")
        print("="*70)
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()

