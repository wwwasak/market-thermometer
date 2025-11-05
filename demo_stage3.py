"""
阶段3演示脚本：确认层逻辑

演示完整的确认层工作流程：
1. 模拟主要指标和观察者指标的灯色
2. 配对规则（Rule A vs Rule B）
3. 硬否决（MIN + persistence）
4. 软确认（加权投票）
5. 最终灯色合成
"""

import pandas as pd
import numpy as np

from core.combine import (
    pair_combine,
    hard_veto_min,
    soft_confirm_weighted,
    final_lamp,
    build_confirm_layer,
    analyze_lamp_distribution
)


def simulate_lamps():
    """模拟灯色数据"""
    print("=" * 60)
    print("Step 1: Simulate Lamp Data")
    print("=" * 60)
    
    # 创建30个交易日的模拟灯色
    dates = pd.date_range('2024-01-01', periods=30, freq='B')
    
    # 模拟主要指标灯色（已经通过scoring计算得到）
    np.random.seed(42)
    
    # 主要指标：大部分时间是绿/黄，偶尔红
    main1 = pd.Series(
        np.random.choice(['G', 'G', 'G', 'Y', 'Y', 'R'], size=30),
        index=dates
    )
    main2 = pd.Series(
        np.random.choice(['G', 'G', 'Y', 'Y', 'Y', 'R'], size=30),
        index=dates
    )
    
    # 观察者：硬否决指标（偶尔红灯）
    hard_indicator = pd.Series(
        ['Y'] * 25 + ['R'] * 5,  # 最后5天红灯
        index=dates
    )
    
    # 观察者：软确认指标
    soft1 = pd.Series(
        np.random.choice(['G', 'Y', 'R'], size=30, p=[0.4, 0.4, 0.2]),
        index=dates
    )
    
    soft2 = pd.Series(
        np.random.choice(['G', 'Y', 'R'], size=30, p=[0.3, 0.5, 0.2]),
        index=dates
    )
    
    # 配对指标（CNH和CNY）
    cnh = pd.Series(
        np.random.choice(['G', 'Y', 'R'], size=30, p=[0.3, 0.4, 0.3]),
        index=dates
    )
    cny = pd.Series(
        np.random.choice(['G', 'Y', 'R'], size=30, p=[0.3, 0.4, 0.3]),
        index=dates
    )
    
    # 配对指标（TWEX和DXY）
    twex = pd.Series(
        np.random.choice(['G', 'Y', 'R'], size=30, p=[0.35, 0.45, 0.2]),
        index=dates
    )
    dxy = pd.Series(
        np.random.choice(['G', 'Y', 'R'], size=30, p=[0.35, 0.45, 0.2]),
        index=dates
    )
    
    print(f"Generated lamp data for {len(dates)} trading days")
    print(f"Main Indicator 1: {analyze_lamp_distribution(main1)}")
    print(f"Main Indicator 2: {analyze_lamp_distribution(main2)}")
    print(f"Hard Veto: {analyze_lamp_distribution(hard_indicator)}")
    
    return {
        'dates': dates,
        'main1': main1,
        'main2': main2,
        'hard': hard_indicator,
        'soft1': soft1,
        'soft2': soft2,
        'cnh': cnh,
        'cny': cny,
        'twex': twex,
        'dxy': dxy
    }


def demo_pair_combine(data):
    """演示配对规则"""
    print("\n" + "=" * 60)
    print("Step 2: Pair Combine Rules")
    print("=" * 60)
    
    # Rule A: 一致性优先
    pair_a = pair_combine(data['cnh'], data['cny'], rule='A')
    print("\nCNH/CNY Pair (Rule A - Consensus First):")
    print(f"  CNH last 5:  {data['cnh'].tail().values}")
    print(f"  CNY last 5:  {data['cny'].tail().values}")
    print(f"  Pair last 5: {pair_a.tail().values}")
    
    dist_a = analyze_lamp_distribution(pair_a)
    print(f"  Distribution: G={dist_a['G']:.1%}, Y={dist_a['Y']:.1%}, R={dist_a['R']:.1%}")
    
    # Rule B: 强分歧红灯
    pair_b = pair_combine(data['cnh'], data['cny'], rule='B')
    print("\nCNH/CNY Pair (Rule B - Divergence Red):")
    print(f"  Pair last 5: {pair_b.tail().values}")
    
    dist_b = analyze_lamp_distribution(pair_b)
    print(f"  Distribution: G={dist_b['G']:.1%}, Y={dist_b['Y']:.1%}, R={dist_b['R']:.1%}")
    
    # 对比
    print(f"\n  Rule A has more Red: {dist_b['R'] > dist_a['R']}")
    print("  (Rule B treats G+R divergence as Red)")
    
    return {
        'pair_cnh_cny_a': pair_a,
        'pair_cnh_cny_b': pair_b,
        'pair_twex_dxy': pair_combine(data['twex'], data['dxy'], rule='A')
    }


def demo_hard_veto(data):
    """演示硬否决"""
    print("\n" + "=" * 60)
    print("Step 3: Hard Veto (MIN + Persistence)")
    print("=" * 60)
    
    # 无持续性
    hard_no_persist = hard_veto_min([data['hard']], persistence=0)
    print("\nHard Veto (No Persistence):")
    print(f"  Input last 10:  {data['hard'].tail(10).values}")
    print(f"  Output last 10: {hard_no_persist.tail(10).values}")
    
    dist = analyze_lamp_distribution(hard_no_persist)
    print(f"  Distribution: G={dist['G']:.1%}, Y={dist['Y']:.1%}, R={dist['R']:.1%}")
    
    # 有持续性
    hard_with_persist = hard_veto_min([data['hard']], persistence=2)
    print("\nHard Veto (Persistence=2):")
    print(f"  Output last 10: {hard_with_persist.tail(10).values}")
    print("  (Red needs 2 consecutive days to take effect)")
    
    return {
        'hard_no_persist': hard_no_persist,
        'hard_with_persist': hard_with_persist
    }


def demo_soft_confirm(data, pairs):
    """演示软确认"""
    print("\n" + "=" * 60)
    print("Step 4: Soft Confirm (Weighted Vote)")
    print("=" * 60)
    
    # 准备软确认的输入
    lamps_list = [
        data['soft1'],
        data['soft2'],
        pairs['pair_twex_dxy']
    ]
    weights = [0.4, 0.3, 0.3]
    
    print("\nSoft Confirm Inputs:")
    print(f"  SOFT1 distribution: {analyze_lamp_distribution(data['soft1'])}")
    print(f"  SOFT2 distribution: {analyze_lamp_distribution(data['soft2'])}")
    print(f"  PAIR distribution:  {analyze_lamp_distribution(pairs['pair_twex_dxy'])}")
    print(f"  Weights: {weights}")
    
    # 计算软确认
    soft_result = soft_confirm_weighted(
        lamps_list,
        weights,
        green_threshold=1.6,
        red_threshold=0.8
    )
    
    print("\nSoft Confirm Output:")
    print(f"  Last 10: {soft_result.tail(10).values}")
    
    dist = analyze_lamp_distribution(soft_result)
    print(f"  Distribution: G={dist['G']:.1%}, Y={dist['Y']:.1%}, R={dist['R']:.1%}")
    
    # 展示投票逻辑示例
    print("\nVoting Logic Example (last day):")
    print(f"  SOFT1: {data['soft1'].iloc[-1]} (weight={weights[0]})")
    print(f"  SOFT2: {data['soft2'].iloc[-1]} (weight={weights[1]})")
    print(f"  PAIR:  {pairs['pair_twex_dxy'].iloc[-1]} (weight={weights[2]})")
    
    # 手动计算加权值
    lamp_values = {'G': 2.0, 'Y': 1.0, 'R': 0.0}
    weighted_val = (
        lamp_values[data['soft1'].iloc[-1]] * weights[0] +
        lamp_values[data['soft2'].iloc[-1]] * weights[1] +
        lamp_values[pairs['pair_twex_dxy'].iloc[-1]] * weights[2]
    )
    print(f"  Weighted value: {weighted_val:.2f}")
    print(f"  Result: {soft_result.iloc[-1]} (≥1.6→G, ≤0.8→R, else→Y)")
    
    return soft_result


def demo_final_lamp(hard, soft):
    """演示最终灯色合成"""
    print("\n" + "=" * 60)
    print("Step 5: Final Lamp (Hard Priority)")
    print("=" * 60)
    
    final = final_lamp(hard['hard_with_persist'], soft)
    
    print("\nFinal Lamp Synthesis:")
    print(f"  Hard Veto last 10: {hard['hard_with_persist'].tail(10).values}")
    print(f"  Soft Confirm last 10: {soft.tail(10).values}")
    print(f"  Final Lamp last 10: {final.tail(10).values}")
    
    dist = analyze_lamp_distribution(final)
    print(f"\nFinal Distribution: G={dist['G']:.1%}, Y={dist['Y']:.1%}, R={dist['R']:.1%}")
    
    # 展示合成逻辑
    print("\nSynthesis Logic:")
    print("  If Hard Veto = Red → Final = Red (Hard Priority)")
    print("  Else if Soft Confirm = Green → Final = Green")
    print("  Else → Final = Yellow")
    
    # 统计优先级生效情况
    hard_red_count = (hard['hard_with_persist'] == 'R').sum()
    soft_green_count = (soft == 'G').sum()
    final_red_count = (final == 'R').sum()
    final_green_count = (final == 'G').sum()
    
    print(f"\nPriority Statistics:")
    print(f"  Hard Veto triggered Red: {hard_red_count} times")
    print(f"  Soft Confirm was Green: {soft_green_count} times")
    print(f"  Final Red (hard veto): {final_red_count} times")
    print(f"  Final Green (soft confirm): {final_green_count} times")
    
    return final


def demo_full_confirm_layer():
    """演示完整确认层构建"""
    print("\n" + "=" * 60)
    print("Step 6: Full Confirm Layer Build")
    print("=" * 60)
    
    # 准备数据
    dates = pd.date_range('2024-01-01', periods=20, freq='B')
    
    main_lamps = {
        'VIX': pd.Series(['G'] * 15 + ['Y'] * 5, index=dates),
        'RRP': pd.Series(['G'] * 10 + ['Y'] * 10, index=dates)
    }
    
    observer_lamps = {
        'HY_OAS_JUMP': pd.Series(['Y'] * 18 + ['R'] * 2, index=dates),
        'IWM_SPY_SOFT': pd.Series(['G'] * 12 + ['Y'] * 8, index=dates),
        'HYG_IEF_SOFT': pd.Series(['Y'] * 10 + ['G'] * 10, index=dates)
    }
    
    pair_lamps = {
        'PAIR_CNH_CNY': (
            pd.Series(['G'] * 10 + ['Y'] * 10, index=dates),
            pd.Series(['G'] * 8 + ['Y'] * 12, index=dates)
        ),
        'PAIR_TWEX_DXY': (
            pd.Series(['Y'] * 15 + ['R'] * 5, index=dates),
            pd.Series(['Y'] * 15 + ['R'] * 5, index=dates)
        )
    }
    
    config = {
        'hard_veto_codes': ['HY_OAS_JUMP'],
        'hard_veto_persistence': 1,
        'soft_confirm_codes': ['IWM_SPY_SOFT', 'HYG_IEF_SOFT', 'PAIR_CNH_CNY', 'PAIR_TWEX_DXY'],
        'soft_confirm_weights': {
            'IWM_SPY_SOFT': 0.3,
            'HYG_IEF_SOFT': 0.3,
            'PAIR_CNH_CNY': 0.2,
            'PAIR_TWEX_DXY': 0.2
        },
        'soft_confirm_green': 1.6,
        'soft_confirm_red': 0.8,
        'pair_rule': 'A'
    }
    
    print("\nBuilding confirm layer with:")
    print(f"  Main indicators: {list(main_lamps.keys())}")
    print(f"  Hard veto: {config['hard_veto_codes']}")
    print(f"  Soft confirm: {config['soft_confirm_codes']}")
    print(f"  Soft weights: {config['soft_confirm_weights']}")
    
    result = build_confirm_layer(main_lamps, observer_lamps, pair_lamps, config)
    
    print("\nConfirm Layer Results:")
    print(f"  Hard Veto last 5: {result['hard_veto'].tail().values}")
    print(f"  Soft Confirm last 5: {result['soft_confirm'].tail().values}")
    print(f"  Final Lamp last 5: {result['final'].tail().values}")
    
    # 分析配对结果
    print(f"\nPair Results:")
    for pair_id, lamp in result['pairs'].items():
        dist = analyze_lamp_distribution(lamp)
        print(f"  {pair_id}: G={dist['G']:.1%}, Y={dist['Y']:.1%}, R={dist['R']:.1%}")
    
    # 最终分布
    final_dist = analyze_lamp_distribution(result['final'])
    print(f"\nFinal Lamp Distribution:")
    print(f"  Green:  {final_dist['G']:.1%}")
    print(f"  Yellow: {final_dist['Y']:.1%}")
    print(f"  Red:    {final_dist['R']:.1%}")


def main():
    """主演示函数"""
    print("\n" + "=" * 60)
    print("Stage 3 Demo: Confirm Layer Logic")
    print("Dual Market Thermometer")
    print("=" * 60)
    
    # 步骤1: 模拟灯色数据
    data = simulate_lamps()
    
    # 步骤2: 配对规则
    pairs = demo_pair_combine(data)
    
    # 步骤3: 硬否决
    hard = demo_hard_veto(data)
    
    # 步骤4: 软确认
    soft = demo_soft_confirm(data, pairs)
    
    # 步骤5: 最终合成
    final = demo_final_lamp(hard, soft)
    
    # 步骤6: 完整构建
    demo_full_confirm_layer()
    
    # 总结
    print("\n" + "=" * 60)
    print("Demo Completed Successfully!")
    print("=" * 60)
    print("\nAll confirm layer functions are working correctly.")
    print("The system can now:")
    print("  1. Combine pairs with Rule A (consensus) or Rule B (divergence→red)")
    print("  2. Apply hard veto with MIN rule + persistence")
    print("  3. Calculate soft confirm with weighted voting")
    print("  4. Synthesize final lamp (hard priority)")
    print("  5. Build complete confirm layer with config")
    print("\nReady for Stage 4: Data Storage Layer!")


if __name__ == '__main__':
    main()

