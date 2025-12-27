# 🎯 真正的问题找到了！

## 🔥 **根本原因**

GUI手动获取时，传递了`start_date`参数，导致pipeline.py中的增量逻辑被跳过！

### **代码流程**：

1. **GUI** (`ui/main_window.py` 第528-532行):
```python
MANUAL_FETCH_DAYS = 7
MANUAL_FETCH_BUFFER = 5  
MIN_MANUAL_FETCH_DAYS = 30  # ← 只有30天！

lookback_days = max(7+5, 30) = 30
start_dt = end_dt - timedelta(days=30)  # 往前30天

worker = ManualFetchWorker(
    start_date=start_dt,  # 传了start_date
    end_date=end_dt
)
```

2. **Pipeline** (`core/pipeline.py` 第268-273行):
```python
if incremental and not start_date:  # ← start_date不是None！
    # 这段永远不会执行
    start_date = last_date - timedelta(days=35)  
```

**结果**：
- 虽然改了pipeline.py为35天，但那段代码根本不执行！
- 实际还是用GUI传入的30天
- 30天不够计算relret20 → value_raw = None

---

## ✅ **已修复**

**文件**: `ui/main_window.py` 第248行

```python
# 修改前
MIN_MANUAL_FETCH_DAYS = 30

# 修改后
MIN_MANUAL_FETCH_DAYS = 50  # 确保有足够历史数据
```

---

## 🚀 **立即测试**

### **步骤1：删除问题数据**

```bash
python force_retest.py
```

### **步骤2：关闭并重启GUI**

**重要**：必须重启才能让ui/main_window.py的修改生效！

```bash
# 关闭当前GUI（Ctrl+C）
# 然后重新启动
python app.py
```

### **步骤3：手动获取数据**

在GUI中：
1. 选择US市场
2. 点击"手动获取最新数据"

### **步骤4：验证**

```bash
python quick_diagnosis.py
```

**应该看到**：
```
IWM_SPY_REL20 详细数据（最近5天）
日期          value_raw    value_tr     z            score
2025-12-26   0.001402     0.001402     xxxxx        xxxxx  ← 有值！
```

### **步骤5：计算评分**

在GUI中点击"计算评分"

---

## 📊 **为什么50天？**

- 50个日历日 ≈ 35个交易日（去掉周末和节假日）
- relret20需要20个交易日
- 留15个交易日缓冲
- 确保数据充足

---

## 🔍 **修改了哪些文件？**

1. ✅ `core/pipeline.py` 第272行：`timedelta(days=5)` → `timedelta(days=35)`
   - 但这个修改对GUI无效（因为GUI传了start_date）

2. ✅ `ui/main_window.py` 第248行：`MIN_MANUAL_FETCH_DAYS = 30` → `50`
   - **这个才是真正有效的修改！**

---

## 📝 **总结**

### **之前的误解**：
以为修改pipeline.py就够了，但没注意到GUI传了start_date参数。

### **真正的问题**：
GUI的`MIN_MANUAL_FETCH_DAYS = 30`天数不够。

### **解决方案**：
改为50天，确保有足够历史数据计算relret20。

---

**现在请关闭GUI，重新启动，手动获取数据！** 🚀

**这次应该彻底解决了！**

