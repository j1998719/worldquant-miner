"""
Alpha Designer Agent
负责根据假设设计 Alpha 表达式
"""
from typing import Dict, Any, List
from .base_agent import BaseAgent


class AlphaDesignerAgent(BaseAgent):
    """
    Alpha 设计 Agent
    根据投资假设和可用的 operators/fields 设计具体的 alpha 表达式
    """
    
    def __init__(self, **kwargs):
        system_prompt = """You are an expert in designing WorldQuant Brain alpha expressions.

Your task is to translate investment hypotheses into valid FastExpr alpha expressions.

CRITICAL RULES:
1. Use ONLY operators and fields from the provided lists
2. DO NOT invent new operators (e.g., no "alpha_returns", "slow_fast_factor_decay")
3. Follow FastExpr syntax exactly
4. All expressions must be valid and executable

Common patterns:
- Momentum: ts_delta(field, days), ts_rank(field, days)
- Standardization: rank(expr), zscore(expr), normalize(expr)
- Filtering: winsorize(expr, std=4)
- Aggregation: ts_mean(field, days), ts_sum(field, days)

Output format (JSON):
{
  "expression": "valid FastExpr expression",
  "explanation": "What this expression captures",
  "operators_used": ["op1", "op2"],
  "fields_used": ["field1", "field2"],
  "expected_properties": {
    "sharpe": "estimated range",
    "turnover": "estimated value"
  }
}

Example:
{
  "expression": "rank(ts_delta(close, 21))",
  "explanation": "Ranks stocks by 21-day price momentum",
  "operators_used": ["rank", "ts_delta"],
  "fields_used": ["close"],
  "expected_properties": {
    "sharpe": "0.5-1.5",
    "turnover": "0.1-0.2"
  }
}"""
        
        super().__init__(
            name="AlphaDesigner",
            system_prompt=system_prompt,
            **kwargs
        )
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        设计 Alpha 表达式
        
        Args:
            context: {
                'hypothesis': Dict,  # 投资假设
                'available_operators': List[str],  # 可用操作符
                'available_fields': List[str],  # 可用字段
                'previous_attempts': List[str],  # 之前尝试的表达式（可选）
            }
        
        Returns:
            {
                'success': bool,
                'alpha_design': Dict or None,
                'error': str (if failed)
            }
        """
        hypothesis = context.get('hypothesis', {})
        available_operators = context.get('available_operators', [])
        available_fields = context.get('available_fields', [])
        previous_attempts = context.get('previous_attempts', [])
        
        if not hypothesis:
            return {
                'success': False,
                'alpha_design': None,
                'error': 'No hypothesis provided'
            }
        
        # 限制操作符和字段列表长度（避免 token 溢出）
        operators_sample = available_operators[:50] if len(available_operators) > 50 else available_operators
        fields_sample = available_fields[:100] if len(available_fields) > 100 else available_fields
        
        # 构建 prompt
        prompt = f"""Hypothesis: {hypothesis.get('hypothesis', '')}
Rationale: {hypothesis.get('rationale', '')}
Expected Signal: {hypothesis.get('expected_signal', '')}

Available Operators (use ONLY these):
{', '.join(operators_sample)}

Available Fields (sample, use ONLY these):
{', '.join(fields_sample[:30])}  # 只显示前30个字段示例
... and {len(fields_sample) - 30} more

Design a valid FastExpr alpha expression that tests this hypothesis."""
        
        if previous_attempts:
            prompt += f"\n\nPrevious attempts (design something DIFFERENT):"
            for i, attempt in enumerate(previous_attempts[-3:], 1):
                prompt += f"\n{i}. {attempt}"
        
        prompt += "\n\nOutput ONLY valid JSON with the expression."
        
        # 调用 LLM
        response = self.call_llm(prompt, format_json=True, num_predict=1000)
        
        if not response:
            return {
                'success': False,
                'alpha_design': None,
                'error': 'LLM returned empty response'
            }
        
        # 解析 JSON
        alpha_design = self.parse_json_response(response)
        
        if not alpha_design:
            return {
                'success': False,
                'alpha_design': None,
                'error': f'Failed to parse JSON: {response[:200]}'
            }
        
        # 验证必要字段
        if 'expression' not in alpha_design:
            return {
                'success': False,
                'alpha_design': None,
                'error': 'Missing expression field'
            }
        
        expression = alpha_design['expression']
        self.log(f"Designed alpha: {expression}")
        
        return {
            'success': True,
            'alpha_design': alpha_design,
            'error': None
        }

