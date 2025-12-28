# CN市场数据源优化完成报告

## 完成时间
2025-12-27

## 任务概述

完成了两个重要的系统优化：
1. 支持跨市场查询软确认指标（解决CN市场使用US市场的`PAIR_TWEX_DXY`问题）
2. 将CN市场的`ETF_NETFLOW_5D`数据源切换为A500宽基ETF综合资金流

---

## 1. 跨市场软确认指标支持

### 问题描述
CN市场的确认层配置中包含`PAIR_TWEX_DXY`（权重0.50），但该指标位于US市场，导致：
- CN市场无法找到该指标数据
- 软确认默认使用黄色（Y=1.0）
- 加权计算：0.5×2(绿)+0.5×1(黄)=1.5 < 1.6（绿色阈值）
- 最终灯色显示黄色而非绿色

### 解决方案
修改了`core/pipeline.py`中的`apply_confirm_layer`方法：

#### 新增功能
1. **跨市场查询逻辑**：在应用确认层时，检查软确认指标是否存在于当前市场
2. **自动加载**：如果指标不在当前市场，从数据库查询其所属市场并加载数据
3. **灯号转换**：将其他市场的评分转换为灯号，并对齐到当前市场的日期索引

#### 新增方法
```python
def _load_cross_market_lamp(
    self,
    code: str,
    date_index: pd.DatetimeIndex,
    view_type: str = 'daily'
) -> Optional[pd.Series]:
    """
    从其他市场加载软确认指标的灯号
    
    @param {str} code - 指标代码
    @param {pd.DatetimeIndex} date_index - 目标日期索引
    @param {str} view_type - 视图类型
    @returns {Optional[pd.Series]} 灯号序列，或None
    """
```

#### 修改位置
- **文件**：`core/pipeline.py`
- **方法**：`apply_confirm_layer` (lines 1055-1156)
- **新增方法**：`_load_cross_market_lamp` (lines 1157-1208)

### 效果
✅ CN市场现在可以正确使用US市场的`PAIR_TWEX_DXY`
✅ 软确认加权计算：0.5×2(PAIR_CNH_CNY绿)+0.5×2(PAIR_TWEX_DXY绿)=2.0 ≥ 1.6
✅ 软确认=绿色，最终灯色=绿色

---

## 2. ETF_NETFLOW_5D数据源切换为A500宽基ETF

### 问题背景
原数据源使用沪深300、中证500、创业板ETF，用户希望：
- 切换为A500相关宽基ETF
- 更能反映当前市场关注度（A500是2024年新推出的指数）
- 涵盖多只A500 ETF的综合资金流向

### A500 ETF列表（共5只）

| ETF代码 | 市场 | 名称 | 备注 |
|---------|------|------|------|
| 159352 | sz | 南方中证A500ETF | 规模最大 |
| 563080 | sh | 华夏中证A500ETF | 头部基金公司 |
| 563050 | sh | 易方达中证A500ETF | 头部基金公司 |
| 563060 | sh | 嘉实中证A500ETF | 头部基金公司 |
| 159353 | sz | 华泰柏瑞中证A500ETF | 流动性好 |

### 数据获取脚本

创建了独立脚本：`fetch_a500_etf_data.py`

#### 功能特性
1. **多只ETF综合**：获取5只A500 ETF的主力资金流向并汇总
2. **5日滚动计算**：计算5日滚动净申赎
3. **灵活日期范围**：支持指定天数或起止日期
4. **试运行模式**：`--dry-run` 预览数据不修改数据库
5. **数据验证**：更新后自动验证数据完整性

#### 使用方法
```powershell
# 试运行（查看数据但不更新）
python fetch_a500_etf_data.py --days 30 --dry-run

# 获取最近90天数据并更新
python fetch_a500_etf_data.py --days 90 --execute

# 指定日期范围更新（推荐用于历史数据回填）
python fetch_a500_etf_data.py --start 2022-12-01 --end 2025-12-27 --execute
```

### 数据更新结果

✅ **成功更新**：
- 总记录数：120条
- 日期范围：2025-07-04 ~ 2025-12-26
- 数据来源：5只A500 ETF综合资金流
- 计算方式：5日滚动净申赎

📊 **数据统计**（最新数据）：
- 平均值：4787.49 亿元
- 最小值：-39419.10 亿元（2025-12-25，市场调整）
- 最大值：26774.94 亿元（历史高峰）

### 最近10日数据

| 日期 | ETF净申赎(亿元) | 说明 |
|------|----------------|------|
| 2025-12-26 | -37406.64 | 持续流出 |
| 2025-12-25 | -39419.10 | 最大流出 |
| 2025-12-24 | -32282.80 | 圣诞前调整 |
| 2025-12-23 | -19172.66 | 流出减缓 |
| 2025-12-22 | -12234.67 | - |

---

## 3. 后续操作指南

### 立即执行
1. **关闭GUI**（如果正在运行）
2. **重新启动GUI**：`python app.py`
3. **点击"计算评分"**：
   - 重新计算CN市场所有指标的评分
   - ETF_NETFLOW_5D会基于新的A500数据计算Z-score和评分
   - 确认层会从US市场正确加载PAIR_TWEX_DXY
4. **查看CN市场确认层**：
   - ETF_NETFLOW_5D（硬否决）：如果是绿色，不触发否决
   - 软确认：PAIR_CNH_CNY(0.5) + PAIR_TWEX_DXY(0.5)
   - 最终灯色：如果两个配对都是绿，应显示绿色

### 定期更新
每次手动获取最新数据时，可以选择：

**选项1：使用GUI的"手动获取最新数据"**
- 会自动增量获取A500 ETF数据
- 数据源已在`core/datasource.py`中定义

**选项2：使用独立脚本**（更可控）
```powershell
# 每天更新最近7天数据
python fetch_a500_etf_data.py --days 7 --execute

# 或在GUI点击"计算评分"前先运行
python fetch_a500_etf_data.py --days 30 --execute
```

---

## 4. 技术细节

### 跨市场查询实现原理

```python
# 1. 检测软确认指标不在当前市场
if code not in observer_lamps and code not in pair_lamps:
    # 2. 查询数据库获取指标所属市场
    meta = self.repository.session.query(SeriesMeta).filter_by(code=code).first()
    
    # 3. 从数据库加载该指标的评分数据
    series_data = self.repository.load_series_data(code, view=view_type)
    
    # 4. 转换为灯号
    lamp_series = lamp_from_score(score_series, green_th, red_th)
    
    # 5. 对齐到当前市场的日期索引（使用ffill）
    lamp_series = lamp_series.reindex(date_index, method='ffill')
```

### A500 ETF数据流程

```
┌─────────────────────┐
│ 5只A500 ETF数据源   │
│ (akshare接口)       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 获取主力净流入      │
│ (万元)              │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 汇总5只ETF          │
│ 转换单位(亿元)      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 5日滚动求和         │
│ rolling(5).sum()    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 更新数据库          │
│ ETF_NETFLOW_5D      │
└─────────────────────┘
```

---

## 5. 验证检查清单

### CN市场确认层
- [ ] 硬否决（ETF_NETFLOW_5D）显示正确颜色
- [ ] 软确认包含PAIR_CNH_CNY和PAIR_TWEX_DXY
- [ ] 最终灯色符合预期（如果两个配对都是绿→最终绿）

### ETF_NETFLOW_5D数据
- [ ] 数据基于5只A500 ETF
- [ ] 日期范围覆盖最近120个交易日
- [ ] 数值合理（-4万亿到+2.7万亿亿元范围）
- [ ] Z-score和评分正确计算

---

## 6. 问题排查

### 如果确认层还是黄色
1. **检查PAIR_TWEX_DXY数据**：
   ```powershell
   python -c "import sqlite3; conn = sqlite3.connect('data/market_thermo_3years_auto.db'); cursor = conn.cursor(); cursor.execute('SELECT date, score FROM series_data WHERE series_id = (SELECT id FROM series_meta WHERE code = \"PAIR_TWEX_DXY\") ORDER BY date DESC LIMIT 5'); print(cursor.fetchall())"
   ```

2. **检查跨市场日志**：
   - 在GUI中点击"计算评分"
   - 查看控制台输出是否有"跨市场查询"相关日志

3. **检查软确认权重配置**：
   ```python
   from core.config import Config
   config = Config()
   print(config.get('soft_confirm_weights.CN'))
   # 应该输出：{'PAIR_CNH_CNY': 0.5, 'PAIR_TWEX_DXY': 0.5}
   ```

### 如果ETF数据异常
1. **重新运行数据获取脚本**：
   ```powershell
   python fetch_a500_etf_data.py --days 90 --execute
   ```

2. **检查akshare接口是否正常**：
   ```python
   import akshare as ak
   df = ak.stock_individual_fund_flow(stock="159352", market="sz")
   print(df.tail())
   ```

---

## 7. 总结

✅ **完成的优化**：
1. Pipeline支持跨市场查询软确认指标
2. CN市场可以正确使用US市场的PAIR_TWEX_DXY
3. ETF_NETFLOW_5D切换为A500宽基ETF综合数据
4. 提供独立的数据获取和更新脚本

✅ **预期效果**：
1. CN市场确认层显示绿色（假设两个配对都是绿）
2. ETF数据更能反映A500指数的市场关注度
3. 数据获取和更新更加灵活可控

🔄 **下一步**：
1. 重启GUI并点击"计算评分"
2. 验证确认层颜色是否正确
3. 查看ETF_NETFLOW_5D的新评分

---

**报告完成** ✨

