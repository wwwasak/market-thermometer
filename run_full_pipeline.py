"""
运行完整的评分计算pipeline

这个脚本会重新计算所有历史数据的评分和综合分数
"""

from core.pipeline import MarketPipeline
from datetime import datetime, timedelta
import sys

def main():
    print("="*70)
    print("运行完整的评分计算Pipeline")
    print("="*70)
    
    # 设置参数
    database_url = "sqlite:///data/market_thermo_3years_auto.db"
    
    # 让用户选择日期范围
    print("\n选择数据范围:")
    print("1. 最近1个月")
    print("2. 最近3个月")
    print("3. 最近1年")
    print("4. 最近2年")
    print("5. 全部数据（3年）")
    
    choice = input("\n请输入选择 (1-5, 默认3): ").strip() or "3"
    
    end_date = datetime.now()
    
    if choice == "1":
        start_date = end_date - timedelta(days=30)
    elif choice == "2":
        start_date = end_date - timedelta(days=90)
    elif choice == "3":
        start_date = end_date - timedelta(days=365)
    elif choice == "4":
        start_date = end_date - timedelta(days=730)
    else:  # choice == "5"
        start_date = end_date - timedelta(days=1095)
    
    print(f"\n日期范围: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
    
    # 让用户选择市场
    print("\n选择市场:")
    print("1. CN市场")
    print("2. US市场")
    print("3. 两个市场")
    
    market_choice = input("\n请输入选择 (1-3, 默认3): ").strip() or "3"
    
    markets = []
    if market_choice == "1":
        markets = ["CN"]
    elif market_choice == "2":
        markets = ["US"]
    else:
        markets = ["CN", "US"]
    
    # 执行pipeline
    results = {}
    
    for market in markets:
        print(f"\n{'='*70}")
        print(f"处理 {market} 市场")
        print(f"{'='*70}")
        
        try:
            pipeline = MarketPipeline(
                market=market,
                database_url=database_url
            )
            
            # 运行日度pipeline
            result = pipeline.run_daily_pipeline(
                start_date=start_date,
                end_date=end_date,
                incremental=False  # 完整计算，不是增量
            )
            
            results[market] = result
            
            if result.get('success'):
                print(f"\n[SUCCESS] {market}市场完成!")
                print(f"  获取指标: {result.get('indicators_fetched', 0)}")
                print(f"  保存记录: {result.get('records_saved', 0)}")
                date_range = result.get('date_range')
                if date_range:
                    print(f"  时间范围: {date_range[0]} 至 {date_range[1]}")
            else:
                print(f"\n[ERROR] {market}市场失败: {result.get('error', 'Unknown error')}")
        
        except Exception as e:
            print(f"\n[ERROR] {market}市场处理失败: {e}")
            import traceback
            traceback.print_exc()
            results[market] = {'success': False, 'error': str(e)}
    
    # 输出总结
    print(f"\n{'='*70}")
    print("执行总结")
    print(f"{'='*70}")
    
    success_count = sum(1 for r in results.values() if r.get('success'))
    total_records = sum(r.get('records_saved', 0) for r in results.values() if r.get('success'))
    
    print(f"成功市场: {success_count}/{len(markets)}")
    print(f"总保存记录: {total_records}")
    
    if success_count == len(markets):
        print("\n✓ 所有市场处理成功！")
        print("\n现在可以打开应用查看市场概览:")
        print("  python app.py")
        return 0
    else:
        print("\n✗ 部分市场处理失败，请查看错误信息")
        return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

