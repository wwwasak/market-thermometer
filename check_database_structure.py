"""
数据库结构检查脚本
检查market_thermo数据库的实际结构
"""

import sqlite3
import pandas as pd

def main():
    db_path = "data/market_thermo_3years_auto.db"
    
    print("=" * 80)
    print("数据库结构详细检查")
    print("=" * 80)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取所有表
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table'
            ORDER BY name
        """)
        tables = cursor.fetchall()
        
        print(f"\n数据库中的表 (共{len(tables)}个):")
        for table in tables:
            print(f"  - {table[0]}")
        
        # 检查每个表的结构和数据量
        for table in tables:
            table_name = table[0]
            print(f"\n{'='*80}")
            print(f"表: {table_name}")
            print(f"{'='*80}")
            
            # 获取表结构
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            print(f"\n列结构:")
            for col in columns:
                print(f"  {col[1]:<20} {col[2]:<10} {'NOT NULL' if col[3] else ''} {'PK' if col[5] else ''}")
            
            # 获取数据量
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"\n数据行数: {count}")
            
            # 如果是series_data或series_meta，显示更多信息
            if table_name == 'series_data':
                # 先获取series_meta信息以关联series_id和code
                cursor.execute("SELECT id, code, name FROM series_meta")
                series_map = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
                
                cursor.execute("""
                    SELECT series_id, COUNT(*), MIN(date), MAX(date)
                    FROM series_data
                    GROUP BY series_id
                    ORDER BY series_id
                """)
                series_info = cursor.fetchall()
                print(f"\n各个series的数据情况:")
                for info in series_info:
                    series_id = info[0]
                    code, name = series_map.get(series_id, ('Unknown', 'Unknown'))
                    print(f"  {code:<30} {info[1]:>5}行  {info[2]} 至 {info[3]}")
            
            elif table_name == 'series_meta':
                df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
                if not df.empty:
                    print(f"\n数据预览:")
                    print(df.to_string(index=False))
            
            elif table_name == 'regimes' and count > 0:
                cursor.execute(f"""
                    SELECT date, market, regime, lamp_final 
                    FROM {table_name} 
                    ORDER BY date DESC 
                    LIMIT 10
                """)
                recent = cursor.fetchall()
                print(f"\n最近10条regime数据:")
                for row in recent:
                    print(f"  {row[0]}  {row[1]:<4}  {row[2]:<12}  {row[3]}")
        
        conn.close()
        
        print(f"\n{'='*80}")
        print("分析结论")
        print(f"{'='*80}")
        
        print("\n1. 数据库使用的是 series_data 表，而不是 indicators 表")
        print("   这可能是新版本的数据库结构")
        
        print("\n2. 需要在 series_data 表中查找 IWM_SPY_REL20 数据")
        
    except Exception as e:
        print(f"[ERROR] 数据库检查失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

