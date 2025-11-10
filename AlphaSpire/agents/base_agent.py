"""
基础 Agent 类
所有 Agent 都继承自此类
"""
import requests
import time
import json
import logging
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """基础 Agent 抽象类"""
    
    def __init__(self, 
                 name: str,
                 system_prompt: str,
                 ollama_url: str = "http://localhost:11434",
                 ollama_model: str = "gemma3:1b",
                 temperature: float = 0.2):
        """
        Args:
            name: Agent 名称
            system_prompt: 系统提示词
            ollama_url: Ollama API URL
            ollama_model: 使用的模型
            temperature: 温度参数
        """
        self.name = name
        self.system_prompt = system_prompt
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model
        self.temperature = temperature
        self.conversation_history = []
    
    def call_llm(self, 
                 prompt: str, 
                 format_json: bool = False,
                 num_predict: int = 2000,
                 timeout: int = 120) -> str:
        """
        调用 Ollama LLM
        
        Args:
            prompt: 用户提示词
            format_json: 是否要求 JSON 格式输出
            num_predict: 最大生成 token 数
            timeout: 超时时间
        
        Returns:
            LLM 的响应文本
        """
        # 构建完整 prompt
        full_prompt = f"System: {self.system_prompt}\n\nUser: {prompt}"
        
        payload = {
            "model": self.ollama_model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": num_predict
            }
        }
        
        if format_json:
            payload["format"] = "json"
        
        try:
            logger.info(f"[{self.name}] Calling LLM...")
            start_time = time.time()
            
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=timeout
            )
            
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '').strip()
                logger.info(f"[{self.name}] LLM responded in {elapsed:.2f}s")
                return response_text
            else:
                logger.error(f"[{self.name}] LLM error: {response.status_code}")
                return ""
        
        except Exception as e:
            logger.error(f"[{self.name}] LLM call failed: {e}")
            return ""
    
    def parse_json_response(self, response: str) -> Optional[Dict]:
        """
        解析 JSON 响应
        
        Args:
            response: LLM 的响应文本
        
        Returns:
            解析后的字典，失败返回 None
        """
        import re
        
        # 移除 markdown 代码块
        cleaned = re.sub(r"```(?:json)?", "", response, flags=re.IGNORECASE).strip()
        
        # 移除思考标签
        if '<think>' in cleaned:
            parts = cleaned.split('</think>')
            if len(parts) > 1:
                cleaned = parts[-1].strip()
        
        # 提取 JSON
        if '{' in cleaned and '}' in cleaned:
            json_start = cleaned.find('{')
            json_end = cleaned.rfind('}') + 1
            cleaned = cleaned[json_start:json_end]
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"[{self.name}] JSON parse error: {e}")
            logger.debug(f"Response: {response[:500]}")
            return None
    
    @abstractmethod
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行 Agent 的主要任务
        
        Args:
            context: 上下文信息字典
        
        Returns:
            执行结果字典
        """
        pass
    
    def log(self, message: str, level: str = "info"):
        """记录日志"""
        log_func = getattr(logger, level, logger.info)
        log_func(f"[{self.name}] {message}")

