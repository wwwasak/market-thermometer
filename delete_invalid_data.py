"""
删除特定日期的无效数据（如半天交易日）

用途：
- 删除半天交易日的成交额/成交量类指标数据
- 删除数据异常的特定日期数据
- 使用ffill机制会自动用前一交易日的有效数据填充

使用方法：
1. 在invalid_data_entries列表中配置需要删除的数据
2. 运行脚本: python delete_invalid_data.py --execute
3. 在GUI中点击"计算评分"重新计算

作者：AI Assistant
日期：2025-12-27
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Dict

# 数据库路径
DB_PATH = "data/market_thermo_3years_auto.db"  # 正确的数据库路径

# ============ 配置需要删除的无效数据 ============
# 每个条目包含：code（指标代码）、date（日期）、market（市场）、reason（原因说明）
invalid_data_entries: List[Dict[str, str]] = [
    # CN市场
    {
        'code': 'NORTH_TURNOVER_SHARE',
        'date': '2025-12-24',
        'market': 'CN',
        'reason': '平安夜半天交易，成交额不具代表性'
    }
    
    # 未来可以添加更多无效日期
    # 例如：春节前、国庆前的半天交易日
    # {
    #     'code': 'NORTH_TURNOVER_SHARE',
    #     'date': '2025-01-28',  # 春节前（示例）
    #     'market': 'CN',
    #     'reason': '春节前半天交易'
    # },
]


def check_database_exists() -> bool:
    """检查数据库是否存在"""
    db_file = Path(DB_PATH)
    if not db_file.exists():
        print(f"[ERROR] 数据库文件不存在: {DB_PATH}")
        print(f"[提示] 请确认数据库路径是否正确")
        return False
    return True


def get_series_id(cursor: sqlite3.Cursor, code: str) -> int:
    """
    获取指标的series_id
    
    @param {sqlite3.Cursor} cursor - 数据库游标
    @param {str} code - 指标代码
    @returns {int} series_id，如果不存在返回None
    """
    cursor.execute(
        "SELECT id FROM series_meta WHERE code = ?",
        (code,)
    )
    result = cursor.fetchone()
    return result[0] if result else None


def check_data_exists(cursor: sqlite3.Cursor, series_id: int, date: str) -> bool:
    """
    检查指定日期的数据是否存在
    
    @param {sqlite3.Cursor} cursor - 数据库游标
    @param {int} series_id - 序列ID
    @param {str} date - 日期字符串
    @returns {bool} 是否存在
    """
    cursor.execute(
        """
        SELECT COUNT(*) FROM series_data 
        WHERE series_id = ? AND date = ?
        """,
        (series_id, date)
    )
    count = cursor.fetchone()[0]
    return count > 0


def delete_regimes_by_date(
    cursor: sqlite3.Cursor,
    date: str,
    market: str,
    dry_run: bool = False
) -> int:
    """
    删除regimes表中指定日期的评分数据
    
    @param {sqlite3.Cursor} cursor - 数据库游标
    @param {str} date - 日期
    @param {str} market - 市场（CN或US）
    @param {bool} dry_run - 是否为试运行
    @returns {int} 删除的记录数
    """
    # 检查是否存在
    cursor.execute(
        "SELECT COUNT(*) FROM regimes WHERE date = ? AND market = ?",
        (date, market)
    )
    count = cursor.fetchone()[0]
    
    if count == 0:
        return 0
    
    if dry_run:
        print(f"[DRY-RUN] 将删除regimes表中 {market}市场 {date} 的评分数据（{count}条）")
        return count
    
    # 删除
    cursor.execute(
        "DELETE FROM regimes WHERE date = ? AND market = ?",
        (date, market)
    )
    
    deleted = cursor.rowcount
    if deleted > 0:
        print(f"[OK] 删除regimes表中 {market}市场 {date} 的评分数据（{deleted}条）")
    
    return deleted


def delete_invalid_entry(
    cursor: sqlite3.Cursor, 
    entry: Dict[str, str],
    dry_run: bool = False
) -> bool:
    """
    删除单个无效数据条目
    
    @param {sqlite3.Cursor} cursor - 数据库游标
    @param {Dict[str, str]} entry - 无效数据条目
    @param {bool} dry_run - 是否为试运行（不实际删除）
    @returns {bool} 是否成功
    """
    code = entry['code']
    date = entry['date']
    reason = entry['reason']
    market = entry.get('market', 'CN')  # 默认CN市场
    
    print(f"\n处理: {code} @ {date} ({market}市场)")
    print(f"原因: {reason}")
    
    # 获取series_id
    series_id = get_series_id(cursor, code)
    
    if series_id is None:
        print(f"[WARN] 未找到指标: {code}")
        return False
    
    print(f"[INFO] 找到指标，series_id = {series_id}")
    
    # 检查数据是否存在
    data_exists = check_data_exists(cursor, series_id, date)
    
    if not data_exists:
        print(f"[INFO] series_data表中该日期没有数据")
    else:
        if dry_run:
            print(f"[DRY-RUN] 将删除series_data表中 {code} 在 {date} 的数据")
        else:
            # 删除series_data数据
            cursor.execute(
                """
                DELETE FROM series_data 
                WHERE series_id = ? AND date = ?
                """,
                (series_id, date)
            )
            
            deleted_count = cursor.rowcount
            
            if deleted_count > 0:
                print(f"[OK] 成功删除series_data表中 {deleted_count} 条记录")
            else:
                print(f"[WARN] 未删除任何series_data记录")
    
    # 同时删除regimes表中该日期的评分数据
    print(f"[INFO] 检查regimes表中 {market}市场 {date} 的评分数据...")
    regimes_deleted = delete_regimes_by_date(cursor, date, market, dry_run)
    
    return True


def main(dry_run: bool = False):
    """
    主函数
    
    @param {bool} dry_run - 是否为试运行模式
    """
    print("=" * 80)
    print("删除无效数据脚本")
    print("=" * 80)
    
    if dry_run:
        print("\n[DRY-RUN 模式] 只显示将要删除的内容，不实际删除\n")
    
    # 检查数据库
    if not check_database_exists():
        return
    
    print(f"\n[INFO] 连接数据库: {DB_PATH}")
    print(f"[INFO] 待处理条目数: {len(invalid_data_entries)}")
    
    # 连接数据库
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    success_count = 0
    fail_count = 0
    
    try:
        # 处理每个无效数据条目
        for i, entry in enumerate(invalid_data_entries, 1):
            print(f"\n{'=' * 60}")
            print(f"[{i}/{len(invalid_data_entries)}]")
            
            if delete_invalid_entry(cursor, entry, dry_run):
                success_count += 1
            else:
                fail_count += 1
        
        # 提交更改
        if not dry_run:
            conn.commit()
            print(f"\n{'=' * 80}")
            print(f"[完成] 数据库更改已提交")
        
    except Exception as e:
        print(f"\n[ERROR] 发生错误: {e}")
        conn.rollback()
        print("[INFO] 已回滚所有更改")
        raise
    
    finally:
        conn.close()
    
    # 总结
    print(f"\n{'=' * 80}")
    print("删除结果总结")
    print("=" * 80)
    print(f"成功处理: {success_count} 个条目")
    print(f"失败/跳过: {fail_count} 个条目")
    
    if dry_run:
        print(f"\n[提示] 这是试运行模式，没有实际删除数据")
        print(f"[提示] 如需实际删除，请运行: python delete_invalid_data.py --execute")
    else:
        print(f"\n[提示] 数据已删除，请执行以下步骤：")
        print(f"  1. 在GUI中切换到对应市场")
        print(f"  2. 点击'计算评分'按钮")
        print(f"  3. ffill机制会自动使用前一交易日的数据填充")
        print(f"  4. 查看评分表，确认数据日期正确")
    
    print("=" * 80)


if __name__ == "__main__":
    import sys
    
    # 检查命令行参数
    execute = '--execute' in sys.argv
    skip_confirm = '--yes' in sys.argv
    
    if execute:
        # 实际执行删除
        if not skip_confirm:
            print("[WARNING] 将实际删除数据库中的数据！")
            response = input("确认要继续吗？(输入 yes 确认): ")
            if response.lower() != 'yes':
                print("[取消] 操作已取消")
                sys.exit(0)
        
        main(dry_run=False)
    else:
        # 试运行模式（默认）
        main(dry_run=True)
        print(f"\n运行完整删除请执行: python delete_invalid_data.py --execute --yes")


