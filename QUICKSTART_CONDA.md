# 🚀 快速开始 - Anaconda环境设置

## 最简单的方式

在项目根目录打开 **Anaconda Prompt** 或 **PowerShell**，运行：

```powershell
# 方式1: 使用自动化脚本（推荐）
.\setup_env.ps1

# 方式2: 使用environment.yml
conda env create -f environment.yml
conda activate market-thermo

# 方式3: 手动创建
conda create -n market-thermo python=3.11 -y
conda activate market-thermo
pip install -r requirements.txt
```

## 详细步骤

### 第一步：创建环境

```powershell
# 推荐使用 Python 3.11
conda create -n market-thermo python=3.11 -y
```

### 第二步：激活环境

```powershell
conda activate market-thermo
```

激活后，命令提示符会变成：
```
(market-thermo) PS D:\code\MyCode\market-thermometer>
```

### 第三步：安装依赖

```powershell
pip install -r requirements.txt
```

如果速度慢，使用清华镜像：
```powershell
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 第四步：验证安装

```powershell
# 检查Python版本
python --version

# 运行测试
python test_config_simple.py
```

## 在Cursor/VSCode中使用

### 1. 选择解释器

- 按 `Ctrl+Shift+P`
- 输入 "Python: Select Interpreter"
- 选择 `market-thermo` 环境

### 2. 打开终端

- 打开新终端，会自动激活 `market-thermo` 环境
- 如果没有自动激活，手动运行：
  ```powershell
  conda activate market-thermo
  ```

## 常见问题

### Q: 提示需要接受服务条款（Terms of Service）

**A**: 新版 Anaconda 需要先接受服务条款：
```powershell
# 接受服务条款
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/msys2

# 然后继续创建环境
conda create -n market-thermo python=3.11 -y
```

或使用开源频道（无需TOS）：
```powershell
conda create -n market-thermo python=3.11 -c conda-forge -y
```

### Q: 提示 "conda 不是内部或外部命令"

**A**: 在 **Anaconda Prompt** 中运行，或初始化conda：
```powershell
# 初始化conda for PowerShell
conda init powershell
# 重启PowerShell后生效
```

### Q: 创建环境很慢

**A**: 添加国内镜像源：
```powershell
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/
conda config --set show_channel_urls yes
```

### Q: pip安装依赖时出错

**A**: 确保已激活环境：
```powershell
# 查看当前环境
conda info --envs

# 确认market-thermo前有*号
# * market-thermo    C:\Users\...\anaconda3\envs\market-thermo
```

## 完整工作流程

```powershell
# 每天开始工作
cd D:\code\MyCode\market-thermometer
conda activate market-thermo

# 开发/测试
python test_config_simple.py

# 工作结束（可选）
conda deactivate
```

## 环境管理

```powershell
# 查看所有环境
conda env list

# 删除环境
conda env remove -n market-thermo

# 导出环境（备份）
conda env export > environment_backup.yml

# 从备份恢复
conda env create -f environment_backup.yml
```

## 下一步

环境设置完成后，继续开发：

1. ✅ 环境已设置
2. ✅ 阶段1已完成
3. ➡️ 准备进入阶段2：核心转换和评分逻辑

告诉我准备好了，我们继续阶段2！

