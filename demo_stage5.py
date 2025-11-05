"""
阶段5演示：数据获取模块

展示从FRED、yfinance和CSV导入数据的功能
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tempfile

from core.datasource import (
    FREDFetcher, YFinanceFetcher, CSVImporter,
    DataSourceManager, DataFetchError,
    align_to_business_days, clean_series, validate_series
)


def print_section(title):
    """打印分隔符"""
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)


def demo_csv_importer():
    """演示CSV导入功能"""
    print_section("1. CSV导入演示")
    
    # 创建示例CSV文件
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='', encoding='utf-8')
    temp_file.write('date,margin_balance\n')
    
    # 生成一些示例数据（模拟两融余额）
    dates = pd.date_range('2024-01-01', periods=20, freq='B')
    for date in dates:
        balance = np.random.uniform(16000, 17000)
        temp_file.write(f'{date.strftime("%Y-%m-%d")},{balance:.2f}\n')
    
    temp_file.close()
    
    print(f"\n[INFO] 创建临时CSV文件: {temp_file.name}")
    
    try:
        # 导入CSV
        importer = CSVImporter()
        data = importer.import_csv(
            temp_file.name,
            date_col='date',
            value_col='margin_balance'
        )
        
        print(f"\n[OK] 成功导入 {len(data)} 条记录")
        print("\n前5条数据:")
        print(data.head())
        print("\n后5条数据:")
        print(data.tail())
        
        # 数据统计
        print(f"\n数据统计:")
        print(f"  开始日期: {data.index.min().strftime('%Y-%m-%d')}")
        print(f"  结束日期: {data.index.max().strftime('%Y-%m-%d')}")
        print(f"  均值: {data.mean():.2f}")
        print(f"  标准差: {data.std():.2f}")
        print(f"  最小值: {data.min():.2f}")
        print(f"  最大值: {data.max():.2f}")
    
    finally:
        # 清理临时文件
        os.unlink(temp_file.name)
        print(f"\n[INFO] 已清理临时文件")


def demo_data_cleaning():
    """演示数据清洗功能"""
    print_section("2. 数据清洗和验证演示")
    
    # 创建带有问题的数据
    print("\n[INFO] 创建测试数据（包含NaN和异常值）")
    dates = pd.date_range('2024-01-01', periods=30, freq='B')
    values = np.random.randn(30) * 10 + 100
    
    # 添加一些NaN
    values[5] = np.nan
    values[10] = np.nan
    values[15] = np.nan
    
    # 添加异常值
    values[20] = 500  # 明显异常
    
    data = pd.Series(values, index=dates)
    
    print(f"\n原始数据:")
    print(f"  长度: {len(data)}")
    print(f"  NaN数量: {data.isna().sum()}")
    print(f"  均值: {data.mean():.2f}")
    print(f"  标准差: {data.std():.2f}")
    
    # 清洗数据
    print("\n[INFO] 清洗数据（移除异常值，插值NaN）...")
    cleaned = clean_series(
        data,
        remove_outliers=True,
        outlier_std=3.0,
        interpolate=True
    )
    
    print(f"\n清洗后数据:")
    print(f"  长度: {len(cleaned)}")
    print(f"  NaN数量: {cleaned.isna().sum()}")
    print(f"  均值: {cleaned.mean():.2f}")
    print(f"  标准差: {cleaned.std():.2f}")
    
    # 验证数据
    print("\n[INFO] 验证数据质量...")
    is_valid, message = validate_series(cleaned, min_length=20, max_gap_days=10)
    
    print(f"\n验证结果: {'通过' if is_valid else '失败'}")
    print(f"  消息: {message}")


def demo_business_day_alignment():
    """演示工作日对齐"""
    print_section("3. 工作日对齐演示")
    
    # 创建不规则日期的数据（模拟周度数据）
    print("\n[INFO] 创建不规则日期的数据...")
    dates = pd.to_datetime([
        '2024-01-05',  # 周五
        '2024-01-12',  # 周五
        '2024-01-19',  # 周五
        '2024-01-26',  # 周五
    ])
    values = [100, 105, 103, 108]
    data = pd.Series(values, index=dates)
    
    print(f"\n原始数据（周度）:")
    print(data)
    
    # 对齐到工作日
    print("\n[INFO] 对齐到工作日（前向填充）...")
    aligned = align_to_business_days(
        data,
        start_date=datetime(2024, 1, 5),
        end_date=datetime(2024, 1, 26)
    )
    
    print(f"\n对齐后数据（日度）:")
    print(f"  长度: {len(aligned)} 天")
    print("\n前10天:")
    print(aligned.head(10))


def demo_fred_fetcher():
    """演示FRED数据获取（可选，需要API key）"""
    print_section("4. FRED数据获取演示")
    
    # 检查API密钥
    api_key = os.getenv('FRED_API_KEY')
    if not api_key:
        print("\n[WARNING] FRED_API_KEY 未设置")
        print("[INFO] 请在.env文件中设置FRED_API_KEY以测试FRED数据获取")
        return
    
    print(f"\n[OK] FRED_API_KEY 已配置")
    
    try:
        fetcher = FREDFetcher(api_key)
        
        if not fetcher.fred:
            print("[WARNING] FRED初始化失败")
            return
        
        # 获取最近30天的RRP数据
        print("\n[INFO] 获取FRED数据: RRPONTSYD（隔夜逆回购）...")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        data = fetcher.fetch('RRPONTSYD', start_date, end_date)
        
        print(f"\n[OK] 成功获取 {len(data)} 条记录")
        print("\n最近5条数据:")
        print(data.tail())
        
        print(f"\n数据统计:")
        print(f"  日期范围: {data.index.min()} 至 {data.index.max()}")
        print(f"  当前值: {data.iloc[-1]:.2f}")
        print(f"  均值: {data.mean():.2f}")
    
    except DataFetchError as e:
        print(f"\n[ERROR] FRED数据获取失败: {e}")
    except Exception as e:
        print(f"\n[ERROR] 发生错误: {e}")


def demo_yfinance_fetcher():
    """演示yfinance数据获取（可选，需要网络）"""
    print_section("5. yfinance数据获取演示")
    
    # 检查网络测试环境变量
    if not os.getenv('TEST_NETWORK'):
        print("\n[INFO] 网络测试已禁用")
        print("[INFO] 设置环境变量 TEST_NETWORK=1 以启用yfinance测试")
        return
    
    try:
        fetcher = YFinanceFetcher()
        
        if not fetcher.yf:
            print("[WARNING] yfinance未安装")
            return
        
        # 获取最近30天的SPY数据
        print("\n[INFO] 获取yfinance数据: SPY（标普500 ETF）...")
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        data = fetcher.fetch('SPY', start_date, end_date)
        
        print(f"\n[OK] 成功获取 {len(data)} 条记录")
        print("\n最近5条数据:")
        print(data.tail())
        
        print(f"\n数据统计:")
        print(f"  日期范围: {data.index.min()} 至 {data.index.max()}")
        print(f"  当前价格: ${data.iloc[-1]:.2f}")
        print(f"  期间涨跌: {((data.iloc[-1] / data.iloc[0] - 1) * 100):.2f}%")
    
    except DataFetchError as e:
        print(f"\n[ERROR] yfinance数据获取失败: {e}")
    except Exception as e:
        print(f"\n[ERROR] 发生错误: {e}")


def demo_data_source_manager():
    """演示数据源管理器"""
    print_section("6. 数据源管理器演示")
    
    manager = DataSourceManager()
    
    print("\n[OK] 数据源管理器初始化完成")
    print(f"  FRED fetcher: {'可用' if manager.fred_fetcher.fred else '不可用'}")
    print(f"  yfinance fetcher: {'可用' if manager.yf_fetcher.yf else '不可用'}")
    print(f"  CSV importer: 可用")
    
    # 示例：根据配置获取数据
    print("\n[INFO] 示例配置:")
    
    configs = [
        {
            'code': 'VIX_LOG',
            'name': 'VIX波动率（对数）',
            'source': 'yfinance',
            'ticker': '^VIX'
        },
        {
            'code': 'RRPONTSYD',
            'name': '隔夜逆回购',
            'source': 'fred',
            'ticker': 'RRPONTSYD'
        },
        {
            'code': 'MARGIN',
            'name': '两融余额',
            'source': 'csv',
            'ticker': 'cn_margin_balance.csv'
        }
    ]
    
    for config in configs:
        print(f"\n  [{config['code']}]")
        print(f"    名称: {config['name']}")
        print(f"    数据源: {config['source']}")
        print(f"    Ticker: {config['ticker']}")
    
    print("\n[INFO] 使用 fetch_by_config() 方法可以根据配置自动选择数据源")


def main():
    """主函数"""
    print("\n")
    print("*" * 60)
    print("  阶段5演示：数据获取模块")
    print("*" * 60)
    
    # 1. CSV导入演示
    demo_csv_importer()
    
    # 2. 数据清洗演示
    demo_data_cleaning()
    
    # 3. 工作日对齐演示
    demo_business_day_alignment()
    
    # 4. FRED数据获取演示（可选）
    demo_fred_fetcher()
    
    # 5. yfinance数据获取演示（可选）
    demo_yfinance_fetcher()
    
    # 6. 数据源管理器演示
    demo_data_source_manager()
    
    # 总结
    print_section("总结")
    print("\n阶段5完成！已实现的功能:")
    print("  [OK] CSV数据导入")
    print("  [OK] 数据清洗和验证")
    print("  [OK] 工作日对齐")
    print("  [OK] FRED数据获取接口")
    print("  [OK] yfinance数据获取接口")
    print("  [OK] 统一数据源管理器")
    
    print("\n下一步（阶段6）:")
    print("  [ ] 完整数据流水线（获取->转换->评分->存储）")
    print("  [ ] 批量处理所有指标")
    print("  [ ] 日度和周度计算")
    print("  [ ] 持久化到数据库")
    
    print("\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INFO] 演示被用户中断")
    except Exception as e:
        print(f"\n[ERROR] 演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

