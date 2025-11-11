"""
应用入口

提供命令行启动PyQt6 GUI的入口点。
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ui.main_window import launch_gui


def _determine_database_url(path: str | None) -> str | None:
    if not path:
        return None
    db_path = Path(path)
    if db_path.exists() and db_path.suffix == ".db":
        return f"sqlite:///{db_path.as_posix()}"
    return path


def main():
    parser = argparse.ArgumentParser(description="双市场温度计 - GUI终端")
    parser.add_argument(
        "--database",
        help="指定SQLite数据库路径或完整SQLAlchemy URL（默认读取配置文件）",
        default=None,
    )
    args = parser.parse_args()

    database_url = _determine_database_url(args.database)
    launch_gui(database_url=database_url)


if __name__ == "__main__":
    main()

