# GUI评分表优化完成 ✅

## 🎯 **解决的问题**

### **问题1：指标有数据但评分表不显示**

**原因**：
- 之前的逻辑是`df.iloc[-1]`，只取最后一行
- 如果最后一行的`score=None`，就什么都不显示
- 导致有`value_raw`和`value_tr`的指标也不显示

**修复**：
- 修改`refresh_data`方法（第1797-1866行）
- 优先查找有`score`的最后一条记录
- 如果没有`score`，退化到查找有`value_tr`的记录
- 如果还没有，再退化到`value_raw`
- 确保只要有数据就显示

### **问题2：评分表缺少数据日期列**

**原因**：
- 用户无法知道每个指标的数据是哪一天的
- 有些指标可能是12月24日，有些是12月26日

**修复**：
- 在表格中添加"数据日期"列（第354-357行）
- 显示每个指标数据的实际日期
- 格式为`YYYY-MM-DD`

### **问题3：评分曲线图缺少最新评分点**

**原因**：
- `update_indicator_chart`会过滤`score > 0`
- 如果某些点是`0`或`NaN`，会被跳过

**修复**：
- 修改为只移除NaN，保留0值（第856行）
- 确保所有有效评分都显示在曲线上

---

## 📋 **修改的文件**

**文件**: `ui/market_overview.py`

### **1. MarketScoreTable类（第322-549行）**

#### **修改1：添加数据日期列**
```python
# 第354-357行
self.table = QTableWidget()
self.table.setColumnCount(7)  # 从6列改为7列
self.table.setHorizontalHeaderLabels([
    "指标代码", "指标名称", "数据日期", "当前值", "Z分数", "评分", "权重(%)"  # 新增"数据日期"
])
```

#### **修改2：update_scores方法支持数据日期**
```python
# 第382-451行
def update_scores(
    self,
    indicator_data: List[Dict],  # 现在每个字典需要包含data_date
    weights: List[float],
    ...
) -> None:
    ...
    # 数据日期
    data_date = ind_data.get('data_date', None)
    if data_date:
        if hasattr(data_date, 'strftime'):
            date_str = data_date.strftime('%Y-%m-%d')
        else:
            date_str = str(data_date)
    else:
        date_str = "-"
    date_item = QTableWidgetItem(date_str)
    self.table.setItem(row, 2, date_item)  # 第2列
    
    # 其他列的索引都+1（从第3列开始）
    ...
```

### **2. MarketOverviewWidget.refresh_data方法（第1797-1866行）**

#### **修改3：智能查找最新有效数据**
```python
# 优先级：有score > 有value_tr > 有value_raw
df_with_score = df[df['score'].notna()]

if not df_with_score.empty:
    # 有评分数据
    latest = df_with_score.iloc[-1]
else:
    # 没有评分，查找转换值
    df_with_tr = df[df['value_tr'].notna()]
    if not df_with_tr.empty:
        latest = df_with_tr.iloc[-1]
    else:
        # 没有转换值，查找原始值
        df_with_raw = df[df['value_raw'].notna()]
        if not df_with_raw.empty:
            latest = df_with_raw.iloc[-1]
        else:
            latest = None

if latest is not None:
    data_date = latest.name  # 记录数据日期
    indicator_data.append({
        'code': code,
        'name': ind.get('name', code),
        'data_date': data_date,  # 新增字段
        'value': latest.get('value_tr', latest.get('value_raw', None)),
        'z': latest.get('z', None),
        'score': latest.get('score', None)
    })
```

### **3. CompositeScoreChart.update_indicator_chart方法（第821-892行）**

#### **修改4：曲线图只移除NaN，保留0值**
```python
# 第856行
# 修改前
valid_scores = filtered_scores[filtered_scores > 0]

# 修改后
valid_scores = filtered_scores.dropna()  # 只移除NaN，保留0和其他有效值
```

---

## 🚀 **效果**

### **评分表现在会显示**：

| 指标代码 | 指标名称 | **数据日期** | 当前值 | Z分数 | 评分 | 权重(%) |
|---------|---------|-------------|--------|------|------|---------|
| IWM_SPY_REL20 | IWM/SPY 20日相对收益 | **2025-12-24** | 0.01 | 0.19 | 51.9 | 15% |
| VIX_LOG | VIX (log & winsor) | **2025-12-24** | 2.60 | 1.54 | 65.4 | 15% |
| HY_OAS | 高收益债利差 | **2025-12-24** | 3.45 | -0.52 | 44.8 | 20% |

**关键变化**：
- ✅ **新增"数据日期"列**：清楚看到每个指标的数据是哪天的
- ✅ **即使没有评分也显示值**：如果某指标有`value_tr`但没有`score`，也会显示值和日期
- ✅ **曲线图显示所有点**：不会因为`score=0`而跳过数据点

### **曲线图改进**：

- 之前：如果`score=0`，点不显示，导致曲线断裂
- 现在：只要`score`不是NaN，都会显示（包括0值）

---

## 📝 **测试步骤**

### **1. 关闭并重启GUI**

```bash
# 如果app.py还在运行，按Ctrl+C关闭
# 然后重新启动
python app.py
```

### **2. 查看评分表**

- 切换到"市场概览"标签页
- 选择"US"市场
- 查看评分表是否有"数据日期"列
- 检查每个指标的数据日期

### **3. 点击表格行查看曲线**

- 点击表格中的某一行（如IWM_SPY_REL20）
- 查看右侧曲线图
- 确认最新的评分点是否显示

### **4. 验证数据获取**

如果还没有12月26日的数据，请：

1. 删除近期数据（如果需要）：
```bash
python force_retest.py
```

2. 在GUI中点击"手动获取最新数据"

3. 点击"计算评分"

4. 刷新查看评分表

---

## 🔍 **检查点**

- [ ] 评分表有7列（包括"数据日期"）
- [ ] 每个指标显示其数据的实际日期
- [ ] 即使某些指标没有评分，但有值时也会显示
- [ ] 曲线图显示最新的评分点
- [ ] 不同指标可能有不同的数据日期（这是正常的）

---

## 💡 **为什么有些指标没有最新日期的数据？**

**正常情况**：
- 不同数据源的更新时间不同
- 例如：
  - `VIX`：股市交易日有数据
  - `HY_OAS`：Fred数据，工作日更新
  - `IWM_SPY_REL20`：依赖yfinance，股市交易日有数据

**如果12月26日是交易日但没有数据**：
- 需要确保GUI的手动获取能正确拉取最新数据
- 我们已经修改了`ui/main_window.py`的`MIN_MANUAL_FETCH_DAYS = 50`
- 重启GUI后应该能正常获取

---

**现在请重启GUI，查看评分表的效果！** 🎉

