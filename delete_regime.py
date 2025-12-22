"""删除特定日期的综合评分数据"""
from datetime import datetime
from storage.repository import Repository
from storage.models import Regime

def delete_regime(market: str, date_str: str):
    # 使用GUI的数据库
    database_url = 'sqlite:///data/market_thermo_3years_auto.db'
    repository = Repository(database_url)
    
    target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    view = 'daily'
    
    print(f"\n删除 {market} 市场 {target_date} 的综合评分...")
    
    with repository.get_session() as session:
        # 查询记录
        records = session.query(Regime).filter(
            Regime.market == market,
            Regime.date == target_date,
            Regime.view == view
        ).all()
        
        if not records:
            print(f"未找到记录")
            return
        
        print(f"找到 {len(records)} 条记录：")
        for rec in records:
            print(f"  - ID: {rec.id}, 评分: {rec.composite_score}")
        
        # 删除
        deleted = session.query(Regime).filter(
            Regime.market == market,
            Regime.date == target_date,
            Regime.view == view
        ).delete()
        
        session.commit()
        print(f"\n已删除 {deleted} 条记录")

if __name__ == '__main__':
    # 修改这里的参数
    delete_regime(
        market='CN',           # 'CN' 或 'US'
        date_str='2025-10-6'  # 'YYYY-MM-DD'
      
    )

