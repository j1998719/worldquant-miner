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

Your task is to generate testable quantitative trading hypotheses based on:
1. Market behavior patterns
2. Financial fundamentals
3. Technical indicators
4. Cross-sectional relationships

Output format (JSON):
{
  "hypothesis": "Clear statement of the relationship or pattern",
  "rationale": "Why this relationship might hold",
  "expected_signal": "What the alpha should capture (momentum/value/quality/etc.)",
  "time_horizon": "Short-term/Medium-term/Long-term",
  "key_factors": ["factor1", "factor2", ...]
}

Example:
{
  "hypothesis": "Stocks with increasing analyst estimate revisions outperform peers",
  "rationale": "Upward revisions signal improving fundamentals and analyst confidence",
  "expected_signal": "earnings_momentum",
  "time_horizon": "Medium-term",
  "key_factors": ["analyst_estimates", "earnings", "revisions"]
}

Be specific, testable, and based on sound financial logic."""
        
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
                'focus_area': str,  # 聚焦领域（可选）
            }
        
        Returns:
            {
                'success': bool,
                'hypothesis': Dict or None,
                'error': str (if failed)
            }
        """
        previous_failures = context.get('previous_failures', [])
        focus_area = context.get('focus_area', '')
        
        # 构建 prompt
        prompt = "Generate a new quantitative trading hypothesis."
        
        if focus_area:
            prompt += f"\n\nFocus on: {focus_area}"
        
        if previous_failures:
            prompt += "\n\nPreviously tried hypotheses (avoid similar ones):"
            for i, failure in enumerate(previous_failures[-3:], 1):  # 只显示最近3个
                prompt += f"\n{i}. {failure}"
        
        prompt += "\n\nGenerate a NEW, DIFFERENT hypothesis. Output ONLY valid JSON."
        
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
        required_fields = ['hypothesis', 'rationale', 'expected_signal']
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

