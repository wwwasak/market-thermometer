"""
样式管理模块

提供现代化浅色主题的QSS样式，以便在主窗口中复用。
"""

MAIN_WINDOW_QSS = """
QWidget {
    font-family: 'Segoe UI', 'Microsoft YaHei', 'PingFang SC', sans-serif;
    font-size: 12px;
    color: #243043;
    background-color: #F6F7FB;
}

QMainWindow {
    background-color: #F6F7FB;
}

QToolBar, QMenuBar {
    background-color: #FFFFFF;
    border: 1px solid #E6ECF5;
}

QStatusBar {
    background-color: #FFFFFF;
    color: #5B6470;
    border-top: 1px solid #E6ECF5;
}

QTabWidget::pane {
    border: 1px solid #D7E1EC;
    border-radius: 6px;
    background: #FFFFFF;
}

QTabBar::tab {
    background: #EFF3F8;
    color: #5B6470;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #FFFFFF;
    color: #1A73E8;
    border: 1px solid #D7E1EC;
    border-bottom: 1px solid #FFFFFF;
}

QListView, QTreeView, QTableView {
    background-color: #FFFFFF;
    border: 1px solid #D7E1EC;
    border-radius: 6px;
    padding: 4px;
    selection-background-color: #E4ECF9;
    selection-color: #1A73E8;
}

QHeaderView::section {
    background-color: #F2F5FA;
    color: #5B6470;
    padding: 4px;
    border: none;
}

QComboBox, QLineEdit, QDateEdit {
    background-color: #FFFFFF;
    border: 1px solid #D7E1EC;
    border-radius: 6px;
    padding: 4px 8px;
    color: #243043;
    selection-background-color: #E4ECF9;
}

QComboBox::drop-down, QDateEdit::drop-down {
    border: none;
}

QPushButton {
    background-color: #1A73E8;
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
}

QPushButton:hover {
    background-color: #3A83EC;
}

QPushButton:pressed {
    background-color: #155FC2;
}

QSplitter::handle {
    background-color: #D7E1EC;
}
"""

