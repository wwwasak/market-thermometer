# 双市场温度计 - Conda环境快速设置脚本
# PowerShell 脚本

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "双市场温度计 - 环境设置" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# 检查conda是否可用
Write-Host "检查 Conda 安装..." -ForegroundColor Yellow
try {
    $condaVersion = conda --version 2>&1
    Write-Host "✓ Conda 已安装: $condaVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ 未找到 Conda。请确保 Anaconda 或 Miniconda 已安装并添加到 PATH。" -ForegroundColor Red
    Write-Host "  或在 Anaconda Prompt 中运行此脚本。" -ForegroundColor Yellow
    exit 1
}

# 询问Python版本选择
Write-Host "`n选择 Python 版本:" -ForegroundColor Yellow
Write-Host "  1. Python 3.11 (推荐)" -ForegroundColor White
Write-Host "  2. Python 3.12" -ForegroundColor White
$choice = Read-Host "请输入选择 (1 或 2，默认 1)"

if ($choice -eq "2") {
    $pythonVersion = "3.12"
} else {
    $pythonVersion = "3.11"
}

Write-Host "`n将使用 Python $pythonVersion" -ForegroundColor Green

# 检查环境是否已存在
Write-Host "`n检查现有环境..." -ForegroundColor Yellow
$envExists = conda env list | Select-String "market-thermo"

if ($envExists) {
    Write-Host "! 环境 'market-thermo' 已存在。" -ForegroundColor Yellow
    $overwrite = Read-Host "是否删除并重新创建? (y/N)"
    
    if ($overwrite -eq "y" -or $overwrite -eq "Y") {
        Write-Host "删除现有环境..." -ForegroundColor Yellow
        conda env remove -n market-thermo -y
        Write-Host "✓ 已删除" -ForegroundColor Green
    } else {
        Write-Host "保留现有环境。如需重新安装依赖，请运行:" -ForegroundColor Yellow
        Write-Host "  conda activate market-thermo" -ForegroundColor White
        Write-Host "  pip install -r requirements.txt --force-reinstall" -ForegroundColor White
        exit 0
    }
}

# 检查并接受TOS（如果需要）
Write-Host "`n检查服务条款状态..." -ForegroundColor Yellow
try {
    # 尝试接受TOS（忽略错误）
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main 2>$null
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r 2>$null
    conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/msys2 2>$null
    Write-Host "✓ 服务条款已接受" -ForegroundColor Green
} catch {
    Write-Host "! TOS命令不可用或已接受" -ForegroundColor Yellow
}

# 创建conda环境
Write-Host "`n创建 conda 环境 (Python $pythonVersion)..." -ForegroundColor Yellow
conda create -n market-thermo python=$pythonVersion -y

if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 环境创建失败" -ForegroundColor Red
    exit 1
}

Write-Host "✓ 环境创建成功" -ForegroundColor Green

# 提示激活环境
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "下一步操作:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. 激活环境:" -ForegroundColor Yellow
Write-Host "   conda activate market-thermo" -ForegroundColor White
Write-Host ""
Write-Host "2. 安装依赖:" -ForegroundColor Yellow
Write-Host "   pip install -r requirements.txt" -ForegroundColor White
Write-Host ""
Write-Host "3. 运行测试:" -ForegroundColor Yellow
Write-Host "   python test_config_simple.py" -ForegroundColor White
Write-Host ""
Write-Host "详细说明请参考: SETUP_CONDA.md" -ForegroundColor Cyan
Write-Host ""

# 询问是否立即激活并安装依赖
$installNow = Read-Host "是否现在激活环境并安装依赖? (Y/n)"

if ($installNow -ne "n" -and $installNow -ne "N") {
    Write-Host "`n激活环境并安装依赖..." -ForegroundColor Yellow
    Write-Host "注意: 需要在新的PowerShell会话中手动执行以下命令:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "conda activate market-thermo" -ForegroundColor Green
    Write-Host "pip install -r requirements.txt" -ForegroundColor Green
    Write-Host "python test_config_simple.py" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "`n请手动执行上述命令完成设置。" -ForegroundColor Yellow
}

Write-Host "`n✓ 设置脚本完成" -ForegroundColor Green

