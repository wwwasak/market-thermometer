"""
配置管理模块

负责加载、保存和管理所有应用配置参数，包括：
- 硬编码的默认值
- 用户自定义参数（从JSON文件或数据库加载）
- 环境变量配置
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv


class Config:
    """
    配置管理器
    
    管理应用的所有配置参数，包括regime阈值、权重、窗口大小等
    """
    
    def __init__(self, env_file: Optional[str] = None):
        """
        初始化配置管理器
        
        @param {Optional[str]} env_file - .env文件路径，默认使用项目根目录的.env
        """
        # 加载环境变量
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()
        
        # 初始化默认配置
        self._config = self._get_default_config()
        
    def _get_default_config(self) -> Dict[str, Any]:
        """
        获取默认配置
        
        @returns {Dict[str, Any]} 包含所有默认参数的字典
        """
        return {
            # ============ Regime阈值配置 ============
            "regime": {
                "attack_threshold": 70,      # Attack regime阈值
                "defense_threshold": 40,     # Defense regime阈值
                "persistence_days": 0,       # 日视图regime持续确认天数（0表示无持续要求）
                "persistence_weeks": 1       # 周视图regime持续确认周数
            },
            
            # ============ 灯色阈值配置 ============
            "lamp": {
                "green_threshold": 60,       # Green灯阈值
                "red_threshold": 40          # Red灯阈值
            },
            
            # ============ Z分数计算窗口配置 ============
            "z_windows": {
                "base": 60,                  # 基础窗口（大多数指标）
                "fast": 40,                  # 快速窗口（相对收益等）
                "slow": 90                   # 慢速窗口（PMI等）
            },
            
            # ============ 转换参数配置 ============
            "transforms": {
                "ewma_lambda": 0.94,         # EWMA平滑参数（用于两融斜率）
                "slope_w_fast": 0.6,         # 斜率计算快速权重
                "slope_w_slow": 0.4,         # 斜率计算慢速权重
                "vix_winsor_low": 0.02,      # VIX winsorize下限百分位
                "vix_winsor_high": 0.98      # VIX winsorize上限百分位
            },
            
            # ============ 持续性配置（确认层） ============
            "persistence": {
                "hard_veto_days": 3,         # 日视图硬否决持续天数
                "hard_veto_weeks": 2         # 周视图硬否决持续周数
            },
            
            # ============ 软确认权重配置 ============
            "soft_confirm_weights": {
                "CN": {
                    "PAIR_CNH_CNY": 0.50,
                    "PAIR_TWEX_DXY": 0.50
                },
                "US": {
                    "IWM_SPY_SOFT": 0.30,
                    "HYG_IEF_SOFT": 0.30,
                    "PAIR_TWEX_DXY": 0.20,
                    "PAIR_CNH_CNY": 0.20
                }
            },
            
            # ============ 软确认阈值配置 ============
            "soft_confirm_thresholds": {
                "green": 1.6,                # 加权平均≥1.6 → Green
                "red": 0.8                   # 加权平均≤0.8 → Red
            },
            
            # ============ 配对规则配置 ============
            "pair_rule": "A",                # Rule A: 一致性优先; Rule B: 强分歧→Red
            
            # ============ 风格权重配置 ============
            # CN市场主要指标权重（顺序：MARGIN_SLOPE, CNH_PCT20, NORTH_TURNOVER_SHARE, 
            #                            CSI1000_OVER_300_REL20, PMI_NEWORDER_YOY_STD, EPS_YIELD_MINUS_CGB10）
            "style_weights": {
                "CN": {
                    "Attack": [24, 16, 12, 20, 16, 12],
                    "Balanced": [20, 14, 12, 18, 18, 18],
                    "Defense": [15, 10, 10, 12, 20, 33]
                },
                # US市场主要指标权重（顺序：RRP_D20, TGA_D20, HY_OAS, VIX_LOG, DFII10, IWM_SPY_REL20）
                "US": {
                    "Attack": [12, 8, 18, 16, 16, 30],
                    "Balanced": [15, 10, 20, 15, 20, 20],
                    "Defense": [18, 12, 24, 18, 28, 0]
                }
            },
            
            # ============ 当前活跃风格 ============
            "active_style": {
                "CN": "Balanced",
                "US": "Balanced"
            },
            
            # ============ 硬否决规则配置 ============
            "hard_veto_rules": {
                "CN": {
                    "ETF_NETFLOW_5D": {
                        "enabled": True,
                        "threshold": None    # None表示使用标准lamp阈值
                    }
                },
                "US": {
                    "HY_OAS_JUMP": {
                        "enabled": True,
                        "delta_z_threshold": 1.5,    # ΔZ(2周) > 1.5
                        "score_threshold": 40        # 或 score ≤ 40
                    },
                    "VIX_EXTREME": {
                        "enabled": True,
                        "z_threshold": 2.0,          # Z > 2.0
                        "score_threshold": 40        # 或 score ≤ 40
                    }
                }
            },
            
            # ============ 数据源配置 ============
            "data_sources": {
                "fred_api_key": os.getenv("FRED_API_KEY", ""),
                "use_proxy": False,
                "http_proxy": os.getenv("HTTP_PROXY", ""),
                "https_proxy": os.getenv("HTTPS_PROXY", "")
            },
            
            # ============ 数据库配置 ============
            "database": {
                "path": os.getenv("DATABASE_PATH", "market_thermo.db")
            },
            
            # ============ 日志配置 ============
            "logging": {
                "level": os.getenv("LOG_LEVEL", "INFO"),
                "file": os.getenv("LOG_FILE", "market_thermo.log")
            },
            
            # ============ 指标定义配置 ============
            "indicators": {
                "CN": {
                    "main": [
                        {
                            "code": "CN_MARGIN_SLOPE",
                            "name": "两融余额斜率(20/60 EWMA)",
                            "direction": "up_good",
                            "transform": "slope_20_60_ewma",
                            "z_type": "Z",
                            "z_window": 60,
                            "source": "csv"
                        },
                        {
                            "code": "CNH_PCT20",
                            "name": "USD/CNH 20日%变动",
                            "direction": "down_good",
                            "transform": "pct20",
                            "z_type": "MADZ",
                            "z_window": 60,
                            "source": "yfinance",
                            "ticker": "CNH=X"
                        },
                        {
                            "code": "NORTH_TURNOVER_SHARE",
                            "name": "北向成交额/全A成交额",
                            "direction": "up_good",
                            "transform": "raw",
                            "z_type": "MADZ",
                            "z_window": 60,
                            "source": "csv"
                        },
                        {
                            "code": "CSI1000_OVER_300_REL20",
                            "name": "中证1000/沪深300 20日相对收益",
                            "direction": "up_good",
                            "transform": "relret20",
                            "z_type": "MADZ",
                            "z_window": 40,
                            "source": "csv"
                        },
                        {
                            "code": "PMI_NEWORDER_YOY_STD",
                            "name": "官方PMI新订单同比标准化",
                            "direction": "up_good",
                            "transform": "yoy_std_ffill",
                            "z_type": "Z",
                            "z_window": 90,
                            "source": "csv"
                        },
                        {
                            "code": "CN_EPS_YIELD_MINUS_CGB10",
                            "name": "股债收益差（盈利收益率-10Y国债）",
                            "direction": "up_good",
                            "transform": "raw_winsor",
                            "z_type": "Z",
                            "z_window": 60,
                            "source": "csv"
                        }
                    ],
                    "observers": [
                        {
                            "code": "ETF_NETFLOW_5D",
                            "name": "宽基ETF 5日净申赎",
                            "role": "hard",
                            "direction": "up_good",
                            "transform": "raw",
                            "source": "csv"
                        },
                        {
                            "code": "CNH",
                            "name": "USD/CNH",
                            "role": "pair",
                            "pair_id": "PAIR_CNH_CNY",
                            "direction": "down_good",
                            "transform": "raw",
                            "source": "yfinance",
                            "ticker": "CNH=X"
                        },
                        {
                            "code": "CNY",
                            "name": "USD/CNY",
                            "role": "pair",
                            "pair_id": "PAIR_CNH_CNY",
                            "direction": "down_good",
                            "transform": "raw",
                            "source": "yfinance",
                            "ticker": "CNY=X"
                        },
                        {
                            "code": "DTWEXBGS",
                            "name": "Trade-Weighted USD",
                            "role": "pair",
                            "pair_id": "PAIR_TWEX_DXY",
                            "direction": "down_good",
                            "transform": "raw",
                            "source": "fred",
                            "ticker": "DTWEXBGS"
                        },
                        {
                            "code": "DXY",
                            "name": "DXY美元指数",
                            "role": "pair",
                            "pair_id": "PAIR_TWEX_DXY",
                            "direction": "down_good",
                            "transform": "raw",
                            "source": "yfinance",
                            "ticker": "DX-Y.NYB"
                        }
                    ]
                },
                "US": {
                    "main": [
                        {
                            "code": "RRP_D20",
                            "name": "RRP Δ20d",
                            "direction": "down_good",
                            "transform": "delta20",
                            "z_type": "Z",
                            "z_window": 60,
                            "source": "fred",
                            "ticker": "RRPONTSYD"
                        },
                        {
                            "code": "TGA_D20",
                            "name": "TGA Δ20d",
                            "direction": "down_good",
                            "transform": "delta20",
                            "z_type": "Z",
                            "z_window": 60,
                            "source": "fred",
                            "ticker": "WTREGEN"
                        },
                        {
                            "code": "HY_OAS",
                            "name": "高收益债利差",
                            "direction": "down_good",
                            "transform": "raw",
                            "z_type": "MADZ",
                            "z_window": 60,
                            "source": "fred",
                            "ticker": "BAMLH0A0HYM2"
                        },
                        {
                            "code": "VIX_LOG",
                            "name": "VIX (log & winsor)",
                            "direction": "down_good",
                            "transform": "log_winsor",
                            "z_type": "MADZ",
                            "z_window": 40,
                            "source": "yfinance",
                            "ticker": "^VIX"
                        },
                        {
                            "code": "DFII10",
                            "name": "10Y TIPS实际利率",
                            "direction": "down_good",
                            "transform": "raw",
                            "z_type": "Z",
                            "z_window": 60,
                            "source": "fred",
                            "ticker": "DFII10"
                        },
                        {
                            "code": "IWM_SPY_REL20",
                            "name": "IWM/SPY 20日相对收益",
                            "direction": "up_good",
                            "transform": "relret20",
                            "z_type": "MADZ",
                            "z_window": 40,
                            "source": "yfinance",
                            "ticker": ["IWM", "SPY"]
                        }
                    ],
                    "observers": [
                        {
                            "code": "HY_OAS_JUMP",
                            "name": "高收益债极端跳升",
                            "role": "hard",
                            "base_indicator": "HY_OAS",
                            "rule": "jump_or_low_score"
                        },
                        {
                            "code": "VIX_EXTREME",
                            "name": "VIX极端值",
                            "role": "hard",
                            "base_indicator": "VIX_LOG",
                            "rule": "extreme_z_or_low_score"
                        },
                        {
                            "code": "IWM_SPY_SOFT",
                            "name": "IWM/SPY软确认",
                            "role": "soft",
                            "base_indicator": "IWM_SPY_REL20"
                        },
                        {
                            "code": "HYG_IEF_SOFT",
                            "name": "HYG/IEF相对强度",
                            "role": "soft",
                            "direction": "up_good",
                            "transform": "relret20",
                            "z_type": "MADZ",
                            "z_window": 40,
                            "source": "yfinance",
                            "ticker": ["HYG", "IEF"]
                        }
                    ]
                }
            }
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置项
        
        @param {str} key - 配置键（支持点号分隔的嵌套键，如 "regime.attack_threshold"）
        @param {Any} default - 默认值
        @returns {Any} 配置值
        """
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> None:
        """
        设置配置项
        
        @param {str} key - 配置键（支持点号分隔的嵌套键）
        @param {Any} value - 配置值
        """
        keys = key.split('.')
        config = self._config
        
        # 导航到最后一层的父节点
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        
        # 设置值
        config[keys[-1]] = value
    
    def get_all(self) -> Dict[str, Any]:
        """
        获取所有配置
        
        @returns {Dict[str, Any]} 完整配置字典
        """
        return self._config.copy()
    
    def get_defaults(self) -> Dict[str, Any]:
        """
        获取默认配置（用于重置）
        
        @returns {Dict[str, Any]} 默认配置字典
        """
        return self._get_default_config()
    
    def load_from_json(self, file_path: str) -> bool:
        """
        从JSON文件加载配置
        
        @param {str} file_path - JSON文件路径
        @returns {bool} 是否成功加载
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return False
            
            with open(path, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
            
            # 深度合并配置（保留未在JSON中指定的默认值）
            self._deep_merge(self._config, loaded_config)
            return True
        
        except Exception as e:
            print(f"加载配置失败: {e}")
            return False
    
    def save_to_json(self, file_path: str, indent: int = 2) -> bool:
        """
        保存配置到JSON文件
        
        @param {str} file_path - JSON文件路径
        @param {int} indent - JSON缩进空格数
        @returns {bool} 是否成功保存
        """
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=indent, ensure_ascii=False)
            
            return True
        
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False
    
    def _deep_merge(self, base: Dict, update: Dict) -> None:
        """
        深度合并两个字典
        
        @param {Dict} base - 基础字典（会被修改）
        @param {Dict} update - 更新字典
        """
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def get_indicator_config(self, market: str, code: str) -> Optional[Dict[str, Any]]:
        """
        获取指定指标的配置
        
        @param {str} market - 市场（'CN' 或 'US'）
        @param {str} code - 指标代码
        @returns {Optional[Dict[str, Any]]} 指标配置，如果不存在返回None
        """
        indicators = self.get(f"indicators.{market}", {})
        
        # 搜索主要指标
        for ind in indicators.get("main", []):
            if ind.get("code") == code:
                return ind.copy()
        
        # 搜索观察者指标
        for ind in indicators.get("observers", []):
            if ind.get("code") == code:
                return ind.copy()
        
        return None
    
    def get_active_weights(self, market: str) -> List[float]:
        """
        获取当前激活风格的权重
        
        @param {str} market - 市场（'CN' 或 'US'）
        @returns {List[float]} 权重列表
        """
        active_style = self.get(f"active_style.{market}", "Balanced")
        return self.get(f"style_weights.{market}.{active_style}", [])
    
    def set_active_style(self, market: str, style: str) -> None:
        """
        设置激活的风格
        
        @param {str} market - 市场（'CN' 或 'US'）
        @param {str} style - 风格名称（'Attack', 'Balanced', 'Defense'）
        """
        if style in ["Attack", "Balanced", "Defense"]:
            self.set(f"active_style.{market}", style)
    
    def reset_to_defaults(self) -> None:
        """
        重置所有配置为默认值
        """
        self._config = self._get_default_config()


# 全局配置实例（单例模式）
_global_config = None


def get_config() -> Config:
    """
    获取全局配置实例
    
    @returns {Config} 配置管理器实例
    """
    global _global_config
    if _global_config is None:
        _global_config = Config()
    return _global_config


def reset_config() -> None:
    """
    重置全局配置实例（主要用于测试）
    """
    global _global_config
    _global_config = None

