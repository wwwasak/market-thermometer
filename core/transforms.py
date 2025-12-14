"""
数据转换模块

包含所有指标的数据转换函数，所有函数都是纯函数，便于单元测试。

转换类型：
- delta20: 20日变动量
- pct20: 20日百分比变动
- relret20: 相对收益率（20日）
- slope_20_60_ewma: 20/60日EWMA斜率组合
- log_winsor: 对数变换 + winsorize截尾
- yoy_std_ffill: 同比标准化后前向填充
- raw_winsor: 原始值 + winsorize截尾
"""

import pandas as pd
import numpy as np
from typing import Optional, Tuple


def transform_delta20(series: pd.Series, window: int = 20) -> pd.Series:
    """
    计算N日变动量（差分）
    
    @param {pd.Series} series - 输入时间序列
    @param {int} window - 回看窗口（默认20个交易日）
    @returns {pd.Series} 变动量序列
    
    @example
    >>> prices = pd.Series([100, 102, 105, 103, 107])
    >>> deltas = transform_delta20(prices, window=2)
    """
    return series - series.shift(window)


def transform_delta20_ffill(series: pd.Series, window: int = 20) -> pd.Series:
    """
    计算N日变动量（差分），先前向填充
    
    用于非每日更新的数据（如TGA每周更新一次）
    
    @param {pd.Series} series - 输入时间序列
    @param {int} window - 回看窗口（默认20个交易日）
    @returns {pd.Series} 变动量序列
    
    @example
    >>> prices = pd.Series([100, np.nan, np.nan, 105], index=pd.date_range('2024-01-01', periods=4))
    >>> deltas = transform_delta20_ffill(prices, window=2)
    """
    # 先前向填充
    filled_series = series.ffill()
    # 再计算差分
    return filled_series - filled_series.shift(window)


def transform_pct20(series: pd.Series, window: int = 20) -> pd.Series:
    """
    计算N日百分比变动
    
    @param {pd.Series} series - 输入时间序列
    @param {int} window - 回看窗口（默认20个交易日）
    @returns {pd.Series} 百分比变动序列（小数形式，如0.05表示5%）
    
    @example
    >>> prices = pd.Series([100, 105, 110])
    >>> pct_changes = transform_pct20(prices, window=1)
    """
    return series.pct_change(periods=window)


def transform_relret20(
    series_a: pd.Series,
    series_b: pd.Series,
    window: int = 20
) -> pd.Series:
    """
    计算相对收益率（A相对于B的20日相对表现）
    
    计算公式: (A_t / A_{t-20}) / (B_t / B_{t-20}) - 1
    或等价于: pct_change(A) - pct_change(B) （近似）
    
    @param {pd.Series} series_a - 序列A（如IWM、中证1000）
    @param {pd.Series} series_b - 序列B（如SPY、沪深300）
    @param {int} window - 回看窗口（默认20个交易日）
    @returns {pd.Series} 相对收益率序列
    
    @example
    >>> iwm = pd.Series([100, 105, 110], index=pd.date_range('2024-01-01', periods=3))
    >>> spy = pd.Series([200, 205, 208], index=pd.date_range('2024-01-01', periods=3))
    >>> relret = transform_relret20(iwm, spy, window=1)
    """
    # 确保索引对齐
    series_a, series_b = series_a.align(series_b, join='inner')
    
    # 计算各自的N日收益率
    ret_a = series_a / series_a.shift(window) - 1
    ret_b = series_b / series_b.shift(window) - 1
    
    # 相对收益 = (1 + ret_a) / (1 + ret_b) - 1
    # 简化为近似: ret_a - ret_b （当收益率较小时）
    # 使用精确公式
    relret = (1 + ret_a) / (1 + ret_b) - 1
    
    return relret


def transform_slope_20_60_ewma(
    series: pd.Series,
    w_fast: float = 0.6,
    w_slow: float = 0.4,
    lmbd: float = 0.94,
    window_fast: int = 20,
    window_slow: int = 60
) -> pd.Series:
    """
    计算20/60日EWMA组合斜率（用于两融余额等）
    
    步骤：
    1. 对原序列分别计算20日和60日的EWMA（指数加权移动平均）
    2. 计算每个EWMA的斜率（当前值 vs 前一个值的变化率）
    3. 按权重组合两个斜率：w_fast * slope_20 + w_slow * slope_60
    
    @param {pd.Series} series - 输入时间序列（如两融余额）
    @param {float} w_fast - 快速斜率权重（默认0.6）
    @param {float} w_slow - 慢速斜率权重（默认0.4）
    @param {float} lmbd - EWMA平滑参数（默认0.94）
    @param {int} window_fast - 快速窗口（默认20）
    @param {int} window_slow - 慢速窗口（默认60）
    @returns {pd.Series} 组合斜率序列
    
    @example
    >>> balance = pd.Series(range(100, 200), index=pd.date_range('2024-01-01', periods=100))
    >>> slope = transform_slope_20_60_ewma(balance)
    """
    # 将lambda转换为pandas的span参数
    # span = (2 / (1 - lambda)) - 1
    span_fast = (2 / (1 - lmbd)) - 1
    span_slow = span_fast  # 使用相同的平滑参数
    
    # 计算EWMA
    ewma_fast = series.ewm(span=window_fast, adjust=False).mean()
    ewma_slow = series.ewm(span=window_slow, adjust=False).mean()
    
    # 计算斜率（相对变化率）
    # slope = (current - previous) / previous
    slope_fast = ewma_fast.pct_change()
    slope_slow = ewma_slow.pct_change()
    
    # 组合斜率
    combined_slope = w_fast * slope_fast + w_slow * slope_slow
    
    return combined_slope


def transform_log_winsor(
    series: pd.Series,
    p_low: float = 0.02,
    p_high: float = 0.98
) -> pd.Series:
    """
    对数变换 + Winsorize截尾（用于VIX等）
    
    步骤：
    1. 对数变换：log(x)
    2. Winsorize：将极端值截尾到指定百分位
    
    @param {pd.Series} series - 输入时间序列（必须为正值）
    @param {float} p_low - 下限百分位（默认0.02，即2%）
    @param {float} p_high - 上限百分位（默认0.98，即98%）
    @returns {pd.Series} 转换后的序列
    
    @example
    >>> vix = pd.Series([10, 15, 20, 50, 100, 12, 14])
    >>> transformed = transform_log_winsor(vix)
    """
    # 对数变换
    log_series = np.log(series)
    
    # 计算百分位数
    lower_bound = log_series.quantile(p_low)
    upper_bound = log_series.quantile(p_high)
    
    # Winsorize：截尾
    winsorized = log_series.clip(lower=lower_bound, upper=upper_bound)
    
    return winsorized


def transform_yoy_std_ffill(
    series: pd.Series,
    freq: str = 'M'
) -> pd.Series:
    """
    同比标准化后前向填充（用于月度PMI等指标）
    
    步骤：
    1. 计算同比变化（12个月前的差值）
    2. 标准化（减均值除标准差）
    3. 前向填充到日频
    
    @param {pd.Series} series - 输入时间序列（月度数据）
    @param {str} freq - 原始频率（'M'=月度）
    @returns {pd.Series} 日频标准化序列
    
    @example
    >>> monthly_pmi = pd.Series([50, 51, 52, 53], index=pd.date_range('2024-01-01', periods=4, freq='MS'))
    >>> daily_std = transform_yoy_std_ffill(monthly_pmi)
    """
    # 计算同比差值（12个月）
    if freq == 'M':
        yoy_diff = series - series.shift(12)
    else:
        # 对于其他频率，可以扩展
        yoy_diff = series - series.shift(12)
    
    # 标准化
    mean_val = yoy_diff.mean()
    std_val = yoy_diff.std()
    
    if std_val > 0:
        standardized = (yoy_diff - mean_val) / std_val
    else:
        standardized = yoy_diff - mean_val

    standardized = standardized.dropna()
    if len(standardized) == 0:
        return standardized

    # 前向填充到工作日频率
    daily_series = forward_fill_to_daily(standardized)
    return daily_series


def transform_raw_winsor(
    series: pd.Series,
    n_sigma: float = 3.0
) -> pd.Series:
    """
    原始值 + Winsorize到±N个标准差（用于股债收益差等）
    
    @param {pd.Series} series - 输入时间序列
    @param {float} n_sigma - 标准差倍数（默认3.0）
    @returns {pd.Series} 截尾后的序列
    
    @example
    >>> eps_yield_diff = pd.Series([0.01, 0.02, 0.03, 0.10, -0.05, 0.02])
    >>> winsorized = transform_raw_winsor(eps_yield_diff)
    """
    mean_val = series.mean()
    std_val = series.std()
    
    lower_bound = mean_val - n_sigma * std_val
    upper_bound = mean_val + n_sigma * std_val
    
    winsorized = series.clip(lower=lower_bound, upper=upper_bound)
    
    return winsorized


def resample_to_weekly(
    series: pd.Series,
    day_of_week: str = 'Fri',
    agg_method: str = 'last'
) -> pd.Series:
    """
    将日频数据重采样到周频（默认使用周五标签）
    
    @param {pd.Series} series - 输入日频时间序列
    @param {str} day_of_week - 周标签（'Mon', 'Tue', 'Wed', 'Thu', 'Fri'）
    @param {str} agg_method - 聚合方法（'last', 'mean', 'sum'等）
    @returns {pd.Series} 周频序列
    
    @example
    >>> daily_data = pd.Series(range(100), index=pd.date_range('2024-01-01', periods=100, freq='B'))
    >>> weekly_data = resample_to_weekly(daily_data)
    """
    # 转换周标签到pandas offset
    # W-FRI 表示周频，以周五为标签
    week_anchor = {
        'Mon': 'W-MON',
        'Tue': 'W-TUE',
        'Wed': 'W-WED',
        'Thu': 'W-THU',
        'Fri': 'W-FRI'
    }
    
    freq_str = week_anchor.get(day_of_week, 'W-FRI')
    
    # 重采样
    if agg_method == 'last':
        resampled = series.resample(freq_str).last()
    elif agg_method == 'mean':
        resampled = series.resample(freq_str).mean()
    elif agg_method == 'sum':
        resampled = series.resample(freq_str).sum()
    elif agg_method == 'first':
        resampled = series.resample(freq_str).first()
    else:
        resampled = series.resample(freq_str).agg(agg_method)
    
    return resampled


def apply_transform(
    series: pd.Series,
    transform_type: str,
    **kwargs
) -> pd.Series:
    """
    通用转换函数分发器
    
    @param {pd.Series} series - 输入序列（或对于relret20，传入元组）
    @param {str} transform_type - 转换类型名称
    @param {dict} kwargs - 额外参数
    @returns {pd.Series} 转换后的序列
    
    @example
    >>> data = pd.Series([100, 102, 105])
    >>> result = apply_transform(data, 'delta20', window=1)
    """
    transform_map = {
        'delta20': transform_delta20,
        'delta20_ffill': transform_delta20_ffill,
        'pct20': transform_pct20,
        'log_winsor': transform_log_winsor,
        'yoy_std_ffill': transform_yoy_std_ffill,
        'raw_winsor': transform_raw_winsor,
        'raw': lambda x: x,  # 不转换
        'slope_20_60_ewma': transform_slope_20_60_ewma,
    }
    
    if transform_type == 'relret20':
        # relret20需要两个序列
        if isinstance(series, tuple) and len(series) == 2:
            return transform_relret20(series[0], series[1], **kwargs)
        else:
            raise ValueError("relret20 requires a tuple of two series")
    
    transform_func = transform_map.get(transform_type)
    
    if transform_func is None:
        raise ValueError(f"Unknown transform type: {transform_type}")
    
    return transform_func(series, **kwargs)


def forward_fill_to_daily(
    series: pd.Series,
    start_date: Optional[pd.Timestamp] = None,
    end_date: Optional[pd.Timestamp] = None,
    freq: str = 'B'  # Business day
) -> pd.Series:
    """
    将低频数据前向填充到日频（工作日）
    
    @param {pd.Series} series - 输入时间序列（低频，如月度）
    @param {pd.Timestamp} start_date - 开始日期（可选）
    @param {pd.Timestamp} end_date - 结束日期（可选）
    @param {str} freq - 目标频率（'B'=工作日, 'D'=日历日）
    @returns {pd.Series} 日频序列
    
    @example
    >>> monthly = pd.Series([50, 51, 52], index=pd.date_range('2024-01-01', periods=3, freq='MS'))
    >>> daily = forward_fill_to_daily(monthly)
    """
    if start_date is None:
        start_date = series.index.min()
    if end_date is None:
        end_date = series.index.max()
    
    # 创建完整的日期范围
    date_range = pd.date_range(start=start_date, end=end_date, freq=freq)
    
    # 重索引并前向填充
    daily_series = series.reindex(date_range, method='ffill')
    
    return daily_series


def calculate_5day_sum(series: pd.Series, window: int = 5) -> pd.Series:
    """
    计算5日滚动和（用于ETF净流入等）
    
    @param {pd.Series} series - 输入时间序列
    @param {int} window - 窗口大小（默认5）
    @returns {pd.Series} 滚动和序列
    
    @example
    >>> daily_flow = pd.Series([100, -50, 200, -100, 150])
    >>> flow_5d = calculate_5day_sum(daily_flow)
    """
    return series.rolling(window=window, min_periods=1).sum()


def align_series(
    *series_list: pd.Series,
    join: str = 'inner'
) -> Tuple[pd.Series, ...]:
    """
    对齐多个时间序列的索引
    
    @param {pd.Series} series_list - 多个序列
    @param {str} join - 对齐方式（'inner', 'outer', 'left', 'right'）
    @returns {Tuple[pd.Series, ...]} 对齐后的序列元组
    
    @example
    >>> s1 = pd.Series([1, 2, 3], index=[0, 1, 2])
    >>> s2 = pd.Series([4, 5, 6], index=[1, 2, 3])
    >>> aligned1, aligned2 = align_series(s1, s2, join='inner')
    """
    if len(series_list) < 2:
        return series_list
    
    # 逐步对齐
    result = list(series_list)
    common_index = result[0].index
    
    for i in range(1, len(result)):
        if join == 'inner':
            common_index = common_index.intersection(result[i].index)
        elif join == 'outer':
            common_index = common_index.union(result[i].index)
    
    # 重新索引所有序列
    aligned = tuple(s.reindex(common_index) for s in result)
    
    return aligned

