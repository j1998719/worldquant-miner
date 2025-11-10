"""
Hypothesis Agent
负责生成投资假设
"""
from typing import Dict, Any, Optional
from .base_agent import BaseAgent


class HypothesisAgent(BaseAgent):
    """
    假设生成 Agent
    根据市场知识和历史数据生成投资假设
    """
    
    def __init__(self, **kwargs):
        system_prompt = """You are a quantitative researcher specializing in generating investment hypotheses.

Generate concise, testable trading hypotheses with concrete implementation guidance.

Output format (JSON):
{
  "hypothesis": "Brief statement of the market pattern or relationship",
  "recommended_operators": ["op1", "op2", "op3"],
  "recommended_fields": ["field1", "field2"],
  "recommended_params": {"param_name": "value or range"}
}

CRITICAL: 
- recommended_fields MUST be chosen from the available fields list provided in the prompt
- recommended_operators should be common FastExpr operators (rank, ts_delta, ts_mean, decay, etc.)
- recommended_params should specify lookback periods, decay values, or thresholds

Example:
{
  "hypothesis": "Short-term price momentum predicts future returns",
  "recommended_operators": ["ts_delta", "rank", "decay"],
  "recommended_fields": ["close", "volume"],
  "recommended_params": {"lookback": "5-21 days", "decay": "0-3"}
}"""
        
        super().__init__(
            name="HypothesisAgent",
            system_prompt=system_prompt,
            **kwargs
        )
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成投资假设
        
        Args:
            context: {
                'previous_failures': List[str],  # 之前失败的假设（可选）
                'operators_data': List[Dict],  # 完整的 operators 数据（必须）
                'fields_data': List[Dict],  # 完整的 fields 数据（必须）
                'enabled_datasets': List[str],  # 启用的数据集（可选）
            }
        
        Returns:
            {
                'success': bool,
                'hypothesis': Dict or None,
                'error': str (if failed)
            }
        """
        previous_failures = context.get('previous_failures', [])
        operators_data = context.get('operators_data', [])
        fields_data = context.get('fields_data', [])
        enabled_datasets = context.get('enabled_datasets', [])
        
        # 构建 prompt
        prompt = "Generate a new quantitative trading hypothesis.\n\n"
        
        # 使用完整的 operators 数据
        if operators_data:
            prompt += self.format_operators_list(operators_data)
            prompt += "\n"
        
        # 使用完整的 fields 数据
        if fields_data:
            prompt += self.format_fields_list(fields_data, enabled_datasets)
            prompt += "\n"
        
        # 避免重复之前的失败
        if previous_failures:
            prompt += "=== Previously Tried Hypotheses (avoid similar) ===\n"
            for i, failure in enumerate(previous_failures[-3:], 1):
                prompt += f"{i}. {failure}\n"
            prompt += "\n"
        
        prompt += "IMPORTANT: recommended_fields MUST be from the available fields list above!\n"
        prompt += "IMPORTANT: recommended_operators MUST be from the available operators list above!\n\n"
        prompt += "Generate a NEW, DIFFERENT hypothesis. Output ONLY valid JSON."
        
        # 调用 LLM
        response = self.call_llm(prompt, format_json=True, num_predict=500)
        
        if not response:
            return {
                'success': False,
                'hypothesis': None,
                'error': 'LLM returned empty response'
            }
        
        # 解析 JSON
        hypothesis = self.parse_json_response(response)
        
        if not hypothesis:
            return {
                'success': False,
                'hypothesis': None,
                'error': f'Failed to parse JSON: {response[:200]}'
            }
        
        # 验证必要字段
        required_fields = ['hypothesis', 'recommended_operators', 'recommended_fields', 'recommended_params']
        missing_fields = [f for f in required_fields if f not in hypothesis]
        
        if missing_fields:
            return {
                'success': False,
                'hypothesis': None,
                'error': f'Missing required fields: {missing_fields}'
            }
        
        self.log(f"Generated hypothesis: {hypothesis['hypothesis']}")
        
        return {
            'success': True,
            'hypothesis': hypothesis,
            'error': None
        }

