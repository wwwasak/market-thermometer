"""
确认层组合逻辑单元测试
"""

import pytest
import pandas as pd
import numpy as np

from core.combine import (
    pair_combine,
    hard_veto_min,
    soft_confirm_weighted,
    final_lamp,
    combine_multiple_pairs,
    build_confirm_layer,
    analyze_lamp_distribution,
    lamp_to_numeric,
    numeric_to_lamp,
    get_lamp_changes,
    count_consecutive_lamps
)


class TestPairCombine:
    """配对规则测试"""
    
    def test_pair_combine_rule_a_both_green(self):
        """Rule A: 两个绿 → 绿"""
        lamp1 = pd.Series(['G', 'G', 'G'])
        lamp2 = pd.Series(['G', 'G', 'G'])
        
        result = pair_combine(lamp1, lamp2, rule='A')
        
        assert (result == 'G').all()
    
    def test_pair_combine_rule_a_both_red(self):
        """Rule A: 两个红 → 红"""
        lamp1 = pd.Series(['R', 'R'])
        lamp2 = pd.Series(['R', 'R'])
        
        result = pair_combine(lamp1, lamp2, rule='A')
        
        assert (result == 'R').all()
    
    def test_pair_combine_rule_a_mixed(self):
        """Rule A: 混合 → 黄"""
        lamp1 = pd.Series(['G', 'R', 'Y', 'G'])
        lamp2 = pd.Series(['R', 'Y', 'Y', 'Y'])
        
        result = pair_combine(lamp1, lamp2, rule='A')
        
        # G+R→Y, R+Y→Y, Y+Y→Y, G+Y→Y
        assert result.iloc[0] == 'Y'
        assert result.iloc[1] == 'Y'
        assert result.iloc[2] == 'Y'
        assert result.iloc[3] == 'Y'
    
    def test_pair_combine_rule_b_divergence(self):
        """Rule B: 强分歧（一红一绿）→ 红"""
        lamp1 = pd.Series(['G', 'R', 'G'])
        lamp2 = pd.Series(['R', 'G', 'G'])
        
        result = pair_combine(lamp1, lamp2, rule='B')
        
        assert result.iloc[0] == 'R'  # G+R → R (强分歧)
        assert result.iloc[1] == 'R'  # R+G → R (强分歧)
        assert result.iloc[2] == 'G'  # G+G → G
    
    def test_pair_combine_rule_b_consensus(self):
        """Rule B: 一致 → 该色"""
        lamp1 = pd.Series(['G', 'R', 'Y'])
        lamp2 = pd.Series(['G', 'R', 'Y'])
        
        result = pair_combine(lamp1, lamp2, rule='B')
        
        assert result.iloc[0] == 'G'
        assert result.iloc[1] == 'R'
        assert result.iloc[2] == 'Y'
    
    def test_pair_combine_with_nan(self):
        """处理NaN"""
        lamp1 = pd.Series(['G', np.nan, 'R'])
        lamp2 = pd.Series(['G', 'G', np.nan])
        
        result = pair_combine(lamp1, lamp2, rule='A')
        
        assert result.iloc[0] == 'G'
        assert result.iloc[1] == 'Y'  # NaN → Y
        assert result.iloc[2] == 'Y'  # NaN → Y
    
    def test_pair_combine_invalid_rule(self):
        """测试无效规则"""
        lamp1 = pd.Series(['G'])
        lamp2 = pd.Series(['G'])
        
        with pytest.raises(ValueError, match="Unknown rule"):
            pair_combine(lamp1, lamp2, rule='C')


class TestHardVeto:
    """硬否决测试"""
    
    def test_hard_veto_all_green(self):
        """全绿 → 绿"""
        lamps = [
            pd.Series(['G', 'G', 'G']),
            pd.Series(['G', 'G', 'G'])
        ]
        
        result = hard_veto_min(lamps, persistence=0)
        
        assert (result == 'G').all()
    
    def test_hard_veto_one_red(self):
        """一个红 → 红（最悲观）"""
        lamps = [
            pd.Series(['G', 'G', 'R']),
            pd.Series(['G', 'Y', 'Y'])
        ]
        
        result = hard_veto_min(lamps, persistence=0)
        
        assert result.iloc[0] == 'G'  # G+G → G
        assert result.iloc[1] == 'Y'  # G+Y → Y
        assert result.iloc[2] == 'R'  # R+Y → R (红胜出)
    
    def test_hard_veto_mixed(self):
        """混合情况"""
        lamps = [
            pd.Series(['G', 'Y', 'R', 'Y']),
            pd.Series(['Y', 'Y', 'Y', 'R']),
            pd.Series(['G', 'G', 'Y', 'Y'])
        ]
        
        result = hard_veto_min(lamps, persistence=0)
        
        # MIN(G,Y,G)=Y, MIN(Y,Y,G)=Y, MIN(R,Y,Y)=R, MIN(Y,R,Y)=R
        assert result.iloc[0] == 'Y'
        assert result.iloc[1] == 'Y'
        assert result.iloc[2] == 'R'
        assert result.iloc[3] == 'R'
    
    def test_hard_veto_with_persistence(self):
        """带持续性的硬否决"""
        lamps = [
            pd.Series(['G', 'R', 'R', 'R', 'G'])
        ]
        
        # 需要2期持续
        result = hard_veto_min(lamps, persistence=2)
        
        # 红灯需要持续2期才生效
        assert len(result) == 5
    
    def test_hard_veto_empty_list(self):
        """空列表应该报错"""
        with pytest.raises(ValueError, match="At least one lamp"):
            hard_veto_min([])


class TestSoftConfirm:
    """软确认测试"""
    
    def test_soft_confirm_all_green(self):
        """全绿 → 绿"""
        lamps = [
            pd.Series(['G', 'G', 'G']),
            pd.Series(['G', 'G', 'G'])
        ]
        weights = [0.5, 0.5]
        
        result = soft_confirm_weighted(lamps, weights)
        
        # Green=2, 加权平均=2.0, ≥1.6 → Green
        assert (result == 'G').all()
    
    def test_soft_confirm_all_red(self):
        """全红 → 红"""
        lamps = [
            pd.Series(['R', 'R', 'R']),
            pd.Series(['R', 'R', 'R'])
        ]
        weights = [0.6, 0.4]
        
        result = soft_confirm_weighted(lamps, weights)
        
        # Red=0, 加权平均=0.0, ≤0.8 → Red
        assert (result == 'R').all()
    
    def test_soft_confirm_mixed_to_yellow(self):
        """混合 → 黄"""
        lamps = [
            pd.Series(['G', 'Y', 'R']),
            pd.Series(['R', 'Y', 'G'])
        ]
        weights = [0.5, 0.5]
        
        result = soft_confirm_weighted(lamps, weights)
        
        # [0] G+R: (2+0)/2=1.0, 0.8<1.0<1.6 → Y
        # [1] Y+Y: (1+1)/2=1.0 → Y
        # [2] R+G: (0+2)/2=1.0 → Y
        assert (result == 'Y').all()
    
    def test_soft_confirm_weighted_green(self):
        """加权倾向绿"""
        lamps = [
            pd.Series(['G']),  # 2.0
            pd.Series(['G']),  # 2.0
            pd.Series(['Y'])   # 1.0
        ]
        weights = [0.4, 0.4, 0.2]
        
        result = soft_confirm_weighted(lamps, weights)
        
        # 0.4*2 + 0.4*2 + 0.2*1 = 1.8 ≥ 1.6 → Green
        assert result.iloc[0] == 'G'
    
    def test_soft_confirm_weighted_red(self):
        """加权倾向红"""
        lamps = [
            pd.Series(['R']),  # 0.0
            pd.Series(['Y']),  # 1.0
            pd.Series(['Y'])   # 1.0
        ]
        weights = [0.6, 0.2, 0.2]
        
        result = soft_confirm_weighted(lamps, weights)
        
        # 0.6*0 + 0.2*1 + 0.2*1 = 0.4 ≤ 0.8 → Red
        assert result.iloc[0] == 'R'
    
    def test_soft_confirm_custom_thresholds(self):
        """自定义阈值"""
        lamps = [
            pd.Series(['G', 'Y'])
        ]
        weights = [1.0]
        
        # 更严格的绿阈值
        result = soft_confirm_weighted(
            lamps, weights,
            green_threshold=1.8,  # G=2.0 仍满足
            red_threshold=0.5     # Y=1.0 不满足
        )
        
        assert result.iloc[0] == 'G'  # 2.0 ≥ 1.8
        assert result.iloc[1] == 'Y'  # 0.5 < 1.0 < 1.8
    
    def test_soft_confirm_weight_normalization(self):
        """权重自动归一化"""
        lamps = [
            pd.Series(['G']),
            pd.Series(['R'])
        ]
        weights = [60, 40]  # 总和100，会归一化为0.6, 0.4
        
        result = soft_confirm_weighted(lamps, weights)
        
        # 0.6*2 + 0.4*0 = 1.2, 0.8<1.2<1.6 → Yellow
        assert result.iloc[0] == 'Y'
    
    def test_soft_confirm_wrong_length(self):
        """权重长度不匹配"""
        lamps = [pd.Series(['G']), pd.Series(['Y'])]
        weights = [1.0]  # 只有1个权重
        
        with pytest.raises(ValueError, match="must match"):
            soft_confirm_weighted(lamps, weights)
    
    def test_soft_confirm_empty(self):
        """空列表"""
        with pytest.raises(ValueError, match="At least one lamp"):
            soft_confirm_weighted([], [])


class TestFinalLamp:
    """最终灯色测试"""
    
    def test_final_lamp_hard_veto_red(self):
        """硬否决为红 → 红"""
        hard = pd.Series(['R', 'R', 'R'])
        soft = pd.Series(['G', 'Y', 'R'])
        
        result = final_lamp(hard, soft)
        
        # 硬否决优先，全是红
        assert (result == 'R').all()
    
    def test_final_lamp_soft_confirm_green(self):
        """硬否决不是红，软确认为绿 → 绿"""
        hard = pd.Series(['Y', 'G', 'Y'])
        soft = pd.Series(['G', 'G', 'G'])
        
        result = final_lamp(hard, soft)
        
        # 硬否决非红，软确认绿 → 绿
        assert (result == 'G').all()
    
    def test_final_lamp_default_yellow(self):
        """其他情况 → 黄"""
        hard = pd.Series(['Y', 'G', 'Y'])
        soft = pd.Series(['Y', 'R', 'Y'])
        
        result = final_lamp(hard, soft)
        
        # 硬否决非红，软确认非绿 → 黄
        assert (result == 'Y').all()
    
    def test_final_lamp_priority_sequence(self):
        """验证优先级顺序"""
        hard = pd.Series(['R', 'Y', 'Y', 'G'])
        soft = pd.Series(['G', 'G', 'R', 'Y'])
        
        result = final_lamp(hard, soft)
        
        assert result.iloc[0] == 'R'  # Hard R → R
        assert result.iloc[1] == 'G'  # Hard Y, Soft G → G
        assert result.iloc[2] == 'Y'  # Hard Y, Soft R → Y
        assert result.iloc[3] == 'Y'  # Hard G, Soft Y → Y (Hard非R，但Soft非G)
    
    def test_final_lamp_with_nan(self):
        """包含NaN"""
        hard = pd.Series(['R', np.nan, 'Y'])
        soft = pd.Series(['G', 'G', np.nan])
        
        result = final_lamp(hard, soft)
        
        assert result.iloc[0] == 'R'
        assert result.iloc[1] == 'Y'  # NaN → Y
        assert result.iloc[2] == 'Y'  # NaN → Y


class TestMultiplePairs:
    """多配对测试"""
    
    def test_combine_multiple_pairs(self):
        """批量处理配对"""
        pairs = {
            'PAIR_1': (pd.Series(['G', 'R']), pd.Series(['G', 'R'])),
            'PAIR_2': (pd.Series(['G', 'Y']), pd.Series(['R', 'Y']))
        }
        
        result = combine_multiple_pairs(pairs, rule='A')
        
        assert 'PAIR_1' in result
        assert 'PAIR_2' in result
        assert result['PAIR_1'].iloc[0] == 'G'  # G+G
        assert result['PAIR_1'].iloc[1] == 'R'  # R+R
        assert result['PAIR_2'].iloc[0] == 'Y'  # G+R
        assert result['PAIR_2'].iloc[1] == 'Y'  # Y+Y


class TestBuildConfirmLayer:
    """完整确认层构建测试"""
    
    def test_build_confirm_layer_basic(self):
        """基础确认层构建"""
        # 准备数据
        main_lamps = {
            'IND1': pd.Series(['G', 'G', 'Y']),
            'IND2': pd.Series(['Y', 'R', 'Y'])
        }
        
        observer_lamps = {
            'HARD1': pd.Series(['Y', 'R', 'Y']),
            'SOFT1': pd.Series(['G', 'Y', 'R'])
        }
        
        pair_lamps = {
            'PAIR1': (pd.Series(['G', 'G', 'Y']), pd.Series(['G', 'Y', 'Y']))
        }
        
        config = {
            'hard_veto_codes': ['HARD1'],
            'hard_veto_persistence': 0,
            'soft_confirm_codes': ['SOFT1', 'PAIR1'],
            'soft_confirm_weights': {'SOFT1': 0.6, 'PAIR1': 0.4},
            'soft_confirm_green': 1.6,
            'soft_confirm_red': 0.8,
            'pair_rule': 'A'
        }
        
        result = build_confirm_layer(main_lamps, observer_lamps, pair_lamps, config)
        
        # 验证结果包含所有必要字段
        assert 'hard_veto' in result
        assert 'soft_confirm' in result
        assert 'final' in result
        assert 'pairs' in result
        
        # 验证配对处理
        assert 'PAIR1' in result['pairs']
        
        # 验证长度一致
        assert len(result['hard_veto']) == 3
        assert len(result['soft_confirm']) == 3
        assert len(result['final']) == 3
    
    def test_build_confirm_layer_no_hard_veto(self):
        """无硬否决的情况"""
        observer_lamps = {
            'SOFT1': pd.Series(['G', 'Y'])
        }
        
        config = {
            'hard_veto_codes': [],  # 无硬否决
            'soft_confirm_codes': ['SOFT1'],
            'soft_confirm_weights': {'SOFT1': 1.0},
            'pair_rule': 'A'
        }
        
        result = build_confirm_layer({}, observer_lamps, {}, config)
        
        # 硬否决应该全是黄色（不触发）
        assert (result['hard_veto'] == 'Y').all()


class TestUtilityFunctions:
    """工具函数测试"""
    
    def test_analyze_lamp_distribution(self):
        """灯色分布分析"""
        lamps = pd.Series(['G', 'G', 'Y', 'R'])
        
        dist = analyze_lamp_distribution(lamps)
        
        assert dist['G'] == 0.5  # 2/4
        assert dist['Y'] == 0.25  # 1/4
        assert dist['R'] == 0.25  # 1/4
    
    def test_lamp_to_numeric(self):
        """灯色转数值"""
        lamps = pd.Series(['G', 'Y', 'R'])
        
        result = lamp_to_numeric(lamps)
        
        assert result.iloc[0] == 2
        assert result.iloc[1] == 1
        assert result.iloc[2] == 0
    
    def test_numeric_to_lamp(self):
        """数值转灯色"""
        values = pd.Series([2.0, 1.0, 0.0, 1.8, 0.3])
        
        result = numeric_to_lamp(values)
        
        assert result.iloc[0] == 'G'  # 2.0 ≥ 1.5
        assert result.iloc[1] == 'Y'  # 0.5 < 1.0 < 1.5
        assert result.iloc[2] == 'R'  # 0.0 ≤ 0.5
        assert result.iloc[3] == 'G'  # 1.8 ≥ 1.5
        assert result.iloc[4] == 'R'  # 0.3 ≤ 0.5
    
    def test_get_lamp_changes(self):
        """检测灯色变化"""
        lamps = pd.Series(['G', 'G', 'Y', 'Y', 'R', 'G'])
        
        changes = get_lamp_changes(lamps)
        
        # 第一个总是True（与NaN比较，视为变化）
        assert changes.iloc[0] == True   # 第一个（与NaN不同）
        assert changes.iloc[1] == False  # G→G 
        assert changes.iloc[2] == True   # G→Y
        assert changes.iloc[3] == False  # Y→Y
        assert changes.iloc[4] == True   # Y→R
        assert changes.iloc[5] == True   # R→G
    
    def test_count_consecutive_lamps(self):
        """统计连续灯色"""
        lamps = pd.Series(['G', 'G', 'G', 'Y', 'R', 'R', 'G'])
        
        consecutive_g = count_consecutive_lamps(lamps, 'G')
        
        assert consecutive_g.iloc[0] == 1  # 第1个G
        assert consecutive_g.iloc[1] == 2  # 第2个G
        assert consecutive_g.iloc[2] == 3  # 第3个G
        assert consecutive_g.iloc[3] == 0  # Y
        assert consecutive_g.iloc[4] == 0  # R
        assert consecutive_g.iloc[5] == 0  # R
        assert consecutive_g.iloc[6] == 1  # 新的G


class TestEdgeCases:
    """边界情况测试"""
    
    def test_empty_series(self):
        """空序列"""
        lamp1 = pd.Series([], dtype=str)
        lamp2 = pd.Series([], dtype=str)
        
        result = pair_combine(lamp1, lamp2, rule='A')
        
        assert len(result) == 0
    
    def test_single_value(self):
        """单值"""
        lamp1 = pd.Series(['G'])
        lamp2 = pd.Series(['G'])
        
        result = pair_combine(lamp1, lamp2, rule='A')
        
        assert result.iloc[0] == 'G'
    
    def test_misaligned_indices(self):
        """索引不对齐"""
        lamp1 = pd.Series(['G', 'Y'], index=[0, 1])
        lamp2 = pd.Series(['R', 'G'], index=[1, 2])
        
        result = pair_combine(lamp1, lamp2, rule='A')
        
        # 应该能处理（内部会对齐）
        assert len(result) >= 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

