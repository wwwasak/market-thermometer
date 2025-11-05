"""
数据仓库模块

提供数据库CRUD操作和查询接口
"""

import json
import hashlib
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, date
import pandas as pd

from sqlalchemy import create_engine, and_, or_, desc
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError

from storage.models import (
    Base, SeriesMeta, SeriesData, Regime, Params, 
    FetchLog, LampHistory
)


class Repository:
    """
    数据仓库类
    
    封装所有数据库操作，提供高级查询接口
    """
    
    def __init__(self, database_url: str = 'sqlite:///market_thermo.db'):
        """
        初始化仓库
        
        @param {str} database_url - 数据库连接字符串
        """
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # 创建表（如果不存在）
        Base.metadata.create_all(self.engine)
    
    def get_session(self) -> Session:
        """获取数据库会话"""
        return self.SessionLocal()
    
    # ==================== SeriesMeta 操作 ====================
    
    def add_series_meta(
        self,
        code: str,
        name: str,
        market: str,
        role: str,
        direction: Optional[str] = None,
        transform: Optional[str] = None,
        z_type: Optional[str] = None,
        z_window: Optional[int] = None,
        source: Optional[str] = None,
        ticker: Optional[str] = None,
        note: Optional[str] = None
    ) -> int:
        """
        添加时间序列元数据
        
        @returns {int} series_id
        """
        session = self.get_session()
        try:
            series = SeriesMeta(
                code=code,
                name=name,
                market=market,
                role=role,
                direction=direction,
                transform=transform,
                z_type=z_type,
                z_window=z_window,
                source=source,
                ticker=ticker,
                note=note
            )
            session.add(series)
            session.commit()
            series_id = series.id
            return series_id
        except IntegrityError:
            session.rollback()
            # 如果code已存在，返回现有ID
            existing = session.query(SeriesMeta).filter_by(code=code).first()
            return existing.id if existing else None
        finally:
            session.close()
    
    def get_series_meta_by_code(self, code: str) -> Optional[Dict]:
        """根据code获取元数据"""
        session = self.get_session()
        try:
            series = session.query(SeriesMeta).filter_by(code=code).first()
            if series:
                return {
                    'id': series.id,
                    'code': series.code,
                    'name': series.name,
                    'market': series.market,
                    'role': series.role,
                    'direction': series.direction,
                    'transform': series.transform,
                    'z_type': series.z_type,
                    'z_window': series.z_window,
                    'source': series.source,
                    'ticker': series.ticker,
                    'note': series.note
                }
            return None
        finally:
            session.close()
    
    def get_all_series_meta(self, market: Optional[str] = None) -> List[Dict]:
        """获取所有元数据"""
        session = self.get_session()
        try:
            query = session.query(SeriesMeta)
            if market:
                query = query.filter_by(market=market)
            
            series_list = query.all()
            return [
                {
                    'id': s.id,
                    'code': s.code,
                    'name': s.name,
                    'market': s.market,
                    'role': s.role,
                    'direction': s.direction,
                    'transform': s.transform
                }
                for s in series_list
            ]
        finally:
            session.close()
    
    # ==================== SeriesData 操作 ====================
    
    def upsert_series_data(
        self,
        series_id: int,
        date: date,
        view: str,
        value_raw: Optional[float] = None,
        value_tr: Optional[float] = None,
        z: Optional[float] = None,
        score: Optional[float] = None
    ) -> bool:
        """
        插入或更新时间序列数据
        
        @returns {bool} 是否成功
        """
        session = self.get_session()
        try:
            # 尝试查找现有记录
            existing = session.query(SeriesData).filter(
                and_(
                    SeriesData.series_id == series_id,
                    SeriesData.date == date,
                    SeriesData.view == view
                )
            ).first()
            
            if existing:
                # 更新
                if value_raw is not None:
                    existing.value_raw = value_raw
                if value_tr is not None:
                    existing.value_tr = value_tr
                if z is not None:
                    existing.z = z
                if score is not None:
                    existing.score = score
            else:
                # 插入
                data = SeriesData(
                    series_id=series_id,
                    date=date,
                    view=view,
                    value_raw=value_raw,
                    value_tr=value_tr,
                    z=z,
                    score=score
                )
                session.add(data)
            
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print(f"Error upserting series data: {e}")
            return False
        finally:
            session.close()
    
    def batch_upsert_series_data(
        self,
        series_id: int,
        data_df: pd.DataFrame,
        view: str
    ) -> int:
        """
        批量插入或更新数据
        
        @param {pd.DataFrame} data_df - 数据框，索引为日期，列为value_raw, value_tr, z, score
        @returns {int} 影响的行数
        """
        count = 0
        for date_val, row in data_df.iterrows():
            if isinstance(date_val, pd.Timestamp):
                date_val = date_val.date()
            
            success = self.upsert_series_data(
                series_id=series_id,
                date=date_val,
                view=view,
                value_raw=row.get('value_raw'),
                value_tr=row.get('value_tr'),
                z=row.get('z'),
                score=row.get('score')
            )
            if success:
                count += 1
        
        return count
    
    def load_series_data(
        self,
        series_id: int,
        view: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """
        加载时间序列数据为DataFrame
        
        @returns {pd.DataFrame} 索引为日期，列为value_raw, value_tr, z, score
        """
        session = self.get_session()
        try:
            query = session.query(SeriesData).filter(
                and_(
                    SeriesData.series_id == series_id,
                    SeriesData.view == view
                )
            )
            
            if start_date:
                query = query.filter(SeriesData.date >= start_date)
            if end_date:
                query = query.filter(SeriesData.date <= end_date)
            
            query = query.order_by(SeriesData.date)
            
            data_list = query.all()
            
            if not data_list:
                return pd.DataFrame()
            
            df = pd.DataFrame([
                {
                    'date': d.date,
                    'value_raw': d.value_raw,
                    'value_tr': d.value_tr,
                    'z': d.z,
                    'score': d.score
                }
                for d in data_list
            ])
            
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            return df
        finally:
            session.close()
    
    def load_series_data_by_code(
        self,
        code: str,
        view: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """根据code加载数据"""
        meta = self.get_series_meta_by_code(code)
        if meta:
            return self.load_series_data(meta['id'], view, start_date, end_date)
        return pd.DataFrame()
    
    # ==================== Regime 操作 ====================
    
    def upsert_regime(
        self,
        date: date,
        market: str,
        view: str,
        regime: Optional[str] = None,
        composite_score: Optional[float] = None,
        lamp_final: Optional[str] = None,
        lamp_soft: Optional[str] = None,
        lamp_hard: Optional[str] = None,
        params_hash: Optional[str] = None
    ) -> bool:
        """插入或更新regime"""
        session = self.get_session()
        try:
            existing = session.query(Regime).filter(
                and_(
                    Regime.date == date,
                    Regime.market == market,
                    Regime.view == view
                )
            ).first()
            
            if existing:
                if regime is not None:
                    existing.regime = regime
                if composite_score is not None:
                    existing.composite_score = composite_score
                if lamp_final is not None:
                    existing.lamp_final = lamp_final
                if lamp_soft is not None:
                    existing.lamp_soft = lamp_soft
                if lamp_hard is not None:
                    existing.lamp_hard = lamp_hard
                if params_hash is not None:
                    existing.params_hash = params_hash
            else:
                regime_obj = Regime(
                    date=date,
                    market=market,
                    view=view,
                    regime=regime,
                    composite_score=composite_score,
                    lamp_final=lamp_final,
                    lamp_soft=lamp_soft,
                    lamp_hard=lamp_hard,
                    params_hash=params_hash
                )
                session.add(regime_obj)
            
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print(f"Error upserting regime: {e}")
            return False
        finally:
            session.close()
    
    def load_regimes(
        self,
        market: str,
        view: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.DataFrame:
        """加载regime数据"""
        session = self.get_session()
        try:
            query = session.query(Regime).filter(
                and_(
                    Regime.market == market,
                    Regime.view == view
                )
            )
            
            if start_date:
                query = query.filter(Regime.date >= start_date)
            if end_date:
                query = query.filter(Regime.date <= end_date)
            
            query = query.order_by(Regime.date)
            
            regimes = query.all()
            
            if not regimes:
                return pd.DataFrame()
            
            df = pd.DataFrame([
                {
                    'date': r.date,
                    'regime': r.regime,
                    'composite_score': r.composite_score,
                    'lamp_final': r.lamp_final,
                    'lamp_soft': r.lamp_soft,
                    'lamp_hard': r.lamp_hard
                }
                for r in regimes
            ])
            
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
            return df
        finally:
            session.close()
    
    # ==================== Params 操作 ====================
    
    def save_params(self, params_dict: Dict[str, Any], version: Optional[str] = None, set_active: bool = True) -> int:
        """保存参数配置"""
        session = self.get_session()
        try:
            if set_active:
                # 将其他配置设为非活跃
                session.query(Params).update({Params.is_active: 0})
            
            json_str = json.dumps(params_dict, ensure_ascii=False, indent=2)
            
            params = Params(
                version=version or datetime.now().strftime('%Y%m%d_%H%M%S'),
                json_blob=json_str,
                is_active=1 if set_active else 0
            )
            session.add(params)
            session.commit()
            return params.id
        finally:
            session.close()
    
    def load_active_params(self) -> Optional[Dict[str, Any]]:
        """加载当前活跃的参数配置"""
        session = self.get_session()
        try:
            params = session.query(Params).filter_by(is_active=1).first()
            if params:
                return json.loads(params.json_blob)
            return None
        finally:
            session.close()
    
    def load_params_by_id(self, params_id: int) -> Optional[Dict[str, Any]]:
        """根据ID加载参数"""
        session = self.get_session()
        try:
            params = session.query(Params).filter_by(id=params_id).first()
            if params:
                return json.loads(params.json_blob)
            return None
        finally:
            session.close()
    
    # ==================== FetchLog 操作 ====================
    
    def add_fetch_log(
        self,
        action: str,
        status: str,
        message: Optional[str] = None,
        market: Optional[str] = None,
        indicator_code: Optional[str] = None,
        records_count: Optional[int] = None
    ) -> int:
        """添加获取日志"""
        session = self.get_session()
        try:
            log = FetchLog(
                action=action,
                status=status,
                message=message,
                market=market,
                indicator_code=indicator_code,
                records_count=records_count
            )
            session.add(log)
            session.commit()
            return log.id
        finally:
            session.close()
    
    def get_recent_logs(self, limit: int = 50) -> List[Dict]:
        """获取最近的日志"""
        session = self.get_session()
        try:
            logs = session.query(FetchLog).order_by(desc(FetchLog.timestamp)).limit(limit).all()
            return [
                {
                    'id': log.id,
                    'timestamp': log.timestamp,
                    'action': log.action,
                    'status': log.status,
                    'message': log.message,
                    'market': log.market
                }
                for log in logs
            ]
        finally:
            session.close()
    
    # ==================== LampHistory 操作 ====================
    
    def upsert_lamp_history(
        self,
        date: date,
        market: str,
        view: str,
        source_type: str,
        source_code: str,
        lamp: str
    ) -> bool:
        """插入或更新灯色历史"""
        session = self.get_session()
        try:
            existing = session.query(LampHistory).filter(
                and_(
                    LampHistory.date == date,
                    LampHistory.market == market,
                    LampHistory.view == view,
                    LampHistory.source_type == source_type,
                    LampHistory.source_code == source_code
                )
            ).first()
            
            if existing:
                existing.lamp = lamp
            else:
                lamp_hist = LampHistory(
                    date=date,
                    market=market,
                    view=view,
                    source_type=source_type,
                    source_code=source_code,
                    lamp=lamp
                )
                session.add(lamp_hist)
            
            session.commit()
            return True
        except Exception as e:
            session.rollback()
            print(f"Error upserting lamp history: {e}")
            return False
        finally:
            session.close()
    
    def load_lamp_history(
        self,
        market: str,
        view: str,
        source_code: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> pd.Series:
        """加载灯色历史"""
        session = self.get_session()
        try:
            query = session.query(LampHistory).filter(
                and_(
                    LampHistory.market == market,
                    LampHistory.view == view,
                    LampHistory.source_code == source_code
                )
            )
            
            if start_date:
                query = query.filter(LampHistory.date >= start_date)
            if end_date:
                query = query.filter(LampHistory.date <= end_date)
            
            query = query.order_by(LampHistory.date)
            
            lamps = query.all()
            
            if not lamps:
                return pd.Series(dtype=str)
            
            dates = [lamp.date for lamp in lamps]
            values = [lamp.lamp for lamp in lamps]
            
            return pd.Series(values, index=pd.to_datetime(dates))
        finally:
            session.close()
    
    # ==================== 辅助方法 ====================
    
    def get_database_info(self) -> Dict[str, Any]:
        """获取数据库信息"""
        session = self.get_session()
        try:
            info = {
                'series_count': session.query(SeriesMeta).count(),
                'data_points_count': session.query(SeriesData).count(),
                'regimes_count': session.query(Regime).count(),
                'params_count': session.query(Params).count(),
                'logs_count': session.query(FetchLog).count(),
                'lamp_history_count': session.query(LampHistory).count()
            }
            return info
        finally:
            session.close()
    
    def clear_all_data(self):
        """清空所有数据表（谨慎使用）"""
        session = self.get_session()
        try:
            session.query(SeriesData).delete()
            session.query(Regime).delete()
            session.query(LampHistory).delete()
            session.query(FetchLog).delete()
            session.query(Params).delete()
            session.query(SeriesMeta).delete()
            session.commit()
        finally:
            session.close()
    
    def compute_params_hash(self, params_dict: Dict[str, Any]) -> str:
        """计算参数哈希"""
        json_str = json.dumps(params_dict, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]

