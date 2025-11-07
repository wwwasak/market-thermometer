"""
指标注册表 - 定义所有CN和US指标的元数据配置

这个文件是reference实现，实际开发时在core/indicator_registry.py中实现。
"""

# ===== CN市场主指标（6个，参与评分） =====

CN_MAIN_INDICATORS = {
    'CN_MARGIN_SLOPE': {
        'name': '两融余额斜率',
        'name_en': 'Margin Balance Slope',
        'market': 'CN',
        'role': 'main',  # 参与CN市场综合评分
        'direction': 'up_good',  # 上升为好
        
        # 数据转换配置
        'transform': 'slope_20_60_ewma',
        'transform_params': {
            'w_fast': 0.6,
            'w_slow': 0.4,
            'lmbd': 0.94  # EWMA lambda
        },
        
        # 标准化配置
        'z_method': 'z',  # 普通Z分数
        'z_window': 60,   # 60个交易日
        'direction_sign': 1,  # up_good对应+1
        
        # 数据源配置
        'source': 'csv',  # 需要CSV导入
        'source_symbol': None,  # CSV文件自定义
        'required_columns': ['date', 'margin_balance'],  # CSV必需列
        
        # 周视图配置
        'weekly_agg': 'last',  # 取每周最后一个值（Friday）
        
        # 依赖关系
        'dependencies': [],  # 无依赖
        
        # 数据获取频率
        'fetch_frequency': 'daily',
        'typical_update_time': '19:00',  # 通常19:00后可获取当日数据
        
        # 描述和计算说明
        'description': '两融余额的20日和60日EWMA斜率的加权组合（0.6/0.4），反映融资融券市场活跃度趋势',
        'calculation': 'slope_20 = slope(ewma(balance, span=20)); slope_60 = slope(ewma(balance, span=60)); final = 0.6*slope_20 + 0.4*slope_60'
    },
    
    'CNH_PCT20': {
        'name': 'USD/CNH 20日%变动',
        'name_en': 'USD/CNH 20-day % Change',
        'market': 'CN',
        'role': 'main',
        'direction': 'down_good',  # CNH贬值（数值上升）为坏
        
        'transform': 'pct20',
        'transform_params': {},
        
        'z_method': 'madz',
        'z_window': 60,
        'direction_sign': -1,
        
        'source': 'yfinance',
        'source_symbol': 'CNH=X',
        'required_columns': None,
        
        'weekly_agg': 'last',
        
        'dependencies': [],
        
        'fetch_frequency': 'daily',
        'typical_update_time': '次日凌晨',
        
        'description': '离岸人民币20日百分比变动率，反映人民币汇率短期趋势',
        'calculation': 'pct20 = (CNH_t - CNH_{t-20}) / CNH_{t-20} * 100'
    },
    
    'NORTH_TURNOVER_SHARE': {
        'name': '北向成交额占比',
        'name_en': 'Northbound Turnover Share',
        'market': 'CN',
        'role': 'main',
        'direction': 'up_good',
        
        'transform': 'raw',  # 原始占比值
        'transform_params': {},
        
        'z_method': 'madz',
        'z_window': 60,
        'direction_sign': 1,
        
        'source': 'csv',
        'source_symbol': None,
        'required_columns': ['date', 'north_turnover', 'total_turnover'],  # 或直接提供比率
        
        'weekly_agg': 'last',  # 或 'mean' 取周平均
        
        'dependencies': [],
        
        'fetch_frequency': 'daily',
        'typical_update_time': '19:00',
        
        'description': '北向资金（陆股通）成交额占全A成交额的比例，反映外资参与度',
        'calculation': 'ratio = north_turnover / total_A_turnover'
    },
    
    'CSI1000_OVER_300_REL20': {
        'name': '中证1000/沪深300相对收益',
        'name_en': 'CSI1000 vs CSI300 Relative Return 20d',
        'market': 'CN',
        'role': 'main',
        'direction': 'up_good',  # 小盘跑赢大盘为好（风险偏好）
        
        'transform': 'relret20',
        'transform_params': {
            'base_symbol': '000852.SS',    # 中证1000
            'reference_symbol': '000300.SS'  # 沪深300
        },
        
        'z_method': 'madz',
        'z_window': 40,  # 更短的窗口（40天）
        'direction_sign': 1,
        
        'source': 'yfinance',
        'source_symbol': ['000852.SS', '000300.SS'],  # 两个标的
        'required_columns': None,
        
        'weekly_agg': 'last',
        
        'dependencies': ['CSI1000_PRICE', 'CSI300_PRICE'],  # 依赖两个价格序列
        
        'fetch_frequency': 'daily',
        'typical_update_time': '16:00',
        
        'description': '中证1000指数相对沪深300指数的20日相对收益，衡量小盘股强弱',
        'calculation': 'relret20 = (CSI1000_t/CSI1000_{t-20} - 1) - (CSI300_t/CSI300_{t-20} - 1)'
    },
    
    'PMI_NEWORDER_YOY_STD': {
        'name': 'PMI新订单同比标准化',
        'name_en': 'PMI New Orders YoY Standardized',
        'market': 'CN',
        'role': 'main',
        'direction': 'up_good',
        
        'transform': 'yoy_std',  # 月度数据，先计算同比，再标准化
        'transform_params': {
            'frequency': 'monthly',
            'ffill': True  # 月度数据需要前向填充到日度
        },
        
        'z_method': 'z',
        'z_window': 90,  # 用更长窗口（90天≈3个月数据点）
        'direction_sign': 1,
        
        'source': 'csv',  # 官方PMI数据需要手动获取
        'source_symbol': None,
        'required_columns': ['date', 'pmi_new_order'],
        
        'weekly_agg': 'last',
        
        'dependencies': [],
        
        'fetch_frequency': 'monthly',
        'typical_update_time': '每月月初',
        
        'description': '官方制造业PMI新订单指数的同比变化标准化值，反映经济动能',
        'calculation': 'yoy = (PMI_t - PMI_{t-12}) / PMI_{t-12}; std = (yoy - mean) / std'
    },
    
    'CN_EPS_YIELD_MINUS_CGB10': {
        'name': '股债收益差',
        'name_en': 'CN Equity EPS Yield Minus 10Y CGB Yield',
        'market': 'CN',
        'role': 'main',
        'direction': 'up_good',  # 股票相对债券更有吸引力为好
        
        'transform': 'subtract',  # 两个序列相减
        'transform_params': {
            'series_a': 'CN_ALL_A_EPS_YIELD',
            'series_b': 'CGB_10Y_YIELD'
        },
        
        'z_method': 'z',
        'z_window': 60,
        'z_winsorize': {'lower': -3, 'upper': 3},  # winsorize到±3σ
        'direction_sign': 1,
        
        'source': 'csv',  # 两个数据都需要CSV导入
        'source_symbol': None,
        'required_columns': ['date', 'eps_yield', 'cgb10_yield'],
        
        'weekly_agg': 'last',
        
        'dependencies': ['CN_ALL_A_EPS_YIELD', 'CGB_10Y_YIELD'],
        
        'fetch_frequency': 'daily',
        'typical_update_time': '17:00',
        
        'description': '全A股票盈利收益率减去10年期国债收益率，衡量股票相对债券的吸引力',
        'calculation': 'spread = EPS_yield - CGB10_yield; Z需要winsorize到±3σ'
    }
}


# ===== US市场主指标（6个，参与评分） =====

US_MAIN_INDICATORS = {
    'RRP_D20': {
        'name': 'RRP 20日变动',
        'name_en': 'Reverse Repo Program 20-day Delta',
        'market': 'US',
        'role': 'main',
        'direction': 'down_good',  # RRP下降释放流动性，为好
        
        'transform': 'delta20',
        'transform_params': {},
        
        'z_method': 'z',
        'z_window': 60,
        'direction_sign': -1,
        
        'source': 'fred',
        'source_symbol': 'RRPONTSYD',
        'required_columns': None,
        
        'weekly_agg': 'last',  # 或'resample'到Friday
        
        'dependencies': [],
        
        'fetch_frequency': 'daily',
        'typical_update_time': '次日凌晨',
        
        'description': '隔夜逆回购操作规模的20日变动，反映流动性变化',
        'calculation': 'delta20 = RRP_t - RRP_{t-20}'
    },
    
    'TGA_D20': {
        'name': 'TGA 20日变动',
        'name_en': 'Treasury General Account 20-day Delta',
        'market': 'US',
        'role': 'main',
        'direction': 'down_good',  # TGA下降释放流动性
        
        'transform': 'delta20',
        'transform_params': {},
        
        'z_method': 'z',
        'z_window': 60,
        'direction_sign': -1,
        
        'source': 'fred',
        'source_symbol': 'WTREGEN',
        'required_columns': None,
        
        'weekly_agg': 'last',
        
        'dependencies': [],
        
        'fetch_frequency': 'daily',
        'typical_update_time': '次日凌晨',
        
        'description': '美国财政部在美联储的一般账户余额20日变动，反映财政流动性',
        'calculation': 'delta20 = TGA_t - TGA_{t-20}'
    },
    
    'HY_OAS': {
        'name': '高收益债利差',
        'name_en': 'High Yield OAS',
        'market': 'US',
        'role': 'main',
        'direction': 'down_good',  # 利差收窄为好（风险偏好提升）
        
        'transform': 'raw',
        'transform_params': {},
        
        'z_method': 'madz',
        'z_window': 60,
        'direction_sign': -1,
        
        'source': 'fred',
        'source_symbol': 'BAMLH0A0HYM2',
        'required_columns': None,
        
        'weekly_agg': 'last',
        
        'dependencies': [],
        
        'fetch_frequency': 'daily',
        'typical_update_time': '次日凌晨',
        
        'description': 'ICE BofA美国高收益债券期权调整利差，反映信用风险溢价',
        'calculation': 'raw value from FRED'
    },
    
    'VIX_LOG': {
        'name': 'VIX对数值',
        'name_en': 'VIX Logarithm',
        'market': 'US',
        'role': 'main',
        'direction': 'down_good',  # 波动率低为好
        
        'transform': 'log_winsor',
        'transform_params': {
            'p_low': 0.02,
            'p_high': 0.98
        },
        
        'z_method': 'madz',
        'z_window': 40,
        'direction_sign': -1,
        
        'source': 'yfinance',
        'source_symbol': '^VIX',
        'required_columns': None,
        
        'weekly_agg': 'last',  # Friday close
        
        'dependencies': [],
        
        'fetch_frequency': 'daily',
        'typical_update_time': '美股收盘后',
        
        'description': 'VIX波动率指数的对数变换并winsorize到2%-98%分位，降低极端值影响',
        'calculation': 'log(VIX) then winsorize to [p2, p98]'
    },
    
    'DFII10': {
        'name': '10年期TIPS实际利率',
        'name_en': '10-Year TIPS Real Yield',
        'market': 'US',
        'role': 'main',
        'direction': 'down_good',  # 实际利率低为好（对股市）
        
        'transform': 'raw',
        'transform_params': {},
        
        'z_method': 'z',
        'z_window': 60,
        'direction_sign': -1,
        
        'source': 'fred',
        'source_symbol': 'DFII10',
        'required_columns': None,
        
        'weekly_agg': 'last',
        
        'dependencies': [],
        
        'fetch_frequency': 'daily',
        'typical_update_time': '次日凌晨',
        
        'description': '10年期TIPS国债的实际收益率，反映实际利率水平',
        'calculation': 'raw value from FRED'
    },
    
    'IWM_SPY_REL20': {
        'name': 'IWM/SPY相对收益',
        'name_en': 'IWM vs SPY Relative Return 20d',
        'market': 'US',
        'role': 'main',
        'direction': 'up_good',  # 小盘跑赢大盘为好
        
        'transform': 'relret20',
        'transform_params': {
            'base_symbol': 'IWM',
            'reference_symbol': 'SPY'
        },
        
        'z_method': 'madz',
        'z_window': 40,
        'direction_sign': 1,
        
        'source': 'yfinance',
        'source_symbol': ['IWM', 'SPY'],
        'required_columns': None,
        
        'weekly_agg': 'last',
        
        'dependencies': ['IWM_PRICE', 'SPY_PRICE'],
        
        'fetch_frequency': 'daily',
        'typical_update_time': '美股收盘后',
        
        'description': 'Russell 2000 ETF (IWM)相对S&P 500 ETF (SPY)的20日相对收益，衡量小盘股强弱',
        'calculation': 'relret20 = (IWM_t/IWM_{t-20} - 1) - (SPY_t/SPY_{t-20} - 1)'
    }
}


# ===== CN市场观察者指标（不参与评分，用于确认层） =====

CN_OBSERVER_INDICATORS = {
    # 硬否决
    'ETF_NETFLOW_5D': {
        'name': '宽基ETF 5日净申赎',
        'name_en': 'Broad-based ETF 5-day Net Flow',
        'market': 'CN',
        'role': 'hard',  # 硬否决
        'direction': 'up_good',
        
        'transform': 'sum5',  # 5日滚动求和
        'transform_params': {},
        
        'z_method': 'madz',
        'z_window': 60,
        'direction_sign': 1,
        
        'source': 'csv',
        'source_symbol': None,
        'required_columns': ['date', 'etf_netflow_billion'],
        
        'weekly_agg': 'sum',  # 周视图求和
        
        'dependencies': [],
        
        'fetch_frequency': 'daily',
        'typical_update_time': '19:00',
        
        'description': '宽基ETF（如沪深300ETF、中证500ETF）5日净申赎额（亿元），反映增量资金',
        'calculation': 'sum(netflow_{t-4} to netflow_t)',
        
        # 硬否决规则
        'hard_veto_rule': {
            'type': 'score_threshold',
            'threshold': 40,
            'condition': 'score <= 40 → Red',
            'persistence_days': 3,
            'persistence_weeks': 2
        }
    },
    
    # 软确认 - 配对指标（与US共用）
    'CNH_LAMP': {
        'name': 'USD/CNH灯色',
        'name_en': 'USD/CNH Lamp',
        'market': 'CN',
        'role': 'pair',  # 配对指标之一
        'pair_group': 'CNH_CNY',
        
        # 从CNH_PCT20派生
        'derived_from': 'CNH_PCT20',
        'lamp_source': 'series_data.lamp_color'
    },
    
    'CNY_LAMP': {
        'name': 'USD/CNY灯色',
        'name_en': 'USD/CNY Lamp',
        'market': 'CN',
        'role': 'pair',
        'pair_group': 'CNH_CNY',
        
        'direction': 'down_good',
        
        'transform': 'pct20',
        'transform_params': {},
        
        'z_method': 'madz',
        'z_window': 60,
        'direction_sign': -1,
        
        'source': 'yfinance',
        'source_symbol': 'CNY=X',
        'required_columns': None,
        
        'weekly_agg': 'last',
        
        'dependencies': [],
        
        'fetch_frequency': 'daily',
        'typical_update_time': '次日凌晨'
    },
    
    'TWEX_LAMP': {
        'name': 'Trade-Weighted USD灯色',
        'name_en': 'TWEX Lamp',
        'market': 'CN',  # CN和US都用
        'role': 'pair',
        'pair_group': 'TWEX_DXY',
        
        'direction': 'down_good',
        
        'transform': 'pct20',
        'transform_params': {},
        
        'z_method': 'madz',
        'z_window': 60,
        'direction_sign': -1,
        
        'source': 'fred',
        'source_symbol': 'DTWEXBGS',
        'required_columns': None,
        
        'weekly_agg': 'last',
        
        'dependencies': [],
        
        'fetch_frequency': 'daily',
        'typical_update_time': '次日凌晨'
    },
    
    'DXY_LAMP': {
        'name': 'DXY美元指数灯色',
        'name_en': 'DXY Lamp',
        'market': 'CN',
        'role': 'pair',
        'pair_group': 'TWEX_DXY',
        
        'direction': 'down_good',
        
        'transform': 'pct20',
        'transform_params': {},
        
        'z_method': 'madz',
        'z_window': 60,
        'direction_sign': -1,
        
        'source': 'yfinance',
        'source_symbol': 'DX-Y.NYB',  # 或使用其他DXY来源
        'required_columns': None,
        
        'weekly_agg': 'last',
        
        'dependencies': [],
        
        'fetch_frequency': 'daily',
        'typical_update_time': '次日凌晨'
    }
}


# ===== US市场观察者指标 =====

US_OBSERVER_INDICATORS = {
    # 硬否决1
    'HY_OAS_JUMP': {
        'name': 'HY OAS极端跳跃',
        'name_en': 'HY OAS Extreme Jump',
        'market': 'US',
        'role': 'hard',
        
        # 从HY_OAS派生
        'derived_from': 'HY_OAS',
        
        'hard_veto_rule': {
            'type': 'z_jump_or_score',
            'z_jump_threshold': 1.5,
            'z_jump_window': 10,  # 2周（10个交易日）
            'score_threshold': 40,
            'condition': 'ΔZ(2w) > +1.5 OR score <= 40 → Red',
            'persistence_days': 3,
            'persistence_weeks': 2
        }
    },
    
    # 硬否决2
    'VIX_EXTREME': {
        'name': 'VIX极值',
        'name_en': 'VIX Extreme Level',
        'market': 'US',
        'role': 'hard',
        
        'derived_from': 'VIX_LOG',
        
        'hard_veto_rule': {
            'type': 'z_threshold_or_score',
            'z_threshold': 2.0,
            'score_threshold': 40,
            'condition': 'Z > +2.0 OR score <= 40 → Red',
            'persistence_days': 3,
            'persistence_weeks': 2
        }
    },
    
    # 软确认1
    'IWM_SPY_SOFT': {
        'name': 'IWM/SPY软确认',
        'name_en': 'IWM/SPY Soft Confirm',
        'market': 'US',
        'role': 'soft',
        
        'derived_from': 'IWM_SPY_REL20',
        'lamp_source': 'series_data.lamp_color',
        
        'soft_confirm_weight': 0.30
    },
    
    # 软确认2
    'HYG_IEF_SOFT': {
        'name': 'HYG/IEF软确认',
        'name_en': 'HYG vs IEF Soft Confirm',
        'market': 'US',
        'role': 'soft',
        
        'direction': 'up_good',  # HYG跑赢IEF为好
        
        'transform': 'relret20',
        'transform_params': {
            'base_symbol': 'HYG',  # 高收益债ETF
            'reference_symbol': 'IEF'  # 7-10年国债ETF
        },
        
        'z_method': 'madz',
        'z_window': 40,
        'direction_sign': 1,
        
        'source': 'yfinance',
        'source_symbol': ['HYG', 'IEF'],
        'required_columns': None,
        
        'weekly_agg': 'last',
        
        'dependencies': ['HYG_PRICE', 'IEF_PRICE'],
        
        'fetch_frequency': 'daily',
        'typical_update_time': '美股收盘后',
        
        'soft_confirm_weight': 0.30
    },
    
    # 软确认3 - 配对（从CN共用）
    'PAIR_TWEX_DXY_SOFT': {
        'name': 'TWEX/DXY配对软确认',
        'name_en': 'TWEX/DXY Pair Soft Confirm',
        'market': 'US',
        'role': 'soft',
        
        'pair_group': 'TWEX_DXY',
        'pair_members': ['TWEX_LAMP', 'DXY_LAMP'],
        'pair_rule': 'A',  # Rule A: Consistency-first
        
        'soft_confirm_weight': 0.20
    },
    
    # 软确认4 - 配对（从CN共用）
    'PAIR_CNH_CNY_SOFT': {
        'name': 'CNH/CNY配对软确认',
        'name_en': 'CNH/CNY Pair Soft Confirm',
        'market': 'US',
        'role': 'soft',
        
        'pair_group': 'CNH_CNY',
        'pair_members': ['CNH_LAMP', 'CNY_LAMP'],
        'pair_rule': 'A',
        
        'soft_confirm_weight': 0.20
    }
}


# ===== 完整注册表整合 =====

INDICATOR_REGISTRY = {
    **CN_MAIN_INDICATORS,
    **US_MAIN_INDICATORS,
    **CN_OBSERVER_INDICATORS,
    **US_OBSERVER_INDICATORS
}


# ===== 辅助函数 =====

def get_indicator_config(code: str) -> dict:
    """
    获取指定指标的配置
    
    Args:
        code: 指标代码，如 'VIX_LOG'
        
    Returns:
        指标配置字典
        
    Raises:
        KeyError: 如果指标代码不存在
    """
    if code not in INDICATOR_REGISTRY:
        raise KeyError(f"未知指标代码: {code}")
    return INDICATOR_REGISTRY[code]


def get_market_indicators(market: str, role: str = None) -> list:
    """
    获取指定市场的指标列表
    
    Args:
        market: 'CN' 或 'US'
        role: 可选，筛选角色 'main' | 'soft' | 'hard' | 'pair'
        
    Returns:
        指标代码列表
    """
    indicators = []
    for code, config in INDICATOR_REGISTRY.items():
        if config['market'] == market:
            if role is None or config['role'] == role:
                indicators.append(code)
    return indicators


def get_indicator_dependencies(code: str) -> list:
    """
    获取指标的依赖列表（递归）
    
    Args:
        code: 指标代码
        
    Returns:
        依赖的指标代码列表（包括间接依赖）
    """
    config = get_indicator_config(code)
    deps = config.get('dependencies', [])
    
    # 递归获取依赖的依赖
    all_deps = set(deps)
    for dep in deps:
        all_deps.update(get_indicator_dependencies(dep))
    
    return list(all_deps)


def validate_indicator_config(code: str) -> tuple[bool, list]:
    """
    验证指标配置的完整性
    
    Returns:
        (is_valid, error_messages)
    """
    errors = []
    
    try:
        config = get_indicator_config(code)
    except KeyError as e:
        return False, [str(e)]
    
    # 必需字段检查
    required_fields = ['name', 'market', 'role', 'source']
    for field in required_fields:
        if field not in config:
            errors.append(f"缺少必需字段: {field}")
    
    # 角色为main时必需字段
    if config.get('role') == 'main':
        main_required = ['direction', 'transform', 'z_method', 'z_window']
        for field in main_required:
            if field not in config:
                errors.append(f"主指标缺少必需字段: {field}")
    
    # 数据源验证
    if config.get('source') == 'yfinance':
        if not config.get('source_symbol'):
            errors.append("yfinance数据源需要source_symbol")
    
    # 依赖关系验证
    for dep in config.get('dependencies', []):
        if dep not in INDICATOR_REGISTRY:
            errors.append(f"依赖的指标不存在: {dep}")
    
    return len(errors) == 0, errors


def get_all_indicators_summary() -> dict:
    """
    获取所有指标的汇总统计
    
    Returns:
        {
            'total': 总数,
            'by_market': {'CN': x, 'US': y},
            'by_role': {'main': x, 'soft': y, 'hard': z, 'pair': w},
            'by_source': {'fred': x, 'yfinance': y, 'csv': z}
        }
    """
    total = len(INDICATOR_REGISTRY)
    
    by_market = {}
    by_role = {}
    by_source = {}
    
    for code, config in INDICATOR_REGISTRY.items():
        # 按市场统计
        market = config['market']
        by_market[market] = by_market.get(market, 0) + 1
        
        # 按角色统计
        role = config['role']
        by_role[role] = by_role.get(role, 0) + 1
        
        # 按数据源统计
        source = config.get('source', 'unknown')
        by_source[source] = by_source.get(source, 0) + 1
    
    return {
        'total': total,
        'by_market': by_market,
        'by_role': by_role,
        'by_source': by_source
    }


# ===== 使用示例 =====

if __name__ == '__main__':
    # 示例1: 获取VIX配置
    vix_config = get_indicator_config('VIX_LOG')
    print(f"VIX配置: {vix_config['name']}")
    print(f"  转换: {vix_config['transform']}")
    print(f"  Z方法: {vix_config['z_method']}({vix_config['z_window']})")
    print(f"  数据源: {vix_config['source']} - {vix_config['source_symbol']}")
    
    # 示例2: 获取US市场所有主指标
    us_main = get_market_indicators('US', role='main')
    print(f"\nUS市场主指标 ({len(us_main)}个):")
    for code in us_main:
        config = get_indicator_config(code)
        print(f"  {code}: {config['name']}")
    
    # 示例3: 获取汇总统计
    summary = get_all_indicators_summary()
    print(f"\n指标汇总:")
    print(f"  总数: {summary['total']}")
    print(f"  按市场: {summary['by_market']}")
    print(f"  按角色: {summary['by_role']}")
    print(f"  按数据源: {summary['by_source']}")
    
    # 示例4: 验证配置
    print(f"\n配置验证:")
    for code in ['VIX_LOG', 'CSI1000_OVER_300_REL20']:
        is_valid, errors = validate_indicator_config(code)
        if is_valid:
            print(f"  {code}: ✓ 配置有效")
        else:
            print(f"  {code}: ✗ 配置错误:")
            for error in errors:
                print(f"    - {error}")

