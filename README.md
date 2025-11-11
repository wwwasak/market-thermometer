# 双市场温度计 (Dual Market Thermometer)

> 🎉 **最新成就**: 18/18指标100%自动获取，0个CSV导入！

一个用于监测中国和美国股市温度的Python桌面应用程序，通过多维度指标分析提供市场状态评估和投资风格建议。

## 📋 功能特性

- **双市场独立监测**: 同时跟踪中国（CN）和美国（US）市场，各自独立评分
- **多指标综合评估**: 整合FRED、yfinance、Stooq、AKShare等多个数据源的关键市场指标
- **智能评分系统**: 基于Z分数和MAD-Z的稳健评分机制（0-100分）
- **三态市场判断**: Attack（进攻）/ Balanced（平衡）/ Defense（防御）
- **三色灯信号**: Green（绿）/ Yellow（黄）/ Red（红）快速判断
- **双时间维度**: 支持日线和周线视图切换
- **确认层机制**: 软确认（加权投票）+ 硬否决（持续性检查）
- **可视化图表**: matplotlib集成，直观展示指标和评分
- **灵活配置**: 支持参数调整、权重自定义、风格切换
- **数据持久化**: SQLite存储，支持历史数据回溯

## 🛠️ 技术栈

- **Python**: 3.11 或 3.12（推荐，3.13暂不兼容）
- **GUI框架**: PyQt6
- **图表库**: matplotlib、pyqtgraph（专业交互图表）
- **数据处理**: pandas, numpy, scipy
- **数据源**: yfinance, fredapi, pandas-datareader (Stooq), akshare
- **数据库**: SQLite + SQLAlchemy
- **配置管理**: python-dotenv

## 📦 安装步骤

### 方式A: 使用Anaconda（推荐）

#### 1. 克隆或下载项目

```powershell
git clone https://github.com/yourusername/market-thermometer.git
cd market-thermometer
```

#### 2. 创建conda环境

```powershell
# 使用environment.yml自动创建（推荐）
conda env create -f environment.yml

# 或手动创建
# conda create -n market-thermo python=3.11 -y
```

#### 3. 激活环境

```powershell
conda activate market-thermo
```

#### 4. 安装依赖（如果手动创建环境）

```powershell
pip install -r requirements.txt
```

**详细说明**: 参见 [SETUP_CONDA.md](SETUP_CONDA.md)

### 方式B: 使用venv（需要Python 3.11或3.12）

#### 1. 克隆或下载项目

```powershell
git clone https://github.com/yourusername/market-thermometer.git
cd market-thermometer
```

#### 2. 创建虚拟环境

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

#### 3. 安装依赖

```powershell
pip install -r requirements.txt
```

### 配置环境变量（两种方式都需要）

复制 `env.example` 为 `.env` 并填入必要的API密钥：

```powershell
Copy-Item env.example .env
```

编辑 `.env` 文件，至少需要配置：

```ini
FRED_API_KEY=your_actual_fred_api_key_here
```

> 💡 **获取FRED API Key**: 访问 [https://fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html) 注册并获取免费API密钥

## 🚀 快速开始

### 1. 获取样例数据库（可选）

```powershell
python fetch_3years_data_auto.py
```

脚本会在 `data/` 目录生成 `market_thermo_3years_auto.db`，自动抓取近三年的全部指标并写入数据库。

### 2. 启动现代化GUI终端

```powershell
# 使用配置中的默认数据库（core/config.py -> database.path）
python app.py

# 或者显式指定数据库文件
python app.py --database data/market_thermo_3years_auto.db
```

### 3. 操作要点

- **左侧控制面板**
  - 市场筛选：全部 / CN / US
  - 角色筛选：main / soft / hard / pair / component
  - 视图切换：日线 / 周线
  - 日期范围：默认展示近一年，可自定义区间并支持一键重置
  - 搜索框：输入代码或名称即可实时过滤
- **指标列表**
  - 单击选中即刻刷新右侧图表
  - 覆盖数据库中所有主指标、观察者及派生组件（含 `CN_EPS_YIELD`、`CN_BOND_10Y` 等）
- **右侧图表区域**
  - 股票软件常见交互：平移、缩放、复位（工具栏）+ 十字光标/悬浮提示
  - 双轴显示：左轴为原始/转换值，右轴为 Score，并附60/40阈值线
  - 支持导出PNG、自动格式化时间轴
- **状态栏**
  - 实时显示记录数、时间范围与最新灯色（Green / Yellow / Red）

## 📡 数据源说明

本项目整合了多个免费数据源，实现了**100%指标自动化获取**：

### 数据源列表

| 数据源 | 用途 | API密钥 | 覆盖市场 |
|-------|------|---------|---------|
| **FRED** | 美国宏观经济指标 | 需要（免费） | US |
| **yfinance** | 股票指数、ETF价格 | 不需要 | US + CN |
| **Stooq** (pandas-datareader) | 外汇数据（CNH/CNY） | 不需要 | CN配对 |
| **AKShare** | 中国市场专有数据 | 不需要 | CN |

### CN市场数据覆盖

- ✅ **自动获取**: 10/10 指标 (100%)
  - 两融余额、北向成交、股指、PMI、国债收益率、ETF流向等
  - **关键突破**: CNH（Stooq）+ CNY（yfinance）配对自动化
  - **新增**: 全A盈利收益率（akshare `stock_a_ttm_lyr`）+ 股债收益差派生
- 📋 **CSV导入**: 0个指标

### US市场数据覆盖

- ✅ **自动获取**: 10/10 指标 (100%)
  - FRED: 逆回购、TGA、通胀保值债、高收益债利差、贸易加权美元、金融条件指数
  - yfinance: VIX、IWM、SPY、HYG、IEF

详细配置请参考：[FINAL_INDICATOR_SOLUTION.md](FINAL_INDICATOR_SOLUTION.md)

## 📊 核心指标说明

### 中国市场（CN）主要指标

| 指标代码 | 名称 | 方向 | 说明 |
|---------|------|------|------|
| CN_MARGIN_SLOPE | 两融余额斜率 | 上升好 | 20/60日EWMA组合斜率 |
| CNH_PCT20 | CNH 20日变动% | 下降好 | 人民币贬值预警 |
| NORTH_TURNOVER_SHARE | 北向成交占比 | 上升好 | 外资活跃度 |
| CSI1000_OVER_300_REL20 | 小盘/大盘相对强度 | 上升好 | 风格轮动指标 |
| PMI_NEWORDER_YOY_STD | PMI新订单同比 | 上升好 | 经济景气度 |
| CN_EPS_YIELD_MINUS_CGB10 | 股债收益差 | 上升好 | 估值吸引力 |

### 美国市场（US）主要指标

| 指标代码 | 名称 | 方向 | 说明 |
|---------|------|------|------|
| RRP_D20 | RRP 20日变动 | 下降好 | 流动性释放信号 |
| TGA_D20 | TGA 20日变动 | 下降好 | 财政部资金流向 |
| HY_OAS | 高收益债利差 | 下降好 | 信用风险温度 |
| VIX_LOG | VIX波动率 | 下降好 | 恐慌情绪指标 |
| DFII10 | 10年TIPS实际利率 | 下降好 | 实际利率水平 |
| IWM_SPY_REL20 | 小盘/大盘相对强度 | 上升好 | 风险偏好指标 |

## 🎨 使用说明

### 界面概览

- **左侧控制面板**：集中完成市场/角色筛选、视图切换、日期范围设置与关键字搜索
- **指标列表**：列出数据库中可用的全部指标（含派生组件），单击即可刷新图表
- **右侧主图**：展示原始值（或转换值）+ Score 双轴折线，提供十字光标、阈值线与导出按钮
- **导航工具栏**：支持平移、缩放、复位、保存、十字光标开启/关闭等操作
- **状态栏**：实时显示数据覆盖范围、记录数量与最新灯色判定结果

### 常用操作流程

1. **载入指标**：左侧列表选择任意指标（如 `CN_MARGIN_SLOPE`、`RRP_D20`、`CN_EPS_YIELD_MINUS_CGB10`）
2. **切换视图**：通过“日线 / 周线”下拉框在不同时间粒度间切换
3. **限制日期**：调整开始/结束日期或使用“重置日期”快速回到最近一年
4. **多条件过滤**：结合市场、角色和搜索词定位目标指标
5. **分析图表**：使用导航工具栏缩放，移动鼠标观察十字光标提示，掌握原始值与Score走势
6. **导出图像**：点击右上角“导出PNG”保存当前图表

### Score / Lamp 判断

- **Score ≥ 70**：Attack（建议进攻配置）
- **40 ≤ Score < 70**：Balanced（维持中性）
- **Score < 40**：Defense（建议防御）
- 状态栏会根据最新 Score 自动提示灯色（Green / Yellow / Red）

## ⚙️ 高级配置

### 自定义参数

配置文件保存在数据库中，也可以导出为JSON格式编辑。

主要可配置项：

```json
{
  "regime": {
    "attack_threshold": 70,
    "defense_threshold": 40,
    "persistence_days": 3
  },
  "style_weights": {
    "CN": {
      "Attack": [24, 16, 12, 20, 16, 12],
      "Balanced": [20, 14, 12, 18, 18, 18],
      "Defense": [15, 10, 10, 12, 20, 33]
    }
  }
}
```

### 风格权重说明

三种预设风格的权重分配（以CN市场为例）：

- **Attack（进攻）**: 偏重动量和风险偏好指标
- **Balanced（平衡）**: 均衡配置各类指标
- **Defense（防御）**: 偏重估值和基本面指标

您可以在GUI中编辑权重表格来自定义。

## 🧪 测试

运行单元测试：

```powershell
# 测试所有模块
python -m pytest tests/ -v

# 测试特定模块
python -m pytest tests/test_transforms.py -v
python -m pytest tests/test_scoring.py -v
```

## 📁 项目结构

```
market-thermometer/
├── app.py                  # 主入口
├── core/                   # 核心逻辑模块
│   ├── config.py          # 配置管理
│   ├── datasource.py      # 数据获取
│   ├── transforms.py      # 数据转换
│   ├── scoring.py         # 评分计算
│   ├── combine.py         # 确认层逻辑
│   ├── pipeline.py        # 数据流水线
│   └── indicator_registry_reference.py
├── storage/               # 数据存储模块
│   ├── models.py         # 数据库模型
│   ├── repository.py     # 数据仓库
│   └── migrate.py        # 数据库迁移
├── ui/                    # 界面模块
│   ├── __init__.py
│   ├── main_window.py    # 主窗口与控制面板
│   ├── charts.py         # Matplotlib图表组件
│   └── styles.py         # 统一QSS风格
├── tests/                 # 测试模块
├── requirements.txt       # 依赖清单
├── env.example           # 环境变量模板
└── README.md             # 本文档
```

## 🔧 常见问题

### Q: 无法获取FRED数据？
**A**: 检查以下几点：
1. `.env` 文件中的 `FRED_API_KEY` 是否正确
2. 网络连接是否正常
3. 是否需要配置代理（在 `.env` 中设置 `HTTP_PROXY`）

### Q: CN市场数据缺失？
**A**: 中国市场的特有数据需要通过CSV导入：
- 准备好格式正确的CSV文件（date, value两列）
- 在界面中点击对应的"Import CSV"按钮
- 支持的日期格式：`YYYY-MM-DD` 或 `YYYY/MM/DD`

### Q: 图表显示不正常？
**A**: 尝试以下方法：
1. 检查数据是否完整（至少需要60-90个交易日）
2. 点击"Recompute Only"重新计算
3. 调整日期范围选择器

### Q: 性能较慢？
**A**: 优化建议：
1. 首次获取数据时选择较短的时间范围（如1年）
2. 增量更新而不是全量重新获取
3. 定期备份数据库并清理过旧数据

## 📝 开发计划

- [x] 阶段1: 项目初始化和基础配置 ✅
- [x] 阶段2: 核心转换和评分逻辑 ✅
- [x] 阶段3: 确认层逻辑 ✅
- [x] 阶段4: 数据存储层 ✅
- [x] 阶段5: 数据获取模块 ✅
- [x] 阶段6: 完整数据流水线 ✅
- [x] 阶段7: 基础GUI框架 ✅
- [x] 阶段8: 图表可视化 ✅
- [ ] 阶段9: 表格视图
- [ ] 阶段10: 视图切换
- [ ] 阶段11: 完整功能集成
- [ ] 阶段12: CN市场完整支持
- [ ] 阶段13: 高级功能和优化
- [ ] 阶段14: 最终测试和文档

**当前进度**: 8/14 阶段完成（57.1%）  
**测试覆盖**: 141个单元测试全部通过 ✅  
**代码统计**: ~9000行（核心+测试+文档）

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📧 联系方式

如有问题或建议，请通过以下方式联系：
- 提交GitHub Issue
- 发送邮件至：your.email@example.com

---

**免责声明**: 本工具仅用于技术分析和研究目的，不构成任何投资建议。投资有风险，决策需谨慎。
