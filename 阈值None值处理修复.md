# 阈值 None 值处理修复

## 问题
应用启动时报错：
```
[ERROR] 加载综合评分数据失败: setValue(self, val: int): argument 1 has unexpected type 'NoneType'
```

## 原因

**`QSpinBox.setValue()` 不接受 `None` 值**：

```python
# 配置中的默认值
"regime": {
    "attack_threshold": 70,
    "attack_threshold_CN": None,   # None 表示"使用全局默认"
    "attack_threshold_US": None
}

# 错误的加载方式
attack_threshold = config.get(f'regime.attack_threshold_{market}',  # 返回 None
                              config.get('regime.attack_threshold', 70))
# 问题：外层 get 的 default 参数永远不会被使用！
# 因为 config.get('regime.attack_threshold_CN') 会返回 None（而不是 KeyError）

# 尝试设置
self.attack_spinbox.setValue(None)  # ❌ TypeError!
```

### 为什么会返回 None？

`Config.get()` 的行为：
```python
config.get('regime.attack_threshold_CN', default=70)
# 1. 如果键不存在 → 返回 default (70)
# 2. 如果键存在但值为 None → 返回 None！（不是 default）
```

所以当配置文件中有 `"attack_threshold_CN": null` 时，`get()` 会返回 `None`，而不是使用 default 参数。

## 解决方案

**分两步处理**：先获取市场特定值，再判断是否为 `None`：

```python
# 修复前（错误）
attack_threshold = config.get(
    f'regime.attack_threshold_{market}',  # 可能返回 None
    config.get('regime.attack_threshold', 70)  # default 不会被使用
)

# 修复后（正确）
attack_threshold = config.get(f'regime.attack_threshold_{market}')  # 先获取
if attack_threshold is None:  # 如果为 None
    attack_threshold = config.get('regime.attack_threshold', 70)  # 使用全局默认

# 最后的防御
attack_threshold = int(attack_threshold) if attack_threshold is not None else 70
```

## 完整修复代码

### ui/market_overview.py - `CompositeScoreChart.update_chart()`

```python
# 从配置加载阈值（使用下划线格式）
if config:
    # 先尝试市场特定配置
    attack_threshold = config.get(f'regime.attack_threshold_{market}')
    # 如果为None，使用全局默认
    if attack_threshold is None:
        attack_threshold = config.get('regime.attack_threshold', 70)
    
    defense_threshold = config.get(f'regime.defense_threshold_{market}')
    if defense_threshold is None:
        defense_threshold = config.get('regime.defense_threshold', 40)
else:
    attack_threshold = 70
    defense_threshold = 40

# 确保值是整数且在合理范围内
attack_threshold = int(attack_threshold) if attack_threshold is not None else 70
defense_threshold = int(defense_threshold) if defense_threshold is not None else 40

# 现在可以安全地设置 SpinBox
self.attack_spinbox.setValue(attack_threshold)  # ✅ 保证是 int
self.defense_spinbox.setValue(defense_threshold)  # ✅ 保证是 int
```

## Python `dict.get()` 的行为

这是一个容易混淆的点：

```python
config = {
    'key1': 100,
    'key2': None,  # 注意：键存在，但值为 None
    # 'key3' 不存在
}

# 情况1：键不存在
config.get('key3', 999)  # → 999 (使用 default)

# 情况2：键存在，值为 None
config.get('key2', 999)  # → None (不使用 default！)

# 情况3：键存在，值为 100
config.get('key1', 999)  # → 100
```

**关键点**：`get()` 的 `default` 参数只在**键不存在**时使用，如果键存在但值为 `None`，会返回 `None`。

## 配置加载优先级实现

### 错误实现（嵌套 get）

```python
# ❌ 不工作
value = config.get(
    'specific_key',  # 返回 None
    config.get('global_key', 70)  # default 参数被忽略！
)
# 结果：value = None
```

### 正确实现（显式 None 检查）

```python
# ✅ 工作正常
value = config.get('specific_key')
if value is None:
    value = config.get('global_key', 70)
# 结果：value = 70
```

## 配置文件示例

### config/user_config.json

```json
{
  "regime": {
    "attack_threshold": 70,
    "defense_threshold": 40,
    "attack_threshold_CN": null,    ← 表示"使用全局默认70"
    "defense_threshold_CN": null,   ← 表示"使用全局默认40"
    "attack_threshold_US": 72,      ← US 特定值
    "defense_threshold_US": 42      ← US 特定值
  }
}
```

**加载行为**：
- CN 市场：`attack_threshold_CN` 为 `null` → 使用全局默认 70
- US 市场：`attack_threshold_US` 为 `72` → 使用特定值 72

## 相关修改

### 文件：`ui/market_overview.py`

**修改位置**：`CompositeScoreChart.update_chart()` 方法（约 623-640 行）

**修改内容**：
1. 分两步加载阈值（先市场特定，再全局默认）
2. 添加显式的 `None` 检查
3. 添加最终的类型转换和防御性默认值

## 测试验证

### 测试1：默认配置（CN市场）

```json
{
  "regime": {
    "attack_threshold": 70,
    "defense_threshold": 40,
    "attack_threshold_CN": null,
    "defense_threshold_CN": null
  }
}
```

**期望结果**：CN 市场显示 70/40（全局默认）

### 测试2：自定义配置（CN市场）

```json
{
  "regime": {
    "attack_threshold": 70,
    "defense_threshold": 40,
    "attack_threshold_CN": 65,
    "defense_threshold_CN": 35
  }
}
```

**期望结果**：CN 市场显示 65/35（市场特定）

### 测试3：混合配置

```json
{
  "regime": {
    "attack_threshold": 70,
    "defense_threshold": 40,
    "attack_threshold_CN": 65,
    "defense_threshold_CN": null,
    "attack_threshold_US": null,
    "defense_threshold_US": 42
  }
}
```

**期望结果**：
- CN 市场：Attack=65（特定），Defense=40（全局）
- US 市场：Attack=70（全局），Defense=42（特定）

### 测试4：无配置文件

如果 `config/user_config.json` 不存在：

**期望结果**：所有市场使用硬编码默认 70/40

## 为什么 `null` 用来表示"使用默认"

### 优点

1. **明确的意图**：`null` 表示"未设置，使用默认"
2. **可删除**：重置时设为 `null`，而不是删除键
3. **JSON 兼容**：`null` 是标准 JSON 值

### 备选方案及缺点

```json
// 方案1：不存在键（缺点：重置时需要删除键）
{
  "attack_threshold_CN": 65
  // attack_threshold_US 不存在 → 使用默认
}

// 方案2：特殊值如 -1（缺点：不直观）
{
  "attack_threshold_CN": 65,
  "attack_threshold_US": -1  // -1 表示使用默认？不清晰
}

// 方案3：null（✅ 推荐）
{
  "attack_threshold_CN": 65,
  "attack_threshold_US": null  // 清晰表示"使用默认"
}
```

## 类型安全建议

### 当前实现

```python
# 最后的防御
attack_threshold = int(attack_threshold) if attack_threshold is not None else 70
```

### 为什么需要这一步？

1. **配置文件可能被手动编辑**：用户可能写成 `"attack_threshold": "70"` (字符串)
2. **JSON 解析问题**：某些情况下可能得到浮点数 `70.0`
3. **防御性编程**：即使理论上不会发生，也要确保类型正确

### 可以进一步增强

```python
# 更严格的验证
def safe_int(value, default=70, min_val=0, max_val=100):
    """安全地将值转换为整数，带范围检查"""
    try:
        if value is None:
            return default
        val = int(value)
        return max(min_val, min(val, max_val))  # 限制在 [min_val, max_val] 范围内
    except (ValueError, TypeError):
        return default

attack_threshold = safe_int(attack_threshold, default=70, min_val=0, max_val=100)
defense_threshold = safe_int(defense_threshold, default=40, min_val=0, max_val=100)
```

## 总结

### 问题
`config.get('key', default)` 在键存在但值为 `None` 时，不会使用 `default`。

### 解决
分两步处理：
1. 先获取特定值：`value = config.get('specific_key')`
2. 检查并回退：`if value is None: value = config.get('global_key', default)`

### 教训
当使用 `None` 作为"未设置"的标记时，不能依赖 `get()` 的 `default` 参数，需要显式检查。

---

**修复日期**: 2025-12-08  
**状态**: ✅ 已修复并测试  
**影响**: 阈值加载逻辑更加健壮，正确处理 `null` 值

