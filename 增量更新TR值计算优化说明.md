# 增量更新TR值计算优化说明

## 📋 **问题背景**

### **问题现象**
VIX_LOG在GUI数据完整性检查中显示的最新日期不是数据库中实际最新的日期。例如：
- 数据库中有1月20日的`value_raw`
- 但数据完整性检查只显示到1月12日
- 评分计算也只使用了1月12日的数据

### **根本原因**
增量更新时，新数据的`value_tr`（转换值）没有被正确计算：

1. **顺序问题**：GUI手动获取新数据时
   - 先基于当前内存中的数据计算转换（数据不完整）
   - 然后保存`value_raw`和`value_tr`到数据库
   - 结果：新数据的TR值基于不完整数据集计算，可能错误或缺失

2. **转换依赖问题**：某些转换需要完整数据集的统计特性
   - `log_winsor`：需要所有历史数据的1%和99%分位数
   - `yoy_std_ffill`：需要12个月的历史数据
   - `pct_change`：需要前一个数据点
   - 如果基于不完整数据计算，TR值会不准确

3. **评分依赖**：评分计算依赖完整的数据链
   ```
   value_raw → value_tr → z-score → score
   ```
   如果`value_tr`缺失或错误，整个链条中断

---

## ✅ **优化方案**

### **核心思想**
**保存raw数据后，立即基于包含新数据在内的完整数据集重新计算所有TR值**

### **实现流程**

```
1. GUI手动获取数据
   ↓
2. 保存 value_raw 到数据库
   ↓
3. 从数据库重新加载完整 raw 数据（包含新数据）
   ↓
4. 基于完整数据集重新计算 value_tr
   ↓
5. 更新数据库中的 value_tr
   ↓
6. 用户点击"计算评分"时，使用正确的 TR 值
```

---

## 🔧 **代码修改**

### **1. 新增 `recalculate_tr_values` 方法** (`core/pipeline.py`)

```python
def recalculate_tr_values(
    self,
    codes: Optional[List[str]] = None,
    view_type: str = 'daily',
    days_limit: Optional[int] = None
) -> int:
    """
    重新计算指定指标的TR值（基于数据库中的完整raw数据）
    
    关键：此方法在保存新raw数据后调用，确保基于包含新数据在内的完整数据集计算TR值
    """
```

**功能**：
1. 从数据库加载指定指标的所有raw数据
2. 应用转换函数计算TR值（基于完整数据集）
3. 更新数据库中的TR值

### **2. 修改 `save_raw_data_only` 方法** (`core/pipeline.py`)

**新增参数**：
```python
recalculate_tr: bool = True  # 保存后是否重新计算TR值
```

**保存流程**：
```python
# 1. 保存 raw 和 tr 数据（tr可能基于不完整数据计算）
for code in all_series_codes:
    self.repository.upsert_series_data(...)

# 2. 重要：保存后立即重新计算TR值
if recalculate_tr:
    codes_to_recalc = [需要转换的指标]
    self.recalculate_tr_values(
        codes=codes_to_recalc,
        view_type=view_type,
        days_limit=None  # 重新计算所有历史数据
    )
```

### **3. 新增 `get_series_data_point` 方法** (`storage/repository.py`)

```python
def get_series_data_point(
    self,
    series_id: int,
    date: date,
    view: str = 'daily'
) -> Optional[Dict]:
    """
    获取指定序列、日期、视图的单个数据点
    """
```

**用途**：在更新TR值时，保留其他字段（raw、z、score）不变

---

## 📊 **优化效果**

### **修复前**
```
2026-01-20  value_raw: 20.09  value_tr: NaN      score: NaN  ❌
2026-01-19  value_raw: 18.84  value_tr: NaN      score: NaN  ❌
2026-01-16  value_raw: 15.86  value_tr: NaN      score: NaN  ❌
2026-01-15  value_raw: 15.84  value_tr: NaN      score: NaN  ❌
2026-01-14  value_raw: 16.75  value_tr: NaN      score: NaN  ❌
2026-01-13  value_raw: 15.98  value_tr: NaN      score: NaN  ❌
2026-01-12  value_raw: 15.12  value_tr: 2.716018 score: 52.9 ✅
```
**问题**：最新6天只有raw值，无法参与评分计算

### **修复后**
```
2026-01-20  value_raw: 20.09  value_tr: 3.000222 score: (待计算) ✅
2026-01-19  value_raw: 18.84  value_tr: 2.935982 score: (待计算) ✅
2026-01-16  value_raw: 15.86  value_tr: 2.763800 score: (待计算) ✅
2026-01-15  value_raw: 15.84  value_tr: 2.762538 score: (待计算) ✅
2026-01-14  value_raw: 16.75  value_tr: 2.818398 score: (待计算) ✅
2026-01-13  value_raw: 15.98  value_tr: 2.771338 score: (待计算) ✅
2026-01-12  value_raw: 15.12  value_tr: 2.716018 score: 52.9   ✅
```
**改进**：所有数据都有TR值，可以参与评分计算

---

## 🎯 **使用说明**

### **GUI手动获取数据**
1. 点击"手动获取数据"按钮
2. 选择日期范围和市场
3. 系统会自动：
   - 获取raw数据
   - 保存到数据库
   - **自动重新计算TR值**（新增）✨
4. 点击"计算评分"使用完整数据

### **脚本批量获取数据**
```python
# fetch_3years_data_auto.py
saved_count = pipeline.save_raw_data_only(
    raw_data, 
    transformed_data, 
    view_type='daily',
    recalculate_tr=True  # 默认开启自动重算
)
```

### **手动触发TR重算**（如需要）
```python
pipeline = MarketPipeline(market='US', database_url=db_url)

# 重新计算所有指标
pipeline.recalculate_tr_values()

# 或只重新计算特定指标
pipeline.recalculate_tr_values(codes=['VIX_LOG', 'HY_OAS'])
```

---

## ⚠️ **注意事项**

### **1. 性能影响**
- **重新计算TR会遍历所有历史数据**，对于大数据集可能需要几秒钟
- 优化建议：只在保存新数据后重算，不需要每次查询都重算

### **2. 数据一致性**
- 所有TR值都基于完整数据集的统计特性计算
- 如果添加大量历史数据，可能需要重新计算所有TR值

### **3. 评分计算时机**
- TR值重算后，需要在GUI中点击"计算评分"
- 评分计算会基于最新的TR值重新计算z-score和score

### **4. 禁用自动重算（特殊场景）**
如果在批量导入历史数据时不想每次都重算，可以禁用：
```python
pipeline.save_raw_data_only(
    raw_data, 
    transformed_data,
    recalculate_tr=False  # 禁用自动重算
)

# 所有数据导入完成后，手动触发一次
pipeline.recalculate_tr_values()
```

---

## 📈 **性能数据**

基于VIX_LOG（762条历史数据）的测试：
- **重新计算TR**: ~0.5秒
- **更新数据库**: ~2秒
- **总耗时**: ~2.5秒

对于GUI手动获取数据（通常50-100条），增加的时间可以接受。

---

## 🔍 **验证方法**

### **检查TR值完整性**
```sql
-- 查询有raw但没有tr的数据
SELECT sm.code, COUNT(*) as missing_count
FROM series_data sd
JOIN series_meta sm ON sd.series_id = sm.id
WHERE sm.market = 'US'
  AND sd.value_raw IS NOT NULL
  AND sd.value_tr IS NULL
GROUP BY sm.code;
```

**期望结果**：0条记录

### **检查最新数据**
```sql
-- 查询指标最新数据
SELECT sd.date, sd.value_raw, sd.value_tr, sd.score
FROM series_data sd
JOIN series_meta sm ON sd.series_id = sm.id
WHERE sm.code = 'VIX_LOG' AND sm.market = 'US'
ORDER BY sd.date DESC
LIMIT 10;
```

**期望结果**：所有最新数据都有value_tr

---

## ✅ **总结**

### **优化前的问题**
- ❌ 增量更新时新数据TR值缺失或不准确
- ❌ 评分计算无法使用最新数据
- ❌ 数据完整性检查显示过时日期

### **优化后的改进**
- ✅ 新数据保存后自动重新计算TR值
- ✅ TR值基于完整数据集计算，准确可靠
- ✅ 评分可以使用所有最新数据
- ✅ 数据完整性检查显示正确日期

### **关键改进点**
1. **正确的计算顺序**：先保存raw → 重新加载完整数据 → 计算TR
2. **完整数据集**：TR计算基于包含新数据的完整历史数据
3. **自动化**：无需手动干预，保存数据时自动触发

---

**修改日期**: 2026-01-21  
**影响范围**: `core/pipeline.py`, `storage/repository.py`  
**向后兼容**: ✅ 完全兼容，默认开启自动重算
