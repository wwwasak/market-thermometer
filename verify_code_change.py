"""
验证当前pipeline.py中的代码是否已修改
"""

import re

# 读取pipeline.py
with open('core/pipeline.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 查找关键行
pattern = r'start_date = last_date - timedelta\(days=(\d+)\)'
matches = re.findall(pattern, content)

print("=" * 80)
print("验证core/pipeline.py中的增量获取天数设置")
print("=" * 80)

if matches:
    print(f"\n找到 {len(matches)} 处 timedelta(days=X) 设置:\n")
    for i, days in enumerate(matches, 1):
        status = "✓ 已修改" if days == "35" else "✗ 未修改"
        print(f"{i}. timedelta(days={days}) {status}")
    
    # 检查是否都是35
    if all(d == "35" for d in matches):
        print("\n[OK] 代码已正确修改为35天")
    elif any(d == "5" for d in matches):
        print("\n[ERROR] 代码还是5天，修改可能未保存或未生效")
    else:
        print(f"\n[WARN] 天数是 {matches[0]}，需要确认")
else:
    print("\n[ERROR] 未找到相关代码")

# 查找具体的行号和上下文
print("\n" + "=" * 80)
print("查找具体代码位置")
print("=" * 80)

lines = content.split('\n')
for i, line in enumerate(lines, 1):
    if 'timedelta(days=' in line and 'last_date' in line:
        print(f"\n第 {i} 行:")
        # 显示上下3行
        start = max(0, i-3)
        end = min(len(lines), i+2)
        for j in range(start, end):
            prefix = ">>> " if j == i-1 else "    "
            print(f"{prefix}{j+1:4d} | {lines[j]}")

print("\n" + "=" * 80)
print("结论")
print("=" * 80)

if matches and matches[0] == "35":
    print("\n✓ 代码已修改为35天")
    print("\n如果GUI还是获取5天数据，请：")
    print("  1. 完全关闭GUI（Ctrl+C或关闭窗口）")
    print("  2. 关闭所有Python进程")
    print("  3. 重新打开终端")
    print("  4. 重新运行: python app.py")
elif matches and matches[0] == "5":
    print("\n✗ 代码还是5天，需要重新修改")
    print("\n请打开 core/pipeline.py，找到第272行左右，")
    print("将 timedelta(days=5) 改为 timedelta(days=35)")
else:
    print("\n? 无法确定状态，请手动检查 core/pipeline.py")

