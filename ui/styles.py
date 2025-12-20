"""
样式管理模块

提供现代化白色主题的QSS样式，以便在主窗口中复用。
灵感来自: Fluent Design, Material Design, macOS Big Sur
"""

# 颜色定义
COLORS = {
    # 主色调 - 蓝色系
    'primary': '#2563EB',           # 主蓝色
    'primary_hover': '#3B82F6',     # 悬停蓝色
    'primary_pressed': '#1D4ED8',   # 按下蓝色
    'primary_light': '#DBEAFE',     # 浅蓝色背景
    
    # 成功/警告/错误色
    'success': '#10B981',           # 成功绿
    'warning': '#F59E0B',           # 警告橙
    'danger': '#EF4444',            # 错误红
    
    # 文字颜色
    'text_primary': '#111827',      # 主文字
    'text_secondary': '#6B7280',    # 次要文字
    'text_disabled': '#9CA3AF',     # 禁用文字
    
    # 背景颜色
    'bg_primary': '#FFFFFF',        # 主背景（纯白）
    'bg_secondary': '#F9FAFB',      # 次要背景
    'bg_tertiary': '#F3F4F6',       # 第三背景
    'bg_hover': '#F3F4F6',          # 悬停背景
    
    # 边框颜色
    'border_light': '#E5E7EB',      # 浅边框
    'border_normal': '#D1D5DB',     # 普通边框
    'border_strong': '#9CA3AF',     # 强边框
    
    # 特殊颜色
    'shadow': 'rgba(0, 0, 0, 0.05)',  # 阴影
    'overlay': 'rgba(0, 0, 0, 0.4)',  # 遮罩
}

# 现代化白色主题样式表
MAIN_WINDOW_QSS = f"""
/* ========================================
   全局样式
   ======================================== */
QWidget {{
    font-family: 'Segoe UI', 'Microsoft YaHei UI', 'PingFang SC', -apple-system, sans-serif;
    font-size: 13px;
    color: {COLORS['text_primary']};
    background-color: {COLORS['bg_secondary']};
}}

QMainWindow {{
    background-color: {COLORS['bg_secondary']};
}}

/* ========================================
   工具栏和菜单栏
   ======================================== */
QToolBar {{
    background-color: {COLORS['bg_primary']};
    border: none;
    border-bottom: 1px solid {COLORS['border_light']};
    padding: 4px;
    spacing: 4px;
}}

QMenuBar {{
    background-color: {COLORS['bg_primary']};
    border-bottom: 1px solid {COLORS['border_light']};
    padding: 4px 8px;
}}

QMenuBar::item {{
    background-color: transparent;
    padding: 6px 12px;
    border-radius: 4px;
}}

QMenuBar::item:selected {{
    background-color: {COLORS['bg_hover']};
}}

QMenu {{
    background-color: {COLORS['bg_primary']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 8px;
    padding: 4px;
}}

QMenu::item {{
    padding: 8px 24px 8px 12px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {COLORS['bg_hover']};
    color: {COLORS['primary']};
}}

/* ========================================
   状态栏
   ======================================== */
QStatusBar {{
    background-color: {COLORS['bg_primary']};
    color: {COLORS['text_secondary']};
    border-top: 1px solid {COLORS['border_light']};
    padding: 4px 8px;
    font-size: 12px;
}}

QStatusBar::item {{
    border: none;
}}

/* ========================================
   标签页
   ======================================== */
QTabWidget::pane {{
    border: 1px solid {COLORS['border_light']};
    border-radius: 8px;
    background: {COLORS['bg_primary']};
    top: -1px;
}}

QTabBar {{
    background-color: transparent;
}}

QTabBar::tab {{
    background: transparent;
    color: {COLORS['text_secondary']};
    padding: 10px 20px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 4px;
    font-weight: 500;
    border: 1px solid transparent;
}}

QTabBar::tab:hover {{
    background: {COLORS['bg_hover']};
    color: {COLORS['text_primary']};
}}

QTabBar::tab:selected {{
    background: {COLORS['bg_primary']};
    color: {COLORS['primary']};
    border: 1px solid {COLORS['border_light']};
    border-bottom: 1px solid {COLORS['bg_primary']};
}}

/* ========================================
   列表/树/表格视图
   ======================================== */
QListView, QTreeView, QTableView {{
    background-color: {COLORS['bg_primary']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {COLORS['primary_light']};
    selection-color: {COLORS['primary']};
    outline: none;
}}

QListView::item, QTreeView::item {{
    padding: 8px;
    border-radius: 4px;
    border: none;
}}

QListView::item:hover, QTreeView::item:hover {{
    background-color: {COLORS['bg_hover']};
}}

QListView::item:selected, QTreeView::item:selected {{
    background-color: {COLORS['primary_light']};
    color: {COLORS['primary']};
    font-weight: 500;
}}

QHeaderView::section {{
    background-color: {COLORS['bg_tertiary']};
    color: {COLORS['text_secondary']};
    padding: 8px;
    border: none;
    border-right: 1px solid {COLORS['border_light']};
    border-bottom: 1px solid {COLORS['border_light']};
    font-weight: 600;
    font-size: 12px;
}}

QHeaderView::section:first {{
    border-top-left-radius: 8px;
}}

QHeaderView::section:last {{
    border-top-right-radius: 8px;
    border-right: none;
}}

/* ========================================
   输入控件
   ======================================== */
QComboBox, QLineEdit, QDateEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {COLORS['bg_primary']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 6px;
    padding: 6px 10px;
    color: {COLORS['text_primary']};
    selection-background-color: {COLORS['primary_light']};
    selection-color: {COLORS['primary']};
}}

QComboBox:hover, QLineEdit:hover, QDateEdit:hover {{
    border-color: {COLORS['border_normal']};
}}

QComboBox:focus, QLineEdit:focus, QDateEdit:focus {{
    border-color: {COLORS['primary']};
    border-width: 2px;
    padding: 5px 9px;
}}

QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {COLORS['text_secondary']};
    margin-right: 4px;
}}

QDateEdit::drop-down {{
    border: none;
    padding-right: 8px;
}}

QDateEdit::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {COLORS['text_secondary']};
    margin-right: 4px;
}}

/* ========================================
   按钮
   ======================================== */
QPushButton {{
    background-color: {COLORS['primary']};
    color: {COLORS['bg_primary']};
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 500;
    font-size: 13px;
}}

QPushButton:hover {{
    background-color: {COLORS['primary_hover']};
}}

QPushButton:pressed {{
    background-color: {COLORS['primary_pressed']};
}}

QPushButton:disabled {{
    background-color: {COLORS['bg_tertiary']};
    color: {COLORS['text_disabled']};
}}

/* 次要按钮样式 */
QPushButton[buttonStyle="secondary"] {{
    background-color: {COLORS['bg_primary']};
    color: {COLORS['primary']};
    border: 1px solid {COLORS['border_normal']};
}}

QPushButton[buttonStyle="secondary"]:hover {{
    background-color: {COLORS['bg_hover']};
    border-color: {COLORS['primary']};
}}

/* 危险按钮样式 */
QPushButton[buttonStyle="danger"] {{
    background-color: {COLORS['danger']};
}}

QPushButton[buttonStyle="danger"]:hover {{
    background-color: #DC2626;
}}

/* 成功按钮样式 */
QPushButton[buttonStyle="success"] {{
    background-color: {COLORS['success']};
}}

QPushButton[buttonStyle="success"]:hover {{
    background-color: #059669;
}}

/* ========================================
   滚动条
   ======================================== */
QScrollBar:vertical {{
    background-color: transparent;
    width: 12px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS['border_normal']};
    border-radius: 6px;
    min-height: 30px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS['border_strong']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    background: none;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 12px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background-color: {COLORS['border_normal']};
    border-radius: 6px;
    min-width: 30px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {COLORS['border_strong']};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
    background: none;
}}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}

/* ========================================
   分割器
   ======================================== */
QSplitter::handle {{
    background-color: {COLORS['border_light']};
    width: 1px;
    height: 1px;
}}

QSplitter::handle:hover {{
    background-color: {COLORS['primary']};
}}

/* ========================================
   框架和分组框
   ======================================== */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    /* HLine = 4, VLine = 5 */
    border: none;
    background-color: {COLORS['border_light']};
}}

QGroupBox {{
    background-color: {COLORS['bg_primary']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: {COLORS['text_primary']};
    left: 12px;
    background-color: {COLORS['bg_primary']};
}}

/* ========================================
   进度条
   ======================================== */
QProgressBar {{
    border: 1px solid {COLORS['border_light']};
    border-radius: 6px;
    background-color: {COLORS['bg_tertiary']};
    text-align: center;
    color: {COLORS['text_secondary']};
    font-size: 11px;
}}

QProgressBar::chunk {{
    background-color: {COLORS['primary']};
    border-radius: 5px;
}}

/* ========================================
   提示框
   ======================================== */
QToolTip {{
    background-color: {COLORS['text_primary']};
    color: {COLORS['bg_primary']};
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* ========================================
   消息框
   ======================================== */
QMessageBox {{
    background-color: {COLORS['bg_primary']};
}}

QMessageBox QLabel {{
    color: {COLORS['text_primary']};
    font-size: 13px;
}}

QMessageBox QPushButton {{
    min-width: 80px;
    padding: 8px 16px;
}}

/* ========================================
   自定义类
   ======================================== */
/* 控制面板 */
.control-panel {{
    background-color: {COLORS['bg_primary']};
    border-right: 1px solid {COLORS['border_light']};
}}

/* 图表容器 */
.chart-container {{
    background-color: {COLORS['bg_primary']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 8px;
}}

/* 标题标签 */
QLabel[labelStyle="title"] {{
    font-size: 16px;
    font-weight: 600;
    color: {COLORS['text_primary']};
    padding: 4px 0;
}}

/* 副标题标签 */
QLabel[labelStyle="subtitle"] {{
    font-size: 14px;
    font-weight: 500;
    color: {COLORS['text_secondary']};
    padding: 2px 0;
}}

/* 小标签 */
QLabel[labelStyle="small"] {{
    font-size: 11px;
    color: {COLORS['text_secondary']};
}}

/* 徽章样式 */
QLabel[badgeStyle="primary"] {{
    background-color: {COLORS['primary_light']};
    color: {COLORS['primary']};
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}

QLabel[badgeStyle="success"] {{
    background-color: #D1FAE5;
    color: {COLORS['success']};
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}

QLabel[badgeStyle="warning"] {{
    background-color: #FEF3C7;
    color: {COLORS['warning']};
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}

QLabel[badgeStyle="danger"] {{
    background-color: #FEE2E2;
    color: {COLORS['danger']};
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}
"""

# 图表样式配置
CHART_STYLE = {
    'background': COLORS['bg_primary'],
    'foreground': COLORS['text_primary'],
    'grid_color': COLORS['border_light'],
    'text_color': COLORS['text_secondary'],
    'line_colors': [
        COLORS['primary'],
        COLORS['success'],
        COLORS['warning'],
        COLORS['danger'],
        '#8B5CF6',  # 紫色
        '#EC4899',  # 粉色
        '#14B8A6',  # 青色
        '#F97316',  # 橙色
    ],
    'font_family': 'Segoe UI, Microsoft YaHei UI, PingFang SC',
    'font_size': 11,
}

def get_lamp_color(lamp: str) -> str:
    """
    获取灯色对应的颜色值
    
    @param {str} lamp - 灯色代码 (red/yellow/green)
    @returns {str} 十六进制颜色值
    """
    lamp_colors = {
        'red': COLORS['danger'],
        'yellow': COLORS['warning'],
        'green': COLORS['success'],
    }
    return lamp_colors.get(lamp, COLORS['text_secondary'])

def get_score_color(score: float) -> str:
    """
    根据评分获取颜色
    
    @param {float} score - 评分值 (0-100)
    @returns {str} 十六进制颜色值
    """
    if score >= 70:
        return COLORS['success']
    elif score >= 50:
        return COLORS['warning']
    else:
        return COLORS['danger']

# 字体大小配置
FONT_SIZES = {
    'small': {
        'base': 11,      # 基础字号
        'title': 14,     # 标题
        'subtitle': 12,  # 副标题
        'small': 10,     # 小字
    },
    'medium': {
        'base': 13,      # 基础字号（默认）
        'title': 16,     # 标题
        'subtitle': 14,  # 副标题
        'small': 11,     # 小字
    },
    'large': {
        'base': 15,      # 基础字号
        'title': 18,     # 标题
        'subtitle': 16,  # 副标题
        'small': 13,     # 小字
    },
}

def get_styled_qss(font_size: str = 'medium') -> str:
    """
    获取指定字体大小的样式表
    
    @param {str} font_size - 字体大小 ('small', 'medium', 'large')
    @returns {str} QSS样式表
    """
    sizes = FONT_SIZES.get(font_size, FONT_SIZES['medium'])
    base = sizes['base']
    title = sizes['title']
    subtitle = sizes['subtitle']
    small = sizes['small']
    
    # 使用f-string替换字体大小
    styled_qss = f"""
/* ========================================
   全局样式
   ======================================== */
QWidget {{
    font-family: 'Segoe UI', 'Microsoft YaHei UI', 'PingFang SC', -apple-system, sans-serif;
    font-size: {base}px;
    color: {COLORS['text_primary']};
    background-color: {COLORS['bg_secondary']};
}}

QMainWindow {{
    background-color: {COLORS['bg_secondary']};
}}

/* ========================================
   工具栏和菜单栏
   ======================================== */
QToolBar {{
    background-color: {COLORS['bg_primary']};
    border: none;
    border-bottom: 1px solid {COLORS['border_light']};
    padding: 4px;
    spacing: 4px;
}}

QMenuBar {{
    background-color: {COLORS['bg_primary']};
    border-bottom: 1px solid {COLORS['border_light']};
    padding: 4px 8px;
    font-size: {base}px;
}}

QMenuBar::item {{
    background-color: transparent;
    padding: 6px 12px;
    border-radius: 4px;
}}

QMenuBar::item:selected {{
    background-color: {COLORS['bg_hover']};
}}

QMenu {{
    background-color: {COLORS['bg_primary']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 8px;
    padding: 4px;
    font-size: {base}px;
}}

QMenu::item {{
    padding: 8px 24px 8px 12px;
    border-radius: 4px;
}}

QMenu::item:selected {{
    background-color: {COLORS['bg_hover']};
    color: {COLORS['primary']};
}}

/* ========================================
   状态栏
   ======================================== */
QStatusBar {{
    background-color: {COLORS['bg_primary']};
    color: {COLORS['text_secondary']};
    border-top: 1px solid {COLORS['border_light']};
    padding: 4px 8px;
    font-size: {small}px;
}}

QStatusBar::item {{
    border: none;
}}

/* ========================================
   标签页
   ======================================== */
QTabWidget::pane {{
    border: 1px solid {COLORS['border_light']};
    border-radius: 8px;
    background: {COLORS['bg_primary']};
    top: -1px;
}}

QTabBar {{
    background-color: transparent;
    font-size: {base}px;
}}

QTabBar::tab {{
    background: transparent;
    color: {COLORS['text_secondary']};
    padding: 10px 20px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 4px;
    font-weight: 500;
    border: 1px solid transparent;
}}

QTabBar::tab:hover {{
    background: {COLORS['bg_hover']};
    color: {COLORS['text_primary']};
}}

QTabBar::tab:selected {{
    background: {COLORS['bg_primary']};
    color: {COLORS['primary']};
    border: 1px solid {COLORS['border_light']};
    border-bottom: 1px solid {COLORS['bg_primary']};
}}

/* ========================================
   列表/树/表格视图
   ======================================== */
QListView, QTreeView, QTableView {{
    background-color: {COLORS['bg_primary']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {COLORS['primary_light']};
    selection-color: {COLORS['primary']};
    outline: none;
    font-size: {base}px;
}}

QListView::item, QTreeView::item {{
    padding: 8px;
    border-radius: 4px;
    border: none;
}}

QListView::item:hover, QTreeView::item:hover {{
    background-color: {COLORS['bg_hover']};
}}

QListView::item:selected, QTreeView::item:selected {{
    background-color: {COLORS['primary_light']};
    color: {COLORS['primary']};
    font-weight: 500;
}}

QHeaderView::section {{
    background-color: {COLORS['bg_tertiary']};
    color: {COLORS['text_secondary']};
    padding: 8px;
    border: none;
    border-right: 1px solid {COLORS['border_light']};
    border-bottom: 1px solid {COLORS['border_light']};
    font-weight: 600;
    font-size: {small}px;
}}

QHeaderView::section:first {{
    border-top-left-radius: 8px;
}}

QHeaderView::section:last {{
    border-top-right-radius: 8px;
    border-right: none;
}}

/* ========================================
   输入控件
   ======================================== */
QComboBox, QLineEdit, QDateEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {COLORS['bg_primary']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 6px;
    padding: 6px 10px;
    color: {COLORS['text_primary']};
    selection-background-color: {COLORS['primary_light']};
    selection-color: {COLORS['primary']};
    font-size: {base}px;
}}

QComboBox:hover, QLineEdit:hover, QDateEdit:hover {{
    border-color: {COLORS['border_normal']};
}}

QComboBox:focus, QLineEdit:focus, QDateEdit:focus {{
    border-color: {COLORS['primary']};
    border-width: 2px;
    padding: 5px 9px;
}}

QComboBox::drop-down {{
    border: none;
    padding-right: 8px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {COLORS['text_secondary']};
    margin-right: 4px;
}}

QDateEdit::drop-down {{
    border: none;
    padding-right: 8px;
}}

QDateEdit::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {COLORS['text_secondary']};
    margin-right: 4px;
}}

/* ========================================
   按钮
   ======================================== */
QPushButton {{
    background-color: {COLORS['primary']};
    color: {COLORS['bg_primary']};
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 500;
    font-size: {base}px;
}}

QPushButton:hover {{
    background-color: {COLORS['primary_hover']};
}}

QPushButton:pressed {{
    background-color: {COLORS['primary_pressed']};
}}

QPushButton:disabled {{
    background-color: {COLORS['bg_tertiary']};
    color: {COLORS['text_disabled']};
}}

/* 次要按钮样式 */
QPushButton[buttonStyle="secondary"] {{
    background-color: {COLORS['bg_primary']};
    color: {COLORS['primary']};
    border: 1px solid {COLORS['border_normal']};
}}

QPushButton[buttonStyle="secondary"]:hover {{
    background-color: {COLORS['bg_hover']};
    border-color: {COLORS['primary']};
}}

/* 危险按钮样式 */
QPushButton[buttonStyle="danger"] {{
    background-color: {COLORS['danger']};
}}

QPushButton[buttonStyle="danger"]:hover {{
    background-color: #DC2626;
}}

/* 成功按钮样式 */
QPushButton[buttonStyle="success"] {{
    background-color: {COLORS['success']};
}}

QPushButton[buttonStyle="success"]:hover {{
    background-color: #059669;
}}

/* ========================================
   滚动条
   ======================================== */
QScrollBar:vertical {{
    background-color: transparent;
    width: 12px;
    margin: 0;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS['border_normal']};
    border-radius: 6px;
    min-height: 30px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS['border_strong']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
    background: none;
}}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 12px;
    margin: 0;
}}

QScrollBar::handle:horizontal {{
    background-color: {COLORS['border_normal']};
    border-radius: 6px;
    min-width: 30px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {COLORS['border_strong']};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
    background: none;
}}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}

/* ========================================
   分割器
   ======================================== */
QSplitter::handle {{
    background-color: {COLORS['border_light']};
    width: 1px;
    height: 1px;
}}

QSplitter::handle:hover {{
    background-color: {COLORS['primary']};
}}

/* ========================================
   框架和分组框
   ======================================== */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    /* HLine = 4, VLine = 5 */
    border: none;
    background-color: {COLORS['border_light']};
}}

QGroupBox {{
    background-color: {COLORS['bg_primary']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: 600;
    font-size: {base}px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: {COLORS['text_primary']};
    left: 12px;
    background-color: {COLORS['bg_primary']};
}}

/* ========================================
   进度条
   ======================================== */
QProgressBar {{
    border: 1px solid {COLORS['border_light']};
    border-radius: 6px;
    background-color: {COLORS['bg_tertiary']};
    text-align: center;
    color: {COLORS['text_secondary']};
    font-size: {small}px;
}}

QProgressBar::chunk {{
    background-color: {COLORS['primary']};
    border-radius: 5px;
}}

/* ========================================
   提示框
   ======================================== */
QToolTip {{
    background-color: {COLORS['text_primary']};
    color: {COLORS['bg_primary']};
    border: none;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: {small}px;
}}

/* ========================================
   消息框
   ======================================== */
QMessageBox {{
    background-color: {COLORS['bg_primary']};
    font-size: {base}px;
}}

QMessageBox QLabel {{
    color: {COLORS['text_primary']};
    font-size: {base}px;
}}

QMessageBox QPushButton {{
    min-width: 80px;
    padding: 8px 16px;
}}

/* ========================================
   自定义类
   ======================================== */
/* 控制面板 */
.control-panel {{
    background-color: {COLORS['bg_primary']};
    border-right: 1px solid {COLORS['border_light']};
}}

/* 图表容器 */
.chart-container {{
    background-color: {COLORS['bg_primary']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 8px;
}}

/* 标题标签 */
QLabel[labelStyle="title"] {{
    font-size: {title}px;
    font-weight: 600;
    color: {COLORS['text_primary']};
    padding: 4px 0;
}}

/* 副标题标签 */
QLabel[labelStyle="subtitle"] {{
    font-size: {subtitle}px;
    font-weight: 500;
    color: {COLORS['text_secondary']};
    padding: 2px 0;
}}

/* 小标签 */
QLabel[labelStyle="small"] {{
    font-size: {small}px;
    color: {COLORS['text_secondary']};
}}

/* 徽章样式 */
QLabel[badgeStyle="primary"] {{
    background-color: {COLORS['primary_light']};
    color: {COLORS['primary']};
    border-radius: 10px;
    padding: 2px 8px;
    font-size: {small}px;
    font-weight: 600;
}}

QLabel[badgeStyle="success"] {{
    background-color: #D1FAE5;
    color: {COLORS['success']};
    border-radius: 10px;
    padding: 2px 8px;
    font-size: {small}px;
    font-weight: 600;
}}

QLabel[badgeStyle="warning"] {{
    background-color: #FEF3C7;
    color: {COLORS['warning']};
    border-radius: 10px;
    padding: 2px 8px;
    font-size: {small}px;
    font-weight: 600;
}}

QLabel[badgeStyle="danger"] {{
    background-color: #FEE2E2;
    color: {COLORS['danger']};
    border-radius: 10px;
    padding: 2px 8px;
    font-size: {small}px;
    font-weight: 600;
}}
"""
    
    return styled_qss
