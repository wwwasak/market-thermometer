"""
测试东方财富成交额接口
"""
import requests
from datetime import datetime, timedelta
import pandas as pd

def test_market_amount(secid: str, name: str):
    """测试获取指定指数的成交额"""
    print(f"\n{'='*60}")
    print(f"测试 {name} ({secid}) 成交额接口")
    print('='*60)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    params_market = {
        "fields1": "f1,f2,f3,f4,f5",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
        "secid": secid,
        "klt": "101",  # 日线
        "fqt": "1",
        "beg": start_date.strftime("%Y%m%d"),
        "end": end_date.strftime("%Y%m%d"),
    }
    headers = {"Referer": "https://quote.eastmoney.com/"}
    
    try:
        print(f"请求URL: https://push2his.eastmoney.com/api/qt/stock/kline/get")
        print(f"参数: {params_market}")
        
        resp_market = requests.get(
            "https://push2his.eastmoney.com/api/qt/stock/kline/get",
            params=params_market,
            headers=headers,
            timeout=10,
        )
        
        print(f"响应状态码: {resp_market.status_code}")
        
        if resp_market.status_code != 200:
            print(f"❌ HTTP错误: {resp_market.status_code}")
            return None
            
        data_market = resp_market.json()
        print(f"响应JSON键: {list(data_market.keys())}")
        
        data = data_market.get("data", {})
        if not data:
            print(f"❌ 没有data字段")
            return None
            
        klines = data.get("klines") or []
        print(f"获取到 {len(klines)} 条K线数据")
        
        if not klines:
            print(f"❌ klines为空")
            return None
        
        # 解析数据
        records = []
        for item in klines:
            parts = item.split(",")
            if len(parts) < 7:
                continue
            date_str = parts[0]
            amount = float(parts[6]) / 1e8  # 转为亿元
            records.append({'date': date_str, 'amount': amount})
        
        df = pd.DataFrame(records)
        print(f"\n最近的成交额数据:")
        print(df.tail(5).to_string(index=False))
        
        return df
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    # 测试上证指数
    sh_data = test_market_amount("1.000001", "上证指数")
    
    # 测试深证成指
    sz_data = test_market_amount("0.399001", "深证成指")
    
    # 总结
    print(f"\n{'='*60}")
    print("总结:")
    print('='*60)
    if sh_data is not None and sz_data is not None:
        print("✅ 两个接口都正常工作")
    elif sh_data is None and sz_data is None:
        print("❌ 两个接口都失败了 - 这就是NORTH_TURNOVER_SHARE为0的原因！")
    else:
        print("⚠️ 有一个接口失败了")
