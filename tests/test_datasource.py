"""
数据源模块单元测试

注意：部分测试需要网络连接和API密钥
"""

import pytest
import pandas as pd
import numpy as np
import tempfile
import os
from datetime import datetime, timedelta

from core.datasource import (
    FREDFetcher, YFinanceFetcher, CSVImporter,
    DataSourceManager, DataFetchError,
    align_to_business_days, clean_series, validate_series
)


class TestCSVImporter:
    """CSV导入器测试（不需要网络）"""
    
    @pytest.fixture
    def temp_csv_file(self):
        """创建临时CSV文件"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='')
        temp_file.write('date,value\n')
        temp_file.write('2024-01-01,100.0\n')
        temp_file.write('2024-01-02,102.5\n')
        temp_file.write('2024-01-03,105.0\n')
        temp_file.write('2024-01-04,103.5\n')
        temp_file.write('2024-01-05,107.0\n')
        temp_file.close()
        
        yield temp_file.name
        
        # 清理
        try:
            os.unlink(temp_file.name)
        except:
            pass
    
    def test_import_csv_basic(self, temp_csv_file):
        """测试基本CSV导入"""
        importer = CSVImporter()
        
        series = importer.import_csv(temp_csv_file)
        
        assert len(series) == 5
        assert series.iloc[0] == 100.0
        assert series.iloc[-1] == 107.0
        assert isinstance(series.index, pd.DatetimeIndex)
    
    def test_import_csv_custom_columns(self):
        """测试自定义列名"""
        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='')
        temp_file.write('timestamp,price\n')
        temp_file.write('2024-01-01,50.0\n')
        temp_file.write('2024-01-02,55.0\n')
        temp_file.close()
        
        try:
            importer = CSVImporter()
            series = importer.import_csv(
                temp_file.name,
                date_col='timestamp',
                value_col='price'
            )
            
            assert len(series) == 2
            assert series.iloc[0] == 50.0
        finally:
            os.unlink(temp_file.name)
    
    def test_import_csv_with_nan(self):
        """测试包含NaN的CSV"""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='')
        temp_file.write('date,value\n')
        temp_file.write('2024-01-01,100\n')
        temp_file.write('2024-01-02,\n')  # 空值
        temp_file.write('2024-01-03,105\n')
        temp_file.close()
        
        try:
            importer = CSVImporter()
            series = importer.import_csv(temp_file.name)
            
            # NaN应该被移除
            assert len(series) == 2
            assert series.iloc[0] == 100
            assert series.iloc[1] == 105
        finally:
            os.unlink(temp_file.name)
    
    def test_import_csv_file_not_found(self):
        """测试文件不存在"""
        importer = CSVImporter()
        
        with pytest.raises(DataFetchError):
            importer.import_csv('nonexistent_file.csv')
    
    def test_import_csv_invalid_column(self, temp_csv_file):
        """测试列名不存在"""
        importer = CSVImporter()
        
        with pytest.raises(DataFetchError, match="not found"):
            importer.import_csv(temp_csv_file, value_col='nonexistent')
    
    def test_import_multiple_csvs(self):
        """测试批量导入"""
        # 创建两个临时文件
        file1 = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='')
        file1.write('date,value\n2024-01-01,100\n')
        file1.close()
        
        file2 = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='')
        file2.write('date,value\n2024-01-01,200\n')
        file2.close()
        
        try:
            importer = CSVImporter()
            configs = [
                {'code': 'DATA1', 'file_path': file1.name},
                {'code': 'DATA2', 'file_path': file2.name}
            ]
            
            results = importer.import_multiple_csvs(configs)
            
            assert 'DATA1' in results
            assert 'DATA2' in results
            assert len(results['DATA1']) == 1
            assert len(results['DATA2']) == 1
        finally:
            os.unlink(file1.name)
            os.unlink(file2.name)


class TestDataAlignment:
    """数据对齐和清洗测试"""
    
    def test_align_to_business_days(self):
        """测试对齐到工作日"""
        # 创建不规则日期的序列
        dates = pd.to_datetime(['2024-01-02', '2024-01-05', '2024-01-10'])
        series = pd.Series([100, 105, 110], index=dates)
        
        aligned = align_to_business_days(
            series,
            start_date=datetime(2024, 1, 2),
            end_date=datetime(2024, 1, 10)
        )
        
        # 应该有更多的日期（工作日）
        assert len(aligned) > len(series)
        # 缺失的日期应该被前向填充
        assert aligned.loc['2024-01-03'] == 100
        assert aligned.loc['2024-01-08'] == 105
    
    def test_clean_series_basic(self):
        """测试基本清洗"""
        data = pd.Series([10, 12, 11, np.nan, 13, 14])
        
        cleaned = clean_series(data)
        
        # NaN应该被移除
        assert len(cleaned) == 5
        assert not cleaned.isna().any()
    
    def test_clean_series_remove_outliers(self):
        """测试移除异常值"""
        # 正常数据 + 异常值
        data = pd.Series([10, 11, 12, 1000, 13, 14, 15])
        
        cleaned = clean_series(data, remove_outliers=True, outlier_std=3)
        
        # 异常值1000应该被移除
        assert 1000 not in cleaned.values
        assert len(cleaned) < len(data)
    
    def test_clean_series_interpolate(self):
        """测试插值"""
        data = pd.Series([10, np.nan, 14, np.nan, 18])
        
        cleaned = clean_series(data, interpolate=True)
        
        # 插值后应该没有NaN
        assert not cleaned.isna().any()
        assert len(cleaned) == 5
    
    def test_validate_series_valid(self):
        """测试有效序列验证"""
        dates = pd.date_range('2024-01-01', periods=100, freq='B')
        series = pd.Series(range(100), index=dates)
        
        is_valid, message = validate_series(series, min_length=60)
        
        assert is_valid is True
        assert message == "OK"
    
    def test_validate_series_too_short(self):
        """测试序列过短"""
        series = pd.Series([1, 2, 3])
        
        is_valid, message = validate_series(series, min_length=10)
        
        assert is_valid is False
        assert "too short" in message.lower()
    
    def test_validate_series_empty(self):
        """测试空序列"""
        series = pd.Series([], dtype=float)
        
        is_valid, message = validate_series(series)
        
        assert is_valid is False
        assert "empty" in message.lower()
    
    def test_validate_series_large_gap(self):
        """测试大间隔"""
        dates = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 2),
            datetime(2024, 3, 1)  # 大间隔
        ]
        series = pd.Series([1, 2, 3], index=pd.DatetimeIndex(dates))
        
        is_valid, message = validate_series(series, min_length=3, max_gap_days=30)
        
        assert is_valid is False
        assert "gap" in message.lower()


@pytest.mark.network
class TestFREDFetcher:
    """FRED数据获取测试（需要网络和API密钥）"""
    
    @pytest.fixture
    def fetcher(self):
        """创建FRED fetcher"""
        return FREDFetcher()
    
    def test_fred_init_without_key(self):
        """测试无API密钥初始化"""
        fetcher = FREDFetcher(api_key=None)
        # 应该能初始化，但可能无法使用
        assert fetcher is not None
    
    @pytest.mark.skipif(not os.getenv('FRED_API_KEY'), reason="FRED_API_KEY not set")
    def test_fred_fetch_basic(self, fetcher):
        """测试基本FRED数据获取"""
        if not fetcher.fred:
            pytest.skip("FRED not initialized")
        
        # 获取最近30天的数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        try:
            data = fetcher.fetch('RRPONTSYD', start_date, end_date)
            
            assert len(data) > 0
            assert isinstance(data, pd.Series)
            assert isinstance(data.index, pd.DatetimeIndex)
        except DataFetchError as e:
            pytest.skip(f"FRED fetch failed: {e}")


@pytest.mark.network
class TestYFinanceFetcher:
    """yfinance数据获取测试（需要网络）"""
    
    @pytest.fixture
    def fetcher(self):
        """创建yfinance fetcher"""
        return YFinanceFetcher()
    
    def test_yfinance_init(self, fetcher):
        """测试初始化"""
        assert fetcher is not None
    
    @pytest.mark.skipif(not os.getenv('TEST_NETWORK'), reason="Network test disabled")
    def test_yfinance_fetch_basic(self, fetcher):
        """测试基本yfinance数据获取"""
        if not fetcher.yf:
            pytest.skip("yfinance not installed")
        
        # 获取最近30天的SPY数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        try:
            data = fetcher.fetch('SPY', start_date, end_date)
            
            assert len(data) > 0
            assert isinstance(data, pd.Series)
        except DataFetchError as e:
            pytest.skip(f"yfinance fetch failed: {e}")
    
    @pytest.mark.skipif(not os.getenv('TEST_NETWORK'), reason="Network test disabled")
    def test_yfinance_fetch_pair(self, fetcher):
        """测试获取配对数据"""
        if not fetcher.yf:
            pytest.skip("yfinance not installed")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        try:
            data1, data2 = fetcher.fetch_pair('IWM', 'SPY', start_date, end_date)
            
            assert len(data1) > 0
            assert len(data2) > 0
            # 索引应该对齐
            assert len(data1) == len(data2)
        except DataFetchError as e:
            pytest.skip(f"yfinance fetch pair failed: {e}")


class TestDataSourceManager:
    """数据源管理器测试"""
    
    @pytest.fixture
    def manager(self):
        """创建数据源管理器"""
        return DataSourceManager()
    
    def test_manager_init(self, manager):
        """测试初始化"""
        assert manager is not None
        assert manager.fred_fetcher is not None
        assert manager.yf_fetcher is not None
        assert manager.csv_importer is not None
    
    def test_fetch_by_config_csv(self, manager):
        """测试根据配置获取（CSV类型）"""
        config = {
            'code': 'TEST',
            'source': 'csv',
            'ticker': 'dummy.csv'
        }
        
        # CSV需要手动导入，应该返回空Series并给出警告
        data = manager.fetch_by_config(config)
        
        assert isinstance(data, pd.Series)
        assert len(data) == 0
    
    def test_fetch_by_config_unknown_source(self, manager):
        """测试未知数据源"""
        config = {
            'code': 'TEST',
            'source': 'unknown',
            'ticker': 'dummy'
        }
        
        data = manager.fetch_by_config(config)
        
        # 应该返回空Series
        assert isinstance(data, pd.Series)
        assert len(data) == 0


if __name__ == '__main__':
    # 运行测试（跳过需要网络的测试）
    pytest.main([__file__, '-v', '-m', 'not network'])

