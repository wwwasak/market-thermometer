"""
主窗口模块

实现基于PyQt6的现代化界面：
- 左侧控制面板：市场筛选、角色筛选、搜索、日期范围、视图选择、指标列表
- 右侧图表区域：股票软件风格的折线图，支持导出/缩放/十字光标等
- 底部状态栏：显示记录数、日期范围、灯色信息

所有数据均从SQLite数据库加载，遵循demand.txt中对GUI与数据展示的设计要求。
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
from PyQt6.QtCore import QDate, QModelIndex, Qt, pyqtSignal
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from core.config import Config
from storage.repository import Repository
from ui.charts import IndicatorChartWidget, IndicatorDisplayConfig
from ui.styles import MAIN_WINDOW_QSS


class IndicatorListModel(QStandardItemModel):
    """指标列表模型"""

    def __init__(self, parent=None):
        super().__init__(parent)

    def add_indicator(self, meta: Dict) -> None:
        item = QStandardItem(f"{meta['code']} · {meta['name']}")
        item.setEditable(False)
        item.setData(meta, Qt.ItemDataRole.UserRole)
        search_key = f"{meta.get('code', '')} {meta.get('name', '')} {meta.get('market', '')} {meta.get('role', '')}"
        item.setData(search_key.lower(), Qt.ItemDataRole.UserRole + 1)
        self.appendRow(item)


class IndicatorControlPanel(QWidget):
    """左侧控制面板"""

    indicator_selected = pyqtSignal(dict)
    filters_changed = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._indicators: List[Dict] = []

        # 市场、角色、视图筛选
        self.market_combo = QComboBox()
        self.market_combo.addItems(["全部市场", "CN", "US"])
        self.market_combo.currentIndexChanged.connect(self._emit_filters_changed)

        self.role_combo = QComboBox()
        self.role_combo.addItems(["全部角色", "main", "soft", "hard", "pair", "component"])
        self.role_combo.currentIndexChanged.connect(self._emit_filters_changed)

        self.view_combo = QComboBox()
        self.view_combo.addItems(["日线 (daily)", "周线 (weekly)"])
        self.view_combo.currentIndexChanged.connect(self._emit_filters_changed)

        # 搜索
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索代码或名称…")
        self.search_edit.textChanged.connect(self._emit_filters_changed)

        # 日期范围
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.dateChanged.connect(self._emit_filters_changed)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.dateChanged.connect(self._emit_filters_changed)

        self.reset_date_btn = QPushButton("重置日期")
        self.reset_date_btn.clicked.connect(self._reset_date_range)

        # 指标列表
        self.list_view = QListView()
        self.list_view.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.list_view.clicked.connect(self._handle_selection)
        self.list_view.doubleClicked.connect(self._handle_selection)

        self.model = IndicatorListModel(self)
        self.list_view.setModel(self.model)

        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        layout.addWidget(self._build_group("市场", self.market_combo))
        layout.addWidget(self._build_group("角色", self.role_combo))
        layout.addWidget(self._build_group("视图", self.view_combo))
        layout.addWidget(self._build_group("搜索", self.search_edit))

        date_frame = QFrame()
        date_layout = QVBoxLayout(date_frame)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.addWidget(QLabel("开始日期"))
        date_layout.addWidget(self.start_date_edit)
        date_layout.addWidget(QLabel("结束日期"))
        date_layout.addWidget(self.end_date_edit)
        date_layout.addWidget(self.reset_date_btn)
        layout.addWidget(self._build_group("日期范围", date_frame))

        list_label = QLabel("指标列表")
        list_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(list_label)
        layout.addWidget(self.list_view, stretch=1)

    # -- 基本操作 --
    def set_indicators(self, indicators: List[Dict]) -> None:
        self.model.clear()
        self._indicators = indicators
        for meta in indicators:
            self.model.add_indicator(meta)
        self.list_view.setCurrentIndex(self.model.index(0, 0) if self.model.rowCount() else QModelIndex())

    def set_default_dates(self, start: date, end: date) -> None:
        self.start_date_edit.setDate(QDate(start.year, start.month, start.day))
        self.end_date_edit.setDate(QDate(end.year, end.month, end.day))

    def selected_view(self) -> str:
        return "daily" if self.view_combo.currentIndex() == 0 else "weekly"

    def selected_date_range(self) -> Tuple[Optional[date], Optional[date]]:
        start = self.start_date_edit.date().toPyDate()
        end = self.end_date_edit.date().toPyDate()
        if start > end:
            start, end = end, start
        return start, end

    def current_filters(self) -> Dict:
        return {
            "market": self.market_combo.currentText(),
            "role": self.role_combo.currentText(),
            "search": self.search_edit.text(),
        }

    # -- 内部逻辑 --
    def _build_group(self, title: str, widget: QWidget) -> QWidget:
        container = QFrame()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        label = QLabel(title)
        label.setStyleSheet("font-weight: 600; color: #A8DADC;")
        layout.addWidget(label)
        layout.addWidget(widget)
        return container

    def _reset_date_range(self) -> None:
        today = date.today()
        start = today - timedelta(days=365)
        self.start_date_edit.setDate(QDate(start.year, start.month, start.day))
        self.end_date_edit.setDate(QDate(today.year, today.month, today.day))
        self._emit_filters_changed()

    def _emit_filters_changed(self) -> None:
        self.filters_changed.emit()

    def _handle_selection(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        meta = index.data(Qt.ItemDataRole.UserRole)
        if meta:
            self.indicator_selected.emit(meta)


class ThermometerMainWindow(QMainWindow):
    """双市场温度计主窗口"""

    def __init__(
        self,
        database_url: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self.config = Config()
        if not database_url:
            db_path = self.config.get("database.path", "market_thermo.db")
            if db_path.startswith("sqlite:///"):
                database_url = db_path
            else:
                database_url = f"sqlite:///{db_path}"

        self.repository = Repository(database_url)

        self.setWindowTitle("双市场温度计 · 图表终端")
        self.resize(1400, 840)

        self.control_panel = IndicatorControlPanel()
        self.control_panel.indicator_selected.connect(self._on_indicator_selected)
        self.control_panel.filters_changed.connect(self._apply_filters)

        self.chart_widget = IndicatorChartWidget()

        splitter = QSplitter()
        splitter.setOrientation(Qt.Orientation.Horizontal)
        splitter.addWidget(self.control_panel)
        splitter.addWidget(self.chart_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 1080])

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)
        self.setCentralWidget(central)

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        self.record_label = QLabel("记录: -")
        self.lamp_label = QLabel("灯色: -")
        self.record_label.setStyleSheet("color: #5B6470;")
        self.lamp_label.setStyleSheet("color: #5B6470;")
        status_bar.addPermanentWidget(self.record_label)
        status_bar.addPermanentWidget(self.lamp_label)

        # 加载指标元数据
        self._all_indicators = self._load_indicator_meta()
        self.control_panel.set_indicators(self._all_indicators)
        default_end = date.today()
        default_start = default_end - timedelta(days=365)
        self.control_panel.set_default_dates(default_start, default_end)

        self.setStyleSheet(MAIN_WINDOW_QSS)

        if self._all_indicators:
            self._on_indicator_selected(self._all_indicators[0])

    # -- 数据加载 --
    def _load_indicator_meta(self) -> List[Dict]:
        meta_list = self.repository.get_all_series_meta()
        meta_list.sort(key=lambda m: (m.get("market", ""), m.get("role", ""), m["code"]))
        return meta_list

    def _apply_filters(self) -> None:
        filters = self.control_panel.current_filters()
        search = filters["search"].lower()
        market = filters["market"]
        role = filters["role"]

        filtered = []
        for meta in self._all_indicators:
            if market != "全部市场" and meta.get("market") != market:
                continue
            if role != "全部角色" and meta.get("role") != role:
                continue
            key = f"{meta.get('code', '').lower()} {meta.get('name', '').lower()}"
            if search and search not in key:
                continue
            filtered.append(meta)

        self.control_panel.set_indicators(filtered)
        if not filtered:
            self.chart_widget.clear()
            self.record_label.setText("记录: -")
            self.lamp_label.setText("灯色: -")

    def _on_indicator_selected(self, meta: Dict) -> None:
        view = self.control_panel.selected_view()
        start_date, end_date = self.control_panel.selected_date_range()

        df = self.repository.load_series_data_by_code(
            meta["code"],
            view=view,
            start_date=start_date,
            end_date=end_date,
        )

        if df is not None and not df.empty:
            df = df.sort_index()
            # 转换索引为DatetimeIndex
            if not isinstance(df.index, pd.DatetimeIndex):
                df.index = pd.to_datetime(df.index)

        display_config = IndicatorDisplayConfig(
            code=meta.get("code", ""),
            name=meta.get("name", ""),
            market=meta.get("market", ""),
            role=meta.get("role", ""),
            direction=meta.get("direction", "up_good"),
        )
        self.chart_widget.set_indicator(display_config, df, view=view)

        # 更新状态栏
        if df is None or df.empty:
            self.record_label.setText("记录: 0")
            self.lamp_label.setText("灯色: -")
            return

        self.record_label.setText(f"记录: {len(df)} · {df.index.min().date()} → {df.index.max().date()}")

        if "score" in df.columns:
            last_score = df["score"].dropna().iloc[-1] if not df["score"].dropna().empty else None
        else:
            last_score = None

        lamp = "-"
        if last_score is not None:
            if last_score >= 60:
                lamp = "绿灯 (>=60)"
            elif last_score <= 40:
                lamp = "红灯 (<=40)"
            else:
                lamp = "黄灯"
        self.lamp_label.setText(f"灯色: {lamp}")


def launch_gui(database_url: Optional[str] = None):
    """启动主窗口"""
    app = QApplication.instance() or QApplication([])
    window = ThermometerMainWindow(database_url=database_url)
    window.show()
    app.exec()

