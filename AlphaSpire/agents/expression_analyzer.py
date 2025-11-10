"""
Expression Analyzer Agent
分析 alpha 表达式的结构，推测其收益来源和策略类型
"""
from typing import Dict, Any, List
from .base_agent import BaseAgent


class ExpressionAnalyzer(BaseAgent):
    """
    表达式分析器
    分析 operators 和 fields 的组合，推测 alpha 的收益来源
    """
    
    def __init__(self, **kwargs):
        system_prompt = """You are a quantitative finance expert specializing in alpha expression analysis.

Your task is to analyze an alpha expression and identify:
1. Strategy type (momentum, mean-reversion, value, quality, etc.)
2. Signal generation mechanism
3. Economic rationale
4. Key operators and their roles
5. Data dependencies (which fields are critical)

Output format (JSON):
{
  "strategy_type": "momentum|mean_reversion|value|quality|volatility|composite",
  "signal_mechanism": "How signals are generated (2-3 sentences)",
  "economic_rationale": "Why this should work (2-3 sentences)",
  "key_operators": [
    {"operator": "operator_name", "role": "what it does in this strategy"}
  ],
  "key_fields": [
    {"field": "field_name", "role": "what it represents"}
  ]
}"""
        
        super().__init__(
            name="ExpressionAnalyzer",
            system_prompt=system_prompt,
            **kwargs
        )
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析表达式结构
        
        Args:
            context: {
                'expression': str,
                'operators_data': List[Dict],
                'fields_data': List[Dict],
                'enabled_datasets': List[str]
            }
        
        Returns:
            {
                'success': bool,
                'analysis': Dict or None,
                'error': str (if failed)
            }
        """
        expression = context.get('expression')
        operators_data = context.get('operators_data', [])
        fields_data = context.get('fields_data', [])
        enabled_datasets = context.get('enabled_datasets', [])
        
        if not expression:
            return {
                'success': False,
                'analysis': None,
                'error': 'No expression provided'
            }
        
        # 格式化 operators 和 fields
        ops_text = self.format_operators_list(operators_data) if operators_data else ""
        fields_text = self.format_fields_list(fields_data, enabled_datasets) if fields_data else ""
        
        prompt = f"""Analyze this alpha expression:

=== Expression ===
{expression}

{ops_text}

{fields_text}

Analyze:
1. What type of strategy is this?
2. How does it generate trading signals?
3. What is the economic logic?
4. Which operators are critical and why?
5. Which fields drive the signal?

Output ONLY valid JSON."""
        
        response = self.call_llm(prompt, format_json=True, num_predict=1500)
        
        if not response:
            return {
                'success': False,
                'analysis': None,
                'error': 'LLM returned empty response'
            }
        
        analysis = self.parse_json_response(response)
        
        if not analysis:
            return {
                'success': False,
                'analysis': None,
                'error': f'Failed to parse JSON: {response[:200]}'
            }
        
        self.log(f"Strategy type: {analysis.get('strategy_type', 'unknown')}")
        
        return {
            'success': True,
            'analysis': analysis,
            'error': None
        }

