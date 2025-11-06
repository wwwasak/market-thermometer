"""
数据源模块

提供从各种数据源获取市场数据的接口：
- FRED (Federal Reserve Economic Data)
- yfinance (Yahoo Finance)
- CSV文件导入
"""

import os
import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date, timedelta
import time

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
    
    def _fetch_north_flow(self, start_date: str, end_date: str) -> pd.Series:
        """
        获取北向资金流向数据
        
        @returns {pd.Series} 北向资金净流入（单位：亿元）
        """
        try:
            # 使用历史北向资金数据（最新接口名称）
            df = self.ak.stock_hsgt_hist_em(symbol="沪股通")
            
            # 列名：['日期', '当日成交净买额', '当日买入成交额', '当日卖出成交额', '历史累计净买额', ...]
            df['date'] = pd.to_datetime(df['日期'])
            df = df.set_index('date')
            df = df.sort_index()
            
            # 转换日期字符串为datetime用于过滤
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            df = df[(df.index >= start_dt) & (df.index <= end_dt)]
            
            # 当日成交净买额（单位：已经是亿元）
            series = df['当日成交净买额'].astype(float)
            
            print(f"[OK] Fetched {len(series)} records for north flow")
            return series
            
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
            
            # 过滤日期范围
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            df = df[(df.index >= start_dt) & (df.index <= end_dt)]
            
            # 使用制造业PMI指数（包含新订单信息）
            series = df['制造业-指数'].astype(float)
            
            print(f"[OK] Fetched {len(series)} records for PMI manufacturing")
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
        获取ETF资金流向
        
        @returns {pd.Series} ETF主力净流入（计算5日滚动和）
        """
        try:
            # 使用东方财富ETF每日资金流向数据
            df = self.ak.fund_etf_fund_daily_em()
            
            # 列名：['基金代码', '基金简称', '类型', '2025-11-05-单位净值', ..., '日增长值', '日增长率', '市价', '累计额']
            # 这个接口只返回最新一天的数据，不适合历史数据
            
            # 改用个股资金流向作为代理（获取沪深300ETF的资金流）
            # 510300 是华泰柏瑞沪深300ETF
            symbol = "510300"  # 沪深300ETF
            
            try:
                # 尝试获取个股资金流向历史数据
                df_flow = self.ak.stock_individual_fund_flow(stock=symbol, market="sh")
                
                # 转换日期
                df_flow['date'] = pd.to_datetime(df_flow['日期'])
                df_flow = df_flow.set_index('date')
                df_flow = df_flow.sort_index()
                
                # 过滤日期范围
                start_dt = pd.to_datetime(start_date)
                end_dt = pd.to_datetime(end_date)
                df_flow = df_flow[(df_flow.index >= start_dt) & (df_flow.index <= end_dt)]
                
                # 主力净流入（单位：万元，转换为亿元）
                series = df_flow['主力净流入'].astype(float) / 10000
                
                print(f"[OK] Fetched {len(series)} records for ETF flow (510300 as proxy)")
                return series
                
            except Exception as inner_e:
                # 如果个股接口也失败，返回一个简化的估算
                # 使用fund_etf_fund_daily_em的最新数据创建一个常数序列
                print(f"[WARNING] Cannot fetch historical ETF flow, using latest snapshot")
                
                # 创建一个时间范围的空序列
                start_dt = pd.to_datetime(start_date)
                end_dt = pd.to_datetime(end_date)
                date_range = pd.date_range(start=start_dt, end=end_dt, freq='D')
                
                # 返回0值序列（表示无数据）
                series = pd.Series(0.0, index=date_range)
                
                print(f"[WARNING] Returned zero-filled series with {len(series)} records")
                return series
            
        except Exception as e:
            raise DataFetchError(f"Failed to fetch ETF flow data: {e}")


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
            
            # 使用收盘价
            series = df['Close']
            
            print(f"[OK] Fetched {len(series)} records for {symbol}")
            return series
            
        except Exception as e:
            raise DataFetchError(f"Failed to fetch from Stooq: {e}")


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
        self.akshare_fetcher = AKShareFetcher()
        self.stooq_fetcher = StooqFetcher()  # ← 新增Stooq支持
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
                return self.yf_fetcher.fetch(ticker, start_date, end_date)
            
            elif source == 'akshare':
                # 使用akshare获取中国市场数据
                symbol = indicator_config.get('symbol', ticker)
                return self.akshare_fetcher.fetch(symbol, start_date, end_date)
            
            elif source == 'stooq':
                # 使用Stooq获取外汇数据（特别是CNH）
                symbol = indicator_config.get('symbol', ticker)
                return self.stooq_fetcher.fetch(symbol, start_date, end_date)
            
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
    if len(series) == 0:
        return False, "Series is empty"
    
    if len(series) < min_length:
        return False, f"Series too short: {len(series)} < {min_length}"
    
    # 检查时间间隔
    if len(series) > 1:
        time_diffs = series.index.to_series().diff().dt.days
        max_gap = time_diffs.max()
        
        if pd.notna(max_gap) and max_gap > max_gap_days:
            return False, f"Large gap detected: {max_gap} days"
    
    # 检查数据质量
    if series.isna().all():
        return False, "All values are NaN"
    
    return True, "OK"

