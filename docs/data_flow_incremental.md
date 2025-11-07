# 增量数据流详细说明

## 🔄 增量更新核心流程

### 流程图：首次获取 vs 增量更新

```
首次获取（空数据库）
┌─────────────────────────────────────────────────────────────────┐
│ 1. 检查 series_meta.last_raw_date                               │
│    结果: NULL （无历史数据）                                      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. 确定获取范围                                                  │
│    start_date = today - 730天（2年）                            │
│    end_date = today                                              │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. 调用数据源API                                                 │
│    FRED: fetch('RRPONTSYD', start, end) → 500条记录             │
│    yfinance: fetch('^VIX', start, end) → 500条记录               │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. 计算完整数据链（所有500条）                                   │
│    raw[0..499] → transformed[0..499] → z[0..499] → score[0..499]│
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. 批量插入 series_data                                          │
│    INSERT 500条记录                                              │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. 更新元数据                                                    │
│    UPDATE series_meta                                            │
│    SET last_raw_date = '2024-11-07'                             │
│        data_quality = 'complete'                                 │
└─────────────────────────────────────────────────────────────────┘


增量更新（第二天）
┌─────────────────────────────────────────────────────────────────┐
│ 1. 检查 series_meta.last_raw_date                               │
│    结果: '2024-11-07' （有历史数据）                             │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. 确定增量范围                                                  │
│    start_date = last_raw_date + 1 = '2024-11-08'                │
│    end_date = today = '2024-11-08'                               │
│    ⚠️ 需要获取: 仅1天数据！                                      │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. 调用数据源API（仅新数据）                                     │
│    FRED: fetch('RRPONTSYD', '2024-11-08', '2024-11-08')         │
│    返回: 1条记录 {'2024-11-08': 450.2}                          │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. 加载历史数据（用于窗口计算）                                  │
│    从数据库读取最近60天的 value_raw（Z计算需要60天窗口）        │
│    DB query: SELECT date, value_raw FROM series_data            │
│              WHERE series_id = X AND date >= '2024-09-09'       │
│    返回: 59条历史 + 1条新数据 = 60条                             │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. 计算数据链（仅新日期）                                        │
│    合并数据: [历史59条, 新1条]                                   │
│    计算转换: transform(60条数据) → 取最后1条结果                 │
│    计算Z:    rolling_z(60条, window=60) → 取最后1条              │
│    计算Score: score_from_z(最后1条Z) → 1条score                 │
│    ✅ 优化: 仅计算新日期，不重算历史                              │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. UPSERT 新数据                                                 │
│    INSERT OR REPLACE INTO series_data                            │
│    (series_id, date, view, value_raw, ..., score_0_100)         │
│    VALUES (X, '2024-11-08', 'daily', 450.2, ..., 67.3)          │
│    影响行数: 1条                                                 │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. 更新元数据                                                    │
│    UPDATE series_meta                                            │
│    SET last_raw_date = '2024-11-08',                            │
│        last_updated = CURRENT_TIMESTAMP                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 完整市场更新流程

### update_market_incremental('US') 详细步骤

```
步骤1: 获取所有US主指标
┌──────────────────────────────────────┐
│ SELECT * FROM series_meta            │
│ WHERE market='US' AND role='main'    │
│                                      │
│ 返回6个指标:                         │
│ - RRP_D20                            │
│ - TGA_D20                            │
│ - HY_OAS                             │
│ - VIX_LOG                            │
│ - DFII10                             │
│ - IWM_SPY_REL20                      │
└──────────────────────────────────────┘
            │
            ▼
步骤2: 并行/顺序更新每个指标（获取→计算→存储）
┌────────────────────────────────────────────────────────────────┐
│ 对每个指标 i 在 [RRP_D20, TGA_D20, ...]:                      │
│   ┌──────────────────────────────────────┐                     │
│   │ 2.1 update_indicator(i.code)         │                     │
│   │   - 检查last_raw_date                │                     │
│   │   - 获取新数据                        │                     │
│   │   - 计算完整数据链                    │                     │
│   │   - 保存到series_data                │                     │
│   └──────────────────────────────────────┘                     │
│                                                                 │
│ 结果: 所有6个主指标的series_data都更新到最新日期               │
└────────────────────────────────────────────────────────────────┘
            │
            ▼
步骤3: 计算市场综合分数（加权平均）
┌────────────────────────────────────────────────────────────────┐
│ 读取当前权重配置（例如Balanced风格）:                          │
│ ┌─────────────────────────────────┐                            │
│ │ SELECT indicator_code, weight   │                            │
│ │ FROM indicator_weights          │                            │
│ │ WHERE market='US'               │                            │
│ │   AND profile='Balanced'        │                            │
│ └─────────────────────────────────┘                            │
│ 返回: {RRP_D20: 15%, TGA_D20: 10%, HY_OAS: 20%, ...}          │
│                                                                 │
│ 对新日期 '2024-11-08':                                          │
│   读取所有6个指标的 score_0_100                                 │
│   计算加权平均:                                                 │
│     market_score = 0.15*62 + 0.10*58 + 0.20*45 + ...          │
│                  = 53.2                                         │
└────────────────────────────────────────────────────────────────┘
            │
            ▼
步骤4: 计算Regime（含persistence逻辑）
┌────────────────────────────────────────────────────────────────┐
│ 读取前几天的regime（用于persistence判断）:                     │
│ ┌─────────────────────────────────────────────┐                │
│ │ SELECT date, regime                         │                │
│ │ FROM regimes                                │                │
│ │ WHERE market='US' AND view='daily'          │                │
│ │   AND date >= '2024-11-05'                  │                │
│ │ ORDER BY date DESC LIMIT 3                  │                │
│ └─────────────────────────────────────────────┘                │
│ 返回: ['Balanced', 'Balanced', 'Balanced']                     │
│                                                                 │
│ 当前分数: 53.2                                                  │
│ 判断: 40 < 53.2 < 70 → 原始regime = 'Balanced'                 │
│                                                                 │
│ Persistence检查（假设需要连续3天确认切换）:                    │
│   如果前3天都是Balanced且当前也是Balanced → 确认为Balanced     │
│   如果前3天Balanced但当前>70 → 需要再观察2天才切换到Attack     │
└────────────────────────────────────────────────────────────────┘
            │
            ▼
步骤5: 更新US观察者指标（软确认+硬否决）
┌────────────────────────────────────────────────────────────────┐
│ 5.1 软确认组件:                                                 │
│   ┌────────────────────────────────────────┐                   │
│   │ 从series_data读取观察者指标的lamp:     │                   │
│   │ - IWM_SPY_REL20 lamp_color → 'G'      │                   │
│   │ - HYG_IEF_REL20 lamp_color → 'Y'      │                   │
│   │ - PAIR_TWEX_DXY → 'G' (从配对计算)    │                   │
│   │ - PAIR_CNH_CNY → 'Y'  (从配对计算)    │                   │
│   └────────────────────────────────────────┘                   │
│                                                                 │
│   加权计算:                                                     │
│     S = 0.30*(G=2) + 0.30*(Y=1) + 0.20*(G=2) + 0.20*(Y=1)     │
│       = 0.6 + 0.3 + 0.4 + 0.2 = 1.5                            │
│     判断: 0.8 < 1.5 < 1.6 → soft_final_lamp = 'Y'             │
│                                                                 │
│ 5.2 硬否决组件:                                                 │
│   ┌────────────────────────────────────────┐                   │
│   │ 检查硬否决规则:                        │                   │
│   │ - HY_OAS_JUMP: ΔZ(2w) = 0.8 < 1.5     │                   │
│   │   → lamp = 'G'                         │                   │
│   │ - VIX_EXTREME: Z = 1.2 < 2.0           │                   │
│   │   → lamp = 'G'                         │                   │
│   └────────────────────────────────────────┘                   │
│                                                                 │
│   MIN with persistence:                                         │
│     当前: MIN(['G', 'G']) = 'G'                                │
│     前3天: ['G', 'G', 'R']                                     │
│     Persistence过滤: 前3天有R，需要再等2天才能解除             │
│     → hard_veto_lamp = 'R' (persistence still active)          │
│                                                                 │
│ 5.3 最终灯色:                                                   │
│   if hard_veto_lamp == 'R':                                    │
│       final_lamp = 'R'                                         │
│   else:                                                        │
│       final_lamp = soft_final_lamp  # 'Y'                      │
│                                                                 │
│   结果: final_lamp = 'R' (硬否决优先)                           │
└────────────────────────────────────────────────────────────────┘
            │
            ▼
步骤6: 保存市场层数据
┌────────────────────────────────────────────────────────────────┐
│ 6.1 保存confirm_layer:                                          │
│   INSERT INTO confirm_layer (date, market, view, ...)          │
│   VALUES ('2024-11-08', 'US', 'daily',                         │
│           'G', 'Y', 'G', 'Y',  -- soft组件                      │
│           1.5, 'Y',            -- soft加权和最终                │
│           'G', 'G', 'R',       -- hard组件                      │
│           'R',                 -- hard最终                      │
│           'R')                 -- final_lamp                    │
│                                                                 │
│ 6.2 保存regimes:                                                │
│   INSERT INTO regimes (date, market, view, ...)                │
│   VALUES ('2024-11-08', 'US', 'daily',                         │
│           53.2,                -- market_score                  │
│           'Balanced',          -- regime                        │
│           'Y', 'R', 'R',       -- lamps (soft, hard, final)    │
│           0, FALSE)            -- persistence counter, changed  │
└────────────────────────────────────────────────────────────────┘
            │
            ▼
步骤7: 记录日志
┌────────────────────────────────────────────────────────────────┐
│ INSERT INTO data_fetch_history                                  │
│ (timestamp, action, status, message,                            │
│  indicator_code, date_range_start, date_range_end,              │
│  records_fetched, records_updated)                              │
│ VALUES                                                          │
│ (NOW(), 'update_market_incremental', 'success',                │
│  'US市场增量更新完成',                                          │
│  NULL, '2024-11-08', '2024-11-08',                             │
│  6, 6)                                                          │
└────────────────────────────────────────────────────────────────┘
```

---

## 🔧 参数重算流程

### recompute_market_full('US', '2024-10-01', '2024-11-08', 'daily', new_params)

```
场景: 用户将regime阈值从70/40改为75/35

步骤1: 保存新参数
┌────────────────────────────────────────────────────────────────┐
│ # 计算新参数的哈希                                              │
│ new_hash = hashlib.md5(json.dumps(new_params).encode()).hexdigest() │
│                                                                 │
│ # 保存到params表                                                │
│ INSERT INTO params (json_blob, params_hash, is_current, description) │
│ VALUES ('{"regime_thresholds": {"attack": 75, ...}}',          │
│         'a3f5c9e1...', 1, '调整regime阈值')                    │
│                                                                 │
│ # 将旧参数标记为非当前                                          │
│ UPDATE params SET is_current = 0 WHERE params_hash != 'a3f5c9e1...' │
└────────────────────────────────────────────────────────────────┘
            │
            ▼
步骤2: 从数据库读取原始数据（不重新获取）
┌────────────────────────────────────────────────────────────────┐
│ 对每个US主指标:                                                 │
│   SELECT date, value_raw                                        │
│   FROM series_data d                                            │
│   JOIN series_meta m ON d.series_id = m.id                     │
│   WHERE m.market = 'US' AND m.role = 'main'                    │
│     AND d.view = 'daily'                                        │
│     AND d.date BETWEEN '2024-10-01' AND '2024-11-08'           │
│   ORDER BY m.code, d.date                                       │
│                                                                 │
│ 结果: 获取所有6个指标的原始数据（约6 * 30 = 180条记录）        │
│ ⚠️ 注意: value_raw不变，从DB读取，不调用API                    │
└────────────────────────────────────────────────────────────────┘
            │
            ▼
步骤3: 用新参数重新计算派生数据
┌────────────────────────────────────────────────────────────────┐
│ 对每个指标的value_raw时间序列:                                  │
│                                                                 │
│ 3.1 转换（transform参数未变，结果相同）:                        │
│     VIX: log_winsor(value_raw, p_low=0.02, p_high=0.98)        │
│     → value_transformed 保持不变                                │
│                                                                 │
│ 3.2 Z分数（窗口参数未变，结果相同）:                            │
│     rolling_madz(value_transformed, window=40)                  │
│     → z_score 保持不变                                          │
│                                                                 │
│ 3.3 Score（公式未变，结果相同）:                                │
│     score = clamp(50 + 10*z_score, 0, 100)                     │
│     → score_0_100 保持不变                                      │
│                                                                 │
│ 3.4 单指标灯色（阈值参数未变，结果相同）:                       │
│     lamp = lamp_from_score(score, green=60, red=40)            │
│     → lamp_color 保持不变                                       │
│                                                                 │
│ ℹ️ 本例中指标级数据不变，因为参数变化仅影响regime判断           │
└────────────────────────────────────────────────────────────────┘
            │
            ▼
步骤4: 重算市场层数据（使用新阈值）
┌────────────────────────────────────────────────────────────────┐
│ 4.1 市场综合分数（权重未变，结果相同）:                         │
│     对每天: market_score = Σ(weight_i * score_i)               │
│     → market_score 保持不变                                     │
│                                                                 │
│ 4.2 Regime判断（使用新阈值 75/35）:                             │
│     旧参数 (70/40):                                             │
│       2024-11-05: score=72 → Attack  (≥70)                     │
│       2024-11-06: score=68 → Balanced (40<x<70)                │
│       2024-11-07: score=73 → Attack  (≥70)                     │
│                                                                 │
│     新参数 (75/35):                                             │
│       2024-11-05: score=72 → Balanced (35<x<75) ⚠️ 变化!        │
│       2024-11-06: score=68 → Balanced (35<x<75)                │
│       2024-11-07: score=73 → Balanced (35<x<75)                │
│                                                                 │
│ 4.3 Persistence重新应用（规则未变，但输入变了）:                │
│     因为新参数下连续3天都是Balanced，确认为Balanced             │
│                                                                 │
│ 4.4 确认层（规则未变，结果相同）:                               │
│     软硬确认逻辑和阈值未变 → final_lamp保持不变                 │
└────────────────────────────────────────────────────────────────┘
            │
            ▼
步骤5: 批量更新数据库
┌────────────────────────────────────────────────────────────────┐
│ 5.1 更新series_data（仅更新params_hash）:                       │
│     UPDATE series_data                                          │
│     SET params_hash = 'a3f5c9e1...'                            │
│     WHERE series_id IN (US主指标)                               │
│       AND date BETWEEN '2024-10-01' AND '2024-11-08'           │
│       AND view = 'daily'                                        │
│                                                                 │
│     影响行数: 180条                                             │
│                                                                 │
│ 5.2 更新regimes（regime字段变化）:                              │
│     UPDATE regimes                                              │
│     SET regime = (新regime值),                                  │
│         params_hash = 'a3f5c9e1...',                           │
│         regime_changed = (是否变化)                             │
│     WHERE market = 'US' AND view = 'daily'                      │
│       AND date BETWEEN '2024-10-01' AND '2024-11-08'           │
│                                                                 │
│     影响行数: 30条                                              │
│                                                                 │
│ 5.3 confirm_layer不需要更新（规则未变）                         │
└────────────────────────────────────────────────────────────────┘
            │
            ▼
步骤6: 返回重算结果
┌────────────────────────────────────────────────────────────────┐
│ return {                                                        │
│     'status': 'success',                                        │
│     'recomputed_records': 210,  # 180 series_data + 30 regimes │
│     'params_hash': 'a3f5c9e1...',                              │
│     'changes': {                                                │
│         'regime_changed_dates': ['2024-11-05', '2024-11-07'],  │
│         'old_regimes': {'2024-11-05': 'Attack', ...},          │
│         'new_regimes': {'2024-11-05': 'Balanced', ...}         │
│     }                                                           │
│ }                                                               │
│                                                                 │
│ ⏱️ 耗时: ~2秒（因为不需要网络请求，纯计算）                     │
└────────────────────────────────────────────────────────────────┘
```

---

## 🔍 GUI查询示例

### 用户打开"US Overview"标签页，选择最近3个月

```
GUI动作: 切换到US Overview标签页
        日期范围: 2024-08-08 到 2024-11-08
        视图: Daily

后端查询流程:
┌────────────────────────────────────────────────────────────────┐
│ 1. 查询市场概览数据                                             │
│    repo.load_market_overview('US', '2024-08-08', '2024-11-08', 'daily') │
│    ↓                                                            │
│    SELECT date, market_score, regime, lamp_final, lamp_soft, lamp_hard │
│    FROM regimes                                                 │
│    WHERE market='US' AND view='daily'                           │
│      AND date BETWEEN '2024-08-08' AND '2024-11-08'            │
│    ORDER BY date                                                │
│    ↓                                                            │
│    返回DataFrame (约60行):                                      │
│      date        market_score  regime     lamp_final  ...       │
│      2024-08-08  65.2          Balanced   Y                     │
│      2024-08-09  68.5          Balanced   G                     │
│      ...                                                        │
│      2024-11-08  53.2          Balanced   R                     │
└────────────────────────────────────────────────────────────────┘
            │
            ▼
┌────────────────────────────────────────────────────────────────┐
│ 2. 绘制Overview图表                                             │
│    OverviewChart.plot(overview_df)                              │
│    ↓                                                            │
│    a) 主图: 折线图(market_score vs date)                        │
│       - Y轴: 0-100                                              │
│       - 横线: 75 (新attack阈值), 35 (新defense阈值)            │
│    ↓                                                            │
│    b) 背景色带: 按regime分段着色                                │
│       - Attack区域: 淡红色                                      │
│       - Balanced区域: 淡黄色                                    │
│       - Defense区域: 淡绿色                                     │
│    ↓                                                            │
│    c) 底部灯色条: 按lamp_final着色                              │
│       - 每天一个色块: G=绿, Y=黄, R=红                          │
└────────────────────────────────────────────────────────────────┘
            │
            ▼
┌────────────────────────────────────────────────────────────────┐
│ 3. 用户悬停鼠标到某个日期点 (2024-11-05)                        │
│    显示工具提示:                                                │
│      日期: 2024-11-05                                           │
│      市场分数: 72.0                                             │
│      Regime: Balanced (新参数下)                                │
│      最终灯色: 红 (硬否决)                                       │
│      软确认: 黄                                                 │
│      硬否决: 红 (VIX极值persistence)                            │
└────────────────────────────────────────────────────────────────┘
```

### 用户点击"VIX_LOG"指标子图

```
GUI动作: 点击左侧指标列表中的"VIX_LOG"
        自动继承日期范围: 2024-08-08 到 2024-11-08
        视图: Daily

后端查询流程:
┌────────────────────────────────────────────────────────────────┐
│ 1. 查询指标完整数据                                             │
│    repo.load_indicator_complete('VIX_LOG', '2024-08-08',       │
│                                  '2024-11-08', 'daily')         │
│    ↓                                                            │
│    SELECT d.date, d.value_raw, d.value_transformed,            │
│           d.z_score, d.score_0_100, d.lamp_color               │
│    FROM series_data d                                           │
│    JOIN series_meta m ON d.series_id = m.id                    │
│    WHERE m.code='VIX_LOG' AND d.view='daily'                   │
│      AND d.date BETWEEN '2024-08-08' AND '2024-11-08'          │
│    ORDER BY d.date                                              │
│    ↓                                                            │
│    返回DataFrame (约60行):                                      │
│      date        value_raw  value_transformed  z_score  score_0_100  lamp_color │
│      2024-08-08  18.23      2.902             0.52     55.2         Y │
│      2024-08-09  16.45      2.800            -0.21     47.9         Y │
│      ...                                                        │
│      2024-11-08  16.23      2.786            -0.45     45.5         Y │
└────────────────────────────────────────────────────────────────┘
            │
            ▼
┌────────────────────────────────────────────────────────────────┐
│ 2. 绘制双Y轴指标图表                                            │
│    IndicatorChart.plot(indicator_df, indicator_config)          │
│    ↓                                                            │
│    a) 左Y轴: value_raw (原始VIX值)                              │
│       - 蓝色实线: value_raw                                     │
│       - 蓝色虚线: value_transformed (log后的值)                 │
│       - Y轴范围: 自动适应 (12-25)                               │
│    ↓                                                            │
│    b) 右Y轴: score_0_100                                        │
│       - 橙色粗线: score_0_100                                   │
│       - 横线: 60 (green阈值), 40 (red阈值)                     │
│       - Y轴范围: 0-100                                          │
│    ↓                                                            │
│    c) 背景色: 按lamp_color分段着色                              │
│       - Green段: 淡绿色                                         │
│       - Yellow段: 淡黄色                                        │
│       - Red段: 淡红色                                           │
└────────────────────────────────────────────────────────────────┘
            │
            ▼
┌────────────────────────────────────────────────────────────────┐
│ 3. 用户悬停到某个点 (2024-10-15)                                │
│    显示详细数值:                                                │
│      日期: 2024-10-15                                           │
│      VIX原始值: 22.45                                           │
│      VIX转换值: 3.111 (log)                                     │
│      Z分数: 1.87 (MADZ 40天)                                    │
│      Score: 68.7                                                │
│      灯色: 绿                                                   │
└────────────────────────────────────────────────────────────────┘
```

---

## 💾 数据持久化保证

### UPSERT语义确保幂等性

```sql
-- SQLite 3.24+ 的 UPSERT 语法
INSERT INTO series_data (series_id, date, view, value_raw, value_transformed, z_score, score_0_100, lamp_color, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
ON CONFLICT(series_id, date, view) 
DO UPDATE SET 
    value_raw = excluded.value_raw,
    value_transformed = excluded.value_transformed,
    z_score = excluded.z_score,
    score_0_100 = excluded.score_0_100,
    lamp_color = excluded.lamp_color,
    updated_at = CURRENT_TIMESTAMP;

-- 结果: 多次执行相同数据不会重复，仅更新
```

### 批量操作优化

```python
# 使用pandas批量upsert (比逐条INSERT快100倍)
def upsert_series_data_batch(series_id: int, df: pd.DataFrame, view: str):
    df['series_id'] = series_id
    df['view'] = view
    df['updated_at'] = datetime.now()
    
    # 方式1: 使用pandas to_sql + SQLAlchemy
    df.to_sql('series_data_temp', con=engine, if_exists='replace', index=False)
    
    engine.execute("""
        INSERT INTO series_data 
        SELECT * FROM series_data_temp
        ON CONFLICT(series_id, date, view) DO UPDATE SET
            value_raw = excluded.value_raw,
            value_transformed = excluded.value_transformed,
            z_score = excluded.z_score,
            score_0_100 = excluded.score_0_100,
            lamp_color = excluded.lamp_color,
            updated_at = excluded.updated_at
    """)
    
    # 方式2: 使用executemany (更快)
    values = df[['series_id', 'date', 'view', 'value_raw', 'value_transformed', 
                 'z_score', 'score_0_100', 'lamp_color']].values.tolist()
    
    cursor.executemany("""
        INSERT INTO series_data (...) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(...) DO UPDATE SET ...
    """, values)
```

---

## 📅 周视图生成详解

### 从日视图重采样生成周视图

```python
def generate_weekly_view(market: str, start_date, end_date):
    """
    从daily数据生成weekly数据（Friday标签）
    """
    # 步骤1: 读取所有日视图数据
    daily_data = {}
    for indicator in get_market_indicators(market, role='main'):
        df = repo.load_indicator_complete(
            indicator.code, start_date, end_date, 'daily'
        )
        daily_data[indicator.code] = df
    
    # 步骤2: 对每个指标重采样
    weekly_data = {}
    for code, daily_df in daily_data.items():
        daily_df.set_index('date', inplace=True)
        
        # 根据指标配置选择聚合方法
        config = get_indicator_config(code)
        agg_method = config['weekly_agg']  # 'last' 或 'mean'
        
        if agg_method == 'last':
            # 取每周Friday的值
            weekly_df = daily_df.resample('W-FRI').last()
        elif agg_method == 'mean':
            # 取每周平均值（某些指标可能需要）
            weekly_df = daily_df.resample('W-FRI').mean()
        
        # 重新计算Z和Score（基于weekly的窗口）
        # 注意: weekly的Z需要用weekly数据的窗口，不是daily窗口
        weekly_df['z_score'] = rolling_madz(
            weekly_df['value_transformed'], 
            window=60  # 60周 ≈ 1.2年
        )
        weekly_df['score_0_100'] = score_from_z(weekly_df['z_score'])
        weekly_df['lamp_color'] = lamp_from_score(weekly_df['score_0_100'])
        
        weekly_data[code] = weekly_df
    
    # 步骤3: 计算market层数据（同daily流程）
    for date in weekly_dates:
        market_score = compute_weighted_score(weekly_data, date)
        regime = compute_regime(market_score, previous_regimes, 
                                persistence_weeks=1)  # 周persistence
        confirm_layer = compute_confirm_layer(weekly_data, date,
                                               persistence_weeks=2)  # 周persistence
        
        # 保存到数据库（view='weekly'）
        repo.save_regime_with_score(market, date, 'weekly', ...)
        repo.save_confirm_layer(market, date, 'weekly', ...)
    
    # 步骤4: 批量保存所有指标的周数据
    for code, weekly_df in weekly_data.items():
        repo.upsert_series_data_batch(code, weekly_df, view='weekly')

# 验证周数据
weekly_vix = repo.load_indicator_complete('VIX_LOG', view='weekly')
print(weekly_vix['date'].dt.day_name().unique())  # 应该只有 ['Friday']
print(len(weekly_vix))  # 应该约为 len(daily_vix) / 5
```

---

## ✅ 数据完整性自检

### 启动时自动检查

```python
def startup_data_check(repo: Repository):
    """
    应用启动时自动检查数据完整性
    """
    issues = []
    
    for market in ['CN', 'US']:
        # 检查最近3个月数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
        
        # 检查指标数据
        completeness = repo.check_data_completeness(
            market, (start_date, end_date), 'daily'
        )
        
        for ind_code, status in completeness.items():
            if status['status'] != 'complete':
                issues.append({
                    'type': 'missing_indicator_data',
                    'indicator': ind_code,
                    'market': market,
                    'coverage': status['coverage_pct'],
                    'missing_days': len(status['missing_dates'])
                })
        
        # 检查market层数据是否与指标数据一致
        regime_dates = repo.get_dates_in_regimes(market, start_date, end_date, 'daily')
        expected_dates = get_business_days(start_date, end_date)
        missing_regime_dates = set(expected_dates) - set(regime_dates)
        
        if missing_regime_dates:
            issues.append({
                'type': 'missing_regime_data',
                'market': market,
                'missing_days': len(missing_regime_dates)
            })
    
    # 显示在GUI日志面板
    if issues:
        log_warning(f"发现 {len(issues)} 个数据完整性问题:")
        for issue in issues:
            if issue['type'] == 'missing_indicator_data':
                log_warning(f"  {issue['market']} - {issue['indicator']}: "
                           f"数据覆盖率 {issue['coverage']:.1f}%")
    else:
        log_info("数据完整性检查通过")
    
    return issues
```

---

## 🎯 总结

### 增量更新的核心优势

1. **节省网络流量**：仅获取新日期数据，减少API调用
2. **提高速度**：增量更新比全量重新获取快100倍
3. **数据溯源**：`last_raw_date`清晰标记数据新鲜度
4. **参数实验**：修改参数后快速重算，不需重新下载
5. **GUI即时响应**：数据库查询延迟<100ms，GUI流畅

### 手动数据更新工作流（用户视角）

```
每天早上（周一到周五）:
1. 打开应用
2. 点击"增量更新"按钮
3. 等待10-30秒（6个US指标 + 部分CN指标自动获取）
4. CSV导入按钮导入CN特有数据（两融、北向、ETF、PMI等）
5. 查看最新的Overview图表和灯色
6. 完成！

参数调优实验:
1. 修改左侧控制面板的参数（如regime阈值）
2. 点击"重新计算"按钮
3. 等待2-5秒（纯计算，无网络）
4. 查看参数变化后的regime和lamp结果
5. 满意则保存，不满意则撤销或继续调整
```

通过这套增量数据库设计，您的应用将具有**专业量化工具**的数据管理能力！🚀

