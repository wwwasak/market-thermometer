# 市场概览启动错误修复

## 问题描述

启动 `python app.py` 时遇到错误：

```
KeyError: "None of ['date'] are in the columns"
```

## 原因分析

这个错误发生在首次启动时，数据库中还没有综合评分数据。新版本的代码尝试加载 `composite_score`，但数据库是在旧版本创建的，缺少相关数据。

## 已修复的问题

✅ **已在代码中添加完善的异常处理**

1. 添加了 try-except 块保护所有数据加载操作
2. 检查 DataFrame 是否为空以及列是否存在
3. 提供友好的错误提示信息
4. 确保在没有数据时 GUI 也能正常启动

## 现在可以正常启动

现在运行 `python app.py` 应该可以正常启动了。如果数据库中没有综合评分数据，你会看到提示信息：

- "暂无综合评分数据。请运行pipeline生成数据。"
- "数据库中没有composite_score字段。请运行最新的pipeline更新数据。"

## 如何生成综合评分数据

### 方法 1：使用 GUI（最简单）

1. 启动应用：`python app.py`
2. 在"指标图表"Tab中
3. 选择市场（CN 或 US）
4. 点击"手动获取最新数据"按钮
5. 等待数据更新完成（可能需要几分钟）
6. 切换到"市场概览"Tab 查看综合评分

### 方法 2：运行 Python 脚本

创建一个文件 `update_composite_scores.py`：

```python
from core.pipeline import MarketPipeline
from datetime import datetime, timedelta

# 设置日期范围
end_date = datetime.now()
start_date = end_date - timedelta(days=365)  # 最近1年

# 更新 US 市场
print("更新 US 市场...")
us_pipeline = MarketPipeline(
    market='US',
    database_url='sqlite:///data/market_thermo_3years_auto.db'
)
result = us_pipeline.run_daily_pipeline(start_date=start_date, end_date=end_date)
print(f"US 市场完成: {result}")

# 更新 CN 市场
print("\n更新 CN 市场...")
cn_pipeline = MarketPipeline(
    market='CN',
    database_url='sqlite:///data/market_thermo_3years_auto.db'
)
result = cn_pipeline.run_daily_pipeline(start_date=start_date, end_date=end_date)
print(f"CN 市场完成: {result}")

print("\n全部完成！现在可以在市场概览中查看综合评分了。")
```

然后运行：
```bash
python update_composite_scores.py
```

### 方法 3：使用现有的数据获取脚本

如果你有 `fetch_3years_data_auto.py` 或类似的脚本，运行它也会生成综合评分：

```bash
python fetch_3years_data_auto.py
```

## 验证修复

运行以下命令验证一切正常：

```bash
python test_market_overview.py
```

预期输出：
```
[OK] US Soft Confirm 权重验证通过!
[OK] CN权重配置正确
[SUCCESS] 所有测试通过!
```

## 更新摘要

### 修改的文件

- ✅ `ui/market_overview.py` - 添加完善的异常处理

### 主要改进

1. **数据加载保护**：所有数据库查询都包裹在 try-except 中
2. **空数据处理**：检查 DataFrame 是否为空以及列是否存在
3. **友好提示**：当数据缺失时显示清晰的提示信息
4. **初始化保护**：确保初始化时即使没有数据也不会崩溃

### 不需要修改的文件

- ❌ `core/pipeline.py` - 已经正确实现综合评分计算
- ❌ `storage/repository.py` - 数据库操作正常
- ❌ `ui/main_window.py` - 主窗口集成正常

## 下一步

1. ✅ 启动应用：`python app.py`
2. ✅ 使用 GUI 或脚本更新数据
3. ✅ 在"市场概览"Tab 查看综合评分和权重配置
4. ✅ 享受新功能！

## 常见问题

### Q: 为什么需要重新生成数据？

A: 因为综合评分功能是新加的。旧数据库中的 `regimes` 表虽然有记录，但 `composite_score` 字段是空的（NULL）。重新运行 pipeline 会填充这些数据。

### Q: 会覆盖原有数据吗？

A: 不会。pipeline 使用 `upsert` 操作，只会更新或插入记录，不会删除现有数据。

### Q: 需要重新获取所有数据吗？

A: 不需要。只需要重新计算评分和综合分数。原始数据（价格、指标值等）不需要重新获取。

### Q: 更新需要多长时间？

A: 取决于数据量：
- 最近 7 天：约 10-30 秒
- 最近 1 年：约 2-5 分钟
- 全部 3 年：约 5-10 分钟

## 技术细节

### 错误的根本原因

原始错误堆栈：
```python
composite_scores = regimes_df.set_index('date')['composite_score']
                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
KeyError: "None of ['date'] are in the columns"
```

这是因为：
1. `regimes_df` 可能为空
2. 或者 'date' 已经是索引而不是列

### 修复方案

```python
# 修复前（会崩溃）
composite_scores = regimes_df.set_index('date')['composite_score']

# 修复后（安全）
if regimes_df is not None and not regimes_df.empty:
    if 'date' in regimes_df.columns:
        regimes_df = regimes_df.set_index('date')
    
    if 'composite_score' in regimes_df.columns:
        composite_scores = regimes_df['composite_score']
        # ... 继续处理
```

## 支持

如果遇到其他问题，请检查：

1. Python 版本：推荐 3.11 或 3.12
2. 依赖包：运行 `pip install -r requirements.txt`
3. 数据库路径：确保 `data/market_thermo_3years_auto.db` 存在
4. 日志输出：查看终端输出的错误信息

祝使用愉快！🎉

