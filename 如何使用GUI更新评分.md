# 如何使用GUI更新评分

## 🎯 **问题：评分没有使用最新数据**

你已经通过"手动获取数据"更新了VIX_LOG的TR值，但评分还在使用旧数据。

---

## ✅ **解决方案：点击"计算评分"按钮**

### 完整操作步骤

#### 1. 启动GUI

```powershell
python app.py
```

#### 2. 计算评分

在GUI界面中：

1. 切换到 **"市场概览"** 标签页
2. 选择 **US市场**
3. 点击 **"计算评分"** 按钮
4. 等待计算完成（通常几秒钟）

#### 3. 验证结果

- 查看VIX_LOG的评分
- 确认评分时间是最新的（2026-01-08）
- US市场的综合评分应该反映最新状态

---

## 📖 **为什么需要两步操作？**

Market-Thermometer的设计分为两个独立步骤：

### 步骤1: "手动获取数据" ✓（你已完成）
- 从yfinance等数据源获取最新数据
- 计算transformed值（如VIX_LOG的log_winsor）
- 保存 `value_raw` 和 `value_tr` 到数据库

### 步骤2: "计算评分" ⚠️（你需要做这一步）
- 从数据库加载TR值
- 计算Z分数（标准化）
- 计算0-100分的评分
- 保存 `z` 和 `score` 到数据库

**这种设计的好处**：
- 可以只获取数据而不重新计算所有历史评分
- 可以在不重新获取数据的情况下调整评分参数
- 灵活性更高

**注意事项**：
- 每次手动获取数据后，记得重新计算评分
- 否则评分会使用旧的TR值

---

## 🔧 **命令行方式（可选）**

如果GUI出现问题，也可以通过命令行计算评分：

### 方式1: 使用现有脚本

```powershell
python recalculate_scores.py --market US
```

### 方式2: 使用Python代码

```python
from core.pipeline import MarketPipeline

# 创建pipeline
pipeline = MarketPipeline(
    market='US',
    database_url='sqlite:///data/market_thermometer.db'
)

# 从数据库加载数据
transformed_data = {}
for indicator in pipeline.indicators:
    code = indicator['code']
    df = pipeline.repository.load_series_data_by_code(code, view='daily')
    if df is not None and 'value_tr' in df.columns:
        transformed_data[code] = df['value_tr'].dropna()

# 计算派生指标
raw_data, transformed_data = pipeline.calculate_derived_indicators({}, transformed_data)

# 计算评分
scores, composite = pipeline.calculate_scores(transformed_data, view_type='daily')

# 应用确认层
confirm_results = pipeline.apply_confirm_layer(scores, view_type='daily')

# 保存到数据库
pipeline.save_to_database({}, transformed_data, scores, confirm_results, composite, view_type='daily')

print("评分已更新！")
```

---

## 📊 **预期结果**

计算评分完成后，VIX_LOG应该显示：

```
VIX_LOG评分（最新5条）:
2026-01-08: TR=2.7376, Z=0.34, Score=53.38 ✓
2026-01-07: TR=2.7331, Z=0.39, Score=53.88 ✓
2026-01-06: TR=2.6912, Z=0.60, Score=56.05 ✓
2026-01-05: TR=2.7014, Z=0.55, Score=55.52 ✓
2026-01-02: TR=2.6748, Z=0.73, Score=57.27 ✓
```

US市场的综合评分和态势（Regime）也会更新到最新。

---

## 🎉 **现在就去GUI点击"计算评分"吧！**

所有问题都会解决！

