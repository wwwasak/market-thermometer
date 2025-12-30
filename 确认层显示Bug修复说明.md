# 确认层显示Bug修复

## 问题描述

用户报告：GUI确认层状态中，**硬指标文字显示"绿色"，但表格里显示的是"黄色"**。

## 问题诊断

### 症状
- 汇总信息（Hard Veto/Soft Confirm/Final Lamp）：正确显示绿色 ✅
- 表格中的指标行：显示黄色 ❌

### 根本原因

GUI的`refresh_data`方法在加载确认层数据时：

**旧代码逻辑**（第1941-1954行）：
```python
# 从lamp_history表获取最新灯色
lamp_hist = self.repository.load_lamp_history(
    market=market,
    view=view,
    source_code=code
)

if lamp_hist is not None and not lamp_hist.empty:
    latest_lamp = lamp_hist.iloc[-1]['lamp']
else:
    latest_lamp = '-'
```

**问题**：
1. `lamp_history`表是**空的**（没有数据）
2. 找不到数据时默认为`'-'`
3. `update_confirm_layer`方法中，`'-'`会被显示为**黄色**（else分支，第1242行）

**为什么lamp_history是空的？**
- 这个表本应存储观察者指标的历史灯色
- 但数据计算流程中可能没有正确写入这个表
- 或者表的用途设计不明确

### 数据验证

```sql
-- regimes表（汇总信息）：有数据 ✅
SELECT date, lamp_hard, lamp_soft, lamp_final
FROM regimes WHERE market = 'CN'
ORDER BY date DESC LIMIT 3;

2025-12-26: Hard=G, Soft=Y, Final=Y  ✅ 正确

-- lamp_history表（表格显示）：无数据 ❌
SELECT * FROM lamp_history WHERE market = 'CN';
-- 返回空

-- series_data表（原始评分）：有数据 ✅
SELECT code, date, score
FROM series_data JOIN series_meta
WHERE code = 'ETF_NETFLOW_5D'
ORDER BY date DESC LIMIT 1;

ETF_NETFLOW_5D: score=87.45 → 应该是绿灯 ✅
```

---

## 解决方案

### 修改内容

**文件**：`ui/market_overview.py`  
**方法**：`refresh_data`  
**行数**：1935-1961

**新逻辑**：
```python
# 直接从series_data获取最新score并计算灯色
series_data_df = self.repository.load_series_data(code, view=view)

if series_data_df is not None and not series_data_df.empty and 'score' in series_data_df.columns:
    # 获取最新的非NaN score
    score_series = series_data_df['score'].dropna()
    if not score_series.empty:
        latest_score = score_series.iloc[-1]
        
        # 根据score计算灯色
        green_th = self.config.get(f'markets.{market}.green_threshold', 60)
        red_th = self.config.get(f'markets.{market}.red_threshold', 40)
        
        if latest_score >= green_th:
            latest_lamp = 'G'
        elif latest_score <= red_th:
            latest_lamp = 'R'
        else:
            latest_lamp = 'Y'
```

### 优点

1. **不依赖lamp_history表**：直接从评分数据计算灯色
2. **逻辑一致**：使用与评分系统相同的阈值（green_threshold/red_threshold）
3. **实时准确**：只要有score就能正确显示灯色
4. **容错性好**：如果没有score，显示'-'而不是错误的黄色

---

## 验证步骤

1. **重启GUI**：`python app.py`
2. **切换到CN市场**
3. **查看确认层状态**：
   - 汇总信息：Hard Veto应该显示"绿灯"（文字）
   - 表格：ETF_NETFLOW_5D那一行应该显示**绿色背景**（与文字一致）

### 预期结果

| 指标 | 角色 | Score | 表格显示 | 汇总显示 |
|------|------|-------|---------|---------|
| ETF_NETFLOW_5D | 硬否决 | 87.45 | 绿色 ✅ | Hard Veto: 绿灯 ✅ |
| PAIR_CNH_CNY | 软确认 | 绿色 | 绿色 ✅ | - |
| PAIR_TWEX_DXY | 软确认 | 绿色 | 绿色 ✅ | - |
| - | - | - | - | Soft Confirm: ? |
| - | - | - | - | Final Lamp: ? |

---

## 技术细节

### 灯色计算逻辑

```python
# 标准灯色阈值（可在config.py中配置）
green_threshold = 60  # score ≥ 60 → 绿灯
red_threshold = 40    # score ≤ 40 → 红灯
# 其他情况 → 黄灯
```

### 数据流

```
series_data (score)
      ↓
  计算灯色
      ↓
  observer_data
      ↓
update_confirm_layer
      ↓
  GUI表格显示
```

### 相关代码位置

1. **GUI数据加载**：`ui/market_overview.py` 第1775-1991行 (`refresh_data`)
2. **确认层更新**：`ui/market_overview.py` 第1190-1274行 (`update_confirm_layer`)
3. **灯色背景设置**：`ui/market_overview.py` 第1237-1243行

---

## 后续改进建议

### 1. lamp_history表的用途
- 如果这个表不再使用，考虑从数据库schema中移除
- 或者明确其用途并在数据计算时正确填充

### 2. 配对指标的处理
- PAIR_CNH_CNY和PAIR_TWEX_DXY是配对指标
- 它们本身没有score，而是由两个组件指标组合而成
- 需要特殊处理这类指标的灯色显示

### 3. 跨市场指标
- PAIR_TWEX_DXY位于US市场
- CN市场的确认层需要从US市场读取其数据
- 当前的修复已经支持跨市场查询（之前的pipeline修改）

---

## 总结

✅ **问题**：GUI表格显示黄色，但文字说绿色  
✅ **原因**：依赖空的lamp_history表  
✅ **修复**：直接从series_data的score计算灯色  
✅ **效果**：表格颜色与文字一致  

**请重启GUI验证修复效果！**

