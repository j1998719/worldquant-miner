"""
WorldQuant Brain API 包装器
用于提交 Alpha 模拟和获取结果
"""
import requests
import time
import logging
from typing import Dict, Optional, Any
from requests.auth import HTTPBasicAuth
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SimulationSettings:
    """Alpha 模拟设置"""
    region: str = "USA"
    universe: str = "TOP3000"
    instrumentType: str = "EQUITY"
    delay: int = 1
    decay: int = 0
    neutralization: str = "SUBINDUSTRY"
    truncation: float = 0.08
    pasteurization: str = "ON"
    unitHandling: str = "VERIFY"
    nanHandling: str = "OFF"
    maxTrade: str = "OFF"
    language: str = "FASTEXPR"
    visualization: bool = False
    testPeriod: str = "P5Y0M0D"


@dataclass
class AlphaResult:
    """Alpha 模拟结果"""
    alpha_id: str
    expression: str
    sharpe: float
    fitness: float
    turnover: float
    returns: float
    drawdown: float
    margin: float
    longCount: int
    shortCount: int
    success: bool = True
    error_message: str = ""
    
    def passes_criteria(self, 
                       min_sharpe: float = 1.25,
                       min_fitness: float = 1.0,
                       max_turnover: float = 0.7,
                       min_turnover: float = 0.01,
                       min_returns: float = 0.0) -> bool:
        """检查是否通过所有标准（WorldQuant Brain's grading criteria）"""
        if not self.success:
            return False
        
        criteria = [
            self.sharpe >= min_sharpe,
            self.fitness >= min_fitness,
            self.turnover <= max_turnover,
            self.turnover >= min_turnover,
            self.returns >= min_returns
        ]
        return all(criteria)
    
    def is_hopeful(self,
                   min_sharpe: float = 0.5,
                   min_fitness: float = 0.6) -> bool:
        """检查是否值得优化（"hopeful" alpha）"""
        if not self.success:
            return False
        return self.sharpe >= min_sharpe and self.fitness >= min_fitness
    
    def get_score(self) -> float:
        """计算综合得分"""
        if not self.success:
            return 0.0
        # 加权评分
        return (self.sharpe * 0.4 + 
                self.fitness * 0.3 + 
                (1.0 - min(self.turnover / 0.4, 1.0)) * 0.2 + 
                self.returns * 0.1)


class WorldQuantAPI:
    """WorldQuant Brain API 客户端"""
    
    def __init__(self, username: str, password: str):
        self.sess = requests.Session()
        self.username = username
        self.password = password
        self._authenticate()
    
    def _authenticate(self):
        """认证到 WorldQuant Brain"""
        logger.info("Authenticating with WorldQuant Brain...")
        self.sess.auth = HTTPBasicAuth(self.username, self.password)
        
        response = self.sess.post('https://api.worldquantbrain.com/authentication')
        
        if response.status_code != 201:
            raise Exception(f"Authentication failed: {response.text}")
        
        logger.info("✅ Authentication successful")
    
    def submit_alpha(self, 
                    expression: str, 
                    settings: Optional[SimulationSettings] = None) -> Optional[str]:
        """
        提交 Alpha 进行模拟
        
        Returns:
            progress_url: 用于监控模拟进度的 URL，如果失败返回 None
        """
        if settings is None:
            settings = SimulationSettings()
        
        simulation_data = {
            'type': 'REGULAR',
            'settings': {
                'instrumentType': settings.instrumentType,
                'region': settings.region,
                'universe': settings.universe,
                'delay': settings.delay,
                'decay': settings.decay,
                'neutralization': settings.neutralization,
                'truncation': settings.truncation,
                'pasteurization': settings.pasteurization,
                'unitHandling': settings.unitHandling,
                'nanHandling': settings.nanHandling,
                'maxTrade': settings.maxTrade,
                'language': settings.language,
                'visualization': settings.visualization,
                'testPeriod': settings.testPeriod
            },
            'regular': expression
        }
        
        try:
            response = self.sess.post('https://api.worldquantbrain.com/simulations', 
                                     json=simulation_data)
            
            # 检查是否需要重新认证
            if response.status_code == 401:
                logger.warning("Authentication expired, refreshing...")
                self._authenticate()
                response = self.sess.post('https://api.worldquantbrain.com/simulations', 
                                         json=simulation_data)
            
            if response.status_code != 201:
                logger.error(f"Simulation submission failed: {response.text}")
                return None
            
            progress_url = response.headers.get('Location')
            if not progress_url:
                logger.error("No progress URL in response")
                return None
            
            logger.info(f"✅ Simulation submitted: {expression[:60]}...")
            return progress_url
            
        except Exception as e:
            logger.error(f"Error submitting simulation: {e}")
            return None
    
    def wait_for_result(self, 
                       progress_url: str, 
                       expression: str,
                       timeout: int = 1800) -> Optional[AlphaResult]:
        """
        等待模拟完成并获取结果
        
        Args:
            progress_url: 模拟进度 URL
            expression: Alpha 表达式
            timeout: 超时时间（秒）
        
        Returns:
            AlphaResult 或 None
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                response = self.sess.get(progress_url)
                
                if response.status_code == 200:
                    data = response.json()
                    status = data.get('status')
                    
                    if status == 'COMPLETE':
                        alpha_id = data.get('alpha')
                        is_data = data.get('is', {})
                        
                        result = AlphaResult(
                            alpha_id=alpha_id,
                            expression=expression,
                            sharpe=is_data.get('sharpe', 0),
                            fitness=is_data.get('fitness', 0),
                            turnover=is_data.get('turnover', 0),
                            returns=is_data.get('returns', 0),
                            drawdown=is_data.get('drawdown', 0),
                            margin=is_data.get('margin', 0),
                            longCount=is_data.get('longCount', 0),
                            shortCount=is_data.get('shortCount', 0),
                            success=True
                        )
                        
                        logger.info(f"✅ Simulation complete - Sharpe: {result.sharpe:.3f}, Fitness: {result.fitness:.3f}")
                        return result
                    
                    elif status in ['FAILED', 'ERROR']:
                        error_msg = data.get('message', 'Unknown error')
                        logger.error(f"❌ Simulation failed: {error_msg}")
                        return AlphaResult(
                            alpha_id="",
                            expression=expression,
                            sharpe=0, fitness=0, turnover=0, returns=0,
                            drawdown=0, margin=0, longCount=0, shortCount=0,
                            success=False,
                            error_message=error_msg
                        )
                
                # 等待后继续检查
                time.sleep(5)
                
            except Exception as e:
                logger.error(f"Error monitoring simulation: {e}")
                time.sleep(10)
        
        logger.warning("⏱️ Simulation timed out")
        return AlphaResult(
            alpha_id="",
            expression=expression,
            sharpe=0, fitness=0, turnover=0, returns=0,
            drawdown=0, margin=0, longCount=0, shortCount=0,
            success=False,
            error_message="Timeout"
        )
    
    def simulate_alpha(self, 
                      expression: str,
                      settings: Optional[SimulationSettings] = None) -> Optional[AlphaResult]:
        """
        提交 Alpha 并等待结果（一步完成）
        
        Args:
            expression: Alpha 表达式
            settings: 模拟设置
        
        Returns:
            AlphaResult 或 None
        """
        progress_url = self.submit_alpha(expression, settings)
        if not progress_url:
            return None
        
        return self.wait_for_result(progress_url, expression)

