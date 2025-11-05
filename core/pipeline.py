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
        self.indicators = main_indicators + observer_indicators
        
        # 获取市场特定参数
        self.market_config = {
            'z_type': self.config.get('z_type', 'Z').upper(),  # 确保大写
            'z_window': self.config.get('z_window', 60),
            'green_threshold': self.config.get('lamp.green_threshold', 60),
            'red_threshold': self.config.get('lamp.red_threshold', 40),
            'confirm_layer': self.config.get('confirm_layer', {})
        }
        
        # 流水线状态
        self.last_update = None
        self.data_cache = {}
    
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
        
        for indicator in self.indicators:
            code = indicator['code']
            source = indicator.get('source', '')
            
            try:
                # 跳过没有source的派生指标（观察者指标）
                if not source:
                    print(f"[SKIP] {code} - 派生指标")
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
        
        print(f"\n[OK] 成功获取 {success_count}/{len(self.indicators)} 个指标")
        
        # 记录获取日志
        self.repository.add_fetch_log(
            action='fetch_all',
            status='success',
            message=f"Fetched {success_count}/{len(self.indicators)} indicators for {self.market}"
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
        
        transformed = {}
        
        for indicator in self.indicators:
            code = indicator['code']
            
            if code not in raw_data:
                continue
            
            transform = indicator.get('transform', 'raw')
            series = raw_data[code]
            
            try:
                if transform == 'raw':
                    transformed[code] = series
                else:
                    # 应用转换
                    transformed[code] = apply_transform(series, transform)
                    print(f"[TRANSFORM] {code}: {transform}")
            
            except Exception as e:
                print(f"[ERROR] {code} 转换失败: {e}")
        
        print(f"[OK] 完成 {len(transformed)} 个指标的转换")
        
        return transformed
    
    def calculate_scores(
        self,
        transformed_data: Dict[str, pd.Series],
        view_type: str = 'daily'
    ) -> pd.DataFrame:
        """
        计算评分和灯号
        
        @param {Dict[str, pd.Series]} transformed_data - 转换后的数据
        @param {str} view_type - 视图类型（'daily' 或 'weekly'）
        @returns {pd.DataFrame} 评分结果
        """
        print(f"\n[INFO] 计算 {view_type} 评分...")
        
        # 对齐所有序列到共同的日期索引
        codes_list = list(transformed_data.keys())
        series_list = [transformed_data[code] for code in codes_list if len(transformed_data[code]) > 0]
        
        if not series_list:
            raise PipelineError("No valid data for scoring")
        
        # 找到所有序列的共同日期索引
        common_dates = series_list[0].index
        for s in series_list[1:]:
            common_dates = common_dates.intersection(s.index)
        
        if len(common_dates) == 0:
            raise PipelineError("No common dates between series")
        
        # 创建DataFrame，保留DatetimeIndex
        df = pd.DataFrame({
            code: transformed_data[code].loc[common_dates]
            for code in codes_list if code in transformed_data
        }, index=common_dates)
        
        # 如果是周度，重采样
        if view_type == 'weekly':
            print("[INFO] 重采样到周度...")
            df = df.resample('W-FRI').last()
        
        # 准备批量标准化配置
        data_dict = {code: df[code] for code in df.columns}
        config_dict = {}
        
        for indicator in self.indicators:
            code = indicator['code']
            if code in df.columns:
                config_dict[code] = {
                    'direction': indicator.get('direction', 'up_good'),
                    'z_type': self.market_config.get('z_type', 'z'),
                    'z_window': self.market_config.get('z_window', 60)
                }
        
        # 批量标准化（返回字典）
        z_dict = batch_standardize(data_dict, config_dict)
        
        # 批量评分（返回字典）
        score_dict = batch_score(z_dict, center=50, scale=10)
        
        # 合并z-score和score到DataFrame
        result_data = {}
        for code in z_dict.keys():
            result_data[f"{code}_z"] = z_dict[code]
            result_data[f"{code}_score"] = score_dict[code]
        
        result_df = pd.DataFrame(result_data)
        
        print(f"[OK] 完成 {len(config_dict)} 个指标的评分")
        if len(result_df) > 0:
            print(f"[INFO] 数据时间范围: {result_df.index.min()} 至 {result_df.index.max()}")
            print(f"[INFO] 总共 {len(result_df)} 个时间点")
        
        return result_df
    
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
        
        # 将评分转换为灯号
        lamps = {}
        
        green_th = self.market_config.get('green_threshold', 60)
        red_th = self.market_config.get('red_threshold', 40)
        
        for code in scores.columns:
            if code.endswith('_score'):
                lamp_code = code.replace('_score', '_lamp')
                lamps[lamp_code] = lamp_from_score(scores[code], green_th, red_th)
        
        # 获取确认层配置
        confirm_config = self.market_config.get('confirm_layer', {})
        
        # 主指标灯号
        main_lamps = {code: lamp for code, lamp in lamps.items() if '_lamp' in code}
        
        # Hard veto 指标（这里简化处理，实际需要根据配置）
        hard_veto_lamps = []
        
        # Soft confirm 指标
        soft_confirm_lamps = list(main_lamps.values())
        soft_weights = [1.0] * len(soft_confirm_lamps)  # 简化为等权重
        
        # 持久化参数
        persistence_daily = confirm_config.get('persistence_daily', 3)
        persistence_weekly = confirm_config.get('persistence_weekly', 2)
        
        # 应用确认层
        try:
            result = build_confirm_layer(
                main_indicator_lamps=main_lamps,
                hard_veto_lamps=hard_veto_lamps,
                soft_confirm_lamps=soft_confirm_lamps,
                soft_weights=soft_weights,
                pair_rules={},
                persistence_daily=persistence_daily if view_type == 'daily' else 0,
                persistence_weekly=persistence_weekly if view_type == 'weekly' else 0,
                view_type=view_type
            )
            
            print(f"[OK] 确认层计算完成")
            
            return result
        
        except Exception as e:
            print(f"[ERROR] 确认层失败: {e}")
            return {}
    
    def save_to_database(
        self,
        raw_data: Dict[str, pd.Series],
        transformed_data: Dict[str, pd.Series],
        scores: pd.DataFrame,
        confirm_results: Dict[str, pd.Series],
        view_type: str = 'daily'
    ) -> int:
        """
        保存所有结果到数据库
        
        @param {Dict[str, pd.Series]} raw_data - 原始数据
        @param {Dict[str, pd.Series]} transformed_data - 转换后数据
        @param {pd.DataFrame} scores - 评分结果
        @param {Dict[str, pd.Series]} confirm_results - 确认层结果
        @param {str} view_type - 视图类型
        @returns {int} 保存的记录数
        """
        print(f"\n[INFO] 保存数据到数据库...")
        
        total_saved = 0
        
        # 1. 保存序列元数据（如果不存在）
        for indicator in self.indicators:
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
        
        # 2. 保存时间序列数据
        for code in raw_data.keys():
            if code not in transformed_data:
                continue
            
            raw_series = raw_data[code]
            trans_series = transformed_data[code]
            
            # 对齐索引
            common_idx = raw_series.index.intersection(trans_series.index)
            
            for date in common_idx:
                try:
                    # 获取对应的评分
                    score_col = f"{code}_score"
                    z_col = f"{code}_z"
                    
                    score_val = None
                    z_val = None
                    
                    if score_col in scores.columns and date in scores.index:
                        score_val = scores.loc[date, score_col]
                    
                    if z_col in scores.columns and date in scores.index:
                        z_val = scores.loc[date, z_col]
                    
                    self.repository.upsert_series_data(
                        code=code,
                        date=date.to_pydatetime(),
                        raw_value=float(raw_series.loc[date]),
                        transformed_value=float(trans_series.loc[date]),
                        z_score=float(z_val) if pd.notna(z_val) else None,
                        score=float(score_val) if pd.notna(score_val) else None,
                        view_type=view_type
                    )
                    
                    total_saved += 1
                
                except Exception as e:
                    # 跳过单个错误
                    continue
        
        # 3. 保存Regime数据
        if 'final_lamp' in confirm_results:
            final_lamp = confirm_results['final_lamp']
            
            # 计算当前参数的哈希
            params_hash = self._calculate_params_hash()
            
            for date in final_lamp.index:
                try:
                    # 这里简化处理，实际需要计算regime
                    regime_val = 'Balanced'  # 临时值
                    
                    self.repository.upsert_regime(
                        date=date.to_pydatetime(),
                        market=self.market,
                        view=view_type,
                        regime=regime_val,
                        final_lamp=final_lamp.loc[date],
                        soft_lamp=confirm_results.get('soft_confirm', pd.Series()).get(date, 'Y'),
                        hard_lamp=confirm_results.get('hard_veto', pd.Series()).get(date, 'G'),
                        params_hash=params_hash
                    )
                
                except Exception as e:
                    continue
        
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
            
            # 3. 计算评分
            scores = self.calculate_scores(transformed_data, view_type='daily')
            
            # 4. 应用确认层
            confirm_results = self.apply_confirm_layer(scores, view_type='daily')
            
            # 5. 保存到数据库
            saved_count = self.save_to_database(
                raw_data, transformed_data, scores, confirm_results, view_type='daily'
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
            scores = self.calculate_scores(transformed_data, view_type='weekly')
            confirm_results = self.apply_confirm_layer(scores, view_type='weekly')
            
            saved_count = self.save_to_database(
                raw_data, transformed_data, scores, confirm_results, view_type='weekly'
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

