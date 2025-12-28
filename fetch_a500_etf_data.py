"""
获取A500相关ETF资金流向数据并更新数据库

功能：
1. 获取多只A500宽基ETF的主力资金流向数据
2. 汇总计算综合资金流
3. 计算5日滚动净申赎
4. 更新数据库中ETF_NETFLOW_5D的历史数据

使用方法：
python fetch_a500_etf_data.py --days 90  # 获取最近90天数据
python fetch_a500_etf_data.py --start 2022-01-01 --end 2025-12-27  # 指定日期范围

作者：AI Assistant
日期：2025-12-27
"""

import sys
import argparse
from datetime import datetime, timedelta
import pandas as pd
import sqlite3

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

try:
    import akshare as ak
    print("[OK] akshare 导入成功")
except ImportError:
    print("[ERROR] 请先安装 akshare: pip install akshare")
    sys.exit(1)


# ============ 配置 ============

# A500相关ETF列表（根据市场情况调整）
A500_ETF_LIST = [
    {"symbol": "159352", "market": "sz", "label": "南方中证A500ETF"},
    {"symbol": "563080", "market": "sh", "label": "华夏中证A500ETF"},
    {"symbol": "563050", "market": "sh", "label": "易方达中证A500ETF"},
    {"symbol": "563060", "market": "sh", "label": "嘉实中证A500ETF"},
    {"symbol": "159353", "market": "sz", "label": "华泰柏瑞中证A500ETF"}
]

# 数据库路径
DB_PATH = "data/market_thermo_3years_auto.db"


def fetch_etf_flow(symbol: str, market: str, label: str, 
                   start_date: str, end_date: str) -> pd.Series:
    """
    获取单只ETF的主力资金流向
    
    @param {str} symbol - ETF代码
    @param {str} market - 市场（sh/sz）
    @param {str} label - ETF名称
    @param {str} start_date - 开始日期
    @param {str} end_date - 结束日期
    @returns {pd.Series} 主力净流入序列（亿元）
    """
    try:
        print(f"[INFO] 正在获取 {label} ({symbol}) 数据...")
        df = ak.stock_individual_fund_flow(stock=symbol, market=market)
        
        if df is None or df.empty:
            print(f"[WARN] {label} 无数据")
            return pd.Series(dtype=float)
        
        # 查找日期列
        date_col = None
        for col in df.columns:
            if '日期' in col:
                date_col = col
                break
        if date_col is None:
            date_col = df.columns[0]
        
        # 查找主力净流入列
        flow_col = None
        flow_candidates = [col for col in df.columns if '主力净流入' in col]
        for col in flow_candidates:
            if '净额' in col:
                flow_col = col
                break
        if flow_col is None and flow_candidates:
            flow_col = flow_candidates[0]
        
        if flow_col is None:
            print(f"[WARN] {label} 无主力净流入数据列")
            return pd.Series(dtype=float)
        
        # 数据清洗
        df['date'] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=['date'])
        df = df.set_index('date').sort_index()
        
        # 日期过滤
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        df = df[(df.index >= start_dt) & (df.index <= end_dt)]
        
        if df.empty:
            print(f"[WARN] {label} 在指定日期范围内无数据")
            return pd.Series(dtype=float)
        
        # 提取主力净流入，单位：万元 -> 亿元
        series = pd.to_numeric(df[flow_col], errors='coerce').dropna()
        series = series / 10000.0
        
        print(f"[OK] {label} 获取 {len(series)} 条记录")
        return series
        
    except Exception as e:
        print(f"[ERROR] {label} 获取失败: {e}")
        return pd.Series(dtype=float)


def fetch_all_a500_etf_flows(start_date: str, end_date: str) -> pd.Series:
    """
    获取所有A500 ETF的综合资金流向
    
    @param {str} start_date - 开始日期
    @param {str} end_date - 结束日期
    @returns {pd.Series} 综合资金流（亿元）
    """
    print("\n" + "=" * 80)
    print("开始获取A500 ETF资金流向数据")
    print("=" * 80)
    
    combined_flow = None
    success_count = 0
    
    for etf in A500_ETF_LIST:
        series = fetch_etf_flow(
            etf['symbol'], 
            etf['market'], 
            etf['label'],
            start_date,
            end_date
        )
        
        if not series.empty:
            if combined_flow is None:
                combined_flow = series
            else:
                combined_flow = combined_flow.add(series, fill_value=0.0)
            success_count += 1
    
    if combined_flow is None or combined_flow.empty:
        raise ValueError("所有ETF数据获取均失败")
    
    print(f"\n[OK] 成功获取 {success_count}/{len(A500_ETF_LIST)} 只ETF数据")
    print(f"[OK] 综合资金流共 {len(combined_flow)} 条记录")
    
    return combined_flow


def calculate_5day_rolling(daily_flow: pd.Series) -> pd.Series:
    """
    计算5日滚动净申赎
    
    @param {pd.Series} daily_flow - 日度资金流
    @returns {pd.Series} 5日滚动和
    """
    print("\n[INFO] 计算5日滚动净申赎...")
    rolling_5d = daily_flow.rolling(window=5, min_periods=1).sum()
    print(f"[OK] 计算完成，共 {len(rolling_5d)} 条记录")
    return rolling_5d


def get_series_id(conn: sqlite3.Connection, code: str, market: str) -> int:
    """
    获取series_id
    
    @param {sqlite3.Connection} conn - 数据库连接
    @param {str} code - 指标代码
    @param {str} market - 市场
    @returns {int} series_id
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM series_meta WHERE code = ? AND market = ?",
        (code, market)
    )
    result = cursor.fetchone()
    if result is None:
        raise ValueError(f"找不到指标 {code} (市场: {market})")
    return result[0]


def update_database(data: pd.Series, code: str = "ETF_NETFLOW_5D", 
                   market: str = "CN", dry_run: bool = False):
    """
    更新数据库中的ETF_NETFLOW_5D数据
    
    @param {pd.Series} data - 数据序列
    @param {str} code - 指标代码
    @param {str} market - 市场
    @param {bool} dry_run - 是否试运行
    """
    print("\n" + "=" * 80)
    print("更新数据库")
    print("=" * 80)
    
    if dry_run:
        print("[DRY-RUN] 试运行模式，不会实际修改数据库")
        print(f"[INFO] 将要更新的数据样例（前5条）：")
        print(data.head())
        print(f"[INFO] 数据统计：")
        print(f"  - 总记录数: {len(data)}")
        print(f"  - 日期范围: {data.index.min()} ~ {data.index.max()}")
        print(f"  - 数值范围: {data.min():.2f} ~ {data.max():.2f} 亿元")
        return
    
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # 获取series_id
        series_id = get_series_id(conn, code, market)
        print(f"[INFO] 指标 {code} 的 series_id = {series_id}")
        
        cursor = conn.cursor()
        
        # 删除旧数据
        cursor.execute(
            "DELETE FROM series_data WHERE series_id = ?",
            (series_id,)
        )
        deleted_count = cursor.rowcount
        print(f"[INFO] 删除旧数据: {deleted_count} 条")
        
        # 插入新数据
        insert_count = 0
        for date, value in data.items():
            if pd.isna(value):
                continue
            
            date_str = date.strftime('%Y-%m-%d')
            cursor.execute(
                """
                INSERT INTO series_data (series_id, date, view, value_raw, value_tr)
                VALUES (?, ?, ?, ?, ?)
                """,
                (series_id, date_str, 'daily', float(value), float(value))
            )
            insert_count += 1
        
        conn.commit()
        print(f"[OK] 插入新数据: {insert_count} 条")
        
        # 验证
        cursor.execute(
            """
            SELECT MIN(date), MAX(date), COUNT(*) 
            FROM series_data 
            WHERE series_id = ?
            """,
            (series_id,)
        )
        min_date, max_date, total = cursor.fetchone()
        print(f"\n[验证] 数据库中 {code} 的数据：")
        print(f"  - 日期范围: {min_date} ~ {max_date}")
        print(f"  - 总记录数: {total}")
        
    except Exception as e:
        print(f"[ERROR] 数据库更新失败: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()
    
    print("=" * 80)
    print("[完成] 数据库更新成功！")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="获取A500 ETF资金流向数据")
    parser.add_argument('--days', type=int, help='获取最近N天的数据（默认90天）')
    parser.add_argument('--start', type=str, help='开始日期（YYYY-MM-DD）')
    parser.add_argument('--end', type=str, help='结束日期（YYYY-MM-DD）')
    parser.add_argument('--dry-run', action='store_true', help='试运行模式，不实际修改数据库')
    parser.add_argument('--execute', action='store_true', help='执行数据库更新')
    
    args = parser.parse_args()
    
    # 确定日期范围
    if args.start and args.end:
        start_date = args.start
        end_date = args.end
    elif args.days:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')
    else:
        # 默认获取最近90天
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    
    print(f"\n日期范围: {start_date} ~ {end_date}\n")
    
    try:
        # 获取数据
        daily_flow = fetch_all_a500_etf_flows(start_date, end_date)
        
        # 计算5日滚动
        rolling_5d = calculate_5day_rolling(daily_flow)
        
        # 更新数据库
        if args.dry_run or not args.execute:
            update_database(rolling_5d, dry_run=True)
            print("\n[提示] 这是试运行模式")
            print("[提示] 如需实际更新数据库，请运行: python fetch_a500_etf_data.py --execute")
        else:
            update_database(rolling_5d, dry_run=False)
            print("\n[提示] 请在GUI中点击'计算评分'来更新评分和确认层")
        
    except Exception as e:
        print(f"\n[ERROR] 执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

