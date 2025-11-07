# 阶段6增强方案总结

## 📌 增强目标

根据您的需求，在原有阶段6基础上进行了**全面增强**，确保：

1. ✅ **增量数据库设计完善**：后期只需手动获取最新数据添加
2. ✅ **所有数据完整持久化**：原始数据和所有派生数据都存储在数据库
3. ✅ **GUI与数据库解耦**：图表仅从数据库读取，不参与计算

---

## 📦 新增/修改的文档

### 1. `todolist.txt` - 阶段6任务详细化

**修改位置**：阶段6（行257-753）

**主要内容**：
- **6.1 数据库Schema完善**：7个表的完整定义
  - `series_meta`：新增增量更新字段（`last_raw_date`, `data_quality`）
  - `series_data`：完整数据链存储（raw → transformed → z → score → lamp）
  - `confirm_layer`：**新增表**，存储软硬确认详情
  - `regimes`：扩展字段（`market_score`, `persistence_counter`）
  - `indicator_weights`：**新增表**，存储不同风格的权重配置
  - `data_fetch_history`：改进日志表
  - 索引优化方案

- **6.2 Repository增量更新方法**：
  - `get_last_data_date()`: 获取最新数据日期
  - `upsert_series_data_batch()`: 批量高效插入
  - `save_indicator_full_pipeline()`: 保存完整数据链
  - `load_indicator_complete()`: 读取完整指标数据
  - `check_data_completeness()`: 数据完整性检查
  - `get_incremental_update_plan()`: 生成增量更新计划

- **6.3 数据流水线完整实现**：
  - `update_market_incremental()`: 增量更新主流程
  - `recompute_market_full()`: 参数重算流程
  - `generate_weekly_view()`: 周视图生成
  - `indicator_registry.py`: 指标配置注册表

- **6.4-6.6 详细测试**：
  - 6个完整测试场景（数据库初始化、增量更新、市场流水线、周视图、完整性检查、参数重算）
  - 每个测试都有PowerShell命令和预期输出
  - 关键注意事项（增量更新策略、数据依赖、性能优化）

### 2. `docs/database_design.md` - 数据库设计详解

**核心内容**：

1. **设计目标**明确：
   - 增量更新、完整持久化、GUI解耦、参数重算、数据溯源

2. **7个表的完整SQL定义**：
   - 每个字段都有详细注释
   - 索引策略说明
   - 数据流示例（如VIX的完整数据链）

3. **增量更新工作流**：
   - 首次运行 vs 增量更新的流程图
   - 数据获取 → 窗口计算 → 批量存储

4. **GUI查询接口设计**：
   - `load_market_overview()`: Overview图表数据
   - `load_indicator_complete()`: 单指标双Y轴图表数据
   - `load_confirm_layer_detail()`: 确认层详情

5. **数据完整性检查**机制

6. **性能优化建议**：
   - 批量插入
   - 索引策略
   - 查询优化
   - 数据分区（可选）

### 3. `docs/data_flow_incremental.md` - 增量数据流详解

**核心内容**：

1. **首次获取 vs 增量更新对比图**：
   - 首次：获取2年数据（500条）
   - 增量：仅获取1天新数据（1条）
   - 清晰展示每一步的操作

2. **完整市场更新流程**：
   - `update_market_incremental('US')`的7个详细步骤
   - 每步的SQL查询、数据流向、计算逻辑

3. **参数重算流程**：
   - 场景示例：修改regime阈值70/40 → 75/35
   - 6个步骤详解（保存参数 → 读取原始数据 → 重算派生数据 → 批量更新）
   - **关键优势**：不重新获取网络数据，纯计算，~2秒完成

4. **GUI查询示例**：
   - 用户打开"US Overview"标签页的后端查询流程
   - 用户点击"VIX_LOG"指标的双Y轴图表生成流程

5. **数据持久化保证**：
   - UPSERT语义示例（SQLite 3.24+）
   - 批量操作优化代码

6. **周视图生成详解**：
   - 从日数据重采样到Friday标签
   - 周窗口的Z分数重算

7. **数据完整性自检**：
   - 启动时自动检查机制

### 4. `core/indicator_registry_reference.py` - 指标配置参考

**核心内容**：

1. **CN市场6个主指标**完整配置：
   - `CN_MARGIN_SLOPE`: 两融余额斜率（slope_20_60_ewma）
   - `CNH_PCT20`: USD/CNH 20日%变动
   - `NORTH_TURNOVER_SHARE`: 北向成交额占比
   - `CSI1000_OVER_300_REL20`: 中证1000/沪深300相对收益
   - `PMI_NEWORDER_YOY_STD`: PMI新订单同比标准化
   - `CN_EPS_YIELD_MINUS_CGB10`: 股债收益差

2. **US市场6个主指标**完整配置：
   - `RRP_D20`: RRP 20日变动
   - `TGA_D20`: TGA 20日变动
   - `HY_OAS`: 高收益债利差
   - `VIX_LOG`: VIX对数值
   - `DFII10`: 10年期TIPS实际利率
   - `IWM_SPY_REL20`: IWM/SPY相对收益

3. **CN观察者指标**：
   - 硬否决：`ETF_NETFLOW_5D`
   - 软确认配对：CNH/CNY, TWEX/DXY

4. **US观察者指标**：
   - 硬否决：`HY_OAS_JUMP`, `VIX_EXTREME`
   - 软确认：`IWM_SPY_SOFT`, `HYG_IEF_SOFT`, 配对

5. **辅助函数**：
   - `get_indicator_config()`: 获取指标配置
   - `get_market_indicators()`: 按市场和角色筛选
   - `validate_indicator_config()`: 配置验证
   - `get_all_indicators_summary()`: 汇总统计

**每个指标包含的配置字段**：
```python
{
    'name': '中文名',
    'name_en': '英文名',
    'market': 'CN' | 'US',
    'role': 'main' | 'soft' | 'hard' | 'pair',
    'direction': 'up_good' | 'down_good',
    'transform': '转换类型',
    'transform_params': {...},
    'z_method': 'z' | 'madz',
    'z_window': 60 | 40 | 90,
    'direction_sign': 1 | -1,
    'source': 'fred' | 'yfinance' | 'csv',
    'source_symbol': '数据源标识',
    'weekly_agg': 'last' | 'mean' | 'sum',
    'dependencies': [...],
    'fetch_frequency': 'daily' | 'weekly' | 'monthly',
    'description': '详细说明',
    'calculation': '计算公式'
}
```

---

## 🎯 核心改进点

### 1. 增量更新机制

**问题**：每次都重新获取全部历史数据，浪费时间和流量

**解决方案**：
```python
# series_meta表新增字段
last_raw_date DATE  # 记录最新数据日期

# 增量更新逻辑
def update_indicator(code):
    last_date = repo.get_last_data_date(code, 'daily')
    if last_date:
        start_date = last_date + timedelta(days=1)  # 从最后日期+1开始
    else:
        start_date = today - timedelta(days=730)  # 首次获取2年
    
    # 仅获取新日期数据
    new_data = fetcher.fetch(symbol, start_date, today)
    
    # 从数据库加载历史数据用于窗口计算
    historical = repo.load_series_data(code, last_date - 60, last_date, 'daily')
    
    # 合并计算
    full_data = pd.concat([historical, new_data])
    transformed = transform(full_data)
    z = rolling_z(transformed[-len(new_data):])  # 仅计算新日期的Z
    
    # 批量upsert新数据
    repo.upsert_series_data_batch(code, new_data_with_derived, 'daily')
    
    # 更新元数据
    repo.update_series_meta(code, last_raw_date=today)
```

**优势**：
- 首次：获取730天数据，耗时~30秒
- 增量：获取1天数据，耗时~2秒（减少93%时间）

### 2. 完整数据链存储

**问题**：原设计仅存储部分派生数据，GUI需要重新计算

**解决方案**：
```python
# series_data表存储完整数据链
CREATE TABLE series_data (
    ...
    value_raw REAL,          # 原始值（API获取）
    value_transformed REAL,  # 转换值（delta20/pct20/slope等）
    z_score REAL,            # Z分数或MADZ
    score_0_100 REAL,        # 0-100分数
    lamp_color TEXT,         # 单指标灯色
    ...
)

# 一次存储，多次读取
repo.save_indicator_full_pipeline(
    'VIX_LOG',
    date_range,
    raw_series,
    transformed_series,
    z_series,
    score_series,
    lamp_series,
    'daily'
)

# GUI读取时无需任何计算
df = repo.load_indicator_complete('VIX_LOG', start, end, 'daily')
chart.plot_dual_axis(df['date'], df['value_raw'], df['score_0_100'])
```

**优势**：
- GUI响应时间<100ms（纯数据库查询）
- 支持任意历史时间段回溯
- 参数变化追溯（通过`params_hash`字段）

### 3. 确认层详细存储

**问题**：原设计仅存储final_lamp，无法查看软硬确认的组成

**解决方案**：
```python
# 新增confirm_layer表
CREATE TABLE confirm_layer (
    ...
    # 软确认组件（每个都存储）
    soft_iwm_spy_lamp TEXT,
    soft_hyg_ief_lamp TEXT,
    soft_twex_dxy_lamp TEXT,
    soft_cnh_cny_lamp TEXT,
    soft_weighted_score REAL,
    soft_final_lamp TEXT,
    
    # 硬否决组件（每个都存储）
    hard_etf_netflow_lamp TEXT,
    hard_hy_oas_jump_lamp TEXT,
    hard_vix_extreme_lamp TEXT,
    hard_veto_lamp TEXT,
    
    # 最终结果
    final_lamp TEXT,
    ...
)
```

**优势**：
- GUI可以显示确认层详情面板
- 用户可以看到哪个硬否决触发了红灯
- 软确认加权分数可视化

### 4. 参数重算能力

**问题**：修改参数后需要重新获取所有数据

**解决方案**：
```python
def recompute_market_full(market, start, end, view, new_params):
    # 1. 从数据库读取原始数据（不调用API）
    for indicator in get_market_indicators(market, 'main'):
        raw_data = repo.load_series_data(indicator, start, end, view,
                                          columns=['date', 'value_raw'])
        
        # 2. 用新参数重新计算派生数据
        transformed = transform(raw_data['value_raw'], **new_params['transforms'])
        z = rolling_z(transformed, window=new_params['z_windows']['base'])
        score = score_from_z(z)
        lamp = lamp_from_score(score, **new_params['lamp_thresholds'])
        
        # 3. 更新数据库（仅派生字段）
        repo.update_derived_data(indicator, date_range, 
                                  transformed, z, score, lamp,
                                  params_hash=new_params_hash)
    
    # 4. 重算market层（regime, confirm_layer）
    # ...
```

**优势**：
- 重算30天数据耗时~2秒（vs 重新获取30秒）
- 支持参数调优实验
- 原始数据不变，可随时回滚

### 5. 周视图生成

**问题**：周数据如何获取？是否需要单独API调用？

**解决方案**：
```python
# 从日数据重采样生成周数据（不需要额外API调用）
def generate_weekly_view(market, start, end):
    for indicator in get_market_indicators(market):
        # 读取日数据
        daily_df = repo.load_indicator_complete(indicator, start, end, 'daily')
        
        # 重采样到Friday
        weekly_df = daily_df.set_index('date').resample('W-FRI').last()
        
        # 重新计算周窗口的Z和Score
        weekly_df['z_score'] = rolling_madz(weekly_df['value_transformed'], 
                                             window=60)  # 60周≈1.2年
        weekly_df['score_0_100'] = score_from_z(weekly_df['z_score'])
        weekly_df['lamp_color'] = lamp_from_score(weekly_df['score_0_100'])
        
        # 保存为view='weekly'
        repo.upsert_series_data_batch(indicator, weekly_df, 'weekly')
```

**优势**：
- 无需额外数据获取
- Friday标签保证一致性
- 独立的周窗口计算更准确

---

## 📊 数据库表关系图

```
series_meta (指标元数据)
    ├── last_raw_date: 最新数据日期
    └── data_quality: 数据质量状态

series_data (时间序列数据) ──┬── view='daily'
    ├── value_raw             └── view='weekly'
    ├── value_transformed
    ├── z_score
    ├── score_0_100
    └── lamp_color

confirm_layer (确认层详情) ──┬── soft组件 (IWM/SPY, HYG/IEF, 配对)
                             ├── hard组件 (ETF流入, HY OAS跳跃, VIX极值)
                             └── final_lamp (硬否决优先)

regimes (市场状态)
    ├── market_score (加权综合分数)
    ├── regime (Attack/Balanced/Defense)
    ├── lamp_final (最终灯色)
    └── persistence_counter (切换确认计数)

indicator_weights (权重配置)
    └── profile (Attack/Balanced/Defense)

params (参数历史)
    └── params_hash (用于追溯)

data_fetch_history (获取日志)
    └── records_updated (增量记录数)
```

---

## 🚀 开发阶段6的行动步骤

### Step 1: 创建完整的数据库Schema

```powershell
# 创建 storage/models.py
# 定义所有7个表的SQLAlchemy模型
# 添加索引和约束
```

参考：`docs/database_design.md` 第2节

### Step 2: 实现Repository方法

```powershell
# 创建 storage/repository.py
# 实现所有查询和upsert方法
```

关键方法（todolist.txt 第350-385行）：
- `get_last_data_date()`
- `upsert_series_data_batch()`
- `save_indicator_full_pipeline()`
- `load_indicator_complete()`
- `check_data_completeness()`
- `get_incremental_update_plan()`

### Step 3: 实现指标配置注册表

```powershell
# 创建 core/indicator_registry.py
# 从 core/indicator_registry_reference.py 复制并调整
```

### Step 4: 实现Scheduler增量更新

```powershell
# 创建 core/scheduler.py
# 实现 update_market_incremental(), recompute_market_full(), generate_weekly_view()
```

参考：`docs/data_flow_incremental.md`

### Step 5: 运行测试

按照todolist.txt第467-685行的6个测试场景逐一验证：

1. 数据库初始化和元数据填充
2. 增量更新单个指标
3. 市场完整流水线
4. 周视图生成
5. 数据完整性检查
6. 参数重算

---

## ✅ 验收标准（阶段6完成后）

### 功能验收

- [ ] **增量更新**：第二天更新仅获取1天新数据，耗时<5秒
- [ ] **完整数据链**：数据库包含raw/transformed/z/score/lamp所有字段
- [ ] **确认层详情**：`confirm_layer`表包含所有软硬组件
- [ ] **参数重算**：修改参数后重算30天数据耗时<5秒
- [ ] **周视图**：weekly数据仅包含Friday，数量约为daily的1/5
- [ ] **数据完整性**：能检测缺失数据并生成更新计划

### 性能验收

- [ ] **首次获取**：US市场6个指标2年数据，耗时<60秒
- [ ] **增量更新**：US市场6个指标1天数据，耗时<10秒
- [ ] **GUI查询**：加载Overview图表，耗时<100ms
- [ ] **参数重算**：重算60天数据，耗时<5秒

### 数据验收

- [ ] **series_meta**：CN 10个指标 + US 10个指标 = 20条记录
- [ ] **series_data**：每个指标2年数据约500条 × 20指标 = 10000条
- [ ] **regimes**：每个市场每天1条 × 2市场 × 500天 = 1000条
- [ ] **confirm_layer**：同regimes
- [ ] **indicator_weights**：CN 3个profile × 6个指标 + US 3 × 6 = 36条

---

## 💡 关键技术要点

### 1. SQLite UPSERT语法（3.24+）

```sql
INSERT INTO series_data (series_id, date, view, value_raw, ...)
VALUES (?, ?, ?, ?, ...)
ON CONFLICT(series_id, date, view)  -- unique constraint
DO UPDATE SET
    value_raw = excluded.value_raw,
    value_transformed = excluded.value_transformed,
    updated_at = CURRENT_TIMESTAMP;
```

### 2. Pandas批量操作

```python
# 比逐条INSERT快100倍
df.to_sql('series_data', con=engine, if_exists='append', 
          index=False, method='multi', chunksize=1000)
```

### 3. 参数哈希追踪

```python
import hashlib
import json

params_hash = hashlib.md5(
    json.dumps(params, sort_keys=True).encode()
).hexdigest()

# 每条记录存储params_hash
# 参数变化时可以检测出哪些数据需要重算
```

### 4. 业务日历（交易日）

```python
import pandas as pd

# 生成交易日序列
trading_days = pd.bdate_range(start='2022-01-01', end='2024-11-08')

# 检查数据完整性
missing_days = set(trading_days) - set(actual_data_dates)
```

---

## 📚 参考文档索引

| 文档 | 内容 | 用途 |
|------|------|------|
| `todolist.txt` 阶段6 | 详细任务清单和测试 | 开发指南 |
| `docs/database_design.md` | 数据库Schema详解 | 实现models.py |
| `docs/data_flow_incremental.md` | 增量更新流程 | 实现scheduler.py |
| `core/indicator_registry_reference.py` | 指标配置参考 | 实现indicator_registry.py |

---

## 🎉 总结

通过本次阶段6的完善，您的项目将获得：

1. **专业级的增量数据管理**：与量化平台媲美的数据获取机制
2. **完整的数据溯源**：所有原始和派生数据都可追溯
3. **快速的参数实验能力**：调参不需要重新获取数据
4. **清晰的GUI数据接口**：前后端完全解耦
5. **可靠的数据完整性检查**：自动检测缺失数据

这为后续阶段7-9的GUI开发奠定了坚实的基础！🚀

---

**下一步行动**：按照todolist.txt阶段6的任务清单，逐步实现各个模块和测试验证。

