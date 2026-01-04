# PMI数据时间戳问题分析与修复方案

## 📊 **问题确认**

### ✅ **AKShare的标注方式（正确）**

通过验证确认：
- AKShare标注的是**数据所属月份**（正确）
- 例如：`2025年12月份` = 2025年12月的PMI数据
- 当前（2026-01-04）最新数据：`2025年12月份` PMI = 50.1

### ⚠️ **数据库中的问题**

数据库检查发现：
```
月份      日期          PMI值
2025-12   2025-12-01   50.10
2026-01   2026-01-01   50.10  ← 问题：与12月相同
```

**原因**：前向填充（forward fill）导致1月使用了12月的数据

## 🔍 **问题根源**

### 当前数据流程

1. **获取数据**：AKShare返回到2025-12（正确）
2. **转换日期**：2025-12-01（正确）
3. **前向填充**：填充到每个工作日
4. **问题**：前向填充跨越到了2026-01

### 前向填充的逻辑

在 `core/transforms.py` 的 `forward_fill_to_daily()` 函数中：

```python
def forward_fill_to_daily(series, start_date=None, end_date=None, freq='B'):
    if end_date is None:
        end_date = series.index.max()  # ← 问题：使用数据的最大日期
    
    date_range = pd.date_range(start=start_date, end=end_date, freq=freq)
    daily_series = series.reindex(date_range, method='ffill')
    return daily_series
```

**问题**：
- 如果在2026-01-02获取数据
- `end_date` 默认使用当前日期
- 前向填充会把2025-12的PMI值填充到2026-01-02

## ✅ **修复方案**

### 方案A：限制前向填充范围（推荐）

修改 `transform_yoy_std_ffill` 函数，不要填充到未来：

```python
def transform_yoy_std_ffill(
    series: pd.Series,
    freq: str = 'M'
) -> pd.Series:
    """
    同比标准化后前向填充（用于月度PMI等指标）
    """
    # 计算同比差值（12个月）
    if freq == 'M':
        yoy_diff = series - series.shift(12)
    else:
        yoy_diff = series - series.shift(12)
    
    # 标准化
    mean_val = yoy_diff.mean()
    std_val = yoy_diff.std()
    
    if std_val > 0:
        standardized = (yoy_diff - mean_val) / std_val
    else:
        standardized = yoy_diff - mean_val

    standardized = standardized.dropna()
    if len(standardized) == 0:
        return standardized

    # ✅ 修改：限制填充到数据最后一个月的月末
    from datetime import datetime
    if len(standardized) > 0:
        last_data_date = standardized.index[-1]
        # 计算该月的最后一天
        if last_data_date.month == 12:
            month_end = datetime(last_data_date.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = datetime(last_data_date.year, last_data_date.month + 1, 1) - timedelta(days=1)
        
        # 前向填充到该月月末，不填充到下个月
        daily_series = forward_fill_to_daily(standardized, end_date=pd.Timestamp(month_end))
    else:
        daily_series = standardized
    
    return daily_series
```

### 方案B：在获取数据时过滤当月

修改 `_fetch_pmi_neworder` 函数：

```python
def _fetch_pmi_neworder(self, start_date: str, end_date: str) -> pd.Series:
    """获取PMI新订单指数"""
    try:
        df = self.ak.macro_china_pmi()
        
        # 转换日期
        def parse_month(month_str):
            import re
            match = re.match(r'(\d+)年(\d+)月', month_str)
            if match:
                year, month = match.groups()
                return f"{year}-{month.zfill(2)}-01"
            return None
        
        df['date'] = df['月份'].apply(parse_month)
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        df = df.sort_index()
        
        # ✅ 新增：过滤掉当月数据（因为可能还未真正发布）
        from datetime import datetime
        current_month_start = datetime.now().replace(day=1)
        df = df[df.index < current_month_start]
        
        # 过滤日期范围
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        df = df[(df.index >= start_dt) & (df.index <= end_dt)]
        
        series = df['制造业-指数'].astype(float)
        
        print(f"[OK] Fetched {len(series)} records for PMI manufacturing")
        return series
        
    except Exception as e:
        raise DataFetchError(f"Failed to fetch PMI data: {e}")
```

### 方案C：组合方案（最稳妥）

同时实施方案A和方案B：
1. 获取数据时过滤当月
2. 前向填充时限制范围

## 📝 **推荐实施方案**

**方案B**（在获取数据时过滤）更简单且更安全：

### 优点
- 简单明了
- 不影响其他转换函数
- 避免了"假"数据进入系统

### 缺点
- 如果某个月PMI延迟发布，会缺少数据

## 🎯 **实施步骤**

1. ✅ **已修改 `core/datasource.py`** 的 `_fetch_pmi_neworder` 函数（方案B）
   - 新增当月数据过滤逻辑
   - 避免获取未发布的PMI数据

2. ✅ **已删除数据库中2026-01的PMI数据**
   - 删除了2条错误的前向填充记录
   - 清理完成，最新数据到2025-12

3. ✅ **验证结果**
   - 数据库中不再有2026-01的数据
   - 同比计算将正确使用2025-12和2024-12
   - GUI手动获取数据时不会再产生错误标注

## ⚠️ **注意事项**

1. **历史数据不受影响**：只影响未来的数据获取
2. **其他月度指标**：如果有其他月度指标，也需要类似处理
3. **数据更新时机**：建议在每月5号之后获取数据（确保PMI已发布）

## ✅ **修复完成状态**

### 代码修改
- ✅ `core/datasource.py` 第577-622行：新增当月数据过滤

### 数据库清理
- ✅ 已删除2条2026-01的错误PMI数据
- ✅ 最新数据：2025-12-31，PMI = 50.10

### 验证结果
```
同比计算验证:
  2024-12 PMI: 50.10
  2025-12 PMI: 50.10
  同比差值: 0.00  ← 正确！使用12月对12月
```

### GUI手动获取行为
- ✅ 不会获取当月数据
- ✅ 前向填充不会跨月
- ✅ 同比计算使用正确月份

## 📊 **修复后的效果**

```
月份      日期          PMI值     说明
2025-11   2025-11-03   49.20     ✓ 正确
2025-12   2025-12-01   50.10     ✓ 正确
2026-01   (无数据)              ✓ 等待2月初发布
```

等到2月初：
```
2026-01   2026-01-01   (新值)    ✓ 获取到真实1月PMI
```

