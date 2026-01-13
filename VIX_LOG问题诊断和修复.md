# VIX_LOG 问题诊断和修复报告

## 📊 **问题描述**

用户报告：
- 评分时VIX_LOG使用的不是最新的值
- VIX_LOG图表没有包含最新数据的曲线
- 怀疑有raw值但没有tr值

## 🔍 **诊断过程**

### 1. 数据库检查

发现有两个数据库文件：
- `data/market_thermometer.db` - **空数据库**（GUI默认使用）
- `data/market_thermo_3years_auto.db` - **有数据**（fetch 3年脚本创建）

### 2. VIX_LOG数据分析

在 `market_thermo_3years_auto.db` 中发现：

**问题前：**
```
VIX_LOG: 754条记录
最新数据:
  2026-01-08  Raw: 15.4500  TR: NULL  ← 问题！
  2026-01-07  Raw: 15.3800  TR: NULL  ← 问题！
  2026-01-06  Raw: 14.7500  TR: NULL  ← 问题！
  2026-01-05  Raw: 14.9000  TR: NULL  ← 问题！
  2026-01-02  Raw: 14.5100  TR: 2.6748  ✓ 正常
```

### 3. 转换测试

测试 `log_winsor` 转换函数：
```python
transform_log_winsor(raw_series)
```

**结果：转换完全正常！**
```
2026-01-08: Raw=15.4500 -> TR=2.7376
2026-01-07: Raw=15.3800 -> TR=2.7331
2026-01-06: Raw=14.7500 -> TR=2.6912
2026-01-05: Raw=14.9000 -> TR=2.7014
2026-01-02: Raw=14.5100 -> TR=2.6748
```

### 4. 根源分析

**转换逻辑正常**，问题出在保存环节：
- 在某次增量更新或评分计算时，最近4天的TR值没有被正确保存到数据库
- 可能是某个操作只更新了raw值，而没有更新TR值

## ✅ **修复方案**

### 执行的修复

运行了 `fix_vix_tr_values.py` 脚本：
1. 从数据库加载所有VIX_LOG的raw数据
2. 重新应用 `log_winsor` 转换
3. 识别缺失TR值的记录（4条）
4. 更新数据库中的TR值

**修复后：**
```
VIX_LOG: 754条记录
最新数据:
  2026-01-08  Raw: 15.4500  TR: 2.7376  ✓
  2026-01-07  Raw: 15.3800  TR: 2.7331  ✓
  2026-01-06  Raw: 14.7500  TR: 2.6912  ✓
  2026-01-05  Raw: 14.9000  TR: 2.7014  ✓
  2026-01-02  Raw: 14.5100  TR: 2.6748  ✓
```

## 🎯 **用户操作指南**

### 问题：GUI可能使用错误的数据库

GUI默认配置：
```python
db_path = self.config.get("database.path", "market_thermo.db")
```

但你的数据在 `market_thermo_3years_auto.db`！

### 解决方案（3选1）

#### 方案1：启动GUI时指定数据库 ⭐ 推荐

```powershell
python app.py --database data/market_thermo_3years_auto.db
```

#### 方案2：修改配置文件

在 `config/user_config.json` 中添加或修改：
```json
{
  "database": {
    "path": "sqlite:///data/market_thermo_3years_auto.db"
  },
  ...
}
```

#### 方案3：重命名数据库

```powershell
# 备份旧的空数据库
mv data/market_thermometer.db data/market_thermometer_backup.db

# 复制有数据的数据库
cp data/market_thermo_3years_auto.db data/market_thermo.db
```

## 📝 **验证步骤**

修复后，请执行以下步骤验证：

### 1. 检查数据库

```powershell
python check_all_databases.py
```

应该看到：
```
VIX_LOG  754条  最新:2026-01-08  TR:OK
```

### 2. 启动GUI

```powershell
python app.py --database data/market_thermo_3years_auto.db
```

### 3. 查看VIX_LOG

在GUI中：
- 选择US市场
- 点击VIX_LOG指标
- 确认图表显示最新数据（2026-01-08）
- 确认评分使用最新值

### 4. 测试评分计算

在GUI中：
- 点击"计算评分"按钮
- 查看US市场评分
- VIX_LOG应该使用最新的转换值进行评分

## 🔧 **预防措施**

为避免将来再次出现此问题：

### 1. 确保一致使用同一数据库

不要同时使用多个数据库文件，选择一个作为主数据库。

### 2. 增量更新后验证

每次GUI手动获取数据后，检查关键指标：
```sql
SELECT date, value_raw, value_tr 
FROM series_data 
WHERE series_id = (SELECT id FROM series_meta WHERE code = 'VIX_LOG')
ORDER BY date DESC 
LIMIT 5;
```

### 3. 监控日志

查看 `fetch_log` 表，确保数据获取和保存都成功。

## 📊 **技术细节**

### VIX_LOG 配置

```json
{
  "code": "VIX_LOG",
  "name": "VIX (log & winsor)",
  "direction": "down_good",
  "transform": "log_winsor",
  "z_type": "MADZ",
  "z_window": 40,
  "source": "yfinance",
  "ticker": "^VIX"
}
```

### log_winsor 转换

转换步骤：
1. 对数变换：`log(x)`
2. Winsorize截尾：将极端值截尾到2%和98%百分位

### 保存逻辑

`save_raw_data_only` 和 `save_to_database` 都会保存：
- `value_raw`：原始值
- `value_tr`：转换值
- `z`：Z分数（仅评分时）
- `score`：评分（仅评分时）

## 🎉 **总结**

✅ **问题已修复！** VIX_LOG的缺失TR值已补全。

⚠️ **关键**：确保GUI使用正确的数据库（`market_thermo_3years_auto.db`）。

📌 **建议**：使用方案1启动GUI，避免配置混淆。

