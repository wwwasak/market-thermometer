# ETF_NETFLOW_5D 数据源统一说明

## 当前状态分析

### ✅ 好消息：逻辑已经统一！

经过检查，**获取三年数据的脚本（fetch_3years_data_auto.py）**和**GUI手动获取**已经使用相同的数据获取逻辑：

```
fetch_3years_data_auto.py
  → AutoDataFetcher.fetch_indicator_with_fallback()
    → DataSourceManager.fetch_by_config()
      → AKShareFetcher.fetch("etf_flow")
        → AKShareFetcher._fetch_etf_flow()  ← 统一逻辑
          ✓ 使用 fund_etf_hist_em API
          ✓ 成交额 × sign(涨跌幅)
          ✓ 加权汇总5只ETF
          ✓ 内置5日滚动和

GUI手动获取
  → MarketPipeline.fetch_and_save_raw_data()
    → MarketPipeline.fetch_all_data()
      → DataSourceManager.fetch_by_config()
        → AKShareFetcher.fetch("etf_flow")
          → AKShareFetcher._fetch_etf_flow()  ← 相同逻辑
```

---

## 数据获取逻辑详解

### 统一实现：core/datasource.py - AKShareFetcher._fetch_etf_flow()

```python
def _fetch_etf_flow(self, start_date: str, end_date: str) -> pd.Series:
    """
    获取A500 ETF的5日净申赎近似值（基于成交额）
    """
    # 1. ETF列表（带权重）
    a500_etf_list = [
        {"code": "159352", "name": "南方中证A500ETF", "weight": 0.50},
        {"code": "563080", "name": "华夏中证A500ETF", "weight": 0.15},
        {"code": "563050", "name": "易方达中证A500ETF", "weight": 0.15},
        {"code": "563060", "name": "嘉实中证A500ETF", "weight": 0.10},
        {"code": "159353", "name": "华泰柏瑞中证A500ETF", "weight": 0.10}
    ]
    
    # 2. 获取各ETF历史行情
    for etf_meta in a500_etf_list:
        df = self.ak.fund_etf_hist_em(symbol=code, period="daily", adjust="")
        
        # 3. 计算带方向的成交额
        turnover = pd.to_numeric(df['成交额'], errors='coerce')
        pct_change = pd.to_numeric(df['涨跌幅'], errors='coerce') / 100.0
        
        directional_flow = turnover * pct_change.apply(
            lambda x: 1 if x > 0 else -1 if x < 0 else 0
        )
        
        # 4. 转换为亿元并应用权重
        directional_flow = (directional_flow / 1e8) * weight
        
        # 5. 汇总
        combined_flow = combined_flow.add(directional_flow, fill_value=0.0)
    
    # 6. 计算5日滚动和
    combined_flow = combined_flow.sort_index()
    rolling_flow = combined_flow.rolling(window=5, min_periods=1).sum()
    
    return rolling_flow
```

---

## 配置确认

### user_config.json

```json
{
  "code": "ETF_NETFLOW_5D",
  "name": "宽基ETF 5日净申赎",
  "role": "hard",
  "direction": "up_good",
  "transform": "raw",        ← 关键：raw表示不进行额外转换
  "source": "akshare",       ← 数据源
  "symbol": "etf_flow"       ← 触发_fetch_etf_flow()
}
```

**为什么transform是"raw"？**
- 因为5日滚动和已经在`_fetch_etf_flow()`中计算完成
- `transform: "raw"`表示直接使用返回的数据，不再进行额外转换

---

## 历史问题说明

### 废弃的独立脚本

#### ❌ fetch_a500_etf_data.py（已废弃）
- 使用 `stock_individual_fund_flow()` - 错误的API
- 获取"主力净流入"数据 - 不准确
- 问题：全是负值，数量级错误（几万亿）

#### ⚠️ fetch_a500_etf_turnover.py（已过时）
- 逻辑与datasource.py一致
- 但作为独立脚本存在是多余的
- 建议：仅在紧急情况下手动补数据时使用

---

## 推荐的数据获取流程

### 方法1：使用三年数据脚本（推荐）

```powershell
# 获取完整三年历史数据（包括ETF_NETFLOW_5D）
python fetch_3years_data_auto.py

# 然后在GUI中计算评分
python app.py
# 点击"计算评分"按钮
```

**优点**：
- ✅ 自动获取所有指标
- ✅ 包含ETF_NETFLOW_5D
- ✅ 逻辑统一，无需手动运行独立脚本

### 方法2：使用GUI手动获取（增量更新）

```powershell
python app.py
# 1. 点击"手动获取最新数据"
# 2. 等待获取完成
# 3. 点击"计算评分"
```

**优点**：
- ✅ 图形界面，操作简单
- ✅ 增量更新，只获取缺失的日期
- ✅ 实时反馈，进度可见

---

## 验证数据一致性

### 检查脚本

创建 `verify_etf_consistency.py`：

```python
"""验证ETF_NETFLOW_5D数据一致性"""
import sqlite3
import pandas as pd

DB_PATH = "data/market_thermo_3years_auto.db"
conn = sqlite3.connect(DB_PATH)

# 获取ETF_NETFLOW_5D数据
df = pd.read_sql("""
    SELECT d.date, d.value_raw, d.value_tr
    FROM series_data d
    JOIN series_meta m ON d.series_id = m.id
    WHERE m.code = 'ETF_NETFLOW_5D'
    AND d.date >= date('now', '-30 days')
    ORDER BY d.date DESC
""", conn)

print("最近30天的ETF_NETFLOW_5D数据:")
print(df.to_string())

# 检查数据特征
print(f"\n数据统计:")
print(f"  记录数: {len(df)}")
print(f"  均值: {df['value_raw'].mean():.2f} 亿元")
print(f"  标准差: {df['value_raw'].std():.2f} 亿元")
print(f"  最小值: {df['value_raw'].min():.2f} 亿元")
print(f"  最大值: {df['value_raw'].max():.2f} 亿元")

conn.close()
```

### 预期结果

```
✓ 数值范围：-100 ~ 300 亿元（合理）
✓ 有正有负：反映市场正常波动
✓ 平均值接近0或小幅正值：符合长期趋势
```

---

## 常见问题

### Q1: 为什么有两个获取ETF数据的脚本？

**A**: 历史遗留问题。

- `fetch_a500_etf_data.py`: 旧逻辑，已废弃
- `fetch_a500_etf_turnover.py`: 独立脚本，功能与datasource.py重复
- **推荐**: 统一使用 `fetch_3years_data_auto.py` 或 GUI手动获取

### Q2: 需要手动运行fetch_a500_etf_turnover.py吗？

**A**: 不需要。

- `fetch_3years_data_auto.py` 会自动调用 `datasource.py` 获取数据
- GUI手动获取也会自动调用相同逻辑
- 独立脚本仅在紧急情况下使用

### Q3: 如何确认数据已对齐？

**A**: 检查数据库。

```python
# 查看最近的数据
python verify_etf_consistency.py

# 如果数值范围合理（几十到几百亿），说明已使用新逻辑
# 如果数值异常（几万亿），说明还有旧数据残留
```

---

## 清理旧数据（如果需要）

如果数据库中仍有旧逻辑的数据，清理步骤：

```powershell
# 1. 备份数据库
cp data/market_thermo_3years_auto.db data/market_thermo_backup.db

# 2. 删除旧的ETF数据
python -c "
import sqlite3
conn = sqlite3.connect('data/market_thermo_3years_auto.db')
cursor = conn.cursor()
cursor.execute('''
    DELETE FROM series_data 
    WHERE series_id = (
        SELECT id FROM series_meta 
        WHERE code = 'ETF_NETFLOW_5D'
    )
''')
conn.commit()
conn.close()
print('已删除旧数据')
"

# 3. 重新获取三年数据
python fetch_3years_data_auto.py

# 4. 在GUI中计算评分
python app.py
```

---

## 总结

### ✅ 当前状态

- **fetch_3years_data_auto.py**: 使用 `datasource.py` 统一逻辑 ✓
- **GUI手动获取**: 使用 `datasource.py` 统一逻辑 ✓
- **ETF_NETFLOW_5D配置**: 正确设置 `symbol: "etf_flow"` ✓

### ✅ 数据获取流程

```
用户操作
  ↓
fetch_3years_data_auto.py 或 GUI手动获取
  ↓
DataSourceManager.fetch_by_config()
  ↓
AKShareFetcher._fetch_etf_flow()
  ↓
fund_etf_hist_em API + 成交额×sign(涨跌幅) + 加权 + 5日滚动
  ↓
数据库（series_data表）
```

### ✅ 结论

**三年数据脚本和GUI手动获取的ETF_NETFLOW_5D逻辑已经完全对齐！**

- 使用相同的API：`fund_etf_hist_em`
- 使用相同的计算逻辑：成交额 × sign(涨跌幅)
- 使用相同的ETF列表和权重
- 使用相同的5日滚动和计算

无需额外修改！✨
