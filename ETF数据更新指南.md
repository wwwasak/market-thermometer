# ETF数据更新指南

## 🎯 目标

将数据库中的旧ETF数据替换为新的A500 ETF数据。

---

## ⚡ 快速操作（推荐）

### **方案1：GUI增量更新（最简单）**

只更新最新数据，保留历史数据混用（不推荐，但最快）：

```powershell
# 1. 启动GUI
python app.py

# 2. 在GUI中：
#    - 点击"手动获取"按钮
#    - 等待获取完成
#    - 切换到CN市场
#    - 点击"计算评分"按钮

# 3. 完成！
```

**优点**：快速，无需删除旧数据  
**缺点**：新旧数据混用，评分可能不够准确

---

### **方案2：完全替换（推荐）**

删除所有旧ETF数据，重新获取3年历史数据：

#### **步骤1：删除旧数据**

创建临时脚本 `delete_etf_data.py`：

```python
"""删除旧的ETF_NETFLOW_5D数据"""
import sqlite3
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = "data/market_thermo_3years_auto.db"

print("=" * 80)
print("删除旧的ETF_NETFLOW_5D数据")
print("=" * 80)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

try:
    # 获取series_id
    cursor.execute("""
        SELECT id FROM series_meta 
        WHERE code = 'ETF_NETFLOW_5D' AND market = 'CN'
    """)
    result = cursor.fetchone()
    
    if result is None:
        print("✗ 找不到ETF_NETFLOW_5D指标")
        sys.exit(1)
    
    series_id = result[0]
    print(f"[INFO] ETF_NETFLOW_5D的series_id = {series_id}")
    
    # 统计要删除的数据
    cursor.execute("""
        SELECT COUNT(*), MIN(date), MAX(date)
        FROM series_data
        WHERE series_id = ?
    """, (series_id,))
    count, min_date, max_date = cursor.fetchone()
    
    print(f"\n[待删除数据]")
    print(f"  记录数: {count}")
    print(f"  日期范围: {min_date} ~ {max_date}")
    
    # 确认
    confirm = input("\n确认删除？(yes/no): ").strip().lower()
    if confirm != 'yes':
        print("已取消")
        sys.exit(0)
    
    # 删除series_data
    cursor.execute("DELETE FROM series_data WHERE series_id = ?", (series_id,))
    deleted_series = cursor.rowcount
    
    # 删除regimes（如果有相关记录）
    cursor.execute("""
        DELETE FROM regimes 
        WHERE market = 'CN' 
        AND date IN (
            SELECT DISTINCT date 
            FROM series_data 
            WHERE series_id = ?
        )
    """, (series_id,))
    deleted_regimes = cursor.rowcount
    
    conn.commit()
    
    print(f"\n[完成]")
    print(f"  ✓ 删除series_data: {deleted_series} 条")
    print(f"  ✓ 删除regimes: {deleted_regimes} 条")
    print("\n下一步：运行 python fetch_3years_data_auto.py --market CN")
    
except Exception as e:
    print(f"\n✗ 删除失败: {e}")
    conn.rollback()
    sys.exit(1)
finally:
    conn.close()
```

运行：
```powershell
python delete_etf_data.py
```

#### **步骤2：重新获取3年数据**

```powershell
python fetch_3years_data_auto.py --market CN
```

等待完成（可能需要几分钟）。

#### **步骤3：在GUI中计算评分**

```powershell
# 1. 启动GUI
python app.py

# 2. 在GUI中：
#    - 切换到CN市场
#    - 点击"计算评分"按钮
#    - 等待评分计算完成

# 3. 完成！查看ETF_NETFLOW_5D的新数据
```

**优点**：数据一致性好，评分准确  
**缺点**：需要重新下载3年数据，耗时较长

---

## 🔍 验证新数据

### 在GUI中验证：

1. **打开GUI**：`python app.py`
2. **切换到CN市场**
3. **查看ETF_NETFLOW_5D指标**：
   - 左侧指标列表中选择"宽基ETF 5日净申赎"
   - 查看右侧图表和数据

### 预期结果：

- ✅ 数据日期更新到最新
- ✅ 数值范围：-100 ~ 300 亿元左右
- ✅ 最近一周应显示资金流入趋势（正值）
- ✅ 确认层状态中"Hard Veto"应该是绿灯（如果评分>60）

---

## 📊 数据对比示例

### 旧数据特征：
- 来源：510300/510500/159915的主力净流入
- 范围：通常 -50 ~ 150 亿元

### 新数据特征：
- 来源：5只A500 ETF的带方向成交额
- 范围：通常 -100 ~ 300 亿元
- 更大的波动范围（反映了更广泛的市场参与）

---

## ❓ 常见问题

### Q1: 为什么要替换数据源？

**A:** 
- 旧数据使用"主力净流入"，定义模糊，数据不稳定
- 新数据使用"成交额×sign(涨跌幅)"，更客观、可靠
- A500指数覆盖更全面，代表性更好

### Q2: 必须删除旧数据吗？

**A:** 
- 不是必须的，但**强烈推荐**
- 新旧数据混用可能导致评分不准确
- 数据来源不同，数值范围也不同

### Q3: 数据获取失败怎么办？

**A:** 
- 检查网络连接
- 确认akshare版本是最新的：`pip install --upgrade akshare`
- 某些ETF可能暂时无法获取，会自动跳过
- 至少需要成功获取3只ETF（总权重>50%）才能计算

### Q4: 历史数据不完整怎么办？

**A:** 
- A500 ETF是2024年新推出的，早期数据可能不完整
- 如果某天数据缺失，会自动使用forward fill填充评分
- 这不影响最新数据的准确性

---

## 🔧 故障排查

### 问题1：删除脚本报错

```
✗ 找不到ETF_NETFLOW_5D指标
```

**解决**：数据库路径错误，检查 `DB_PATH` 是否指向正确的数据库文件。

---

### 问题2：fetch_3years_data_auto.py获取失败

```
[ERROR] Failed to fetch ETF flow data
```

**解决**：
1. 检查网络连接
2. 更新akshare：`pip install --upgrade akshare`
3. 如果仍失败，尝试只获取最近90天：
   ```powershell
   python fetch_a500_etf_turnover.py --days 90 --execute
   ```

---

### 问题3：GUI中看不到新数据

**解决**：
1. 确认数据已保存到数据库（检查 `fetch_3years_data_auto.py` 输出）
2. 在GUI中点击"计算评分"按钮
3. 完全关闭并重新打开GUI
4. 结束所有python.exe进程后重新启动

---

## 📝 检查清单

更新完成后，请确认：

- [ ] GUI中能看到ETF_NETFLOW_5D的最新数据
- [ ] 数据日期是最近的交易日
- [ ] 数值范围合理（-100 ~ 300 亿元左右）
- [ ] 确认层状态正常显示（绿色/黄色/红色）
- [ ] 评分计算正常（有score值）
- [ ] 复合评分图表正常显示

---

## ✅ 完成

恭喜！您已成功将ETF数据源切换到新的A500 ETF逻辑。

**现在系统会自动在所有场景中使用新数据源！**

