"""
仅重新计算评分（不获取新数据）

使用数据库中已有的原始数据重新计算评分
"""

from storage.repository import Repository
from core.config import Config
from core.transforms import apply_transform
from core.scoring import standardize_with_direction, score_from_z, lamp_from_score, regime_from_score, weighted_score
import pandas as pd
import numpy as np
from datetime import datetime

def recalculate_scores_from_db():
    """从数据库重新计算评分"""
    print("="*70)
    print("从数据库重新计算评分")
    print("="*70)
    
    database_url = "sqlite:///data/market_thermo_3years_auto.db"
    repository = Repository(database_url)
    config = Config()
    
    # 默认使用CN市场
    market = "CN"
    view = "daily"
    
    print(f"\n处理 {market} 市场，{view} 视图...")
    
    # 获取主要指标配置
    main_indicators = config.get(f"indicators.{market}.main", [])
    active_style = config.get(f"active_style.{market}", "Balanced")
    weights = config.get(f"style_weights.{market}.{active_style}", [])
    
    print(f"风格: {active_style}")
    print(f"主要指标数量: {len(main_indicators)}")
    print(f"权重数量: {len(weights)}")
    
    if len(main_indicators) != len(weights):
        print(f"\n[ERROR] 指标数量({len(main_indicators)})与权重数量({len(weights)})不匹配！")
        return
    
    # 步骤1：从数据库加载所有指标的原始/转换数据
    print(f"\n步骤1: 加载数据...")
    indicator_data = {}
    
    for ind in main_indicators:
        code = ind['code']
        print(f"  加载 {code}...", end=" ")
        
        df = repository.load_series_data_by_code(code, view=view)
        
        if df is not None and not df.empty:
            # 使用转换值，如果没有则用原始值
            if 'value_tr' in df.columns:
                series = df['value_tr'].dropna()
            elif 'value_raw' in df.columns:
                series = df['value_raw'].dropna()
            else:
                print("无有效列")
                continue
            
            if len(series) > 0:
                indicator_data[code] = series
                print(f"OK ({len(series)} 条记录)")
            else:
                print("无数据")
        else:
            print("无数据")
    
    if not indicator_data:
        print("\n[ERROR] 没有找到任何指标数据！")
        return
    
    print(f"\n找到 {len(indicator_data)} 个指标的数据")
    
    # 步骤2：计算Z分数和评分（不对齐，独立计算）
    print(f"\n步骤2: 计算Z分数和评分（独立计算，不对齐）...")
    scores_dict = {}
    z_dict = {}
    
    for ind in main_indicators:
        code = ind['code']
        if code not in indicator_data:
            continue
        
        series = indicator_data[code]  # 使用原始序列，不对齐
        direction = ind.get('direction', 'up_good')
        z_type = ind.get('z_type', 'Z')
        z_window = ind.get('z_window', 60)
        transform_type = ind.get('transform', 'raw')
        
        print(f"  {code}: {len(series)} 条记录, direction={direction}, z_type={z_type}, window={z_window}")
        
        # **修复：对月度指标（如PMI），先在月度数据点计算评分，再前向填充**
        is_monthly_indicator = 'ffill' in transform_type or code in ['PMI_NEWORDER_YOY_STD']
        
        if is_monthly_indicator:
            print(f"    [月度指标] 使用月度评分模式")
            # 识别数据变化点（月度发布日期）
            value_changes = series != series.shift(1)
            monthly_points = series[value_changes].dropna()
            
            if len(monthly_points) > 0:
                print(f"    检测到 {len(monthly_points)} 个月度数据点")
                
                # 对月度数据，使用更小的window（月数）
                monthly_z_window = min(12, len(monthly_points) - 1) if len(monthly_points) > 1 else 1
                print(f"    使用window={monthly_z_window}个月")
                
                # 只对月度数据点计算Z-score
                z_monthly = standardize_with_direction(
                    monthly_points,
                    direction=direction,
                    z_type=z_type,
                    window=monthly_z_window
                )
                
                # 计算月度评分
                score_monthly = score_from_z(z_monthly, center=50, scale=10)
                
                # 前向填充到所有日期
                z = z_monthly.reindex(series.index, method='ffill')
                score = score_monthly.reindex(series.index, method='ffill')
            else:
                z = pd.Series(index=series.index, dtype=float)
                score = pd.Series(index=series.index, dtype=float)
        else:
            # 对于日度指标，正常计算
            z = standardize_with_direction(
                series,
                direction=direction,
                z_type=z_type,
                window=z_window
            )
            
            # 计算评分
            score = score_from_z(z, center=50, scale=10)
        
        z_dict[code] = z
        scores_dict[code] = score
        
        # 统计
        z_valid = z.notna().sum()
        score_valid = score.notna().sum()
        print(f"    Z分数: {z_valid}/{len(z)} 个有效, 评分: {score_valid}/{len(score)} 个有效")
        
        if score_valid > 0:
            print(f"    评分范围: {score.min():.1f} - {score.max():.1f}, 均值: {score.mean():.1f}")
    
    # 步骤3：对齐所有序列以计算综合评分
    print(f"\n步骤3: 对齐数据以计算综合评分...")
    all_dates = set()
    for series in scores_dict.values():
        all_dates.update(series.index)
    
    all_dates = sorted(list(all_dates))
    print(f"  日期范围: {all_dates[0]} 至 {all_dates[-1]}")
    print(f"  总天数: {len(all_dates)}")
    
    # 创建对齐的评分DataFrame
    score_matrix = pd.DataFrame(index=pd.DatetimeIndex(all_dates))
    for code, score_series in scores_dict.items():
        score_matrix[code] = score_series
    
    print(f"  评分矩阵形状: {score_matrix.shape}")
    print(f"  列名: {list(score_matrix.columns)}")
    
    # 步骤4：计算综合评分
    print(f"\n步骤4: 计算综合评分...")
    
    # 检查权重
    main_codes = [ind['code'] for ind in main_indicators if ind['code'] in score_matrix.columns]
    available_weights = [weights[i] for i, ind in enumerate(main_indicators) if ind['code'] in main_codes]
    
    print(f"  可用指标: {len(main_codes)}")
    print(f"  可用权重: {available_weights}")
    
    if len(main_codes) == len(available_weights):
        composite_score = weighted_score(score_matrix[main_codes], available_weights, normalize=True)
        
        comp_valid = composite_score.notna().sum()
        print(f"  综合评分: {comp_valid}/{len(composite_score)} 个有效值")
        
        if comp_valid > 0:
            print(f"  范围: {composite_score.min():.1f} - {composite_score.max():.1f}")
            print(f"  最近5个值: {list(composite_score.tail(5).values)}")
        else:
            print(f"  [ERROR] 综合评分全部为NaN!")
    else:
        print(f"  [ERROR] 指标和权重数量不匹配!")
        composite_score = pd.Series(index=score_matrix.index, dtype=float)
    
    # 步骤5：保存到数据库
    print(f"\n步骤5: 保存到数据库...")
    
    save_count = 0
    score_save_count = 0
    
    # 获取series_id映射
    code_to_series_id = {}
    for code in main_codes:
        meta = repository.get_series_meta_by_code(code)
        if meta:
            code_to_series_id[code] = meta['id']
    
    print(f"  找到 {len(code_to_series_id)} 个序列ID映射")
    
    # 保存每个指标的评分
    for code in main_codes:
        series_id = code_to_series_id.get(code)
        if not series_id:
            print(f"  [WARN] {code}: 未找到series_id")
            continue
        
        score_series = scores_dict.get(code)
        z_series = z_dict.get(code)
        
        if score_series is None:
            continue
        
        # 遍历所有日期
        for date_idx in score_series.index:
            try:
                score_val = score_series.loc[date_idx]
                z_val = z_series.loc[date_idx] if z_series is not None else None
                
                # 只更新有有效评分的记录
                if pd.notna(score_val):
                    # 转换日期
                    if isinstance(date_idx, pd.Timestamp):
                        record_date = date_idx.date()
                    else:
                        record_date = pd.Timestamp(date_idx).date()
                    
                    # 只更新z和score字段
                    success = repository.upsert_series_data(
                        series_id=series_id,
                        date=record_date,
                        view=view,
                        z=float(z_val) if pd.notna(z_val) else None,
                        score=float(score_val)
                    )
                    
                    if success:
                        save_count += 1
                        score_save_count += 1
            
            except Exception as e:
                print(f"  [WARN] 保存失败 ({code}, {date_idx}): {e}")
                continue
        
        print(f"  {code}: 保存 {score_save_count} 条评分数据")
        score_save_count = 0
    
    print(f"\n[OK] 总共保存 {save_count} 条评分数据")
    
    # 步骤6：保存综合评分和regime
    print(f"\n步骤6: 保存综合评分和regime...")
    
    regime_save_count = 0
    for date_idx in composite_score.index:
        try:
            comp_val = composite_score.loc[date_idx]
            
            if pd.notna(comp_val):
                # 转换日期
                if isinstance(date_idx, pd.Timestamp):
                    record_date = date_idx.date()
                else:
                    record_date = pd.Timestamp(date_idx).date()
                
                # 计算regime
                if comp_val >= 70:
                    regime_val = 'Attack'
                elif comp_val <= 40:
                    regime_val = 'Defense'
                else:
                    regime_val = 'Balanced'
                
                # 保存
                repository.upsert_regime(
                    date=record_date,
                    market=market,
                    view=view,
                    regime=regime_val,
                    composite_score=float(comp_val),
                    lamp_final='Y',  # 暂时使用默认值
                    lamp_soft='Y',
                    lamp_hard='Y',
                    params_hash='manual_calc'
                )
                
                regime_save_count += 1
        
        except Exception as e:
            print(f"  [WARN] 保存regime失败 ({date_idx}): {e}")
            continue
    
    print(f"  保存 {regime_save_count} 条regime数据")
    
    print(f"\n{'='*70}")
    print("完成！")
    print(f"{'='*70}")
    print(f"总计: {save_count} 条评分数据, {regime_save_count} 条综合评分数据")
    print(f"\n现在可以打开应用查看结果:")
    print(f"  python app.py")


if __name__ == '__main__':
    try:
        recalculate_scores_from_db()
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()

