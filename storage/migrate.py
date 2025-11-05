"""
数据库迁移和初始化模块

提供数据库初始化、迁移和备份功能
"""

import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import create_engine, inspect

from storage.models import Base, get_table_names
from storage.repository import Repository
from core.config import Config


def init_database(database_url: str = 'sqlite:///market_thermo.db', force: bool = False) -> bool:
    """
    初始化数据库
    
    创建所有表并加载默认配置
    
    @param {str} database_url - 数据库连接字符串
    @param {bool} force - 是否强制重建（会删除现有数据）
    @returns {bool} 是否成功
    """
    try:
        engine = create_engine(database_url, echo=False)
        
        if force:
            print("Warning: Force mode enabled. Dropping all existing tables...")
            Base.metadata.drop_all(engine)
        
        # 创建所有表
        Base.metadata.create_all(engine)
        
        print(f"[OK] Database initialized: {database_url}")
        print(f"[OK] Created tables: {', '.join(get_table_names())}")
        
        # 加载默认配置
        repo = Repository(database_url)
        config = Config()
        default_params = config.get_all()
        
        params_id = repo.save_params(default_params, version='default', set_active=True)
        print(f"[OK] Loaded default configuration (params_id={params_id})")
        
        # 添加默认指标元数据
        _init_default_indicators(repo, config)
        
        return True
    
    except Exception as e:
        print(f"[ERROR] Error initializing database: {e}")
        import traceback
        traceback.print_exc()
        return False


def _init_default_indicators(repo: Repository, config: Config):
    """初始化默认指标元数据"""
    print("\n[OK] Initializing default indicators...")
    
    # CN市场主要指标
    cn_main = config.get('indicators.CN.main', [])
    for ind in cn_main:
        repo.add_series_meta(
            code=ind['code'],
            name=ind['name'],
            market='CN',
            role='main',
            direction=ind.get('direction'),
            transform=ind.get('transform'),
            z_type=ind.get('z_type'),
            z_window=ind.get('z_window'),
            source=ind.get('source'),
            ticker=ind.get('ticker', '')
        )
    
    # CN市场观察者
    cn_observers = config.get('indicators.CN.observers', [])
    for ind in cn_observers:
        repo.add_series_meta(
            code=ind['code'],
            name=ind['name'],
            market='CN',
            role=ind.get('role', 'observer'),
            direction=ind.get('direction'),
            transform=ind.get('transform'),
            source=ind.get('source'),
            ticker=ind.get('ticker', '')
        )
    
    # US市场主要指标
    us_main = config.get('indicators.US.main', [])
    for ind in us_main:
        ticker = ind.get('ticker')
        if isinstance(ticker, list):
            ticker = ','.join(ticker)
        
        repo.add_series_meta(
            code=ind['code'],
            name=ind['name'],
            market='US',
            role='main',
            direction=ind.get('direction'),
            transform=ind.get('transform'),
            z_type=ind.get('z_type'),
            z_window=ind.get('z_window'),
            source=ind.get('source'),
            ticker=ticker
        )
    
    # US市场观察者
    us_observers = config.get('indicators.US.observers', [])
    for ind in us_observers:
        ticker = ind.get('ticker')
        if isinstance(ticker, list):
            ticker = ','.join(ticker)
        
        repo.add_series_meta(
            code=ind['code'],
            name=ind['name'],
            market='US',
            role=ind.get('role', 'observer'),
            direction=ind.get('direction'),
            transform=ind.get('transform'),
            z_type=ind.get('z_type'),
            z_window=ind.get('z_window'),
            source=ind.get('source'),
            ticker=ticker
        )
    
    print(f"  [OK] Added {len(cn_main)} CN main indicators")
    print(f"  [OK] Added {len(cn_observers)} CN observers")
    print(f"  [OK] Added {len(us_main)} US main indicators")
    print(f"  [OK] Added {len(us_observers)} US observers")


def backup_database(
    database_path: str = 'market_thermo.db',
    backup_dir: str = 'backups'
) -> Optional[str]:
    """
    备份数据库
    
    @param {str} database_path - 数据库文件路径
    @param {str} backup_dir - 备份目录
    @returns {Optional[str]} 备份文件路径，失败返回None
    """
    try:
        db_file = Path(database_path)
        if not db_file.exists():
            print(f"❌ Database file not found: {database_path}")
            return None
        
        # 创建备份目录
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)
        
        # 生成备份文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = backup_path / f"{db_file.stem}_backup_{timestamp}{db_file.suffix}"
        
        # 复制文件
        shutil.copy2(db_file, backup_file)
        
        print(f"[OK] Database backed up to: {backup_file}")
        return str(backup_file)
    
    except Exception as e:
        print(f"[ERROR] Error backing up database: {e}")
        return None


def restore_database(
    backup_file: str,
    database_path: str = 'market_thermo.db',
    confirm: bool = True
) -> bool:
    """
    从备份恢复数据库
    
    @param {str} backup_file - 备份文件路径
    @param {str} database_path - 目标数据库路径
    @param {bool} confirm - 是否需要确认（生产环境应为True）
    @returns {bool} 是否成功
    """
    try:
        backup_path = Path(backup_file)
        if not backup_path.exists():
            print(f"[ERROR] Backup file not found: {backup_file}")
            return False
        
        db_file = Path(database_path)
        
        if confirm and db_file.exists():
            print(f"Warning: This will overwrite existing database: {database_path}")
            response = input("Continue? (yes/no): ")
            if response.lower() != 'yes':
                print("Restore cancelled.")
                return False
        
        # 复制备份文件
        shutil.copy2(backup_path, db_file)
        
        print(f"[OK] Database restored from: {backup_file}")
        return True
    
    except Exception as e:
        print(f"[ERROR] Error restoring database: {e}")
        return False


def check_database_integrity(database_url: str = 'sqlite:///market_thermo.db') -> Dict[str, Any]:
    """
    检查数据库完整性
    
    @returns {Dict} 检查结果
    """
    try:
        engine = create_engine(database_url, echo=False)
        inspector = inspect(engine)
        
        # 检查表是否存在
        existing_tables = inspector.get_table_names()
        expected_tables = get_table_names()
        
        missing_tables = set(expected_tables) - set(existing_tables)
        extra_tables = set(existing_tables) - set(expected_tables)
        
        # 统计数据
        repo = Repository(database_url)
        db_info = repo.get_database_info()
        
        result = {
            'status': 'ok' if not missing_tables else 'incomplete',
            'existing_tables': existing_tables,
            'missing_tables': list(missing_tables),
            'extra_tables': list(extra_tables),
            'statistics': db_info
        }
        
        # 打印报告
        print("\n" + "=" * 60)
        print("Database Integrity Check")
        print("=" * 60)
        print(f"Status: {result['status'].upper()}")
        print(f"Tables: {len(existing_tables)}/{len(expected_tables)}")
        
        if missing_tables:
            print(f"[WARNING] Missing tables: {', '.join(missing_tables)}")
        
        if extra_tables:
            print(f"[INFO] Extra tables: {', '.join(extra_tables)}")
        
        print("\nStatistics:")
        for key, value in db_info.items():
            print(f"  {key}: {value}")
        
        return result
    
    except Exception as e:
        print(f"[ERROR] Error checking database: {e}")
        return {'status': 'error', 'message': str(e)}


def upgrade_database(database_url: str = 'sqlite:///market_thermo.db'):
    """
    升级数据库（用于版本迁移）
    
    目前只是占位符，未来可以添加版本迁移逻辑
    """
    print("Database upgrade functionality not yet implemented.")
    print("For major schema changes, consider:")
    print("  1. Backup current database")
    print("  2. Export data to CSV")
    print("  3. Initialize new database with init_database(force=True)")
    print("  4. Re-import data")


# CLI接口（可以通过命令行调用）

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python -m storage.migrate init [--force]")
        print("  python -m storage.migrate backup")
        print("  python -m storage.migrate check")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'init':
        force = '--force' in sys.argv
        init_database(force=force)
    
    elif command == 'backup':
        backup_database()
    
    elif command == 'check':
        check_database_integrity()
    
    elif command == 'restore':
        if len(sys.argv) < 3:
            print("Usage: python -m storage.migrate restore <backup_file>")
            sys.exit(1)
        backup_file = sys.argv[2]
        restore_database(backup_file, confirm=True)
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

