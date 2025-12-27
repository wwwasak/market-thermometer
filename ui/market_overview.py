"""
市场概览组件

显示市场综合评分、各指标评分表格、权重配置以及确认层可视化
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
    QSplitter,
    QFrame,
    QHeaderView,
    QMessageBox,
    QProgressDialog,
    QDoubleSpinBox,
    QSpinBox,
    QDialog,
)
import pyqtgraph as pg

from storage.repository import Repository
from core.config import Config
from datetime import datetime, timedelta
from pathlib import Path

# 配置文件路径
CONFIG_FILE = Path("config/user_config.json")


class ScoreCalculationWorker(QThread):
    """
    后台线程：计算评分数据
    """
    
    progress = pyqtSignal(str)  # 进度消息
    completed = pyqtSignal(dict)  # 完成信号
    failed = pyqtSignal(str)  # 失败信号
    completeness_check = pyqtSignal(dict, object)  # 数据完整性检查信号 (report, pipeline)
    
    def __init__(
        self,
        database_url: str,
        market: str,
        view: str,
        config: Config,
        parent=None
    ):
        super().__init__(parent)
        self.database_url = database_url
        self.market = market
        self.view = view
        self.config = config
        self.user_choice = None  # 用户选择：'use_latest', 'skip', 'cancel'
        self._wait_for_user = False  # 是否等待用户选择
        self._skip_today = False  # 是否跳过今天的评分
    
    def set_user_choice(self, choice: str):
        """
        设置用户选择并继续执行
        
        @param {str} choice - 'use_latest', 'skip', 或 'cancel'
        """
        self.user_choice = choice
        self._wait_for_user = False
    
    def run(self):
        """执行评分计算"""
        try:
            from core.pipeline import MarketPipeline
            
            self.progress.emit(f"初始化 {self.market} 市场流水线...")
            
            # 创建pipeline
            pipeline = MarketPipeline(
                market=self.market,
                database_url=self.database_url,
                config=self.config
            )
            
            self.progress.emit("加载数据库中的原始数据...")
            
            # 从数据库加载所有已有的原始数据
            raw_data = {}
            transformed_data = {}
            
            for indicator in pipeline.indicators:
                code = indicator['code']
                
                try:
                    self.progress.emit(f"加载 {code}...")
                    
                    df = pipeline.repository.load_series_data_by_code(
                        code,
                        view='daily'  # 始终从日度数据开始
                    )
                    
                    if df is not None and not df.empty:
                        # 确保索引是DatetimeIndex
                        if not isinstance(df.index, pd.DatetimeIndex):
                            df.index = pd.to_datetime(df.index)
                        
                        # 获取原始值和转换值
                        if 'value_raw' in df.columns:
                            raw_series = df['value_raw'].dropna()
                            if len(raw_series) > 0:
                                raw_data[code] = raw_series
                        
                        if 'value_tr' in df.columns:
                            tr_series = df['value_tr'].dropna()
                            if len(tr_series) > 0:
                                transformed_data[code] = tr_series
                        elif 'value_raw' in df.columns:
                            # 如果没有转换值，使用原始值
                            raw_series = df['value_raw'].dropna()
                            if len(raw_series) > 0:
                                transformed_data[code] = raw_series
                    
                except Exception as e:
                    self.progress.emit(f"[WARN] 加载 {code} 失败: {e}")
                    continue
            
            if not transformed_data:
                raise Exception("没有找到可用的数据进行评分计算")
            
            self.progress.emit(f"找到 {len(transformed_data)} 个指标的数据")
            
            # 计算派生指标（如果需要）
            self.progress.emit("计算派生指标...")
            raw_data, transformed_data = pipeline.calculate_derived_indicators(
                raw_data,
                transformed_data
            )
            
            # **新增：检查今天的数据完整性**
            self.progress.emit("检查数据完整性...")
            from datetime import datetime
            today = datetime.now()
            completeness_report = pipeline.check_today_data_completeness(
                transformed_data,
                target_date=today
            )
            
            # 判断是否需要弹窗：只有当日数据缺失时才弹窗
            # 历史数据缺失自动使用最近有效数据
            need_user_confirmation = False
            
            if not completeness_report['all_complete']:
                # 检查缺失的是当日数据还是历史数据
                # 如果是今天（周一到周五的交易日），才需要用户确认
                is_today_trading_day = today.weekday() < 5  # 0-4是周一到周五
                
                if is_today_trading_day:
                    # 今天是交易日，检查是否有指标缺少今天的数据
                    for ind in completeness_report['missing_indicators']:
                        # 只要有指标的数据不是今天的（days_ago > 0），就需要用户确认
                        # 例如：今天24日，指标数据是20日，days_ago=4，应该提示用户
                        if ind['days_ago'] is not None and ind['days_ago'] > 0:
                            # 有指标缺少今天的数据，需要用户确认
                            need_user_confirmation = True
                            break
                
                if need_user_confirmation:
                    self.progress.emit("发现部分指标缺少当日数据，等待用户选择...")
                    
                    # 发送信号并等待用户选择
                    self._wait_for_user = True
                    self.completeness_check.emit(completeness_report, pipeline)
                    
                    # 等待用户选择（通过事件循环）
                    while self._wait_for_user:
                        self.msleep(100)  # 等待100ms
                    
                    # 检查用户选择
                    if self.user_choice == 'cancel':
                        self.progress.emit("用户取消了评分计算")
                        self.failed.emit("用户取消了评分计算")
                        return
                    elif self.user_choice == 'skip':
                        self.progress.emit("用户选择跳过当日评分，将计算历史数据但排除今天")
                        # 继续计算，但在后续步骤中排除今天的数据
                        # 设置标志，让后续逻辑知道要排除今天
                        self._skip_today = True
                    elif self.user_choice == 'use_latest':
                        self.progress.emit("用户选择使用最近数据，继续计算评分...")
                        # 继续执行，使用现有数据计算评分
                else:
                    # 历史数据缺失，自动使用最近有效数据
                    missing_count = len(completeness_report['missing_indicators'])
                    self.progress.emit(f"检测到 {missing_count} 个指标的历史数据有缺失，自动使用最近有效数据计算评分...")
            else:
                self.progress.emit("所有主指标数据完整，继续计算评分...")
            
            # 计算评分（日度）
            self.progress.emit("计算日度评分...")
            scores_daily, composite_daily = pipeline.calculate_scores(
                transformed_data,
                view_type='daily'
            )
            
            # **如果用户选择跳过今天，从评分结果中移除今天的数据**
            if self._skip_today:
                today = datetime.now().date()
                today_timestamp = pd.Timestamp(today)
                
                # 从scores_daily中移除今天的数据
                if today_timestamp in scores_daily.index:
                    scores_daily = scores_daily[scores_daily.index != today_timestamp]
                    self.progress.emit(f"已移除今天({today})的评分数据")
                
                # 从composite_daily中移除今天的数据
                if today_timestamp in composite_daily.index:
                    composite_daily = composite_daily[composite_daily.index != today_timestamp]
                    self.progress.emit(f"已移除今天({today})的综合评分")
            
            # 调试信息：检查评分数据
            self.progress.emit(f"评分DataFrame形状: {scores_daily.shape}")
            self.progress.emit(f"评分列数: {len(scores_daily.columns)}")
            
            # 检查是否有score列
            score_cols = [col for col in scores_daily.columns if '_score' in col]
            z_cols = [col for col in scores_daily.columns if '_z' in col]
            self.progress.emit(f"找到 {len(score_cols)} 个评分列, {len(z_cols)} 个Z分数列")
            
            # 检查评分列的数据
            if score_cols:
                first_score_col = score_cols[0]
                score_series = scores_daily[first_score_col]
                non_nan_count = score_series.notna().sum()
                self.progress.emit(f"样例评分列 {first_score_col}: {non_nan_count}/{len(score_series)} 个有效值")
                if non_nan_count > 0:
                    sample_scores = score_series.dropna().head(3)
                    self.progress.emit(f"样例评分值: {list(sample_scores.values)}")
            
            # 检查综合评分
            if len(composite_daily) > 0:
                non_nan_comp = composite_daily.notna().sum()
                self.progress.emit(f"综合评分: {non_nan_comp}/{len(composite_daily)} 个有效值")
                if non_nan_comp > 0:
                    self.progress.emit(f"综合评分范围: {composite_daily.min():.1f} - {composite_daily.max():.1f}")
                else:
                    self.progress.emit("警告：综合评分全部为NaN或0！")
            else:
                self.progress.emit("警告：综合评分为空！")
            
            # 应用确认层
            self.progress.emit("应用确认层...")
            confirm_results_daily = pipeline.apply_confirm_layer(
                scores_daily,
                view_type='daily'
            )
            
            # 保存到数据库
            self.progress.emit("保存日度数据到数据库...")
            saved_daily = pipeline.save_to_database(
                raw_data,
                transformed_data,
                scores_daily,
                confirm_results_daily,
                composite_daily,
                view_type='daily'
            )
            
            result = {
                'success': True,
                'market': self.market,
                'daily_records': saved_daily,
                'weekly_records': 0,
                'date_range': (
                    scores_daily.index.min() if len(scores_daily) > 0 else None,
                    scores_daily.index.max() if len(scores_daily) > 0 else None
                )
            }
            
            # 如果需要周度数据
            if self.view == 'weekly':
                self.progress.emit("计算周度评分...")
                scores_weekly, composite_weekly = pipeline.calculate_scores(
                    transformed_data,
                    view_type='weekly'
                )
                
                confirm_results_weekly = pipeline.apply_confirm_layer(
                    scores_weekly,
                    view_type='weekly'
                )
                
                self.progress.emit("保存周度数据到数据库...")
                saved_weekly = pipeline.save_to_database(
                    raw_data,
                    transformed_data,
                    scores_weekly,
                    confirm_results_weekly,
                    composite_weekly,
                    view_type='weekly'
                )
                
                result['weekly_records'] = saved_weekly
            
            self.progress.emit("计算完成！")
            self.completed.emit(result)
            
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n\n{traceback.format_exc()}"
            self.failed.emit(error_msg)


class MarketScoreTable(QWidget):
    """
    市场评分表格
    
    显示各个指标的当前评分、权重、方向等信息
    支持权重编辑
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # 标题和按钮
        title_layout = QHBoxLayout()
        
        title_label = QLabel("指标评分表")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #1F2933;")
        
        self.save_weights_btn = QPushButton("保存权重")
        self.save_weights_btn.setToolTip("保存修改的指标权重到配置")
        self.save_weights_btn.clicked.connect(self._on_save_weights)
        
        self.reset_weights_btn = QPushButton("重置为当前风格")
        self.reset_weights_btn.setToolTip("重置权重为当前选择的风格默认值")
        self.reset_weights_btn.clicked.connect(self._on_reset_weights)
        
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(self.reset_weights_btn)
        title_layout.addWidget(self.save_weights_btn)
        
        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(7)  # 添加数据日期列
        self.table.setHorizontalHeaderLabels([
            "指标代码", "指标名称", "数据日期", "当前值", "Z分数", "评分", "权重(%)"
        ])
        
        # 设置表格样式
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        # 布局
        layout = QVBoxLayout(self)
        layout.addLayout(title_layout)
        layout.addWidget(self.table)
        
        # 保存权重SpinBox的引用
        self.weight_spinboxes: Dict[str, QSpinBox] = {}
        
        # 保存配置、市场和风格的引用
        self._config = None
        self._market = None
        self._style = None
        self._indicator_codes = []
        self._original_weights = []
    
    def update_scores(
        self,
        indicator_data: List[Dict],
        weights: List[float],
        current_date: Optional[date] = None,
        market: str = None,
        style: str = None,
        config: Config = None
    ) -> None:
        """
        更新评分表格
        
        @param {List[Dict]} indicator_data - 指标数据列表，每个字典包含code, name, data_date, value, z, score
        @param {List[float]} weights - 权重列表
        @param {Optional[date]} current_date - 当前日期（弃用，改用data_date）
        @param {str} market - 市场代码
        @param {str} style - 风格
        @param {Config} config - 配置对象
        """
        self._config = config
        self._market = market
        self._style = style
        self._indicator_codes = [ind.get('code') for ind in indicator_data]
        self._original_weights = weights.copy()
        self.weight_spinboxes.clear()
        
        self.table.setRowCount(len(indicator_data))
        
        for row, (ind_data, weight) in enumerate(zip(indicator_data, weights)):
            # 指标代码
            code = ind_data.get('code', '')
            code_item = QTableWidgetItem(code)
            code_item.setFlags(code_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, code_item)
            
            # 指标名称
            name_item = QTableWidgetItem(ind_data.get('name', ''))
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, name_item)
            
            # 数据日期
            data_date = ind_data.get('data_date', None)
            if data_date:
                # 如果是pandas Timestamp或datetime，格式化为字符串
                if hasattr(data_date, 'strftime'):
                    date_str = data_date.strftime('%Y-%m-%d')
                else:
                    date_str = str(data_date)
            else:
                date_str = "-"
            date_item = QTableWidgetItem(date_str)
            date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 2, date_item)
            
            # 当前值
            value = ind_data.get('value', None)
            value_str = f"{value:.2f}" if value is not None and not pd.isna(value) else "-"
            value_item = QTableWidgetItem(value_str)
            value_item.setFlags(value_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 3, value_item)
            
            # Z分数
            z_score = ind_data.get('z', None)
            z_str = f"{z_score:.2f}" if z_score is not None and not pd.isna(z_score) else "-"
            z_item = QTableWidgetItem(z_str)
            z_item.setFlags(z_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 4, z_item)
            
            # 评分（移除颜色背景）
            score = ind_data.get('score', None)
            score_str = f"{score:.1f}" if score is not None and not pd.isna(score) else "-"
            score_item = QTableWidgetItem(score_str)
            score_item.setFlags(score_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 5, score_item)
            
            # 权重 - 使用SpinBox可编辑
            spinbox = QSpinBox()
            spinbox.setRange(0, 100)
            spinbox.setValue(int(weight))
            spinbox.setSuffix("%")
            spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            self.table.setCellWidget(row, 6, spinbox)
            self.weight_spinboxes[code] = spinbox
    
    def _on_save_weights(self) -> None:
        """保存权重按钮点击事件"""
        if not self._config or not self._market or not self._style:
            QMessageBox.warning(self, "错误", "无法保存：缺少配置信息")
            return
        
        # 收集当前的权重
        new_weights = []
        total_weight = 0
        
        for code in self._indicator_codes:
            spinbox = self.weight_spinboxes.get(code)
            if spinbox:
                weight = spinbox.value()
                new_weights.append(weight)
                total_weight += weight
        
        # 验证权重总和
        if total_weight != 100:
            reply = QMessageBox.question(
                self,
                "权重总和不为100",
                f"当前权重总和为 {total_weight}%，不等于100%。\n\n"
                f"是否归一化权重到100%？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # 归一化
                normalized_weights = [int(w * 100 / total_weight) for w in new_weights]
                
                # 处理舍入误差：调整最大权重确保总和为100
                current_sum = sum(normalized_weights)
                if current_sum != 100:
                    max_idx = normalized_weights.index(max(normalized_weights))
                    normalized_weights[max_idx] += (100 - current_sum)
                
                new_weights = normalized_weights
                
                # 更新显示
                for code, weight in zip(self._indicator_codes, new_weights):
                    spinbox = self.weight_spinboxes.get(code)
                    if spinbox:
                        spinbox.blockSignals(True)
                        spinbox.setValue(weight)
                        spinbox.blockSignals(False)
                
                total_weight = 100
            else:
                return
        
        # 保存到配置
        try:
            config_key = f"style_weights.{self._market}.{self._style}"
            self._config.set(config_key, new_weights)
            
            # 确保配置目录存在
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._config.save_to_json(str(CONFIG_FILE))
            
            QMessageBox.information(
                self,
                "保存成功",
                f"{self._market}市场 {self._style}风格的权重已更新。\n\n"
                f"权重总和: {total_weight}%\n\n"
                f"提示：权重修改后，建议点击'计算评分'按钮重新计算评分数据。"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "保存失败",
                f"保存权重失败：\n\n{str(e)}"
            )
    
    def _on_reset_weights(self) -> None:
        """重置权重为当前风格的默认值"""
        if not self._original_weights:
            return
        
        reply = QMessageBox.question(
            self,
            "确认重置",
            f"确定要重置为 {self._style} 风格的默认权重吗？\n\n"
            f"当前修改将被丢弃。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 恢复原始权重
            for code, weight in zip(self._indicator_codes, self._original_weights):
                spinbox = self.weight_spinboxes.get(code)
                if spinbox:
                    spinbox.blockSignals(True)
                    spinbox.setValue(int(weight))
                    spinbox.blockSignals(False)
    
    # 移除_get_lamp_from_score方法，主要指标不显示灯色


class CompositeScoreChart(QWidget):
    """
    综合评分曲线图
    
    显示市场综合评分的时间序列以及regime分区
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # 设置焦点策略以接收键盘事件
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        
        # 保存配置引用和当前市场
        self._config = None
        self._current_market = None
        
        # 标题和控件
        self.title_label = QLabel("市场综合评分")
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #1F2933;")
        
        # 阈值调整控件
        self.attack_spinbox = QSpinBox()
        self.attack_spinbox.setRange(50, 100)
        self.attack_spinbox.setValue(70)
        self.attack_spinbox.setPrefix("Attack: ")
        self.attack_spinbox.setSuffix(" 分")
        self.attack_spinbox.setToolTip("Attack阈值（绿色线）")
        self.attack_spinbox.valueChanged.connect(self._on_attack_threshold_changed)
        
        self.defense_spinbox = QSpinBox()
        self.defense_spinbox.setRange(0, 50)
        self.defense_spinbox.setValue(40)
        self.defense_spinbox.setPrefix("Defense: ")
        self.defense_spinbox.setSuffix(" 分")
        self.defense_spinbox.setToolTip("Defense阈值（红色线）")
        self.defense_spinbox.valueChanged.connect(self._on_defense_threshold_changed)
        
        # 阈值重置按钮
        self.reset_thresholds_btn = QPushButton("重置阈值")
        self.reset_thresholds_btn.setToolTip("重置为默认阈值(70/40)")
        self.reset_thresholds_btn.clicked.connect(self._on_reset_thresholds)
        
        self.export_btn = QPushButton("导出图表")
        self.export_btn.clicked.connect(self._export_chart)
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(QLabel("阈值设置:"))
        header_layout.addWidget(self.attack_spinbox)
        header_layout.addWidget(self.defense_spinbox)
        header_layout.addWidget(self.reset_thresholds_btn)
        header_layout.addWidget(self.export_btn)
        
        # 图表 - 简化版
        pg.setConfigOptions(antialias=True, background="w", foreground="#1F2933")
        self.graphics = pg.GraphicsLayoutWidget()
        
        # 设置图表的大小策略，防止其影响父窗口大小
        from PyQt6.QtWidgets import QSizePolicy
        self.graphics.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # 使用DateAxisItem作为X轴
        date_axis = pg.DateAxisItem(orientation='bottom')
        self.plot = self.graphics.addPlot(row=0, col=0, axisItems={'bottom': date_axis})
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.plot.setLabel('left', '评分', color='#1F2933', **{'font-size': '10pt'})
        self.plot.setLabel('bottom', '日期', color='#1F2933', **{'font-size': '10pt'})
        
        # 添加阈值线（更细、更浅）
        self.attack_line = pg.InfiniteLine(
            angle=0, pos=70, 
            pen=pg.mkPen('#4CAF50', width=1, style=Qt.PenStyle.DashLine),
            label='Attack (70)', labelOpts={'color': '#4CAF50'}
        )
        self.defense_line = pg.InfiniteLine(
            angle=0, pos=40,
            pen=pg.mkPen('#F44336', width=1, style=Qt.PenStyle.DashLine),
            label='Defense (40)', labelOpts={'color': '#F44336'}
        )
        self.plot.addItem(self.attack_line)
        self.plot.addItem(self.defense_line)
        
        # 简化的评分曲线 - 只有线，没有点
        self.score_curve = self.plot.plot(
            pen=pg.mkPen('#2196F3', width=2),
            name='综合评分'
        )
        
        # 添加十字准线（更细）
        self.vLine = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen('#999999', width=0.5, style=Qt.PenStyle.DashLine))
        self.hLine = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen('#999999', width=0.5, style=Qt.PenStyle.DashLine))
        self.plot.addItem(self.vLine, ignoreBounds=True)
        self.plot.addItem(self.hLine, ignoreBounds=True)
        
        # 创建文本标签用于显示鼠标位置的数值（固定在顶部）
        self.value_label = QLabel("")
        self.value_label.setStyleSheet(
            "QLabel { "
            "background-color: rgba(255, 255, 255, 220); "
            "border: 1px solid #999999; "
            "border-radius: 3px; "
            "padding: 5px 10px; "
            "font-size: 11pt; "
            "color: #1F2933; "
            "}"
        )
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setVisible(False)
        
        # 连接鼠标移动事件
        self.plot.scene().sigMouseMoved.connect(self._on_mouse_moved)
        
        # 隐藏十字线（初始状态）
        self.vLine.setVisible(False)
        self.hLine.setVisible(False)
        
        # 当前选中的数据点索引（用于键盘导航）
        self._current_index = None
        self._timestamps = None
        self._values = None
        
        # 信息标签
        self.info_label = QLabel("选择日期范围以加载数据")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: #5B6470;")
        
        # 设置整个图表控件的大小策略
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        # 布局
        layout = QVBoxLayout(self)
        layout.addLayout(header_layout)
        layout.addWidget(self.value_label)  # 数值显示在图表上方
        layout.addWidget(self.graphics, stretch=1)
        layout.addWidget(self.info_label)
        
        self._data = None
        self._current_mode = 'composite'  # 'composite' 或 'indicator'
        self._current_indicator = None
    
    def update_chart(
        self,
        composite_scores: pd.Series,
        market: str,
        view: str,
        config: Optional[Config] = None
    ) -> None:
        """
        更新图表
        
        @param {pd.Series} composite_scores - 综合评分序列
        @param {str} market - 市场代码
        @param {str} view - 视图类型
        @param {Config} config - 配置对象
        """
        if composite_scores is None or len(composite_scores) == 0:
            self.score_curve.clear()
            self.info_label.setText("无可用数据")
            return
        
        # 保存配置和市场
        self._config = config
        self._current_market = market
        
        # 从配置加载阈值（使用下划线格式）
        if config:
            # 先尝试市场特定配置
            attack_threshold = config.get(f'regime.attack_threshold_{market}')
            # 如果为None，使用全局默认
            if attack_threshold is None:
                attack_threshold = config.get('regime.attack_threshold', 70)
            
            defense_threshold = config.get(f'regime.defense_threshold_{market}')
            if defense_threshold is None:
                defense_threshold = config.get('regime.defense_threshold', 40)
        else:
            attack_threshold = 70
            defense_threshold = 40
        
        # 确保值是整数且在合理范围内
        attack_threshold = int(attack_threshold) if attack_threshold is not None else 70
        defense_threshold = int(defense_threshold) if defense_threshold is not None else 40
        
        # 更新SpinBox值（不触发信号）
        self.attack_spinbox.blockSignals(True)
        self.defense_spinbox.blockSignals(True)
        self.attack_spinbox.setValue(attack_threshold)
        self.defense_spinbox.setValue(defense_threshold)
        self.attack_spinbox.blockSignals(False)
        self.defense_spinbox.blockSignals(False)
        
        # 更新阈值线位置
        self.attack_line.setPos(attack_threshold)
        self.defense_line.setPos(defense_threshold)
        self.attack_line.label.setText(f'Attack ({attack_threshold})')
        self.defense_line.label.setText(f'Defense ({defense_threshold})')
        
        # 只显示最近一年的数据（性能优化）
        from datetime import datetime, timedelta
        one_year_ago = datetime.now() - timedelta(days=365)
        
        # 过滤数据
        mask = composite_scores.index >= pd.Timestamp(one_year_ago)
        filtered_scores = composite_scores[mask]
        
        if len(filtered_scores) == 0:
            # 如果最近一年没有数据，使用全部数据
            filtered_scores = composite_scores
        
        # 移除NaN和0值（0分和NaN都是无效评分）
        # 使用forward fill后，有效评分应该>0
        valid_scores = filtered_scores[(filtered_scores.notna()) & (filtered_scores > 0)]
        
        if len(valid_scores) == 0:
            self.score_curve.clear()
            self.info_label.setText("暂无有效评分数据")
            return
        
        self._data = valid_scores.copy()
        
        # 转换为时间戳
        timestamps = (pd.to_datetime(valid_scores.index).view('int64') / 1e9).astype(float)
        values = valid_scores.values.astype(float)
        
        # 保存用于键盘导航
        self._timestamps = timestamps
        self._values = values
        self._current_index = None
        
        # 更新曲线（简化，不显示点）
        self.score_curve.setData(timestamps, values)
        
        # 更新信息
        start_date = valid_scores.index[0]
        end_date = valid_scores.index[-1]
        latest_score = valid_scores.iloc[-1]
        
        total_points = len(filtered_scores)
        valid_points = len(valid_scores)
        
        self.info_label.setText(
            f"{market} 市场 · {view} · "
            f"{start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')} · "
            f"最新评分: {latest_score:.1f} · "
            f"有效数据点: {valid_points}/{total_points}"
        )
        
        # 记录当前模式
        self._current_mode = 'composite'
        self._current_indicator = None
        self.title_label.setText("市场综合评分（最近1年）")
    
    def update_indicator_chart(
        self,
        indicator_code: str,
        indicator_name: str,
        score_series: pd.Series,
        market: str,
        view: str
    ) -> None:
        """
        更新为单个指标的评分曲线
        
        @param {str} indicator_code - 指标代码
        @param {str} indicator_name - 指标名称
        @param {pd.Series} score_series - 评分序列
        @param {str} market - 市场代码
        @param {str} view - 视图类型
        """
        if score_series is None or len(score_series) == 0:
            self.score_curve.clear()
            self.info_label.setText(f"{indicator_name}: 无可用评分数据")
            return
        
        # 只显示最近一年的数据（性能优化）
        from datetime import datetime, timedelta
        one_year_ago = datetime.now() - timedelta(days=365)
        
        # 过滤数据
        mask = score_series.index >= pd.Timestamp(one_year_ago)
        filtered_scores = score_series[mask]
        
        if len(filtered_scores) == 0:
            # 如果最近一年没有数据，使用全部数据
            filtered_scores = score_series
        
        # 移除NaN值和0值（0分和NaN都是无效评分）
        valid_scores = filtered_scores[(filtered_scores.notna()) & (filtered_scores > 0)]
        
        if len(valid_scores) == 0:
            self.score_curve.clear()
            self.info_label.setText(f"{indicator_name}: 暂无有效评分数据")
            return
        
        self._data = valid_scores.copy()
        
        # 转换为时间戳
        timestamps = (pd.to_datetime(valid_scores.index).view('int64') / 1e9).astype(float)
        values = valid_scores.values.astype(float)
        
        # 保存用于键盘导航
        self._timestamps = timestamps
        self._values = values
        self._current_index = None
        
        # 更新曲线
        self.score_curve.setData(timestamps, values)
        
        # 更新标题和信息
        self.title_label.setText(f"指标评分: {indicator_name}（最近1年）")
        
        start_date = valid_scores.index[0]
        end_date = valid_scores.index[-1]
        
        # 计算有效评分数量
        total_count = len(filtered_scores)
        valid_count = len(valid_scores)
        latest_score = valid_scores.iloc[-1] if len(valid_scores) > 0 else None
        
        info_text = (
            f"{market} 市场 · {view} · {indicator_code} · "
            f"{start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')} · "
            f"有效数据: {valid_count}/{total_count}"
        )
        
        if latest_score is not None:
            info_text += f" · 最新评分: {latest_score:.1f}"
        
        self.info_label.setText(info_text)
        
        # 记录当前模式
        self._current_mode = 'indicator'
        self._current_indicator = indicator_code
    
    def clear(self) -> None:
        """清空图表"""
        self.score_curve.clear()
        self.info_label.setText("选择日期范围以加载数据")
        self._data = None
        self._timestamps = None
        self._values = None
        self._current_index = None
        self.vLine.setVisible(False)
        self.hLine.setVisible(False)
        self.value_label.setVisible(False)
    
    def _on_mouse_moved(self, pos) -> None:
        """鼠标移动事件处理 - 显示十字准线和数值"""
        if self._data is None or len(self._data) == 0:
            return
        
        if self._timestamps is None or self._values is None:
            return
        
        # 检查鼠标是否在绘图区域内
        if self.plot.sceneBoundingRect().contains(pos):
            # 将场景坐标转换为数据坐标
            mouse_point = self.plot.vb.mapSceneToView(pos)
            x_value = mouse_point.x()  # 时间戳
            
            # 找到最接近的数据点
            idx = (np.abs(self._timestamps - x_value)).argmin()
            
            if idx < len(self._data):
                self._current_index = idx
                self._update_crosshair_display(idx)
        else:
            # 鼠标离开绘图区域，隐藏十字线
            self.vLine.setVisible(False)
            self.hLine.setVisible(False)
            self.value_label.setVisible(False)
    
    def _update_crosshair_display(self, idx: int) -> None:
        """更新十字准线和数值显示"""
        if idx < 0 or idx >= len(self._data):
            return
        
        actual_date = self._data.index[idx]
        actual_score = self._data.iloc[idx]
        actual_timestamp = self._timestamps[idx]
        
        # 更新十字准线位置
        self.vLine.setPos(actual_timestamp)
        self.hLine.setPos(actual_score)
        self.vLine.setVisible(True)
        self.hLine.setVisible(True)
        
        # 更新标签内容（显示在图表上方）
        date_str = actual_date.strftime('%Y-%m-%d') if hasattr(actual_date, 'strftime') else str(actual_date)
        
        # 获取星期
        weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        weekday = weekday_names[actual_date.weekday()] if hasattr(actual_date, 'weekday') else ''
        
        label_text = f"日期: {date_str} {weekday}  |  评分: {actual_score:.2f}  |  位置: {idx+1}/{len(self._data)}"
        
        self.value_label.setText(label_text)
        self.value_label.setVisible(True)
    
    def keyPressEvent(self, event) -> None:
        """键盘事件处理 - 支持左右箭头键导航"""
        from PyQt6.QtCore import Qt
        
        if self._current_index is None or self._data is None:
            super().keyPressEvent(event)
            return
        
        if event.key() == Qt.Key.Key_Left:
            # 左箭头 - 上一个数据点
            if self._current_index > 0:
                self._current_index -= 1
                self._update_crosshair_display(self._current_index)
                event.accept()
        elif event.key() == Qt.Key.Key_Right:
            # 右箭头 - 下一个数据点
            if self._current_index < len(self._data) - 1:
                self._current_index += 1
                self._update_crosshair_display(self._current_index)
                event.accept()
        else:
            super().keyPressEvent(event)
    
    def focusInEvent(self, event) -> None:
        """获得焦点时的处理"""
        super().focusInEvent(event)
        # 确保组件可以接收键盘事件
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    
    def _export_chart(self) -> None:
        """导出图表"""
        from PyQt6.QtWidgets import QFileDialog
        from datetime import datetime
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出综合评分图表",
            f"composite_score_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png",
            "PNG 图片 (*.png)"
        )
        
        if file_path:
            exporter = pg.exporters.ImageExporter(self.plot)
            exporter.export(file_path)
    
    def _on_attack_threshold_changed(self, value: int) -> None:
        """Attack阈值改变事件"""
        self.attack_line.setPos(value)
        self.attack_line.label.setText(f'Attack ({value})')
        
        # 验证合理性
        defense_value = self.defense_spinbox.value()
        if value <= defense_value:
            # 不保存，提示用户
            QMessageBox.warning(
                self,
                "阈值设置错误",
                f"Attack阈值({value})必须大于Defense阈值({defense_value})。\n\n"
                f"请调整后配置才会生效。"
            )
            return
        
        # 保存到配置（自动保存）
        if self._config and self._current_market:
            # 使用下划线格式: attack_threshold_CN 而不是 attack_threshold.CN
            config_key = f'regime.attack_threshold_{self._current_market}'
            self._config.set(config_key, value)
            try:
                # 确保配置目录存在
                CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
                self._config.save_to_json(str(CONFIG_FILE))
                # 静默保存，不弹窗（避免打扰）
                print(f"[INFO] {self._current_market}市场Attack阈值已保存: {value}")
            except Exception as e:
                print(f"[WARN] 保存Attack阈值失败: {e}")
    
    def _on_defense_threshold_changed(self, value: int) -> None:
        """Defense阈值改变事件"""
        self.defense_line.setPos(value)
        self.defense_line.label.setText(f'Defense ({value})')
        
        # 验证合理性
        attack_value = self.attack_spinbox.value()
        if value >= attack_value:
            # 不保存，提示用户
            QMessageBox.warning(
                self,
                "阈值设置错误",
                f"Defense阈值({value})必须小于Attack阈值({attack_value})。\n\n"
                f"请调整后配置才会生效。"
            )
            return
        
        # 保存到配置（自动保存）
        if self._config and self._current_market:
            # 使用下划线格式: defense_threshold_CN 而不是 defense_threshold.CN
            config_key = f'regime.defense_threshold_{self._current_market}'
            self._config.set(config_key, value)
            try:
                # 确保配置目录存在
                CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
                self._config.save_to_json(str(CONFIG_FILE))
                # 静默保存，不弹窗
                print(f"[INFO] {self._current_market}市场Defense阈值已保存: {value}")
            except Exception as e:
                print(f"[WARN] 保存Defense阈值失败: {e}")
    
    def _on_reset_thresholds(self) -> None:
        """重置阈值为默认值"""
        reply = QMessageBox.question(
            self,
            "确认重置阈值",
            f"确定要重置{self._current_market or '当前市场'}的阈值为默认值吗？\n\n"
            f"默认Attack: 70分\n"
            f"默认Defense: 40分\n\n"
            f"当前设置将被覆盖。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # 重置为默认值
            self.attack_spinbox.blockSignals(True)
            self.defense_spinbox.blockSignals(True)
            self.attack_spinbox.setValue(70)
            self.defense_spinbox.setValue(40)
            self.attack_spinbox.blockSignals(False)
            self.defense_spinbox.blockSignals(False)
            
            # 更新阈值线
            self.attack_line.setPos(70)
            self.defense_line.setPos(40)
            self.attack_line.label.setText('Attack (70)')
            self.defense_line.label.setText('Defense (40)')
            
            # 从配置中删除市场特定设置
            if self._config and self._current_market:
                # 使用下划线格式
                attack_key = f'regime.attack_threshold_{self._current_market}'
                defense_key = f'regime.defense_threshold_{self._current_market}'
                
                # 设置为None（get会忽略并返回默认值）
                try:
                    self._config.set(attack_key, None)
                    self._config.set(defense_key, None)
                except:
                    pass
                
                try:
                    # 确保配置目录存在
                    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
                    self._config.save_to_json(str(CONFIG_FILE))
                    QMessageBox.information(
                        self,
                        "重置成功",
                        f"{self._current_market}市场的阈值已重置为默认值(70/40)。"
                    )
                except Exception as e:
                    QMessageBox.critical(self, "保存失败", f"保存配置失败：\n\n{str(e)}")


class ConfirmLayerPanel(QWidget):
    """
    确认层面板
    
    显示Hard Veto、Soft Confirm和Final Lamp的状态
    支持Soft Confirm权重的查看和编辑
    """
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        # 标题
        title_label = QLabel("确认层状态")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #1F2933;")
        
        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels([
            "观察者", "角色", "当前灯色", "Soft权重(%)"
        ])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setAlternatingRowColors(True)
        
        # 保存权重SpinBox的引用
        self.weight_spinboxes: Dict[str, QDoubleSpinBox] = {}
        
        # 汇总信息
        self.summary_frame = QFrame()
        self.summary_frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        summary_layout = QHBoxLayout(self.summary_frame)
        
        self.hard_label = QLabel("Hard Veto: -")
        self.soft_label = QLabel("Soft Confirm: -")
        self.final_label = QLabel("Final Lamp: -")
        
        # 添加保存权重按钮
        self.save_weights_btn = QPushButton("保存权重")
        self.save_weights_btn.setToolTip("保存修改的Soft Confirm权重到配置")
        self.save_weights_btn.clicked.connect(self._on_save_weights)
        
        summary_layout.addWidget(self.hard_label)
        summary_layout.addWidget(self.soft_label)
        summary_layout.addWidget(self.final_label)
        summary_layout.addStretch()
        summary_layout.addWidget(self.save_weights_btn)
        
        # 布局
        layout = QVBoxLayout(self)
        layout.addWidget(title_label)
        layout.addWidget(self.summary_frame)
        layout.addWidget(self.table, stretch=1)
        
        # 保存当前市场和配置的引用
        self._current_market = None
        self._config = None
    
    def update_confirm_layer(
        self,
        observer_data: List[Dict],
        hard_veto_lamp: str,
        soft_confirm_lamp: str,
        final_lamp: str,
        soft_weights: Dict[str, float],
        market: str,
        config: Config
    ) -> None:
        """
        更新确认层状态
        
        @param {List[Dict]} observer_data - 观察者数据列表
        @param {str} hard_veto_lamp - 硬否决灯色
        @param {str} soft_confirm_lamp - 软确认灯色
        @param {str} final_lamp - 最终灯色
        @param {Dict[str, float]} soft_weights - 软确认权重
        @param {str} market - 市场代码
        @param {Config} config - 配置对象
        """
        self._current_market = market
        self._config = config
        self.weight_spinboxes.clear()
        
        self.table.setRowCount(len(observer_data))
        
        for row, obs_data in enumerate(observer_data):
            # 观察者代码
            code = obs_data.get('code', '')
            code_item = QTableWidgetItem(code)
            code_item.setFlags(code_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, code_item)
            
            # 角色
            role = obs_data.get('role', '')
            role_display = "硬否决" if role == "hard" else "软确认" if role == "soft" else "配对"
            role_item = QTableWidgetItem(role_display)
            role_item.setFlags(role_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 1, role_item)
            
            # 当前灯色
            lamp = obs_data.get('lamp', '-')
            lamp_display = self._lamp_to_chinese(lamp)
            lamp_item = QTableWidgetItem(lamp_display)
            lamp_item.setFlags(lamp_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            
            if lamp == 'G':
                lamp_item.setBackground(Qt.GlobalColor.green)
            elif lamp == 'R':
                lamp_item.setBackground(Qt.GlobalColor.red)
            else:
                lamp_item.setBackground(Qt.GlobalColor.yellow)
            
            self.table.setItem(row, 2, lamp_item)
            
            # Soft Confirm权重 - 使用SpinBox可编辑
            weight = soft_weights.get(code, 0.0)
            
            if role == "soft" or role == "pair":  # 只有soft和pair角色有权重
                spinbox = QDoubleSpinBox()
                spinbox.setRange(0.0, 100.0)
                spinbox.setValue(weight * 100)  # 转换为百分比
                spinbox.setSuffix("%")
                spinbox.setDecimals(1)
                spinbox.setSingleStep(1.0)
                spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
                
                self.table.setCellWidget(row, 3, spinbox)
                self.weight_spinboxes[code] = spinbox
            else:
                # hard角色没有权重
                weight_item = QTableWidgetItem("-")
                weight_item.setFlags(weight_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 3, weight_item)
        
        # 更新汇总信息
        self.hard_label.setText(f"Hard Veto: {self._lamp_to_chinese(hard_veto_lamp)}")
        self.soft_label.setText(f"Soft Confirm: {self._lamp_to_chinese(soft_confirm_lamp)}")
        self.final_label.setText(f"Final Lamp: {self._lamp_to_chinese(final_lamp)}")
        
        # 设置汇总标签颜色
        self._set_label_color(self.hard_label, hard_veto_lamp)
        self._set_label_color(self.soft_label, soft_confirm_lamp)
        self._set_label_color(self.final_label, final_lamp)
    
    def _on_save_weights(self) -> None:
        """保存权重按钮点击事件"""
        if not self._current_market or not self._config:
            QMessageBox.warning(self, "错误", "无法保存：缺少市场或配置信息")
            return
        
        # 收集当前的权重
        new_weights = {}
        total_weight = 0.0
        
        for code, spinbox in self.weight_spinboxes.items():
            weight = spinbox.value() / 100.0  # 转换回小数
            new_weights[code] = weight
            total_weight += weight
        
        # 验证权重总和
        if abs(total_weight - 1.0) > 0.01:  # 允许1%的误差
            reply = QMessageBox.question(
                self,
                "权重总和不为1",
                f"当前权重总和为 {total_weight*100:.1f}%，不等于100%。\n\n是否归一化权重？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # 归一化
                for code in new_weights:
                    new_weights[code] /= total_weight
                
                # 更新显示
                for code, spinbox in self.weight_spinboxes.items():
                    spinbox.setValue(new_weights[code] * 100)
            else:
                return
        
        # 保存到配置
        try:
            config_key = f"soft_confirm_weights.{self._current_market}"
            self._config.set(config_key, new_weights)
            
            # 确保配置目录存在
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._config.save_to_json(str(CONFIG_FILE))
            
            QMessageBox.information(
                self,
                "保存成功",
                f"{self._current_market}市场的Soft Confirm权重已更新。\n\n"
                f"权重总和: {sum(new_weights.values())*100:.1f}%\n\n"
                f"请点击'计算评分'按钮重新计算以应用新权重。"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "保存失败",
                f"保存权重失败：\n\n{str(e)}"
            )
    
    @staticmethod
    def _lamp_to_chinese(lamp: str) -> str:
        """将灯色代码转换为中文"""
        mapping = {
            'G': '绿灯',
            'Y': '黄灯',
            'R': '红灯'
        }
        return mapping.get(lamp, '-')
    
    @staticmethod
    def _set_label_color(label: QLabel, lamp: str) -> None:
        """设置标签颜色"""
        if lamp == 'G':
            label.setStyleSheet("font-weight: bold; color: green;")
        elif lamp == 'R':
            label.setStyleSheet("font-weight: bold; color: red;")
        else:
            label.setStyleSheet("font-weight: bold; color: orange;")


class MarketOverviewWidget(QWidget):
    """
    市场概览主组件
    
    集成评分表格、综合评分图表和确认层面板
    """
    
    def __init__(
        self,
        database_url: str,
        config: Optional[Config] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        
        self.repository = Repository(database_url)
        self.config = config or Config()
        self.database_url = database_url
        
        # 计算线程
        self._calc_worker = None
        self._progress_dialog = None
        
        # 控制面板
        control_layout = QHBoxLayout()
        
        self.market_combo = QComboBox()
        self.market_combo.addItems(["CN", "US"])
        self.market_combo.currentTextChanged.connect(self._on_market_changed)
        
        self.view_combo = QComboBox()
        self.view_combo.addItems(["daily", "weekly"])
        self.view_combo.currentTextChanged.connect(self._on_view_changed)
        
        self.style_combo = QComboBox()
        self.style_combo.addItems(["Attack", "Balanced", "Defense"])
        self.style_combo.currentTextChanged.connect(self._on_style_changed)
        
        self.calc_score_btn = QPushButton("计算评分")
        self.calc_score_btn.clicked.connect(self._on_calculate_scores)
        self.calc_score_btn.setToolTip("根据当前权重设置重新计算所有历史评分数据")
        
        self.refresh_btn = QPushButton("刷新显示")
        self.refresh_btn.clicked.connect(self.refresh_data)
        
        self.show_composite_btn = QPushButton("显示综合评分")
        self.show_composite_btn.clicked.connect(self._on_show_composite)
        self.show_composite_btn.setToolTip("返回综合评分曲线视图")
        
        control_layout.addWidget(QLabel("市场:"))
        control_layout.addWidget(self.market_combo)
        control_layout.addWidget(QLabel("视图:"))
        control_layout.addWidget(self.view_combo)
        control_layout.addWidget(QLabel("风格:"))
        control_layout.addWidget(self.style_combo)
        control_layout.addStretch()
        control_layout.addWidget(self.show_composite_btn)
        control_layout.addWidget(self.calc_score_btn)
        control_layout.addWidget(self.refresh_btn)
        
        # 主要组件
        self.score_table = MarketScoreTable()
        self.composite_chart = CompositeScoreChart()
        self.confirm_panel = ConfirmLayerPanel()
        
        # 连接表格点击事件
        self.score_table.table.cellClicked.connect(self._on_table_cell_clicked)
        
        # 使用分割器
        top_splitter = QSplitter(Qt.Orientation.Horizontal)
        top_splitter.addWidget(self.score_table)
        top_splitter.addWidget(self.composite_chart)
        top_splitter.setStretchFactor(0, 1)
        top_splitter.setStretchFactor(1, 2)
        
        main_splitter = QSplitter(Qt.Orientation.Vertical)
        main_splitter.addWidget(top_splitter)
        main_splitter.addWidget(self.confirm_panel)
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 1)
        
        # 主布局
        layout = QVBoxLayout(self)
        layout.addLayout(control_layout)
        layout.addWidget(main_splitter, stretch=1)
        
        # 初始加载（使用try-except防止数据库为空时崩溃）
        try:
            self.refresh_data()
        except Exception as e:
            print(f"[WARN] 初始数据加载失败: {e}")
            # 显示友好提示
            self.composite_chart.info_label.setText(
                "暂无数据。请点击主窗口的'手动获取最新数据'按钮更新数据。"
            )
    
    def _on_market_changed(self, market: str) -> None:
        """市场切换事件"""
        # 更新风格选项
        active_style = self.config.get(f"active_style.{market}", "Balanced")
        self.style_combo.setCurrentText(active_style)
        self.refresh_data()
    
    def _on_view_changed(self, view: str) -> None:
        """视图切换事件"""
        self.refresh_data()
    
    def _on_style_changed(self, style: str) -> None:
        """风格切换事件"""
        market = self.market_combo.currentText()
        self.config.set_active_style(market, style)
        self.refresh_data()
    
    def _on_table_cell_clicked(self, row: int, column: int) -> None:
        """表格单元格点击事件 - 显示对应指标的评分曲线"""
        try:
            # 获取点击行的指标代码（第0列）
            code_item = self.score_table.table.item(row, 0)
            if not code_item:
                return
            
            indicator_code = code_item.text()
            
            # 获取指标名称（第1列）
            name_item = self.score_table.table.item(row, 1)
            indicator_name = name_item.text() if name_item else indicator_code
            
            # 获取当前市场和视图
            market = self.market_combo.currentText()
            view = self.view_combo.currentText()
            
            # 从数据库加载该指标的评分历史
            df = self.repository.load_series_data_by_code(indicator_code, view=view)
            
            if df is not None and not df.empty and 'score' in df.columns:
                score_series = df['score'].dropna()
                
                if len(score_series) > 0:
                    # 更新图表为指标评分曲线
                    self.composite_chart.update_indicator_chart(
                        indicator_code=indicator_code,
                        indicator_name=indicator_name,
                        score_series=score_series,
                        market=market,
                        view=view
                    )
                else:
                    QMessageBox.information(
                        self,
                        "无评分数据",
                        f"指标 {indicator_name} ({indicator_code}) 暂无评分数据。"
                    )
            else:
                QMessageBox.information(
                    self,
                    "无数据",
                    f"未找到指标 {indicator_name} ({indicator_code}) 的数据。"
                )
        
        except Exception as e:
            QMessageBox.warning(
                self,
                "加载失败",
                f"加载指标评分数据失败: {str(e)}"
            )
    
    def _on_show_composite(self) -> None:
        """显示综合评分按钮点击事件"""
        # 重新加载综合评分视图
        market = self.market_combo.currentText()
        view = self.view_combo.currentText()
        
        try:
            regimes_df = self.repository.load_regimes(market=market, view=view)
            
            if regimes_df is not None and not regimes_df.empty:
                # 检查是否有 'date' 列，如果没有，可能已经是索引
                if 'date' in regimes_df.columns:
                    regimes_df = regimes_df.set_index('date')
                
                # 检查是否有 'composite_score' 列
                if 'composite_score' in regimes_df.columns:
                    composite_scores = regimes_df['composite_score']
                    composite_scores = composite_scores.dropna()
                    
                    if len(composite_scores) > 0:
                        self.composite_chart.update_chart(composite_scores, market, view, self.config)
                    else:
                        QMessageBox.information(
                            self,
                            "无数据",
                            "暂无综合评分数据。请点击'计算评分'按钮生成数据。"
                        )
                else:
                    QMessageBox.information(
                        self,
                        "无数据",
                        "数据库中没有composite_score字段。请运行最新的pipeline更新数据。"
                    )
            else:
                QMessageBox.information(
                    self,
                    "无数据",
                    f"暂无{market}市场的{view}数据。请先运行数据获取。"
                )
        except Exception as e:
            QMessageBox.warning(
                self,
                "加载失败",
                f"加载综合评分数据失败: {str(e)}"
            )
    
    def _on_calculate_scores(self) -> None:
        """计算评分按钮点击事件"""
        # 检查是否已有计算在进行
        if self._calc_worker and self._calc_worker.isRunning():
            QMessageBox.warning(
                self,
                "提示",
                "评分计算正在进行中，请稍候..."
            )
            return
        
        market = self.market_combo.currentText()
        view = self.view_combo.currentText()
        style = self.style_combo.currentText()
        
        # 确认对话框
        reply = QMessageBox.question(
            self,
            "确认计算评分",
            f"将根据当前配置重新计算 {market} 市场的评分数据：\n\n"
            f"市场: {market}\n"
            f"视图: {view}\n"
            f"风格: {style}\n\n"
            f"这将覆盖数据库中现有的评分数据。是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # 创建进度对话框
        self._progress_dialog = QProgressDialog(
            "正在计算评分...",
            "取消",
            0,
            0,  # 不确定进度
            self
        )
        self._progress_dialog.setWindowTitle("计算评分")
        self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.canceled.connect(self._on_calculation_canceled)
        
        # 禁用控件
        self.calc_score_btn.setEnabled(False)
        self.market_combo.setEnabled(False)
        self.view_combo.setEnabled(False)
        self.style_combo.setEnabled(False)
        
        # 创建并启动计算线程
        self._calc_worker = ScoreCalculationWorker(
            database_url=self.database_url,
            market=market,
            view=view,
            config=self.config,
            parent=self
        )
        
        self._calc_worker.completeness_check.connect(self._on_completeness_check)
        self._calc_worker.progress.connect(self._on_calculation_progress)
        self._calc_worker.completed.connect(self._on_calculation_completed)
        self._calc_worker.failed.connect(self._on_calculation_failed)
        self._calc_worker.finished.connect(self._on_calculation_finished)
        
        self._calc_worker.start()
    
    def _on_completeness_check(self, report: dict, pipeline: object) -> None:
        """
        处理数据完整性检查
        
        @param {dict} report - 完整性报告
        @param {object} pipeline - MarketPipeline实例（未使用，仅用于信号传递）
        """
        from ui.data_completeness_dialog import DataCompletenessDialog
        
        # **修复：完全关闭进度对话框，避免阻塞**
        if self._progress_dialog:
            self._progress_dialog.close()
            self._progress_dialog = None
        
        # 显示数据完整性对话框
        dialog = DataCompletenessDialog(
            completeness_report=report,
            market=self.market_combo.currentText(),
            parent=self
        )
        
        result = dialog.exec()
        user_choice = dialog.get_user_choice()
        
        # **修复：重新创建进度对话框**
        self._progress_dialog = QProgressDialog(
            "正在计算评分...",
            "取消",
            0,
            0,
            self
        )
        self._progress_dialog.setWindowTitle("计算评分")
        self._progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.canceled.connect(self._on_calculation_canceled)
        self._progress_dialog.show()
        
        # 将用户选择传递给Worker线程
        if self._calc_worker:
            if result == QDialog.DialogCode.Accepted:
                # 用户接受了
                if user_choice == 'use_latest':
                    self._calc_worker.set_user_choice('use_latest')
                elif user_choice == 'skip':
                    self._calc_worker.set_user_choice('skip')
                elif user_choice is None:
                    # 数据完整，直接继续
                    self._calc_worker.set_user_choice('use_latest')
            else:
                # 用户取消了
                self._calc_worker.set_user_choice('cancel')
    
    def _on_calculation_progress(self, message: str) -> None:
        """计算进度更新"""
        if self._progress_dialog:
            self._progress_dialog.setLabelText(message)
    
    def _on_calculation_completed(self, result: dict) -> None:
        """计算完成"""
        if self._progress_dialog:
            self._progress_dialog.close()
        
        # 检查是否是跳过的情况
        if result.get('skipped'):
            QMessageBox.information(
                self,
                "已跳过评分",
                f"{result['market']} 市场：\n\n"
                f"{result.get('message', '用户选择跳过当日评分')}\n\n"
                f"提示：请先获取最新数据，然后再重新计算评分。"
            )
            return
        
        # 正常完成的情况
        if not result.get('success'):
            # 失败但不是跳过
            QMessageBox.warning(
                self,
                "计算未完成",
                f"{result['market']} 市场评分计算未完成。\n\n"
                f"{result.get('message', '未知原因')}"
            )
            return
        
        # 显示成功结果
        date_range = result.get('date_range', (None, None))
        date_str = ""
        if date_range[0] and date_range[1]:
            date_str = f"\n日期范围: {date_range[0].strftime('%Y-%m-%d')} 至 {date_range[1].strftime('%Y-%m-%d')}"
        
        QMessageBox.information(
            self,
            "计算完成",
            f"{result['market']} 市场评分计算完成！\n\n"
            f"日度记录: {result['daily_records']} 条\n"
            f"周度记录: {result['weekly_records']} 条"
            f"{date_str}"
        )
        
        # 刷新显示
        self.refresh_data()
    
    def _on_calculation_failed(self, error_msg: str) -> None:
        """计算失败"""
        if self._progress_dialog:
            self._progress_dialog.close()
        
        QMessageBox.critical(
            self,
            "计算失败",
            f"评分计算失败：\n\n{error_msg}"
        )
    
    def _on_calculation_finished(self) -> None:
        """计算线程结束（无论成功或失败）"""
        # 恢复控件
        self.calc_score_btn.setEnabled(True)
        self.market_combo.setEnabled(True)
        self.view_combo.setEnabled(True)
        self.style_combo.setEnabled(True)
        
        self._calc_worker = None
    
    def _on_calculation_canceled(self) -> None:
        """用户取消计算"""
        if self._calc_worker and self._calc_worker.isRunning():
            reply = QMessageBox.question(
                self,
                "确认取消",
                "确定要取消评分计算吗？\n\n已计算的数据将被保存。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # 先通知Worker取消
                self._calc_worker.set_user_choice('cancel')
                # 等待线程结束
                self._calc_worker.terminate()
                self._calc_worker.wait()
                QMessageBox.information(self, "已取消", "评分计算已取消。")
    
    def refresh_data(self) -> None:
        """刷新数据"""
        try:
            market = self.market_combo.currentText()
            view = self.view_combo.currentText()
            style = self.style_combo.currentText()
            
            # 获取主要指标配置
            main_indicators = self.config.get(f"indicators.{market}.main", [])
            weights = self.config.get(f"style_weights.{market}.{style}", [])
            
            if not main_indicators:
                print(f"[WARN] 未找到{market}市场的指标配置")
                return
            
            if len(main_indicators) != len(weights):
                print(f"[WARN] 指标数量({len(main_indicators)})与权重数量({len(weights)})不匹配")
                return
        except Exception as e:
            print(f"[ERROR] 加载配置失败: {e}")
            return
        
        # 加载各指标的最新数据
        indicator_data = []
        latest_date = None
        
        try:
            for ind in main_indicators:
                code = ind['code']
                try:
                    df = self.repository.load_series_data_by_code(code, view=view)
                    
                    if df is not None and not df.empty:
                        # 应用forward fill填充缺失数据（假期等情况）
                        # 对value_tr, z, score列进行前向填充
                        df_filled = df.copy()
                        for col in ['value_tr', 'z', 'score']:
                            if col in df_filled.columns:
                                df_filled[col] = df_filled[col].ffill()
                        
                        # 移除评分为0或NaN的行（0分无效，NaN也无效）
                        valid_df = df_filled[
                            (df_filled['score'].notna()) & 
                            (df_filled['score'] > 0)
                        ]
                        
                        if not valid_df.empty:
                            # 使用最后一条有效评分的记录
                            latest = valid_df.iloc[-1]
                            data_date = latest.name
                            latest_date = data_date if latest_date is None else latest_date
                            
                            indicator_data.append({
                                'code': code,
                                'name': ind.get('name', code),
                                'data_date': data_date,
                                'value': latest.get('value_tr', latest.get('value_raw', None)),
                                'z': latest.get('z', None),
                                'score': latest.get('score', None)
                            })
                        else:
                            # 没有有效评分，尝试查找value_tr
                            df_with_tr = df_filled[df_filled['value_tr'].notna()]
                            if not df_with_tr.empty:
                                latest = df_with_tr.iloc[-1]
                                data_date = latest.name
                                latest_date = data_date if latest_date is None else latest_date
                                
                                indicator_data.append({
                                    'code': code,
                                    'name': ind.get('name', code),
                                    'data_date': data_date,
                                    'value': latest.get('value_tr', latest.get('value_raw', None)),
                                    'z': latest.get('z', None),
                                    'score': None  # 明确标记无评分
                                })
                            else:
                                # 完全没有数据
                                indicator_data.append({
                                    'code': code,
                                    'name': ind.get('name', code),
                                    'data_date': None,
                                    'value': None,
                                    'z': None,
                                    'score': None
                                })
                    else:
                        indicator_data.append({
                            'code': code,
                            'name': ind.get('name', code),
                            'data_date': None,
                            'value': None,
                            'z': None,
                            'score': None
                        })
                except Exception as e:
                    print(f"[WARN] 加载指标{code}数据失败: {e}")
                    indicator_data.append({
                        'code': code,
                        'name': ind.get('name', code),
                        'data_date': None,
                        'value': None,
                        'z': None,
                        'score': None
                    })
            
            # 更新评分表格
            if indicator_data:
                self.score_table.update_scores(
                    indicator_data, 
                    weights, 
                    latest_date,
                    market,
                    style,
                    self.config
                )
        except Exception as e:
            print(f"[ERROR] 加载指标数据失败: {e}")
        
        # 加载综合评分数据
        try:
            regimes_df = self.repository.load_regimes(market=market, view=view)
            
            if regimes_df is not None and not regimes_df.empty:
                # 检查是否有 'date' 列，如果没有，可能已经是索引
                if 'date' in regimes_df.columns:
                    regimes_df = regimes_df.set_index('date')
                
                # 检查是否有 'composite_score' 列
                if 'composite_score' in regimes_df.columns:
                    composite_scores = regimes_df['composite_score']
                    composite_scores = composite_scores.dropna()
                    
                    if len(composite_scores) > 0:
                        self.composite_chart.update_chart(composite_scores, market, view, self.config)
                    else:
                        self.composite_chart.clear()
                        self.composite_chart.info_label.setText(
                            "暂无综合评分数据。请运行pipeline生成数据。"
                        )
                else:
                    self.composite_chart.clear()
                    self.composite_chart.info_label.setText(
                        "数据库中没有composite_score字段。请运行最新的pipeline更新数据。"
                    )
            else:
                self.composite_chart.clear()
                self.composite_chart.info_label.setText(
                    f"暂无{market}市场的{view}数据。请先运行数据获取。"
                )
        except Exception as e:
            print(f"[ERROR] 加载综合评分数据失败: {e}")
            self.composite_chart.clear()
            self.composite_chart.info_label.setText(f"加载数据失败: {str(e)}")
        
        # 加载确认层数据
        try:
            observer_indicators = self.config.get(f"indicators.{market}.observers", [])
            soft_weights = self.config.get(f"soft_confirm_weights.{market}", {})
            
            observer_data = []
            for obs in observer_indicators:
                code = obs['code']
                role = obs.get('role', '')
                
                try:
                    # 从lamp_history表获取最新灯色
                    lamp_hist = self.repository.load_lamp_history(
                        market=market,
                        view=view,
                        source_code=code
                    )
                    
                    if lamp_hist is not None and not lamp_hist.empty:
                        latest_lamp = lamp_hist.iloc[-1]['lamp']
                    else:
                        latest_lamp = '-'
                except Exception as e:
                    print(f"[WARN] 加载观察者{code}灯色失败: {e}")
                    latest_lamp = '-'
                
                observer_data.append({
                    'code': code,
                    'name': obs.get('name', code),
                    'role': role,
                    'lamp': latest_lamp
                })
            
            # 获取最终灯色
            hard_veto_lamp = 'Y'
            soft_confirm_lamp = 'Y'
            final_lamp = 'Y'
            
            try:
                # 重新加载以确保有完整的数据
                regimes_df_for_lamp = self.repository.load_regimes(market=market, view=view)
                
                if regimes_df_for_lamp is not None and not regimes_df_for_lamp.empty:
                    latest_regime = regimes_df_for_lamp.iloc[-1]
                    hard_veto_lamp = latest_regime.get('lamp_hard', 'Y')
                    soft_confirm_lamp = latest_regime.get('lamp_soft', 'Y')
                    final_lamp = latest_regime.get('lamp_final', 'Y')
            except Exception as e:
                print(f"[WARN] 加载最终灯色失败: {e}")
            
            self.confirm_panel.update_confirm_layer(
                observer_data,
                hard_veto_lamp,
                soft_confirm_lamp,
                final_lamp,
                soft_weights,
                market,
                self.config
            )
        except Exception as e:
            print(f"[ERROR] 加载确认层数据失败: {e}")

