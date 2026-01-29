# NORTH_TURNOVER_SHARE 为0 的问题诊断和修复

## 问题现象

从2025年12月6日开始，`NORTH_TURNOVER_SHARE`（北向成交额占比）的 `value_tr` 字段全部变成了0。

## 诊断结果

### 数据库检查

```
- value_raw（北向成交额）：正常，有数据（如 4041.16 亿元）
- value_tr（成交额占比）：异常，全部为 0
- 最后正常日期：2025-12-05（占比：0.111652）
- 问题开始日期：2025-12-06（占比：0.000000）
```

### 根本原因

**全市场成交额获取失败** → 占比计算分母为0 → 结果为0

计算公式：
```
value_tr = 北向成交额 / (上证成交额 + 深证成交额)
```

当分母（全市场成交额）获取失败时，代码将其设为0，导致占比也是0。

### 网络连接问题

测试发现所有访问东方财富API的请求都失败：
- 主接口：`push2his.eastmoney.com` → Connection aborted
- 备用接口：`push2.eastmoney.com` → Connection aborted

可能原因：
1. 网络防火墙/代理限制
2. 东方财富API服务器问题
3. IP被限流

## 已实施的修复

### 代码修改位置

`core/datasource.py` 第511-540行

### 修复内容

添加了备用方案（fallback），当主接口失败时自动尝试备用接口：

```python
# 主方案：东方财富 push2his API
try:
    sh_turnover = _fetch_market_amount("1.000001")  # 上证指数
    sz_turnover = _fetch_market_amount("0.399001")  # 深证成指
    total_turnover = sh_turnover.add(sz_turnover, fill_value=0.0)
except Exception as market_exc:
    # 备用方案：akshare的stock_zh_index_daily_em
    sh_df = ak.stock_zh_index_daily_em(symbol="sh000001")
    # ...获取成交额...
```

## 当前状态

**修复已完成，但仍需解决网络连接问题**

由于网络限制，当前两个方案都无法访问东方财富API。

## 解决方法

### 方法1：检查网络连接（推荐）

1. 测试能否访问东方财富网站：
   ```
   https://www.eastmoney.com/
   ```

2. 如果无法访问，可能需要：
   - 关闭VPN/代理
   - 检查防火墙设置
   - 更换网络环境

3. 如果可以访问网站但API失败，可能是IP被限流，需要：
   - 等待一段时间
   - 更换IP地址

### 方法2：手动更新一次完整数据

由于`value_raw`（北向成交额）是正常的，只是`value_tr`（占比）为0，可以：

1. 使用GUI"手动获取最新数据"功能时，会自动应用备用方案
2. 一旦网络恢复，下次更新就会正常

### 方法3：使用历史占比均值（临时方案）

如果长期无法访问东方财富API，可以考虑：
- 使用历史平均占比（约0.12左右）
- 或使用最近一次有效占比进行前向填充

## 测试验证

### 诊断脚本

运行以下脚本检查数据库状态：
```bash
python check_north_data.py
```

### 测试网络连接

```bash
python test_fallback_only.py
```

如果看到类似输出说明网络正常：
```
[OK] 获取到 5 条记录
全市场成交额（上证+深证，亿元）:
  2026-01-26: 14518.60 亿元
```

如果看到 `Connection aborted` 说明网络有问题。

## 下次手动获取数据时

当你在GUI中点击"手动获取最新数据"时：

1. 如果网络正常：
   - 北向成交额会更新
   - 全市场成交额会通过备用方案获取
   - 占比会正常计算
   - `value_tr` 不再是0

2. 如果网络仍有问题：
   - 北向成交额会更新
   - 全市场成交额失败
   - 占比仍然是0
   - 控制台会显示警告信息

## 监控建议

在GUI或日志中留意以下消息：

✅ 正常：
```
[OK] Fetched market turnover from EastMoney push2 API
[OK] Fetched 5 records for north flow (DEAL_AMT + ratio)
```

⚠️ 使用备用方案：
```
[WARNING] Failed to fetch market turnover from EastMoney push2 API
[INFO] Trying fallback method using akshare...
[OK] Fallback successful: got 5 market turnover records
```

❌ 失败：
```
[WARNING] Failed to fetch market turnover from EastMoney push2 API
[ERROR] Fallback also failed
[WARNING] Setting total_turnover to 0 - NORTH_TURNOVER_SHARE ratio will be 0
```

## 长期解决方案考虑

如果东方财富API持续不稳定，可以考虑：

1. **增加更多备用数据源**：
   - tushare（需要积分）
   - 直接爬取交易所网站
   - 使用Wind/Bloomberg等付费数据源

2. **优化重试机制**：
   - 增加超时时间
   - 指数退避重试
   - 添加User-Agent轮换

3. **缓存策略**：
   - 如果当天获取失败，使用前一天占比估算

## 总结

- **问题**：全市场成交额获取失败导致占比为0
- **原因**：网络无法访问东方财富API
- **修复**：已添加备用方案，等待网络恢复即可自动修复
- **下一步**：检查网络连接，或等待下次更新时自动修复
