"""
数据源模块

提供从各种数据源获取市场数据的接口：
- FRED (Federal Reserve Economic Data)
- yfinance (Yahoo Finance)
- CSV文件导入
"""

import os
import time
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests

# 环境变量和配置
from dotenv import load_dotenv
load_dotenv()


class DataFetchError(Exception):
    """数据获取错误"""
    pass


class FREDFetcher:
    """
    FRED (Federal Reserve Economic Data) 数据获取器
    
    需要 FRED_API_KEY 环境变量
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        初始化FRED获取器
        
        @param {Optional[str]} api_key - FRED API密钥，如果不提供则从环境变量读取
        """
        self.api_key = api_key or os.getenv('FRED_API_KEY')
        
        if not self.api_key:
            print("[WARNING] FRED_API_KEY not found. Set it in .env file or pass to constructor.")
        
        self.fred = None
        if self.api_key:
            try:
                from fredapi import Fred
                self.fred = Fred(api_key=self.api_key)
            except ImportError:
                print("[ERROR] fredapi not installed. Run: pip install fredapi")
            except Exception as e:
                print(f"[ERROR] Failed to initialize FRED: {e}")
    
    def fetch(
        self,
        series_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        retry: int = 3,
        retry_delay: float = 1.0
    ) -> pd.Series:
        """
        获取FRED时间序列数据
        
        @param {str} series_id - FRED序列ID（如 'RRPONTSYD', 'WTREGEN'）
        @param {Optional[datetime]} start_date - 开始日期
        @param {Optional[datetime]} end_date - 结束日期
        @param {int} retry - 重试次数
        @param {float} retry_delay - 重试延迟（秒）
        @returns {pd.Series} 时间序列数据
        
        @example
        >>> fetcher = FREDFetcher()
        >>> rrp = fetcher.fetch('RRPONTSYD', start_date=datetime(2024, 1, 1))
        """
        if not self.fred:
            raise DataFetchError("FRED not initialized. Check API key.")
        
        for attempt in range(retry):
            try:
                data = self.fred.get_series(
                    series_id,
                    observation_start=start_date,
                    observation_end=end_date
                )
                
                if data is None or len(data) == 0:
                    raise DataFetchError(f"No data returned for {series_id}")
                
                # 确保索引是DatetimeIndex
                if not isinstance(data.index, pd.DatetimeIndex):
                    data.index = pd.to_datetime(data.index)
                
                print(f"[OK] Fetched {len(data)} records for {series_id}")
                return data
            
            except Exception as e:
                if attempt < retry - 1:
                    print(f"[WARNING] Attempt {attempt + 1} failed for {series_id}: {e}")
                    time.sleep(retry_delay)
                else:
                    raise DataFetchError(f"Failed to fetch {series_id} after {retry} attempts: {e}")
    
    def fetch_multiple(
        self,
        series_ids: List[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, pd.Series]:
        """
        批量获取多个FRED序列
        
        @param {List[str]} series_ids - FRED序列ID列表
        @returns {Dict[str, pd.Series]} 序列字典 {series_id: data}
        """
        results = {}
        
        for series_id in series_ids:
            try:
                data = self.fetch(series_id, start_date, end_date)
                results[series_id] = data
            except DataFetchError as e:
                print(f"[ERROR] Failed to fetch {series_id}: {e}")
                results[series_id] = pd.Series(dtype=float)
        
        return results


class YFinanceFetcher:
    """
    yfinance (Yahoo Finance) 数据获取器
    
    用于获取股票、指数、外汇等价格数据
    """
    
    def __init__(self):
        """初始化yfinance获取器"""
        self.yf = None
        try:
            import yfinance as yf
            self.yf = yf
        except ImportError:
            print("[ERROR] yfinance not installed. Run: pip install yfinance")
    
    def fetch(
        self,
        ticker: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        column: str = 'Close',
        retry: int = 3,
        retry_delay: float = 1.0
    ) -> pd.Series:
        """
        获取yfinance价格数据
        
        @param {str} ticker - 股票代码（如 '^VIX', 'SPY', 'IWM'）
        @param {Optional[datetime]} start_date - 开始日期
        @param {Optional[datetime]} end_date - 结束日期
        @param {str} column - 使用的列（'Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume'）
        @param {int} retry - 重试次数
        @param {float} retry_delay - 重试延迟（秒）
        @returns {pd.Series} 时间序列数据
        
        @example
        >>> fetcher = YFinanceFetcher()
        >>> vix = fetcher.fetch('^VIX', start_date=datetime(2024, 1, 1))
        """
        if not self.yf:
            raise DataFetchError("yfinance not initialized.")
        
        for attempt in range(retry):
            try:
                # 使用Ticker对象下载数据（更可靠）
                ticker_obj = self.yf.Ticker(ticker)
                df = ticker_obj.history(
                    start=start_date,
                    end=end_date,
                    auto_adjust=True
                )
                
                if df is None or len(df) == 0:
                    raise DataFetchError(f"No data returned for {ticker}")
                
                # 提取指定列
                if column not in df.columns:
                    available = ', '.join(df.columns)
                    raise DataFetchError(f"Column '{column}' not found. Available: {available}")
                
                series = df[column]
                series = series.dropna()
                
                if len(series) == 0:
                    raise DataFetchError(f"No valid data for {ticker}")
                
                print(f"[OK] Fetched {len(series)} records for {ticker}")
                return series
            
            except Exception as e:
                if attempt < retry - 1:
                    print(f"[WARNING] Attempt {attempt + 1} failed for {ticker}: {e}")
                    time.sleep(retry_delay)
                else:
                    raise DataFetchError(f"Failed to fetch {ticker} after {retry} attempts: {e}")
    
    def fetch_multiple(
        self,
        tickers: List[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        column: str = 'Close'
    ) -> Dict[str, pd.Series]:
        """
        批量获取多个ticker数据
        
        @param {List[str]} tickers - ticker列表
        @returns {Dict[str, pd.Series]} 序列字典
        """
        results = {}
        
        for ticker in tickers:
            try:
                data = self.fetch(ticker, start_date, end_date, column)
                results[ticker] = data
            except DataFetchError as e:
                print(f"[ERROR] Failed to fetch {ticker}: {e}")
                results[ticker] = pd.Series(dtype=float)
        
        return results
    
    def fetch_pair(
        self,
        ticker1: str,
        ticker2: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Tuple[pd.Series, pd.Series]:
        """
        获取一对ticker数据（用于相对收益率计算）
        
        @param {str} ticker1 - 第一个ticker
        @param {str} ticker2 - 第二个ticker
        @returns {Tuple[pd.Series, pd.Series]} 对齐后的两个序列
        """
        data1 = self.fetch(ticker1, start_date, end_date)
        data2 = self.fetch(ticker2, start_date, end_date)
        
        # 对齐索引
        data1, data2 = data1.align(data2, join='inner')
        
        return data1, data2


class AKShareFetcher:
    """
    AKShare数据获取器
    
    用于获取中国市场数据（两融、北向资金、PMI、指数等）
    akshare是免费的中国金融数据接口，无需API密钥
    
    @see https://github.com/akfamily/akshare
    """
    
    def __init__(self):
        """
        初始化AKShare获取器
        
        @raises {DataFetchError} 如果akshare未安装
        """
        try:
            import akshare as ak
            self.ak = ak
            self._available = True
        except ImportError:
            self._available = False
            print("[WARNING] akshare not installed. Install with: pip install akshare")
    
    def fetch(
        self,
        symbol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.Series:
        """
        根据symbol获取akshare数据
        
        @param {str} symbol - 数据标识符，格式如下:
            - "margin_sse" - 上交所融资融券余额
            - "north_flow" - 北向资金流向
            - "index:000852" - 指数数据（中证1000）
            - "pmi_neworder" - PMI新订单指数
            - "bond_10y" - 10年期国债收益率
            - "eps_yield" - 全A盈利收益率（E/P = 1/PE）
            - "etf_flow" - ETF资金流向
        @param {datetime} start_date - 开始日期
        @param {datetime} end_date - 结束日期
        @returns {pd.Series} 时间序列数据
        
        @example
        >>> fetcher = AKShareFetcher()
        >>> margin = fetcher.fetch("margin_sse", start_date=datetime(2023, 1, 1))
        """
        if not self._available:
            raise DataFetchError("akshare is not available. Please install it first.")
        
        try:
            # 格式化日期为字符串
            start_str = start_date.strftime('%Y%m%d') if start_date else "20200101"
            end_str = end_date.strftime('%Y%m%d') if end_date else datetime.now().strftime('%Y%m%d')
            
            # 根据symbol类型获取不同数据
            if symbol == "margin_sse":
                return self._fetch_margin(start_str, end_str)
            elif symbol == "north_flow":
                return self._fetch_north_flow(start_str, end_str)
            elif symbol.startswith("index:"):
                index_code = symbol.split(":")[1]
                return self._fetch_index(index_code, start_str, end_str)
            elif symbol == "pmi_neworder":
                return self._fetch_pmi_neworder(start_str, end_str)
            elif symbol == "bond_10y":
                return self._fetch_bond_yield(start_str, end_str, maturity="10年")
            elif symbol == "eps_yield":
                return self._fetch_eps_yield(start_str, end_str)
            elif symbol == "etf_flow":
                return self._fetch_etf_flow(start_str, end_str)
            else:
                raise DataFetchError(f"Unknown akshare symbol: {symbol}")
                
        except Exception as e:
            raise DataFetchError(f"Failed to fetch akshare data for {symbol}: {e}")
    
    def _fetch_margin(self, start_date: str, end_date: str) -> pd.Series:
        """
        获取融资融券余额数据
        
        @returns {pd.Series} 融资融券余额（单位：亿元）
        """
        try:
            # 获取上交所融资融券数据
            df = self.ak.stock_margin_sse(start_date=start_date, end_date=end_date)
            
            # 列名：['本日融资余额', '融资余额', '融资买入额', '融券余额', '融券卖出量', '融券余量', '融资融券余额']
            # 找到日期列（可能是不同的名称）
            date_col = None
            for col in df.columns:
                if '日期' in col or 'date' in col.lower() or col == '本日融资余额':
                    # '本日融资余额'列实际是日期格式YYYYMMDD
                    date_col = col
                    break
            
            if date_col is None:
                # 如果找不到明确的日期列，使用第一列
                date_col = df.columns[0]
            
            df['date'] = pd.to_datetime(df[date_col], format='%Y%m%d', errors='coerce')
            df = df.set_index('date')
            df = df.dropna()  # 移除日期转换失败的行
            
            # 使用融资融券余额总计（单位：元，需要转换为亿元）
            margin_col = None
            for col in ['融资融券余额', '融资融券余额(元)']:
                if col in df.columns:
                    margin_col = col
                    break
            
            if margin_col is None:
                raise DataFetchError("Cannot find margin balance column")
            
            series = df[margin_col].astype(float)
            # 转换为亿元
            series = series / 100000000
            
            print(f"[OK] Fetched {len(series)} records for margin trading")
            return series
            
        except Exception as e:
            raise DataFetchError(f"Failed to fetch margin data: {e}")
    
    def _fetch_north_flow(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取北向资金流向数据（成交额与占比）
        
        新规后东方财富接口将成交额字段调整为 DEAL_AMT，并将原 BUY_AMT / SELL_AMT 置空。
        这里直接使用 DEAL_AMT 作为“北向成交额（亿元）”的原始值，同时结合上证指数与深证成指的
        成交额总和估算全市场成交额，用于计算“成交额占比”。
        
        @returns {pd.DataFrame} 包含 value_raw（北向成交额，亿元）和 value_tr（北向成交额/全市场成交额）
        """
        try:
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)

            if pd.isna(start_dt) or pd.isna(end_dt):
                raise DataFetchError("Invalid start or end date for north flow fetch")

            def _fetch_mutual_series(mutual_type: str) -> pd.Series:
                url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
                params = {
                    "reportName": "RPT_MUTUAL_DEAL_HISTORY",
                    "columns": "TRADE_DATE,DEAL_AMT,BUY_AMT,SELL_AMT",
                    "filter": f'(MUTUAL_TYPE="{mutual_type}")',
                    "sortColumns": "TRADE_DATE",
                    "sortTypes": "-1",
                    "pageSize": "2000",
                    "pageNumber": "1",
                    "source": "WEB",
                    "client": "WEB",
                    "token": "70f12f0f4f091e459a279469fe49eca5",
                }

                records: List[Dict[str, Any]] = []
                while True:
                    resp = requests.get(url, params=params, timeout=10)
                    resp.raise_for_status()
                    data_json = resp.json()
                    result = data_json.get("result")

                    if not result:
                        break

                    data = result.get("data") or []
                    if not data:
                        break

                    records.extend(data)

                    page_number = int(params["pageNumber"])
                    total_pages = int(result.get("pages", page_number))
                    if page_number >= total_pages:
                        break

                    params["pageNumber"] = str(page_number + 1)
                    time.sleep(0.2)

                if not records:
                    return pd.Series(dtype=float)

                df_local = pd.DataFrame(records)
                df_local["date"] = pd.to_datetime(df_local["TRADE_DATE"], errors="coerce")
                df_local = df_local.dropna(subset=["date"])
                df_local = df_local[(df_local["date"] >= start_dt) & (df_local["date"] <= end_dt)]
                df_local = df_local.sort_values("date")

                if df_local.empty:
                    return pd.Series(dtype=float)

                deal_amt_local = pd.to_numeric(df_local.get("DEAL_AMT"), errors="coerce")
                fallback_buy = pd.to_numeric(df_local.get("BUY_AMT"), errors="coerce")
                series_local = deal_amt_local.where(deal_amt_local.notna(), fallback_buy).fillna(0.0)
                series_local = series_local / 100.0  # 百万元 -> 亿元

                return pd.Series(series_local.values, index=df_local["date"], dtype=float)

            # 分别获取沪股通与深股通成交额，并取总和
            sh_series = _fetch_mutual_series("001")
            sz_series = _fetch_mutual_series("003")

            if len(sh_series) == 0 and len(sz_series) == 0:
                # 若单腿均为空，尝试直接拉取“北向资金”合计（005）
                combined_series = _fetch_mutual_series("005")
                if len(combined_series) == 0:
                    raise DataFetchError("No data returned for north flow (SH/SZ)")
                value_raw = combined_series
            else:
                value_raw = sh_series.add(sz_series, fill_value=0.0)
                value_raw = value_raw.sort_index()

            def _fetch_market_amount(secid: str) -> pd.Series:
                """
                通过东方财富 push2 接口获取指定指数的成交额（单位：亿元）
                """
                params_market = {
                    "fields1": "f1,f2,f3,f4,f5",
                    "fields2": "f51,f52,f53,f54,f55,f56,f57",
                    "secid": secid,
                    "klt": "101",  # 日线
                    "fqt": "1",
                    "beg": start_dt.strftime("%Y%m%d"),
                    "end": end_dt.strftime("%Y%m%d"),
                }
                headers = {"Referer": "https://quote.eastmoney.com/"}
                resp_market = requests.get(
                    "https://push2his.eastmoney.com/api/qt/stock/kline/get",
                    params=params_market,
                    headers=headers,
                    timeout=10,
                )
                resp_market.raise_for_status()
                data_market = resp_market.json().get("data", {})
                klines = data_market.get("klines") or []
                if not klines:
                    raise DataFetchError(f"No kline data returned for secid {secid}")

                records = {}
                for item in klines:
                    parts = item.split(",")
                    if len(parts) < 7:
                        continue
                    date_key = pd.to_datetime(parts[0], errors="coerce")
                    amount = pd.to_numeric(parts[6], errors="coerce")
                    if pd.isna(date_key) or pd.isna(amount):
                        continue
                    records[date_key.normalize()] = amount / 1e8  # 转为亿元

                return pd.Series(records, dtype=float).sort_index()

            total_turnover = pd.Series(dtype=float)
            try:
                sh_turnover = _fetch_market_amount("1.000001")
                sz_turnover = _fetch_market_amount("0.399001")
                total_turnover = sh_turnover.add(sz_turnover, fill_value=0.0)
                print(f"[OK] Fetched market turnover from EastMoney push2 API")
            except Exception as market_exc:
                print(f"[WARNING] Failed to fetch market turnover from EastMoney push2 API: {market_exc}")
                print(f"[INFO] Trying fallback method using akshare stock_zh_index_daily_em...")
                
                # 备用方案：使用akshare的stock_zh_index_daily_em获取东财指数数据（包含成交额）
                try:
                    sh_df = self.ak.stock_zh_index_daily_em(symbol="sh000001")
                    sh_df['date'] = pd.to_datetime(sh_df['date'])
                    sh_df = sh_df.set_index('date').sort_index()
                    sh_df = sh_df[(sh_df.index >= start_dt) & (sh_df.index <= end_dt)]
                    sh_turnover_fallback = pd.to_numeric(sh_df['amount'], errors='coerce') / 1e8  # 元 -> 亿元
                    
                    sz_df = self.ak.stock_zh_index_daily_em(symbol="sz399001")
                    sz_df['date'] = pd.to_datetime(sz_df['date'])
                    sz_df = sz_df.set_index('date').sort_index()
                    sz_df = sz_df[(sz_df.index >= start_dt) & (sz_df.index <= end_dt)]
                    sz_turnover_fallback = pd.to_numeric(sz_df['amount'], errors='coerce') / 1e8  # 元 -> 亿元
                    
                    total_turnover = sh_turnover_fallback.add(sz_turnover_fallback, fill_value=0.0)
                    print(f"[OK] Fallback successful: got {len(total_turnover)} market turnover records via akshare")
                except Exception as fallback_exc:
                    print(f"[ERROR] Fallback also failed: {fallback_exc}")
                    print(f"[WARNING] Setting total_turnover to 0 - NORTH_TURNOVER_SHARE ratio will be 0")
                    total_turnover = pd.Series(0.0, index=value_raw.index)

            total_turnover = total_turnover.reindex(value_raw.index, fill_value=0.0)
            with np.errstate(divide="ignore", invalid="ignore"):
                value_tr = value_raw / total_turnover.replace(0, np.nan)
            value_tr = value_tr.replace([np.inf, -np.inf], np.nan).fillna(0.0)

            result = pd.DataFrame(
                {
                    "value_raw": value_raw,
                    "value_tr": value_tr,
                },
                index=value_raw.index,
            )

            print(f"[OK] Fetched {len(result)} records for north flow (DEAL_AMT + ratio)")
            return result

        except Exception as e:
            raise DataFetchError(f"Failed to fetch north flow data: {e}")
    
    def _fetch_index(self, code: str, start_date: str, end_date: str) -> pd.Series:
        """
        获取指数数据
        
        @param {str} code - 指数代码，如 "000852" (中证1000)
        @returns {pd.Series} 指数收盘价
        """
        try:
            # akshare指数代码需要加上市场前缀
            if not code.startswith(('sh', 'sz')):
                # 上海交易所的指数
                if code.startswith('00'):
                    code = f'sh{code}'
                else:
                    code = f'sz{code}'
            
            # 获取指数日线数据
            df = self.ak.stock_zh_index_daily(symbol=code)
            
            # 过滤日期范围
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
            df = df.sort_index()
            
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            df = df[(df.index >= start_dt) & (df.index <= end_dt)]
            
            # 使用收盘价
            series = df['close']
            series = series.astype(float)
            
            print(f"[OK] Fetched {len(series)} records for index {code}")
            return series
            
        except Exception as e:
            raise DataFetchError(f"Failed to fetch index {code} data: {e}")
    
    def _fetch_pmi_neworder(self, start_date: str, end_date: str) -> pd.Series:
        """
        获取PMI新订单指数
        
        @returns {pd.Series} PMI制造业指数（作为新订单的代理）
        """
        try:
            # 获取中国PMI数据
            df = self.ak.macro_china_pmi()
            
            # 列名：['月份', '制造业-指数', '制造业-同比增长', '非制造业-指数', '非制造业-同比增长']
            # 月份格式如：'2025年10月份'
            
            # 转换日期 - 从'月份'列提取
            def parse_month(month_str):
                # 从'2025年10月份'提取为'2025-10-01'
                import re
                match = re.match(r'(\d+)年(\d+)月', month_str)
                if match:
                    year, month = match.groups()
                    return f"{year}-{month.zfill(2)}-01"
                return None
            
            df['date'] = df['月份'].apply(parse_month)
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
            df = df.sort_index()
            
            # 过滤掉当月数据（PMI在下月初发布，当月数据可能是前向填充的旧值）
            # 例如：1月获取数据时，只取到12月，避免把12月PMI错误地标注为1月
            from datetime import datetime as dt
            current_month_start = dt.now().replace(day=1)
            df = df[df.index < pd.Timestamp(current_month_start)]
            
            # 过滤日期范围
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            df = df[(df.index >= start_dt) & (df.index <= end_dt)]
            
            # 使用制造业PMI指数（包含新订单信息）
            series = df['制造业-指数'].astype(float)
            
            print(f"[OK] Fetched {len(series)} records for PMI manufacturing (filtered current month)")
            return series
            
        except Exception as e:
            raise DataFetchError(f"Failed to fetch PMI data: {e}")
    
    def _fetch_bond_yield(self, start_date: str, end_date: str, maturity: str = "10年") -> pd.Series:
        """
        获取国债收益率（使用bond_zh_us_rate API）
        
        @param {str} maturity - 期限（"10年"）
        @returns {pd.Series} 国债收益率（%）
        """
        try:
            # 获取中美国债收益率历史数据
            df = self.ak.bond_zh_us_rate()
            
            # 这个API返回的是历史时间序列，列名直接包含"中国国债收益率10年"等
            # 示例列名: ['日期', '中国国债收益率2年', '中国国债收益率5年', '中国国债收益率10年', ...]
            
            # 查找日期列
            date_col = None
            for col in df.columns:
                if '日期' in col or 'date' in col.lower():
                    date_col = col
                    break
            
            if date_col is None:
                # 如果没找到日期列名，使用第一列
                date_col = df.columns[0]
            
            # 查找中国10年期国债收益率列
            yield_col = None
            for col in df.columns:
                if '中国' in col and '国债' in col and '收益率' in col and '10年' in col:
                    yield_col = col
                    break
            
            if yield_col is None:
                raise DataFetchError(f"Cannot find CN 10Y yield column in: {list(df.columns)}")
            
            # 转换日期并设置为索引
            df[date_col] = pd.to_datetime(df[date_col])
            df = df.set_index(date_col)
            df = df.sort_index()
            
            # 提取收益率序列
            series = df[yield_col]
            
            # 过滤时间范围
            if start_date:
                start_dt = pd.to_datetime(start_date)
                series = series[series.index >= start_dt]
            if end_date:
                end_dt = pd.to_datetime(end_date)
                series = series[series.index <= end_dt]
            
            # 确保数据类型为float
            series = pd.to_numeric(series, errors='coerce')
            
            # 删除NaN值
            series = series.dropna()
            
            print(f"[OK] Fetched {len(series)} records for CN bond 10Y yield")
            return series
            
        except Exception as e:
            raise DataFetchError(f"Failed to fetch bond yield data: {e}")
    
    def _fetch_eps_yield(self, start_date: str, end_date: str) -> pd.Series:
        """
        获取全A盈利收益率（E/P = 1/PE）
        
        使用AKShare的stock_a_ttm_lyr接口获取全A市盈率
        然后计算盈利收益率 = 1 / PE
        
        @returns {pd.Series} 盈利收益率（%）
        """
        try:
            # 获取全A市盈率TTM数据
            df = self.ak.stock_a_ttm_lyr()
            
            if df is None or len(df) == 0:
                raise DataFetchError("stock_a_ttm_lyr returned empty data")
            
            # 转换日期
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
            df = df.sort_index()
            
            # 使用中位数PE(TTM)计算盈利收益率
            # middlePETTM是更稳健的指标（不受极值影响）
            pe_series = df['middlePETTM']
            
            # 盈利收益率 = 1 / PE，转换为百分比
            eps_yield = (1 / pe_series) * 100
            
            # 过滤时间范围
            if start_date:
                start_dt = pd.to_datetime(start_date)
                eps_yield = eps_yield[eps_yield.index >= start_dt]
            if end_date:
                end_dt = pd.to_datetime(end_date)
                eps_yield = eps_yield[eps_yield.index <= end_dt]
            
            # 确保数据类型为float
            eps_yield = pd.to_numeric(eps_yield, errors='coerce')
            eps_yield = eps_yield.dropna()
            
            print(f"[OK] Fetched {len(eps_yield)} records for CN EPS yield")
            return eps_yield
            
        except Exception as e:
            raise DataFetchError(f"Failed to fetch EPS yield data: {e}")
    
    def _fetch_etf_flow(self, start_date: str, end_date: str) -> pd.Series:
        """
        获取A500 ETF的5日净申赎近似值（基于成交额）
        
        逻辑：
        1. 成交额 = 成交量 × 平均价格
        2. 成交额大 → 说明有大量资金参与交易
        3. 结合涨跌幅：涨且成交额大 → 资金流入；跌且成交额大 → 资金流出
        4. 计算：成交额 × sign(涨跌幅) = 带方向的资金流
        5. 计算5日滚动和
        
        @returns {pd.Series} A500 ETF 5日滚动净申赎（亿元）
        """
        # A500相关ETF列表
        a500_etf_list = [
            {"code": "159352", "name": "南方中证A500ETF", "weight": 0.50},  # 规模最大
            {"code": "563080", "name": "华夏中证A500ETF", "weight": 0.15},
            {"code": "563050", "name": "易方达中证A500ETF", "weight": 0.15},
            {"code": "563060", "name": "嘉实中证A500ETF", "weight": 0.10},
            {"code": "159353", "name": "华泰柏瑞中证A500ETF", "weight": 0.10}
        ]
        
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        combined_flow = None
        fetch_errors = []
        success_count = 0
        
        print(f"[INFO] Fetching A500 ETF flows ({len(a500_etf_list)} ETFs)...")
        
        for etf_meta in a500_etf_list:
            code = etf_meta['code']
            name = etf_meta['name']
            weight = etf_meta['weight']
            
            try:
                # 获取ETF历史行情
                df = self.ak.fund_etf_hist_em(symbol=code, period="daily", adjust="")
                
                if df is None or df.empty:
                    fetch_errors.append(f"{name}: no data")
                    continue
                
                # 处理日期
                df['date'] = pd.to_datetime(df['日期'], errors='coerce')
                df = df.dropna(subset=['date'])
                df = df.set_index('date').sort_index()
                
                # 日期过滤
                df = df[(df.index >= start_dt) & (df.index <= end_dt)]
                
                if df.empty:
                    fetch_errors.append(f"{name}: no data in date range")
                    continue
                
                # 计算带方向的成交额
                # 成交额（元） × sign(涨跌幅) → 表示资金流向
                turnover = pd.to_numeric(df['成交额'], errors='coerce')  # 单位：元
                pct_change = pd.to_numeric(df['涨跌幅'], errors='coerce') / 100.0  # 百分比转小数
                
                # 带方向成交额 = 成交额 × sign(涨跌幅)
                directional_flow = turnover * pct_change.apply(
                    lambda x: 1 if x > 0 else -1 if x < 0 else 0
                )
                
                # 元 -> 亿元，并应用权重
                directional_flow = (directional_flow / 1e8) * weight
                directional_flow = directional_flow.dropna()
                
                if combined_flow is None:
                    combined_flow = directional_flow
                else:
                    combined_flow = combined_flow.add(directional_flow, fill_value=0.0)
                
                success_count += 1
                print(f"[OK] Fetched {len(directional_flow)} records for {name} (weight: {weight})")
                
            except Exception as e:
                fetch_errors.append(f"{name}: {str(e)}")
                print(f"[WARN] Failed to fetch {name}: {e}")
                continue
        
        if combined_flow is None or combined_flow.empty:
            error_msg = "; ".join(fetch_errors) if fetch_errors else "unknown reason"
            raise DataFetchError(f"Failed to fetch A500 ETF flow data: {error_msg}")
        
        # 计算5日滚动和
        combined_flow = combined_flow.sort_index()
        rolling_flow = combined_flow.rolling(window=5, min_periods=1).sum()
        rolling_flow = rolling_flow[(rolling_flow.index >= start_dt) & (rolling_flow.index <= end_dt)]
        
        print(f"[OK] Aggregated {success_count}/{len(a500_etf_list)} A500 ETFs into 5D rolling series with {len(rolling_flow)} records")
        return rolling_flow


class AKForexFetcher:
    """
    东方财富外汇历史数据获取器（基于 AkShare）
    
    数据来源：https://quote.eastmoney.com/cnyrate/
    """

    def fetch(
        self,
        symbol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> pd.Series:
        """
        获取外汇历史数据，例如 USD/CNH。

        @param symbol: 外汇代码，如 'USDCNH'
        @param start_date: 开始日期
        @param end_date: 结束日期
        @returns: pd.Series，索引为日期，数值为收盘价
        """
        try:
            import akshare as ak
        except ImportError as exc:
            raise DataFetchError("akshare not installed. Run: pip install akshare") from exc

        try:
            df = ak.forex_hist_em(symbol=symbol.upper())
        except Exception as exc:
            raise DataFetchError(f"Failed to fetch forex {symbol} from EastMoney: {exc}") from exc

        if df is None or df.empty:
            raise DataFetchError(f"No forex data returned for {symbol}")

        # 原始列名为中文，按位置重命名
        df.columns = ["date", "symbol", "name", "close", "open", "high", "low", "pct_change"]
        df["date"] = pd.to_datetime(df["date"])
        df.sort_values("date", inplace=True)

        if start_date:
            df = df[df["date"] >= pd.to_datetime(start_date)]
        if end_date:
            df = df[df["date"] <= pd.to_datetime(end_date)]

        if df.empty:
            raise DataFetchError(f"No forex data for {symbol} in requested range")

        series = pd.Series(df["close"].astype(float).values, index=df["date"])
        print(f"[OK] Fetched {len(series)} forex records for {symbol} from EastMoney")
        return series


class CSVImporter:
    """
    CSV文件导入器
    
    用于导入中国市场特有数据（两融余额、北向成交等）
    作为akshare的备用方案
    """
    
    def __init__(self):
        """初始化CSV导入器"""
        pass
    
    def import_csv(
        self,
        file_path: str,
        date_col: str = 'date',
        value_col: str = 'value',
        date_format: Optional[str] = None,
        skiprows: Optional[int] = None,
        encoding: str = 'utf-8'
    ) -> pd.Series:
        """
        从CSV文件导入时间序列数据
        
        @param {str} file_path - CSV文件路径
        @param {str} date_col - 日期列名
        @param {str} value_col - 数值列名
        @param {Optional[str]} date_format - 日期格式（如 '%Y-%m-%d'）
        @param {Optional[int]} skiprows - 跳过的行数
        @param {str} encoding - 文件编码
        @returns {pd.Series} 时间序列数据
        
        @example
        >>> importer = CSVImporter()
        >>> margin = importer.import_csv('cn_margin_balance.csv')
        """
        try:
            # 读取CSV
            df = pd.read_csv(
                file_path,
                skiprows=skiprows,
                encoding=encoding
            )
            
            # 检查列是否存在
            if date_col not in df.columns:
                raise DataFetchError(f"Date column '{date_col}' not found in CSV")
            if value_col not in df.columns:
                raise DataFetchError(f"Value column '{value_col}' not found in CSV")
            
            # 解析日期
            if date_format:
                df[date_col] = pd.to_datetime(df[date_col], format=date_format)
            else:
                df[date_col] = pd.to_datetime(df[date_col])
            
            # 转换为Series
            df = df.set_index(date_col)
            series = df[value_col]
            
            # 转换为数值类型
            series = pd.to_numeric(series, errors='coerce')
            
            # 删除NaN
            series = series.dropna()
            
            # 排序
            series = series.sort_index()
            
            print(f"[OK] Imported {len(series)} records from {file_path}")
            return series
        
        except Exception as e:
            raise DataFetchError(f"Failed to import {file_path}: {e}")
    
    def import_multiple_csvs(
        self,
        file_configs: List[Dict[str, Any]]
    ) -> Dict[str, pd.Series]:
        """
        批量导入多个CSV文件
        
        @param {List[Dict]} file_configs - 文件配置列表，每个配置包含file_path和其他参数
        @returns {Dict[str, pd.Series]} 序列字典 {code: data}
        
        @example
        >>> configs = [
        ...     {'code': 'MARGIN', 'file_path': 'margin.csv', 'value_col': 'balance'},
        ...     {'code': 'NORTH', 'file_path': 'north.csv', 'value_col': 'ratio'}
        ... ]
        >>> data = importer.import_multiple_csvs(configs)
        """
        results = {}
        
        for config in file_configs:
            code = config.pop('code')
            file_path = config.get('file_path')
            
            try:
                data = self.import_csv(**config)
                results[code] = data
            except DataFetchError as e:
                print(f"[ERROR] Failed to import {code} from {file_path}: {e}")
                results[code] = pd.Series(dtype=float)
        
        return results


class StooqFetcher:
    """
    Stooq数据获取器（通过pandas_datareader）
    
    用于获取外汇数据，特别是CNH（离岸人民币）
    Stooq是免费的波兰金融数据提供商
    """
    
    def __init__(self):
        """
        初始化Stooq获取器
        """
        try:
            import pandas_datareader as pdr
            self.pdr = pdr
            self._available = True
        except ImportError:
            self._available = False
            print("[WARNING] pandas_datareader not installed. Install with: pip install pandas-datareader")
    
    def fetch(
        self,
        symbol: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.Series:
        """
        从Stooq获取数据
        
        @param {str} symbol - 数据标识符
            - "CNH" - 离岸人民币（USD/CNH）
            - "CNY" - 在岸人民币（USD/CNY）
        @param {datetime} start_date - 开始日期
        @param {datetime} end_date - 结束日期
        @returns {pd.Series} 时间序列数据
        
        @example
        >>> fetcher = StooqFetcher()
        >>> cnh = fetcher.fetch("CNH", start_date, end_date)
        """
        if not self._available:
            raise DataFetchError("pandas_datareader is not available")
        
        try:
            # 获取数据（Stooq返回的数据是倒序的）
            df = self.pdr.get_data_stooq(symbol, start_date, end_date)
            
            if df is None or len(df) == 0:
                raise DataFetchError(f"No data returned for {symbol}")
            
            # 转换为正序
            df = df.sort_index()
            
            series = df['Close'].astype(float)

            # Stooq的CNH/CNY报价为“100美元兑本币”，需转换为USD/CNH
            if symbol.upper() in {"CNH", "CNY"}:
                series = 100.0 / series
            
            print(f"[OK] Fetched {len(series)} records for {symbol}")
            return series
            
        except Exception as e:
            raise DataFetchError(f"Failed to fetch from Stooq: {e}")


class ExchangeRateHostFetcher:
    """
    ExchangeRate.host 汇率获取器
    
    免费提供多货币历史汇率，支持按日期范围查询。
    文档：https://exchangerate.host/#/#docs
    """

    BASE_URL = "https://api.exchangerate.host/timeseries"

    def fetch(
        self,
        base: str = "USD",
        symbol: str = "CNH",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        retry: int = 3,
        retry_delay: float = 1.0,
    ) -> pd.Series:
        """
        获取指定货币对的汇率时间序列（默认 USD/CNH）
        
        @param base: 基础货币（默认 USD）
        @param symbol: 目标货币（默认 CNH）
        @param start_date: 开始日期
        @param end_date: 结束日期
        @returns: pd.Series，索引为日期，数值为汇率
        """
        if start_date is None:
            end_date = end_date or datetime.utcnow()
            start_date = end_date - timedelta(days=730)
        if end_date is None:
            end_date = datetime.utcnow()

        base = base.upper()
        symbol = symbol.upper()

        params = {
            "base": base,
            "symbols": symbol,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
        }

        for attempt in range(retry):
            try:
                response = requests.get(self.BASE_URL, params=params, timeout=10)
                response.raise_for_status()
                payload = response.json()

                if not payload.get("success", False):
                    raise DataFetchError(f"ExchangeRate.host returned error: {payload}")

                rates = payload.get("rates", {})
                if not rates:
                    raise DataFetchError("Empty rates returned")

                data = {
                    pd.to_datetime(date_str): values.get(symbol)
                    for date_str, values in rates.items()
                    if values and values.get(symbol) is not None
                }

                if not data:
                    raise DataFetchError("No valid data points returned")

                series = pd.Series(data, dtype=float).sort_index()
                print(f"[OK] Fetched {len(series)} records for {base}/{symbol} from ExchangeRate.host")
                return series

            except (requests.RequestException, ValueError) as exc:
                if attempt < retry - 1:
                    print(f"[WARNING] Attempt {attempt + 1} failed for ExchangeRateHost {base}/{symbol}: {exc}")
                    time.sleep(retry_delay)
                else:
                    raise DataFetchError(f"Failed to fetch {base}/{symbol} after {retry} attempts: {exc}")


class DataSourceManager:
    """
    数据源管理器
    
    统一管理所有数据源，提供高级接口
    """
    
    def __init__(self, fred_api_key: Optional[str] = None):
        """
        初始化数据源管理器
        
        @param {Optional[str]} fred_api_key - FRED API密钥
        """
        self.fred_fetcher = FREDFetcher(fred_api_key)
        self.yf_fetcher = YFinanceFetcher()
        # 提供别名，兼容不同代码引用
        self.yfinance_fetcher = self.yf_fetcher
        self.akshare_fetcher = AKShareFetcher()
        self.stooq_fetcher = StooqFetcher()  # ← 新增Stooq支持
        self.ak_forex_fetcher = AKForexFetcher()
        self.fx_fetcher = ExchangeRateHostFetcher()
        self.csv_importer = CSVImporter()
    
    def fetch_by_config(
        self,
        indicator_config: Dict[str, Any],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> pd.Series:
        """
        根据指标配置获取数据
        
        @param {Dict} indicator_config - 指标配置（包含source和ticker信息）
        @returns {pd.Series} 时间序列数据
        
        @example
        >>> config = {
        ...     'code': 'VIX_LOG',
        ...     'source': 'yfinance',
        ...     'ticker': '^VIX'
        ... }
        >>> data = manager.fetch_by_config(config)
        """
        source = indicator_config.get('source', '').lower()
        ticker = indicator_config.get('ticker')
        code = indicator_config.get('code', 'UNKNOWN')
        
        try:
            if source == 'fred':
                return self.fred_fetcher.fetch(ticker, start_date, end_date)
            
            elif source == 'yfinance':
                if isinstance(ticker, (list, tuple)):
                    tickers = list(ticker)
                    if len(tickers) == 2:
                        return self.yf_fetcher.fetch_pair(
                            tickers[0],
                            tickers[1],
                            start_date,
                            end_date
                        )
                    else:
                        series_tuple = tuple(
                            self.yf_fetcher.fetch(t, start_date, end_date)
                            for t in tickers
                        )
                        return series_tuple
                return self.yf_fetcher.fetch(ticker, start_date, end_date)
            
            elif source == 'akshare':
                # 使用akshare获取中国市场数据
                symbol = indicator_config.get('symbol', ticker)
                if isinstance(symbol, (list, tuple)):
                    series_tuple = tuple(
                        self.akshare_fetcher.fetch(sym, start_date, end_date)
                        for sym in symbol
                    )
                    return series_tuple
                return self.akshare_fetcher.fetch(symbol, start_date, end_date)
            
            elif source == 'stooq':
                # 使用Stooq获取外汇数据（特别是CNH）
                symbol = indicator_config.get('symbol', ticker)
                return self.stooq_fetcher.fetch(symbol, start_date, end_date)
            
            elif source in {'akshare_fx', 'ak_forex', 'eastmoney_fx'}:
                symbol = indicator_config.get('symbol') or indicator_config.get('ticker')
                if not symbol:
                    raise DataFetchError("akshare forex fetcher requires 'symbol' or 'ticker'")
                return self.ak_forex_fetcher.fetch(
                    symbol=str(symbol),
                    start_date=start_date,
                    end_date=end_date,
                )
            
            elif source in ('exchangerate', 'exchangerate_host', 'exchange_rate_host'):
                base_currency = indicator_config.get('base', 'USD')
                target_currency = indicator_config.get('symbol') or indicator_config.get('ticker')
                if not target_currency:
                    raise DataFetchError("ExchangeRateHost requires 'symbol' or 'ticker' for target currency")
                return self.fx_fetcher.fetch(
                    base=str(base_currency),
                    symbol=str(target_currency),
                    start_date=start_date,
                    end_date=end_date,
                )
            
            elif source == 'csv':
                # CSV需要事先导入，这里返回空
                print(f"[WARNING] {code} requires manual CSV import")
                return pd.Series(dtype=float)
            
            else:
                raise DataFetchError(f"Unknown source: {source}")
        
        except DataFetchError as e:
            print(f"[ERROR] Failed to fetch {code}: {e}")
            return pd.Series(dtype=float)
    
    def fetch_all_indicators(
        self,
        indicator_configs: List[Dict[str, Any]],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, pd.Series]:
        """
        批量获取所有指标数据
        
        @param {List[Dict]} indicator_configs - 指标配置列表
        @returns {Dict[str, pd.Series]} 数据字典 {code: series}
        """
        results = {}
        
        print(f"\n[INFO] Fetching {len(indicator_configs)} indicators...")
        
        for config in indicator_configs:
            code = config.get('code', 'UNKNOWN')
            print(f"\n[INFO] Fetching {code}...")
            
            data = self.fetch_by_config(config, start_date, end_date)
            results[code] = data
            
            # 简短延迟避免API限制
            time.sleep(0.2)
        
        print(f"\n[OK] Fetched {len([d for d in results.values() if len(d) > 0])}/{len(indicator_configs)} indicators successfully")
        
        return results


def align_to_business_days(
    series: pd.Series,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> pd.Series:
    """
    将序列对齐到工作日（business days）
    
    @param {pd.Series} series - 输入序列
    @param {Optional[datetime]} start_date - 开始日期
    @param {Optional[datetime]} end_date - 结束日期
    @returns {pd.Series} 对齐后的序列
    """
    if len(series) == 0:
        return series
    
    # 确定日期范围
    if start_date is None:
        start_date = series.index.min()
    if end_date is None:
        end_date = series.index.max()
    
    # 创建工作日范围
    business_days = pd.bdate_range(start=start_date, end=end_date)
    
    # 重索引并前向填充
    aligned = series.reindex(business_days, method='ffill')
    
    return aligned


def clean_series(
    series: pd.Series,
    remove_outliers: bool = False,
    outlier_std: float = 5.0,
    interpolate: bool = False
) -> pd.Series:
    """
    清洗时间序列数据
    
    @param {pd.Series} series - 输入序列
    @param {bool} remove_outliers - 是否移除异常值
    @param {float} outlier_std - 异常值标准差倍数
    @param {bool} interpolate - 是否插值填充缺失值
    @returns {pd.Series} 清洗后的序列
    """
    cleaned = series.copy()
    
    # 移除异常值（使用中位数和MAD，对异常值更稳健）
    if remove_outliers and len(cleaned) > 0:
        median = cleaned.median()
        mad = (cleaned - median).abs().median()
        
        if mad > 0:
            # 使用MAD方法
            mad_score = (cleaned - median).abs() / mad
            # MAD-Z > 3.5 通常被认为是异常值
            threshold = outlier_std * 1.4826  # 转换因子
            cleaned = cleaned.where(mad_score <= threshold)
        else:
            # 如果MAD为0，使用标准差方法
            mean = cleaned.mean()
            std = cleaned.std()
            if std > 0:
                lower_bound = mean - outlier_std * std
                upper_bound = mean + outlier_std * std
                cleaned = cleaned.where((cleaned >= lower_bound) & (cleaned <= upper_bound))
    
    # 插值
    if interpolate:
        cleaned = cleaned.interpolate(method='linear', limit_direction='forward')
    
    # 删除仍然为NaN的值
    cleaned = cleaned.dropna()
    
    return cleaned


def validate_series(
    series: pd.Series,
    min_length: int = 60,
    max_gap_days: int = 30
) -> Tuple[bool, str]:
    """
    验证时间序列数据质量
    
    @param {pd.Series} series - 输入序列
    @param {int} min_length - 最小长度要求
    @param {int} max_gap_days - 最大允许间隔天数
    @returns {Tuple[bool, str]} (是否通过, 错误信息)
    """
    if isinstance(series, pd.DataFrame):
        if 'value_raw' in series.columns:
            series_to_check = series['value_raw']
        else:
            series_to_check = series.iloc[:, 0]
    else:
        series_to_check = series

    if len(series_to_check) == 0:
        return False, "Series is empty"
    
    if len(series_to_check) < min_length:
        return False, f"Series too short: {len(series_to_check)} < {min_length}"
    
    # 检查时间间隔
    if len(series_to_check) > 1:
        time_diffs = series_to_check.index.to_series().diff().dt.days
        max_gap = time_diffs.max()
        
        if pd.notna(max_gap) and max_gap > max_gap_days:
            return False, f"Large gap detected: {max_gap} days"
    
    # 检查数据质量
    if series_to_check.isna().all():
        return False, "All values are NaN"
    
    return True, "OK"

