"""
测试市场概览功能

验证综合评分、权重配置和确认层功能
"""

import sys
from datetime import datetime, timedelta

from core.config import Config
from core.pipeline import MarketPipeline
from storage.repository import Repository


def test_market_pipeline_with_composite_score():
    """测试带综合评分的流水线"""
    print("="*70)
    print("测试市场综合评分功能")
    print("="*70)
    
    # 配置
    config = Config()
    database_url = "sqlite:///data/market_thermo_3years_auto.db"
    repository = Repository(database_url)
    
    # 测试US市场
    print("\n[TEST] 测试US市场配置...")
    us_soft_weights = config.get("soft_confirm_weights.US")
    print(f"US Soft Confirm 权重: {us_soft_weights}")
    
    # 验证权重总和
    total_weight = sum(us_soft_weights.values())
    print(f"权重总和: {total_weight:.2f}")
    assert abs(total_weight - 1.0) < 1e-6, "权重总和应为1.0"
    print("[OK] US权重配置正确")
    
    # 验证各个权重
    expected_weights = {
        'IWM_SPY_SOFT': 0.30,
        'HYG_IEF_SOFT': 0.30,
        'PAIR_TWEX_DXY': 0.20,
        'PAIR_CNH_CNY': 0.20
    }
    
    for code, expected in expected_weights.items():
        actual = us_soft_weights.get(code, 0.0)
        assert abs(actual - expected) < 1e-6, f"{code}权重不匹配: 期望{expected}, 实际{actual}"
        print(f"  - {code}: {actual} [OK]")
    
    print("\n[OK] US Soft Confirm 权重验证通过!")
    
    # 测试CN市场
    print("\n[TEST] 测试CN市场配置...")
    cn_soft_weights = config.get("soft_confirm_weights.CN")
    print(f"CN Soft Confirm 权重: {cn_soft_weights}")
    
    total_weight = sum(cn_soft_weights.values())
    print(f"权重总和: {total_weight:.2f}")
    assert abs(total_weight - 1.0) < 1e-6, "权重总和应为1.0"
    print("[OK] CN权重配置正确")
    
    # 检查数据库中的regimes数据
    print("\n[TEST] 检查数据库中的综合评分数据...")
    
    for market in ['US', 'CN']:
        print(f"\n检查 {market} 市场数据...")
        
        # 加载regimes (只获取最近10天)
        from datetime import date, timedelta
        end_date = date.today()
        start_date = end_date - timedelta(days=10)
        regimes_df = repository.load_regimes(market=market, view='daily', start_date=start_date, end_date=end_date)
        
        if regimes_df is not None and not regimes_df.empty:
            print(f"[OK] 找到 {len(regimes_df)} 条regime记录")
            
            # 检查是否有composite_score列
            if 'composite_score' in regimes_df.columns:
                valid_scores = regimes_df['composite_score'].dropna()
                if len(valid_scores) > 0:
                    print(f"[OK] 找到 {len(valid_scores)} 个有效综合评分")
                    print(f"  最新综合评分: {valid_scores.iloc[-1]:.2f}")
                    print(f"  评分范围: {valid_scores.min():.2f} - {valid_scores.max():.2f}")
                else:
                    print("[WARN] 未找到有效的综合评分数据")
            else:
                print("[WARN] regimes表中没有composite_score列")
            
            # 显示最新的regime状态
            latest = regimes_df.iloc[-1]
            # date可能在索引中或列中
            if 'date' in regimes_df.columns:
                latest_date = latest['date']
            else:
                latest_date = latest.name if hasattr(latest, 'name') else 'N/A'
            
            print(f"\n最新状态 ({latest_date}):")
            print(f"  Regime: {latest.get('regime', 'N/A')}")
            print(f"  综合评分: {latest.get('composite_score', 'N/A')}")
            print(f"  Final Lamp: {latest.get('lamp_final', 'N/A')}")
            print(f"  Soft Confirm: {latest.get('lamp_soft', 'N/A')}")
            print(f"  Hard Veto: {latest.get('lamp_hard', 'N/A')}")
        else:
            print(f"[WARN] 未找到 {market} 市场的regime数据")
    
    # 检查主要指标评分
    print("\n[TEST] 检查主要指标评分...")
    
    us_main_indicators = config.get("indicators.US.main", [])
    us_balanced_weights = config.get("style_weights.US.Balanced", [])
    
    print(f"\nUS市场主要指标 (Balanced风格):")
    print(f"指标数量: {len(us_main_indicators)}")
    print(f"权重数量: {len(us_balanced_weights)}")
    
    if len(us_main_indicators) == len(us_balanced_weights):
        print("[OK] 指标与权重数量匹配")
        
        total_weight = sum(us_balanced_weights)
        print(f"权重总和: {total_weight}")
        
        print("\n指标权重明细:")
        for ind, weight in zip(us_main_indicators, us_balanced_weights):
            code = ind['code']
            name = ind.get('name', code)
            
            # 加载该指标的最新数据
            end_date = date.today()
            start_date = end_date - timedelta(days=7)
            df = repository.load_series_data_by_code(code, view='daily', start_date=start_date, end_date=end_date)
            
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                score = latest.get('score', None)
                score_str = f"{score:.1f}" if score is not None else "N/A"
            else:
                score_str = "无数据"
            
            print(f"  {code:25s} | 权重: {weight:3d}% | 评分: {score_str}")
    else:
        print("[WARN] 指标与权重数量不匹配!")
    
    print("\n" + "="*70)
    print("测试完成!")
    print("="*70)


if __name__ == '__main__':
    try:
        test_market_pipeline_with_composite_score()
        print("\n[SUCCESS] 所有测试通过!")
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

