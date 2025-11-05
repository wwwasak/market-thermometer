"""
完整的端到端流水线测试

验证：
1. 真实数据获取
2. 数据转换
3. 评分计算
4. 派生指标计算
5. 确认层应用
6. 数据库存储
"""

import os
import pandas as pd
from datetime import datetime, timedelta
from core.pipeline import MarketPipeline
from core.transforms import apply_transform
from storage.migrate import init_database, check_database_integrity


def print_section(title):
    """打印分隔符"""
    print("\n" + "="*70)
    print(f"  {title}")
    print("="*70)


def test_data_fetch():
    """测试1: 真实数据获取"""
    print_section("测试1: 真实数据获取")
    
    # 创建流水线
    db_url = 'sqlite:///data/test_e2e.db'
    os.makedirs('data', exist_ok=True)
    
    print("\n[INFO] 初始化数据库...")
    init_database(db_url, force=True)
    
    print("\n[INFO] 创建US市场流水线...")
    pipeline = MarketPipeline(market='US', database_url=db_url)
    
    print(f"[INFO] 配置的指标总数: {len(pipeline.indicators)}")
    
    # 分类指标
    main_indicators = [ind for ind in pipeline.indicators if ind.get('role') not in ['hard', 'soft', 'pair']]
    observer_indicators = [ind for ind in pipeline.indicators if ind.get('role') in ['hard', 'soft', 'pair']]
    
    print(f"  - 主指标: {len(main_indicators)}")
    print(f"  - 观察者指标: {len(observer_indicators)}")
    
    # 获取数据（90天）
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    print(f"\n[INFO] 获取数据 ({start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')})...")
    raw_data = pipeline.fetch_all_data(start_date, end_date, incremental=False)
    
    print(f"\n[结果] 成功获取 {len(raw_data)}/{len(main_indicators)} 个主指标")
    
    if len(raw_data) == 0:
        print("\n[错误] 未能获取任何数据，请检查:")
        print("  1. FRED_API_KEY 环境变量")
        print("  2. 网络连接")
        return None, None
    
    print("\n获取到的数据详情:")
    for code, series in raw_data.items():
        indicator = next((ind for ind in pipeline.indicators if ind['code'] == code), {})
        source = indicator.get('source', 'N/A')
        print(f"  {code:20s}: {len(series):4d} 条记录 [{source:8s}] 最新值: {series.iloc[-1]:10.2f}")
    
    return pipeline, raw_data


def test_data_transforms(pipeline, raw_data):
    """测试2: 数据转换"""
    print_section("测试2: 数据转换")
    
    if not raw_data:
        print("[跳过] 无原始数据")
        return None
    
    print("\n[INFO] 应用数据转换...")
    transformed_data = pipeline.transform_data(raw_data)
    
    print(f"\n[结果] 成功转换 {len(transformed_data)}/{len(raw_data)} 个指标")
    
    print("\n转换详情:")
    for code, series in transformed_data.items():
        indicator = next((ind for ind in pipeline.indicators if ind['code'] == code), {})
        transform = indicator.get('transform', 'raw')
        
        # 显示转换前后的对比
        raw_val = raw_data[code].iloc[-1] if code in raw_data else None
        trans_val = series.iloc[-1]
        
        print(f"  {code:20s}: {transform:15s} | 原始={raw_val:8.2f} → 转换={trans_val:8.2f}")
    
    return transformed_data


def test_derived_indicators(raw_data, transformed_data):
    """测试3: 派生指标计算"""
    print_section("测试3: 派生指标计算")
    
    if not transformed_data:
        print("[跳过] 无转换数据")
        return {}
    
    derived = {}
    
    # 测试相对收益率指标（如果基础数据可用）
    print("\n[INFO] 计算派生指标...")
    
    # 示例：计算IWM相对SPY的20日相对收益（如果数据可用）
    if 'IWM_SPY_REL20' not in raw_data:
        print("\n[INFO] IWM_SPY_REL20 需要单独获取IWM和SPY...")
        # 这里可以添加配对数据的获取逻辑
        print("  [SKIP] 配对指标需要特殊处理")
    
    # 示例：检测跳升（基于HY_OAS）
    if 'HY_OAS' in transformed_data:
        print("\n[INFO] 计算HY_OAS_JUMP（跳升检测）...")
        hy_oas = transformed_data['HY_OAS']
        
        # 简单示例：计算2周变化
        if len(hy_oas) >= 10:
            delta = hy_oas.diff(10)
            jump_detected = delta.iloc[-1] if pd.notna(delta.iloc[-1]) else 0
            derived['HY_OAS_JUMP'] = jump_detected
            print(f"  最近10天变化: {jump_detected:+.4f}")
    
    # 示例：检测VIX极端值
    if 'VIX_LOG' in transformed_data:
        print("\n[INFO] 计算VIX_EXTREME（极端值检测）...")
        vix_log = transformed_data['VIX_LOG']
        extreme_detected = vix_log.iloc[-1] > vix_log.quantile(0.95)
        derived['VIX_EXTREME'] = extreme_detected
        print(f"  当前值: {vix_log.iloc[-1]:.4f}, 95分位: {vix_log.quantile(0.95):.4f}")
        print(f"  极端值: {'是' if extreme_detected else '否'}")
    
    print(f"\n[结果] 计算了 {len(derived)} 个派生指标")
    
    return derived


def test_scoring(pipeline, transformed_data):
    """测试4: 评分计算"""
    print_section("测试4: 评分计算")
    
    if not transformed_data:
        print("[跳过] 无转换数据")
        return None
    
    print("\n[INFO] 计算日度评分...")
    try:
        scores = pipeline.calculate_scores(transformed_data, view_type='daily')
        
        print(f"\n[成功] 计算了 {len(scores.columns)//2} 个指标的评分")
        print(f"  数据点数: {len(scores)}")
        print(f"  时间范围: {scores.index.min().strftime('%Y-%m-%d')} 至 {scores.index.max().strftime('%Y-%m-%d')}")
        
        # 显示最新评分
        print("\n最新评分（最近一天）:")
        latest_date = scores.index[-1]
        for col in scores.columns:
            if col.endswith('_score'):
                code = col.replace('_score', '')
                z_col = f'{code}_z'
                
                score = scores.loc[latest_date, col]
                z_score = scores.loc[latest_date, z_col] if z_col in scores.columns else None
                
                if pd.notna(score):
                    print(f"  {code:20s}: Score={score:5.1f}, Z={z_score:+6.2f}" if pd.notna(z_score) else f"  {code:20s}: Score={score:5.1f}")
        
        return scores
    
    except Exception as e:
        print(f"\n[错误] 评分计算失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_confirm_layer(pipeline, scores):
    """测试5: 确认层应用"""
    print_section("测试5: 确认层应用")
    
    if scores is None or len(scores) == 0:
        print("[跳过] 无评分数据")
        return None
    
    print("\n[INFO] 应用确认层逻辑...")
    try:
        confirm_results = pipeline.apply_confirm_layer(scores, view_type='daily')
        
        if 'final_lamp' in confirm_results:
            final_lamp = confirm_results['final_lamp']
            
            # 统计灯号分布
            from core.combine import analyze_lamp_distribution
            dist = analyze_lamp_distribution(final_lamp)
            
            print(f"\n[成功] 确认层计算完成")
            print(f"  总天数: {len(final_lamp)}")
            print(f"\n灯号分布:")
            total = len(final_lamp)
            for lamp, count in dist.items():
                lamp_name = {'G': '绿灯', 'Y': '黄灯', 'R': '红灯'}.get(lamp, lamp)
                pct = count / total * 100 if total > 0 else 0
                print(f"    {lamp_name}: {count:3d} 天 ({pct:5.1f}%)")
            
            # 显示最近5天
            print(f"\n最近5天灯号:")
            for date, lamp in final_lamp.tail(5).items():
                lamp_name = {'G': '绿灯', 'Y': '黄灯', 'R': '红灯'}.get(lamp, lamp)
                print(f"  {date.strftime('%Y-%m-%d')}: {lamp_name}")
            
            return confirm_results
        else:
            print("\n[警告] 未生成最终灯号")
            return confirm_results
    
    except Exception as e:
        print(f"\n[错误] 确认层失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_database_storage(pipeline, raw_data, transformed_data, scores, confirm_results):
    """测试6: 数据库存储"""
    print_section("测试6: 数据库存储")
    
    if not raw_data or not transformed_data or scores is None:
        print("[跳过] 数据不完整")
        return False
    
    print("\n[INFO] 保存数据到数据库...")
    try:
        saved_count = pipeline.save_to_database(
            raw_data,
            transformed_data,
            scores,
            confirm_results or {},
            view_type='daily'
        )
        
        print(f"\n[成功] 保存了 {saved_count} 条记录")
        
        # 检查数据库完整性
        print("\n[INFO] 检查数据库完整性...")
        integrity = check_database_integrity(pipeline.repository.database_url)
        
        print("\n数据库统计:")
        for key, value in integrity.items():
            if key != 'status':
                print(f"  {key}: {value}")
        
        return True
    
    except Exception as e:
        print(f"\n[错误] 数据库存储失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_pipeline_run():
    """测试7: 完整流水线运行"""
    print_section("测试7: 完整流水线运行")
    
    db_url = 'sqlite:///data/test_e2e_full.db'
    
    print("\n[INFO] 创建全新的流水线实例...")
    pipeline = MarketPipeline(market='US', database_url=db_url)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    
    print(f"[INFO] 运行完整日度流水线...")
    print(f"  时间范围: {start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}")
    
    try:
        result = pipeline.run_daily_pipeline(start_date, end_date, incremental=False)
        
        if result['success']:
            print(f"\n[成功] 完整流水线运行成功！")
            print(f"\n运行结果:")
            print(f"  市场: {result['market']}")
            print(f"  视图类型: {result['view_type']}")
            print(f"  获取指标: {result['indicators_fetched']}")
            print(f"  保存记录: {result['records_saved']}")
            if 'date_range' in result and result['date_range']:
                print(f"  时间范围: {result['date_range'][0]} 至 {result['date_range'][1]}")
            print(f"  完成时间: {result['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
            
            return True
        else:
            print(f"\n[失败] 流水线运行失败")
            print(f"  错误: {result.get('error', 'Unknown error')}")
            return False
    
    except Exception as e:
        print(f"\n[错误] 流水线运行异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "*"*70)
    print("  端到端流水线完整测试")
    print("*"*70)
    
    results = {}
    
    # 测试1: 数据获取
    pipeline, raw_data = test_data_fetch()
    results['数据获取'] = pipeline is not None and len(raw_data) > 0
    
    if not results['数据获取']:
        print("\n[终止] 无法继续后续测试")
        return results
    
    # 测试2: 数据转换
    transformed_data = test_data_transforms(pipeline, raw_data)
    results['数据转换'] = transformed_data is not None and len(transformed_data) > 0
    
    # 测试3: 派生指标
    derived = test_derived_indicators(raw_data, transformed_data)
    results['派生指标'] = len(derived) > 0
    
    # 测试4: 评分计算
    scores = test_scoring(pipeline, transformed_data)
    results['评分计算'] = scores is not None and len(scores) > 0
    
    # 测试5: 确认层
    confirm_results = test_confirm_layer(pipeline, scores)
    results['确认层'] = confirm_results is not None
    
    # 测试6: 数据库存储
    storage_ok = test_database_storage(pipeline, raw_data, transformed_data, scores, confirm_results)
    results['数据库存储'] = storage_ok
    
    # 测试7: 完整流水线
    full_pipeline_ok = test_full_pipeline_run()
    results['完整流水线'] = full_pipeline_ok
    
    # 总结
    print_section("测试总结")
    
    print("\n测试结果:")
    for test_name, passed in results.items():
        status = "[OK] 通过" if passed else "[X] 失败"
        print(f"  {test_name:12s}: {status}")
    
    total = len(results)
    passed = sum(results.values())
    
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n" + "🎉"*35)
        print("  [成功] 所有端到端测试通过！")
        print("  系统已准备就绪，可以处理真实数据。")
        print("🎉"*35)
    else:
        print("\n[警告] 部分测试失败，请检查上述错误信息")
    
    print("\n" + "*"*70)
    print()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INFO] 测试被用户中断")
    except Exception as e:
        print(f"\n[错误] 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()

