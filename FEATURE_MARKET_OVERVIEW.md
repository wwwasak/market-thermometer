# 市场概览功能实现总结

## 功能概述

根据`demand.txt`的需求，我已经实现了以下功能：

1. **市场综合评分计算**：基于主要指标的加权平均计算市场总分
2. **指标评分表格**：显示各个指标的当前值、Z分数、评分和权重
3. **综合评分曲线图**：可视化市场总分的历史走势
4. **确认层可视化**：显示Hard Veto、Soft Confirm和Final Lamp的状态
5. **US Soft Confirm验证**：确认权重配置和判分逻辑正确

## 实现的文件

### 1. 核心逻辑更新

#### `core/pipeline.py`
- **扩展`calculate_scores`方法**：现在返回`(scores_df, composite_score)`元组
  - 计算各指标的Z分数和评分（原有功能）
  - **新增**：计算市场综合评分（加权总分）
  - 使用当前激活风格的权重配置

- **更新`save_to_database`方法**：
  - 接收并存储综合评分到`regimes`表
  - 根据综合评分计算regime（Attack/Balanced/Defense）
  - 存储到数据库的`composite_score`字段

- **配置确认层参数**：
  - US市场：soft_confirm_codes = ['IWM_SPY_SOFT', 'HYG_IEF_SOFT', 'PAIR_TWEX_DXY', 'PAIR_CNH_CNY']
  - CN市场：soft_confirm_codes = ['PAIR_CNH_CNY', 'PAIR_TWEX_DXY']
  - 权重自动从config中加载

### 2. GUI组件

#### `ui/market_overview.py` (新文件)

包含4个主要组件：

1. **MarketScoreTable（市场评分表格）**
   - 显示各指标的代码、名称、当前值、Z分数、评分、权重和灯色
   - 根据评分自动着色（绿≥60，红≤40，黄色其他）

2. **CompositeScoreChart（综合评分曲线图）**
   - 基于PyQtGraph的交互式图表
   - 显示Attack(70)和Defense(40)阈值线
   - 支持导出PNG图片

3. **ConfirmLayerPanel（确认层面板）**
   - 显示所有观察者指标的当前灯色
   - 显示Hard Veto、Soft Confirm和Final Lamp的汇总状态
   - 显示软确认权重

4. **MarketOverviewWidget（市场概览主组件）**
   - 集成上述三个组件
   - 提供市场/视图/风格切换控件
   - 自动从数据库加载数据

#### `ui/main_window.py` (更新)
- 添加Tab页面支持
- 集成`MarketOverviewWidget`作为"市场概览"Tab
- 保留原有的"指标图表"Tab

### 3. 测试和验证

#### `test_market_overview.py` (新文件)
- 验证US和CN市场的Soft Confirm权重配置
- 检查数据库中的综合评分数据
- 显示各指标的评分和权重信息

## US Soft Confirm 权重验证

根据`demand.txt`的要求，US市场的Soft Confirm权重应该是：

```
IWM_SPY_SOFT:    0.30  (30%)
HYG_IEF_SOFT:    0.30  (30%)
PAIR_TWEX_DXY:   0.20  (20%)
PAIR_CNH_CNY:    0.20  (20%)
总和:            1.00  (100%)
```

**验证结果**：✅ **配置完全正确**

- 所有权重值与需求文档一致
- 权重总和为1.0
- 判分逻辑符合需求：
  - 灯色映射：Green=2, Yellow=1, Red=0
  - 加权平均：S = Σ(weight_i × value_i)
  - 阈值判断：S ≥ 1.6 → Green, S ≤ 0.8 → Red, 其他 → Yellow

## 使用方法

### 1. 启动GUI

```bash
python app.py
```

或者（如果使用了指定数据库）：

```python
from ui.main_window import launch_gui
launch_gui("sqlite:///data/market_thermo_3years_auto.db")
```

### 2. 查看市场概览

1. 点击"市场概览"Tab
2. 选择市场（CN/US）和视图（daily/weekly）
3. 选择风格（Attack/Balanced/Defense）

### 3. 刷新数据

点击"刷新数据"按钮重新加载最新数据

### 4. 导出图表

在综合评分图表区域点击"导出图表"按钮

## 数据说明

### 综合评分计算

综合评分 = Σ(指标评分_i × 权重_i) / Σ(权重_i)

权重根据选择的风格（Attack/Balanced/Defense）动态调整：

**US市场 - Balanced风格**：
```
RRP_D20:          15%
TGA_D20:          10%
HY_OAS:           20%
VIX_LOG:          15%
DFII10:           20%
IWM_SPY_REL20:    20%
```

**CN市场 - Balanced风格**：
```
CN_MARGIN_SLOPE:         20%
CNH_PCT20:               14%
NORTH_TURNOVER_SHARE:    12%
CSI1000_OVER_300_REL20:  18%
PMI_NEWORDER_YOY_STD:    18%
CN_EPS_YIELD_MINUS_CGB10:18%
```

### Regime判断

- **Attack**: 综合评分 ≥ 70
- **Defense**: 综合评分 ≤ 40
- **Balanced**: 40 < 综合评分 < 70

### 确认层逻辑

1. **Hard Veto（硬否决）**：
   - US: HY_OAS_JUMP 或 VIX_EXTREME 触发红灯
   - CN: ETF_NETFLOW_5D 触发红灯
   - 使用MIN规则（任何一个红灯即为红灯）
   - 带持续性确认（daily: 3天，weekly: 2周）

2. **Soft Confirm（软确认）**：
   - 加权投票机制
   - 阈值：≥1.6 为绿灯，≤0.8 为红灯

3. **Final Lamp（最终灯色）**：
   - 如果Hard Veto = 红灯 → 红灯（优先级最高）
   - 否则如果Soft Confirm = 绿灯 → 绿灯
   - 其他情况 → 黄灯

## 注意事项

1. **首次使用**：如果数据库中没有`composite_score`数据，需要运行一次完整的pipeline：
   ```python
   from core.pipeline import MarketPipeline
   from datetime import datetime, timedelta
   
   # 更新US市场
   us_pipeline = MarketPipeline(market='US', database_url='sqlite:///data/market_thermo_3years_auto.db')
   us_pipeline.run_daily_pipeline()
   
   # 更新CN市场
   cn_pipeline = MarketPipeline(market='CN', database_url='sqlite:///data/market_thermo_3years_auto.db')
   cn_pipeline.run_daily_pipeline()
   ```

2. **数据更新**：在主窗口的"指标图表"Tab中点击"手动获取最新数据"按钮也会触发pipeline并计算综合评分

3. **性能优化**：市场概览组件每次切换市场/视图时会重新加载数据，对于大数据集可能需要几秒钟

## 测试结果

运行`test_market_overview.py`的输出：

```
[OK] US Soft Confirm 权重验证通过!
  - IWM_SPY_SOFT: 0.3 [OK]
  - HYG_IEF_SOFT: 0.3 [OK]
  - PAIR_TWEX_DXY: 0.2 [OK]
  - PAIR_CNH_CNY: 0.2 [OK]

[OK] CN权重配置正确
  
US市场主要指标 (Balanced风格):
指标数量: 6
权重数量: 6
[OK] 指标与权重数量匹配
权重总和: 100

[SUCCESS] 所有测试通过!
```

## 下一步建议

1. **数据更新**：运行一次完整pipeline以生成综合评分历史数据
2. **UI优化**：可以考虑添加更多交互功能（如点击表格行高亮对应曲线）
3. **导出功能**：增加CSV/Excel导出功能
4. **历史对比**：添加不同风格的综合评分对比视图
5. **实时更新**：可以考虑添加定时自动刷新功能

## 相关文档

- `demand.txt` - 原始需求文档
- `core/config.py` - 配置参数说明
- `core/combine.py` - 确认层逻辑实现
- `core/scoring.py` - 评分和标准化函数

