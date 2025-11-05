"""
数据库模型定义

使用SQLAlchemy ORM定义所有数据表结构。
"""

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Date, Text, 
    ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class SeriesMeta(Base):
    """
    时间序列元数据表
    
    存储指标的基本信息和配置
    """
    __tablename__ = 'series_meta'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    market = Column(String(10), nullable=False, index=True)  # 'CN' or 'US'
    role = Column(String(20), nullable=False, index=True)  # 'main', 'soft', 'hard', 'pair'
    direction = Column(String(20))  # 'up_good' or 'down_good'
    transform = Column(String(50))  # 转换类型
    z_type = Column(String(20))  # 'Z' or 'MADZ'
    z_window = Column(Integer)  # Z分数计算窗口
    source = Column(String(50))  # 'fred', 'yfinance', 'csv', 'manual'
    ticker = Column(String(100))  # 数据源的ticker/代码
    note = Column(Text)  # 备注
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    data_points = relationship("SeriesData", back_populates="series", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<SeriesMeta(code='{self.code}', name='{self.name}', market='{self.market}')>"


class SeriesData(Base):
    """
    时间序列数据表
    
    存储指标的时间序列数据（原始值、转换值、Z分数、评分）
    """
    __tablename__ = 'series_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    series_id = Column(Integer, ForeignKey('series_meta.id'), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    view = Column(String(10), nullable=False, index=True)  # 'daily' or 'weekly'
    
    value_raw = Column(Float)  # 原始值
    value_tr = Column(Float)  # 转换后的值
    z = Column(Float)  # Z分数
    score = Column(Float)  # 评分（0-100）
    
    created_at = Column(DateTime, default=datetime.now)
    
    # 关系
    series = relationship("SeriesMeta", back_populates="data_points")
    
    # 唯一约束：同一指标、同一日期、同一视图只能有一条记录
    __table_args__ = (
        UniqueConstraint('series_id', 'date', 'view', name='uix_series_date_view'),
        Index('idx_series_date_view', 'series_id', 'date', 'view'),
    )
    
    def __repr__(self):
        return f"<SeriesData(series_id={self.series_id}, date={self.date}, view='{self.view}', score={self.score})>"


class Regime(Base):
    """
    市场态势表
    
    存储每个市场每天的regime和灯色信息
    """
    __tablename__ = 'regimes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    market = Column(String(10), nullable=False, index=True)  # 'CN' or 'US'
    view = Column(String(10), nullable=False, index=True)  # 'daily' or 'weekly'
    
    # Regime信息
    regime = Column(String(20))  # 'Attack', 'Balanced', 'Defense'
    composite_score = Column(Float)  # 综合评分
    
    # 灯色信息
    lamp_final = Column(String(1))  # 'G', 'Y', 'R'
    lamp_soft = Column(String(1))  # 软确认灯色
    lamp_hard = Column(String(1))  # 硬否决灯色
    
    # 参数哈希（用于追踪参数变化）
    params_hash = Column(String(64))
    
    created_at = Column(DateTime, default=datetime.now)
    
    # 唯一约束
    __table_args__ = (
        UniqueConstraint('date', 'market', 'view', name='uix_date_market_view'),
        Index('idx_date_market_view', 'date', 'market', 'view'),
    )
    
    def __repr__(self):
        return f"<Regime(date={self.date}, market='{self.market}', regime='{self.regime}', lamp='{self.lamp_final}')>"


class Params(Base):
    """
    参数配置表
    
    存储应用的配置参数历史
    """
    __tablename__ = 'params'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(50))  # 版本标识
    json_blob = Column(Text, nullable=False)  # JSON格式的参数
    is_active = Column(Integer, default=0)  # 是否为当前活跃配置（1=是，0=否）
    note = Column(Text)  # 备注
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<Params(id={self.id}, version='{self.version}', active={self.is_active})>"


class FetchLog(Base):
    """
    数据获取日志表
    
    记录每次数据获取的状态和结果
    """
    __tablename__ = 'fetch_log'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.now, index=True)
    action = Column(String(100), nullable=False)  # 'fetch_fred', 'fetch_yfinance', 'import_csv', etc.
    status = Column(String(20), nullable=False)  # 'success', 'error', 'partial'
    message = Column(Text)  # 详细信息或错误消息
    
    # 额外信息
    market = Column(String(10))  # 'CN', 'US', or 'both'
    indicator_code = Column(String(50))  # 相关指标代码
    records_count = Column(Integer)  # 影响的记录数
    
    def __repr__(self):
        return f"<FetchLog(action='{self.action}', status='{self.status}', time={self.timestamp})>"


class LampHistory(Base):
    """
    灯色历史表
    
    存储各个指标和配对的灯色历史（用于确认层分析）
    """
    __tablename__ = 'lamp_history'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    market = Column(String(10), nullable=False, index=True)
    view = Column(String(10), nullable=False, index=True)
    
    # 灯色来源
    source_type = Column(String(20), nullable=False)  # 'indicator', 'pair', 'hard_veto', 'soft_confirm'
    source_code = Column(String(50), nullable=False, index=True)  # 指标代码或配对ID
    
    # 灯色值
    lamp = Column(String(1), nullable=False)  # 'G', 'Y', 'R'
    
    created_at = Column(DateTime, default=datetime.now)
    
    # 唯一约束
    __table_args__ = (
        UniqueConstraint('date', 'market', 'view', 'source_type', 'source_code', name='uix_lamp_unique'),
        Index('idx_lamp_lookup', 'date', 'market', 'view', 'source_code'),
    )
    
    def __repr__(self):
        return f"<LampHistory(date={self.date}, source='{self.source_code}', lamp='{self.lamp}')>"


# 辅助函数

def create_all_tables(engine):
    """
    创建所有表
    
    @param {Engine} engine - SQLAlchemy引擎
    """
    Base.metadata.create_all(engine)


def drop_all_tables(engine):
    """
    删除所有表（谨慎使用）
    
    @param {Engine} engine - SQLAlchemy引擎
    """
    Base.metadata.drop_all(engine)


def get_table_names():
    """
    获取所有表名
    
    @returns {List[str]} 表名列表
    """
    return [table.name for table in Base.metadata.sorted_tables]

