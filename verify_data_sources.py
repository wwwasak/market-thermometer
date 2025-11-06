"""
数据源快速验证脚本

验证所有数据源是否正常工作：
- FRED (US市场)
- yfinance (US + CN市场)
- Stooq (CNH外汇)
- AKShare (CN市场)
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath('.'))

from core.datasource import DataSourceManager

print("="*80)
print("  数据源验证")
print("="*80)

# 初始化数据源管理器
fred_key = os.getenv('FRED_API_KEY')
if not fred_key:
    print("\n[WARNING] 未设置FRED_API_KEY环境变量")
    print("请在.env文件中配置: FRED_API_KEY=your_key_here")
    print("获取免费API key: https://fred.stlouisfed.org/docs/api/api_key.html\n")

dsm = DataSourceManager(fred_api_key=fred_key)

end_date = datetime.now()
start_date = end_date - timedelta(days=365)  # 1年

print(f"\n测试日期范围: {start_date.date()} 至 {end_date.date()}")

results = {}

# 测试FRED
print("\n" + "="*80)
print("  1. FRED (美国宏观数据)")
print("="*80)
try:
    if fred_key:
        data = dsm.fred_fetcher.fetch('RRPONTSYD', start_date, end_date)
        if len(data) > 0:
            print(f"[OK] FRED: {len(data)}条数据")
            results['fred'] = True
        else:
            print("[FAIL] FRED: 无数据")
            results['fred'] = False
    else:
        print("[SKIP] 未配置API key")
        results['fred'] = None
except Exception as e:
    print(f"[FAIL] FRED: {str(e)[:60]}")
    results['fred'] = False

# 测试yfinance (US)
print("\n" + "="*80)
print("  2. yfinance (美国市场)")
print("="*80)
try:
    data = dsm.yf_fetcher.fetch('SPY', start_date, end_date)
    if len(data) > 100:
        print(f"[OK] yfinance US: {len(data)}条数据 (SPY)")
        results['yfinance_us'] = True
    else:
        print(f"[FAIL] yfinance US: 数据不足")
        results['yfinance_us'] = False
except Exception as e:
    print(f"[FAIL] yfinance US: {str(e)[:60]}")
    results['yfinance_us'] = False

# 测试yfinance (CN)
print("\n" + "="*80)
print("  3. yfinance (CNY在岸人民币)")
print("="*80)
try:
    data = dsm.yf_fetcher.fetch('CNY=X', start_date, end_date)
    if len(data) > 100:
        print(f"[OK] yfinance CN: {len(data)}条数据 (CNY=X)")
        results['yfinance_cn'] = True
    else:
        print(f"[FAIL] yfinance CN: 数据不足")
        results['yfinance_cn'] = False
except Exception as e:
    print(f"[FAIL] yfinance CN: {str(e)[:60]}")
    results['yfinance_cn'] = False

# 测试Stooq (CNH)
print("\n" + "="*80)
print("  4. Stooq (CNH离岸人民币) - 关键配对")
print("="*80)
try:
    data = dsm.stooq_fetcher.fetch('CNH', start_date, end_date)
    if len(data) > 100:
        print(f"[OK] Stooq: {len(data)}条数据 (CNH)")
        print(f"    最新值: {data.iloc[-1]:.4f}")
        results['stooq'] = True
    else:
        print(f"[FAIL] Stooq: 数据不足")
        results['stooq'] = False
except Exception as e:
    print(f"[FAIL] Stooq: {str(e)[:60]}")
    results['stooq'] = False

# 测试AKShare
print("\n" + "="*80)
print("  5. AKShare (中国市场)")
print("="*80)
try:
    data = dsm.akshare_fetcher.fetch('margin_sse', start_date, end_date)
    if len(data) > 100:
        print(f"[OK] AKShare: {len(data)}条数据 (两融余额)")
        results['akshare'] = True
    else:
        print(f"[FAIL] AKShare: 数据不足")
        results['akshare'] = False
except Exception as e:
    print(f"[FAIL] AKShare: {str(e)[:60]}")
    results['akshare'] = False

# 汇总
print("\n" + "="*80)
print("  验证结果汇总")
print("="*80)

all_ok = True
for source, status in results.items():
    if status is True:
        print(f"  [OK]   {source}")
    elif status is False:
        print(f"  [FAIL] {source}")
        all_ok = False
    else:
        print(f"  [SKIP] {source}")

print("\n" + "="*80)
if all_ok and None not in results.values():
    print("\n[SUCCESS] 所有数据源验证通过！")
    print("\n您可以开始使用应用程序了:")
    print("  python app.py")
elif results.get('stooq') and results.get('yfinance_cn'):
    print("\n[SUCCESS] 核心数据源验证通过！")
    print("\n关键配对CNH+CNY可以正常工作:")
    print("  - CNH (Stooq): OK")
    print("  - CNY (yfinance): OK")
    if not fred_key:
        print("\n[NOTE] 建议配置FRED_API_KEY以启用US市场功能")
else:
    print("\n[WARNING] 部分数据源验证失败")
    print("\n请检查网络连接和依赖安装:")
    print("  pip install -r requirements.txt")

print("\n" + "="*80)

