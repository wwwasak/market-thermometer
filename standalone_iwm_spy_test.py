"""
完全独立的IWM_SPY_REL20数据获取测试

不依赖任何项目代码，直接测试yfinance
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

print("=" * 80)
print("独立测试：IWM_SPY_REL20数据获取")
print("=" * 80)
print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

# 步骤1: 获取足够的历史数据（需要至少20个交易日来计算relret20）
print("步骤1: 获取IWM和SPY的历史数据")
print("-" * 80)

end_date = datetime.now()
start_date = end_date - timedelta(days=45)  # 获取45天数据，确保有足够的交易日

print(f"请求时间范围: {start_date.date()} 至 {end_date.date()}\n")

# 获取IWM
print("获取IWM数据...")
iwm = yf.download("IWM", start=start_date, end=end_date, progress=False)
print(f"[OK] IWM: {len(iwm)} 条数据")
print(f"    日期范围: {iwm.index[0].strftime('%Y-%m-%d')} 至 {iwm.index[-1].strftime('%Y-%m-%d')}")
print(f"    最近5天:")
print(iwm[['Close']].tail(5))

# 获取SPY
print("\n获取SPY数据...")
spy = yf.download("SPY", start=start_date, end=end_date, progress=False)
print(f"[OK] SPY: {len(spy)} 条数据")
print(f"    日期范围: {spy.index[0].strftime('%Y-%m-%d')} 至 {spy.index[-1].strftime('%Y-%m-%d')}")
print(f"    最近5天:")
print(spy[['Close']].tail(5))

# 步骤2: 检查12月26日数据
print("\n" + "=" * 80)
print("步骤2: 检查12月26日数据")
print("-" * 80)

target_date = pd.Timestamp('2025-12-26')

iwm_has_26 = target_date in iwm.index
spy_has_26 = target_date in spy.index

print(f"IWM有12月26日数据: {iwm_has_26}")
if iwm_has_26:
    print(f"  Close: {iwm.loc[target_date, 'Close']}")

print(f"SPY有12月26日数据: {spy_has_26}")
if spy_has_26:
    print(f"  Close: {spy.loc[target_date, 'Close']}")

# 步骤3: 合并数据并对齐
print("\n" + "=" * 80)
print("步骤3: 合并IWM和SPY数据")
print("-" * 80)

# 提取Close列
if isinstance(iwm.columns, pd.MultiIndex):
    iwm_close = iwm['Close'].iloc[:, 0] if isinstance(iwm['Close'], pd.DataFrame) else iwm['Close']
else:
    iwm_close = iwm['Close']

if isinstance(spy.columns, pd.MultiIndex):
    spy_close = spy['Close'].iloc[:, 0] if isinstance(spy['Close'], pd.DataFrame) else spy['Close']
else:
    spy_close = spy['Close']

# 确保是Series类型
if not isinstance(iwm_close, pd.Series):
    iwm_close = pd.Series(iwm_close)
if not isinstance(spy_close, pd.Series):
    spy_close = pd.Series(spy_close)

# 对齐数据（只保留两个都有的日期）
df = pd.DataFrame({
    'IWM': iwm_close,
    'SPY': spy_close
})

# 删除任何有NaN的行
df_clean = df.dropna()

print(f"\n合并后数据量: {len(df_clean)}")
print(f"日期范围: {df_clean.index[0].strftime('%Y-%m-%d')} 至 {df_clean.index[-1].strftime('%Y-%m-%d')}")

print(f"\n合并后的最近5天:")
print(df_clean.tail(5))

# 检查12月26日是否在合并后的数据中
print(f"\n12月26日在合并数据中: {target_date in df_clean.index}")

# 步骤4: 计算relret20
print("\n" + "=" * 80)
print("步骤4: 计算relret20（20日相对收益）")
print("-" * 80)

# 计算20日收益率
df_clean['IWM_ret20'] = df_clean['IWM'] / df_clean['IWM'].shift(20) - 1
df_clean['SPY_ret20'] = df_clean['SPY'] / df_clean['SPY'].shift(20) - 1

# 计算相对收益
df_clean['relret20'] = (1 + df_clean['IWM_ret20']) / (1 + df_clean['SPY_ret20']) - 1

print(f"\n计算完成，最近10天的结果:")
print("-" * 80)
print(df_clean[['IWM', 'SPY', 'IWM_ret20', 'SPY_ret20', 'relret20']].tail(10).to_string())

# 步骤5: 检查12月26日的relret20
print("\n" + "=" * 80)
print("步骤5: 检查12月26日的relret20值")
print("-" * 80)

if target_date in df_clean.index:
    row_26 = df_clean.loc[target_date]
    
    print(f"\n12月26日数据:")
    print(f"  IWM价格: {row_26['IWM']}")
    print(f"  SPY价格: {row_26['SPY']}")
    print(f"  IWM 20日收益率: {row_26['IWM_ret20']}")
    print(f"  SPY 20日收益率: {row_26['SPY_ret20']}")
    print(f"  relret20: {row_26['relret20']}")
    
    # 判断是否为NaN
    if pd.isna(row_26['relret20']):
        print(f"\n[ERROR] relret20是NaN！")
        
        # 诊断原因
        print(f"\n诊断NaN原因:")
        
        if pd.isna(row_26['IWM_ret20']):
            print(f"  [问题] IWM_ret20是NaN")
            # 检查20天前的数据
            date_20_days_ago = df_clean.index[df_clean.index.get_loc(target_date) - 20]
            print(f"    需要的历史日期: {date_20_days_ago.strftime('%Y-%m-%d')}")
            if date_20_days_ago in df_clean.index:
                iwm_20d_ago = df_clean.loc[date_20_days_ago, 'IWM']
                print(f"    20天前IWM价格: {iwm_20d_ago}")
                print(f"    当前IWM价格: {row_26['IWM']}")
                print(f"    应该的收益率: {(row_26['IWM'] / iwm_20d_ago - 1)}")
            else:
                print(f"    [ERROR] 20天前的数据不存在！")
        
        if pd.isna(row_26['SPY_ret20']):
            print(f"  [问题] SPY_ret20是NaN")
            date_20_days_ago = df_clean.index[df_clean.index.get_loc(target_date) - 20]
            print(f"    需要的历史日期: {date_20_days_ago.strftime('%Y-%m-%d')}")
            if date_20_days_ago in df_clean.index:
                spy_20d_ago = df_clean.loc[date_20_days_ago, 'SPY']
                print(f"    20天前SPY价格: {spy_20d_ago}")
                print(f"    当前SPY价格: {row_26['SPY']}")
                print(f"    应该的收益率: {(row_26['SPY'] / spy_20d_ago - 1)}")
            else:
                print(f"    [ERROR] 20天前的数据不存在！")
    else:
        print(f"\n[OK] relret20计算成功: {row_26['relret20']:.6f}")
else:
    print(f"\n[ERROR] 合并数据中没有12月26日！")
    print(f"\n可能原因:")
    print(f"  1. IWM或SPY在12月26日没有数据")
    print(f"  2. 数据对齐时被过滤掉了")

# 步骤6: 检查最近有效的relret20值
print("\n" + "=" * 80)
print("步骤6: 查看最近有效的relret20值")
print("-" * 80)

valid_relret = df_clean[df_clean['relret20'].notna()]

if not valid_relret.empty:
    print(f"\n最近5个有效的relret20值:")
    print(valid_relret[['relret20']].tail(5).to_string())
    
    latest_valid_date = valid_relret.index[-1]
    print(f"\n最新有效日期: {latest_valid_date.strftime('%Y-%m-%d')}")
    
    if latest_valid_date < target_date:
        days_diff = (target_date - latest_valid_date).days
        print(f"[WARN] 最新有效日期比12月26日早 {days_diff} 天")
else:
    print(f"\n[ERROR] 没有任何有效的relret20值！")

# 总结
print("\n" + "=" * 80)
print("测试总结")
print("=" * 80)

print(f"\n1. yfinance数据获取:")
print(f"   IWM: {len(iwm)} 条, 最新到 {iwm.index[-1].strftime('%Y-%m-%d')}")
print(f"   SPY: {len(spy)} 条, 最新到 {spy.index[-1].strftime('%Y-%m-%d')}")

print(f"\n2. 12月26日原始数据:")
print(f"   IWM有: {iwm_has_26}")
print(f"   SPY有: {spy_has_26}")
print(f"   合并后有: {target_date in df_clean.index}")

print(f"\n3. relret20计算:")
if target_date in df_clean.index:
    has_valid_relret = pd.notna(df_clean.loc[target_date, 'relret20'])
    print(f"   12月26日relret20有效: {has_valid_relret}")
    if has_valid_relret:
        print(f"   值: {df_clean.loc[target_date, 'relret20']:.6f}")
    else:
        print(f"   [ERROR] relret20是NaN，需要检查历史数据完整性")
else:
    print(f"   [ERROR] 无法计算，因为12月26日不在合并数据中")

print("\n" + "=" * 80)

