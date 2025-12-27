"""
强制重新测试：完全独立的流程

1. 删除12月26日数据
2. 模拟增量获取（使用修改后的代码）
3. 检查结果
"""

import sys
import sqlite3
from datetime import datetime
import pandas as pd

print("=" * 80)
print("强制重新测试")
print("=" * 80)
print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# 步骤1: 删除12月26日数据
print("步骤1: 删除12月26日的US数据")
print("-" * 80)

conn = sqlite3.connect('data/market_thermo_3years_auto.db')
cursor = conn.cursor()

cursor.execute("""
    DELETE FROM series_data
    WHERE series_id IN (SELECT id FROM series_meta WHERE market = 'US')
    AND date = '2025-12-26'
    AND view = 'daily'
""")

deleted = cursor.rowcount
conn.commit()
print(f"[OK] 删除了 {deleted} 条记录\n")

conn.close()

# 步骤2: 检查当前代码配置
print("步骤2: 检查pipeline.py配置")
print("-" * 80)

with open('core/pipeline.py', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f, 1):
        if 'timedelta(days=' in line and 'last_date' in line:
            print(f"第{i}行: {line.strip()}")
            if 'days=35' in line:
                print("[OK] 代码已修改为35天\n")
            else:
                print("[ERROR] 代码还是旧版本\n")
            break

# 步骤3: 提示用户操作
print("步骤3: 下一步操作")
print("-" * 80)

print("""
请按照以下步骤操作：

1. 完全关闭当前运行的GUI
   - 按 Ctrl+C
   - 或直接关闭终端窗口

2. 打开新的终端窗口

3. 激活环境并运行GUI:
   conda activate market-thermo
   python app.py

4. 在GUI中:
   - 选择US市场
   - 点击"手动获取最新数据"

5. 观察控制台输出，确认看到：
   [INFO] 增量更新模式，从 2025-11-22 开始  ← 应该是11月22日左右
   （而不是 2025-12-22）

6. 获取完成后，运行验证:
   python quick_diagnosis.py

7. 如果IWM_SPY_REL20的12月26日还是None，
   请将控制台的完整输出发给我。
""")

print("=" * 80)
print("准备工作完成！")
print("=" * 80)
print("\n数据已删除，代码已确认。")
print("现在请关闭GUI，重新启动，然后获取数据。")

