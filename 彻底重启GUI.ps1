# 彻底重启GUI - 清除所有缓存和进程

Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "彻底重启GUI" -ForegroundColor Cyan
Write-Host "=" * 80 -ForegroundColor Cyan

# 1. 杀死所有Python进程
Write-Host "`n步骤1: 杀死所有Python进程..." -ForegroundColor Yellow
$pythonProcesses = Get-Process | Where-Object {$_.ProcessName -like "*python*"}

if ($pythonProcesses) {
    Write-Host "  找到 $($pythonProcesses.Count) 个Python进程" -ForegroundColor Yellow
    $pythonProcesses | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "  [OK] 已关闭" -ForegroundColor Green
} else {
    Write-Host "  [OK] 没有运行中的Python进程" -ForegroundColor Green
}

# 2. 清除__pycache__
Write-Host "`n步骤2: 清除Python缓存..." -ForegroundColor Yellow
$cacheCount = 0

Get-ChildItem -Path . -Recurse -Filter "__pycache__" -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    $cacheCount++
}

Get-ChildItem -Path . -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
    $cacheCount++
}

Write-Host "  [OK] 清除了 $cacheCount 个缓存项" -ForegroundColor Green

# 3. 等待
Write-Host "`n步骤3: 等待10秒确保完全退出..." -ForegroundColor Yellow
Start-Sleep -Seconds 10
Write-Host "  [OK] 完成" -ForegroundColor Green

# 4. 启动GUI
Write-Host "`n步骤4: 启动GUI..." -ForegroundColor Yellow
Write-Host "  执行: python app.py" -ForegroundColor Gray
Write-Host ""
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "现在启动GUI..." -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host ""

python app.py

