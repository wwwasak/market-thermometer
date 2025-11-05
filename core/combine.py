"""
确认层组合逻辑模块

实现软确认、硬否决、配对规则和最终灯色合成。
包含两种配对规则：
- Rule A (一致性优先): 两个同色→该色，否则→黄
- Rule B (强分歧红灯): 一红一绿→红，其他同Rule A

所有函数都是纯函数，便于单元测试。
"""

import pandas as pd
import numpy as np
from typing import Literal, List, Dict, Tuple, Optional


# 灯色类型定义
LampColor = Literal['G', 'Y', 'R']  # Green, Yellow, Red


def pair_combine(
    lamp1: pd.Series,
    lamp2: pd.Series,
    rule: Literal['A', 'B'] = 'A'
) -> pd.Series:
    """
    配对灯色组合规则
    
    Rule A (一致性优先，默认):
    - 两个都是绿 → 绿
    - 两个都是红 → 红
    - 其他情况 → 黄
    
    Rule B (强分歧红灯):
    - 一个红一个绿 → 红（强分歧视为风险）
    - 两个都是绿 → 绿
    - 两个都是红 → 红
    - 其他情况 → 黄
    
    @param {pd.Series} lamp1 - 第一个灯色序列（'G', 'Y', 'R'）
    @param {pd.Series} lamp2 - 第二个灯色序列
    @param {str} rule - 规则类型（'A' 或 'B'）
    @returns {pd.Series} 组合后的灯色序列
    
    @example
    >>> lamp1 = pd.Series(['G', 'R', 'G', 'Y'])
    >>> lamp2 = pd.Series(['G', 'R', 'R', 'Y'])
    >>> result = pair_combine(lamp1, lamp2, rule='A')
    """
    # 确保索引对齐
    lamp1, lamp2 = lamp1.align(lamp2, join='outer')
    
    def combine_rule_a(l1, l2):
        """Rule A: 一致性优先"""
        if pd.isna(l1) or pd.isna(l2):
            return 'Y'
        if l1 == l2 == 'G':
            return 'G'
        elif l1 == l2 == 'R':
            return 'R'
        else:
            return 'Y'
    
    def combine_rule_b(l1, l2):
        """Rule B: 强分歧红灯"""
        if pd.isna(l1) or pd.isna(l2):
            return 'Y'
        if l1 == l2 == 'G':
            return 'G'
        elif l1 == l2 == 'R':
            return 'R'
        elif (l1 == 'R' and l2 == 'G') or (l1 == 'G' and l2 == 'R'):
            return 'R'  # 强分歧 → 红
        else:
            return 'Y'
    
    if rule == 'A':
        return pd.Series(
            [combine_rule_a(l1, l2) for l1, l2 in zip(lamp1, lamp2)],
            index=lamp1.index
        )
    elif rule == 'B':
        return pd.Series(
            [combine_rule_b(l1, l2) for l1, l2 in zip(lamp1, lamp2)],
            index=lamp1.index
        )
    else:
        raise ValueError(f"Unknown rule: {rule}. Must be 'A' or 'B'")


def hard_veto_min(
    lamps: List[pd.Series],
    persistence: int = 0
) -> pd.Series:
    """
    硬否决规则：多个灯色取MIN（红 < 黄 < 绿）
    
    逻辑：
    - 任何一个红 → 红（最悲观）
    - 全部绿 → 绿（最乐观）
    - 其他 → 黄
    
    可选：应用持续性规则，红灯需要持续N期才生效
    
    @param {List[pd.Series]} lamps - 灯色序列列表
    @param {int} persistence - 持续期数（0=无持续性）
    @returns {pd.Series} 组合后的灯色
    
    @example
    >>> lamp1 = pd.Series(['G', 'G', 'Y', 'R'])
    >>> lamp2 = pd.Series(['G', 'Y', 'Y', 'Y'])
    >>> result = hard_veto_min([lamp1, lamp2])
    >>> # ['G', 'Y', 'Y', 'R']
    """
    if not lamps:
        raise ValueError("At least one lamp series is required")
    
    # 定义灯色优先级（数值越小越悲观）
    lamp_priority = {'R': 0, 'Y': 1, 'G': 2}
    
    # 将灯色转换为数值
    lamp_values = []
    for lamp in lamps:
        values = lamp.map(lamp_priority).fillna(1)  # NaN当作Yellow
        lamp_values.append(values)
    
    # 取最小值（最悲观）
    min_values = pd.concat(lamp_values, axis=1).min(axis=1)
    
    # 转换回灯色
    reverse_map = {v: k for k, v in lamp_priority.items()}
    combined = min_values.map(reverse_map)
    
    # 应用持续性
    if persistence > 0:
        from core.scoring import apply_persistence
        combined = apply_persistence(combined, persistence, default_value='Y')
    
    return combined


def soft_confirm_weighted(
    lamps: List[pd.Series],
    weights: List[float],
    green_threshold: float = 1.6,
    red_threshold: float = 0.8
) -> pd.Series:
    """
    软确认加权投票
    
    步骤：
    1. 将灯色映射到数值：Green=2, Yellow=1, Red=0
    2. 计算加权平均：S = Σ(weight_i * value_i)
    3. 根据阈值分类：
       - S ≥ green_threshold → Green
       - S ≤ red_threshold → Red
       - 其他 → Yellow
    
    @param {List[pd.Series]} lamps - 灯色序列列表
    @param {List[float]} weights - 权重列表（应总和为1.0）
    @param {float} green_threshold - 绿灯阈值（默认1.6）
    @param {float} red_threshold - 红灯阈值（默认0.8）
    @returns {pd.Series} 加权后的灯色
    
    @example
    >>> lamps = [
    ...     pd.Series(['G', 'Y', 'R']),
    ...     pd.Series(['G', 'G', 'Y']),
    ...     pd.Series(['Y', 'Y', 'Y'])
    ... ]
    >>> weights = [0.5, 0.3, 0.2]
    >>> result = soft_confirm_weighted(lamps, weights)
    """
    if len(lamps) != len(weights):
        raise ValueError(f"Number of lamps ({len(lamps)}) must match weights ({len(weights)})")
    
    if not lamps:
        raise ValueError("At least one lamp series is required")
    
    # 归一化权重
    weights_array = np.array(weights)
    weights_normalized = weights_array / weights_array.sum()
    
    # 灯色到数值的映射
    lamp_to_value = {'G': 2.0, 'Y': 1.0, 'R': 0.0}
    
    # 转换为数值并计算加权平均
    weighted_values = []
    for lamp, weight in zip(lamps, weights_normalized):
        values = lamp.map(lamp_to_value).fillna(1.0)  # NaN当作Yellow
        weighted_values.append(values * weight)
    
    # 计算加权和
    weighted_sum = pd.concat(weighted_values, axis=1).sum(axis=1)
    
    # 根据阈值分类
    def classify(s):
        if pd.isna(s):
            return 'Y'
        elif s >= green_threshold:
            return 'G'
        elif s <= red_threshold:
            return 'R'
        else:
            return 'Y'
    
    return weighted_sum.apply(classify)


def final_lamp(
    hard_veto: pd.Series,
    soft_confirm: pd.Series
) -> pd.Series:
    """
    最终灯色合成
    
    规则（硬否决优先）：
    - 如果 hard_veto == Red → Red（硬否决）
    - 否则如果 soft_confirm == Green → Green（软确认通过）
    - 其他 → Yellow（中性）
    
    @param {pd.Series} hard_veto - 硬否决灯色
    @param {pd.Series} soft_confirm - 软确认灯色
    @returns {pd.Series} 最终灯色
    
    @example
    >>> hard = pd.Series(['Y', 'R', 'Y', 'Y'])
    >>> soft = pd.Series(['G', 'G', 'Y', 'R'])
    >>> final = final_lamp(hard, soft)
    >>> # ['G', 'R', 'Y', 'Y']
    """
    # 确保索引对齐
    hard_veto, soft_confirm = hard_veto.align(soft_confirm, join='outer')
    
    def combine(h, s):
        if pd.isna(h) or pd.isna(s):
            return 'Y'
        if h == 'R':
            return 'R'  # 硬否决优先
        elif s == 'G':
            return 'G'  # 软确认通过
        else:
            return 'Y'  # 默认黄色
    
    return pd.Series(
        [combine(h, s) for h, s in zip(hard_veto, soft_confirm)],
        index=hard_veto.index
    )


def combine_multiple_pairs(
    pair_lamps: Dict[str, Tuple[pd.Series, pd.Series]],
    rule: Literal['A', 'B'] = 'A'
) -> Dict[str, pd.Series]:
    """
    批量处理多个配对
    
    @param {Dict} pair_lamps - 配对字典 {pair_id: (lamp1, lamp2)}
    @param {str} rule - 配对规则
    @returns {Dict} 组合结果字典 {pair_id: combined_lamp}
    
    @example
    >>> pairs = {
    ...     'PAIR_CNH_CNY': (pd.Series(['G', 'Y']), pd.Series(['G', 'G'])),
    ...     'PAIR_TWEX_DXY': (pd.Series(['R', 'Y']), pd.Series(['R', 'Y']))
    ... }
    >>> result = combine_multiple_pairs(pairs, rule='A')
    """
    result = {}
    for pair_id, (lamp1, lamp2) in pair_lamps.items():
        result[pair_id] = pair_combine(lamp1, lamp2, rule=rule)
    return result


def build_confirm_layer(
    main_lamps: Dict[str, pd.Series],
    observer_lamps: Dict[str, pd.Series],
    pair_lamps: Dict[str, Tuple[pd.Series, pd.Series]],
    config: Dict
) -> Dict[str, pd.Series]:
    """
    构建完整的确认层
    
    @param {Dict} main_lamps - 主要指标灯色 {code: lamp_series}
    @param {Dict} observer_lamps - 观察者单个灯色 {code: lamp_series}
    @param {Dict} pair_lamps - 配对灯色 {pair_id: (lamp1, lamp2)}
    @param {Dict} config - 配置参数
        - hard_veto_codes: List[str] - 硬否决指标代码
        - hard_veto_persistence: int - 硬否决持续期数
        - soft_confirm_codes: List[str] - 软确认指标代码
        - soft_confirm_weights: Dict[str, float] - 软确认权重
        - soft_confirm_green: float - 软确认绿阈值
        - soft_confirm_red: float - 软确认红阈值
        - pair_rule: str - 配对规则（'A' 或 'B'）
    @returns {Dict} 结果字典
        - 'hard_veto': 硬否决灯色
        - 'soft_confirm': 软确认灯色
        - 'final': 最终灯色
        - 'pairs': 配对组合结果
    
    @example
    >>> # 完整示例见单元测试
    """
    # 处理配对
    pair_rule = config.get('pair_rule', 'A')
    pairs_combined = combine_multiple_pairs(pair_lamps, rule=pair_rule)
    
    # 硬否决
    hard_veto_codes = config.get('hard_veto_codes', [])
    hard_veto_lamps = []
    for code in hard_veto_codes:
        if code in observer_lamps:
            hard_veto_lamps.append(observer_lamps[code])
    
    if hard_veto_lamps:
        hard_persistence = config.get('hard_veto_persistence', 0)
        hard_veto_result = hard_veto_min(hard_veto_lamps, persistence=hard_persistence)
    else:
        # 如果没有硬否决指标，默认为黄色（不触发）
        if observer_lamps:
            first_lamp = list(observer_lamps.values())[0]
            hard_veto_result = pd.Series(['Y'] * len(first_lamp), index=first_lamp.index)
        else:
            hard_veto_result = pd.Series(['Y'])
    
    # 软确认
    soft_confirm_codes = config.get('soft_confirm_codes', [])
    soft_confirm_lamps = []
    soft_confirm_weights_list = []
    
    for code in soft_confirm_codes:
        # 检查是否是配对
        if code in pairs_combined:
            soft_confirm_lamps.append(pairs_combined[code])
            soft_confirm_weights_list.append(config['soft_confirm_weights'][code])
        # 检查是否是单个观察者
        elif code in observer_lamps:
            soft_confirm_lamps.append(observer_lamps[code])
            soft_confirm_weights_list.append(config['soft_confirm_weights'][code])
    
    if soft_confirm_lamps:
        soft_green = config.get('soft_confirm_green', 1.6)
        soft_red = config.get('soft_confirm_red', 0.8)
        soft_confirm_result = soft_confirm_weighted(
            soft_confirm_lamps,
            soft_confirm_weights_list,
            green_threshold=soft_green,
            red_threshold=soft_red
        )
    else:
        # 如果没有软确认指标，默认为黄色
        soft_confirm_result = pd.Series(['Y'] * len(hard_veto_result), index=hard_veto_result.index)
    
    # 最终合成
    final_result = final_lamp(hard_veto_result, soft_confirm_result)
    
    return {
        'hard_veto': hard_veto_result,
        'soft_confirm': soft_confirm_result,
        'final': final_result,
        'pairs': pairs_combined
    }


def analyze_lamp_distribution(lamp: pd.Series) -> Dict[str, float]:
    """
    分析灯色分布
    
    @param {pd.Series} lamp - 灯色序列
    @returns {Dict} 分布统计 {'G': 0.3, 'Y': 0.5, 'R': 0.2}
    
    @example
    >>> lamps = pd.Series(['G', 'G', 'Y', 'R'])
    >>> dist = analyze_lamp_distribution(lamps)
    """
    counts = lamp.value_counts()
    total = len(lamp)
    
    distribution = {}
    for color in ['G', 'Y', 'R']:
        distribution[color] = counts.get(color, 0) / total if total > 0 else 0.0
    
    return distribution


def lamp_to_numeric(lamp: pd.Series) -> pd.Series:
    """
    将灯色转换为数值（用于可视化）
    
    @param {pd.Series} lamp - 灯色序列
    @returns {pd.Series} 数值序列（G=2, Y=1, R=0）
    
    @example
    >>> lamps = pd.Series(['G', 'Y', 'R'])
    >>> numeric = lamp_to_numeric(lamps)
    >>> # [2, 1, 0]
    """
    mapping = {'G': 2, 'Y': 1, 'R': 0}
    return lamp.map(mapping)


def numeric_to_lamp(numeric: pd.Series) -> pd.Series:
    """
    将数值转换为灯色
    
    @param {pd.Series} numeric - 数值序列
    @returns {pd.Series} 灯色序列
    
    @example
    >>> values = pd.Series([2, 1, 0, 1.5])
    >>> lamps = numeric_to_lamp(values)
    """
    def classify(v):
        if pd.isna(v):
            return 'Y'
        elif v >= 1.5:
            return 'G'
        elif v <= 0.5:
            return 'R'
        else:
            return 'Y'
    
    return numeric.apply(classify)


def get_lamp_changes(lamp: pd.Series) -> pd.Series:
    """
    检测灯色变化点
    
    @param {pd.Series} lamp - 灯色序列
    @returns {pd.Series} 布尔序列（True=发生变化）
    
    @example
    >>> lamps = pd.Series(['G', 'G', 'Y', 'Y', 'R'])
    >>> changes = get_lamp_changes(lamps)
    >>> # [False, False, True, False, True]
    """
    return lamp != lamp.shift(1)


def count_consecutive_lamps(lamp: pd.Series, color: LampColor) -> pd.Series:
    """
    计算连续相同灯色的次数
    
    @param {pd.Series} lamp - 灯色序列
    @param {str} color - 要统计的颜色
    @returns {pd.Series} 连续次数序列
    
    @example
    >>> lamps = pd.Series(['G', 'G', 'G', 'Y', 'R', 'R'])
    >>> consecutive_g = count_consecutive_lamps(lamps, 'G')
    >>> # [1, 2, 3, 0, 0, 0]
    """
    is_color = (lamp == color).astype(int)
    
    # 计算连续次数
    consecutive = is_color * (is_color.groupby((is_color != is_color.shift()).cumsum()).cumcount() + 1)
    
    return consecutive

