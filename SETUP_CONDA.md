# Anaconda 环境设置指南

## 问题说明

Python 3.13 当前与 pandas 2.1.4 存在兼容性问题（Cython编译错误）。推荐使用 Python 3.11 或 3.12。

## 方案1: 使用 environment.yml（推荐）

### 1. 创建虚拟环境

```powershell
# 使用Python 3.11（推荐）
conda env create -f environment.yml

# 或者如果想用Python 3.12，先编辑environment.yml把python=3.11改为python=3.12，然后再运行
```

### 2. 激活环境

```powershell
conda activate market-thermo
```

### 3. 验证安装

```powershell
# 检查Python版本
python --version
# 应该显示 Python 3.11.x 或 3.12.x

# 运行测试
python test_config_simple.py
```

## 方案2: 手动创建环境

### 1. 创建新的conda环境

```powershell
# 使用Python 3.11
conda create -n market-thermo python=3.11 -y

# 或使用Python 3.12
# conda create -n market-thermo python=3.12 -y
```

### 2. 激活环境

```powershell
conda activate market-thermo
```

### 3. 安装依赖

```powershell
pip install -r requirements.txt
```

## 常用命令

### 查看所有conda环境

```powershell
conda env list
```

### 激活环境

```powershell
conda activate market-thermo
```

### 退出环境

```powershell
conda deactivate
```

### 删除环境（如果需要重建）

```powershell
conda env remove -n market-thermo
```

### 导出当前环境（用于备份）

```powershell
conda env export > environment_backup.yml
```

## 验证环境设置

运行以下命令确认环境正确：

```powershell
# 1. 激活环境
conda activate market-thermo

# 2. 检查Python版本
python --version

# 3. 检查关键包
python -c "import pandas; print('pandas:', pandas.__version__)"
python -c "import PyQt6; print('PyQt6: OK')"
python -c "import matplotlib; print('matplotlib:', matplotlib.__version__)"

# 4. 运行配置测试
python test_config_simple.py
```

## 在VSCode/Cursor中使用conda环境

### 1. 选择Python解释器

1. 按 `Ctrl+Shift+P` 打开命令面板
2. 输入 "Python: Select Interpreter"
3. 选择 `market-thermo` 环境对应的Python解释器
   - 通常路径类似: `C:\Users\YourName\anaconda3\envs\market-thermo\python.exe`

### 2. 设置终端默认环境

在项目根目录创建或编辑 `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": "${env:CONDA_PREFIX}\\python.exe",
    "python.terminal.activateEnvironment": true,
    "terminal.integrated.env.windows": {
        "CONDA_DEFAULT_ENV": "market-thermo"
    }
}
```

## 故障排查

### 问题0: 提示需要接受服务条款（TOS）

**错误信息**: `CondaToSNonInteractiveError: Terms of Service have not been accepted`

**解决方案**: 
```powershell
# 接受Anaconda频道的服务条款
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/msys2

# 然后重新创建环境
conda create -n market-thermo python=3.11 -y
```

**备选方案**: 使用 conda-forge（开源频道，无TOS限制）
```powershell
conda create -n market-thermo python=3.11 -c conda-forge -y
```

### 问题1: conda命令找不到

**解决方案**: 确保Anaconda已添加到PATH，或使用Anaconda Prompt运行命令

### 问题2: 环境创建失败

**解决方案**: 
```powershell
# 清理conda缓存
conda clean --all -y

# 更新conda
conda update -n base -c defaults conda

# 重新创建环境
conda env create -f environment.yml
```

### 问题3: pip安装依赖很慢

**解决方案**: 使用国内镜像源
```powershell
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 问题4: 在Cursor/VSCode终端无法激活conda环境

**解决方案**: 
```powershell
# 初始化PowerShell的conda支持
conda init powershell

# 重启终端后再试
conda activate market-thermo
```

## 推荐工作流程

```powershell
# 1. 打开项目
cd D:\code\MyCode\market-thermometer

# 2. 激活环境
conda activate market-thermo

# 3. 开发/测试
python test_config_simple.py

# 4. 完成后退出（可选）
conda deactivate
```

## 后续开发时

每次开始开发前，只需：

```powershell
conda activate market-thermo
```

在Cursor中，如果已经设置好Python解释器，打开集成终端会自动激活环境。

