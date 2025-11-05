"""
数据转换模块单元测试
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from core.transforms import (
    transform_delta20,
    transform_pct20,
    transform_relret20,
    transform_slope_20_60_ewma,
    transform_log_winsor,
    transform_yoy_std_ffill,
    transform_raw_winsor,
    resample_to_weekly,
    apply_transform,
    forward_fill_to_daily,
    calculate_5day_sum,
    align_series
)


class TestBasicTransforms:
    """基础转换函数测试"""
    
    def test_delta20(self):
        """测试delta20转换"""
        # 创建测试数据
        data = pd.Series([100, 102, 105, 108, 110])
        
        # 计算2日变动
        result = transform_delta20(data, window=2)
        
        # 验证
        assert pd.isna(result.iloc[0])  # 前2个应该是NaN
        assert pd.isna(result.iloc[1])
        assert result.iloc[2] == 5  # 105 - 100 = 5
        assert result.iloc[3] == 6  # 108 - 102 = 6
        assert result.iloc[4] == 5  # 110 - 105 = 5
    
    def test_pct20(self):
        """测试pct20百分比变动"""
        data = pd.Series([100, 110, 121])
        
        result = transform_pct20(data, window=1)
        
        assert pd.isna(result.iloc[0])
        assert abs(result.iloc[1] - 0.10) < 0.001  # 10%
        assert abs(result.iloc[2] - 0.10) < 0.001  # 10%
    
    def test_relret20(self):
        """测试相对收益率"""
        # 创建两个序列
        dates = pd.date_range('2024-01-01', periods=5, freq='B')
        iwm = pd.Series([100, 105, 110, 108, 112], index=dates)
        spy = pd.Series([200, 204, 206, 208, 210], index=dates)
        
        # 计算2日相对收益
        result = transform_relret20(iwm, spy, window=2)
        
        # 验证前2个是NaN
        assert pd.isna(result.iloc[0])
        assert pd.isna(result.iloc[1])
        
        # IWM: 110/100 = 1.10, SPY: 206/200 = 1.03
        # relret = 1.10/1.03 - 1 ≈ 0.068
        assert abs(result.iloc[2] - 0.068) < 0.01
    
    def test_log_winsor(self):
        """测试对数变换和winsorize"""
        # 包含极端值的数据
        data = pd.Series([10, 12, 15, 100, 13, 14, 11])
        
        result = transform_log_winsor(data, p_low=0.1, p_high=0.9)
        
        # 验证结果是对数值
        assert result.min() > 0  # 对数值应该都是正的（因为原值都>1）
        
        # 极端值应该被截尾
        log_100 = np.log(100)
        assert result.iloc[3] < log_100  # 100的对数应该被截尾
    
    def test_raw_winsor(self):
        """测试原始值winsorize"""
        data = pd.Series([1, 2, 3, 100, 4, 5, 2])
        
        result = transform_raw_winsor(data, n_sigma=2)
        
        # 极端值100应该被截尾
        assert result.iloc[3] < 100
        assert result.iloc[3] < result.max() or result.iloc[3] == result.max()


class TestComplexTransforms:
    """复杂转换函数测试"""
    
    def test_slope_20_60_ewma(self):
        """测试EWMA斜率组合"""
        # 创建上升趋势数据
        data = pd.Series(range(100, 200))
        
        result = transform_slope_20_60_ewma(
            data,
            w_fast=0.6,
            w_slow=0.4,
            window_fast=20,
            window_slow=60
        )
        
        # 验证结果存在且大部分为正（上升趋势）
        assert len(result) == len(data)
        valid_result = result.dropna()
        assert len(valid_result) > 50  # 应该有足够多的有效值
        # 上升趋势应该有正斜率
        assert valid_result.tail(20).mean() > 0
    
    def test_yoy_std_ffill(self):
        """测试同比标准化"""
        # 创建月度数据（24个月）
        dates = pd.date_range('2023-01-01', periods=24, freq='MS')
        # 创建有同比增长的数据
        data = pd.Series(range(50, 74), index=dates)
        
        result = transform_yoy_std_ffill(data, freq='M')
        
        # 前12个月应该是NaN（没有同比）
        assert result.iloc[:12].isna().all()
        
        # 后面的应该有值
        assert not result.iloc[12:].isna().all()


class TestResampling:
    """重采样和对齐测试"""
    
    def test_resample_to_weekly(self):
        """测试周频重采样"""
        # 创建日频数据（一个月）
        dates = pd.date_range('2024-01-01', periods=20, freq='B')
        data = pd.Series(range(20), index=dates)
        
        # 重采样到周五
        result = resample_to_weekly(data, day_of_week='Fri', agg_method='last')
        
        # 应该有大约4周的数据
        assert len(result) >= 3
        assert len(result) <= 5
        
        # 索引应该是周五
        for date in result.index:
            assert date.dayofweek == 4  # 4 = Friday
    
    def test_forward_fill_to_daily(self):
        """测试前向填充到日频"""
        # 创建月度数据
        dates = pd.date_range('2024-01-01', periods=3, freq='MS')
        data = pd.Series([50, 51, 52], index=dates)
        
        # 填充到日频
        result = forward_fill_to_daily(
            data,
            start_date=pd.Timestamp('2024-01-01'),
            end_date=pd.Timestamp('2024-03-31'),
            freq='B'
        )
        
        # 应该有约60个工作日
        assert len(result) > 40
        assert len(result) < 70
        
        # 1月的所有工作日应该都是50
        jan_data = result['2024-01']
        assert (jan_data == 50).all()
    
    def test_calculate_5day_sum(self):
        """测试5日滚动和"""
        data = pd.Series([10, 20, 30, 40, 50])
        
        result = calculate_5day_sum(data, window=3)
        
        # 第一个值应该是10（只有1个数）
        assert result.iloc[0] == 10
        # 第三个值应该是60（10+20+30）
        assert result.iloc[2] == 60
        # 最后一个值应该是120（30+40+50）
        assert result.iloc[4] == 120
    
    def test_align_series(self):
        """测试序列对齐"""
        s1 = pd.Series([1, 2, 3], index=[0, 1, 2])
        s2 = pd.Series([4, 5, 6], index=[1, 2, 3])
        
        # Inner join
        aligned1, aligned2 = align_series(s1, s2, join='inner')
        
        # 应该只有索引1和2
        assert len(aligned1) == 2
        assert len(aligned2) == 2
        assert list(aligned1.index) == [1, 2]
        assert list(aligned1.values) == [2, 3]
        assert list(aligned2.values) == [4, 5]


class TestApplyTransform:
    """通用转换分发器测试"""
    
    def test_apply_transform_delta20(self):
        """测试通过分发器调用delta20"""
        data = pd.Series([100, 102, 105])
        
        result = apply_transform(data, 'delta20', window=1)
        
        assert pd.isna(result.iloc[0])
        assert result.iloc[1] == 2
        assert result.iloc[2] == 3
    
    def test_apply_transform_raw(self):
        """测试raw转换（不转换）"""
        data = pd.Series([100, 102, 105])
        
        result = apply_transform(data, 'raw')
        
        pd.testing.assert_series_equal(result, data)
    
    def test_apply_transform_relret20(self):
        """测试通过分发器调用relret20"""
        dates = pd.date_range('2024-01-01', periods=3, freq='B')
        s1 = pd.Series([100, 105, 110], index=dates)
        s2 = pd.Series([200, 202, 206], index=dates)
        
        result = apply_transform((s1, s2), 'relret20', window=1)
        
        assert len(result) == 3
        assert pd.isna(result.iloc[0])
    
    def test_apply_transform_invalid(self):
        """测试无效转换类型"""
        data = pd.Series([100, 102, 105])
        
        with pytest.raises(ValueError, match="Unknown transform type"):
            apply_transform(data, 'invalid_transform')


class TestEdgeCases:
    """边界情况测试"""
    
    def test_empty_series(self):
        """测试空序列"""
        data = pd.Series([], dtype=float)
        
        result = transform_delta20(data, window=20)
        
        assert len(result) == 0
    
    def test_series_with_nans(self):
        """测试包含NaN的序列"""
        data = pd.Series([100, np.nan, 105, 108, np.nan])
        
        result = transform_delta20(data, window=2)
        
        # 应该能处理NaN
        assert len(result) == len(data)
    
    def test_constant_series(self):
        """测试常数序列"""
        data = pd.Series([100] * 10)
        
        result = transform_pct20(data, window=5)
        
        # 常数序列的百分比变化应该是0
        valid_result = result.dropna()
        assert (valid_result == 0).all()
    
    def test_single_value(self):
        """测试单个值"""
        data = pd.Series([100])
        
        result = transform_delta20(data, window=1)
        
        assert len(result) == 1
        assert pd.isna(result.iloc[0])


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

