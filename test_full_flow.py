"""
完整流程测试：从获取到保存

手动模拟GUI的完整流程，看哪一步出错
"""

from datetime import datetime, timedelta
from storage.repository import Repository
from core.pipeline import MarketPipeline
import pandas as pd

def test_full_flow():
    print("=" * 80)
    print("完整流程测试")
    print("=" * 80)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    db_url = 'sqlite:///data/market_thermo_3years_auto.db'
    repo = Repository(db_url)
    pipeline = MarketPipeline('US', repo)
    
    # 步骤1: 删除12月26日数据
    print("步骤1: 删除12月26日的IWM_SPY_REL20数据")
    print("-" * 80)
    
    session = repo.get_session()
    from storage.models import SeriesMeta, SeriesData
    
    meta = session.query(SeriesMeta).filter(SeriesMeta.code == 'IWM_SPY_REL20').first()
    if meta:
        deleted = session.query(SeriesData).filter(
            SeriesData.series_id == meta.id,
            SeriesData.date == '2025-12-26',
            SeriesData.view == 'daily'
        ).delete()
        session.commit()
        print(f"[OK] 删除了 {deleted} 条记录\n")
    session.close()
    
    # 步骤2: 增量获取数据
    print("步骤2: 增量获取IWM_SPY_REL20数据")
    print("-" * 80)
    
    raw_data = pipeline.fetch_all_data(incremental=True, skip_validation=True)
    
    if 'IWM_SPY_REL20' not in raw_data:
        print("[ERROR] 未获取到IWM_SPY_REL20数据")
        return
    
    iwm_spy_raw = raw_data['IWM_SPY_REL20']
    print(f"\n[OK] 获取到IWM_SPY_REL20原始数据")
    print(f"    类型: {type(iwm_spy_raw)}")
    
    if isinstance(iwm_spy_raw, tuple):
        print(f"    tuple长度: {len(iwm_spy_raw)}")
        for i, s in enumerate(iwm_spy_raw):
            print(f"    Series {i}: {len(s)} 条数据, 日期范围: {s.index[0]} 至 {s.index[-1]}")
            print(f"              最后3条:")
            print(s.tail(3))
    
    # 步骤3: 转换数据
    print("\n步骤3: 转换数据")
    print("-" * 80)
    
    transformed = pipeline.transform_data(raw_data, incremental=True, view_type='daily')
    
    if 'IWM_SPY_REL20' not in transformed:
        print("[ERROR] 转换后没有IWM_SPY_REL20数据")
        return
    
    iwm_spy_tr = transformed['IWM_SPY_REL20']
    print(f"\n[OK] IWM_SPY_REL20转换完成")
    print(f"    类型: {type(iwm_spy_tr)}")
    print(f"    长度: {len(iwm_spy_tr)}")
    print(f"    日期范围: {iwm_spy_tr.index[0]} 至 {iwm_spy_tr.index[-1]}")
    print(f"\n    转换后的数据（全部）:")
    print(iwm_spy_tr)
    
    # 检查12月26日
    if pd.Timestamp('2025-12-26') in iwm_spy_tr.index:
        val_26 = iwm_spy_tr.loc[pd.Timestamp('2025-12-26')]
        print(f"\n    [OK] 12月26日的值: {val_26}")
    else:
        print(f"\n    [ERROR] 转换结果中没有12月26日！")
        print(f"    实际索引: {list(iwm_spy_tr.index)}")
    
    # 步骤4: 保存数据
    print("\n步骤4: 保存数据到数据库")
    print("-" * 80)
    
    print(f"\nraw_data中IWM_SPY_REL20的类型: {type(raw_data['IWM_SPY_REL20'])}")
    print(f"transformed中IWM_SPY_REL20的类型: {type(transformed['IWM_SPY_REL20'])}")
    
    pipeline.save_data(raw_data, transformed, view_type='daily', skip_derived=True)
    print("[OK] 数据已保存")
    
    # 步骤5: 验证数据库
    print("\n步骤5: 验证数据库")
    print("-" * 80)
    
    session = repo.get_session()
    data_26 = session.query(SeriesData).filter(
        SeriesData.series_id == meta.id,
        SeriesData.date == '2025-12-26',
        SeriesData.view == 'daily'
    ).first()
    
    if data_26:
        print(f"\n[OK] 数据库中有12月26日记录")
        print(f"    value_raw: {data_26.value_raw}")
        print(f"    value_tr: {data_26.value_tr}")
        
        if data_26.value_raw is not None and not pd.isna(data_26.value_raw):
            print(f"\n✓✓✓ 成功！12月26日数据正常保存")
        else:
            print(f"\n✗✗✗ 失败！value_raw是NaN")
    else:
        print(f"\n✗✗✗ 失败！数据库中没有12月26日记录")
    
    session.close()


if __name__ == "__main__":
    try:
        test_full_flow()
    except Exception as e:
        print(f"\n[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()

