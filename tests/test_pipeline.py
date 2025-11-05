"""
数据流水线模块单元测试
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import tempfile
import os

from core.pipeline import MarketPipeline, PipelineError
from core.config import Config


class TestMarketPipeline:
    """市场流水线测试"""
    
    @pytest.fixture
    def temp_db(self):
        """创建临时数据库"""
        temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_file.close()
        
        db_url = f'sqlite:///{temp_file.name}'
        
        yield db_url
        
        # 清理
        try:
            os.unlink(temp_file.name)
        except:
            pass
    
    @pytest.fixture
    def pipeline(self, temp_db):
        """创建流水线实例"""
        return MarketPipeline(market='US', database_url=temp_db)
    
    def test_pipeline_init(self, pipeline):
        """测试流水线初始化"""
        assert pipeline is not None
        assert pipeline.market == 'US'
        assert pipeline.data_source is not None
        assert pipeline.repository is not None
        assert pipeline.config is not None
    
    def test_transform_data_basic(self, pipeline):
        """测试基本数据转换"""
        # 创建测试数据
        dates = pd.date_range('2024-01-01', periods=100, freq='B')
        raw_data = {
            'TEST1': pd.Series(range(100, 200), index=dates),
            'TEST2': pd.Series(range(200, 300), index=dates)
        }
        
        # 模拟指标配置
        pipeline.indicators = [
            {'code': 'TEST1', 'transform': 'raw'},
            {'code': 'TEST2', 'transform': 'raw'}
        ]
        
        transformed = pipeline.transform_data(raw_data)
        
        assert 'TEST1' in transformed
        assert 'TEST2' in transformed
        assert len(transformed['TEST1']) == 100
    
    def test_calculate_scores_basic(self, pipeline):
        """测试评分计算"""
        # 创建测试数据
        dates = pd.date_range('2024-01-01', periods=100, freq='B')
        
        # 生成随机数据
        np.random.seed(42)
        transformed_data = {
            'TEST1': pd.Series(np.random.randn(100) * 10 + 100, index=dates),
            'TEST2': pd.Series(np.random.randn(100) * 5 + 50, index=dates)
        }
        
        # 模拟指标配置
        pipeline.indicators = [
            {'code': 'TEST1', 'direction': 'up_good'},
            {'code': 'TEST2', 'direction': 'down_good'}
        ]
        
        scores = pipeline.calculate_scores(transformed_data, view_type='daily')
        
        assert len(scores) > 0
        assert 'TEST1_z' in scores.columns or 'TEST1_score' in scores.columns
    
    def test_calculate_scores_weekly(self, pipeline):
        """测试周度评分计算"""
        dates = pd.date_range('2024-01-01', periods=100, freq='B')
        
        np.random.seed(42)
        transformed_data = {
            'TEST1': pd.Series(np.random.randn(100) * 10 + 100, index=dates)
        }
        
        pipeline.indicators = [
            {'code': 'TEST1', 'direction': 'up_good'}
        ]
        
        scores = pipeline.calculate_scores(transformed_data, view_type='weekly')
        
        # 周度数据应该更少
        assert len(scores) < 100
        assert len(scores) > 10
    
    def test_apply_confirm_layer_basic(self, pipeline):
        """测试确认层应用"""
        # 创建测试评分数据
        dates = pd.date_range('2024-01-01', periods=50, freq='B')
        
        scores_df = pd.DataFrame({
            'TEST1_score': np.random.randint(0, 100, 50),
            'TEST2_score': np.random.randint(0, 100, 50)
        }, index=dates)
        
        pipeline.indicators = [
            {'code': 'TEST1'},
            {'code': 'TEST2'}
        ]
        
        result = pipeline.apply_confirm_layer(scores_df, view_type='daily')
        
        # 确认层应该返回结果
        assert isinstance(result, dict)
    
    def test_params_hash_calculation(self, pipeline):
        """测试参数哈希计算"""
        hash1 = pipeline._calculate_params_hash()
        
        assert isinstance(hash1, str)
        assert len(hash1) == 16
        
        # 相同配置应该产生相同哈希
        hash2 = pipeline._calculate_params_hash()
        assert hash1 == hash2
    
    def test_empty_data_handling(self, pipeline):
        """测试空数据处理"""
        empty_data = {}
        
        transformed = pipeline.transform_data(empty_data)
        assert len(transformed) == 0
    
    def test_invalid_transform(self, pipeline):
        """测试无效转换"""
        dates = pd.date_range('2024-01-01', periods=50, freq='B')
        raw_data = {
            'TEST1': pd.Series(range(50), index=dates)
        }
        
        pipeline.indicators = [
            {'code': 'TEST1', 'transform': 'invalid_transform'}
        ]
        
        # 应该处理错误并跳过
        transformed = pipeline.transform_data(raw_data)
        
        # 无效转换应该被跳过
        assert 'TEST1' not in transformed or len(transformed) == 0


@pytest.mark.integration
class TestPipelineIntegration:
    """流水线集成测试"""
    
    @pytest.fixture
    def temp_db(self):
        """创建临时数据库"""
        temp_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_file.close()
        
        db_url = f'sqlite:///{temp_file.name}'
        
        # 初始化数据库
        from storage.migrate import init_database
        init_database(db_url)
        
        yield db_url
        
        # 清理
        try:
            os.unlink(temp_file.name)
        except:
            pass
    
    def test_save_to_database_basic(self, temp_db):
        """测试保存到数据库"""
        pipeline = MarketPipeline(market='US', database_url=temp_db)
        
        # 创建测试数据
        dates = pd.date_range('2024-01-01', periods=10, freq='B')
        
        raw_data = {
            'TEST1': pd.Series(range(100, 110), index=dates)
        }
        
        transformed_data = {
            'TEST1': pd.Series(range(100, 110), index=dates)
        }
        
        scores = pd.DataFrame({
            'TEST1_z': [0.1] * 10,
            'TEST1_score': [50] * 10
        }, index=dates)
        
        confirm_results = {
            'final_lamp': pd.Series(['Y'] * 10, index=dates)
        }
        
        # 添加指标元数据
        pipeline.indicators = [
            {
                'code': 'TEST1',
                'name': '测试指标1',
                'role': 'main',
                'direction': 'up_good',
                'transform': 'raw',
                'source': 'test',
                'ticker': 'TEST'
            }
        ]
        
        # 保存
        saved_count = pipeline.save_to_database(
            raw_data, transformed_data, scores, confirm_results, view_type='daily'
        )
        
        assert saved_count > 0
    
    def test_get_last_data_date(self, temp_db):
        """测试获取最后数据日期"""
        pipeline = MarketPipeline(market='US', database_url=temp_db)
        
        # 初始应该返回None
        last_date = pipeline._get_last_data_date()
        assert last_date is None


@pytest.mark.slow
@pytest.mark.skipif(not os.getenv('RUN_SLOW_TESTS'), reason="Slow test skipped")
class TestFullPipeline:
    """完整流水线测试（较慢）"""
    
    def test_end_to_end_pipeline(self):
        """端到端流水线测试"""
        # 这个测试需要真实的API访问
        # 在CI环境中应该跳过
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

