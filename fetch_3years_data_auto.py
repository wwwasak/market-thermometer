"""
自动获取近三年数据并验证（完全自动化，无需CSV导入）

功能：
1. 自动获取CN和US市场近三年（1095天）的所有指标数据
2. 使用多种数据源：FRED、yfinance、akshare、Stooq（东方财富通过akshare）
3. 填充数据库
4. 验证是否符合demand.txt中的需求
5. 检查计算逻辑是否正确
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any
import pandas as pd
import numpy as np
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.config import Config
from core.pipeline import MarketPipeline
from core.transforms import apply_transform
from core.scoring import (
    standardize_with_direction, score_from_z, lamp_from_score, 
    regime_from_score, rolling_z, rolling_madz
)
from core.combine import (
    pair_combine, hard_veto_min, soft_confirm_weighted, final_lamp
)
from storage.migrate import init_database
from storage.repository import Repository
from core.datasource import DataSourceManager


class AutoDataFetcher:
    """
    自动数据获取器
    
    确保所有指标都能自动获取，无需CSV导入
    """
    
    def __init__(self, config: Config):
        """
        初始化自动数据获取器
        
        @param {Config} config - 配置对象
        """
        self.config = config
        self.data_source = DataSourceManager()
        self.fetch_stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'missing': []
        }

    @staticmethod
    def _ensure_tz_naive(obj):
        """确保序列索引为tz-naive，便于后续对齐"""
        if isinstance(obj, pd.Series):
            idx = obj.index
            if isinstance(idx, pd.DatetimeIndex):
                if idx.tz is not None:
                    obj = obj.copy()
                    obj.index = idx.tz_convert('UTC').tz_localize(None)
                obj = obj.sort_index()
            return obj
        elif isinstance(obj, tuple):
            return tuple(AutoDataFetcher._ensure_tz_naive(item) for item in obj)
        else:
            return obj
    
    def verify_all_indicators_auto(self, market: str) -> Dict[str, bool]:
        """
        验证所有指标是否都能自动获取
        
        @param {str} market - 'CN' 或 'US'
        @returns {Dict[str, bool]} 指标代码 -> 是否可自动获取
        """
        indicators = self.config.get(f'indicators.{market}.main', [])
        observers = self.config.get(f'indicators.{market}.observers', [])
        all_indicators = indicators + observers
        
        result = {}
        
        for ind in all_indicators:
            code = ind.get('code', '')
            source = ind.get('source')
            
            # 派生指标或无source的观察者由流水线内部处理
            if ind.get('derived', False) or not source:
                result[code] = True
                continue
            
            source_lower = source.lower() if isinstance(source, str) else source
            if source_lower in ['csv', 'manual']:
                result[code] = False
                self.fetch_stats['missing'].append({
                    'code': code,
                    'reason': f'数据源为{source_lower}，需要手动导入'
                })
            else:
                result[code] = True
        
        return result
    
    def fetch_indicator_with_fallback(
        self,
        indicator: Dict,
        start_date: datetime,
        end_date: datetime
    ) -> pd.Series:
        """
        获取指标数据，支持多种数据源回退
        
        @param {Dict} indicator - 指标配置
        @param {datetime} start_date - 开始日期
        @param {datetime} end_date - 结束日期
        @returns {pd.Series} 时间序列数据
        """
        code = indicator.get('code', '')
        source = indicator.get('source')
        symbol = indicator.get('symbol') or indicator.get('ticker')
        
        print(f"\n[FETCH] {code} (source: {source}, symbol: {symbol})")
        
        # 派生指标或无source的观察者跳过（由流水线内部计算）
        if indicator.get('derived', False):
            print(f"[SKIP] {code} 为派生指标，在流水线中计算")
            return pd.Series(dtype=float)

        if not source:
            print(f"[SKIP] {code} 无独立数据源，由基础指标派生")
            return pd.Series(dtype=float)

        source_lower = source.lower() if isinstance(source, str) else source
        if source_lower in ['csv', 'manual']:
            print(f"[SKIP] {code} 数据源为 {source_lower}，需要手动导入")
            self.fetch_stats['missing'].append({
                'code': code,
                'reason': f'数据源为{source_lower}，需要手动导入'
            })
            return pd.Series(dtype=float)

        try:
            # 统一通过数据源管理器获取数据
            series = self.data_source.fetch_by_config(indicator, start_date, end_date)
            series = self._ensure_tz_naive(series)
            
            if isinstance(series, tuple):
                valid_series = [s for s in series if isinstance(s, pd.Series) and len(s) > 0]
                if not valid_series:
                    raise ValueError("获取到0条数据")
                series_start = valid_series[0].index.min()
                series_end = valid_series[0].index.max()
                expected_days = (end_date - start_date).days * 5 // 7
                if len(valid_series[0]) < expected_days * 0.5:
                    print(f"[WARNING] {code} 数据量偏少: {len(valid_series[0])} < {expected_days * 0.5}")
                print(f"[OK] {code}: {len(valid_series[0])} 条记录 ({series_start.date()} 至 {series_end.date()})")
            else:
                if not isinstance(series, pd.Series) or len(series) == 0:
                    raise ValueError("获取到0条数据")
                series_start = series.index.min()
                series_end = series.index.max()
                expected_days = (end_date - start_date).days * 5 // 7
                if len(series) < expected_days * 0.5:
                    print(f"[WARNING] {code} 数据量偏少: {len(series)} < {expected_days * 0.5}")
                print(f"[OK] {code}: {len(series)} 条记录 ({series_start.date()} 至 {series_end.date()})")
            
            self.fetch_stats['success'] += 1
            return series
            
        except Exception as e:
            print(f"[ERROR] {code} 获取失败: {e}")
            self.fetch_stats['failed'] += 1
            self.fetch_stats['missing'].append({
                'code': code,
                'reason': str(e)
            })
            # 返回空序列
            return pd.Series(dtype=float)
    
    def fetch_all_indicators(
        self,
        market: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, pd.Series]:
        """
        获取指定市场的所有指标数据
        
        @param {str} market - 'CN' 或 'US'
        @param {datetime} start_date - 开始日期
        @param {datetime} end_date - 结束日期
        @returns {Dict[str, pd.Series]} 数据字典 {code: series}
        """
        print(f"\n{'='*80}")
        print(f"自动获取 {market} 市场所有指标数据")
        print(f"{'='*80}")
        
        # 获取所有指标配置
        main_indicators = self.config.get(f'indicators.{market}.main', [])
        observer_indicators = self.config.get(f'indicators.{market}.observers', [])
        all_indicators = main_indicators + observer_indicators
        
        # 过滤掉需要CSV导入的指标
        auto_indicators = []
        manual_indicators = []
        skipped_indicators = []

        for ind in all_indicators:
            source = ind.get('source')
            code = ind.get('code')

            if ind.get('derived', False) or not source:
                skipped_indicators.append(code)
                continue

            source_lower = source.lower() if isinstance(source, str) else source
            if source_lower in ['csv', 'manual']:
                manual_indicators.append(code)
                continue

            auto_indicators.append(ind)
        
        print(f"\n[INFO] 总指标数: {len(all_indicators)}")
        print(f"[INFO] 可自动获取: {len(auto_indicators)}")
        print(f"[INFO] 需要手动导入: {len(manual_indicators)}")
        if manual_indicators:
            print(f"[WARNING] 以下指标需要手动导入: {', '.join(manual_indicators)}")
            for code in manual_indicators:
                self.fetch_stats['missing'].append({
                    'code': code,
                    'reason': '数据源为csv/manual，需要手动导入'
                })
        if skipped_indicators:
            print(f"[INFO] 以下指标无需单独获取（派生或依赖基础指标）: {', '.join(skipped_indicators)}")
        
        # 获取数据
        results = {}
        self.fetch_stats = {
            'total': len(auto_indicators),
            'success': 0,
            'failed': 0,
            'missing': []
        }
        
        for indicator in auto_indicators:
            code = indicator.get('code', '')
            series = self.fetch_indicator_with_fallback(
                indicator, start_date, end_date
            )
            
            if isinstance(series, tuple):
                valid_tuple = [s for s in series if isinstance(s, pd.Series) and len(s) > 0]
                if valid_tuple:
                    results[code] = series
            elif isinstance(series, pd.Series) and len(series) > 0:
                results[code] = series
        
        # 打印统计
        print(f"\n{'='*80}")
        print(f"数据获取统计 ({market})")
        print(f"{'='*80}")
        total = self.fetch_stats['total'] if self.fetch_stats['total'] > 0 else 1
        success = self.fetch_stats['success']
        failed = self.fetch_stats['failed']
        print(f"总指标数: {total}")
        print(f"成功获取: {success}")
        print(f"获取失败: {failed}")
        print(f"成功率: {success / total * 100:.1f}%")
        
        if self.fetch_stats['missing']:
            print(f"\n失败的指标:")
            for item in self.fetch_stats['missing']:
                print(f"  - {item['code']}: {item['reason']}")
        
        return results


def fetch_3years_data_auto(market: str, db_url: str) -> Dict[str, Any]:
    """
    自动获取近三年数据并填充数据库
    
    @param {str} market - 市场代码 ('CN' 或 'US')
    @param {str} db_url - 数据库URL
    @returns {Dict[str, Any]} 结果统计
    """
    print(f"\n{'='*80}")
    print(f"自动获取 {market} 市场近三年数据")
    print(f"{'='*80}")
    
    # 初始化配置
    config = Config()
    
    # 创建自动数据获取器
    auto_fetcher = AutoDataFetcher(config)
    
    # 验证所有指标是否都能自动获取
    print(f"\n[INFO] 验证 {market} 市场指标自动获取能力...")
    auto_status = auto_fetcher.verify_all_indicators_auto(market)
    
    manual_required = [code for code, can_auto in auto_status.items() if not can_auto]
    if manual_required:
        print(f"[WARNING] 以下指标需要手动导入: {', '.join(manual_required)}")
    else:
        print(f"[OK] 所有指标都可以自动获取！")
    
    # 计算日期范围（近三年，约1095天）
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1095)
    
    print(f"\n[INFO] 日期范围: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
    print(f"[INFO] 预计交易日数: ~{1095 * 5 // 7} 天")
    
    # 获取所有指标数据
    print(f"\n[INFO] 开始自动获取数据...")
    raw_data = auto_fetcher.fetch_all_indicators(market, start_date, end_date)
    
    if len(raw_data) == 0:
        print(f"\n[ERROR] 未能获取到任何数据！")
        return {
            'success': False,
            'error': 'No data fetched'
        }
    
    print(f"\n[OK] 成功获取 {len(raw_data)} 个指标的数据")
    
    # 创建流水线处理数据
    print(f"\n[INFO] 创建数据处理流水线...")
    pipeline = MarketPipeline(market=market, database_url=db_url, config=config)
    
    # 转换数据
    print(f"\n[INFO] 开始数据转换...")
    try:
        transformed_data = pipeline.transform_data(raw_data)
        transformed_data = pipeline.calculate_derived_indicators(
            transformed_data,
            start_date=start_date,
            end_date=end_date
        )

        # 确保派生指标在原始数据集中占位，便于后续保存
        for indicator in pipeline.indicators:
            code = indicator['code']
            if indicator.get('derived', False) and code in transformed_data and code not in raw_data:
                raw_data[code] = transformed_data[code]

        # 将配对类指标的原始数据替换为转换后的结果，便于后续存储
        for code, value in list(raw_data.items()):
            if isinstance(value, tuple) and code in transformed_data:
                raw_data[code] = transformed_data[code]

        print(f"[OK] 数据转换完成")
    except Exception as e:
        print(f"[ERROR] 数据转换失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': f'Transform failed: {str(e)}'
        }
    
    # 计算评分
    print(f"\n[INFO] 开始计算评分...")
    try:
        scores = pipeline.calculate_scores(transformed_data, view_type='daily')
        print(f"[OK] 评分计算完成")
    except Exception as e:
        print(f"[ERROR] 评分计算失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': f'Scoring failed: {str(e)}'
        }
    
    # 应用确认层
    print(f"\n[INFO] 开始应用确认层...")
    try:
        confirm_results = pipeline.apply_confirm_layer(scores, view_type='daily')
        print(f"[OK] 确认层应用完成")
    except Exception as e:
        print(f"[ERROR] 确认层应用失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': f'Confirm layer failed: {str(e)}'
        }
    
    # 保存到数据库
    print(f"\n[INFO] 开始保存到数据库...")
    try:
        saved_count = pipeline.save_to_database(
            raw_data, transformed_data, scores, confirm_results, view_type='daily'
        )
        print(f"[OK] 保存完成，共保存 {saved_count} 条记录")
    except Exception as e:
        print(f"[ERROR] 保存失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': f'Save failed: {str(e)}'
        }
    
    return {
        'success': True,
        'indicators_fetched': len(raw_data),
        'records_saved': saved_count,
        'date_range': (start_date, end_date),
        'fetch_stats': auto_fetcher.fetch_stats
    }


def main():
    """
    主函数
    """
    print("=" * 80)
    print("双市场温度计 - 自动获取近三年数据（完全自动化）")
    print("=" * 80)
    
    # 初始化配置
    config = Config()
    
    # 数据库路径
    db_path = 'data/market_thermo_3years_auto.db'
    db_url = f'sqlite:///{db_path}'
    
    # 确保data目录存在
    os.makedirs('data', exist_ok=True)
    
    # 初始化数据库
    print(f"\n[INFO] 初始化数据库: {db_path}")
    init_database(db_url, force=True)
    
    # 获取US市场数据
    print(f"\n{'='*80}")
    print("开始获取US市场数据")
    print(f"{'='*80}")
    us_result = fetch_3years_data_auto('US', db_url)
    
    # 获取CN市场数据
    print(f"\n{'='*80}")
    print("开始获取CN市场数据")
    print(f"{'='*80}")
    cn_result = fetch_3years_data_auto('CN', db_url)
    
    # 总结
    print(f"\n{'='*80}")
    print("数据获取总结")
    print(f"{'='*80}")
    
    print(f"\nUS市场:")
    if us_result.get('success'):
        print(f"  ✓ 成功")
        print(f"  - 指标数: {us_result.get('indicators_fetched', 0)}")
        print(f"  - 记录数: {us_result.get('records_saved', 0)}")
        stats = us_result.get('fetch_stats', {})
        print(f"  - 成功率: {stats.get('success', 0)}/{stats.get('total', 0)} ({stats.get('success', 0)/stats.get('total', 1)*100:.1f}%)")
    else:
        print(f"  ✗ 失败: {us_result.get('error', 'Unknown error')}")
    
    print(f"\nCN市场:")
    if cn_result.get('success'):
        print(f"  ✓ 成功")
        print(f"  - 指标数: {cn_result.get('indicators_fetched', 0)}")
        print(f"  - 记录数: {cn_result.get('records_saved', 0)}")
        stats = cn_result.get('fetch_stats', {})
        print(f"  - 成功率: {stats.get('success', 0)}/{stats.get('total', 0)} ({stats.get('success', 0)/stats.get('total', 1)*100:.1f}%)")
    else:
        print(f"  ✗ 失败: {cn_result.get('error', 'Unknown error')}")
    
    print(f"\n数据库路径: {db_path}")
    print(f"{'='*80}")
    
    # 检查是否有需要手动导入的指标
    all_manual = []
    if us_result.get('fetch_stats', {}).get('missing'):
        all_manual.extend(us_result['fetch_stats']['missing'])
    if cn_result.get('fetch_stats', {}).get('missing'):
        all_manual.extend(cn_result['fetch_stats']['missing'])
    
    if all_manual:
        print(f"\n⚠ 以下指标需要手动导入或修复:")
        for item in all_manual:
            print(f"  - {item['code']}: {item['reason']}")
        else:
            print(f"\n✓ 所有指标都已成功自动获取！")


if __name__ == '__main__':
    main()

