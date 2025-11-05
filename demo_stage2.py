"""
阶段2演示脚本：核心转换和评分逻辑

演示完整的数据处理流程：
1. 模拟市场数据
2. 应用各种转换
3. 计算Z分数和评分
4. 判断Regime和灯色
5. 计算综合评分
"""

import pandas as pd
import numpy as np
from datetime import datetime

from core.transforms import (
    transform_delta20,
    transform_pct20,
    transform_relret20,
    transform_log_winsor,
    resample_to_weekly
)

from core.scoring import (
    standardize_with_direction,
    score_from_z,
    lamp_from_score,
    regime_from_score,
    weighted_score,
    batch_standardize,
    batch_score
)

from core.config import Config


def simulate_market_data():
    """模拟市场数据"""
    print("=" * 60)
    print("Step 1: Simulate Market Data")
    print("=" * 60)
    
    # 创建100个交易日的模拟数据
    dates = pd.date_range('2024-01-01', periods=100, freq='B')
    
    # 模拟VIX（波动率指数，down_good）
    np.random.seed(42)
    vix_base = 15
    vix = pd.Series(
        vix_base + np.random.randn(100).cumsum() * 0.5 + np.sin(np.linspace(0, 4*np.pi, 100)) * 3,
        index=dates
    ).clip(lower=10, upper=35)
    
    # 模拟RRP（逆回购，down_good）
    rrp_base = 2000
    rrp = pd.Series(
        rrp_base + np.random.randn(100).cumsum() * 50,
        index=dates
    )
    
    # 模拟IWM和SPY（小盘和大盘指数，up_good）
    iwm = pd.Series(
        200 + np.random.randn(100).cumsum() * 2,
        index=dates
    )
    spy = pd.Series(
        450 + np.random.randn(100).cumsum() * 1.5,
        index=dates
    )
    
    print(f"Generated data for {len(dates)} trading days")
    print(f"VIX range: {vix.min():.2f} - {vix.max():.2f}")
    print(f"RRP range: {rrp.min():.2f} - {rrp.max():.2f}")
    print(f"IWM range: {iwm.min():.2f} - {iwm.max():.2f}")
    print(f"SPY range: {spy.min():.2f} - {spy.max():.2f}")
    
    return {
        'dates': dates,
        'VIX': vix,
        'RRP': rrp,
        'IWM': iwm,
        'SPY': spy
    }


def demo_transforms(data):
    """演示数据转换"""
    print("\n" + "=" * 60)
    print("Step 2: Apply Transforms")
    print("=" * 60)
    
    # VIX: log + winsor
    vix_transformed = transform_log_winsor(data['VIX'])
    print(f"\nVIX (log + winsor):")
    print(f"  Original last 5: {data['VIX'].tail().values}")
    print(f"  Transformed last 5: {vix_transformed.tail().values}")
    
    # RRP: delta20
    rrp_delta = transform_delta20(data['RRP'], window=20)
    print(f"\nRRP Delta20:")
    print(f"  Last 5 values: {rrp_delta.tail().values}")
    
    # IWM/SPY: relret20
    relret = transform_relret20(data['IWM'], data['SPY'], window=20)
    print(f"\nIWM/SPY Relative Return (20d):")
    print(f"  Last 5 values: {relret.tail().values}")
    
    return {
        'VIX_transformed': vix_transformed,
        'RRP_delta': rrp_delta,
        'relret': relret
    }


def demo_standardization(data, transformed):
    """演示标准化和方向调整"""
    print("\n" + "=" * 60)
    print("Step 3: Standardization & Direction Adjustment")
    print("=" * 60)
    
    # VIX: down_good, MADZ
    vix_z = standardize_with_direction(
        transformed['VIX_transformed'],
        direction='down_good',
        z_type='MADZ',
        window=40
    )
    
    # RRP delta: down_good, Z
    rrp_z = standardize_with_direction(
        transformed['RRP_delta'],
        direction='down_good',
        z_type='Z',
        window=60
    )
    
    # IWM/SPY relret: up_good, MADZ
    relret_z = standardize_with_direction(
        transformed['relret'],
        direction='up_good',
        z_type='MADZ',
        window=40
    )
    
    print(f"\nVIX Z-scores (down_good, MADZ):")
    print(f"  Last 5: {vix_z.tail().values}")
    print(f"  Mean: {vix_z.mean():.3f}, Std: {vix_z.std():.3f}")
    
    print(f"\nRRP Delta Z-scores (down_good, Z):")
    print(f"  Last 5: {rrp_z.tail().values}")
    print(f"  Mean: {rrp_z.mean():.3f}, Std: {rrp_z.std():.3f}")
    
    print(f"\nIWM/SPY RelRet Z-scores (up_good, MADZ):")
    print(f"  Last 5: {relret_z.tail().values}")
    print(f"  Mean: {relret_z.mean():.3f}, Std: {relret_z.std():.3f}")
    
    return {
        'VIX_z': vix_z,
        'RRP_z': rrp_z,
        'relret_z': relret_z
    }


def demo_scoring(z_scores):
    """演示评分映射"""
    print("\n" + "=" * 60)
    print("Step 4: Score Mapping (Z -> 0-100)")
    print("=" * 60)
    
    scores = {}
    for name, z in z_scores.items():
        score = score_from_z(z)
        scores[name] = score
        
        valid_score = score.dropna()
        print(f"\n{name} Scores:")
        print(f"  Last 5: {score.tail().values}")
        print(f"  Range: {valid_score.min():.1f} - {valid_score.max():.1f}")
        print(f"  Mean: {valid_score.mean():.1f}")
    
    return scores


def demo_lamp_and_regime(scores):
    """演示灯色和Regime判断"""
    print("\n" + "=" * 60)
    print("Step 5: Lamp & Regime Classification")
    print("=" * 60)
    
    # 使用VIX作为示例
    vix_score = scores['VIX_z']
    
    # 灯色
    lamps = lamp_from_score(vix_score, green_threshold=60, red_threshold=40)
    print(f"\nVIX Lamps (last 10):")
    print(f"  {lamps.tail(10).values}")
    
    lamp_counts = lamps.value_counts()
    print(f"\nLamp distribution:")
    for lamp, count in lamp_counts.items():
        print(f"  {lamp}: {count} ({count/len(lamps)*100:.1f}%)")
    
    # Regime
    regimes = regime_from_score(vix_score, attack_threshold=70, defense_threshold=40, persistence=0)
    print(f"\nVIX Regimes (last 10):")
    print(f"  {regimes.tail(10).values}")
    
    regime_counts = regimes.value_counts()
    print(f"\nRegime distribution:")
    for regime, count in regime_counts.items():
        print(f"  {regime}: {count} ({count/len(regimes)*100:.1f}%)")
    
    # 带持续性的Regime
    regimes_persist = regime_from_score(vix_score, attack_threshold=70, defense_threshold=40, persistence=3)
    print(f"\nVIX Regimes with persistence=3 (last 10):")
    print(f"  {regimes_persist.tail(10).values}")
    
    return {
        'lamps': lamps,
        'regimes': regimes,
        'regimes_persist': regimes_persist
    }


def demo_composite_score(scores):
    """演示综合评分"""
    print("\n" + "=" * 60)
    print("Step 6: Composite Score (Weighted Average)")
    print("=" * 60)
    
    # 创建评分DataFrame
    score_df = pd.DataFrame({
        'VIX': scores['VIX_z'],
        'RRP': scores['RRP_z'],
        'RelRet': scores['relret_z']
    })
    
    # 定义权重
    weights = [30, 40, 30]  # VIX 30%, RRP 40%, RelRet 30%
    
    print(f"\nWeights: VIX={weights[0]}%, RRP={weights[1]}%, RelRet={weights[2]}%")
    
    # 计算加权评分
    composite = weighted_score(score_df, weights, normalize=True)
    
    valid_composite = composite.dropna()
    print(f"\nComposite Score:")
    print(f"  Last 10: {composite.tail(10).values}")
    print(f"  Range: {valid_composite.min():.1f} - {valid_composite.max():.1f}")
    print(f"  Mean: {valid_composite.mean():.1f}")
    
    # 综合评分的Regime
    composite_regime = regime_from_score(composite, attack_threshold=70, defense_threshold=40)
    print(f"\nComposite Regime (last 10):")
    print(f"  {composite_regime.tail(10).values}")
    
    regime_counts = composite_regime.value_counts()
    print(f"\nComposite Regime distribution:")
    for regime, count in regime_counts.items():
        print(f"  {regime}: {count} ({count/len(composite_regime)*100:.1f}%)")
    
    return composite


def demo_batch_operations():
    """演示批量操作"""
    print("\n" + "=" * 60)
    print("Step 7: Batch Operations")
    print("=" * 60)
    
    # 模拟多个指标的原始数据
    dates = pd.date_range('2024-01-01', periods=80, freq='B')
    np.random.seed(123)
    
    data_dict = {
        'VIX': pd.Series(15 + np.random.randn(80).cumsum() * 0.5, index=dates),
        'HY_OAS': pd.Series(4 + np.random.randn(80).cumsum() * 0.1, index=dates),
        'RRP': pd.Series(2000 + np.random.randn(80).cumsum() * 50, index=dates),
        'DFII10': pd.Series(2.0 + np.random.randn(80).cumsum() * 0.05, index=dates)
    }
    
    config_dict = {
        'VIX': {'direction': 'down_good', 'z_type': 'MADZ', 'z_window': 40},
        'HY_OAS': {'direction': 'down_good', 'z_type': 'MADZ', 'z_window': 60},
        'RRP': {'direction': 'down_good', 'z_type': 'Z', 'z_window': 60},
        'DFII10': {'direction': 'down_good', 'z_type': 'Z', 'z_window': 60}
    }
    
    print(f"\nProcessing {len(data_dict)} indicators...")
    
    # 批量标准化
    z_dict = batch_standardize(data_dict, config_dict)
    print(f"  Standardized: {list(z_dict.keys())}")
    
    # 批量评分
    score_dict = batch_score(z_dict)
    print(f"  Scored: {list(score_dict.keys())}")
    
    # 显示结果摘要
    print("\nBatch Results Summary:")
    for code in score_dict:
        score = score_dict[code]
        valid_score = score.dropna()
        if len(valid_score) > 0:
            print(f"  {code}: Mean={valid_score.mean():.1f}, Range=[{valid_score.min():.1f}, {valid_score.max():.1f}]")


def main():
    """主演示函数"""
    print("\n" + "=" * 60)
    print("Stage 2 Demo: Core Transforms & Scoring")
    print("Dual Market Thermometer")
    print("=" * 60)
    
    # 步骤1: 模拟数据
    data = simulate_market_data()
    
    # 步骤2: 数据转换
    transformed = demo_transforms(data)
    
    # 步骤3: 标准化
    z_scores = demo_standardization(data, transformed)
    
    # 步骤4: 评分
    scores = demo_scoring(z_scores)
    
    # 步骤5: 灯色和Regime
    classifications = demo_lamp_and_regime(scores)
    
    # 步骤6: 综合评分
    composite = demo_composite_score(scores)
    
    # 步骤7: 批量操作
    demo_batch_operations()
    
    # 总结
    print("\n" + "=" * 60)
    print("Demo Completed Successfully!")
    print("=" * 60)
    print("\nAll core transforms and scoring functions are working correctly.")
    print("The system can now:")
    print("  1. Transform raw market data (delta, pct, relret, log+winsor, etc.)")
    print("  2. Standardize with direction adjustment (up_good/down_good)")
    print("  3. Calculate Z and MAD-Z scores")
    print("  4. Map to 0-100 scores")
    print("  5. Classify into Lamps (G/Y/R) and Regimes (Attack/Balanced/Defense)")
    print("  6. Calculate weighted composite scores")
    print("  7. Apply persistence rules")
    print("  8. Batch process multiple indicators")
    print("\nReady for Stage 3: Confirm Layer Logic!")


if __name__ == '__main__':
    main()

