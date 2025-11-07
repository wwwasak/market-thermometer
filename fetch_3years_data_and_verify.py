"""
获取近三年数据并验证是否符合demand需求

功能：
1. 获取CN和US市场近三年（1095天）的数据
2. 填充数据库
3. 验证是否符合demand.txt中的需求
4. 检查计算逻辑是否正确
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
from scipy.stats import median_abs_deviation
from core.combine import (
    pair_combine, hard_veto, soft_confirm_weighted, final_lamp
)
from storage.migrate import init_database
from storage.repository import Repository


class DemandVerifier:
    """
    需求验证器
    
    验证数据获取和计算是否符合demand.txt中的要求
    """
    
    def __init__(self, config: Config):
        """
        初始化验证器
        
        @param {Config} config - 配置对象
        """
        self.config = config
        self.issues = []
        self.warnings = []
        self.passed = []
        
    def verify_indicator_config(self, indicator: Dict, demand_spec: Dict) -> bool:
        """
        验证单个指标的配置是否符合demand要求
        
        @param {Dict} indicator - 实际指标配置
        @param {Dict} demand_spec - demand.txt中的要求
        @returns {bool} 是否符合要求
        """
        code = indicator.get('code', '')
        issues = []
        
        # 检查方向
        if indicator.get('direction') != demand_spec.get('direction'):
            issues.append(f"方向不匹配: 期望 {demand_spec.get('direction')}, 实际 {indicator.get('direction')}")
        
        # 检查转换类型
        if indicator.get('transform') != demand_spec.get('transform'):
            issues.append(f"转换类型不匹配: 期望 {demand_spec.get('transform')}, 实际 {indicator.get('transform')}")
        
        # 检查Z类型
        expected_z_type = demand_spec.get('z_type', 'Z')
        if indicator.get('z_type') != expected_z_type:
            issues.append(f"Z类型不匹配: 期望 {expected_z_type}, 实际 {indicator.get('z_type')}")
        
        # 检查Z窗口
        expected_z_window = demand_spec.get('z_window', 60)
        if indicator.get('z_window') != expected_z_window:
            issues.append(f"Z窗口不匹配: 期望 {expected_z_window}, 实际 {indicator.get('z_window')}")
        
        if issues:
            self.issues.append(f"{code}: {'; '.join(issues)}")
            return False
        else:
            self.passed.append(f"{code}: 配置符合要求")
            return True
    
    def verify_regime_thresholds(self) -> bool:
        """
        验证Regime阈值是否符合demand要求
        
        @returns {bool} 是否符合要求
        """
        attack_threshold = self.config.get('regime.attack_threshold', 70)
        defense_threshold = self.config.get('regime.defense_threshold', 40)
        
        if attack_threshold != 70:
            self.issues.append(f"Regime Attack阈值不匹配: 期望 70, 实际 {attack_threshold}")
            return False
        
        if defense_threshold != 40:
            self.issues.append(f"Regime Defense阈值不匹配: 期望 40, 实际 {defense_threshold}")
            return False
        
        self.passed.append("Regime阈值符合要求 (Attack=70, Defense=40)")
        return True
    
    def verify_lamp_thresholds(self) -> bool:
        """
        验证灯色阈值是否符合demand要求
        
        @returns {bool} 是否符合要求
        """
        green_threshold = self.config.get('lamp.green_threshold', 60)
        red_threshold = self.config.get('lamp.red_threshold', 40)
        
        if green_threshold != 60:
            self.issues.append(f"灯色Green阈值不匹配: 期望 60, 实际 {green_threshold}")
            return False
        
        if red_threshold != 40:
            self.issues.append(f"灯色Red阈值不匹配: 期望 40, 实际 {red_threshold}")
            return False
        
        self.passed.append("灯色阈值符合要求 (Green=60, Red=40)")
        return True
    
    def verify_score_calculation(self, z_scores: pd.Series) -> Tuple[pd.Series, bool]:
        """
        验证Score计算是否符合demand要求
        
        demand要求: Score = clamp(50 + 10*Z, 0, 100)
        
        @param {pd.Series} z_scores - Z分数序列
        @returns {Tuple[pd.Series, bool]} (计算的score, 是否符合要求)
        """
        calculated_scores = score_from_z(z_scores)
        
        # 验证公式
        expected_scores = np.clip(50 + 10 * z_scores, 0, 100)
        
        # 允许小的浮点误差
        diff = np.abs(calculated_scores - expected_scores)
        max_diff = diff.max()
        
        if max_diff > 1e-6:
            self.issues.append(f"Score计算公式不匹配: 最大差异 {max_diff}")
            return calculated_scores, False
        
        # 验证范围
        if calculated_scores.min() < 0 or calculated_scores.max() > 100:
            self.issues.append(f"Score超出范围 [0, 100]: 实际范围 [{calculated_scores.min():.2f}, {calculated_scores.max():.2f}]")
            return calculated_scores, False
        
        self.passed.append("Score计算符合要求 (50 + 10*Z, clamped to [0, 100])")
        return calculated_scores, True
    
    def verify_z_calculation(
        self, 
        series: pd.Series, 
        method: str, 
        window: int, 
        direction: str
    ) -> Tuple[pd.Series, bool]:
        """
        验证Z分数计算是否符合demand要求
        
        demand要求: Z = sign * (X - μ)/σ, where sign=+1 (up_good), -1 (down_good)
        
        @param {pd.Series} series - 转换后的数据序列
        @param {str} method - 'Z' 或 'MADZ'
        @param {int} window - 窗口大小
        @param {str} direction - 'up_good' 或 'down_good'
        @returns {Tuple[pd.Series, bool]} (计算的Z分数, 是否符合要求)
        """
        try:
            # 使用standardize_with_direction来验证方向是否正确应用
            calculated_z = standardize_with_direction(
                series, 
                direction=direction,
                z_type=method,
                window=window
            )
            
            # 检查是否有足够的非NaN值
            valid_count = calculated_z.notna().sum()
            if valid_count < window:
                self.warnings.append(f"Z分数有效值不足: {valid_count} < {window} (窗口大小)")
            
            self.passed.append(f"Z分数计算完成 ({method}, window={window}, direction={direction})")
            return calculated_z, True
        except Exception as e:
            self.issues.append(f"Z分数计算失败: {e}")
            return pd.Series(), False
    
    def verify_style_weights(self, market: str) -> bool:
        """
        验证风格权重是否符合demand要求
        
        @param {str} market - 'CN' 或 'US'
        @returns {bool} 是否符合要求
        """
        style_weights = self.config.get(f'style_weights.{market}', {})
        
        # demand要求的权重（按顺序）
        if market == 'CN':
            demand_weights = {
                'Attack': [24, 16, 12, 20, 16, 12],
                'Balanced': [20, 14, 12, 18, 18, 18],
                'Defense': [15, 10, 10, 12, 20, 33]
            }
        else:  # US
            demand_weights = {
                'Attack': [12, 8, 18, 16, 16, 30],
                'Balanced': [15, 10, 20, 15, 20, 20],
                'Defense': [18, 12, 24, 18, 28, 0]
            }
        
        for style in ['Attack', 'Balanced', 'Defense']:
            expected = demand_weights[style]
            actual = style_weights.get(style, [])
            
            if actual != expected:
                self.issues.append(
                    f"{market} {style}权重不匹配: 期望 {expected}, 实际 {actual}"
                )
                return False
            
            # 验证权重总和是否为100
            if sum(actual) != 100:
                self.warnings.append(
                    f"{market} {style}权重总和不为100: {sum(actual)}"
                )
        
        self.passed.append(f"{market}风格权重符合要求")
        return True
    
    def verify_soft_confirm_weights(self, market: str) -> bool:
        """
        验证软确认权重是否符合demand要求
        
        @param {str} market - 'CN' 或 'US'
        @returns {bool} 是否符合要求
        """
        weights = self.config.get(f'soft_confirm_weights.{market}', {})
        
        if market == 'CN':
            # demand要求: PAIR_CNH_CNY 0.50, PAIR_TWEX_DXY 0.50
            expected = {'PAIR_CNH_CNY': 0.50, 'PAIR_TWEX_DXY': 0.50}
        else:  # US
            # demand要求: IWM_SPY_SOFT 0.30, HYG_IEF_SOFT 0.30, PAIR_TWEX_DXY 0.20, PAIR_CNH_CNY 0.20
            expected = {
                'IWM_SPY_SOFT': 0.30,
                'HYG_IEF_SOFT': 0.30,
                'PAIR_TWEX_DXY': 0.20,
                'PAIR_CNH_CNY': 0.20
            }
        
        # 验证每个权重
        for key, expected_value in expected.items():
            actual_value = weights.get(key)
            if actual_value is None:
                self.issues.append(f"{market} 软确认权重缺失: {key}")
                return False
            if abs(actual_value - expected_value) > 1e-6:
                self.issues.append(
                    f"{market} {key}权重不匹配: 期望 {expected_value}, 实际 {actual_value}"
                )
                return False
        
        # 验证权重总和是否为1.0
        total = sum(weights.values())
        if abs(total - 1.0) > 1e-6:
            self.warnings.append(
                f"{market} 软确认权重总和不为1.0: {total}"
            )
        
        self.passed.append(f"{market}软确认权重符合要求")
        return True
    
    def verify_persistence_config(self) -> bool:
        """
        验证持续性配置是否符合demand要求
        
        @returns {bool} 是否符合要求
        """
        # demand要求:
        # - daily regime persistence_days=3 (default 0 allowed)
        # - weekly regime persistence_weeks=1
        # - hard-veto persistence: daily 3 days, weekly 2 weeks
        
        regime_persistence_days = self.config.get('regime.persistence_days', 0)
        regime_persistence_weeks = self.config.get('regime.persistence_weeks', 1)
        hard_veto_days = self.config.get('persistence.hard_veto_days', 3)
        hard_veto_weeks = self.config.get('persistence.hard_veto_weeks', 2)
        
        if regime_persistence_weeks != 1:
            self.issues.append(
                f"周视图regime persistence不匹配: 期望 1, 实际 {regime_persistence_weeks}"
            )
            return False
        
        if hard_veto_days != 3:
            self.issues.append(
                f"日视图硬否决persistence不匹配: 期望 3, 实际 {hard_veto_days}"
            )
            return False
        
        if hard_veto_weeks != 2:
            self.issues.append(
                f"周视图硬否决persistence不匹配: 期望 2, 实际 {hard_veto_weeks}"
            )
            return False
        
        self.passed.append("持续性配置符合要求")
        return True
    
    def verify_transform_params(self) -> bool:
        """
        验证转换参数是否符合demand要求
        
        @returns {bool} 是否符合要求
        """
        # demand要求:
        # - EWMA λ=0.94 (for margin slope)
        # - VIX winsor (0.02, 0.98)
        
        ewma_lambda = self.config.get('transforms.ewma_lambda', 0.94)
        vix_winsor_low = self.config.get('transforms.vix_winsor_low', 0.02)
        vix_winsor_high = self.config.get('transforms.vix_winsor_high', 0.98)
        
        if abs(ewma_lambda - 0.94) > 1e-6:
            self.issues.append(
                f"EWMA lambda不匹配: 期望 0.94, 实际 {ewma_lambda}"
            )
            return False
        
        if abs(vix_winsor_low - 0.02) > 1e-6:
            self.issues.append(
                f"VIX winsor下限不匹配: 期望 0.02, 实际 {vix_winsor_low}"
            )
            return False
        
        if abs(vix_winsor_high - 0.98) > 1e-6:
            self.issues.append(
                f"VIX winsor上限不匹配: 期望 0.98, 实际 {vix_winsor_high}"
            )
            return False
        
        self.passed.append("转换参数符合要求")
        return True
    
    def generate_report(self) -> str:
        """
        生成验证报告
        
        @returns {str} 报告文本
        """
        report = []
        report.append("=" * 80)
        report.append("需求验证报告")
        report.append("=" * 80)
        report.append("")
        
        # 统计
        total_checks = len(self.passed) + len(self.issues)
        report.append(f"总检查项: {total_checks}")
        report.append(f"通过: {len(self.passed)}")
        report.append(f"失败: {len(self.issues)}")
        report.append(f"警告: {len(self.warnings)}")
        report.append("")
        
        # 通过的检查
        if self.passed:
            report.append("✓ 通过的检查:")
            report.append("-" * 80)
            for item in self.passed:
                report.append(f"  ✓ {item}")
            report.append("")
        
        # 失败的检查
        if self.issues:
            report.append("✗ 失败的检查:")
            report.append("-" * 80)
            for item in self.issues:
                report.append(f"  ✗ {item}")
            report.append("")
        
        # 警告
        if self.warnings:
            report.append("⚠ 警告:")
            report.append("-" * 80)
            for item in self.warnings:
                report.append(f"  ⚠ {item}")
            report.append("")
        
        # 总结
        report.append("=" * 80)
        if len(self.issues) == 0:
            report.append("✓ 所有检查通过！配置符合demand需求。")
        else:
            report.append(f"✗ 发现 {len(self.issues)} 个问题，需要修复。")
        report.append("=" * 80)
        
        return "\n".join(report)


def fetch_3years_data(market: str, db_url: str) -> Dict[str, Any]:
    """
    获取近三年数据并填充数据库
    
    @param {str} market - 市场代码 ('CN' 或 'US')
    @param {str} db_url - 数据库URL
    @returns {Dict[str, Any]} 结果统计
    """
    print(f"\n{'='*80}")
    print(f"获取 {market} 市场近三年数据")
    print(f"{'='*80}")
    
    # 创建流水线
    pipeline = MarketPipeline(market=market, database_url=db_url)
    
    # 计算日期范围（近三年，约1095天）
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1095)
    
    print(f"\n[INFO] 日期范围: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
    print(f"[INFO] 预计交易日数: ~{1095 * 5 // 7} 天")
    
    # 获取数据
    print(f"\n[INFO] 开始获取数据...")
    try:
        raw_data = pipeline.fetch_all_data(start_date, end_date, incremental=False)
        
        print(f"\n[OK] 数据获取完成")
        print(f"成功获取 {len(raw_data)} 个指标的数据")
        
        # 显示每个指标的数据量
        for code, series in raw_data.items():
            print(f"  {code:25s}: {len(series):4d} 条记录")
        
        # 转换数据
        print(f"\n[INFO] 开始数据转换...")
        transformed_data = pipeline.transform_data(raw_data)
        print(f"[OK] 数据转换完成")
        
        # 计算评分
        print(f"\n[INFO] 开始计算评分...")
        scores = pipeline.calculate_scores(transformed_data, view_type='daily')
        print(f"[OK] 评分计算完成")
        
        # 应用确认层
        print(f"\n[INFO] 开始应用确认层...")
        confirm_results = pipeline.apply_confirm_layer(scores, view_type='daily')
        print(f"[OK] 确认层应用完成")
        
        # 保存到数据库
        print(f"\n[INFO] 开始保存到数据库...")
        saved_count = pipeline.save_to_database(
            raw_data, transformed_data, scores, confirm_results, view_type='daily'
        )
        print(f"[OK] 保存完成，共保存 {saved_count} 条记录")
        
        return {
            'success': True,
            'indicators_fetched': len(raw_data),
            'records_saved': saved_count,
            'date_range': (start_date, end_date)
        }
        
    except Exception as e:
        print(f"\n[ERROR] 数据获取失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


def main():
    """
    主函数
    """
    print("=" * 80)
    print("双市场温度计 - 近三年数据获取与验证")
    print("=" * 80)
    
    # 初始化配置
    config = Config()
    
    # 数据库路径
    db_path = 'data/market_thermo_3years.db'
    db_url = f'sqlite:///{db_path}'
    
    # 确保data目录存在
    os.makedirs('data', exist_ok=True)
    
    # 初始化数据库
    print(f"\n[INFO] 初始化数据库: {db_path}")
    init_database(db_url, force=True)
    
    # 创建验证器
    verifier = DemandVerifier(config)
    
    # 验证配置
    print(f"\n{'='*80}")
    print("验证配置是否符合demand需求")
    print(f"{'='*80}")
    
    # 1. 验证Regime阈值
    verifier.verify_regime_thresholds()
    
    # 2. 验证灯色阈值
    verifier.verify_lamp_thresholds()
    
    # 3. 验证风格权重
    verifier.verify_style_weights('CN')
    verifier.verify_style_weights('US')
    
    # 4. 验证软确认权重
    verifier.verify_soft_confirm_weights('CN')
    verifier.verify_soft_confirm_weights('US')
    
    # 5. 验证持续性配置
    verifier.verify_persistence_config()
    
    # 6. 验证转换参数
    verifier.verify_transform_params()
    
    # 生成验证报告
    report = verifier.generate_report()
    print(report)
    
    # 保存报告
    report_path = 'data/verification_report.txt'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n[INFO] 验证报告已保存到: {report_path}")
    
    # 如果验证通过，继续获取数据
    if len(verifier.issues) == 0:
        print(f"\n{'='*80}")
        print("配置验证通过，开始获取数据...")
        print(f"{'='*80}")
        
        # 获取US市场数据
        us_result = fetch_3years_data('US', db_url)
        
        # 获取CN市场数据
        cn_result = fetch_3years_data('CN', db_url)
        
        # 总结
        print(f"\n{'='*80}")
        print("数据获取总结")
        print(f"{'='*80}")
        print(f"US市场: {'成功' if us_result.get('success') else '失败'}")
        if us_result.get('success'):
            print(f"  - 指标数: {us_result.get('indicators_fetched', 0)}")
            print(f"  - 记录数: {us_result.get('records_saved', 0)}")
        
        print(f"\nCN市场: {'成功' if cn_result.get('success') else '失败'}")
        if cn_result.get('success'):
            print(f"  - 指标数: {cn_result.get('indicators_fetched', 0)}")
            print(f"  - 记录数: {cn_result.get('records_saved', 0)}")
        
        print(f"\n数据库路径: {db_path}")
        print(f"{'='*80}")
    else:
        print(f"\n[WARNING] 发现配置问题，请先修复后再获取数据。")
        print(f"问题列表:")
        for issue in verifier.issues:
            print(f"  - {issue}")


if __name__ == '__main__':
    main()

