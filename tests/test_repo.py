"""
数据存储层单元测试
"""

import pytest
import pandas as pd
import tempfile
import os
from datetime import date, datetime, timedelta

from storage.repository import Repository
from storage.migrate import init_database, backup_database, check_database_integrity


class TestRepository:
    """Repository基础测试"""
    
    @pytest.fixture
    def temp_repo(self):
        """创建临时数据库仓库"""
        # 使用临时文件
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        
        db_url = f'sqlite:///{temp_db.name}'
        repo = Repository(db_url)
        
        yield repo
        
        # 清理
        try:
            os.unlink(temp_db.name)
        except:
            pass
    
    def test_repository_init(self, temp_repo):
        """测试仓库初始化"""
        assert temp_repo is not None
        assert temp_repo.engine is not None
    
    def test_get_database_info(self, temp_repo):
        """测试数据库信息获取"""
        info = temp_repo.get_database_info()
        
        assert isinstance(info, dict)
        assert 'series_count' in info
        assert 'data_points_count' in info
        assert info['series_count'] >= 0


class TestSeriesMeta:
    """序列元数据测试"""
    
    @pytest.fixture
    def temp_repo(self):
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        repo = Repository(f'sqlite:///{temp_db.name}')
        yield repo
        try:
            os.unlink(temp_db.name)
        except:
            pass
    
    def test_add_series_meta(self, temp_repo):
        """测试添加元数据"""
        series_id = temp_repo.add_series_meta(
            code='TEST_IND',
            name='测试指标',
            market='CN',
            role='main',
            direction='up_good',
            transform='raw',
            z_type='Z',
            z_window=60,
            source='test'
        )
        
        assert series_id is not None
        assert series_id > 0
    
    def test_get_series_meta_by_code(self, temp_repo):
        """测试根据code获取元数据"""
        # 添加指标
        temp_repo.add_series_meta(
            code='VIX',
            name='VIX波动率',
            market='US',
            role='main',
            direction='down_good'
        )
        
        # 获取
        meta = temp_repo.get_series_meta_by_code('VIX')
        
        assert meta is not None
        assert meta['code'] == 'VIX'
        assert meta['name'] == 'VIX波动率'
        assert meta['market'] == 'US'
        assert meta['direction'] == 'down_good'
    
    def test_get_series_meta_not_found(self, temp_repo):
        """测试获取不存在的元数据"""
        meta = temp_repo.get_series_meta_by_code('NONEXISTENT')
        
        assert meta is None
    
    def test_add_duplicate_code(self, temp_repo):
        """测试添加重复code"""
        code = 'DUPLICATE'
        
        id1 = temp_repo.add_series_meta(
            code=code,
            name='First',
            market='CN',
            role='main'
        )
        
        id2 = temp_repo.add_series_meta(
            code=code,
            name='Second',
            market='CN',
            role='main'
        )
        
        # 应该返回相同的ID
        assert id1 == id2
    
    def test_get_all_series_meta(self, temp_repo):
        """测试获取所有元数据"""
        # 添加多个指标
        temp_repo.add_series_meta(code='IND1', name='指标1', market='CN', role='main')
        temp_repo.add_series_meta(code='IND2', name='指标2', market='US', role='main')
        temp_repo.add_series_meta(code='IND3', name='指标3', market='CN', role='soft')
        
        # 获取所有
        all_series = temp_repo.get_all_series_meta()
        assert len(all_series) == 3
        
        # 按市场过滤
        cn_series = temp_repo.get_all_series_meta(market='CN')
        assert len(cn_series) == 2


class TestSeriesData:
    """序列数据测试"""
    
    @pytest.fixture
    def temp_repo_with_series(self):
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        repo = Repository(f'sqlite:///{temp_db.name}')
        
        # 添加测试指标
        series_id = repo.add_series_meta(
            code='TEST',
            name='测试',
            market='CN',
            role='main'
        )
        
        yield repo, series_id
        
        try:
            os.unlink(temp_db.name)
        except:
            pass
    
    def test_upsert_series_data(self, temp_repo_with_series):
        """测试插入数据"""
        repo, series_id = temp_repo_with_series
        
        success = repo.upsert_series_data(
            series_id=series_id,
            date=date(2024, 1, 1),
            view='daily',
            value_raw=100.0,
            value_tr=100.0,
            z=0.5,
            score=55.0
        )
        
        assert success is True
    
    def test_upsert_duplicate(self, temp_repo_with_series):
        """测试更新已存在的数据"""
        repo, series_id = temp_repo_with_series
        test_date = date(2024, 1, 1)
        
        # 插入
        repo.upsert_series_data(
            series_id=series_id,
            date=test_date,
            view='daily',
            value_raw=100.0,
            score=50.0
        )
        
        # 更新
        repo.upsert_series_data(
            series_id=series_id,
            date=test_date,
            view='daily',
            score=60.0  # 只更新score
        )
        
        # 加载验证
        df = repo.load_series_data(series_id, 'daily')
        assert len(df) == 1
        assert df.iloc[0]['score'] == 60.0
        assert df.iloc[0]['value_raw'] == 100.0  # 原值保留
    
    def test_load_series_data(self, temp_repo_with_series):
        """测试加载数据"""
        repo, series_id = temp_repo_with_series
        
        # 插入多条数据
        dates = [date(2024, 1, i) for i in range(1, 6)]
        for i, d in enumerate(dates):
            repo.upsert_series_data(
                series_id=series_id,
                date=d,
                view='daily',
                value_raw=float(100 + i),
                score=float(50 + i)
            )
        
        # 加载
        df = repo.load_series_data(series_id, 'daily')
        
        assert len(df) == 5
        assert df.index[0] == pd.Timestamp('2024-01-01')
        assert df.iloc[0]['value_raw'] == 100.0
        assert df.iloc[-1]['score'] == 54.0
    
    def test_load_series_data_with_date_range(self, temp_repo_with_series):
        """测试带日期范围的加载"""
        repo, series_id = temp_repo_with_series
        
        # 插入10天数据
        for i in range(1, 11):
            repo.upsert_series_data(
                series_id=series_id,
                date=date(2024, 1, i),
                view='daily',
                value_raw=float(i),
                score=float(i)
            )
        
        # 加载1月3日到1月7日
        df = repo.load_series_data(
            series_id,
            'daily',
            start_date=date(2024, 1, 3),
            end_date=date(2024, 1, 7)
        )
        
        assert len(df) == 5
        assert df.iloc[0]['value_raw'] == 3.0
        assert df.iloc[-1]['value_raw'] == 7.0
    
    def test_load_series_data_by_code(self, temp_repo_with_series):
        """测试根据code加载数据"""
        repo, series_id = temp_repo_with_series
        
        repo.upsert_series_data(
            series_id=series_id,
            date=date(2024, 1, 1),
            view='daily',
            value_raw=100.0
        )
        
        df = repo.load_series_data_by_code('TEST', 'daily')
        
        assert len(df) == 1
        assert df.iloc[0]['value_raw'] == 100.0
    
    def test_batch_upsert(self, temp_repo_with_series):
        """测试批量插入"""
        repo, series_id = temp_repo_with_series
        
        # 创建DataFrame
        dates = pd.date_range('2024-01-01', periods=5, freq='B')
        data_df = pd.DataFrame({
            'value_raw': [100, 102, 104, 106, 108],
            'value_tr': [100, 102, 104, 106, 108],
            'z': [0, 0.5, 1.0, 1.5, 2.0],
            'score': [50, 55, 60, 65, 70]
        }, index=dates)
        
        count = repo.batch_upsert_series_data(series_id, data_df, 'daily')
        
        assert count == 5
        
        # 验证
        loaded_df = repo.load_series_data(series_id, 'daily')
        assert len(loaded_df) == 5


class TestRegime:
    """Regime测试"""
    
    @pytest.fixture
    def temp_repo(self):
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        repo = Repository(f'sqlite:///{temp_db.name}')
        yield repo
        try:
            os.unlink(temp_db.name)
        except:
            pass
    
    def test_upsert_regime(self, temp_repo):
        """测试插入regime"""
        success = temp_repo.upsert_regime(
            date=date(2024, 1, 1),
            market='CN',
            view='daily',
            regime='Attack',
            composite_score=75.0,
            lamp_final='G',
            lamp_soft='G',
            lamp_hard='Y'
        )
        
        assert success is True
    
    def test_load_regimes(self, temp_repo):
        """测试加载regimes"""
        # 插入多条
        for i in range(1, 6):
            temp_repo.upsert_regime(
                date=date(2024, 1, i),
                market='CN',
                view='daily',
                regime='Attack' if i <= 3 else 'Balanced',
                composite_score=float(70 + i),
                lamp_final='G' if i <= 3 else 'Y'
            )
        
        # 加载
        df = temp_repo.load_regimes('CN', 'daily')
        
        assert len(df) == 5
        assert df.iloc[0]['regime'] == 'Attack'
        assert df.iloc[-1]['regime'] == 'Balanced'


class TestParams:
    """参数配置测试"""
    
    @pytest.fixture
    def temp_repo(self):
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        repo = Repository(f'sqlite:///{temp_db.name}')
        yield repo
        try:
            os.unlink(temp_db.name)
        except:
            pass
    
    def test_save_params(self, temp_repo):
        """测试保存参数"""
        params = {
            'regime': {'attack': 70, 'defense': 40},
            'lamp': {'green': 60, 'red': 40}
        }
        
        params_id = temp_repo.save_params(params, version='test_v1')
        
        assert params_id is not None
        assert params_id > 0
    
    def test_load_active_params(self, temp_repo):
        """测试加载活跃参数"""
        params1 = {'version': 1, 'value': 100}
        params2 = {'version': 2, 'value': 200}
        
        # 保存两个版本
        temp_repo.save_params(params1, version='v1', set_active=False)
        temp_repo.save_params(params2, version='v2', set_active=True)
        
        # 加载活跃的
        active = temp_repo.load_active_params()
        
        assert active is not None
        assert active['version'] == 2
        assert active['value'] == 200
    
    def test_load_params_by_id(self, temp_repo):
        """测试根据ID加载参数"""
        params = {'test': 'value'}
        params_id = temp_repo.save_params(params, version='test')
        
        loaded = temp_repo.load_params_by_id(params_id)
        
        assert loaded is not None
        assert loaded['test'] == 'value'


class TestFetchLog:
    """获取日志测试"""
    
    @pytest.fixture
    def temp_repo(self):
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        repo = Repository(f'sqlite:///{temp_db.name}')
        yield repo
        try:
            os.unlink(temp_db.name)
        except:
            pass
    
    def test_add_fetch_log(self, temp_repo):
        """测试添加日志"""
        log_id = temp_repo.add_fetch_log(
            action='fetch_fred',
            status='success',
            message='Fetched 100 records',
            market='US',
            indicator_code='VIX',
            records_count=100
        )
        
        assert log_id is not None
        assert log_id > 0
    
    def test_get_recent_logs(self, temp_repo):
        """测试获取最近日志"""
        # 添加多条日志
        for i in range(10):
            temp_repo.add_fetch_log(
                action=f'action_{i}',
                status='success',
                market='CN'
            )
        
        # 获取最近5条
        logs = temp_repo.get_recent_logs(limit=5)
        
        assert len(logs) == 5
        assert logs[0]['action'] == 'action_9'  # 最新的在前


class TestLampHistory:
    """灯色历史测试"""
    
    @pytest.fixture
    def temp_repo(self):
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        repo = Repository(f'sqlite:///{temp_db.name}')
        yield repo
        try:
            os.unlink(temp_db.name)
        except:
            pass
    
    def test_upsert_lamp_history(self, temp_repo):
        """测试插入灯色历史"""
        success = temp_repo.upsert_lamp_history(
            date=date(2024, 1, 1),
            market='CN',
            view='daily',
            source_type='indicator',
            source_code='VIX',
            lamp='G'
        )
        
        assert success is True
    
    def test_load_lamp_history(self, temp_repo):
        """测试加载灯色历史"""
        # 插入多条
        for i in range(1, 6):
            lamp = 'G' if i <= 2 else ('Y' if i <= 4 else 'R')
            temp_repo.upsert_lamp_history(
                date=date(2024, 1, i),
                market='CN',
                view='daily',
                source_type='indicator',
                source_code='TEST_IND',
                lamp=lamp
            )
        
        # 加载
        series = temp_repo.load_lamp_history('CN', 'daily', 'TEST_IND')
        
        assert len(series) == 5
        assert series.iloc[0] == 'G'
        assert series.iloc[-1] == 'R'


class TestMigration:
    """数据库迁移测试"""
    
    def test_init_database(self):
        """测试数据库初始化"""
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        db_url = f'sqlite:///{temp_db.name}'
        
        try:
            success = init_database(db_url, force=True)
            assert success is True
            
            # 验证表已创建
            repo = Repository(db_url)
            info = repo.get_database_info()
            assert info['series_count'] > 0  # 应该有默认指标
        finally:
            try:
                os.unlink(temp_db.name)
            except:
                pass
    
    def test_backup_database(self):
        """测试数据库备份"""
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        
        # 创建数据库
        init_database(f'sqlite:///{temp_db.name}')
        
        try:
            # 备份
            backup_file = backup_database(temp_db.name, backup_dir='test_backups')
            
            assert backup_file is not None
            assert os.path.exists(backup_file)
            
            # 清理
            os.unlink(backup_file)
            os.rmdir('test_backups')
        finally:
            try:
                os.unlink(temp_db.name)
            except:
                pass
    
    def test_check_database_integrity(self):
        """测试数据库完整性检查"""
        temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        temp_db.close()
        db_url = f'sqlite:///{temp_db.name}'
        
        try:
            init_database(db_url)
            result = check_database_integrity(db_url)
            
            assert result['status'] == 'ok'
            assert len(result['missing_tables']) == 0
        finally:
            try:
                os.unlink(temp_db.name)
            except:
                pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

