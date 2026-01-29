"""
测试akshare获取全市场成交额的备用方案
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

def test_akshare_market_turnover():
    """测试使用akshare获取市场成交额"""
    print("="*60)
    print("测试 akshare 获取市场成交额（备用方案）")
    print("="*60)
    
    try:
        # 获取上证指数数据
        print("\n[1] 获取上证指数数据...")
        sh_df = ak.stock_zh_index_daily(symbol="sh000001")
        print(f"  获取到 {len(sh_df)} 条记录")
        print(f"  列名: {list(sh_df.columns)}")
        
        # 转换日期并设置索引
        sh_df['date'] = pd.to_datetime(sh_df['date'])
        sh_df = sh_df.set_index('date').sort_index()
        
        # 获取最近7天的数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        sh_df_recent = sh_df[(sh_df.index >= start_date) & (sh_df.index <= end_date)]
        
        # 成交额：元 -> 亿元
        sh_turnover = pd.to_numeric(sh_df_recent['amount'], errors='coerce') / 1e8
        
        print(f"\n  最近的上证指数成交额（亿元）:")
        for date, value in sh_turnover.items():
            print(f"    {date.strftime('%Y-%m-%d')}: {value:,.2f}")
        
        # 获取深证成指数据
        print("\n[2] 获取深证成指数据...")
        sz_df = ak.stock_zh_index_daily(symbol="sz399001")
        print(f"  获取到 {len(sz_df)} 条记录")
        
        # 转换日期并设置索引
        sz_df['date'] = pd.to_datetime(sz_df['date'])
        sz_df = sz_df.set_index('date').sort_index()
        
        # 获取最近7天的数据
        sz_df_recent = sz_df[(sz_df.index >= start_date) & (sz_df.index <= end_date)]
        
        # 成交额：元 -> 亿元
        sz_turnover = pd.to_numeric(sz_df_recent['amount'], errors='coerce') / 1e8
        
        print(f"\n  最近的深证成指成交额（亿元）:")
        for date, value in sz_turnover.items():
            print(f"    {date.strftime('%Y-%m-%d')}: {value:,.2f}")
        
        # 合计
        print("\n[3] 计算全市场成交额（上证+深证）...")
        total_turnover = sh_turnover.add(sz_turnover, fill_value=0.0)
        
        print(f"\n  全市场成交额（亿元）:")
        for date, value in total_turnover.items():
            print(f"    {date.strftime('%Y-%m-%d')}: {value:,.2f}")
        
        print("\n" + "="*60)
        print("结果: ✅ akshare备用方案正常工作！")
        print("="*60)
        return True
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        print("\n" + "="*60)
        print("结果: ❌ akshare备用方案失败")
        print("="*60)
        return False

if __name__ == "__main__":
    test_akshare_market_turnover()
