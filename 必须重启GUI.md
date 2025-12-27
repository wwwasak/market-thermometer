# ⚠️ 重要：必须重启GUI才能生效！

## 📌 **当前状态**

✅ **代码已修改**：`pipeline.py` 第272行已改为 `timedelta(days=35)`
✅ **数据已删除**：12月26日的4条问题记录已删除
❌ **GUI还在使用旧代码**：因为Python进程没有重启

---

## 🚀 **立即操作步骤**

### **步骤1：完全关闭GUI**

如果GUI还在运行：
1. 按 `Ctrl + C`
2. 或直接关闭终端窗口

**重要**：必须完全关闭Python进程！

---

### **步骤2：打开新的终端**

1. 打开新的PowerShell或CMD窗口
2. 切换到项目目录：
   ```bash
   cd D:\code\MyCode\market-thermometer
   ```
3. 激活环境：
   ```bash
   conda activate market-thermo
   ```

---

### **步骤3：启动GUI**

```bash
python app.py
```

---

### **步骤4：手动获取数据**

在GUI中：
1. 选择 **US市场**
2. 点击 **"手动获取最新数据"**

---

### **步骤5：观察控制台输出**

**关键**：确认看到以下输出：

```
[INFO] 增量更新模式，从 2025-11-22 开始  ← 注意这个日期！
```

**如果看到**：
- ✅ `从 2025-11-22 开始` 或更早 → 代码生效了，往前拿了35天
- ❌ `从 2025-12-22 开始` → 还是5天，代码没生效

**还应该看到**：
```
[OK] Fetched XX records for IWM   ← 应该有20-30条
[OK] Fetched XX records for SPY   ← 应该有20-30条
[INFO] IWM_SPY_REL20: 新数据计算得到XX个relret20值
[OK] IWM_SPY_REL20: 保存 XX 条记录
```

---

### **步骤6：验证数据**

在PowerShell中运行：
```bash
python quick_diagnosis.py
```

**预期结果**：
```
IWM_SPY_REL20 详细数据（最近5天）
日期          value_raw    value_tr     z            score
2025-12-26   0.001402     0.001402     xxxxx        xxxxx  ← 有值！
2025-12-24   0.008386     0.008386     0.191232     51.91
```

---

### **步骤7：计算评分**

在GUI中点击 **"计算评分"**

---

## 🔍 **如果还是不行**

如果按照上面的步骤，IWM_SPY_REL20的12月26日还是None，请：

1. 在控制台查找这行：
   ```
   [INFO] 增量更新模式，从 XXXX-XX-XX 开始
   ```
   告诉我这个日期是什么

2. 查找这几行：
   ```
   [OK] Fetched XX records for IWM
   [OK] Fetched XX records for SPY
   ```
   告诉我获取了多少条

3. 运行这个测试：
   ```bash
   python test_project_datasource.py
   ```
   将输出发给我

---

## 📝 **为什么必须重启GUI？**

Python的模块导入是**缓存**的：
- 第一次 `import core.pipeline` 时，Python会读取并缓存代码
- 即使你修改了 `pipeline.py` 文件
- 已经运行的Python进程**不会自动重新读取**
- 必须**完全关闭进程**，重新启动才能加载新代码

---

## ✅ **成功的标志**

1. ✅ 控制台显示 `从 2025-11-22 开始`（或更早）
2. ✅ `quick_diagnosis.py` 显示IWM_SPY_REL20的12月26日有`value_raw`
3. ✅ VIX_LOG的12月26日有`value_tr`
4. ✅ GUI评分表显示所有指标

---

**现在请按照步骤1-7操作，关闭GUI并重新启动！** 🚀

