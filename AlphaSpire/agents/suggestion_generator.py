"""
Suggestion Generator Agent
综合性能分析和表达式分析，生成具体的优化建议
"""
from typing import Dict, Any, List
from .base_agent import BaseAgent


class SuggestionGenerator(BaseAgent):
    """
    优化建议生成器
    基于性能指标和表达式分析，生成具体的优化建议
    """
    
    def __init__(self, **kwargs):
        system_prompt = """You are a quantitative finance expert specializing in alpha optimization.

Your task is to generate concrete optimization suggestions based on:
1. Performance metrics analysis (strengths, weaknesses, priorities)
2. Expression structure analysis (strategy type, operators, fields)

Generate 3-5 specific, actionable suggestions with actual expression examples.

Output format (JSON):
{
  "suggested_expressions": [
    {
      "direction": "What this optimization aims to improve",
      "expression": "Actual FastExpr expression (MUST be valid syntax)",
      "rationale": "Why this should help (1-2 sentences)"
    }
  ]
}

CRITICAL RULES:
1. Use ONLY operators from the available list
2. Use ONLY fields from the available list
3. Each expression MUST have correct number of parameters
4. Suggestions should directly address the identified weaknesses"""
        
        super().__init__(
            name="SuggestionGenerator",
            system_prompt=system_prompt,
            **kwargs
        )
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成优化建议
        
        Args:
            context: {
                'expression': str,
                'metrics_analysis': Dict,
                'expression_analysis': Dict,
                'operators_data': List[Dict],
                'fields_data': List[Dict],
                'enabled_datasets': List[str]
            }
        
        Returns:
            {
                'success': bool,
                'suggestions': List[Dict] or None,
                'error': str (if failed)
            }
        """
        expression = context.get('expression')
        metrics_analysis = context.get('metrics_analysis', {})
        expression_analysis = context.get('expression_analysis', {})
        operators_data = context.get('operators_data', [])
        fields_data = context.get('fields_data', [])
        enabled_datasets = context.get('enabled_datasets', [])
        
        if not expression:
            return {
                'success': False,
                'suggestions': None,
                'error': 'No expression provided'
            }
        
        # 格式化 operators 和 fields
        ops_text = self.format_operators_list(operators_data) if operators_data else ""
        fields_text = self.format_fields_list(fields_data, enabled_datasets) if fields_data else ""
        
        # 提取关键信息
        improvement_priority = metrics_analysis.get('improvement_priority', 'unknown')
        strategy_type = expression_analysis.get('strategy_type', 'unknown')
        key_operators = expression_analysis.get('key_operators', [])
        key_fields = expression_analysis.get('key_fields', [])
        
        prompt = f"""Generate optimization suggestions for this alpha:

=== Original Expression ===
{expression}

=== Performance Analysis ===
Grade: {metrics_analysis.get('performance_grade', 'unknown')}
Improvement Priority: {improvement_priority}
Strengths: {', '.join(metrics_analysis.get('key_strengths', []))}
Weaknesses: {', '.join(metrics_analysis.get('key_weaknesses', []))}

=== Expression Analysis ===
Strategy Type: {strategy_type}
Signal Mechanism: {expression_analysis.get('signal_mechanism', 'N/A')}

{ops_text}

{fields_text}

CRITICAL: Each operator requires EXACT number of parameters!
Examples:
- ts_corr(x, y, d) - needs 3 parameters
- ts_delta(x, d) - needs 2 parameters
- rank(x) - needs 1 parameter
- ts_decay_linear(x, d) - needs 2 parameters

Generate 3-5 concrete optimization suggestions.
Focus on addressing: {improvement_priority}

Output ONLY valid JSON with suggested_expressions array."""
        
        response = self.call_llm(prompt, format_json=True, num_predict=2000)
        
        if not response:
            return {
                'success': False,
                'suggestions': None,
                'error': 'LLM returned empty response'
            }
        
        result = self.parse_json_response(response)
        
        if not result or 'suggested_expressions' not in result:
            return {
                'success': False,
                'suggestions': None,
                'error': f'Failed to parse JSON or missing suggested_expressions: {response[:200]}'
            }
        
        suggestions = result['suggested_expressions']
        self.log(f"Generated {len(suggestions)} optimization suggestions")
        
        return {
            'success': True,
            'suggestions': suggestions,
            'error': None
        }

