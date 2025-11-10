"""
Optimizer Agent
负责优化现有的 Alpha 表达式
"""
from typing import Dict, Any
from .base_agent import BaseAgent


class OptimizerAgent(BaseAgent):
    """
    优化 Agent
    根据评估反馈优化 alpha 表达式
    """
    
    def __init__(self, **kwargs):
        system_prompt = """You are an expert in optimizing WorldQuant Brain alpha expressions.

Your task is to improve an existing alpha expression based on evaluation feedback.

Optimization strategies:
1. If turnover too high (>0.4): Add ts_rank, hump, or reduce lookback period
2. If sharpe too low: Try different operators, add cross-sectional standardization (rank/zscore)
3. If fitness low: Add winsorize to reduce outliers
4. If returns negative: Try reverse(), or change the direction

Common improvements:
- Add rank() or zscore() for cross-sectional normalization
- Add winsorize(expr, std=4) to handle outliers
- Use ts_rank instead of ts_delta for more stable signals
- Adjust lookback periods (try 5, 10, 21, 60, 120 days)
- Combine with other factors using multiply() or add()

CRITICAL RULES:
1. Use ONLY operators from the provided list
2. Keep the core logic similar but improve execution
3. Output ONLY valid FastExpr syntax
4. Explain what you changed and why

Output format (JSON):
{
  "optimized_expression": "improved expression",
  "changes_made": ["change1", "change2"],
  "rationale": "Why these changes should help",
  "target_improvement": "What metric should improve"
}"""
        
        super().__init__(
            name="Optimizer",
            system_prompt=system_prompt,
            **kwargs
        )
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        优化 Alpha 表达式
        
        Args:
            context: {
                'expression': str,  # 当前表达式
                'result': AlphaResult,  # 模拟结果
                'evaluation': Dict,  # 评估反馈
                'available_operators': List[str],  # 可用操作符
            }
        
        Returns:
            {
                'success': bool,
                'optimization': Dict,
                'error': str (if failed)
            }
        """
        expression = context.get('expression', '')
        result = context.get('result')
        evaluation = context.get('evaluation', {})
        available_operators = context.get('available_operators', [])
        
        if not expression or not result:
            return {
                'success': False,
                'optimization': None,
                'error': 'Missing expression or result'
            }
        
        # 分析主要问题
        issues = []
        if result.turnover > 0.4:
            issues.append(f"High turnover ({result.turnover:.3f})")
        if result.sharpe < 1.0:
            issues.append(f"Low Sharpe ({result.sharpe:.3f})")
        if result.fitness < 0.5:
            issues.append(f"Low fitness ({result.fitness:.3f})")
        
        # 限制操作符列表
        operators_sample = available_operators[:50] if len(available_operators) > 50 else available_operators
        
        # 构建 prompt
        prompt = f"""Current Expression: {expression}

Performance Issues:
{chr(10).join(f'- {issue}' for issue in issues)}

Results:
- Sharpe: {result.sharpe:.3f}
- Fitness: {result.fitness:.3f}
- Turnover: {result.turnover:.3f}
- Returns: {result.returns:.3f}

Evaluation Feedback:
{evaluation.get('analysis', 'N/A')}

Available Operators (use ONLY these):
{', '.join(operators_sample)}

Optimize this expression to address the main issues.
Focus on the most critical problem: {issues[0] if issues else 'general improvement'}

Output ONLY valid JSON with the optimized expression."""
        
        # 调用 LLM
        response = self.call_llm(prompt, format_json=True, num_predict=1000)
        
        if not response:
            return {
                'success': False,
                'optimization': None,
                'error': 'LLM returned empty response'
            }
        
        # 解析 JSON
        optimization = self.parse_json_response(response)
        
        if not optimization or 'optimized_expression' not in optimization:
            return {
                'success': False,
                'optimization': None,
                'error': f'Failed to parse optimization: {response[:200]}'
            }
        
        optimized_expr = optimization['optimized_expression']
        self.log(f"Optimized: {expression[:50]}... -> {optimized_expr[:50]}...")
        
        return {
            'success': True,
            'optimization': optimization,
            'error': None
        }

