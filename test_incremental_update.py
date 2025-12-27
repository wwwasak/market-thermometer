"""
测试增量更新优化功能

验证：
1. 历史数据加载功能
2. 转换计算时的自动补充历史数据
3. value_tr是否正确计算
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from storage.repository import Repository
from core.config import Config
from core.pipeline import MarketPipeline
import pandas as pd


def test_repository_load_history():
    """测试Repository的历史数据加载功能"""
    print("=" * 80)
    print("测试1: Repository历史数据加载")
    print("=" * 80)
    
    repo = Repository('sqlite:///data/market_thermo_3years_auto.db')
    
    # 测试加载IWM_SPY_REL20的历史数据
    print("\n加载IWM_SPY_REL20最近30天历史数据...")
    series = repo.load_raw_series_by_code('IWM_SPY_REL20', limit_days=30)
    
    if series is None:
        print("[WARN] 数据库中没有IWM_SPY_REL20数据，这是正常的（可能还未初始化）")
        print("  建议先运行: python fetch_3years_data_auto.py")
        return False
    
    print(f"[OK] 加载成功！")
    print(f"  - 数据行数: {len(series)}")
    print(f"  - 日期范围: {series.index[0]} 至 {series.index[-1]}")
    print(f"  - 数据类型: {series.dtype}")
    print(f"\n最近5天数据:")
    print(series.tail(5))
    
    return True


def test_pipeline_transform_with_history():
    """测试Pipeline在增量模式下的转换计算"""
    print("\n" + "=" * 80)
    print("测试2: Pipeline增量模式转换计算")
    print("=" * 80)
    
    config = Config()
    pipeline = MarketPipeline(
        market='US',
        database_url='sqlite:///data/market_thermo_3years_auto.db'
    )
    
    # 模拟只有7天新数据的情况
    print("\n模拟场景：只有7天新数据，需要计算relret20（需要25天）")
    
    # 创建模拟的7天数据
    end_date = datetime.now()
    dates = pd.date_range(end=end_date, periods=7, freq='B')
    
    # 模拟IWM和SPY价格数据（7天）
    mock_iwm = pd.Series(
        [250.1, 251.2, 249.8, 252.3, 251.9, 250.5, 251.8],
        index=dates
    )
    mock_spy = pd.Series(
        [680.5, 682.1, 679.3, 683.2, 681.8, 680.2, 682.5],
        index=dates
    )
    
    raw_data = {
        'IWM_SPY_REL20': (mock_iwm, mock_spy)
    }
    
    print(f"  - 内存中数据: {len(mock_iwm)}天")
    print(f"  - 所需窗口: 25天")
    print(f"  - 差距: {25 - len(mock_iwm)}天")
    
    # 测试增量模式
    print("\n执行transform_data（incremental=True）...")
    try:
        transformed = pipeline.transform_data(
            raw_data,
            incremental=True,
            view_type='daily'
        )
        
        if 'IWM_SPY_REL20' in transformed:
            result = transformed['IWM_SPY_REL20']
            print(f"[OK] 转换成功！")
            print(f"  - 结果长度: {len(result)}")
            print(f"  - NaN数量: {result.isna().sum()}")
            print(f"\n转换结果（最近5天）:")
            print(result.tail(5))
            
            # 检查是否有NaN
            if result.isna().any():
                print("\n[WARN] 结果中仍有NaN值")
                print("  可能原因：数据库历史数据不足")
                return False
            else:
                print("\n[SUCCESS] 所有value_tr都计算成功，无NaN！")
                return True
        else:
            print("[ERROR] 转换结果中没有IWM_SPY_REL20")
            return False
            
    except Exception as e:
        print(f"[ERROR] 转换失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fetch_and_save_incremental():
    """测试完整的增量获取和保存流程"""
    print("\n" + "=" * 80)
    print("测试3: 完整增量获取流程")
    print("=" * 80)
    
    print("\n注意：此测试会实际调用yfinance获取数据")
    response = input("是否继续？(y/n): ")
    
    if response.lower() != 'y':
        print("跳过测试3")
        return True
    
    pipeline = MarketPipeline(
        market='US',
        database_url='sqlite:///data/market_thermo_3years_auto.db'
    )
    
    # 只获取最近7天
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    print(f"\n获取日期范围: {start_date.date()} 至 {end_date.date()}")
    print("执行 fetch_and_save_raw_data（incremental=True）...")
    
    try:
        result = pipeline.fetch_and_save_raw_data(
            start_date=start_date,
            end_date=end_date,
            incremental=True
        )
        
        if result.get('success'):
            print(f"\n[SUCCESS] 增量获取成功！")
            print(f"  - 市场: {result.get('market')}")
            print(f"  - 保存记录数: {result.get('saved_count', 0)}")
            print(f"  - 日期范围: {result.get('date_range', '')}")
            
            # 验证IWM_SPY_REL20的value_tr
            print("\n验证IWM_SPY_REL20的value_tr...")
            repo = Repository('sqlite:///data/market_thermo_3years_auto.db')
            
            # 查询最新几天的数据
            import sqlite3
            conn = sqlite3.connect('data/market_thermo_3years_auto.db')
            query = """
                SELECT s.code, d.date, d.value_raw, d.value_tr
                FROM series_data d
                JOIN series_meta s ON d.series_id = s.id
                WHERE s.code = 'IWM_SPY_REL20'
                AND d.date >= date('now', '-7 days')
                ORDER BY d.date DESC
            """
            df = pd.read_sql(query, conn)
            conn.close()
            
            if not df.empty:
                print(f"\n最近7天的数据:")
                print(df.to_string(index=False))
                
                # 检查NaN
                nan_count = df['value_tr'].isna().sum()
                if nan_count > 0:
                    print(f"\n[WARN] 有{nan_count}条记录的value_tr为NaN")
                    return False
                else:
                    print(f"\n[SUCCESS] 所有value_tr都有值，无NaN！")
                    return True
            else:
                print("[WARN] 没有找到最近7天的数据")
                return False
        else:
            print(f"[ERROR] 增量获取失败: {result.get('error', 'Unknown')}")
            return False
            
    except Exception as e:
        print(f"[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "=" * 80)
    print("增量更新优化功能测试")
    print("=" * 80)
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    results = {}
    
    # 测试1
    results['test1'] = test_repository_load_history()
    
    # 测试2（只有测试1成功才继续）
    if results['test1']:
        results['test2'] = test_pipeline_transform_with_history()
    else:
        results['test2'] = None
        print("\n[SKIP] 测试2被跳过（数据库未初始化）")
    
    # 测试3
    results['test3'] = test_fetch_and_save_incremental()
    
    # 总结
    print("\n" + "=" * 80)
    print("测试总结")
    print("=" * 80)
    
    for test_name, result in results.items():
        if result is None:
            status = "[SKIP]"
        elif result:
            status = "[PASS]"
        else:
            status = "[FAIL]"
        print(f"{status} {test_name}")
    
    passed = sum(1 for r in results.values() if r is True)
    total = sum(1 for r in results.values() if r is not None)
    
    print(f"\n通过: {passed}/{total}")
    
    if passed == total:
        print("\n✓ 所有测试通过！增量更新优化工作正常。")
    else:
        print("\n⚠ 部分测试失败，请检查上面的错误信息。")


if __name__ == "__main__":
    main()

