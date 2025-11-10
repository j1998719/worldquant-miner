"""
Alpha Designer Agent
负责从成功案例的优化建议中选择 Alpha 表达式
"""
import json
import random
from pathlib import Path
from typing import Dict, Any, List, Set
from .base_agent import BaseAgent


class AlphaDesignerAgent(BaseAgent):
    """
    Alpha 设计 Agent（优化版）
    不再依赖 LLM 生成，直接从 hopeful_alphas.json 的 optimization_suggestions 中选择表达式
    """
    
    def __init__(self, **kwargs):
        # 不再需要复杂的 system_prompt，因为不使用 LLM
        system_prompt = "Expression selector from hopeful alphas"
        
        super().__init__(
            name="AlphaDesigner",
            system_prompt=system_prompt,
            **kwargs
        )
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        从 hopeful_alphas.json 的 optimization_suggestions 中选择表达式
        
        Args:
            context: {
                'previous_attempts': List[str],  # 之前尝试的表达式（可选）
            }
        
        Returns:
            {
                'success': bool,
                'alpha_design': Dict or None,
                'error': str (if failed)
            }
        """
        previous_attempts = context.get('previous_attempts', [])
        
        # 从 hopeful_alphas.json 提取所有 expression_example
        candidates = self._extract_expression_candidates()
        
        if not candidates:
            return {
                'success': False,
                'alpha_design': None,
                'error': 'No expression candidates found in hopeful_alphas.json'
            }
        
        # 过滤掉已经尝试过的表达式
        previous_set = set(previous_attempts)
        available = [expr for expr in candidates if expr not in previous_set]
        
        if not available:
            self.log("All candidates tried, recycling from beginning...")
            available = candidates
        
        # 随机选择一个表达式
        selected_expression = random.choice(available)
        
        self.log(f"Selected expression from hopeful alphas: {selected_expression}")
        
        return {
            'success': True,
            'alpha_design': {
                'expression': selected_expression,
                'source': 'hopeful_alphas_optimization_suggestions'
            },
            'error': None
        }
    
    def _extract_expression_candidates(self) -> List[str]:
        """从 hopeful_alphas.json 提取所有表达式候选"""
        hopeful_file = Path(__file__).resolve().parents[1] / "results" / "hopeful_alphas.json"
        
        if not hopeful_file.exists():
            self.log("hopeful_alphas.json not found, returning empty list")
            return []
        
        try:
            with open(hopeful_file, 'r', encoding='utf-8') as f:
                hopeful_alphas = json.load(f)
            
            candidates = []
            
            for alpha in hopeful_alphas:
                # 添加原始表达式
                original_expr = alpha.get('expression')
                if original_expr and original_expr not in candidates:
                    candidates.append(original_expr)
                
                # 提取所有 suggested_expressions（新格式）
                analysis = alpha.get('analysis', {})
                
                # 支持旧格式（optimization_suggestions）和新格式（suggested_expressions）
                suggestions = analysis.get('suggested_expressions', []) or analysis.get('optimization_suggestions', [])
                
                for suggestion in suggestions:
                    # 新格式使用 'expression'，旧格式使用 'expression_example'
                    expr = suggestion.get('expression') or suggestion.get('expression_example')
                    if expr and expr not in candidates:
                        candidates.append(expr)
            
            self.log(f"Extracted {len(candidates)} unique expression candidates")
            return candidates
            
        except Exception as e:
            self.log(f"Error extracting expression candidates: {e}")
            return []
    

