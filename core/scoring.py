"""
评分和标准化模块

包含Z分数计算、MAD-Z计算、评分映射、regime判断、灯色判断等核心逻辑。
所有函数都是纯函数，便于单元测试。
"""

import pandas as pd
import numpy as np
from typing import Literal, Optional, Tuple


def rolling_z(
    series: pd.Series,
    window: int = 60,
    min_periods: Optional[int] = None
) -> pd.Series:
    """
    计算滚动Z分数（标准化）
    
    Z = (X - μ) / σ
    其中μ和σ是滚动窗口内的均值和标准差
    
    @param {pd.Series} series - 输入时间序列
    @param {int} window - 滚动窗口大小（默认60个交易日）
    @param {int} min_periods - 最小观测数（默认为window）
    @returns {pd.Series} Z分数序列
    
    @example
    >>> prices = pd.Series([100, 102, 105, 103, 107, 110])
    >>> z_scores = rolling_z(prices, window=3)
    """
    if min_periods is None:
        min_periods = window
    
    # 计算滚动均值和标准差
    rolling_mean = series.rolling(window=window, min_periods=min_periods).mean()
    rolling_std = series.rolling(window=window, min_periods=min_periods).std()
    
    # 计算Z分数
    z = (series - rolling_mean) / rolling_std
    
    # 处理标准差为0的情况
    z = z.replace([np.inf, -np.inf], np.nan)
    
    return z


def rolling_madz(
    series: pd.Series,
    window: int = 60,
    min_periods: Optional[int] = None,
    mad_constant: float = 1.4826
) -> pd.Series:
    """
    计算滚动MAD-Z分数（稳健标准化）
    
    MAD-Z = (X - median) / (MAD * 1.4826)
    其中MAD是中位数绝对偏差（Median Absolute Deviation）
    1.4826是使MAD与正态分布标准差一致的常数
    
    MAD-Z对异常值更稳健，适合有尖峰厚尾的数据
    
    @param {pd.Series} series - 输入时间序列
    @param {int} window - 滚动窗口大小（默认60）
    @param {int} min_periods - 最小观测数（默认为window）
    @param {float} mad_constant - MAD缩放常数（默认1.4826）
    @returns {pd.Series} MAD-Z分数序列
    
    @example
    >>> data = pd.Series([10, 11, 12, 100, 13, 14])  # 包含异常值100
    >>> madz = rolling_madz(data, window=3)
    """
    if min_periods is None:
        min_periods = window
    
    # 计算滚动中位数
    rolling_median = series.rolling(window=window, min_periods=min_periods).median()
    
    # 计算MAD: median(|X - median(X)|)
    abs_dev = (series - rolling_median).abs()
    rolling_mad = abs_dev.rolling(window=window, min_periods=min_periods).median()
    
    # 计算MAD-Z分数
    # 使用缩放后的MAD作为稳健标准差估计
    madz = (series - rolling_median) / (rolling_mad * mad_constant)
    
    # 处理MAD为0的情况
    madz = madz.replace([np.inf, -np.inf], np.nan)
    
    return madz


def standardize_with_direction(
    series: pd.Series,
    direction: Literal['up_good', 'down_good'],
    z_type: Literal['Z', 'MADZ'] = 'Z',
    window: int = 60,
    **kwargs
) -> pd.Series:
    """
    考虑方向的标准化
    
    对于up_good指标：Z分数保持不变
    对于down_good指标：Z分数取反（使得值越低，Z分数越高）
    
    @param {pd.Series} series - 输入序列
    @param {str} direction - 'up_good'（值越高越好）或 'down_good'（值越低越好）
    @param {str} z_type - 'Z'（标准Z分数）或 'MADZ'（稳健Z分数）
    @param {int} window - 滚动窗口大小
    @param {dict} kwargs - 传递给Z计算函数的其他参数
    @returns {pd.Series} 方向统一后的Z分数
    
    @example
    >>> vix = pd.Series([15, 20, 25, 18, 16])  # VIX，down_good
    >>> z = standardize_with_direction(vix, 'down_good', 'Z', window=3)
    """
    # 计算原始Z分数
    if z_type == 'Z':
        z = rolling_z(series, window=window, **kwargs)
    elif z_type == 'MADZ':
        z = rolling_madz(series, window=window, **kwargs)
    else:
        raise ValueError(f"Unknown z_type: {z_type}")
    
    # 根据方向调整符号
    if direction == 'down_good':
        # 对于down_good指标，取反Z分数
        # 这样，值越低 → 原始Z越负 → 取反后Z越正
        z = -z
    elif direction == 'up_good':
        # 保持不变
        pass
    else:
        raise ValueError(f"Unknown direction: {direction}")
    
    return z


def score_from_z(
    z: pd.Series,
    center: float = 50.0,
    scale: float = 10.0,
    min_score: float = 0.0,
    max_score: float = 100.0
) -> pd.Series:
    """
    将Z分数映射到0-100评分区间
    
    Score = clamp(center + scale * Z, min_score, max_score)
    默认：Score = clamp(50 + 10*Z, 0, 100)
    
    解释：
    - Z = 0 → Score = 50（中性）
    - Z = +2 → Score = 70（Attack区域）
    - Z = -1 → Score = 40（Defense区域）
    - Z = +5 → Score = 100（上限）
    
    @param {pd.Series} z - Z分数序列
    @param {float} center - 中心点（默认50）
    @param {float} scale - 缩放系数（默认10）
    @param {float} min_score - 最小分数（默认0）
    @param {float} max_score - 最大分数（默认100）
    @returns {pd.Series} 评分序列（0-100）
    
    @example
    >>> z = pd.Series([0, 1, -1, 2, -2])
    >>> scores = score_from_z(z)
    """
    # 线性映射
    score = center + scale * z
    
    # 截断到[min_score, max_score]
    score = score.clip(lower=min_score, upper=max_score)
    
    return score


def lamp_from_score(
    score: pd.Series,
    green_threshold: float = 60.0,
    red_threshold: float = 40.0
) -> pd.Series:
    """
    根据评分判断灯色
    
    - Score ≥ green_threshold → 'G' (Green)
    - Score ≤ red_threshold → 'R' (Red)
    - 其他 → 'Y' (Yellow)
    
    @param {pd.Series} score - 评分序列（0-100）
    @param {float} green_threshold - 绿灯阈值（默认60）
    @param {float} red_threshold - 红灯阈值（默认40）
    @returns {pd.Series} 灯色序列（'G', 'Y', 'R'）
    
    @example
    >>> scores = pd.Series([70, 50, 30])
    >>> lamps = lamp_from_score(scores)
    """
    def classify(s):
        if pd.isna(s):
            return 'Y'
        elif s >= green_threshold:
            return 'G'
        elif s <= red_threshold:
            return 'R'
        else:
            return 'Y'
    
    return score.apply(classify)


def regime_from_score(
    score: pd.Series,
    attack_threshold: float = 70.0,
    defense_threshold: float = 40.0,
    persistence: int = 0
) -> pd.Series:
    """
    根据评分判断市场态势（Regime）
    
    - Score ≥ attack_threshold → 'Attack'（进攻）
    - Score ≤ defense_threshold → 'Defense'（防御）
    - 其他 → 'Balanced'（平衡）
    
    可选：持续性确认（persistence > 0）
    需要连续N期满足条件才切换regime
    
    @param {pd.Series} score - 评分序列
    @param {float} attack_threshold - Attack阈值（默认70）
    @param {float} defense_threshold - Defense阈值（默认40）
    @param {int} persistence - 持续确认期数（0=无确认，>0=需要N期确认）
    @returns {pd.Series} Regime序列（'Attack', 'Balanced', 'Defense'）
    
    @example
    >>> scores = pd.Series([75, 72, 68, 45, 42, 38])
    >>> regimes = regime_from_score(scores, persistence=2)
    """
    # 初步分类
    def classify(s):
        if pd.isna(s):
            return 'Balanced'
        elif s >= attack_threshold:
            return 'Attack'
        elif s <= defense_threshold:
            return 'Defense'
        else:
            return 'Balanced'
    
    regime = score.apply(classify)
    
    # 如果需要持续性确认
    if persistence > 0:
        regime = apply_persistence(regime, persistence)
    
    return regime


def apply_persistence(
    series: pd.Series,
    persistence: int,
    default_value: Optional[str] = None
) -> pd.Series:
    """
    应用持续性规则：只有连续N期都是某个值时才切换
    
    这可以减少频繁的状态切换（减少噪音）
    
    @param {pd.Series} series - 输入序列（如regime或lamp）
    @param {int} persistence - 持续期数
    @param {str} default_value - 默认值（可选，用于初始化）
    @returns {pd.Series} 应用持续性后的序列
    
    @example
    >>> regimes = pd.Series(['Attack', 'Attack', 'Balanced', 'Attack', 'Attack'])
    >>> smoothed = apply_persistence(regimes, persistence=2)
    """
    if persistence <= 0:
        return series
    
    result = series.copy()
    
    if default_value is None:
        current_state = series.iloc[0] if len(series) > 0 else None
    else:
        current_state = default_value
    
    confirmed_count = 0
    pending_state = current_state
    
    for i in range(len(series)):
        candidate = series.iloc[i]
        
        if pd.isna(candidate):
            result.iloc[i] = current_state
            continue
        
        if candidate == current_state:
            # 继续保持当前状态
            confirmed_count = 0
            pending_state = current_state
        elif candidate == pending_state:
            # 延续待确认状态
            confirmed_count += 1
            if confirmed_count >= persistence:
                # 达到持续要求，切换状态
                current_state = pending_state
                confirmed_count = 0
        else:
            # 新的候选状态
            pending_state = candidate
            confirmed_count = 1
        
        result.iloc[i] = current_state
    
    return result


def weighted_score(
    scores: pd.DataFrame,
    weights: list,
    normalize: bool = True
) -> pd.Series:
    """
    计算加权总分
    
    对于每个时间点，只使用有效（非NaN）的指标进行加权，并动态归一化权重
    
    @param {pd.DataFrame} scores - 评分矩阵（每列是一个指标）
    @param {list} weights - 权重列表（与列顺序对应）
    @param {bool} normalize - 是否归一化权重到总和为1
    @returns {pd.Series} 加权总分
    
    @example
    >>> df = pd.DataFrame({'ind1': [70, 60, np.nan], 'ind2': [50, 80, 90]})
    >>> weights = [0.6, 0.4]
    >>> total = weighted_score(df, weights)
    # 第1行: 70*0.6 + 50*0.4 = 62
    # 第2行: 60*0.6 + 80*0.4 = 68
    # 第3行: 90*1.0 = 90 (只有ind2有值，权重归一化为1.0)
    """
    if len(weights) != len(scores.columns):
        raise ValueError(f"Weights length {len(weights)} must match columns {len(scores.columns)}")
    
    weights_array = np.array(weights)
    
    if normalize:
        weights_array = weights_array / weights_array.sum()
    
    # 对每一行单独计算加权和，动态处理NaN
    def weighted_sum_row(row):
        """对单行计算加权和，只使用非NaN值并重新归一化权重"""
        valid_mask = row.notna()
        
        if not valid_mask.any():
            # 全部为NaN，返回NaN
            return np.nan
        
        # 只使用有效的值和对应的权重
        valid_values = row[valid_mask].values
        valid_weights = weights_array[valid_mask.values]
        
        # 重新归一化权重
        normalized_weights = valid_weights / valid_weights.sum()
        
        # 计算加权和
        weighted_sum = (valid_values * normalized_weights).sum()
        
        return weighted_sum
    
    # 应用到每一行
    result = scores.apply(weighted_sum_row, axis=1)
    
    return result


def check_extreme_jump(
    series: pd.Series,
    window: int = 10,
    z_window: int = 60,
    threshold: float = 1.5
) -> pd.Series:
    """
    检测极端跳升（用于HY OAS硬否决规则）
    
    判断标准：ΔZ(window) > threshold
    即：Z分数在window期内的变化超过threshold
    
    @param {pd.Series} series - 原始时间序列
    @param {int} window - 观察窗口（默认10个交易日，约2周）
    @param {int} z_window - Z分数计算窗口（默认60）
    @param {float} threshold - 跳升阈值（默认1.5）
    @returns {pd.Series} 布尔序列（True=检测到极端跳升）
    
    @example
    >>> hy_oas = pd.Series([3.5, 3.6, 3.7, 5.0, 5.2, 5.1])
    >>> jumps = check_extreme_jump(hy_oas, window=2, z_window=3, threshold=1.0)
    """
    # 计算Z分数
    z = rolling_z(series, window=z_window)
    
    # 计算Z分数的变化
    delta_z = z - z.shift(window)
    
    # 检测是否超过阈值
    is_extreme = delta_z > threshold
    
    return is_extreme


def check_extreme_z(
    z: pd.Series,
    threshold: float = 2.0
) -> pd.Series:
    """
    检测Z分数是否超过极端阈值
    
    @param {pd.Series} z - Z分数序列
    @param {float} threshold - 阈值（默认2.0）
    @returns {pd.Series} 布尔序列（True=超过阈值）
    
    @example
    >>> z = pd.Series([0.5, 1.5, 2.5, 1.0])
    >>> extreme = check_extreme_z(z, threshold=2.0)
    """
    return z > threshold


def calculate_composite_score(
    indicator_scores: pd.DataFrame,
    weights: list,
    market: str = 'CN'
) -> pd.Series:
    """
    计算市场综合评分（主要指标的加权平均）
    
    @param {pd.DataFrame} indicator_scores - 指标评分矩阵
    @param {list} weights - 权重列表
    @param {str} market - 市场标识（'CN' 或 'US'）
    @returns {pd.Series} 综合评分
    
    @example
    >>> scores = pd.DataFrame({
    ...     'IND1': [70, 65, 60],
    ...     'IND2': [60, 55, 50]
    ... })
    >>> weights = [60, 40]
    >>> composite = calculate_composite_score(scores, weights)
    """
    # 权重归一化
    weights_array = np.array(weights)
    weights_normalized = weights_array / weights_array.sum() * 100
    
    # 加权平均
    composite = weighted_score(indicator_scores, weights_normalized, normalize=True)
    
    return composite


def batch_standardize(
    data_dict: dict,
    config_dict: dict
) -> dict:
    """
    批量标准化多个指标
    
    @param {dict} data_dict - 指标数据字典 {code: series}
    @param {dict} config_dict - 指标配置字典 {code: {direction, z_type, z_window}}
    @returns {dict} Z分数字典 {code: z_series}
    
    @example
    >>> data = {'VIX': pd.Series([15, 20, 25]), 'SPY': pd.Series([400, 410, 405])}
    >>> config = {
    ...     'VIX': {'direction': 'down_good', 'z_type': 'MADZ', 'z_window': 40},
    ...     'SPY': {'direction': 'up_good', 'z_type': 'Z', 'z_window': 60}
    ... }
    >>> z_dict = batch_standardize(data, config)
    """
    z_dict = {}
    
    for code, series in data_dict.items():
        if code not in config_dict:
            continue
        
        cfg = config_dict[code]
        direction = cfg.get('direction', 'up_good')
        z_type = cfg.get('z_type', 'Z')
        z_window = cfg.get('z_window', 60)
        
        z = standardize_with_direction(
            series,
            direction=direction,
            z_type=z_type,
            window=z_window
        )
        
        z_dict[code] = z
    
    return z_dict


def batch_score(
    z_dict: dict,
    **score_kwargs
) -> dict:
    """
    批量计算评分
    
    @param {dict} z_dict - Z分数字典 {code: z_series}
    @param {dict} score_kwargs - 传递给score_from_z的参数
    @returns {dict} 评分字典 {code: score_series}
    
    @example
    >>> z_dict = {'IND1': pd.Series([0, 1, -1]), 'IND2': pd.Series([0.5, -0.5, 1.5])}
    >>> scores = batch_score(z_dict)
    """
    score_dict = {}
    
    for code, z_series in z_dict.items():
        score = score_from_z(z_series, **score_kwargs)
        score_dict[code] = score
    
    return score_dict

