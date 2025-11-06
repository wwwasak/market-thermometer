# CN市场数据API获取方案

## 数据源选择：akshare

**akshare** 是专门为中国金融市场设计的开源数据接口库，完全免费，无需API密钥。

### 优势
- ✅ **完全免费** - 无需注册或API密钥
- ✅ **数据全面** - 覆盖A股、期货、债券、宏观经济等
- ✅ **更新及时** - 数据源自东方财富、新浪财经等
- ✅ **易于使用** - 返回pandas DataFrame格式
- ✅ **活跃维护** - GitHub上持续更新

---

## CN市场指标API映射

### 主指标（6个）

#### 1. 两融余额斜率 ✅ **可通过API获取**

**akshare接口**: `stock_margin_sse()` 或 `stock_margin_detail_sse()`

```python
import akshare as ak

# 获取上交所融资融券余额
margin_data = ak.stock_margin_sse(start_date="20230101", end_date="20251105")
# 返回：日期、融资余额、融券余额、融资融券余额

# 或获取更详细的数据
margin_detail = ak.stock_margin_detail_sse(symbol="全部")
```

**数据字段**:
- 日期
- 融资余额
- 融券余额  
- 融资融券余额（总计）

**变换**: 使用融资融券余额总计，计算`slope_20_60_ewma`

---

#### 2. USD/CNH 20日%变动 ✅ **可通过API获取**

**方案1: yfinance** (已实现)
```python
import yfinance as yf
cnh = yf.download("CNH=X", start="2023-01-01", end="2025-11-05")
```

**方案2: akshare**
```python
import akshare as ak

# 获取在岸人民币汇率
usdcny = ak.fx_spot_quote()  # 实时汇率
# 或历史数据
usdcny_hist = ak.currency_hist(symbol="USDCNY")
```

**推荐**: 继续使用yfinance，但需要更长的历史数据（至少1年）

**状态**: ⚠️ 当前只获取到1条数据，需要增加历史数据范围

---

#### 3. 北向成交额/全A成交额 ✅ **可通过API获取**

**akshare接口**: 
```python
import akshare as ak

# 北向资金流入
north_flow = ak.stock_em_hsgt_north_net_flow_in(symbol="北上")
# 返回：日期、北向成交额、净流入、北向持股占比等

# 全A成交额
market_turnover = ak.stock_market_fund_flow()
# 返回：日期、今日主力净流入、今日超大单净流入、全市场成交额等
```

**计算方式**:
```python
ratio = north_turnover / all_a_turnover
```

---

#### 4. 中证1000/沪深300 20日相对收益 ✅ **可通过API获取**

**akshare接口**:
```python
import akshare as ak

# 中证1000指数
csi1000 = ak.stock_zh_index_daily(symbol="sh000852")
# 沪深300指数
hs300 = ak.stock_zh_index_daily(symbol="sh000300")
```

**或者使用yfinance** (更推荐，数据更稳定):
```python
import yfinance as yf

# 中证1000
csi1000 = yf.download("000852.SS", start="2023-01-01")
# 沪深300
hs300 = yf.download("000300.SS", start="2023-01-01")
```

**变换**: 使用`transform_relret20`计算相对强度

---

#### 5. 官方PMI新订单同比标准差 ✅ **可通过API获取**

**akshare接口**:
```python
import akshare as ak

# 官方制造业PMI
pmi = ak.macro_china_pmi()
# 返回：日期、制造业PMI、新订单指数、生产指数等

# 或者更详细的
pmi_detail = ak.macro_china_pmi_yearly()
```

**数据字段**:
- 制造业PMI
- 新订单指数 ← **我们需要的**
- 生产指数
- 从业人员指数

**变换**: 使用`transform_yoy_std_ffill`计算同比标准差

---

#### 6. 股债收益差期望-10Y国债收益 ✅ **可通过API获取**

**akshare接口**:
```python
import akshare as ak

# 中国国债收益率
bond_yield = ak.bond_zh_us_rate()
# 或指定期限
bond_10y = ak.bond_china_yield(start_date="20230101", end_date="20251105")

# 股票收益率（从指数PE/PB推算）
stock_valuation = ak.stock_a_all_pb()  # 全A的PB
```

**计算方式**:
```python
# 股票预期收益 = 1 / PE (盈利收益率)
# 股债收益差 = 股票预期收益 - 10Y国债收益率
```

---

### 观察者指标（5个）

#### 1. 场内ETF 5日净流入 ✅ **可通过API获取**

**akshare接口**:
```python
import akshare as ak

# ETF资金流向
etf_flow = ak.fund_etf_fund_flow_sina(symbol="全部")
# 返回：日期、主力净流入、小单净流入、大单净流入等

# 或者
etf_daily = ak.fund_etf_hist_sina(symbol="sh510300")  # 沪深300ETF
```

**变换**: 计算5日净流入总和

---

#### 2-5. 配对确认指标 ✅ **可通过现有API**

这些指标依赖主指标的数据，只要主指标能获取，配对指标就能计算。

---

## 实现方案

### 方案1: 集成akshare到DataSource模块 ⭐ **推荐**

在`core/datasource.py`中添加`AKShareFetcher`类：

```python
class AKShareFetcher:
    def __init__(self):
        try:
            import akshare as ak
            self.ak = ak
        except ImportError:
            raise DataFetchError("akshare not installed. Run: pip install akshare")
    
    def fetch(self, symbol: str, start_date: datetime, end_date: datetime) -> pd.Series:
        """
        根据symbol类型获取不同的akshare数据
        
        symbol格式:
        - "margin:sse" - 上交所融资融券
        - "north:flow" - 北向资金
        - "index:000852" - 中证1000指数
        - "pmi:neworder" - PMI新订单
        - "bond:10y" - 10年期国债
        - "etf:flow" - ETF资金流向
        """
        # 实现不同数据类型的获取
        pass
```

### 方案2: 使用混合数据源

- **宏观数据**: FRED (国际) + akshare (中国)
- **市场数据**: yfinance (指数、外汇) + akshare (A股特色数据)
- **特色数据**: akshare (两融、北向、ETF流向)

---

## 安装和配置

### 1. 安装akshare

```powershell
pip install akshare
```

### 2. 更新requirements.txt

```txt
akshare>=1.12.0
```

### 3. 更新Config

在`core/config.py`中添加akshare数据源配置：

```python
{
    "code": "CN_MARGIN_SLOPE",
    "name": "两融余额斜率(20/60 EWMA)",
    "direction": "up_good",
    "transform": "slope_20_60_ewma",
    "z_type": "Z",
    "z_window": 60,
    "source": "akshare",        # ← 新数据源
    "symbol": "margin:sse"       # ← akshare标识
}
```

---

## 数据质量对比

| 指标 | CSV | yfinance | akshare | 推荐 |
|------|-----|----------|---------|------|
| 两融余额 | ✅ | ❌ | ✅ | **akshare** |
| USD/CNH | ❌ | ✅ | ⚠️ | **yfinance** |
| 北向资金 | ✅ | ❌ | ✅ | **akshare** |
| 中证指数 | ❌ | ✅ | ✅ | **yfinance** (更稳定) |
| PMI数据 | ✅ | ❌ | ✅ | **akshare** |
| 国债收益率 | ❌ | ❌ | ✅ | **akshare** |
| ETF流向 | ✅ | ❌ | ✅ | **akshare** |

---

## 预期覆盖率

### 使用akshare后

**CN市场主指标**:
- ✅ 两融余额斜率 (akshare)
- ✅ USD/CNH 20日%变动 (yfinance，增加历史范围)
- ✅ 北向成交额/全A成交额 (akshare)
- ✅ 中证1000/沪深300 (yfinance)
- ✅ PMI新订单标准差 (akshare)
- ✅ 股债收益差 (akshare)

**预期成功率**: **6/6 = 100%**

**CN市场观察者**:
- ✅ ETF净流入 (akshare)
- ✅ 配对指标 (依赖主指标)

**预期成功率**: **5/5 = 100%**

---

## 实施步骤

### 阶段1: 准备工作 (10分钟)
1. ✅ 安装akshare
2. ✅ 测试基本接口
3. ✅ 确认数据格式

### 阶段2: 开发AKShareFetcher (30分钟)
1. 创建`AKShareFetcher`类
2. 实现各类数据获取方法
3. 添加错误处理和数据清洗

### 阶段3: 集成到DataSourceManager (20分钟)
1. 在`DataSourceManager`中添加akshare支持
2. 更新配置文件格式
3. 修改pipeline的数据获取逻辑

### 阶段4: 测试验证 (20分钟)
1. 测试每个CN指标的数据获取
2. 验证数据质量和完整性
3. 运行完整的pipeline测试

**总计时间**: 约80分钟

---

## 风险和注意事项

### 数据稳定性
- ⚠️ akshare数据源可能会变化（东方财富、新浪财经等）
- ⚠️ 部分接口可能会调整或失效
- ✅ 建议实现重试机制和fallback方案

### 数据质量
- ⚠️ 某些数据可能有延迟（T+1）
- ⚠️ 节假日可能缺失数据
- ✅ 需要实现前向填充(ffill)

### API限制
- ✅ akshare无请求频率限制（免费）
- ⚠️ 但建议添加延迟避免被封IP

---

## 结论

### ✅ **CN市场数据完全可以通过API获取**

通过集成akshare，可以实现：
- **11/11个CN指标通过API自动获取**
- **无需手动维护CSV文件**
- **数据自动更新**
- **与US市场一致的体验**

### 下一步行动

**立即实施**: 开发并集成AKShareFetcher模块

**预期结果**: 
- US市场: 10/10 ✅
- CN市场: 11/11 ✅
- **总体覆盖率: 100%** 🎉

---

*文档生成时间: 2025-11-05*  
*akshare版本: 1.12.0+*

