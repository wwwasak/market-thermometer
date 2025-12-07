"""
数据流水线模块

实现完整的数据处理流程：
获取 → 转换 → 评分 → 确认层 → 存储
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import hashlib
import json

from core.config import Config
from core.datasource import DataSourceManager, align_to_business_days, validate_series
from core.transforms import apply_transform, align_series, resample_to_weekly, forward_fill_to_daily
from core.scoring import (
    standardize_with_direction, score_from_z, lamp_from_score, regime_from_score,
    apply_persistence, batch_standardize, batch_score
)
from core.combine import build_confirm_layer
from storage.repository import Repository
from storage.models import SeriesMeta


class PipelineError(Exception):
    """流水线错误"""
    pass


class MarketPipeline:
    """
    市场数据处理流水线
    
    完整流程：
    1. 从数据源获取原始数据
    2. 应用数据转换
    3. 计算Z-score和评分
    4. 分类为灯号和风格
    5. 应用确认层逻辑
    6. 存储到数据库
    """
    
    def __init__(
        self,
        market: str = 'US',
        database_url: str = 'sqlite:///data/market_thermo.db',
        config: Optional[Config] = None
    ):
        """
        初始化流水线
        
        @param {str} market - 市场代码（'US' 或 'CN'）
        @param {str} database_url - 数据库连接URL
        @param {Optional[Config]} config - 配置对象
        """
        self.market = market.upper()
        self.config = config or Config()
        
        # 初始化组件
        self.data_source = DataSourceManager()
        self.repository = Repository(database_url)
        
        # 获取市场配置
        main_indicators = self.config.get(f'indicators.{self.market}.main', [])
        observer_indicators = self.config.get(f'indicators.{self.market}.observers', [])
        
        # 规范化指标配置并建立索引
        self.indicators: List[Dict[str, Any]] = []
        self.indicator_lookup: Dict[str, Dict[str, Any]] = {}
        
        for cfg in main_indicators:
            normalized = self._normalize_indicator_config(cfg.copy(), default_role='main')
            self.indicators.append(normalized)
            self.indicator_lookup[normalized['code']] = normalized
        
        for cfg in observer_indicators:
            normalized = self._normalize_indicator_config(
                cfg.copy(),
                default_role=cfg.get('role', 'observer')
            )
            self.indicators.append(normalized)
            self.indicator_lookup[normalized['code']] = normalized
        
        # 扩展派生/配对组件配置
        self._augment_indicator_components()
        
        # 获取市场特定参数
        # 配置确认层参数
        soft_confirm_codes = []
        soft_confirm_weights = {}
        hard_veto_codes = []
        
        if self.market == 'US':
            # US市场的确认层配置
            soft_confirm_codes = ['IWM_SPY_SOFT', 'HYG_IEF_SOFT', 'PAIR_TWEX_DXY', 'PAIR_CNH_CNY']
            soft_confirm_weights = self.config.get('soft_confirm_weights.US', {})
            hard_veto_codes = ['HY_OAS_JUMP', 'VIX_EXTREME']
        elif self.market == 'CN':
            # CN市场的确认层配置
            soft_confirm_codes = ['PAIR_CNH_CNY', 'PAIR_TWEX_DXY']
            soft_confirm_weights = self.config.get('soft_confirm_weights.CN', {})
            hard_veto_codes = ['ETF_NETFLOW_5D']
        
        self.market_config = {
            'z_type': self.config.get('z_type', 'Z').upper(),  # 确保大写
            'z_window': self.config.get('z_window', 60),
            'green_threshold': self.config.get('lamp.green_threshold', 60),
            'red_threshold': self.config.get('lamp.red_threshold', 40),
            'confirm_layer': {
                'hard_veto_codes': hard_veto_codes,
                'soft_confirm_codes': soft_confirm_codes,
                'soft_confirm_weights': soft_confirm_weights,
                'soft_confirm_green': self.config.get('soft_confirm_thresholds.green', 1.6),
                'soft_confirm_red': self.config.get('soft_confirm_thresholds.red', 0.8),
                'pair_rule': self.config.get('pair_rule', 'A')
            }
        }
        
        # 流水线状态
        self.last_update = None
        self.data_cache = {}
    
    @staticmethod
    def _ensure_naive_series(series: pd.Series) -> pd.Series:
        if not isinstance(series, pd.Series):
            return series
        idx = series.index
        if isinstance(idx, pd.DatetimeIndex):
            if idx.tz is not None:
                series = series.copy()
                series.index = idx.tz_convert('UTC').tz_localize(None)
            series = series.sort_index()
        return series

    @staticmethod
    def _align_raw_series(raw_series: pd.Series, target_index: pd.Index) -> pd.Series:
        """
        将低频原始序列与目标索引对齐，必要时进行前向填充
        以便在GUI中展示原始值（解决月度/周度指标原始值缺失的问题）
        """
        if not isinstance(raw_series, pd.Series):
            return raw_series

        aligned = raw_series.reindex(target_index)
        if len(aligned) == 0:
            return aligned

        nan_ratio = aligned.isna().sum() / len(aligned) if len(aligned) > 0 else 1.0
        if nan_ratio > 0.3:  # 低频数据通常缺失较多，前向填充以保证可视化
            aligned = aligned.ffill()
        return aligned
    
    def _normalize_indicator_config(
        self,
        config: Dict[str, Any],
        default_role: str = 'main'
    ) -> Dict[str, Any]:
        """
        标准化指标配置，补全缺省字段
        
        @param {Dict[str, Any]} config - 原始配置
        @param {str} default_role - 默认角色
        @returns {Dict[str, Any]} 规范化后的配置
        """
        cfg = config
        code = cfg.get('code')
        if not code:
            raise ValueError("Indicator configuration must include 'code'")
        
        cfg.setdefault('market', self.market)
        cfg.setdefault('role', default_role)
        cfg.setdefault('name', code)
        cfg.setdefault('direction', 'up_good')
        cfg.setdefault('transform', 'raw')
        cfg.setdefault('z_type', 'Z')
        cfg.setdefault('z_window', 60)
        
        if 'include_in_scoring' not in cfg:
            if cfg.get('pair'):
                cfg['include_in_scoring'] = False
            elif cfg.get('derived', False):
                cfg['include_in_scoring'] = True
            elif cfg.get('source'):
                cfg['include_in_scoring'] = True
            else:
                cfg['include_in_scoring'] = False
        
        return cfg
    
    def _augment_indicator_components(self) -> None:
        """
        将派生指标及配对指标所需的组件补充到指标列表中
        """
        extra_indicators: List[Dict[str, Any]] = []
        seen_codes = set(self.indicator_lookup.keys())
        
        for indicator in list(self.indicators):
            components = indicator.get('components', [])
            if not components:
                continue
            
            if indicator.get('derived'):
                for component in components:
                    comp_code = component.get('code')
                    if not comp_code or comp_code in seen_codes:
                        continue
                    
                    comp_cfg = component.copy()
                    comp_cfg.setdefault('name', comp_code)
                    comp_cfg.setdefault('direction', 'up_good')
                    comp_cfg.setdefault('transform', 'raw')
                    comp_cfg.setdefault('z_type', indicator.get('z_type', 'Z'))
                    comp_cfg.setdefault('z_window', indicator.get('z_window', 60))
                    comp_cfg['role'] = comp_cfg.get('role', 'component')
                    comp_cfg['parent_code'] = indicator['code']
                    comp_cfg['include_in_scoring'] = comp_cfg.get('include_in_scoring', False)
                    
                    normalized = self._normalize_indicator_config(comp_cfg, default_role='component')
                    extra_indicators.append(normalized)
                    seen_codes.add(comp_code)
                    self.indicator_lookup[comp_code] = normalized
            
            if indicator.get('pair'):
                for component in components:
                    comp_code = component.get('code')
                    if not comp_code or comp_code in seen_codes:
                        continue
                    
                    comp_cfg = component.copy()
                    comp_cfg.setdefault('name', comp_code)
                    comp_cfg.setdefault('direction', 'up_good')
                    comp_cfg.setdefault('transform', component.get('transform', 'raw'))
                    comp_cfg.setdefault('z_type', component.get('z_type', 'Z'))
                    comp_cfg.setdefault('z_window', component.get('z_window', 60))
                    comp_cfg['role'] = comp_cfg.get('role', 'pair_component')
                    comp_cfg['parent_code'] = indicator['code']
                    comp_cfg['include_in_scoring'] = comp_cfg.get('include_in_scoring', True)
                    
                    normalized = self._normalize_indicator_config(comp_cfg, default_role='component')
                    extra_indicators.append(normalized)
                    seen_codes.add(comp_code)
                    self.indicator_lookup[comp_code] = normalized
        
        if extra_indicators:
            self.indicators.extend(extra_indicators)

    def fetch_all_data(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        incremental: bool = False
    ) -> Dict[str, pd.Series]:
        """
        获取所有指标的原始数据
        
        @param {Optional[datetime]} start_date - 开始日期
        @param {Optional[datetime]} end_date - 结束日期
        @param {bool} incremental - 是否增量更新
        @returns {Dict[str, pd.Series]} 数据字典 {code: series}
        """
        print(f"\n[INFO] 开始获取 {self.market} 市场数据...")
        
        # 确定日期范围
        if incremental and not start_date:
            # 增量模式：从最后一次更新开始
            last_date = self._get_last_data_date()
            if last_date:
                start_date = last_date - timedelta(days=5)  # 重叠5天确保数据完整
                print(f"[INFO] 增量更新模式，从 {start_date.strftime('%Y-%m-%d')} 开始")
        
        if not start_date:
            # 默认获取2年数据
            end_date = end_date or datetime.now()
            start_date = end_date - timedelta(days=730)
            print(f"[INFO] 全量获取模式，时间范围: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
        
        # 获取数据
        results = {}
        success_count = 0
        total_fetchable = sum(
            1
            for indicator in self.indicator_lookup.values()
            if indicator.get('source') and indicator.get('source', '').lower() != 'csv'
        )
        
        for indicator in self.indicator_lookup.values():
            code = indicator['code']
            source = indicator.get('source', '')
            
            try:
                # 跳过没有source的派生指标（观察者指标）
                if not source:
                    print(f"[SKIP] {code} - 无可用数据源")
                    continue
                
                # 跳过CSV类型（需要手动导入）
                if source.lower() == 'csv':
                    print(f"[SKIP] {code} - 需要CSV手动导入")
                    continue
                
                # 获取数据
                print(f"[FETCH] {code} ({indicator.get('name', '')})...")
                data = self.data_source.fetch_by_config(indicator, start_date, end_date)
                
                if len(data) > 0:
                    # 验证数据质量（降低最小长度要求以支持短期数据）
                    is_valid, message = validate_series(data, min_length=20)
                    if is_valid:
                        results[code] = data
                        success_count += 1
                        print(f"  [OK] {len(data)} 条记录")
                    else:
                        print(f"  [WARN] 数据质量不合格: {message}")
                else:
                    print(f"  [FAIL] 未获取到数据")
            
            except Exception as e:
                print(f"  [ERROR] {code} 获取失败: {e}")
        
        if total_fetchable == 0:
            total_fetchable = 1  # 避免除零或显示0
        print(f"\n[OK] 成功获取 {success_count}/{total_fetchable} 个指标")
        
        # 记录获取日志
        self.repository.add_fetch_log(
            action='fetch_all',
            status='success',
            message=f"Fetched {success_count}/{total_fetchable} indicators for {self.market}"
        )
        
        return results
    
    def transform_data(
        self,
        raw_data: Dict[str, pd.Series]
    ) -> Dict[str, pd.Series]:
        """
        应用数据转换
        
        @param {Dict[str, pd.Series]} raw_data - 原始数据
        @returns {Dict[str, pd.Series]} 转换后的数据
        """
        print(f"\n[INFO] 应用数据转换...")
        
        transformed: Dict[str, pd.Series] = {}
        
        for code, data_obj in raw_data.items():
            indicator = self.indicator_lookup.get(code, {})
            transform = indicator.get('transform', 'raw')
            extra_value_tr: Optional[pd.Series] = None

            if isinstance(data_obj, pd.DataFrame):
                if 'value_raw' not in data_obj.columns:
                    print(f"[WARN] {code} 数据缺少 value_raw 列，跳过转换")
                    continue
                series = self._ensure_naive_series(data_obj['value_raw'])
                if 'value_tr' in data_obj.columns:
                    extra_value_tr = self._ensure_naive_series(data_obj['value_tr'])
            else:
                series = self._ensure_naive_series(data_obj)
            
            try:
                if extra_value_tr is not None:
                    transformed_series = extra_value_tr
                elif transform == 'raw':
                    transformed_series = series
                else:
                    transformed_series = apply_transform(series, transform)
                    print(f"[TRANSFORM] {code}: {transform}")

                transformed[code] = self._ensure_naive_series(transformed_series)
            
            except Exception as e:
                print(f"[ERROR] {code} 转换失败: {e}")
        
        print(f"[OK] 完成 {len(transformed)} 个指标的转换")
        
        return transformed
    
    def calculate_derived_indicators(
        self,
        raw_data: Dict[str, pd.Series],
        transformed_data: Dict[str, pd.Series],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Tuple[Dict[str, pd.Series], Dict[str, pd.Series]]:
        """
        计算派生指标
        
        @param {Dict[str, pd.Series]} raw_data - 原始数据（将被更新）
        @param {Dict[str, pd.Series]} transformed_data - 转换后数据（将被更新）
        @param {Optional[datetime]} start_date - 开始日期
        @param {Optional[datetime]} end_date - 结束日期
        @returns {Tuple[Dict[str, pd.Series], Dict[str, pd.Series]]} (更新后的原始数据, 更新后的转换数据)
        """
        print(f"\n[INFO] 计算派生指标...")
        
        result = transformed_data.copy()
        derived_count = 0
        
        for indicator in self.indicators:
            code = indicator['code']
            
            # 跳过非派生指标
            if not indicator.get('derived', False):
                continue
            
            components = indicator.get('components', [])
            calculation = indicator.get('calculation', '')
            
            if not components or not calculation:
                print(f"[SKIP] {code} - 缺少组件或计算公式")
                continue
            
            try:
                print(f"[DERIVE] {code} ({indicator.get('name', '')})...")
                
                # 获取组件数据
                component_data = {}
                for comp in components:
                    comp_code = comp['code']
                    comp_source = comp.get('source')
                    comp_symbol = comp.get('symbol')
                    
                    # 获取组件数据（若转换结果缺失，尝试拉取）
                    if comp_code not in raw_data:
                        print(f"  [FETCH] 组件 {comp_code}...")
                        comp_config = {
                            'code': comp_code,
                            'source': comp_source,
                            'symbol': comp_symbol
                        }
                        comp_series = self.data_source.fetch_by_config(comp_config, start_date, end_date)
                        
                        if len(comp_series) > 0:
                            comp_series = self._ensure_naive_series(comp_series)
                            component_data[comp_code] = comp_series
                            raw_data[comp_code] = comp_series  # 保存组件原始数据
                            
                            # 注册动态组件配置，便于后续存储
                            if comp_code not in self.indicator_lookup:
                                comp_cfg = {
                                    'code': comp_code,
                                    'name': comp.get('name', comp_code),
                                    'role': comp.get('role', 'component'),
                                    'direction': comp.get('direction', 'up_good'),
                                    'transform': comp.get('transform', 'raw'),
                                    'source': comp_source,
                                    'symbol': comp_symbol,
                                    'ticker': comp.get('ticker'),
                                    'z_type': comp.get('z_type', indicator.get('z_type', 'Z')),
                                    'z_window': comp.get('z_window', indicator.get('z_window', 60)),
                                    'include_in_scoring': comp.get('include_in_scoring', False),
                                    'parent_code': indicator['code']
                                }
                                normalized = self._normalize_indicator_config(comp_cfg, default_role='component')
                                self.indicators.append(normalized)
                                self.indicator_lookup[comp_code] = normalized
                            
                            comp_transform = self.indicator_lookup[comp_code].get('transform', 'raw')
                            if comp_transform == 'raw':
                                result[comp_code] = comp_series
                            else:
                                result[comp_code] = self._ensure_naive_series(
                                    apply_transform(comp_series, comp_transform)
                                )
                            print(f"    [OK] {len(comp_series)} 条记录")
                        else:
                            print(f"    [FAIL] 未获取到数据")
                            raise Exception(f"组件 {comp_code} 数据获取失败")
                    else:
                        base_series = raw_data[comp_code]
                        component_data[comp_code] = base_series
                        if comp_code not in result:
                            comp_transform = self.indicator_lookup.get(comp_code, {}).get('transform', 'raw')
                            if comp_transform == 'raw':
                                result[comp_code] = base_series
                            else:
                                result[comp_code] = self._ensure_naive_series(
                                    apply_transform(base_series, comp_transform)
                                )
                
                # 计算派生指标
                # 解析计算公式并执行（简单的减法）
                if '-' in calculation:
                    parts = calculation.split('-')
                    var1 = parts[0].strip()
                    var2 = parts[1].strip()
                    
                    if var1 in component_data and var2 in component_data:
                        # 对齐时间序列
                        series1 = component_data[var1]
                        series2 = component_data[var2]
                        
                        # 对齐索引
                        series1, series2 = series1.align(series2, join='inner')
                        derived_series = series1 - series2
                        
                        # 应用转换（如winsor）
                        transform = indicator.get('transform', 'raw')
                        transformed_series = derived_series
                        if transform != 'raw':
                            transformed_series = apply_transform(derived_series, transform)
                        
                        derived_series = self._ensure_naive_series(derived_series)
                        transformed_series = self._ensure_naive_series(transformed_series)
                        
                        # 保存原始/转换数据
                        raw_data[code] = derived_series
                        result[code] = transformed_series
                        derived_count += 1
                        print(f"  [OK] 计算完成: {len(derived_series)} 条记录")
                    else:
                        print(f"  [FAIL] 缺少必要的组件数据")
                else:
                    print(f"  [WARN] 不支持的计算公式: {calculation}")
            
            except Exception as e:
                print(f"  [ERROR] {code} 计算失败: {e}")
        
        print(f"[OK] 完成 {derived_count} 个派生指标的计算")
        
        return raw_data, result
    
    def calculate_scores(
        self,
        transformed_data: Dict[str, pd.Series],
        view_type: str = 'daily'
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        计算评分和灯号
        
        @param {Dict[str, pd.Series]} transformed_data - 转换后的数据
        @param {str} view_type - 视图类型（'daily' 或 'weekly'）
        @returns {Tuple[pd.DataFrame, pd.Series]} (评分结果DataFrame, 综合评分Series)
        """
        print(f"\n[INFO] 计算 {view_type} 评分...")
        
        # 选择参与评分的指标
        scoring_codes = [
            code for code, series in transformed_data.items()
            if isinstance(series, pd.Series)
            and len(series) > 0
            and self.indicator_lookup.get(code, {}).get('include_in_scoring', True)
        ]

        if not scoring_codes:
            raise PipelineError("No valid data for scoring")

        # **关键修复：先对每个序列独立计算Z分数和评分，然后再对齐**
        # 这样可以避免对齐时前面大量NaN导致MADZ无法计算的问题
        
        z_dict = {}
        score_dict = {}
        
        # 对每个指标独立计算Z分数和评分
        for code in scoring_codes:
            series = transformed_data[code]
            indicator = self.indicator_lookup.get(code, {})
            
            direction = indicator.get('direction', 'up_good')
            z_type = indicator.get('z_type', self.market_config.get('z_type', 'Z'))
            z_window = indicator.get('z_window', self.market_config.get('z_window', 60))
            
            # 计算Z分数
            z = standardize_with_direction(
                series,
                direction=direction,
                z_type=z_type,
                window=z_window
            )
            
            # 计算评分
            score = score_from_z(z, center=50, scale=10)
            
            z_dict[code] = z
            score_dict[code] = score
        
        # 现在对齐所有Z分数和评分到统一的日期索引
        series_list = [transformed_data[code] for code in scoring_codes]
        all_dates = series_list[0].index
        for s in series_list[1:]:
            all_dates = all_dates.union(s.index)

        if len(all_dates) == 0:
            raise PipelineError("No dates available for scoring")

        all_dates = pd.to_datetime(all_dates, utc=True)
        all_dates = all_dates.tz_localize(None)
        all_dates = all_dates.sort_values()

        # 对齐原始转换数据
        df = pd.DataFrame(
            {code: transformed_data[code].reindex(all_dates) for code in scoring_codes},
            index=all_dates
        )
        
        # 如果是周度，重采样
        if view_type == 'weekly':
            print("[INFO] 重采样到周度...")
            df = df.resample('W-FRI').last()
            # 也需要重采样Z分数和评分
            z_dict = {code: z.resample('W-FRI').last() for code, z in z_dict.items()}
            score_dict = {code: score.resample('W-FRI').last() for code, score in score_dict.items()}
        
        # 合并z-score和score到DataFrame
        result_data = {}
        for code in z_dict.keys():
            result_data[f"{code}_z"] = z_dict[code]
            result_data[f"{code}_score"] = score_dict[code]
        
        result_df = pd.DataFrame(result_data)
        
        # 计算综合评分（只用main角色的指标）
        main_indicators = [
            ind for ind in self.indicators 
            if ind.get('role') == 'main'
        ]
        
        composite_score = pd.Series(index=result_df.index, dtype=float)
        
        if main_indicators:
            # 获取当前市场和风格的权重
            active_style = self.config.get(f"active_style.{self.market}", "Balanced")
            weights_full = self.config.get(f"style_weights.{self.market}.{active_style}", [])
            
            # 只使用有评分数据的main指标（至少要有部分数据，不要求全部非空）
            main_codes_with_scores = []
            for ind in main_indicators:
                code = ind['code']
                if code in score_dict:
                    score_series = score_dict[code]
                    # 只要有任何非空值就算有数据
                    if isinstance(score_series, pd.Series) and len(score_series.dropna()) > 0:
                        main_codes_with_scores.append(code)
            
            print(f"[INFO] 主要指标: {len(main_indicators)}个配置, {len(main_codes_with_scores)}个有数据")
            
            if len(main_codes_with_scores) == 0:
                print(f"[WARN] 所有主要指标均无数据，无法计算综合评分")
                print(f"[WARN] 可能原因：时间窗口太短，导致指标计算失败")
            else:
                print(f"[INFO] 有数据的指标: {main_codes_with_scores}")
                
                # 构建评分矩阵（只用有数据的指标）
                score_matrix = pd.DataFrame(
                    {code: score_dict.get(code, pd.Series(dtype=float)) for code in main_codes_with_scores}
                )
                
                # 根据指标在main_indicators中的位置提取对应权重
                weights = []
                for code in main_codes_with_scores:
                    # 找到这个指标在main_indicators中的位置
                    idx = next((i for i, ind in enumerate(main_indicators) if ind['code'] == code), None)
                    if idx is not None and idx < len(weights_full):
                        weights.append(weights_full[idx])
                    else:
                        # 如果找不到对应权重，使用平均值
                        avg_weight = sum(weights_full) / len(weights_full) if weights_full else 1.0
                        weights.append(avg_weight)
                        print(f"[WARN] {code} 使用默认权重 {avg_weight:.1f}")
                
                if len(weights) != len(main_codes_with_scores):
                    print(f"[ERROR] 权重提取失败: 需要{len(main_codes_with_scores)}个，得到{len(weights)}个")
                elif len(weights) > 0:
                    from core.scoring import weighted_score
                    
                    # 注意：weighted_score会在每个时间点只使用那些非空的指标进行加权
                    composite_score = weighted_score(score_matrix, weights, normalize=True)
                    
                    # 检查综合评分是否有效
                    valid_count = composite_score.notna().sum()
                    if valid_count > 0:
                        print(f"[INFO] 计算综合评分: 使用 {active_style} 风格，{len(main_codes_with_scores)} 个主要指标")
                        print(f"[INFO] 综合评分: {valid_count}/{len(composite_score)} 个有效值")
                        print(f"[INFO] 综合评分范围: {composite_score.min():.2f} - {composite_score.max():.2f}")
                    else:
                        print(f"[WARN] 综合评分全部为NaN")
        
        print(f"[OK] 完成 {len(scoring_codes)} 个指标的评分")
        if len(result_df) > 0:
            print(f"[INFO] 数据时间范围: {result_df.index.min()} 至 {result_df.index.max()}")
            print(f"[INFO] 总共 {len(result_df)} 个时间点")
        
        return result_df, composite_score
    
    def apply_confirm_layer(
        self,
        scores: pd.DataFrame,
        view_type: str = 'daily'
    ) -> Dict[str, pd.Series]:
        """
        应用确认层逻辑
        
        @param {pd.DataFrame} scores - 评分结果
        @param {str} view_type - 视图类型
        @returns {Dict[str, pd.Series]} 确认层结果
        """
        print(f"\n[INFO] 应用 {view_type} 确认层...")
        
        # 将评分转换为灯号（按指标代码）
        indicator_lamps: Dict[str, pd.Series] = {}
        green_th = self.market_config.get('green_threshold', 60)
        red_th = self.market_config.get('red_threshold', 40)

        for code, indicator in self.indicator_lookup.items():
            score_col = f"{code}_score"
            if score_col in scores.columns:
                indicator_lamps[code] = lamp_from_score(scores[score_col], green_th, red_th)

        # 按角色区分灯号
        main_lamps: Dict[str, pd.Series] = {}
        observer_lamps: Dict[str, pd.Series] = {}
        pair_lamps: Dict[str, Tuple[pd.Series, pd.Series]] = {}

        for code, indicator in self.indicator_lookup.items():
            role = indicator.get('role', 'main')

            if indicator.get('pair'):
                components = indicator.get('components', [])
                if len(components) == 2:
                    comp_lamps = []
                    for comp in components:
                        comp_code = comp.get('code')
                        if comp_code in indicator_lamps:
                            comp_lamps.append(indicator_lamps[comp_code])
                    if len(comp_lamps) == 2:
                        pair_lamps[code] = (comp_lamps[0], comp_lamps[1])
                continue

            lamp_series = indicator_lamps.get(code)
            if lamp_series is None:
                continue

            if role in ['hard', 'soft', 'pair']:
                observer_lamps[code] = lamp_series
            else:
                main_lamps[code] = lamp_series

        confirm_config = self.market_config.get('confirm_layer', {}) or {}

        config_params = {
            'hard_veto_codes': confirm_config.get('hard_veto_codes', []),
            'hard_veto_persistence': confirm_config.get('hard_veto_persistence', 3 if view_type == 'daily' else 0),
            'soft_confirm_codes': confirm_config.get('soft_confirm_codes', []),
            'soft_confirm_weights': confirm_config.get('soft_confirm_weights', {}),
            'soft_confirm_green': confirm_config.get('soft_confirm_green', 1.6),
            'soft_confirm_red': confirm_config.get('soft_confirm_red', 0.8),
            'pair_rule': confirm_config.get('pair_rule', 'A')
        }

        try:
            result = build_confirm_layer(
                main_lamps=main_lamps,
                observer_lamps=observer_lamps,
                pair_lamps=pair_lamps,
                config=config_params
            )

            print(f"[OK] 确认层计算完成")

            return {
                'hard_veto': result.get('hard_veto'),
                'soft_confirm': result.get('soft_confirm'),
                'final': result.get('final'),
                'pair_lamps': result.get('pairs', {})
            }

        except Exception as e:
            print(f"[ERROR] 确认层失败: {e}")
            return {}
    
    def save_to_database(
        self,
        raw_data: Dict[str, pd.Series],
        transformed_data: Dict[str, pd.Series],
        scores: pd.DataFrame,
        confirm_results: Dict[str, pd.Series],
        composite_score: pd.Series,
        view_type: str = 'daily'
    ) -> int:
        """
        保存所有结果到数据库
        
        @param {Dict[str, pd.Series]} raw_data - 原始数据
        @param {Dict[str, pd.Series]} transformed_data - 转换后数据
        @param {pd.DataFrame} scores - 评分结果
        @param {Dict[str, pd.Series]} confirm_results - 确认层结果
        @param {pd.Series} composite_score - 综合评分
        @param {str} view_type - 视图类型
        @returns {int} 保存的记录数
        """
        print(f"\n[INFO] 保存数据到数据库...")
        
        total_saved = 0
        
        # 1. 保存序列元数据（如果不存在）
        for indicator in self.indicator_lookup.values():
            code = indicator['code']
            
            existing = self.repository.get_series_meta_by_code(code)
            if not existing:
                self.repository.add_series_meta(
                    code=code,
                    name=indicator.get('name', ''),
                    market=self.market,
                    role=indicator.get('role', ''),
                    direction=indicator.get('direction', 'up_good'),
                    transform=indicator.get('transform', 'raw'),
                    source=indicator.get('source', ''),
                    ticker=indicator.get('ticker', '')
                )
        
        # 准备code到series_id的映射
        code_to_series_id: Dict[str, int] = {}
        for indicator in self.indicator_lookup.values():
            code = indicator['code']
            meta = self.repository.get_series_meta_by_code(code)
            if meta and 'id' in meta:
                code_to_series_id[code] = meta['id']

        # 2. 保存时间序列数据
        all_series_codes = set(raw_data.keys()) | set(transformed_data.keys())
        
        print(f"[DEBUG] 准备保存 {len(all_series_codes)} 个序列的数据")
        print(f"[DEBUG] scores DataFrame: {scores.shape}, 列名前10个: {list(scores.columns)[:10]}")
        print(f"[DEBUG] scores索引类型: {type(scores.index)}, 前3个: {list(scores.index[:3])}")
        
        # 检查评分数据是否有效
        score_cols = [col for col in scores.columns if '_score' in col]
        if score_cols:
            sample_col = score_cols[0]
            non_nan = scores[sample_col].notna().sum()
            if non_nan > 0:
                print(f"[DEBUG] 样例评分列 {sample_col}: {non_nan}/{len(scores)} 个有效值, 范围: {scores[sample_col].min():.2f}-{scores[sample_col].max():.2f}")
            else:
                print(f"[WARN] 样例评分列 {sample_col}: 全部为NaN!")
        
        for code in all_series_codes:
            series_id = code_to_series_id.get(code)
            if series_id is None:
                continue

            raw_obj = raw_data.get(code)
            trans_series = transformed_data.get(code)
            extra_value_tr_series: Optional[pd.Series] = None

            if trans_series is None or len(trans_series) == 0:
                continue

            trans_series = self._ensure_naive_series(trans_series)

            target_index = trans_series.index

            if isinstance(raw_obj, pd.DataFrame):
                if 'value_raw' not in raw_obj.columns:
                    continue
                raw_series = self._ensure_naive_series(raw_obj['value_raw'])
                raw_series = self._align_raw_series(raw_series, target_index)
                if 'value_tr' in raw_obj.columns:
                    extra_value_tr_series = self._ensure_naive_series(raw_obj['value_tr']).reindex(target_index)
            elif isinstance(raw_obj, pd.Series):
                raw_series = self._ensure_naive_series(raw_obj)
                raw_series = self._align_raw_series(raw_series, target_index)
            else:
                raw_series = pd.Series(index=target_index, dtype=float)
            
            # 调试：检查score列
            score_col = f"{code}_score"
            z_col = f"{code}_z"
            has_score_col = score_col in scores.columns
            has_z_col = z_col in scores.columns
            
            if not has_score_col and not has_z_col:
                # 这是正常的，对于observer或component角色的指标
                pass
            
            saved_count = 0
            score_saved = 0
            
            # 关键修复：统一索引类型以确保匹配
            # 将trans_series的索引和scores的索引都转换为Timestamp
            trans_dates = pd.to_datetime(trans_series.index)
            scores_dates = pd.to_datetime(scores.index)
            
            for i, date in enumerate(trans_series.index):
                try:
                    trans_value = trans_series.iloc[i]
                    
                    # 将日期转换为Timestamp以便在scores中查找
                    lookup_date = pd.Timestamp(date)
                    if lookup_date.tz is not None:
                        lookup_date = lookup_date.tz_localize(None)
                    
                    # 准备record_date
                    if isinstance(date, pd.Timestamp):
                        record_date = date.date()
                    elif isinstance(date, datetime):
                        record_date = date.date()
                    else:
                        record_date = date
                    
                    # 获取对应的评分（使用Timestamp查找）
                    score_val = None
                    z_val = None
                    
                    if has_score_col:
                        # 尝试精确匹配
                        try:
                            if lookup_date in scores.index:
                                score_val = scores.loc[lookup_date, score_col]
                            else:
                                # 尝试使用isin查找最接近的日期
                                mask = scores.index == lookup_date
                                if mask.any():
                                    score_val = scores.loc[mask, score_col].iloc[0]
                        except Exception as e:
                            pass
                        
                        if pd.notna(score_val):
                            score_saved += 1
                    
                    if has_z_col:
                        try:
                            if lookup_date in scores.index:
                                z_val = scores.loc[lookup_date, z_col]
                            else:
                                mask = scores.index == lookup_date
                                if mask.any():
                                    z_val = scores.loc[mask, z_col].iloc[0]
                        except:
                            pass
                    
                    raw_value = raw_series.loc[date] if date in raw_series.index else None
                    if raw_value is not None and (not np.isscalar(raw_value) or pd.isna(raw_value)):
                        raw_value = None
                    
                    if extra_value_tr_series is not None and date in extra_value_tr_series.index:
                        value_tr = extra_value_tr_series.loc[date]
                    else:
                        value_tr = trans_value

                    if value_tr is not None and (not np.isscalar(value_tr) or pd.isna(value_tr)):
                        value_tr = None
                    
                    self.repository.upsert_series_data(
                        series_id=series_id,
                        date=record_date,
                        view=view_type,
                        value_raw=float(raw_value) if raw_value is not None else None,
                        value_tr=float(value_tr) if value_tr is not None else None,
                        z=float(z_val) if pd.notna(z_val) else None,
                        score=float(score_val) if pd.notna(score_val) else None
                    )
                    
                    total_saved += 1
                    saved_count += 1
                
                except Exception as e:
                    print(f"[WARN] 保存 {code} 数据失败 ({date}): {e}")
                    continue
            
            # 输出每个指标的保存统计
            if has_score_col or has_z_col:
                print(f"[DEBUG] {code}: 总共{saved_count}条，其中{score_saved}条有评分数据")
        
        # 3. 保存Regime数据
        if 'final' in confirm_results:
            final_lamp = confirm_results['final']
            hard_veto_lamp = confirm_results.get('hard_veto', pd.Series(dtype=str))
            soft_confirm_lamp = confirm_results.get('soft_confirm', pd.Series(dtype=str))
            
            # 计算当前参数的哈希
            params_hash = self._calculate_params_hash()
            
            # 计算regime
            attack_threshold = self.config.get('regime.attack_threshold', 70)
            defense_threshold = self.config.get('regime.defense_threshold', 40)
            persistence = self.config.get('regime.persistence_days' if view_type == 'daily' else 'regime.persistence_weeks', 0)
            
            regime_series = regime_from_score(
                composite_score,
                attack_threshold=attack_threshold,
                defense_threshold=defense_threshold,
                persistence=persistence
            )
            
            for date in final_lamp.index:
                try:
                    # 确保date是有效的日期对象
                    if isinstance(date, pd.Timestamp):
                        record_date = date.date()
                    elif isinstance(date, datetime):
                        record_date = date.date()
                    elif isinstance(date, str):
                        record_date = pd.to_datetime(date).date()
                    else:
                        # 尝试转换
                        try:
                            record_date = pd.to_datetime(date).date()
                        except:
                            print(f"[WARN] 无法转换日期: {date}, type: {type(date)}")
                            continue
                    
                    # 获取regime值
                    regime_val = regime_series.loc[date] if date in regime_series.index else 'Balanced'
                    comp_score_val = composite_score.loc[date] if date in composite_score.index else None
                    
                    # 获取灯色值（确保使用正确的访问方式）
                    final_lamp_val = final_lamp.loc[date] if date in final_lamp.index else 'Y'
                    soft_lamp_val = soft_confirm_lamp.loc[date] if date in soft_confirm_lamp.index else 'Y'
                    hard_lamp_val = hard_veto_lamp.loc[date] if date in hard_veto_lamp.index else 'Y'
                    
                    self.repository.upsert_regime(
                        date=record_date,
                        market=self.market,
                        view=view_type,
                        regime=regime_val,
                        composite_score=float(comp_score_val) if pd.notna(comp_score_val) else None,
                        lamp_final=final_lamp_val,
                        lamp_soft=soft_lamp_val,
                        lamp_hard=hard_lamp_val,
                        params_hash=params_hash
                    )
                
                except Exception as e:
                    print(f"[WARN] 保存regime数据失败 ({date}): {e}")
                    continue
            
            # 保存聚合灯色历史
            lamp_series_map = [
                ('final', 'FINAL_LAMP', final_lamp),
                ('soft_confirm', 'SOFT_CONFIRM', soft_confirm_lamp),
                ('hard_veto', 'HARD_VETO', hard_veto_lamp)
            ]
            
            for source_type, source_code, lamp_series in lamp_series_map:
                if lamp_series.empty:
                    continue
                for date, lamp_value in lamp_series.items():
                    try:
                        if pd.isna(lamp_value):
                            continue
                        
                        # 确保date是有效的日期对象
                        if isinstance(date, pd.Timestamp):
                            record_date = date.date()
                        elif isinstance(date, datetime):
                            record_date = date.date()
                        elif isinstance(date, str):
                            record_date = pd.to_datetime(date).date()
                        else:
                            # 尝试转换
                            try:
                                record_date = pd.to_datetime(date).date()
                            except:
                                print(f"[WARN] 无法转换灯色历史日期: {date}, type: {type(date)}")
                                continue

                        self.repository.upsert_lamp_history(
                            date=record_date,
                            market=self.market,
                            view=view_type,
                            source_type=source_type,
                            source_code=source_code,
                            lamp=lamp_value
                        )
                    except Exception as e:
                        print(f"[WARN] 记录灯色历史失败 ({source_code}, {date}): {e}")
        
        print(f"[OK] 保存了 {total_saved} 条记录到数据库")
        
        # 记录日志
        self.repository.add_fetch_log(
            action='save_pipeline',
            status='success',
            message=f"Saved {total_saved} records for {self.market} {view_type}"
        )
        
        return total_saved
    
    def run_daily_pipeline(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        incremental: bool = False
    ) -> Dict[str, Any]:
        """
        运行日度流水线
        
        @param {Optional[datetime]} start_date - 开始日期
        @param {Optional[datetime]} end_date - 结束日期  
        @param {bool} incremental - 是否增量更新
        @returns {Dict[str, Any]} 运行结果
        """
        print("\n" + "="*70)
        print(f"  运行 {self.market} 市场日度流水线")
        print("="*70)
        
        try:
            # 1. 获取数据
            raw_data = self.fetch_all_data(start_date, end_date, incremental)
            
            if not raw_data:
                raise PipelineError("No data fetched")
            
            # 2. 转换数据
            transformed_data = self.transform_data(raw_data)
            
            # 2.5 计算派生指标
            raw_data, transformed_data = self.calculate_derived_indicators(
                raw_data,
                transformed_data,
                start_date,
                end_date
            )
            
            # 3. 计算评分
            scores, composite_score = self.calculate_scores(transformed_data, view_type='daily')
            
            # 4. 应用确认层
            confirm_results = self.apply_confirm_layer(scores, view_type='daily')
            
            # 5. 保存到数据库
            saved_count = self.save_to_database(
                raw_data, transformed_data, scores, confirm_results, composite_score, view_type='daily'
            )
            
            self.last_update = datetime.now()
            
            result = {
                'success': True,
                'market': self.market,
                'view_type': 'daily',
                'indicators_fetched': len(raw_data),
                'records_saved': saved_count,
                'date_range': (scores.index.min(), scores.index.max()),
                'timestamp': self.last_update
            }
            
            print("\n" + "="*70)
            print(f"  日度流水线完成")
            print("="*70)
            print(f"[OK] 获取指标: {result['indicators_fetched']}")
            print(f"[OK] 保存记录: {result['records_saved']}")
            print(f"[OK] 时间范围: {result['date_range'][0]} 至 {result['date_range'][1]}")
            
            return result
        
        except Exception as e:
            print(f"\n[ERROR] 日度流水线失败: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def run_weekly_pipeline(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        运行周度流水线
        
        @param {Optional[datetime]} start_date - 开始日期
        @param {Optional[datetime]} end_date - 结束日期
        @returns {Dict[str, Any]} 运行结果
        """
        print("\n" + "="*70)
        print(f"  运行 {self.market} 市场周度流水线")
        print("="*70)
        
        try:
            # 周度流水线复用日度数据
            raw_data = self.fetch_all_data(start_date, end_date, incremental=False)
            
            if not raw_data:
                raise PipelineError("No data fetched")
            
            transformed_data = self.transform_data(raw_data)
            raw_data, transformed_data = self.calculate_derived_indicators(
                raw_data,
                transformed_data,
                start_date,
                end_date
            )
            scores, composite_score = self.calculate_scores(transformed_data, view_type='weekly')
            confirm_results = self.apply_confirm_layer(scores, view_type='weekly')
            
            saved_count = self.save_to_database(
                raw_data, transformed_data, scores, confirm_results, composite_score, view_type='weekly'
            )
            
            result = {
                'success': True,
                'market': self.market,
                'view_type': 'weekly',
                'indicators_fetched': len(raw_data),
                'records_saved': saved_count,
                'date_range': (scores.index.min(), scores.index.max()),
                'timestamp': datetime.now()
            }
            
            print("\n" + "="*70)
            print(f"  周度流水线完成")
            print("="*70)
            print(f"[OK] 获取指标: {result['indicators_fetched']}")
            print(f"[OK] 保存记录: {result['records_saved']}")
            
            return result
        
        except Exception as e:
            print(f"\n[ERROR] 周度流水线失败: {e}")
            
            return {
                'success': False,
                'error': str(e)
            }
    
    def run_full_pipeline(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        incremental: bool = False
    ) -> Dict[str, Any]:
        """
        运行完整流水线（日度 + 周度）
        
        @param {Optional[datetime]} start_date - 开始日期
        @param {Optional[datetime]} end_date - 结束日期
        @param {bool} incremental - 是否增量更新
        @returns {Dict[str, Any]} 运行结果
        """
        print("\n" + "*"*70)
        print(f"  {self.market} 市场完整流水线")
        print("*"*70)
        
        # 运行日度
        daily_result = self.run_daily_pipeline(start_date, end_date, incremental)
        
        # 运行周度
        weekly_result = self.run_weekly_pipeline(start_date, end_date)
        
        return {
            'daily': daily_result,
            'weekly': weekly_result,
            'overall_success': daily_result['success'] and weekly_result['success']
        }
    
    def _get_last_data_date(self) -> Optional[datetime]:
        """获取最后一次数据日期"""
        try:
            # 从数据库查询最后日期
            data = self.repository.load_series_data(limit=1)
            if data:
                return max([d.date for d in data])
        except:
            pass
        
        return None
    
    def _calculate_params_hash(self) -> str:
        """计算当前参数配置的哈希值"""
        params_dict = {
            'market': self.market,
            'z_window': self.market_config.get('z_window'),
            'green_threshold': self.market_config.get('green_threshold'),
            'red_threshold': self.market_config.get('red_threshold')
        }
        
        params_str = json.dumps(params_dict, sort_keys=True)
        return hashlib.md5(params_str.encode()).hexdigest()[:16]

