"""
图表组件（PyQtGraph版）

提供接近专业股票终端的交互体验：
- 平移 / 缩放 / 双击复位
- 十字准星 + 动态数值提示
- 双纵轴（原始值 & Score）以及阈值线
- 可导出高分辨率 PNG
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ui.styles import CHART_STYLE

# 配置PyQtGraph使用白色背景和现代化样式
pg.setConfigOptions(
    antialias=True,
    background=CHART_STYLE['background'],
    foreground=CHART_STYLE['foreground']
)


class DateAxisItem(pg.AxisItem):
    """自定义时间轴，格式化为 YYYY-MM-DD。"""

    def tickStrings(self, values, scale, spacing):
        labels = []
        for v in values:
            if np.isnan(v):
                labels.append("")
            else:
                labels.append(pd.to_datetime(v, unit="s").strftime("%Y-%m-%d"))
        return labels


@dataclass
class IndicatorDisplayConfig:
    """图表显示配置"""

    code: str
    name: str
    market: str
    role: str
    direction: str


class IndicatorChartWidget(QWidget):
    """基于PyQtGraph的股票式折线图。"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._safe_float = lambda v: float(v) if v is not None and str(v) != "" and not pd.isna(v) else np.nan
        self._config: Optional[IndicatorDisplayConfig] = None
        self._df: Optional[pd.DataFrame] = None
        self._timestamps: np.ndarray = np.array([])
        self._view: str = "daily"
        self._score_available = False

        # 顶部信息区
        self._status_label = QLabel("选择指标以加载数据")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._status_label.setStyleSheet(f"""
            color: {CHART_STYLE['text_color']};
            font-size: 13px;
            padding: 4px;
        """)

        self._info_label = QLabel("悬停显示数值")
        self._info_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._info_label.setStyleSheet(f"""
            color: {CHART_STYLE['text_color']};
            font-size: 12px;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            padding: 4px;
        """)

        self._value_mode = "raw"  # 'raw' or 'transformed'
        self._toggle_btn = QPushButton("显示转换值")
        self._toggle_btn.clicked.connect(self._toggle_value_mode)

        self._reset_btn = QPushButton("复位视图")
        self._reset_btn.clicked.connect(self._reset_view)
        self._export_btn = QPushButton("导出PNG")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._handle_export)

        header_layout = QHBoxLayout()
        header_layout.addWidget(self._status_label, stretch=1)
        header_layout.addWidget(self._info_label, stretch=1)
        header_layout.addWidget(self._toggle_btn, stretch=0)
        header_layout.addWidget(self._reset_btn, stretch=0)
        header_layout.addWidget(self._export_btn, stretch=0)

        # 图表主体
        self._graphics = pg.GraphicsLayoutWidget()
        self._plot = self._graphics.addPlot(
            row=0,
            col=0,
            axisItems={"bottom": DateAxisItem(orientation="bottom")},
        )
        self._plot.setMenuEnabled(False)
        
        # 网格线样式 - 浅灰色，更细腻
        self._plot.showGrid(x=True, y=True, alpha=0.15)
        
        # 左侧Y轴样式 - 主数据
        left_axis = self._plot.getAxis("left")
        left_axis.setLabel("原始/转换值", color=CHART_STYLE['foreground'])
        left_axis.setPen(pg.mkPen(CHART_STYLE['grid_color'], width=1))
        left_axis.setTextPen(CHART_STYLE['text_color'])
        
        # 底部X轴样式
        bottom_axis = self._plot.getAxis("bottom")
        bottom_axis.setPen(pg.mkPen(CHART_STYLE['grid_color'], width=1))
        bottom_axis.setTextPen(CHART_STYLE['text_color'])

        # 右侧Y轴样式 - Score
        self._score_axis = self._plot.getAxis("right")
        self._score_axis.setLabel("Score (0-100)", color=CHART_STYLE['line_colors'][2])
        self._score_axis.setPen(pg.mkPen(CHART_STYLE['line_colors'][2], width=1))
        self._score_axis.setTextPen(CHART_STYLE['line_colors'][2])

        self._score_view = pg.ViewBox()
        self._plot.scene().addItem(self._score_view)
        self._score_axis.linkToView(self._score_view)
        self._score_view.setXLink(self._plot)
        self._plot.vb.sigResized.connect(self._update_views)

        # 主线与标记 - 使用现代化蓝色
        primary_color = CHART_STYLE['line_colors'][0]
        self._price_curve = self._plot.plot(pen=pg.mkPen(primary_color, width=2.5))
        self._price_marker = pg.ScatterPlotItem(
            size=10,
            brush=pg.mkBrush(primary_color),
            pen=pg.mkPen('w', width=2),
        )
        self._plot.addItem(self._price_marker)

        # Score线与阈值 - 使用现代化颜色
        score_color = CHART_STYLE['line_colors'][2]
        success_color = CHART_STYLE['line_colors'][1]
        danger_color = CHART_STYLE['line_colors'][3]
        
        self._score_curve = pg.PlotCurveItem(pen=pg.mkPen(score_color, width=2))
        self._score_view.addItem(self._score_curve)
        self._score_marker = pg.ScatterPlotItem(
            size=10,
            brush=pg.mkBrush(score_color),
            pen=pg.mkPen('w', width=2),
        )
        self._score_view.addItem(self._score_marker)

        # 阈值线 - 绿色(60分)和红色(40分)
        self._threshold_green = pg.InfiniteLine(
            angle=0,
            pos=60,
            pen=pg.mkPen(success_color, width=1.5, style=Qt.PenStyle.DashLine),
        )
        self._threshold_red = pg.InfiniteLine(
            angle=0,
            pos=40,
            pen=pg.mkPen(danger_color, width=1.5, style=Qt.PenStyle.DashLine),
        )
        self._score_view.addItem(self._threshold_green)
        self._score_view.addItem(self._threshold_red)

        # 十字准星 - 更细腻的灰色
        crosshair_color = CHART_STYLE['grid_color']
        self._v_line = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen(crosshair_color, width=1))
        self._h_line = pg.InfiniteLine(angle=0, movable=False, pen=pg.mkPen(crosshair_color, width=1))
        self._plot.addItem(self._v_line, ignoreBounds=True)
        self._plot.addItem(self._h_line, ignoreBounds=True)
        self._v_line.hide()
        self._h_line.hide()

        self._signal_proxy = pg.SignalProxy(
            self._plot.scene().sigMouseMoved,
            rateLimit=60,
            slot=self._on_mouse_move,
        )

        self._update_views()

        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(header_layout)
        layout.addWidget(self._graphics, stretch=1)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    # ------------------------------
    # 外部接口
    # ------------------------------
    def set_indicator(
        self,
        config: IndicatorDisplayConfig,
        data_frame: pd.DataFrame,
        view: str = "daily",
    ) -> None:
        self._config = config
        self._df = data_frame.copy() if data_frame is not None else None
        self._view = view

        if self._df is None or self._df.empty:
            self.clear()
            self._status_label.setText(f"{config.code} 暂无数据")
            return

        self._df.sort_index(inplace=True)
        self._timestamps = (pd.to_datetime(self._df.index).view("int64") / 1e9).astype(float)
        self._status_label.setText(
            f"{config.code} · {config.name} · {view} · {self._df.index.min().date()} → {self._df.index.max().date()}"
        )
        self._export_btn.setEnabled(True)
        self._plot_data()

    def clear(self) -> None:
        self._config = None
        self._df = None
        self._timestamps = np.array([])
        self._status_label.setText("选择指标以加载数据")
        self._info_label.setText("悬停显示数值")
        self._export_btn.setEnabled(False)
        self._clear_plot()

    # ------------------------------
    # 绘制逻辑
    # ------------------------------
    def _clear_plot(self) -> None:
        self._price_curve.clear()
        self._score_curve.clear()
        self._price_marker.setData([], [])
        self._score_marker.setData([], [])
        self._v_line.hide()
        self._h_line.hide()
        self._threshold_green.hide()
        self._threshold_red.hide()
        self._score_axis.setLabel("")
        self._score_axis.setTicks([])
        self._score_available = False
        self._toggle_btn.setEnabled(False)

    def _plot_data(self) -> None:
        assert self._df is not None

        primary = self._df.get("value_raw")
        transformed = self._df.get("value_tr")
        if primary is None or primary.dropna().empty:
            primary = transformed

        primary_values = primary.astype(float).values if primary is not None else np.array([])
        alt_values = transformed.astype(float).values if transformed is not None else np.array([])

        # 根据当前模式选择展示序列
        if self._value_mode == "transformed" and transformed is not None and not transformed.dropna().empty:
            display_series = transformed
            display_values = alt_values
            axis_label = "转换值"
        else:
            display_series = primary
            display_values = primary_values
            axis_label = "原始值"
            self._value_mode = "raw"
            self._toggle_btn.setText("显示转换值")

        self._price_curve.setData(self._timestamps, display_values, connect="finite")
        has_transformed = transformed is not None and not transformed.dropna().empty
        self._toggle_btn.setEnabled(has_transformed)
        if not has_transformed:
            self._toggle_btn.setText("显示转换值")
        self._plot.getAxis("left").setLabel(axis_label, color="#1F2933")

        valid_primary = display_series.dropna() if display_series is not None else pd.Series(dtype=float)
        if not valid_primary.empty:
            min_val = valid_primary.min()
            max_val = valid_primary.max()
            if min_val == max_val:
                span = abs(min_val) if min_val != 0 else 1
                min_val -= span * 0.1
                max_val += span * 0.1
            self._plot.setYRange(min_val, max_val, padding=0.1)
        else:
            self._plot.enableAutoRange(axis=pg.ViewBox.YAxis)

        score = self._df.get("score")
        if score is not None and not score.dropna().empty:
            score_values = score.astype(float).values
            self._score_curve.setData(self._timestamps, score_values, connect="finite")
            score_min = min(score.min(skipna=True) - 5, 0)
            score_max = max(score.max(skipna=True) + 5, 100)
            self._score_view.setYRange(score_min, score_max, padding=0.05)
            self._threshold_green.show()
            self._threshold_red.show()
            self._score_axis.setLabel("Score (0-100)", color="#E65100")
            self._score_axis.setTicks(None)
            self._score_available = True
        else:
            self._score_curve.clear()
            self._score_marker.setData([], [])
            self._threshold_green.hide()
            self._threshold_red.hide()
            self._score_axis.setLabel("")
            self._score_axis.setTicks([])
            self._score_available = False

        if len(self._timestamps) > 0:
            self._plot.setXRange(self._timestamps[0], self._timestamps[-1], padding=0.02)

        self._price_marker.setData([], [])
        self._score_marker.setData([], [])
        self._v_line.hide()
        self._h_line.hide()
        self._info_label.setText("悬停显示数值")
        self._update_views()

    def _update_views(self) -> None:
        self._score_view.setGeometry(self._plot.vb.sceneBoundingRect())
        self._score_view.linkedViewChanged(self._plot.vb, self._score_view.XAxis)

    def _reset_view(self) -> None:
        if self._df is None or self._df.empty:
            return
        if len(self._timestamps) > 0:
            self._plot.setXRange(self._timestamps[0], self._timestamps[-1], padding=0.02)
        self._plot.enableAutoRange(axis=pg.ViewBox.YAxis)
        if self._score_available:
            score = self._df["score"].dropna()
            if not score.empty:
                score_min = min(score.min() - 5, 0)
                score_max = max(score.max() + 5, 100)
                self._score_view.setYRange(score_min, score_max, padding=0.05)
        self._price_marker.setData([], [])
        self._score_marker.setData([], [])
        self._v_line.hide()
        self._h_line.hide()
        self._info_label.setText("悬停显示数值")

    def _on_mouse_move(self, event) -> None:
        if self._df is None or self._df.empty or len(self._timestamps) == 0:
            return

        pos = event[0]
        if not self._plot.sceneBoundingRect().contains(pos):
            self._v_line.hide()
            self._h_line.hide()
            self._price_marker.setData([], [])
            self._score_marker.setData([], [])
            self._info_label.setText("悬停显示数值")
            return

        mouse_point = self._plot.vb.mapSceneToView(pos)
        x_val = mouse_point.x()
        idx = int(np.clip(np.searchsorted(self._timestamps, x_val), 0, len(self._timestamps) - 1))
        ts = self._timestamps[idx]
        row = self._df.iloc[idx]
        dt = pd.to_datetime(ts, unit="s")

        raw_val = self._safe_float(row.get("value_raw"))
        tr_val = self._safe_float(row.get("value_tr"))
        score_val = self._safe_float(row.get("score"))

        if self._value_mode == "transformed" and not np.isnan(tr_val):
            primary_val = tr_val
            value_label = "转换"
        else:
            primary_val = raw_val if not np.isnan(raw_val) else tr_val
            value_label = "原始"
        if np.isnan(primary_val):
            self._price_marker.setData([], [])
            self._h_line.hide()
        else:
            self._price_marker.setData([ts], [primary_val])
            self._h_line.setPos(primary_val)
            self._h_line.show()

        if self._score_available and not np.isnan(score_val):
            self._score_marker.setData([ts], [score_val])
        else:
            self._score_marker.setData([], [])

        self._v_line.setPos(ts)
        self._v_line.show()

        def fmt(val: Optional[float]) -> str:
            if val is None or np.isnan(val):
                return "-"
            return f"{val:,.3f}"

        self._info_label.setText(
            f"{dt.strftime('%Y-%m-%d')} | {value_label} {fmt(primary_val)} | Score {fmt(score_val)}"
        )

    def _toggle_value_mode(self) -> None:
        if self._df is None or self._df.empty:
            return
        self._value_mode = "transformed" if self._value_mode == "raw" else "raw"
        self._toggle_btn.setText("显示原始值" if self._value_mode == "transformed" else "显示转换值")
        self._plot_data()

    # ------------------------------
    # 导出
    # ------------------------------
    def _handle_export(self) -> None:
        if self._config is None:
            return
        default_name = f"{self._config.code}_{self._view}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出图表为PNG",
            default_name,
            "PNG 图片 (*.png)",
        )
        if file_path:
            self._graphics.grab().save(file_path)

