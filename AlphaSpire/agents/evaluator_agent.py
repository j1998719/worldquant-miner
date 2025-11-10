"""
Evaluator Agent
负责评估 Alpha 结果并决定下一步行动
"""
from typing import Dict, Any
from .base_agent import BaseAgent


class EvaluatorAgent(BaseAgent):
    """
    评估 Agent
    评估模拟结果并决定是优化还是生成新假设
    """
    
    def __init__(self, **kwargs):
        system_prompt = """You are an expert quantitative analyst evaluating alpha performance.

Your task is to:
1. Analyze simulation results
2. Identify what works and what doesn't
3. Decide whether to optimize the current alpha or generate a new hypothesis

Evaluation criteria (WorldQuant Brain's grading system):
- Sharpe Ratio >= 1.25 (LOW_SHARPE threshold)
- Fitness >= 1.0 (LOW_FITNESS threshold)
- Turnover: 0.01 <= turnover <= 0.7 (LOW/HIGH_TURNOVER limits)
- Returns > 0

Decision logic:
- If ALL criteria met: ACCEPT (stop iteration)
- If Sharpe >= 0.5 and Fitness >= 0.6 ("hopeful"): OPTIMIZE (try to improve)
- If Sharpe < 0.5 or major issues: NEW_HYPOTHESIS (start fresh)

Output format (JSON):
{
  "decision": "ACCEPT" | "OPTIMIZE" | "NEW_HYPOTHESIS",
  "analysis": "Detailed analysis of the results",
  "strengths": ["what works well"],
  "weaknesses": ["what needs improvement"],
  "recommendation": "Specific recommendation for next step"
}"""
        
        super().__init__(
            name="Evaluator",
            system_prompt=system_prompt,
            **kwargs
        )
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估 Alpha 结果
        
        Args:
            context: {
                'result': AlphaResult,  # 模拟结果
                'expression': str,  # Alpha 表达式
                'hypothesis': Dict,  # 原始假设
                'iteration': int,  # 当前迭代次数
            }
        
        Returns:
            {
                'success': bool,
                'evaluation': Dict,
                'error': str (if failed)
            }
        """
        result = context.get('result')
        expression = context.get('expression', '')
        hypothesis = context.get('hypothesis', {})
        iteration = context.get('iteration', 0)
        
        if not result:
            return {
                'success': False,
                'evaluation': None,
                'error': 'No result provided'
            }
        
        # 构建 prompt
        prompt = f"""Alpha Expression: {expression}

Hypothesis: {hypothesis.get('hypothesis', 'N/A')}

Simulation Results:
- Sharpe: {result.sharpe:.3f}
- Fitness: {result.fitness:.3f}
- Turnover: {result.turnover:.3f}
- Returns: {result.returns:.3f}
- Drawdown: {result.drawdown:.3f}
- Success: {result.success}
{f'- Error: {result.error_message}' if result.error_message else ''}

Current iteration: {iteration}

Analyze these results and decide:
1. ACCEPT - if meets ALL WorldQuant criteria (Sharpe >= 1.25, Fitness >= 1.0, 0.01 <= Turnover <= 0.7)
2. OPTIMIZE - if "hopeful" but needs improvement (Sharpe >= 0.5, Fitness >= 0.6)
3. NEW_HYPOTHESIS - if fundamental issues (Sharpe < 0.5 or failed)

Output ONLY valid JSON with your decision and analysis."""
        
        # 调用 LLM
        response = self.call_llm(prompt, format_json=True, num_predict=800)
        
        if not response:
            # 如果 LLM 失败，使用规则基础的评估
            return self._fallback_evaluation(result, iteration)
        
        # 解析 JSON
        evaluation = self.parse_json_response(response)
        
        if not evaluation or 'decision' not in evaluation:
            # JSON 解析失败，使用 fallback
            return self._fallback_evaluation(result, iteration)
        
        decision = evaluation.get('decision', 'NEW_HYPOTHESIS')
        self.log(f"Evaluation decision: {decision}")
        
        return {
            'success': True,
            'evaluation': evaluation,
            'error': None
        }
    
    def _fallback_evaluation(self, result, iteration: int) -> Dict[str, Any]:
        """
        基于规则的 fallback 评估
        当 LLM 失败时使用
        """
        self.log("Using fallback rule-based evaluation")
        
        # 规则基础的决策（使用 WorldQuant 标准）
        if result.passes_criteria(min_sharpe=1.25, min_fitness=1.0, max_turnover=0.7, min_turnover=0.01):
            decision = "ACCEPT"
            analysis = f"✅ Meets ALL WorldQuant criteria: Sharpe={result.sharpe:.3f}, Fitness={result.fitness:.3f}"
        elif result.is_hopeful(min_sharpe=0.5, min_fitness=0.6) and iteration < 3:
            decision = "OPTIMIZE"
            analysis = f"🔧 Hopeful alpha worth optimizing: Sharpe={result.sharpe:.3f}, Fitness={result.fitness:.3f}"
        else:
            decision = "NEW_HYPOTHESIS"
            if not result.success:
                analysis = f"❌ Failed with error: {result.error_message}"
            else:
                analysis = f"🔄 Below hopeful threshold (Sharpe={result.sharpe:.3f}, Fitness={result.fitness:.3f}), needs new approach"
        
        evaluation = {
            'decision': decision,
            'analysis': analysis,
            'strengths': [],
            'weaknesses': [],
            'recommendation': f"Proceed with {decision}"
        }
        
        return {
            'success': True,
            'evaluation': evaluation,
            'error': None
        }

