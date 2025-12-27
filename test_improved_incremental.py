"""
测试改进后的增量更新逻辑

测试流程:
1. 删除最近几天的US数据
2. 模拟增量获取（只获取最近5天）
3. 验证value_tr是否正确计算
"""

import sys
from datetime import datetime, timedelta
import pandas as pd
from storage.repository import Repository
from core.pipeline import Pipeline

def main():
    print("=" * 80)
    print("测试改进后的增量更新逻辑")
    print("=" * 80)
    print(f"运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    db_url = 'sqlite:///data/market_thermo_3years_auto.db'
    repo = Repository(db_url)
    
    # 步骤1: 检查当前状态
    print("步骤1: 检查当前IWM_SPY_REL20状态")
    print("-" * 80)
    
    session = repo.get_session()
    from storage.models import SeriesMeta, SeriesData
    
    meta = session.query(SeriesMeta).filter(SeriesMeta.code == 'IWM_SPY_REL20').first()
    if not meta:
        print("[ERROR] 找不到IWM_SPY_REL20指标")
        session.close()
        return
    
    # 查询最近10天数据
    recent_data = session.query(SeriesData).filter(
        SeriesData.series_id == meta.id,
        SeriesData.view == 'daily'
    ).order_by(SeriesData.date.desc()).limit(10).all()
    
    print(f"\n当前最近10天数据:")
    for d in recent_data:
        date_str = d.date.strftime('%Y-%m-%d') if hasattr(d.date, 'strftime') else str(d.date)
        v_raw_str = f"{d.value_raw:.6f}" if d.value_raw is not None else "None"
        v_tr_str = f"{d.value_tr:.6f}" if d.value_tr is not None else "None"
        score_str = f"{d.score:.2f}" if d.score is not None else "None"
        print(f"  {date_str}: raw={v_raw_str}, tr={v_tr_str}, score={score_str}")
    
    # 步骤2: 删除12月24日之后的数据
    print("\n步骤2: 删除12月24日之后的数据")
    print("-" * 80)
    
    delete_count = session.query(SeriesData).filter(
        SeriesData.series_id == meta.id,
        SeriesData.date > '2025-12-24',
        SeriesData.view == 'daily'
    ).delete()
    
    session.commit()
    print(f"[OK] 删除了 {delete_count} 条记录")
    session.close()
    
    # 步骤3: 使用增量模式获取数据
    print("\n步骤3: 使用增量模式获取最新数据")
    print("-" * 80)
    
    pipeline = Pipeline('US', repo)
    
    # 增量获取（会自动从最后一次更新开始 - 5天）
    raw_data = pipeline.fetch_all_data(incremental=True, skip_validation=True)
    
    print(f"\n[OK] 获取到 {len(raw_data)} 个指标的数据")
    
    if 'IWM_SPY_REL20' in raw_data:
        iwm_spy_data = raw_data['IWM_SPY_REL20']
        print(f"\nIWM_SPY_REL20新获取的数据:")
        if isinstance(iwm_spy_data, tuple):
            print(f"  类型: tuple (包含 {len(iwm_spy_data)} 个series)")
            for i, s in enumerate(iwm_spy_data):
                print(f"  Series {i}: {len(s)} 条数据")
        else:
            print(f"  类型: {type(iwm_spy_data)}")
            print(f"  数据量: {len(iwm_spy_data)}")
            print(f"  最近5条:")
            print(iwm_spy_data.tail())
    else:
        print("\n[WARN] 没有获取到IWM_SPY_REL20数据")
    
    # 步骤4: 应用转换（重点测试）
    print("\n步骤4: 应用转换（测试完整历史加载）")
    print("-" * 80)
    
    transformed = pipeline.transform_data(raw_data, incremental=True, view_type='daily')
    
    if 'IWM_SPY_REL20' in transformed:
        iwm_spy_tr = transformed['IWM_SPY_REL20']
        print(f"\n[OK] IWM_SPY_REL20转换成功")
        print(f"  转换后数据量: {len(iwm_spy_tr)}")
        print(f"  最近5条转换结果:")
        print(iwm_spy_tr.tail())
        
        # 检查是否有NaN
        nan_count = iwm_spy_tr.isna().sum()
        print(f"\n  NaN数量: {nan_count}/{len(iwm_spy_tr)}")
        
        if nan_count == 0:
            print("\n  ✓ 所有value_tr都计算成功，没有NaN！")
        else:
            print(f"\n  ✗ 还有 {nan_count} 个NaN值")
    else:
        print("\n[ERROR] 转换后没有IWM_SPY_REL20数据")
    
    # 步骤5: 保存数据
    print("\n步骤5: 保存数据到数据库")
    print("-" * 80)
    
    pipeline.save_data(raw_data, transformed, view_type='daily', skip_derived=True)
    print("[OK] 数据已保存")
    
    # 步骤6: 验证数据库
    print("\n步骤6: 验证数据库中的数据")
    print("-" * 80)
    
    session = repo.get_session()
    final_data = session.query(SeriesData).filter(
        SeriesData.series_id == meta.id,
        SeriesData.view == 'daily',
        SeriesData.date >= '2025-12-24'
    ).order_by(SeriesData.date.desc()).all()
    
    print(f"\n数据库中12月24日之后的数据:")
    for d in final_data:
        date_str = d.date.strftime('%Y-%m-%d') if hasattr(d.date, 'strftime') else str(d.date)
        v_raw_str = f"{d.value_raw:.6f}" if d.value_raw is not None else "None"
        v_tr_str = f"{d.value_tr:.6f}" if d.value_tr is not None else "None"
        print(f"  {date_str}: raw={v_raw_str}, tr={v_tr_str}")
    
    # 检查是否有NaN
    nan_count = sum(1 for d in final_data if d.value_tr is None or pd.isna(d.value_tr))
    print(f"\n  value_tr为NaN的记录数: {nan_count}/{len(final_data)}")
    
    if nan_count == 0:
        print("\n" + "=" * 80)
        print("✓✓✓ 测试成功！所有新数据的value_tr都正确计算！")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print(f"✗ 测试失败：还有 {nan_count} 条记录的value_tr为NaN")
        print("=" * 80)
    
    session.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()

