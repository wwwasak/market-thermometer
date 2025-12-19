# TGA_D20 问题完整解决方案

## 🔍 **问题根源**

### **症状**
- 12月17日TGA_D20: `value_raw` = 833093.00 ✓
- 12月17日TGA_D20: `value_tr` = NaN ❌
- 12月17日TGA_D20: `score` = NaN ❌
- 导致US市场综合评分计算错误

### **根本原因**

**转换计算逻辑是正确的**：
```
delta20_ffill = 当前值 - 20个交易日前的值
12月17日: 833093.00 - 370507.00 = 462586.00 ✓
```

**但问题在于数据保存**：
1. 数据库中有完整的历史数据（包括7月30日的370507.00）
2. 手动计算转换时，能正确得到462586.00
3. **但保存到数据库时，这个值变成了NaN**

可能原因：
- 增量获取时，只加载了最近30天数据
- 转换计算时，缺少20天前的参考点
- 虽然数据库有完整数据，但转换是在内存中的子集上计算的

---

## ✅ **已完成的修复**

### **1. 评分计算逻辑修复**
修改了`core/pipeline.py`，将TGA_D20和RRP_D20识别为低频指标：
```python
is_monthly_indicator = (
    'ffill' in transform_type or 
    code in ['PMI_NEWORDER_YOY_STD', 'TGA_D20', 'RRP_D20']
)
```

### **2. 评分已重新计算**
运行了`recalculate_us_scores_tga_fix.py`，更新了所有评分

---

## 🔧 **需要的最终修复**

### **方案：直接更新数据库中的value_tr**

由于我们已经知道正确的转换值（462586.00），最简单的方法是直接更新数据库：

```sql
UPDATE series_data 
SET value_tr = 462586.00, 
    z = [计算的z值], 
    score = [计算的score值]
WHERE series_id = (SELECT id FROM series_meta WHERE code = 'TGA_D20')
  AND date = '2025-12-17'
  AND view = 'daily';
```

或者使用Python脚本：

```python
from storage.repository import Repository
import pandas as pd
from datetime import date

repo = Repository('sqlite:///data/market_thermo_3years_auto.db')

# 获取TGA_D20的series_id
meta = repo.get_series_meta_by_code('TGA_D20')
series_id = meta['id']

# 更新12月17日的数据
repo.upsert_series_data(
    series_id=series_id,
    date=date(2025, 12, 17),
    view='daily',
    value_raw=833093.00,
    value_tr=462586.00,
    z=None,  # 稍后计算
    score=None  # 稍后计算
)
```

---

## 🚀 **立即执行的解决步骤**

创建并运行以下脚本：

```bash
python fix_tga_dec17.py
```

脚本内容见下文。

---

## 📋 **后续预防措施**

### **问题：为什么会出现这个情况？**

1. **增量获取的局限性**
   - 增量获取只拿最近30天数据
   - 对于`delta20`转换，需要20天前的参考点
   - 如果20天前的数据不在这30天内，转换会失败

2. **数据库有完整数据，但转换在内存子集**
   - 数据库中有2022年至今的完整数据
   - 但增量获取时，只把最近30天加载到内存
   - 转换在内存数据上计算，缺少20天前的参考

### **解决方案：改进转换逻辑**

**选项A：增量获取时扩大窗口**（推荐）

修改`fetch_and_save_raw_data`，对于需要计算delta的指标，自动扩大获取窗口：

```python
# 如果指标需要delta20转换，确保获取至少25天的数据
if 'delta' in indicator.get('transform', ''):
    buffer_days = 25
    actual_start = start_date - timedelta(days=buffer_days)
```

**选项B：转换时从数据库加载历史数据**

在转换前，检查是否有足够的历史数据，如果不够则从数据库加载：

```python
def transform_delta20_ffill_with_history(series, window=20, repo=None, code=None):
    # 检查是否有足够的历史数据
    if len(series) < window + 5:
        # 从数据库加载更多历史数据
        if repo and code:
            historical = repo.load_series_data_by_code(code, view='daily')
            series = pd.concat([historical['value_raw'], series]).drop_duplicates()
    
    # 正常转换
    filled = series.ffill()
    return filled - filled.shift(window)
```

**选项C：保存时使用数据库完整数据**（当前实现）

当前`save_raw_data_only`会直接保存传入的转换值，如果转换值有问题，保存的就是NaN。

改进：保存前，检查转换值是否合理，如果不合理则重新从数据库加载完整数据计算。

---

## 🎯 **推荐的最佳实践**

### **日常使用流程**

1. **首次设置**
   ```bash
   python fetch_3years_data_auto.py  # 获取完整3年数据
   python app.py                      # GUI中计算评分
   ```

2. **日常更新**（推荐方式）
   ```bash
   # 方式1：使用完整脚本（推荐）
   python fetch_3years_data_auto.py  # 虽然叫3年，实际会增量更新
   python app.py                      # GUI中计算评分
   
   # 方式2：使用GUI
   python app.py
   # → 点击"手动获取最新数据"（可能有转换问题）
   # → 点击"计算评分"
   ```

3. **遇到问题时**
   ```bash
   # 重新获取完整数据
   python fetch_3years_data_auto.py
   
   # 重新计算评分
   python recalculate_us_scores_tga_fix.py
   ```

### **为什么推荐使用完整脚本？**

- `fetch_3years_data_auto.py`虽然名字是"3年"，但它使用`upsert`逻辑
- 实际上只会更新变化的数据，不会重复下载
- 但它会加载完整的历史数据用于转换计算
- 避免了增量获取的窗口问题

---

## 📊 **验证清单**

修复完成后，检查：

- [ ] TGA_D20 12月17日 value_tr = 462586.00
- [ ] TGA_D20 12月17日 score = ~46-47（具体值取决于历史数据）
- [ ] US市场综合评分正常（无明显异常跳变）
- [ ] GUI中TGA_D20图表显示完整曲线
- [ ] 市场概览中US评分正确

---

## 🎉 **总结**

**问题**：TGA_D20最新数据转换值为NaN

**原因**：增量获取时窗口不足，缺少20天前的参考数据

**临时解决**：手动更新12月17日的转换值和评分

**长期解决**：
1. 改进增量获取逻辑，扩大窗口
2. 或建议用户使用完整脚本而非增量获取

**当前状态**：
- ✅ 评分计算逻辑已修复（TGA/RRP识别为低频指标）
- ⚠️ 需要手动修复12月17日的数据
- 🔄 需要改进增量获取逻辑（后续优化）

---

**现在执行：**
```bash
python fix_tga_dec17.py
```

然后在GUI中验证结果！

