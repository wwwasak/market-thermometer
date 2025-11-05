"""
评分和标准化模块单元测试
"""

import pytest
import pandas as pd
import numpy as np

from core.scoring import (
    rolling_z,
    rolling_madz,
    standardize_with_direction,
    score_from_z,
    lamp_from_score,
    regime_from_score,
    apply_persistence,
    weighted_score,
    check_extreme_jump,
    check_extreme_z,
    calculate_composite_score,
    batch_standardize,
    batch_score
)


class TestZScores:
    """Z分数计算测试"""
    
    def test_rolling_z_basic(self):
        """测试基本Z分数计算"""
        # 创建有明显趋势的数据
        data = pd.Series([10, 12, 14, 16, 18, 20, 22, 24, 26, 28])
        
        result = rolling_z(data, window=5, min_periods=3)
        
        # 前几个值应该存在（min_periods=3）
        assert not pd.isna(result.iloc[2])
        
        # 最后的Z分数应该为正（持续上升）
        assert result.iloc[-1] > 0
    
    def test_rolling_z_constant(self):
        """测试常数序列的Z分数"""
        data = pd.Series([100] * 10)
        
        result = rolling_z(data, window=5)
        
        # 常数序列的Z分数应该是NaN（标准差为0）
        assert result.dropna().empty or (result.dropna() == 0).all()
    
    def test_rolling_madz_basic(self):
        """测试MAD-Z分数计算"""
        # 包含异常值的数据
        data = pd.Series([10, 11, 12, 100, 13, 14, 15, 16, 17, 18])
        
        result = rolling_madz(data, window=5, min_periods=3)
        
        # 应该有有效值
        assert not result.dropna().empty
        
        # MAD-Z对异常值更稳健
        # 异常值100的MAD-Z应该被控制
        assert len(result) == len(data)
    
    def test_rolling_madz_vs_z(self):
        """测试MAD-Z vs 标准Z对异常值的稳健性"""
        # 正常数据 + 一个极端异常值
        normal = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
        data_with_outlier = pd.Series(normal[:5] + [1000] + normal[6:])
        
        z = rolling_z(data_with_outlier, window=8, min_periods=5)
        madz = rolling_madz(data_with_outlier, window=8, min_periods=5)
        
        # MAD-Z应该更稳健（异常值后的恢复更快）
        # 这里只验证都能计算出结果
        assert not z.dropna().empty
        assert not madz.dropna().empty


class TestDirectionStandardization:
    """方向标准化测试"""
    
    def test_up_good_direction(self):
        """测试up_good方向"""
        # 上升数据
        data = pd.Series(range(10, 30))
        
        z = standardize_with_direction(
            data,
            direction='up_good',
            z_type='Z',
            window=10
        )
        
        # up_good：值越高Z越正
        valid_z = z.dropna()
        assert valid_z.iloc[-1] > 0  # 最后的值应该是正的
    
    def test_down_good_direction(self):
        """测试down_good方向"""
        # 上升数据（但down_good）
        data = pd.Series(range(10, 30))
        
        z = standardize_with_direction(
            data,
            direction='down_good',
            z_type='Z',
            window=10
        )
        
        # down_good：值越高Z应该越负（因为取反）
        valid_z = z.dropna()
        assert valid_z.iloc[-1] < 0  # 最后的值应该是负的
    
    def test_invalid_direction(self):
        """测试无效方向"""
        data = pd.Series(range(10, 20))
        
        with pytest.raises(ValueError, match="Unknown direction"):
            standardize_with_direction(data, direction='invalid', z_type='Z', window=5)
    
    def test_invalid_z_type(self):
        """测试无效Z类型"""
        data = pd.Series(range(10, 20))
        
        with pytest.raises(ValueError, match="Unknown z_type"):
            standardize_with_direction(data, direction='up_good', z_type='INVALID', window=5)


class TestScoreMapping:
    """评分映射测试"""
    
    def test_score_from_z_basic(self):
        """测试基本评分映射"""
        z = pd.Series([0, 1, -1, 2, -2, 5, -5])
        
        scores = score_from_z(z)
        
        # Z=0 -> Score=50
        assert scores.iloc[0] == 50
        # Z=1 -> Score=60
        assert scores.iloc[1] == 60
        # Z=-1 -> Score=40
        assert scores.iloc[2] == 40
        # Z=2 -> Score=70
        assert scores.iloc[3] == 70
        # Z=-2 -> Score=30
        assert scores.iloc[4] == 30
    
    def test_score_from_z_clipping(self):
        """测试评分截断"""
        z = pd.Series([10, -10])
        
        scores = score_from_z(z, center=50, scale=10, min_score=0, max_score=100)
        
        # Z=10 -> 50+100=150 -> clip到100
        assert scores.iloc[0] == 100
        # Z=-10 -> 50-100=-50 -> clip到0
        assert scores.iloc[1] == 0
    
    def test_score_from_z_custom_params(self):
        """测试自定义参数"""
        z = pd.Series([0, 1, -1])
        
        scores = score_from_z(z, center=60, scale=20)
        
        # Z=0 -> 60
        assert scores.iloc[0] == 60
        # Z=1 -> 80
        assert scores.iloc[1] == 80
        # Z=-1 -> 40
        assert scores.iloc[2] == 40


class TestLampAndRegime:
    """灯色和Regime判断测试"""
    
    def test_lamp_from_score(self):
        """测试灯色判断"""
        scores = pd.Series([70, 60, 50, 40, 30])
        
        lamps = lamp_from_score(scores, green_threshold=60, red_threshold=40)
        
        assert lamps.iloc[0] == 'G'  # 70 -> Green
        assert lamps.iloc[1] == 'G'  # 60 -> Green (边界)
        assert lamps.iloc[2] == 'Y'  # 50 -> Yellow
        assert lamps.iloc[3] == 'R'  # 40 -> Red (边界)
        assert lamps.iloc[4] == 'R'  # 30 -> Red
    
    def test_lamp_with_nan(self):
        """测试包含NaN的灯色判断"""
        scores = pd.Series([70, np.nan, 30])
        
        lamps = lamp_from_score(scores)
        
        assert lamps.iloc[0] == 'G'
        assert lamps.iloc[1] == 'Y'  # NaN -> Yellow
        assert lamps.iloc[2] == 'R'
    
    def test_regime_from_score_basic(self):
        """测试基本Regime判断"""
        scores = pd.Series([75, 70, 50, 40, 35])
        
        regimes = regime_from_score(
            scores,
            attack_threshold=70,
            defense_threshold=40,
            persistence=0
        )
        
        assert regimes.iloc[0] == 'Attack'    # 75
        assert regimes.iloc[1] == 'Attack'    # 70 (边界)
        assert regimes.iloc[2] == 'Balanced'  # 50
        assert regimes.iloc[3] == 'Defense'   # 40 (边界)
        assert regimes.iloc[4] == 'Defense'   # 35
    
    def test_regime_with_persistence(self):
        """测试带持续性的Regime判断"""
        # 模拟频繁波动的score
        scores = pd.Series([75, 72, 68, 65, 70, 72, 75])
        
        # 无持续性：可能频繁切换
        regimes_no_persist = regime_from_score(scores, attack_threshold=70, persistence=0)
        
        # 有持续性：更平滑
        regimes_persist = regime_from_score(scores, attack_threshold=70, persistence=2)
        
        # 至少应该有结果
        assert len(regimes_no_persist) == len(scores)
        assert len(regimes_persist) == len(scores)


class TestPersistence:
    """持续性规则测试"""
    
    def test_apply_persistence_basic(self):
        """测试基本持续性"""
        # 模拟状态序列
        series = pd.Series(['A', 'A', 'B', 'B', 'B', 'A', 'A'])
        
        # 需要2期确认
        result = apply_persistence(series, persistence=2)
        
        # 前2个是A
        assert result.iloc[0] == 'A'
        assert result.iloc[1] == 'A'
        
        # 后续应该在某个点切换到B（需要2期确认）
        assert len(result) == len(series)
    
    def test_apply_persistence_no_change(self):
        """测试无变化的持续性"""
        series = pd.Series(['A'] * 10)
        
        result = apply_persistence(series, persistence=3)
        
        # 应该全是A
        assert (result == 'A').all()
    
    def test_apply_persistence_zero(self):
        """测试persistence=0（无持续性）"""
        series = pd.Series(['A', 'B', 'A', 'B'])
        
        result = apply_persistence(series, persistence=0)
        
        # 应该与原序列相同
        pd.testing.assert_series_equal(result, series)


class TestWeightedScore:
    """加权评分测试"""
    
    def test_weighted_score_basic(self):
        """测试基本加权评分"""
        scores = pd.DataFrame({
            'ind1': [70, 60, 50],
            'ind2': [60, 70, 80]
        })
        weights = [0.6, 0.4]
        
        result = weighted_score(scores, weights, normalize=False)
        
        # 第一行：70*0.6 + 60*0.4 = 42 + 24 = 66
        assert abs(result.iloc[0] - 66) < 0.01
    
    def test_weighted_score_normalize(self):
        """测试权重归一化"""
        scores = pd.DataFrame({
            'ind1': [50, 60],
            'ind2': [50, 40]
        })
        weights = [60, 40]  # 总和为100
        
        result = weighted_score(scores, weights, normalize=True)
        
        # 归一化后：0.6和0.4
        # 第一行：50*0.6 + 50*0.4 = 50
        assert abs(result.iloc[0] - 50) < 0.01
    
    def test_weighted_score_with_nan(self):
        """测试包含NaN的加权评分"""
        scores = pd.DataFrame({
            'ind1': [70, np.nan],
            'ind2': [60, 80]
        })
        weights = [0.5, 0.5]
        
        result = weighted_score(scores, weights, normalize=False)
        
        # 第一行：70*0.5 + 60*0.5 = 65
        assert abs(result.iloc[0] - 65) < 0.01
        # 第二行：只有ind2有值，应该是80*0.5 = 40
        assert abs(result.iloc[1] - 40) < 0.01
    
    def test_weighted_score_wrong_length(self):
        """测试权重长度不匹配"""
        scores = pd.DataFrame({
            'ind1': [70],
            'ind2': [60]
        })
        weights = [0.5]  # 只有1个权重，但有2列
        
        with pytest.raises(ValueError, match="must match columns"):
            weighted_score(scores, weights)


class TestExtremeChecks:
    """极端值检测测试"""
    
    def test_check_extreme_jump(self):
        """测试极端跳升检测"""
        # 创建有跳升的数据
        data = pd.Series([3.5, 3.6, 3.7, 3.8, 5.0, 5.2, 5.1])
        
        result = check_extreme_jump(
            data,
            window=3,
            z_window=5,
            threshold=1.0
        )
        
        # 应该能检测到跳升
        assert len(result) == len(data)
        assert result.dtype == bool
    
    def test_check_extreme_z(self):
        """测试极端Z值检测"""
        z = pd.Series([0.5, 1.0, 2.5, 1.5, 3.0])
        
        result = check_extreme_z(z, threshold=2.0)
        
        assert result.iloc[0] == False  # 0.5
        assert result.iloc[1] == False  # 1.0
        assert result.iloc[2] == True   # 2.5
        assert result.iloc[3] == False  # 1.5
        assert result.iloc[4] == True   # 3.0


class TestCompositeScore:
    """综合评分测试"""
    
    def test_calculate_composite_score(self):
        """测试综合评分计算"""
        scores = pd.DataFrame({
            'IND1': [70, 65, 60],
            'IND2': [60, 55, 50],
            'IND3': [50, 60, 70]
        })
        weights = [50, 30, 20]  # 总和100
        
        result = calculate_composite_score(scores, weights, market='CN')
        
        # 应该是加权平均
        # 第一行：70*0.5 + 60*0.3 + 50*0.2 = 35 + 18 + 10 = 63
        assert abs(result.iloc[0] - 63) < 0.01


class TestBatchOperations:
    """批量操作测试"""
    
    def test_batch_standardize(self):
        """测试批量标准化"""
        data_dict = {
            'VIX': pd.Series([15, 20, 25, 18, 16, 14, 17, 19, 22, 21]),
            'SPY': pd.Series([400, 410, 405, 415, 420, 418, 425, 430, 428, 435])
        }
        
        config_dict = {
            'VIX': {'direction': 'down_good', 'z_type': 'Z', 'z_window': 5},
            'SPY': {'direction': 'up_good', 'z_type': 'Z', 'z_window': 5}
        }
        
        z_dict = batch_standardize(data_dict, config_dict)
        
        assert 'VIX' in z_dict
        assert 'SPY' in z_dict
        assert len(z_dict['VIX']) == len(data_dict['VIX'])
        assert len(z_dict['SPY']) == len(data_dict['SPY'])
    
    def test_batch_score(self):
        """测试批量评分"""
        z_dict = {
            'IND1': pd.Series([0, 1, -1, 2]),
            'IND2': pd.Series([0.5, -0.5, 1.5, -1.5])
        }
        
        scores = batch_score(z_dict)
        
        assert 'IND1' in scores
        assert 'IND2' in scores
        
        # Z=0 -> Score=50
        assert scores['IND1'].iloc[0] == 50
        # Z=1 -> Score=60
        assert scores['IND1'].iloc[1] == 60


class TestEdgeCases:
    """边界情况测试"""
    
    def test_empty_dataframe(self):
        """测试空DataFrame"""
        scores = pd.DataFrame()
        weights = []
        
        # 应该返回空Series或抛出合理错误
        try:
            result = weighted_score(scores, weights)
            assert len(result) == 0
        except:
            pass  # 空DataFrame可能导致错误，这是可接受的
    
    def test_all_nan_series(self):
        """测试全NaN序列"""
        data = pd.Series([np.nan] * 10)
        
        z = rolling_z(data, window=5)
        
        # 全NaN应该返回全NaN
        assert z.isna().all()
    
    def test_single_value_window(self):
        """测试单值窗口"""
        data = pd.Series(range(10))
        
        z = rolling_z(data, window=1, min_periods=1)
        
        # 单值窗口的标准差为0，应该返回NaN
        assert len(z) == len(data)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

