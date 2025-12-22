import sys
sys.stdout.reconfigure(encoding='utf-8')

from storage.repository import Repository

repo = Repository('sqlite:///data/market_thermo_3years_auto.db')
meta_list = repo.get_all_series_meta()

us_indicators = [m for m in meta_list if m.get('market') == 'US']
print(f'US市场指标数量: {len(us_indicators)}')
print('\nUS市场所有指标:')
for m in us_indicators:
    code = m['code']
    name = m.get('name', 'N/A')[:30]
    role = m.get('role', 'N/A')
    print(f"  - {code:25s} | {name:30s} | role={role}")

