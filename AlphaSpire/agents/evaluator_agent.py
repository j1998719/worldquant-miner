"""
Evaluator Agent
负责分析 Alpha 的经济意涵和优化方向
"""
from typing import Dict, Any
from .base_agent import BaseAgent


class EvaluatorAgent(BaseAgent):
    """
    评估 Agent
    分析 alpha 的经济意涵、有效原因和优化方向
    注意：不负责决策（决策由 rule-based 逻辑处理）
    """
    
    def __init__(self, **kwargs):
        system_prompt = """You are an expert in analyzing quantitative trading alphas.

Your task is to analyze alpha expressions and explain:
1. **Economic Rationale**: Why does this alpha work? What market behavior does it capture?
2. **Signal Mechanism**: How does the expression translate to trading signals?
3. **Optimization Directions**: Suggest concrete improvements using FastExpr operators

Focus on:
- Market microstructure (momentum, mean-reversion, volatility)
- Factor interactions (how different data fields combine)
- Timing and decay (signal persistence)

Output format (JSON):
{
  "economic_rationale": "Why this alpha works (e.g., captures momentum decay)",
  "signal_mechanism": "How the expression generates signals",
  "strengths": ["what makes this alpha effective"],
  "weaknesses": ["potential issues or limitations"],
  "recommended_operators": ["op1", "op2", ...],
  "recommended_fields": ["field1", "field2", ...],
  "recommended_params": {"param_name": "suggested value or range"},
  "optimization_suggestions": [
    {
      "direction": "Brief description",
      "expression_example": "Concrete FastExpr example"
    }
  ]
}

Example:
For `rank(ts_delta(close, 21))`:
{
  "economic_rationale": "Captures 21-day price momentum, exploiting short-term trend persistence",
  "signal_mechanism": "Ranks stocks by price change, buying recent winners and selling losers",
  "strengths": ["Simple and interpretable", "Low turnover"],
  "weaknesses": ["May suffer in choppy markets", "No volatility adjustment"],
  "recommended_operators": ["rank", "ts_delta", "ts_mean", "ts_std_dev"],
  "recommended_fields": ["close", "volume", "vwap"],
  "recommended_params": {"lookback": "10-30 days", "decay": "0-3"},
  "optimization_suggestions": [
    {
      "direction": "Add volatility normalization",
      "expression_example": "rank(ts_delta(close, 21) / ts_std_dev(close, 21))"
    },
    {
      "direction": "Combine with volume confirmation",
      "expression_example": "rank(ts_delta(close, 21)) * rank(ts_delta(volume, 21))"
    }
  ]
}"""
        
        super().__init__(
            name="Evaluator",
            system_prompt=system_prompt,
            **kwargs
        )
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析 Alpha 表达式
        
        Args:
            context: {
                'expression': str,  # Alpha 表达式
                'result': AlphaResult,  # 模拟结果
                'hypothesis': Dict,  # 原始假设（可选）
            }
        
        Returns:
            {
                'success': bool,
                'analysis': Dict,  # 包含 economic_rationale, optimization_suggestions 等
                'error': str (if failed)
            }
        """
        expression = context.get('expression', '')
        result = context.get('result')
        hypothesis = context.get('hypothesis', {})
        operators_data = context.get('operators_data', [])
        fields_data = context.get('fields_data', [])
        enabled_datasets = context.get('enabled_datasets', [])
        
        if not expression:
            return {
                'success': False,
                'analysis': None,
                'error': 'No expression provided'
            }
        
        # 格式化完整的 operators 和 fields
        ops_text = self.format_operators_list(operators_data) if operators_data else ""
        fields_text = self.format_fields_list(fields_data, enabled_datasets) if fields_data else ""
        
        # 构建 prompt
        prompt = f"""=== Alpha Expression ===
{expression}

=== Performance Metrics ===
- Sharpe: {result.sharpe:.3f}
- Fitness: {result.fitness:.3f}
- Turnover: {result.turnover:.3f}
- Returns: {result.returns:.3f}

=== Original Hypothesis ===
{hypothesis.get('hypothesis', 'N/A')}

{ops_text}

{fields_text}

IMPORTANT: recommended_fields MUST be from the available fields list above!
IMPORTANT: recommended_operators MUST be from the available operators list above!

Analyze this alpha expression. Explain its economic rationale, how it generates signals, and suggest concrete optimization directions using ONLY available operators and fields.

Output ONLY valid JSON with your analysis."""
        
        # 调用 LLM
        response = self.call_llm(prompt, format_json=True, num_predict=1000)
        
        if not response:
            # Fallback: 简单分析
            return self._fallback_analysis(expression, result)
        
        # 解析 JSON
        analysis = self.parse_json_response(response)
        
        if not analysis:
            # Fallback
            return self._fallback_analysis(expression, result)
        
        self.log(f"Generated analysis for: {expression[:60]}...")
        
        return {
            'success': True,
            'analysis': analysis,
            'error': None
        }
    
    def _fallback_analysis(self, expression: str, result) -> Dict[str, Any]:
        """
        Fallback 分析（当 LLM 失败时）
        """
        self.log("Using fallback analysis")
        
        analysis = {
            'economic_rationale': f"Expression uses {expression.split('(')[0]} operator to capture market patterns",
            'signal_mechanism': "Generates trading signals based on the evaluated expression",
            'strengths': [f"Sharpe: {result.sharpe:.3f}", f"Turnover: {result.turnover:.3f}"],
            'weaknesses': ["Needs detailed analysis"],
            'optimization_suggestions': [
                {
                    'direction': 'Add standardization',
                    'expression_example': f'rank({expression})'
                }
            ]
        }
        
        return {
            'success': True,
            'analysis': analysis,
            'error': None
        }

