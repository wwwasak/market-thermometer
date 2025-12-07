# 评分计算问题修复总结

## 问题描述

用户报告运行 `python run_full_pipeline.py` 后，数据库中有完整的原始数据，但评分数据全部为0或空值。

## 根本原因

在 `core/pipeline.py` 的 `calculate_scores` 方法中，存在致命的逻辑错误：

```python
# 错误的流程（旧代码）：
1. 先对齐所有指标的转换数据到统一的日期索引（取并集）
2. 对齐后的DataFrame前面会有大量NaN（因为不同指标的起始日期不同）
3. 然后对这个对齐后的DataFrame计算Z分数
4. MAD-Z等滚动窗口计算需要足够的连续数据，前面的NaN导致无法计算
5. 结果：大部分指标的Z分数全为NaN，评分也全为NaN
```

**具体表现**：
- `CN_MARGIN_SLOPE` (使用标准Z): 只有48/798个有效评分
- `CNH_PCT20` (使用MADZ): 0/798个有效评分
- `NORTH_TURNOVER_SHARE` (使用MADZ): 0/798个有效评分
- 综合评分全部为0.0

## 解决方案

修改 `calculate_scores` 方法的计算顺序：

```python
# 正确的流程（新代码）：
1. 对每个指标独立计算Z分数和评分（使用各自原始的时间序列）
2. Z分数和评分计算完成后，再对齐所有序列到统一的日期索引
3. 这样每个指标都能基于自己的完整数据进行滚动窗口计算
```

## 关键代码修改

### core/pipeline.py - calculate_scores方法

**修改前（第549-592行）**：
```python
# 对齐所有序列到统一的日期索引（取并集）
df = pd.DataFrame(
    {code: transformed_data[code].reindex(all_dates) for code in scoring_codes},
    index=all_dates
)

# 准备批量标准化配置
data_dict = {code: df[code] for code in df.columns}  # ❌ 使用对齐后的数据

# 批量标准化（返回字典）
z_dict = batch_standardize(data_dict, config_dict)  # ❌ Z分数计算基于有NaN的数据
```

**修改后**：
```python
# ✅ 先对每个指标独立计算Z分数和评分
z_dict = {}
score_dict = {}

for code in scoring_codes:
    series = transformed_data[code]  # ✅ 使用原始序列，不对齐
    indicator = self.indicator_lookup.get(code, {})
    
    # 计算Z分数
    z = standardize_with_direction(
        series,
        direction=indicator.get('direction', 'up_good'),
        z_type=indicator.get('z_type', 'Z'),
        window=indicator.get('z_window', 60)
    )
    
    # 计算评分
    score = score_from_z(z, center=50, scale=10)
    
    z_dict[code] = z
    score_dict[code] = score

# ✅ Z分数和评分计算完成后，再对齐
df = pd.DataFrame(
    {code: transformed_data[code].reindex(all_dates) for code in scoring_codes},
    index=all_dates
)
```

### core/pipeline.py - save_to_database方法

添加了更详细的调试信息，帮助诊断问题：

```python
print(f"[DEBUG] 准备保存 {len(all_series_codes)} 个序列的数据")
print(f"[DEBUG] scores DataFrame: {scores.shape}, 列名前10个: {list(scores.columns)[:10]}")
print(f"[DEBUG] scores索引类型: {type(scores.index)}, 前3个: {list(scores.index[:3])}")

# 检查评分数据是否有效
score_cols = [col for col in scores.columns if '_score' in col]
if score_cols:
    sample_col = score_cols[0]
    non_nan = scores[sample_col].notna().sum()
    if non_nan > 0:
        print(f"[DEBUG] 样例评分列 {sample_col}: {non_nan}/{len(scores)} 个有效值, 范围: {scores[sample_col].min():.2f}-{scores[sample_col].max():.2f}")
```

## 修复效果

### 修复前
```
CN_MARGIN_SLOPE: Z分数: 48/798 个有效, 评分: 48/798 个有效
CNH_PCT20: Z分数: 0/798 个有效, 评分: 0/798 个有效
NORTH_TURNOVER_SHARE: Z分数: 0/798 个有效, 评分: 0/798 个有效
综合评分范围: 0.0 - 27.0 (实际全是0)
总共保存 96 条评分数据
```

### 修复后
```
CN_MARGIN_SLOPE: Z分数: 670/730 个有效, 评分: 670/730 个有效
CNH_PCT20: Z分数: 645/763 个有效, 评分: 645/763 个有效
NORTH_TURNOVER_SHARE: Z分数: 586/704 个有效, 评分: 586/704 个有效
综合评分范围: 0.0 - 59.0 (实际有分布)
总共保存 3445 条评分数据（+3349条）
```

## 辅助工具

创建了 `recalculate_scores.py` 脚本，可以基于数据库中已有的原始数据重新计算评分，无需重新获取数据：

```bash
python recalculate_scores.py
```

该脚本会：
1. 从数据库加载所有指标的value_tr数据
2. 对每个指标独立计算Z分数和评分
3. 计算综合评分
4. 更新数据库中的z和score字段
5. 更新数据库中的composite_score和regime

## 技术要点

### 为什么对齐顺序很重要？

1. **滚动窗口计算需要连续数据**
   - MAD-Z、标准Z都需要一个滚动窗口（如60天）的历史数据
   - 如果数据开头有大量NaN，窗口内全是NaN，无法计算中位数/均值

2. **不同指标的起始日期不同**
   - `CN_MARGIN_SLOPE` 可能从2022-12-05开始
   - `ETF_NETFLOW_5D` 可能从2023-06-01开始
   - 取并集对齐后，`ETF_NETFLOW_5D`在2022-12-05到2023-05-31期间全是NaN

3. **正确的做法**
   - 每个指标使用自己的完整时间序列计算Z分数
   - 计算完成后再对齐，这样只是在显示/存储时补充NaN，不影响计算

## 相关文件

- `core/pipeline.py` - 主要修复文件
- `recalculate_scores.py` - 辅助工具：重新计算评分
- `test_recalc_scoring.py` - 测试脚本
- `test_madz.py` - MADZ计算测试
- `check_db_data.py` - 数据库数据检查

## 后续建议

1. ✅ 已修复：Pipeline评分计算逻辑
2. ✅ 已验证：使用测试脚本验证修复效果
3. ⏭️ 待测试：在GUI中查看评分数据和综合评分曲线
4. ⏭️ 待运行：对US市场也执行相同的修复测试

## 日期

2025-12-07

