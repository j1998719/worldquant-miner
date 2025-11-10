"""
Metrics Analyzer Agent
分析 alpha 的性能指标（Sharpe, Fitness, Turnover, Returns）
"""
from typing import Dict, Any
from .base_agent import BaseAgent


class MetricsAnalyzer(BaseAgent):
    """
    性能指标分析器
    基于 WorldQuant Brain 的评分标准分析 alpha 表现
    """
    
    def __init__(self, **kwargs):
        system_prompt = """You are a quantitative finance expert analyzing alpha performance metrics.

WorldQuant Brain Metrics:

1. **Sharpe Ratio**: Risk-adjusted returns
   - Measures return per unit of risk
   - Higher is better (target >= 1.25)

2. **Fitness**: Overall quality score
   - Formula: Fitness = Sharpe * abs(Returns) / Turnover
   - Balances profitability against trading costs
   - Higher fitness = better risk-adjusted returns with lower turnover
   - Target >= 1.0

3. **Turnover**: Trading frequency
   - Measures how often positions change
   - Too high (>0.7) = excessive trading costs
   - Too low (<0.1) = insufficient signal utilization
   - Optimal range varies by strategy

4. **Returns**: Absolute returns
   - Total profit/loss
   - Target > 0.1 (10%+)

Output format (JSON):
{
  "performance_grade": "excellent|good|fair|poor",
  "sharpe_analysis": "Assessment of Sharpe ratio vs target",
  "fitness_analysis": "Assessment of fitness score vs target (explain the formula)",
  "turnover_analysis": "Assessment of turnover vs optimal range",
  "key_strengths": ["strength1", "strength2"],
  "key_weaknesses": ["weakness1", "weakness2"],
  "improvement_priority": "sharpe|fitness|turnover"
}"""
        
        super().__init__(
            name="MetricsAnalyzer",
            system_prompt=system_prompt,
            **kwargs
        )
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        分析性能指标
        
        Args:
            context: {
                'result': AlphaResult object,
                'criteria': Dict (success criteria from config)
            }
        
        Returns:
            {
                'success': bool,
                'analysis': Dict or None,
                'error': str (if failed)
            }
        """
        result = context.get('result')
        criteria = context.get('criteria', {})
        
        if not result:
            return {
                'success': False,
                'analysis': None,
                'error': 'No result provided'
            }
        
        # 提取 criteria（如果没有提供，使用默认值）
        min_sharpe = criteria.get('min_sharpe', 1.25)
        min_fitness = criteria.get('min_fitness', 1.0)
        max_turnover = criteria.get('max_turnover', 0.7)
        min_turnover = criteria.get('min_turnover', 0.1)
        min_returns = criteria.get('min_returns', 0.1)
        
        # 计算 Fitness（验证公式）
        calculated_fitness = 0
        if result.turnover > 0:
            calculated_fitness = result.sharpe * abs(result.returns) / result.turnover
        
        prompt = f"""Analyze this alpha's performance metrics:

=== Performance Metrics ===
- Sharpe Ratio: {result.sharpe:.3f}
- Fitness: {result.fitness:.3f}
- Turnover: {result.turnover:.3f}
- Returns: {result.returns:.3f}

=== Calculated Fitness (for verification) ===
Fitness = Sharpe * abs(Returns) / Turnover
        = {result.sharpe:.3f} * {abs(result.returns):.3f} / {result.turnover:.3f}
        = {calculated_fitness:.3f}

=== Success Criteria (from config.yaml) ===
- Minimum Sharpe: {min_sharpe}
- Minimum Fitness: {min_fitness}
- Turnover Range: {min_turnover} - {max_turnover}
- Minimum Returns: {min_returns}

=== Pass/Fail Status ===
- Sharpe: {"✅ PASS" if result.sharpe >= min_sharpe else f"❌ FAIL (need {min_sharpe - result.sharpe:.2f} more)"}
- Fitness: {"✅ PASS" if result.fitness >= min_fitness else f"❌ FAIL (need {min_fitness - result.fitness:.2f} more)"}
- Turnover: {"✅ PASS" if min_turnover <= result.turnover <= max_turnover else f"❌ FAIL (out of range)"}
- Returns: {"✅ PASS" if result.returns >= min_returns else f"❌ FAIL (need {min_returns - result.returns:.2f} more)"}

Provide a concise analysis focusing on:
1. Overall performance grade (relative to criteria)
2. Specific strengths and weaknesses
3. Priority area for improvement
4. Explain the Fitness formula relationship

Output ONLY valid JSON."""
        
        response = self.call_llm(prompt, format_json=True, num_predict=1000)
        
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
        
        self.log(f"Metrics analysis: {analysis.get('performance_grade', 'unknown')}")
        
        return {
            'success': True,
            'analysis': analysis,
            'error': None
        }

