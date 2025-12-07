"""
测试修复后的Pipeline
"""

from core.pipeline import MarketPipeline
from core.config import Config
from datetime import datetime, timedelta

def test_cn_pipeline():
    """测试CN市场pipeline"""
    print("="*70)
    print("测试CN市场Pipeline (1年数据)")
    print("="*70)
    
    config = Config()
    database_url = "sqlite:///data/market_thermo_3years_auto.db"
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    pipeline = MarketPipeline(market='CN', database_url=database_url, config=config)
    
    try:
        print(f"\n1. 获取数据 ({start_date.date()} 至 {end_date.date()})")
        raw_data = pipeline.fetch_all_data(start_date, end_date, incremental=False)
        print(f"   成功获取 {len(raw_data)} 个指标的数据")
        
        print(f"\n2. 转换数据")
        transformed_data = pipeline.transform_data(raw_data)
        print(f"   完成 {len(transformed_data)} 个指标的转换")
        
        print(f"\n3. 计算派生指标")
        raw_data, transformed_data = pipeline.calculate_derived_indicators(
            raw_data, transformed_data, start_date, end_date
        )
        
        print(f"\n4. 计算评分")
        scores, composite_score = pipeline.calculate_scores(transformed_data, view_type='daily')
        print(f"   评分DataFrame: {scores.shape}")
        print(f"   综合评分Series: {len(composite_score)}, 有效值: {composite_score.notna().sum()}")
        
        # 检查主要指标的评分
        main_indicators = [ind for ind in pipeline.indicators if ind.get('role') == 'main']
        print(f"\n主要指标评分统计:")
        for ind in main_indicators:
            code = ind['code']
            score_col = f"{code}_score"
            if score_col in scores.columns:
                score_series = scores[score_col]
                valid = score_series.notna().sum()
                print(f"   {code:30s}: {valid}/{len(score_series)} 个有效值")
                if valid > 0:
                    print(f"      范围: {score_series.min():.2f} - {score_series.max():.2f}")
        
        print(f"\n5. 保存到数据库")
        
        # 应用确认层
        confirm_results = pipeline.apply_confirm_layer(scores, composite_score, view_type='daily')
        
        # 保存
        saved = pipeline.save_to_database(
            raw_data=raw_data,
            transformed_data=transformed_data,
            scores=scores,
            confirm_results=confirm_results,
            view_type='daily'
        )
        
        print(f"   保存了 {saved} 条记录")
        
        print(f"\n✓ CN市场测试完成！")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_saved_data():
    """验证保存的数据"""
    print("\n" + "="*70)
    print("验证保存的数据")
    print("="*70)
    
    from storage.repository import Repository
    database_url = "sqlite:///data/market_thermo_3years_auto.db"
    repo = Repository(database_url)
    
    # 检查CN_MARGIN_SLOPE
    code = "CN_MARGIN_SLOPE"
    df = repo.load_series_data_by_code(code, view='daily')
    
    if df is not None and not df.empty:
        print(f"\n{code}:")
        print(f"  总记录数: {len(df)}")
        print(f"  有score的记录数: {df['score'].notna().sum()}")
        print(f"  有z的记录数: {df['z'].notna().sum()}")
        
        if df['score'].notna().sum() > 0:
            print(f"  最新5条记录:")
            print(df[['value_tr', 'z', 'score']].tail())
        else:
            print(f"  [WARN] 没有评分数据！")
    
    # 检查综合评分
    regimes_df = repo.load_regimes(market='CN', view='daily')
    
    if regimes_df is not None and not regimes_df.empty:
        print(f"\nCN市场综合评分:")
        print(f"  总记录数: {len(regimes_df)}")
        print(f"  有composite_score的记录数: {regimes_df['composite_score'].notna().sum()}")
        
        if regimes_df['composite_score'].notna().sum() > 0:
            print(f"  评分范围: {regimes_df['composite_score'].min():.2f} - {regimes_df['composite_score'].max():.2f}")
            print(f"\n  最新5条记录:")
            print(regimes_df[['composite_score', 'regime', 'lamp_final']].tail())
        else:
            print(f"  [WARN] 没有综合评分数据！")


if __name__ == '__main__':
    success = test_cn_pipeline()
    
    if success:
        verify_saved_data()
    
    print("\n" + "="*70)
    print("测试完成！")
    print("="*70)

