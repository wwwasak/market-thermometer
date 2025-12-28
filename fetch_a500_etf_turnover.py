"""
基于成交额的A500 ETF资金流向数据获取脚本

说明：
由于akshare无法获取ETF历史份额变动数据，本脚本采用"成交额"作为资金流向的近似指标。

逻辑：
1. 成交额 = 成交量 × 平均价格
2. 成交额大 → 说明有大量资金参与交易
3. 结合涨跌幅：涨且成交额大 → 资金流入；跌且成交额大 → 资金流出
4. 计算：成交额 × 涨跌幅符号 = 带方向的资金流

优点：
- 能反映市场活跃度和资金参与程度
- 数据可获取，历史数据完整
- 结合价格变动，更合理

局限性：
- 不等于真实的申购赎回
- 二级市场换手不代表资金进出基金

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

# A500相关ETF列表
A500_ETF_LIST = [
    {"code": "159352", "name": "南方中证A500ETF", "weight": 0.50},  # 规模最大
    {"code": "563080", "name": "华夏中证A500ETF", "weight": 0.15},
    {"code": "563050", "name": "易方达中证A500ETF", "weight": 0.15},
    {"code": "563060", "name": "嘉实中证A500ETF", "weight": 0.10},
    {"code": "159353", "name": "华泰柏瑞中证A500ETF", "weight": 0.10}
]

# 数据库路径
DB_PATH = "data/market_thermo_3years_auto.db"


def fetch_etf_trading_volume(code: str, name: str, weight: float,
                              start_date: str, end_date: str) -> pd.Series:
    """
    获取单只ETF的带方向成交额
    
    @param {str} code - ETF代码
    @param {str} name - ETF名称
    @param {float} weight - 权重
    @param {str} start_date - 开始日期
    @param {str} end_date - 结束日期
    @returns {pd.Series} 带方向成交额序列（亿元）
    """
    try:
        print(f"[INFO] 正在获取 {name} ({code}) 数据...")
        
        # 获取历史行情
        df = ak.fund_etf_hist_em(symbol=code, period="daily", adjust="")
        
        if df is None or df.empty:
            print(f"[WARN] {name} 无数据")
            return pd.Series(dtype=float)
        
        # 处理日期
        df['date'] = pd.to_datetime(df['日期'], errors='coerce')
        df = df.dropna(subset=['date'])
        df = df.set_index('date').sort_index()
        
        # 日期过滤
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        df = df[(df.index >= start_dt) & (df.index <= end_dt)]
        
        if df.empty:
            print(f"[WARN] {name} 在指定日期范围内无数据")
            return pd.Series(dtype=float)
        
        # 计算带方向的成交额
        # 成交额（元） × 涨跌幅符号 → 表示资金流向
        turnover = pd.to_numeric(df['成交额'], errors='coerce')  # 单位：元
        pct_change = pd.to_numeric(df['涨跌幅'], errors='coerce') / 100.0  # 百分比转小数
        
        # 带方向成交额 = 成交额 × sign(涨跌幅)
        # 涨：正值，表示资金流入；跌：负值，表示资金流出
        directional_flow = turnover * pct_change.apply(lambda x: 1 if x > 0 else -1 if x < 0 else 0)
        
        # 元 -> 亿元，并应用权重
        directional_flow = (directional_flow / 1e8) * weight
        
        directional_flow = directional_flow.dropna()
        
        print(f"[OK] {name} 获取 {len(directional_flow)} 条记录（权重:{weight}）")
        return directional_flow
        
    except Exception as e:
        print(f"[ERROR] {name} 获取失败: {e}")
        return pd.Series(dtype=float)


def fetch_all_a500_etf_flows(start_date: str, end_date: str) -> pd.Series:
    """
    获取所有A500 ETF的综合资金流向
    
    @param {str} start_date - 开始日期
    @param {str} end_date - 结束日期
    @returns {pd.Series} 综合资金流（亿元）
    """
    print("\n" + "=" * 80)
    print("开始获取A500 ETF资金流向数据（基于成交额）")
    print("=" * 80)
    
    combined_flow = None
    success_count = 0
    
    for etf in A500_ETF_LIST:
        series = fetch_etf_trading_volume(
            etf['code'], 
            etf['name'], 
            etf['weight'],
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
        print(f"\n[INFO] 数据统计：")
        print(f"  - 总记录数: {len(data)}")
        print(f"  - 日期范围: {data.index.min()} ~ {data.index.max()}")
        print(f"  - 数值范围: {data.min():.2f} ~ {data.max():.2f} 亿元")
        print(f"  - 平均值: {data.mean():.2f} 亿元")
        
        # 显示最近的趋势
        recent = data.tail(10)
        positive_days = (recent > 0).sum()
        print(f"\n[INFO] 最近10日趋势：")
        print(f"  - 资金流入天数: {positive_days} 天")
        print(f"  - 资金流出天数: {10-positive_days} 天")
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
    parser = argparse.ArgumentParser(description="获取A500 ETF资金流向数据（基于成交额）")
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
            print("[提示] 如需实际更新数据库，请运行: python fetch_a500_etf_turnover.py --execute")
        else:
            update_database(rolling_5d, dry_run=False)
            print("\n[提示] 请在GUI中点击'计算评分'来更新评分和确认层")
        
    except Exception as e:
        print(f"\n[ERROR] 执行失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

