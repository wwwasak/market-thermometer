"""
主窗口模块

实现基于PyQt6的现代化界面：
- 左侧控制面板：市场筛选、角色筛选、日期范围、视图选择、指标列表（可调整大小）
- 右侧图表区域：股票软件风格的折线图，支持导出/缩放/十字光标等
- 底部状态栏：显示记录数、日期范围、灯色信息
- 字体大小：支持全局调整（小/中/大）

所有数据均从SQLite数据库加载，遵循demand.txt中对GUI与数据展示的设计要求。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from pathlib import Path

import pandas as pd
from PyQt6.QtCore import QDate, QModelIndex, Qt, pyqtSignal, QThread
from PyQt6.QtGui import QStandardItem, QStandardItemModel, QAction
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
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.config import Config
from storage.repository import Repository
from ui.charts import IndicatorChartWidget, IndicatorDisplayConfig
from ui.market_overview import MarketOverviewWidget
from ui.styles import MAIN_WINDOW_QSS, get_styled_qss


class ManualFetchWorker(QThread):
    """后台线程：执行手动增量获取"""

    completed = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(
        self,
        database_url: str,
        markets: List[str],
        start_date: datetime,
        end_date: datetime,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.database_url = database_url
        self.markets = markets
        self.start_date = start_date
        self.end_date = end_date

    def run(self) -> None:  # pragma: no cover - 线程执行体
        try:
            from core.pipeline import MarketPipeline

            result: Dict[str, Dict] = {}
            for market in self.markets:
                pipeline = MarketPipeline(market=market, database_url=self.database_url)
                # 只获取原始数据，不计算评分
                result[market] = pipeline.fetch_and_save_raw_data(
                    start_date=self.start_date,
                    end_date=self.end_date,
                    incremental=True,
                )
            self.completed.emit(result)
        except Exception as exc:  # pragma: no cover
            self.failed.emit(str(exc))


class IndicatorListModel(QStandardItemModel):
    """指标列表模型"""

    def __init__(self, parent=None):
        super().__init__(parent)

    def add_indicator(self, meta: Dict) -> None:
        item = QStandardItem(f"{meta['code']} · {meta['name']}")
        item.setEditable(False)
        item.setData(meta, Qt.ItemDataRole.UserRole)
        self.appendRow(item)


class IndicatorControlPanel(QWidget):
    """左侧控制面板"""

    indicator_selected = pyqtSignal(dict)
    filters_changed = pyqtSignal()
    manual_fetch_requested = pyqtSignal()

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

        # 日期范围
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.dateChanged.connect(self._emit_filters_changed)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.dateChanged.connect(self._emit_filters_changed)

        self.reset_date_btn = QPushButton("重置日期")
        self.reset_date_btn.clicked.connect(self._reset_date_range)

        self.manual_fetch_btn = QPushButton("手动获取最新数据")
        self.manual_fetch_btn.setToolTip("获取最近7个交易日的原始数据（不计算评分）\n获取完成后，请点击'计算评分'按钮")
        self.manual_fetch_btn.clicked.connect(self._emit_manual_fetch)

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
        list_label.setProperty("labelStyle", "subtitle")
        layout.addWidget(list_label)
        layout.addWidget(self.list_view, stretch=1)
        layout.addWidget(self.manual_fetch_btn)

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

    def selected_market_code(self) -> Optional[str]:
        market_text = self.market_combo.currentText()
        if market_text == "全部市场":
            return None
        return market_text

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
        }

    def set_manual_fetch_enabled(self, enabled: bool) -> None:
        self.manual_fetch_btn.setEnabled(enabled)

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

    def _emit_manual_fetch(self) -> None:
        self.manual_fetch_requested.emit()


class ThermometerMainWindow(QMainWindow):
    """双市场温度计主窗口"""

    MANUAL_FETCH_DAYS = 7
    MANUAL_FETCH_BUFFER = 5
    MIN_MANUAL_FETCH_DAYS = 30

    def __init__(
        self,
        database_url: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self.config = Config()
        
        # 尝试加载用户配置
        user_config_file = Path("config/user_config.json")
        if user_config_file.exists():
            self.config.load_from_json(str(user_config_file))
            print(f"[INFO] 已加载用户配置: {user_config_file}")
        
        if not database_url:
            db_path = self.config.get("database.path", "market_thermo.db")
            if db_path.startswith("sqlite:///"):
                database_url = db_path
            else:
                database_url = f"sqlite:///{db_path}"

        self.database_url = database_url
        self.repository = Repository(database_url)
        self._manual_fetch_worker: Optional[ManualFetchWorker] = None
        self._current_indicator: Optional[Dict] = None
        self._current_font_size = 'medium'  # 当前字体大小

        self.setWindowTitle("双市场温度计 · 图表终端")
        # 先设置一个合理的默认大小（如果用户还原窗口时使用）
        self.resize(1400, 840)
        
        # 创建菜单栏
        self._create_menu_bar()

        self.control_panel = IndicatorControlPanel()
        self.control_panel.indicator_selected.connect(self._on_indicator_selected)
        self.control_panel.filters_changed.connect(self._apply_filters)
        self.control_panel.manual_fetch_requested.connect(self._on_manual_fetch_requested)

        # 创建Tab页面
        self.tab_widget = QTabWidget()
        
        # 指标图表Tab
        self.chart_widget = IndicatorChartWidget()
        self.tab_widget.addTab(self.chart_widget, "指标图表")
        
        # 市场概览Tab
        self.overview_widget = MarketOverviewWidget(
            database_url=self.database_url,
            config=self.config
        )
        self.tab_widget.addTab(self.overview_widget, "市场概览")

        splitter = QSplitter()
        splitter.setOrientation(Qt.Orientation.Horizontal)
        splitter.addWidget(self.control_panel)
        splitter.addWidget(self.tab_widget)
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
        self.record_label.setProperty("labelStyle", "small")
        self.lamp_label.setProperty("labelStyle", "small")
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
        
        # 标记需要保持最大化状态
        self._keep_maximized = True
        
        # 设置窗口大小约束，防止子控件影响窗口大小
        # 获取屏幕大小
        screen = QApplication.primaryScreen().geometry()
        # 设置最小大小为合理值，最大大小为屏幕大小
        self.setMinimumSize(800, 600)
        self.setMaximumSize(screen.width(), screen.height())
        
        # 在所有控件创建完成后，最大化窗口
        # 使用 QTimer 延迟调用，确保所有控件完全初始化
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, self.showMaximized)
    
    def _create_menu_bar(self) -> None:
        """创建菜单栏"""
        menubar = self.menuBar()
        
        # 视图菜单
        view_menu = menubar.addMenu("视图(&V)")
        
        # 字体大小子菜单
        font_size_menu = view_menu.addMenu("字体大小")
        
        # 小号字体
        small_font_action = QAction("小号 (11px)", self)
        small_font_action.setCheckable(True)
        small_font_action.triggered.connect(lambda: self._change_font_size('small'))
        font_size_menu.addAction(small_font_action)
        
        # 中号字体（默认）
        medium_font_action = QAction("中号 (13px)", self)
        medium_font_action.setCheckable(True)
        medium_font_action.setChecked(True)
        medium_font_action.triggered.connect(lambda: self._change_font_size('medium'))
        font_size_menu.addAction(medium_font_action)
        
        # 大号字体
        large_font_action = QAction("大号 (15px)", self)
        large_font_action.setCheckable(True)
        large_font_action.triggered.connect(lambda: self._change_font_size('large'))
        font_size_menu.addAction(large_font_action)
        
        # 将动作组合，使其互斥
        self._font_size_actions = {
            'small': small_font_action,
            'medium': medium_font_action,
            'large': large_font_action,
        }
    
    def resizeEvent(self, event):
        """
        重写窗口大小改变事件，防止非用户操作导致的大小变化
        """
        super().resizeEvent(event)
        
        # 如果需要保持最大化，检查当前状态
        if hasattr(self, '_keep_maximized') and self._keep_maximized:
            if not self.isMaximized() and not self.isMinimized():
                # 阻止非用户操作的大小变化
                # 使用 blockSignals 暂时阻止信号，避免递归
                self.blockSignals(True)
                self.showMaximized()
                self.blockSignals(False)
    
    def changeEvent(self, event):
        """
        监控窗口状态变化，强制保持最大化
        """
        super().changeEvent(event)
        
        # 监控窗口状态变化
        if event.type() == event.Type.WindowStateChange:
            if hasattr(self, '_keep_maximized') and self._keep_maximized:
                # 如果不是最大化状态，立即恢复
                if not self.isMaximized() and not self.isMinimized():
                    # 使用 setWindowState 直接设置状态，更快
                    self.setWindowState(Qt.WindowState.WindowMaximized)
    
    def _change_font_size(self, size: str) -> None:
        """
        切换字体大小
        
        @param {str} size - 字体大小 ('small', 'medium', 'large')
        """
        if size not in ['small', 'medium', 'large']:
            return
        
        # 更新当前字体大小
        self._current_font_size = size
        
        # 更新菜单项选中状态
        for key, action in self._font_size_actions.items():
            action.setChecked(key == size)
        
        # 应用新的样式表
        styled_qss = get_styled_qss(size)
        self.setStyleSheet(styled_qss)
        
        # 更新状态栏提示
        size_names = {'small': '小号', 'medium': '中号', 'large': '大号'}
        self.statusBar().showMessage(f"字体大小已切换为: {size_names[size]}", 2000)

    # -- 数据加载 --
    def _load_indicator_meta(self) -> List[Dict]:
        meta_list = self.repository.get_all_series_meta()
        meta_list.sort(key=lambda m: (m.get("market", ""), m.get("role", ""), m["code"]))
        return meta_list

    def _apply_filters(self) -> None:
        filters = self.control_panel.current_filters()
        market = filters["market"]
        role = filters["role"]

        filtered = []
        for meta in self._all_indicators:
            if market != "全部市场" and meta.get("market") != market:
                continue
            if role != "全部角色" and meta.get("role") != role:
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
        self._current_indicator = meta

    # -- 手动获取逻辑 --
    def _on_manual_fetch_requested(self) -> None:
        if self._manual_fetch_worker and self._manual_fetch_worker.isRunning():
            QMessageBox.information(self, "提示", "已有手动获取任务在执行，请稍候。")
            return

        selected_market = self.control_panel.selected_market_code()
        markets = ["CN", "US"] if selected_market is None else [selected_market]

        end_dt = datetime.now()
        lookback_days = max(
            self.MANUAL_FETCH_DAYS + self.MANUAL_FETCH_BUFFER,
            self.MIN_MANUAL_FETCH_DAYS,
        )
        start_dt = end_dt - timedelta(days=lookback_days)

        self.statusBar().showMessage("手动获取数据中，请稍候…")
        self.control_panel.set_manual_fetch_enabled(False)

        self._manual_fetch_worker = ManualFetchWorker(
            database_url=self.database_url,
            markets=markets,
            start_date=start_dt,
            end_date=end_dt,
        )
        self._manual_fetch_worker.completed.connect(self._on_manual_fetch_completed)
        self._manual_fetch_worker.failed.connect(self._on_manual_fetch_failed)
        self._manual_fetch_worker.finished.connect(self._clear_manual_worker)
        self._manual_fetch_worker.start()

    def _on_manual_fetch_completed(self, result: Dict[str, Dict]) -> None:
        self.statusBar().showMessage("手动获取完成", 3000)
        self.control_panel.set_manual_fetch_enabled(True)
        self._refresh_current_indicator()

        summary_lines = ["原始数据已保存到数据库：", ""]
        for market, payload in result.items():
            if payload.get("success"):
                records = payload.get("records_saved", 0)
                date_range = payload.get("date_range")
                if date_range:
                    start_str = date_range[0].strftime("%Y-%m-%d")
                    end_str = date_range[1].strftime("%Y-%m-%d")
                    summary_lines.append(f"{market}: ✓ {records} 条 ({start_str} → {end_str})")
                else:
                    summary_lines.append(f"{market}: ✓ {records} 条")
            else:
                summary_lines.append(f"{market}: ✗ {payload.get('error', 'unknown error')}")
        
        summary_lines.append("")
        summary_lines.append("⚠ 注意：仅保存了原始数据，未计算评分")
        summary_lines.append("请切换到相应市场后点击'计算评分'按钮")

        QMessageBox.information(self, "数据获取完成", "\n".join(summary_lines))

    def _on_manual_fetch_failed(self, message: str) -> None:
        self.statusBar().showMessage("手动获取失败", 5000)
        self.control_panel.set_manual_fetch_enabled(True)
        QMessageBox.critical(self, "手动获取失败", message)

    def _clear_manual_worker(self) -> None:
        self._manual_fetch_worker = None

    def _refresh_current_indicator(self) -> None:
        if self._current_indicator:
            self._on_indicator_selected(self._current_indicator)


def launch_gui(database_url: Optional[str] = None):
    """启动主窗口"""
    app = QApplication.instance() or QApplication([])
    window = ThermometerMainWindow(database_url=database_url)
    # 窗口会通过构造函数中的 showMaximized() 显示，这里不需要再调用 show()
    # window.show() 会覆盖 showMaximized() 的效果
    app.exec()

