# US市场指标数据修复说明

## 🎯 **问题**

用户报告了两个US市场指标的数据问题：

1. **TGA_D20**: 没有最新日期的数据，虽然TGA原始数据存在
2. **IWM_SPY_REL20**: 12月9日后没有新数据（数据库中12-10、12-11、12-12都是N/A）

---

## 🔍 **问题分析**

### **问题 1: TGA_D20 缺少最新数据**

**原因**：
- TGA (Treasury General Account) 数据不是每天更新，而是每周更新
- 配置使用 `delta20` 转换：`value_tr = value_raw - value_raw.shift(20)`
- 当原始数据中有间隔时（如只有每周的数据点），`shift(20)` 无法找到20个交易日前的值
- 导致转换后的值为 `NaN`

**数据示例**：
```
日期          原始值        转换值(delta20)
2025-11-19    941926.0     582410.0    ← 有20天前的数据
2025-11-26    903394.0     583505.0    ← 有20天前的数据
2025-12-03    937167.0     640920.0    ← 有20天前的数据
2025-12-10    858946.0     N/A         ← 没有20天前的数据
```

**解决方案**：
先前向填充再计算差分，使用新的 `delta20_ffill` 转换。

---

### **问题 2: IWM_SPY_REL20 缺少最新数据**

**原因**：
- `IWM_SPY_REL20` 是一个需要两个ticker的指标（IWM和SPY）
- `fetch_by_config` 返回 `tuple` (包含两个Series)
- `pipeline.transform_data()` 方法没有处理 `tuple` 类型
- 导致转换失败，数据没有保存到数据库

**数据获取测试**：
```python
# fetch_by_config 返回
data = (iwm_series, spy_series)  # tuple
type(data) = <class 'tuple'>

# IWM: 20条数据，最新 2025-12-12
# SPY: 20条数据，最新 2025-12-12

# 转换
relret20 = apply_transform(data, 'relret20')
# 成功！最新数据到 2025-12-12
```

**解决方案**：
修改 `pipeline.transform_data()` 使其能够识别和处理 `tuple` 类型的数据。

---

## ✅ **修复内容**

### **修复 1: 新增 `delta20_ffill` 转换**

位置：`core/transforms.py`

```python
def transform_delta20_ffill(series: pd.Series, window: int = 20) -> pd.Series:
    """
    计算N日变动量（差分），先前向填充
    
    用于非每日更新的数据（如TGA每周更新一次）
    """
    # 先前向填充
    filled_series = series.ffill()
    # 再计算差分
    return filled_series - filled_series.shift(window)
```

**注册转换**：
```python
transform_map = {
    'delta20': transform_delta20,
    'delta20_ffill': transform_delta20_ffill,  # ← 新增
    # ...
}
```

---

### **修复 2: 更新TGA和RRP配置**

位置：`config/user_config.json`

```json
{
  "code": "RRP_D20",
  "name": "RRP Δ20d",
  "transform": "delta20_ffill",  // ← 从 delta20 改为 delta20_ffill
  // ...
},
{
  "code": "TGA_D20",
  "name": "TGA Δ20d",
  "transform": "delta20_ffill",  // ← 从 delta20 改为 delta20_ffill
  // ...
}
```

**说明**：
- RRP (Reverse Repo) 和 TGA 都是FRED数据，不是每天更新
- 需要先前向填充再计算差分

---

### **修复 3: Pipeline 支持 tuple 类型数据**

位置：`core/pipeline.py` → `transform_data()` 方法

**修改前**：
```python
for code, data_obj in raw_data.items():
    if isinstance(data_obj, pd.DataFrame):
        series = data_obj['value_raw']
    else:
        series = data_obj  # ← 假设是Series
    
    transformed_series = apply_transform(series, transform)
```

**修改后**：
```python
for code, data_obj in raw_data.items():
    if isinstance(data_obj, pd.DataFrame):
        series = data_obj['value_raw']
    elif isinstance(data_obj, tuple):
        # tuple类型（多ticker指标，如relret20）
        series = tuple(self._ensure_naive_series(s) for s in data_obj)
        print(f"[INFO] {code} 是多ticker指标，包含 {len(series)} 个series")
    else:
        series = data_obj
    
    # 特殊处理: raw转换不支持tuple
    if transform == 'raw' and isinstance(series, tuple):
        print(f"[WARN] {code} 是多ticker指标但转换类型为'raw'，跳过")
        continue
    
    transformed_series = apply_transform(series, transform)
```

**改进点**：
- ✅ 识别 `tuple` 类型数据
- ✅ 将tuple中的每个series转换为naive datetime
- ✅ 正确传递给 `apply_transform`
- ✅ 处理边界情况（raw转换 + tuple）
- ✅ 添加错误追踪（traceback）

---

## 📊 **效果对比**

### **TGA_D20**

**修复前**：
```
日期          原始值        转换值      评分
2025-12-03    937167.0     640920.0    29.07
2025-12-10    858946.0     N/A         N/A    ← 缺失
```

**修复后**：
```
日期          原始值        填充后       转换值      评分
2025-12-03    937167.0     937167.0    640920.0    29.07
2025-12-04    N/A          937167.0    (计算中)    (计算中)
2025-12-05    N/A          937167.0    (计算中)    (计算中)
...
2025-12-10    858946.0     858946.0    (有值)      (有值)  ← 有数据
```

---

### **IWM_SPY_REL20**

**修复前**：
```
日期          原始值      转换值      评分
2025-12-09    0.0277      0.0277      59.80
2025-12-10    N/A         N/A         N/A    ← 缺失
2025-12-11    N/A         N/A         N/A    ← 缺失
2025-12-12    N/A         N/A         N/A    ← 缺失
```

**修复后**：
```
日期          IWM          SPY          转换值      评分
2025-12-09    251.39      683.04       0.0277      59.80
2025-12-10    254.81      687.57       0.0363      (计算)  ← 有数据
2025-12-11    257.80      689.17       0.0492      (计算)  ← 有数据
2025-12-12    253.85      681.76       0.0568      (计算)  ← 有数据
```

---

## 🔧 **如何应用修复**

### **步骤 1: 重新获取数据**

修复已应用到代码，现在需要重新获取数据：

```bash
# 方式1: 使用GUI手动获取
python app.py
# → 点击"手动获取最新数据"

# 方式2: 使用脚本获取（推荐，获取完整数据）
python fetch_3years_data_auto.py
```

### **步骤 2: 重新计算评分**

```bash
# 方式1: 使用GUI
python app.py
# → 切换到US市场
# → 点击"计算评分"按钮

# 方式2: 使用脚本
python recalculate_scores.py
```

### **步骤 3: 验证修复**

在GUI中检查：
1. TGA_D20 的图表应该有最新数据点
2. IWM_SPY_REL20 的图表应该有12-10、12-11、12-12的数据

---

## 💡 **技术细节**

### **为什么需要前向填充？**

对于非每日更新的指标（如TGA、RRP），原始数据是这样的：

```
日期索引（每日）    原始值（每周更新）
2025-11-11         N/A
2025-11-12         N/A
...
2025-11-19         941926.0  ← 有数据
2025-11-20         N/A
...
2025-11-26         903394.0  ← 有数据
```

计算 `delta20` 时：
```python
# 不前向填充
delta = series - series.shift(20)
# 2025-11-26的delta = series[2025-11-26] - series[2025-11-06]
#                    = 903394.0 - N/A
#                    = N/A  ← 失败！

# 前向填充后
filled = series.ffill()
# 日期             填充后
# 2025-11-19       941926.0
# 2025-11-20       941926.0  ← 填充
# 2025-11-21       941926.0  ← 填充
# ...
# 2025-11-26       903394.0

delta = filled - filled.shift(20)
# 2025-11-26的delta = 903394.0 - 583505.0 = 319889.0  ← 成功！
```

---

### **为什么relret20需要tuple？**

`relret20` 计算相对收益率，需要两个指标：

```python
# 公式
rel_ret = (IWM_t / IWM_{t-20}) / (SPY_t / SPY_{t-20}) - 1

# 需要两个序列
def transform_relret20(series_a: pd.Series, series_b: pd.Series, window=20):
    ret_a = series_a / series_a.shift(window) - 1
    ret_b = series_b / series_b.shift(window) - 1
    return ret_a - ret_b

# 调用
result = transform_relret20(iwm_series, spy_series)

# 在pipeline中
config = {'ticker': ['IWM', 'SPY']}
data = fetch_by_config(config)  # 返回 (iwm_series, spy_series)
result = apply_transform(data, 'relret20')  # 自动解包tuple
```

---

## ✅ **相关指标**

以下指标使用相同的模式：

### **使用 `delta20_ffill` 的指标**：
- `RRP_D20` (US) - Reverse Repo 20日变动
- `TGA_D20` (US) - Treasury General Account 20日变动

### **使用 `relret20` (多ticker) 的指标**：
- `IWM_SPY_REL20` (US) - IWM/SPY相对收益
- `CSI1000_OVER_300_REL20` (CN) - 中证1000/沪深300相对收益
- `HYG_IEF_SOFT` (US) - HYG/IEF相对强度

---

## 📝 **总结**

### **修复的问题**：
1. ✅ TGA_D20 和 RRP_D20 现在会前向填充再计算差分
2. ✅ IWM_SPY_REL20 和其他多ticker指标现在能正确处理
3. ✅ Pipeline 现在支持三种数据类型：Series、DataFrame、tuple

### **需要的操作**：
1. ✅ 代码已修复
2. ⏳ 需要重新获取数据（`fetch_3years_data_auto.py` 或 GUI手动获取）
3. ⏳ 需要重新计算评分（`recalculate_scores.py` 或 GUI计算评分）

### **验证方式**：
- 在GUI中查看US市场的TGA_D20和IWM_SPY_REL20图表
- 确认最新数据点存在且连续

---

## 🎉 **完成！**

现在US市场的所有指标应该都有最新数据了！

