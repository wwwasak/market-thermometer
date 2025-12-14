# US市场指标完整修复指南

## 🎯 **问题现状**

用户报告：GUI手动获取后还是没有TGA_D20和IWM_SPY_REL20最新的指标数据

**诊断结果**：
1. ✅ 配置文件已更新（`delta20` → `delta20_ffill`）
2. ✅ 代码已修复（支持tuple类型）
3. ❌ **数据库元数据未更新**（还是旧的 `delta20`）
4. ❌ **tuple类型数据保存逻辑缺失**

---

## 🔧 **已完成的修复**

### **修复 1: 数据库元数据已更新**

运行了 `update_us_transforms.py` 脚本，更新了：
- `TGA_D20`: `delta20` → `delta20_ffill`
- `RRP_D20`: `delta20` → `delta20_ffill`

### **修复 2: Pipeline 完整支持 tuple**

修改了两处保存逻辑：

#### **`save_raw_data_only()` 方法**

```python
elif isinstance(raw_obj, tuple):
    # tuple类型（多ticker指标），使用转换后的序列作为原始值
    raw_series = trans_series.copy()
    print(f"[INFO] {code} 是多ticker指标，使用转换后的值作为原始值")
```

#### **`save_to_database()` 方法**

```python
elif isinstance(raw_obj, tuple):
    # tuple类型（多ticker指标），使用转换后的序列作为原始值
    raw_series = trans_series.copy()
```

**说明**：
- 多ticker指标（如IWM_SPY_REL20）的原始数据是tuple（包含两个Series）
- 数据库中的 `value_raw` 字段只能保存单个数值
- 因此将转换后的相对收益率保存为原始值
- 这样可以正常显示和评分

---

## 📋 **完整修复清单**

### ✅ **已完成的修复**

1. ✅ 新增 `delta20_ffill` 转换类型（`core/transforms.py`）
2. ✅ 更新配置文件中的转换类型（`config/user_config.json`）
3. ✅ Pipeline支持tuple类型转换（`core/pipeline.py` - `transform_data`）
4. ✅ 更新数据库元数据（运行了 `update_us_transforms.py`）
5. ✅ Pipeline支持tuple类型保存（`core/pipeline.py` - `save_raw_data_only` 和 `save_to_database`）

### ⏳ **需要执行的操作**

1. ⏳ 重新获取US市场数据
2. ⏳ 重新计算US市场评分

---

## 🚀 **执行步骤**

### **方式 1: 使用脚本（推荐，最彻底）**

```bash
# 步骤1: 重新获取3年历史数据
python fetch_3years_data_auto.py

# 这会：
# - 获取US和CN市场的3年数据
# - 使用新的delta20_ffill转换
# - 正确保存tuple类型指标
# - 只保存原始数据和转换值（不保存评分）

# 步骤2: 重新计算评分
python recalculate_scores.py

# 这会：
# - 从数据库读取所有原始数据
# - 使用更新后的元数据重新转换
# - 计算评分并保存
```

---

### **方式 2: 使用GUI（快速但不彻底）**

```bash
python app.py
```

**在GUI中**：

1. **切换到US市场**

2. **点击"手动获取最新数据"**
   - 获取最近7天的原始数据
   - 使用新的转换逻辑

3. **点击"计算评分"按钮**
   - 从数据库读取所有历史数据
   - 重新计算转换和评分
   - 保存结果

**注意**：GUI手动获取只获取最近7天，对于历史数据的修复不彻底。推荐使用方式1。

---

## 🔍 **验证修复**

### **方式1: 使用GUI查看**

```bash
python app.py
```

在GUI中检查：

1. **TGA_D20**
   - 切换到US市场
   - 在左侧列表选择 `TGA_D20`
   - 查看图表，应该有最新数据到今天
   - 最新数据点应该有转换值和评分

2. **IWM_SPY_REL20**
   - 在左侧列表选择 `IWM_SPY_REL20`
   - 查看图表，应该有12-10、12-11、12-12的数据
   - 所有最近数据点都应该有转换值和评分

3. **市场综合评分**
   - 切换到"市场概览"标签
   - 查看综合评分图表
   - 应该包含这些指标的最新评分

### **方式2: 使用脚本查看**

创建一个简单的验证脚本：

```python
from storage.repository import Repository
from storage.models import SeriesData, SeriesMeta

database_url = 'sqlite:///data/market_thermo_3years_auto.db'
repository = Repository(database_url)

indicators = ['TGA_D20', 'IWM_SPY_REL20']

with repository.get_session() as session:
    for code in indicators:
        meta = session.query(SeriesMeta).filter(
            SeriesMeta.code == code
        ).first()
        
        if meta:
            print(f"\n{code}:")
            print(f"  转换类型: {meta.transform}")
            
            # 获取最新3条数据
            recent = session.query(SeriesData).filter(
                SeriesData.series_id == meta.id,
                SeriesData.view == 'daily'
            ).order_by(SeriesData.date.desc()).limit(3).all()
            
            for rec in recent:
                print(f"  {rec.date}: raw={rec.value_raw:.2f if rec.value_raw else 'N/A'}, "
                      f"tr={rec.value_tr:.2f if rec.value_tr else 'N/A'}, "
                      f"score={rec.score:.2f if rec.score else 'N/A'}")
```

**预期输出**：

```
TGA_D20:
  转换类型: delta20_ffill
  2025-12-12: raw=858946.00, tr=(有值), score=(有值)
  2025-12-11: raw=858946.00, tr=(有值), score=(有值)
  2025-12-10: raw=858946.00, tr=(有值), score=(有值)

IWM_SPY_REL20:
  转换类型: relret20
  2025-12-12: raw=0.06, tr=0.06, score=(有值)
  2025-12-11: raw=0.05, tr=0.05, score=(有值)
  2025-12-10: raw=0.04, tr=0.04, score=(有值)
```

---

## 💡 **技术要点**

### **1. 为什么需要 `delta20_ffill`？**

TGA和RRP数据不是每天更新：

```
日期          TGA原始值
2025-12-03    937167.0   ← 周二有数据
2025-12-04    (无)
2025-12-05    (无)
...
2025-12-10    858946.0   ← 周二有数据
```

使用 `delta20`:
```python
delta = series - series.shift(20)
# 2025-12-10的值 = 858946 - series[20天前]
# 但20天前可能没有数据 → N/A
```

使用 `delta20_ffill`:
```python
filled = series.ffill()  # 先前向填充
# 日期          填充后
# 2025-12-03    937167.0
# 2025-12-04    937167.0  ← 填充
# 2025-12-05    937167.0  ← 填充
# ...
# 2025-12-10    858946.0

delta = filled - filled.shift(20)
# 现在20天前有值了 → 成功！
```

---

### **2. 为什么tuple指标的value_raw = value_tr？**

对于多ticker指标（如IWM_SPY_REL20）：

- **原始数据**: `(iwm_series, spy_series)` - tuple类型
- **转换后**: `relret20_series` - 单个Series

数据库设计：
```
SeriesData表:
- value_raw: Float  ← 只能存单个数值
- value_tr: Float   ← 只能存单个数值
```

因此：
```python
# 无法保存：
value_raw = (iwm_series, spy_series)  # ❌ 不能存tuple

# 解决方案：
value_raw = relret20_series  # ✅ 保存转换后的值
value_tr = relret20_series   # ✅ 两者相同
```

**优点**：
- ✅ 可以正常保存和查询
- ✅ 图表显示正常
- ✅ 评分计算正常
- ✅ 不影响功能

---

### **3. GUI手动获取为什么还不够？**

GUI手动获取：
- 获取最近7天原始数据
- 使用新的转换逻辑
- 保存到数据库

**问题**：
- 历史数据（7天之前）还是用旧的转换逻辑
- 评分计算会使用所有历史数据
- 因此还是会有问题

**解决方案**：
- 运行 `fetch_3years_data_auto.py` 重新获取所有数据
- 或运行 `recalculate_scores.py` 使用新逻辑重新计算

---

## ⚠️ **常见问题**

### **Q1: 为什么元数据需要更新？**

**A**: 数据库中的元数据（SeriesMeta表）存储了每个指标的转换类型。评分计算时会读取这个元数据来决定使用哪种转换。配置文件改了，但数据库没改，所以还是用旧的转换。

### **Q2: 为什么不能直接删除旧数据重新获取？**

**A**: 可以，但：
1. 删除会丢失历史评分和确认层数据
2. 重新获取需要时间
3. 更好的方式是保留原始数据，只重新计算转换和评分

### **Q3: RRP_D20为什么有些日期是N/A？**

**A**: RRP也不是每天更新。使用 `delta20_ffill` 后，会先填充再计算差分，应该能解决这个问题。

---

## ✅ **总结**

### **修复完成**：
1. ✅ 代码修复：支持 `delta20_ffill` 和 tuple类型
2. ✅ 配置更新：TGA和RRP使用 `delta20_ffill`
3. ✅ 元数据更新：数据库中的转换类型已更新
4. ✅ 保存逻辑：tuple类型可以正确保存

### **下一步**：
1. ⏳ 运行 `python fetch_3years_data_auto.py`（推荐）
2. ⏳ 或在GUI中：手动获取 + 计算评分
3. ✅ 验证结果

现在应该可以看到TGA_D20和IWM_SPY_REL20的最新数据了！🎉

