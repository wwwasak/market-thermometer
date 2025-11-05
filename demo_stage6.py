"""
阶段6演示：完整数据流水线

展示从数据获取到存储的完整流程
"""

import os
from datetime import datetime, timedelta
from core.pipeline import MarketPipeline
from storage.migrate import init_database, check_database_integrity


def print_section(title):
    """打印分隔符"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def demo_pipeline_init():
    """演示流水线初始化"""
    print_section("1. 流水线初始化")
    
    # 数据库路径
    db_path = 'data/demo_thermo.db'
    db_url = f'sqlite:///{db_path}'
    
    # 确保data目录存在
    os.makedirs('data', exist_ok=True)
    
    # 初始化数据库
    print(f"\n[INFO] 初始化数据库: {db_path}")
    init_database(db_url, force=True)
    
    # 创建流水线
    print(f"\n[INFO] 创建US市场流水线...")
    pipeline = MarketPipeline(market='US', database_url=db_url)
    
    print(f"\n[OK] 流水线初始化完成")
    print(f"  市场: {pipeline.market}")
    print(f"  指标数量: {len(pipeline.indicators)}")
    print(f"  数据库: {db_path}")
    
    return pipeline, db_url


def demo_data_fetch(pipeline):
    """演示数据获取"""
    print_section("2. 数据获取")
    
    # 获取最近3个月的数据
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    print(f"\n[INFO] 时间范围: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
    print(f"[INFO] 开始获取数据...")
    
    raw_data = pipeline.fetch_all_data(start_date, end_date, incremental=False)
    
    print(f"\n[OK] 数据获取完成")
    print(f"\n获取到的指标:")
    for code, series in raw_data.items():
        print(f"  {code:15s}: {len(series):4d} 条记录 (最新: {series.iloc[-1]:.2f})")
    
    return raw_data


def demo_data_transform(pipeline, raw_data):
    """演示数据转换"""
    print_section("3. 数据转换")
    
    print(f"\n[INFO] 应用数据转换...")
    
    transformed_data = pipeline.transform_data(raw_data)
    
    print(f"\n[OK] 转换完成")
    print(f"\n转换后的数据:")
    for code, series in transformed_data.items():
        indicator = next((i for i in pipeline.indicators if i['code'] == code), {})
        transform = indicator.get('transform', 'raw')
        print(f"  {code:15s}: {transform:20s} ({len(series)} 条记录)")
    
    return transformed_data


def demo_scoring(pipeline, transformed_data):
    """演示评分计算"""
    print_section("4. 评分计算")
    
    print(f"\n[INFO] 计算日度评分...")
    
    scores = pipeline.calculate_scores(transformed_data, view_type='daily')
    
    print(f"\n[OK] 评分完成")
    print(f"  数据点数: {len(scores)}")
    print(f"  评分列数: {len(scores.columns)}")
    print(f"  时间范围: {scores.index.min()} 至 {scores.index.max()}")
    
    # 显示最新的评分
    print(f"\n最新评分（{scores.index[-1].strftime('%Y-%m-%d')}）:")
    for col in scores.columns:
        if col.endswith('_score'):
            code = col.replace('_score', '')
            score = scores[col].iloc[-1]
            if pd.notna(score):
                print(f"  {code:15s}: {score:5.1f}")
    
    return scores


def demo_confirm_layer(pipeline, scores):
    """演示确认层"""
    print_section("5. 确认层逻辑")
    
    print(f"\n[INFO] 应用确认层...")
    
    confirm_results = pipeline.apply_confirm_layer(scores, view_type='daily')
    
    print(f"\n[OK] 确认层完成")
    
    if 'final_lamp' in confirm_results:
        final_lamp = confirm_results['final_lamp']
        
        # 统计灯号分布
        from core.combine import analyze_lamp_distribution
        dist = analyze_lamp_distribution(final_lamp)
        
        print(f"\n灯号分布:")
        print(f"  绿灯 (Green): {dist.get('G', 0)} 天 ({dist.get('G', 0) / len(final_lamp) * 100:.1f}%)")
        print(f"  黄灯 (Yellow): {dist.get('Y', 0)} 天 ({dist.get('Y', 0) / len(final_lamp) * 100:.1f}%)")
        print(f"  红灯 (Red): {dist.get('R', 0)} 天 ({dist.get('R', 0) / len(final_lamp) * 100:.1f}%)")
        
        print(f"\n最近5天灯号:")
        for date, lamp in final_lamp.tail().items():
            lamp_name = {'G': '绿灯', 'Y': '黄灯', 'R': '红灯'}.get(lamp, lamp)
            print(f"  {date.strftime('%Y-%m-%d')}: {lamp_name}")
    
    return confirm_results


def demo_save_to_db(pipeline, raw_data, transformed_data, scores, confirm_results):
    """演示保存到数据库"""
    print_section("6. 保存到数据库")
    
    print(f"\n[INFO] 保存数据到数据库...")
    
    saved_count = pipeline.save_to_database(
        raw_data, transformed_data, scores, confirm_results, view_type='daily'
    )
    
    print(f"\n[OK] 保存完成")
    print(f"  保存记录数: {saved_count}")
    
    return saved_count


def demo_full_pipeline(pipeline):
    """演示完整流水线"""
    print_section("7. 完整流水线运行")
    
    # 设置日期范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    print(f"\n[INFO] 运行完整流水线...")
    print(f"  市场: {pipeline.market}")
    print(f"  时间范围: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
    
    # 运行日度流水线
    result = pipeline.run_daily_pipeline(start_date, end_date, incremental=False)
    
    if result['success']:
        print(f"\n[成功] 流水线运行完成")
        print(f"\n运行结果:")
        print(f"  市场: {result['market']}")
        print(f"  视图类型: {result['view_type']}")
        print(f"  获取指标: {result['indicators_fetched']}")
        print(f"  保存记录: {result['records_saved']}")
        print(f"  时间范围: {result['date_range'][0]} 至 {result['date_range'][1]}")
        print(f"  完成时间: {result['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print(f"\n[失败] 流水线运行失败")
        print(f"  错误: {result.get('error', 'Unknown error')}")
    
    return result


def demo_database_check(db_url):
    """演示数据库检查"""
    print_section("8. 数据库完整性检查")
    
    print(f"\n[INFO] 检查数据库...")
    
    integrity = check_database_integrity(db_url)
    
    print(f"\n数据库统计:")
    for key, value in integrity.items():
        if key != 'status':
            print(f"  {key}: {value}")


def main():
    """主函数"""
    print("\n" + "*"*70)
    print("  阶段6演示：完整数据流水线")
    print("*"*70)
    
    try:
        # 1. 初始化流水线
        pipeline, db_url = demo_pipeline_init()
        
        # 2. 分步演示
        print("\n" + "-"*70)
        print("  分步演示流程")
        print("-"*70)
        
        # 获取数据
        raw_data = demo_data_fetch(pipeline)
        
        if not raw_data:
            print("\n[警告] 未获取到数据，跳过后续步骤")
            return
        
        # 转换数据
        transformed_data = demo_data_transform(pipeline, raw_data)
        
        # 计算评分
        import pandas as pd  # 需要导入pandas用于后面的判断
        scores = demo_scoring(pipeline, transformed_data)
        
        # 确认层
        confirm_results = demo_confirm_layer(pipeline, scores)
        
        # 保存到数据库
        saved_count = demo_save_to_db(pipeline, raw_data, transformed_data, scores, confirm_results)
        
        # 3. 完整流水线演示
        print("\n" + "-"*70)
        print("  完整流水线演示")
        print("-"*70)
        
        # 创建新的流水线实例测试完整流程
        pipeline2 = MarketPipeline(market='US', database_url=db_url)
        result = demo_full_pipeline(pipeline2)
        
        # 4. 数据库检查
        demo_database_check(db_url)
        
        # 总结
        print_section("总结")
        
        print("\n阶段6完成！已实现的功能:")
        print("  [OK] 数据获取模块集成")
        print("  [OK] 数据转换流程")
        print("  [OK] 评分计算流程")
        print("  [OK] 确认层逻辑应用")
        print("  [OK] 数据库持久化")
        print("  [OK] 完整流水线编排")
        print("  [OK] 日度流水线")
        print("  [OK] 增量更新支持")
        
        print("\n下一步（阶段7）:")
        print("  [ ] 基础GUI框架")
        print("  [ ] PyQt6界面初始化")
        print("  [ ] 主窗口布局")
        print("  [ ] 菜单和工具栏")
        
        print("\n" + "*"*70)
        print()
    
    except KeyboardInterrupt:
        print("\n\n[INFO] 演示被用户中断")
    except Exception as e:
        print(f"\n[ERROR] 演示过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()

