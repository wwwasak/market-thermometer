"""
数据完整性检查对话框

用于在手动获取数据后，提示用户哪些主指标缺少当日数据
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox
)
from PyQt6.QtCore import Qt
from typing import Dict, Any, List


class DataCompletenessDialog(QDialog):
    """
    数据完整性检查对话框
    
    显示哪些主指标缺少当日数据，并询问用户是否使用最近数据填充
    """
    
    def __init__(
        self,
        completeness_report: Dict[str, Any],
        market: str,
        parent=None
    ):
        """
        @param {Dict[str, Any]} completeness_report - 完整性报告
        @param {str} market - 市场名称（CN/US）
        @param {QWidget} parent - 父窗口
        """
        super().__init__(parent)
        
        self.completeness_report = completeness_report
        self.market = market
        self.user_choice = None  # 'use_latest', 'skip', 'cancel'
        
        self._init_ui()
    
    def _init_ui(self):
        """初始化UI"""
        target_date = self.completeness_report['target_date']
        missing_indicators = self.completeness_report['missing_indicators']
        complete_count = self.completeness_report['complete_count']
        total_count = self.completeness_report['main_indicator_count']
        
        self.setWindowTitle(f"{self.market}市场数据完整性检查")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        
        layout = QVBoxLayout(self)
        
        # 标题
        title_label = QLabel(
            f"<h3>{self.market}市场 {target_date.strftime('%Y-%m-%d')} 数据完整性检查</h3>"
        )
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        # 统计信息
        stats_label = QLabel(
            f"<p>主指标总数: <b>{total_count}</b> | "
            f"有当日数据: <b style='color: green;'>{complete_count}</b> | "
            f"缺少当日数据: <b style='color: red;'>{len(missing_indicators)}</b></p>"
        )
        stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(stats_label)
        
        # 缺失数据表格
        if missing_indicators:
            missing_label = QLabel("<b>以下指标缺少当日数据：</b>")
            layout.addWidget(missing_label)
            
            table = QTableWidget()
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(["指标代码", "指标名称", "最新数据日期", "距今天数"])
            table.setRowCount(len(missing_indicators))
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            
            for row, ind in enumerate(missing_indicators):
                # 指标代码
                code_item = QTableWidgetItem(ind['code'])
                table.setItem(row, 0, code_item)
                
                # 指标名称
                name_item = QTableWidgetItem(ind['name'])
                table.setItem(row, 1, name_item)
                
                # 最新数据日期
                if ind['has_data'] and ind['latest_date']:
                    date_item = QTableWidgetItem(ind['latest_date'].strftime('%Y-%m-%d'))
                else:
                    date_item = QTableWidgetItem("无数据")
                    date_item.setForeground(Qt.GlobalColor.red)
                table.setItem(row, 2, date_item)
                
                # 距今天数
                if ind['has_data'] and ind['days_ago'] is not None:
                    days_item = QTableWidgetItem(f"{ind['days_ago']} 天")
                    if ind['days_ago'] <= 1:
                        days_item.setForeground(Qt.GlobalColor.darkGreen)
                    elif ind['days_ago'] <= 3:
                        days_item.setForeground(Qt.GlobalColor.darkYellow)
                    else:
                        days_item.setForeground(Qt.GlobalColor.red)
                else:
                    days_item = QTableWidgetItem("N/A")
                    days_item.setForeground(Qt.GlobalColor.red)
                table.setItem(row, 3, days_item)
            
            # 调整列宽
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            
            layout.addWidget(table)
            
            # 提示信息
            info_label = QLabel(
                "<p style='color: #666;'>"
                "💡 <b>提示：</b><br>"
                "• <b>使用最近数据</b>：使用这些指标的最新有效数据来计算今天的综合评分<br>"
                "• <b>跳过当日评分</b>：计算历史数据的评分，但不计算今天的评分（等待数据更新）<br>"
                "• <b>取消</b>：取消整个评分计算流程"
                "</p>"
            )
            info_label.setWordWrap(True)
            layout.addWidget(info_label)
        else:
            # 所有数据完整
            complete_label = QLabel(
                "<p style='color: green; font-size: 14px;'>"
                "✅ 所有主指标都有当日数据，数据完整！"
                "</p>"
            )
            complete_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(complete_label)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        if missing_indicators:
            # 有缺失数据时的按钮
            use_latest_btn = QPushButton("使用最近数据")
            use_latest_btn.setProperty("buttonStyle", "primary")
            use_latest_btn.setToolTip("使用指标的最新有效数据计算今天的评分")
            use_latest_btn.clicked.connect(self._on_use_latest)
            button_layout.addWidget(use_latest_btn)
            
            skip_btn = QPushButton("跳过当日评分")
            skip_btn.setToolTip("计算历史数据评分，但不计算今天的评分")
            skip_btn.clicked.connect(self._on_skip)
            button_layout.addWidget(skip_btn)
            
            cancel_btn = QPushButton("取消")
            cancel_btn.clicked.connect(self._on_cancel)
            button_layout.addWidget(cancel_btn)
        else:
            # 数据完整时只有确认按钮
            ok_btn = QPushButton("确定")
            ok_btn.setProperty("buttonStyle", "primary")
            ok_btn.clicked.connect(self.accept)
            button_layout.addWidget(ok_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        # 应用样式
        self.setStyleSheet("""
            QDialog {
                background-color: white;
            }
            QLabel {
                color: #243043;
            }
            QTableWidget {
                border: 1px solid #E5E7EB;
                border-radius: 4px;
                background-color: white;
                gridline-color: #E5E7EB;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #DBEAFE;
                color: #1E40AF;
            }
            QHeaderView::section {
                background-color: #F3F4F6;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #2563EB;
                font-weight: 600;
                color: #243043;
            }
            QPushButton {
                padding: 8px 24px;
                border-radius: 6px;
                border: 1px solid #D1D5DB;
                background-color: white;
                color: #243043;
                font-weight: 500;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #F9FAFB;
                border-color: #9CA3AF;
            }
            QPushButton[buttonStyle="primary"] {
                background-color: #2563EB;
                color: white;
                border: none;
            }
            QPushButton[buttonStyle="primary"]:hover {
                background-color: #1D4ED8;
            }
            QPushButton:pressed {
                background-color: #E5E7EB;
            }
            QPushButton[buttonStyle="primary"]:pressed {
                background-color: #1E40AF;
            }
        """)
    
    def _on_use_latest(self):
        """用户选择使用最近数据"""
        self.user_choice = 'use_latest'
        self.accept()
    
    def _on_skip(self):
        """用户选择跳过评分"""
        self.user_choice = 'skip'
        self.accept()
    
    def _on_cancel(self):
        """用户取消"""
        self.user_choice = 'cancel'
        self.reject()
    
    def get_user_choice(self) -> str:
        """
        获取用户选择
        
        @returns {str} 'use_latest', 'skip', 'cancel', 或 None（数据完整）
        """
        if not self.completeness_report['missing_indicators']:
            return None  # 数据完整，无需选择
        
        return self.user_choice

