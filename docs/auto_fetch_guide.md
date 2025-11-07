# 完全自动获取近三年数据指南

## 📋 功能说明

`fetch_3years_data_auto.py` 脚本实现了**完全自动化**的数据获取，无需任何CSV导入。

### 支持的数据源

1. **FRED** - 美国经济数据（需要FRED_API_KEY）
   - RRP、TGA、HY OAS、TIPS实际利率、Trade-Weighted USD等

2. **yfinance** - Yahoo Finance（免费，无需API密钥）
   - VIX、IWM、SPY、HYG、IEF、CNY汇率等

3. **akshare** - 中国金融数据（免费，无需API密钥）
   - 融资融券余额、北向资金、指数、PMI、国债收益率、ETF资金流等
   - **注意**：akshare底层使用东方财富API，所以东方财富数据通过akshare获取

4. **Stooq** - 波兰金融数据（免费，通过pandas-datareader）
   - CNH（离岸人民币）汇率等

## 🚀 使用方法

### 前置条件

1. **安装依赖**：
```powershell
pip install -r requirements.txt
```

2. **配置FRED API密钥**（可选，仅US市场需要）：
```powershell
# 创建 .env 文件
echo "FRED_API_KEY=your_fred_api_key_here" > .env
```

**注意**：如果没有FRED API密钥，US市场的部分指标（RRP、TGA、HY OAS等）将无法获取，但其他指标（VIX、IWM/SPY等）仍可正常获取。

### 运行脚本

```powershell
# 在项目根目录运行
python fetch_3years_data_auto.py
```

### 输出说明

脚本会：

1. **验证所有指标是否都能自动获取**
   - 检查是否有需要CSV导入的指标
   - 显示自动获取能力统计

2. **自动获取US市场数据**
   - 获取所有US主指标和观察者指标
   - 显示每个指标的获取状态和数据量

3. **自动获取CN市场数据**
   - 获取所有CN主指标和观察者指标
   - 显示每个指标的获取状态和数据量

4. **处理数据并填充数据库**
   - 数据转换
   - 评分计算
   - 确认层应用
   - 保存到数据库

5. **生成统计报告**
   - 成功/失败指标统计
   - 数据量统计
   - 数据库路径

## 📊 数据源映射

### US市场指标

| 指标代码 | 指标名称 | 数据源 | 符号/代码 |
|---------|---------|--------|----------|
| RRP_D20 | RRP 20日变动 | FRED | RRPONTSYD |
| TGA_D20 | TGA 20日变动 | FRED | WTREGEN |
| HY_OAS | 高收益债利差 | FRED | BAMLH0A0HYM2 |
| VIX_LOG | VIX对数 | yfinance | ^VIX |
| DFII10 | 10Y TIPS实际利率 | FRED | DFII10 |
| IWM_SPY_REL20 | IWM/SPY相对收益 | yfinance | IWM, SPY |
| HYG_IEF_SOFT | HYG/IEF相对强度 | yfinance | HYG, IEF |
| TWEX | Trade-Weighted USD | FRED | DTWEXBGS |
| DXY | 美元指数 | yfinance | DX-Y.NYB |
| CNH | 离岸人民币 | Stooq | CNH |
| CNY | 在岸人民币 | yfinance | CNY=X |

### CN市场指标

| 指标代码 | 指标名称 | 数据源 | 符号/代码 |
|---------|---------|--------|----------|
| CN_MARGIN_SLOPE | 两融余额斜率 | akshare | margin_sse |
| CNH_PCT20 | USD/CNH 20日%变动 | Stooq | CNH |
| NORTH_TURNOVER_SHARE | 北向成交额占比 | akshare | north_flow |
| CSI1000_OVER_300_REL20 | 中证1000/沪深300相对收益 | akshare | index:000852, index:000300 |
| PMI_NEWORDER_YOY_STD | PMI新订单同比标准化 | akshare | pmi_neworder |
| CN_EPS_YIELD_MINUS_CGB10 | 股债收益差 | akshare | eps_yield, bond_10y |
| ETF_NETFLOW_5D | ETF 5日净申赎 | akshare | etf_flow |
| CNY | USD/CNY | yfinance | CNY=X |

## ✅ 自动化覆盖率

### US市场：100% ✅

所有US市场指标都可以自动获取：
- FRED数据：需要API密钥（可选）
- yfinance数据：完全免费，无需密钥
- Stooq数据：完全免费，无需密钥

### CN市场：100% ✅

所有CN市场指标都可以自动获取：
- akshare数据：完全免费，无需密钥（底层使用东方财富API）
- yfinance数据：完全免费，无需密钥
- Stooq数据：完全免费，无需密钥

**注意**：akshare底层使用东方财富API，所以东方财富数据通过akshare获取，无需单独配置。

## 🔍 数据获取统计

脚本会显示每个指标的获取状态：

```
[FETCH] VIX_LOG (source: yfinance, symbol: ^VIX)
[OK] Fetched 1095 records for ^VIX
[OK] VIX_LOG: 1095 条记录 (2022-01-01 至 2025-01-01)

[FETCH] CN_MARGIN_SLOPE (source: akshare, symbol: margin_sse)
[OK] Fetched 726 records for margin trading
[OK] CN_MARGIN_SLOPE: 726 条记录 (2022-01-01 至 2025-01-01)
```

## ⚠️ 注意事项

1. **网络要求**：
   - 需要稳定的网络连接
   - 某些数据源可能有访问限制（如akshare）
   - 建议在网络稳定的环境下运行

2. **数据获取时间**：
   - 近三年数据获取可能需要10-30分钟
   - 取决于网络速度和数据源响应速度
   - akshare数据获取可能较慢（需要逐个指标获取）

3. **数据完整性**：
   - 脚本会检查数据量是否足够（至少50%的预期数据）
   - 如果某个指标获取失败，会显示错误信息
   - 部分指标缺失不影响其他指标的计算

4. **FRED API限制**：
   - 如果没有FRED API密钥，US市场的部分指标将无法获取
   - 但其他指标（VIX、IWM/SPY等）仍可正常获取
   - 建议申请免费的FRED API密钥：https://fred.stlouisfed.org/docs/api/api_key.html

5. **akshare更新**：
   - akshare接口可能不定期更新
   - 如果某个接口失效，可能需要更新akshare版本
   - 建议使用最新版本的akshare：`pip install --upgrade akshare`

## 🐛 故障排除

### 问题1：akshare数据获取失败
```
[ERROR] akshare is not available. Please install it first.
```
**解决方案**：
```powershell
pip install akshare
```

### 问题2：Stooq数据获取失败
```
[ERROR] pandas_datareader is not available
```
**解决方案**：
```powershell
pip install pandas-datareader
```

### 问题3：FRED数据获取失败
```
[ERROR] FRED not initialized. Check API key.
```
**解决方案**：
- 检查`.env`文件中是否配置了`FRED_API_KEY`
- 或申请免费的FRED API密钥：https://fred.stlouisfed.org/docs/api/api_key.html

### 问题4：yfinance数据获取失败
```
[ERROR] Failed to fetch ^VIX after 3 attempts
```
**解决方案**：
- 检查网络连接
- 更新yfinance：`pip install --upgrade yfinance`
- 某些数据源可能有访问限制，稍后重试

### 问题5：数据量不足
```
[WARNING] VIX_LOG 数据量偏少: 100 < 500
```
**解决方案**：
- 检查日期范围是否正确
- 某些数据源可能没有足够的历史数据
- 可以尝试调整日期范围

## 📈 后续步骤

数据获取完成后，您可以：

1. **查看数据库**：
   ```python
   from storage.repository import Repository
   repo = Repository('data/market_thermo_3years_auto.db')
   # 查询数据...
   ```

2. **运行GUI应用**：
   ```powershell
   python app.py
   ```

3. **进行数据分析**：
   - 使用pandas读取数据库数据
   - 进行自定义分析和可视化

## 📝 相关文档

- `demand.txt` - 完整的需求规格
- `docs/database_design.md` - 数据库设计文档
- `docs/data_flow_incremental.md` - 数据流说明
- `core/datasource.py` - 数据源实现
- `CN_MARKET_100_PERCENT_AUTOMATED.md` - CN市场100%自动化报告

