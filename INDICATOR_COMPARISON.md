# 指标对比：需求 vs 当前实现

## ❌ 问题发现

### CN市场

#### 主指标（demand.txt要求6个）

| # | demand.txt需求 | 当前实现 | 状态 |
|---|---------------|---------|------|
| 1 | CN_MARGIN_SLOPE | ✅ CN_MARGIN_SLOPE | ✅ 正确 |
| 2 | CNH_PCT20 | ✅ CNH_PCT20 | ✅ 正确 |
| 3 | NORTH_TURNOVER_SHARE | ✅ NORTH_TURNOVER_SHARE | ✅ 正确 |
| 4 | CSI1000_OVER_300_REL20 | ✅ CSI1000_OVER_300_REL20 | ✅ 正确 |
| 5 | PMI_NEWORDER_YOY_STD | ✅ PMI_NEWORDER_YOY_STD | ✅ 正确 |
| 6 | **CN_EPS_YIELD_MINUS_CGB10**<br>（股债收益差 = 全A盈利收益率 - 10Y国债） | ❌ CN_BOND_10Y<br>❌ CN_EPS_YIELD (分开的) | ❌ **错误！应该是派生指标** |

**问题**：第6个主指标应该是**股债收益差**（单个派生指标），不是CN_BOND_10Y和CN_EPS_YIELD分开的两个指标。

#### 观察者指标

| 用途 | demand.txt需求 | 当前实现 | 状态 |
|------|---------------|---------|------|
| Hard veto | ETF_NETFLOW_5D | ✅ ETF_FLOW_5D | ✅ 正确 |
| Soft confirm (pair) | CNY (for PAIR_CNH_CNY) | ✅ CNY_PCT20 | ✅ 正确 |
| - | - | ❌ CSI300_PCT20 | ❌ **多余！不需要** |
| - | - | ❌ CN_EPS_YIELD (单独) | ❌ **多余！应该在主指标的股债差中** |

**问题**：观察者指标多了CSI300_PCT20和CN_EPS_YIELD，这两个不在需求中。

---

### US市场

#### 主指标（demand.txt要求6个）

| # | demand.txt需求 | 当前实现 | 状态 |
|---|---------------|---------|------|
| 1 | RRP_D20 | ✅ RRP_D20 | ✅ 正确 |
| 2 | TGA_D20 | ✅ TGA_D20 | ✅ 正确 |
| 3 | HY_OAS | ✅ HY_OAS | ✅ 正确 |
| 4 | VIX_LOG | ✅ VIX_LOG | ✅ 正确 |
| 5 | DFII10 | ✅ DFII10 | ✅ 正确 |
| 6 | IWM_SPY_REL20 | ✅ IWM_SPY_REL20 | ✅ 正确 |

**状态**：✅ US主指标完全正确

#### 观察者指标

##### Hard Veto

| 需求 | 说明 | 状态 |
|------|------|------|
| HY_OAS_JUMP | 基于HY_OAS主指标计算<br>(ΔZ(2w) > +1.5 OR score ≤ 40) | ⚠️ 需确认实现 |
| VIX_EXTREME | 基于VIX_LOG主指标计算<br>(Z > +2.0 OR score ≤ 40) | ⚠️ 需确认实现 |

##### Soft Confirm

| 需求 | 权重 | 数据来源 | 当前实现 | 状态 |
|------|------|---------|---------|------|
| IWM_SPY_SOFT | 0.30 | 基于IWM_SPY_REL20主指标 | ⚠️ 需确认 | ⚠️ |
| HYG_IEF_SOFT | 0.30 | 需要HYG、IEF价格数据 | ❌ 未实现？ | ❌ |
| PAIR_TWEX_DXY | 0.20 | 需要DTWEXBGS、DXY数据 | ❌ 未实现？ | ❌ |
| PAIR_CNH_CNY | 0.20 | CNH(主指标) + CNY(观察者) | ✅ CNY已实现 | ✅ |

**问题**：US观察者指标可能缺失HYG、IEF、DTWEXBGS、DXY等数据。

---

## 📋 正确的指标清单

### CN市场（正确版本）

#### 主指标（6个）
1. ✅ CN_MARGIN_SLOPE - 两融余额斜率
2. ✅ CNH_PCT20 - USD/CNH 20日%变动
3. ✅ NORTH_TURNOVER_SHARE - 北向成交额占比
4. ✅ CSI1000_OVER_300_REL20 - 中证1000/沪深300相对收益
5. ✅ PMI_NEWORDER_YOY_STD - PMI新订单同比标准化
6. ❌ **CN_EPS_YIELD_MINUS_CGB10** - 股债收益差（需要修改实现）
   - 基础数据：全A盈利收益率 (CSV)
   - 基础数据：10年期国债收益率 (akshare ✅)
   - 计算：EPS收益率 - 10Y国债收益率

#### 观察者指标（2个）
1. ✅ ETF_NETFLOW_5D - 宽基ETF 5日净申赎 (Hard veto)
2. ✅ CNY - USD/CNY价格 (Soft confirm, for PAIR_CNH_CNY)

#### 需要删除的多余指标
- ❌ CSI300_PCT20 - 不在需求中
- ❌ CN_EPS_YIELD (单独) - 应该合并到股债收益差中

---

### US市场（正确版本）

#### 主指标（6个）- 全部正确 ✅
1. ✅ RRP_D20
2. ✅ TGA_D20
3. ✅ HY_OAS
4. ✅ VIX_LOG
5. ✅ DFII10
6. ✅ IWM_SPY_REL20

#### 观察者指标

##### Hard Veto（2个，基于主指标计算）
1. HY_OAS_JUMP - 从HY_OAS派生
2. VIX_EXTREME - 从VIX_LOG派生

##### Soft Confirm（4个数据源，形成4个灯）
1. IWM_SPY_SOFT (0.30) - 从IWM_SPY_REL20主指标派生
2. **HYG_IEF_SOFT** (0.30) - 需要额外数据：
   - ❓ HYG (iShares iBoxx High Yield Corporate Bond ETF)
   - ❓ IEF (iShares 7-10 Year Treasury Bond ETF)
3. **PAIR_TWEX_DXY** (0.20) - 需要额外数据：
   - ❓ DTWEXBGS (FRED: Trade Weighted U.S. Dollar Index)
   - ❓ DXY (U.S. Dollar Index)
4. PAIR_CNH_CNY (0.20) - 已有：
   - ✅ CNH (主指标)
   - ✅ CNY (观察者)

---

## 🔧 需要修复的问题

### 优先级1：CN主指标第6个（关键错误）

**问题**：当前实现将CN_BOND_10Y作为主指标，但需求要求的是**股债收益差**

**修复方案**：
```python
# 主指标第6个应该是派生指标
CN_EPS_YIELD_MINUS_CGB10 = CN_EPS_YIELD - CN_BOND_10Y

# 基础数据：
# - CN_EPS_YIELD: CSV导入（全A盈利收益率）
# - CN_BOND_10Y: akshare自动获取 ✅ 已实现
```

### 优先级2：CN观察者指标清理

**删除多余指标**：
- CSI300_PCT20（不在需求中）
- CN_EPS_YIELD单独指标（应该用于计算股债差，不单独作为观察者）

### 优先级3：US观察者数据补充

**需要补充的数据源**：
```python
# Soft confirm所需数据
HYG = yfinance.download('HYG')  # 高收益债ETF
IEF = yfinance.download('IEF')  # 7-10年国债ETF
DTWEXBGS = fred.get('DTWEXBGS')  # 贸易加权美元指数
DXY = yfinance.download('DX-Y.NYB')  # 美元指数

# 计算相对收益
HYG_IEF_REL20 = relret20(HYG, IEF)
# 然后转换为灯信号
```

---

## 📊 数据源覆盖率（修正后）

### CN市场
- **主指标基础数据**：
  - 5个自动获取 ✅ (margin, CNH, north, indices, PMI)
  - 1个akshare ✅ (bond 10Y)
  - 1个CSV 📋 (EPS yield)
  - **股债差派生**：自动计算 ✅
- **观察者数据**：
  - ETF净流入：akshare ✅
  - CNY：yfinance ✅

### US市场
- **主指标**：100%自动 ✅
- **观察者数据**：
  - Hard veto：基于主指标计算 ✅
  - HYG, IEF：yfinance可获取 ✅
  - DTWEXBGS：FRED可获取 ✅
  - DXY：yfinance可获取 ✅

---

## ✅ 总结

**当前问题**：
1. ❌ CN主指标第6个错误：应该是**股债收益差**，不是单独的国债收益率
2. ❌ CN观察者多了2个不需要的指标（CSI300_PCT20, CN_EPS_YIELD单独）
3. ⚠️ US观察者数据需要补充（HYG, IEF, DTWEXBGS, DXY）

**修复后覆盖率**：
- CN主指标：6/6 (5个自动 + 1个派生自动)
- CN观察者：2/2 (全部自动)
- US主指标：6/6 (全部自动)
- US观察者：全部可自动获取 ✅

**好消息**：所有需要的数据都可以自动获取！只需要重新组织指标结构。

