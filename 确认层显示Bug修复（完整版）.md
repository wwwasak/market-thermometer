# 确认层表格显示Bug修复（完整版）

## 问题总结

用户报告：确认层状态表格中，**"Hard Veto: 绿灯"文字显示正确，但表格里的"当前灯色"列显示黄色**。

---

## 问题原因（2个Bug）

### Bug 1: 依赖空的lamp_history表
GUI试图从`lamp_history`表读取灯色，但这个表是空的，导致默认显示黄色。

### Bug 2: 调用了错误的Repository方法
修改为从score计算灯色后，调用了错误的方法：
- ❌ 调用：`self.repository.load_series_data(code, view=view)`  
  - 这个方法需要`series_id: int`参数，不是`code: str`
  - 传入code导致类型不匹配，返回空数据
- ✅ 应该调用：`self.repository.load_series_data_by_code(code, view=view)`
  - 这个方法接受`code: str`参数

---

## 修复内容

### 文件：`ui/market_overview.py`

#### 修改1：从score计算灯色（第1940-1974行）

**旧逻辑**：
```python
# 从lamp_history表获取最新灯色（表是空的）
lamp_hist = self.repository.load_lamp_history(
    market=market, view=view, source_code=code
)
if lamp_hist is not None and not lamp_hist.empty:
    latest_lamp = lamp_hist.iloc[-1]['lamp']
else:
    latest_lamp = '-'  # 默认黄色
```

**新逻辑**：
```python
# 直接从series_data获取最新score并计算灯色
series_data_df = self.repository.load_series_data_by_code(code, view=view)  # ✅ 正确方法

if series_data_df is not None and not series_data_df.empty and 'score' in series_data_df.columns:
    score_series = series_data_df['score'].dropna()
    if not score_series.empty:
        latest_score = score_series.iloc[-1]
        
        # 根据score计算灯色
        green_th = self.config.get(f'markets.{market}.green_threshold', 60)
        red_th = self.config.get(f'markets.{market}.red_threshold', 40)
        
        if latest_score >= green_th:
            latest_lamp = 'G'  # 绿灯
        elif latest_score <= red_th:
            latest_lamp = 'R'  # 红灯
        else:
            latest_lamp = 'Y'  # 黄灯
```

---

## 验证结果

### 数据验证
```
ETF_NETFLOW_5D:
  - score = 87.45 (远高于绿色阈值60)
  - 计算灯色 = G (绿灯) ✅
  - regimes表的lamp_hard = G (绿灯) ✅
  - 匹配成功！

CNY:
  - score = 66.20 (高于绿色阈值60)
  - 计算灯色 = G (绿灯) ✅
```

### GUI显示预期

| 位置 | 内容 | 预期显示 |
|------|------|---------|
| 汇总信息 | Hard Veto | ✅ 绿灯（文字） |
| 表格第1行 | ETF_NETFLOW_5D | ✅ 绿色背景 |
| 表格第2行 | CNY (配对) | ✅ 绿色背景 |

---

## 重要提示

### ⚠️ 必须完全重启GUI

由于Python的模块缓存机制，修改代码后必须：

1. **完全关闭所有GUI窗口**
2. **打开任务管理器**
3. **结束所有`python.exe`进程**（确保旧代码不再运行）
4. **重新运行**：`python app.py`

**不要只是点击关闭按钮！** Python进程可能还在后台运行旧代码。

---

## 技术细节

### Repository的两个方法

```python
# 方法1：按series_id加载（需要先查询id）
def load_series_data(
    self,
    series_id: int,  # ← 需要int
    view: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> pd.DataFrame

# 方法2：按code加载（内部会先查询id）✅ GUI应该用这个
def load_series_data_by_code(
    self,
    code: str,  # ← 接受str
    view: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> pd.DataFrame
```

### 灯色映射逻辑

```python
# 颜色设置（update_confirm_layer方法，第1237-1243行）
if lamp == 'G':
    lamp_item.setBackground(Qt.GlobalColor.green)  # 绿色
elif lamp == 'R':
    lamp_item.setBackground(Qt.GlobalColor.red)    # 红色
else:
    lamp_item.setBackground(Qt.GlobalColor.yellow) # 黄色（默认）
```

---

## 测试步骤

1. **完全关闭GUI和Python进程**
2. **重新启动**：`python app.py`
3. **切换到CN市场**
4. **观察确认层状态表格**：
   - ETF_NETFLOW_5D那一行应该是**绿色背景**
   - 与底部"Hard Veto: 绿灯"文字一致
   - CNY那一行也应该是**绿色背景**

---

## 相关文件

- **修改的文件**：`ui/market_overview.py` (第1940-1942行)
- **相关方法**：
  - `MarketOverviewWidget.refresh_data` (第1775-2005行)
  - `ConfirmLayerPanel.update_confirm_layer` (第1190-1274行)
- **数据源**：`storage/repository.py`
  - `load_series_data_by_code` (第305-316行)

---

## Bug修复总结

✅ **Bug 1**: 依赖空的lamp_history表 → 改为从score计算  
✅ **Bug 2**: 调用错误的Repository方法 → 改用load_series_data_by_code  
✅ **验证**: 测试脚本确认数据加载正确，灯色计算正确  
✅ **待验证**: 用户重启GUI后查看表格显示

**请完全重启GUI并验证！**

