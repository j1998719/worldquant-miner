"""
Alpha Designer Agent
负责根据假设设计 Alpha 表达式
"""
import json
from pathlib import Path
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
                'operators_data': List[Dict],  # 完整的 operators 数据
                'fields_data': List[Dict],  # 完整的 fields 数据
                'enabled_datasets': List[str],  # 启用的数据集
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
        previous_attempts = context.get('previous_attempts', [])
        
        if not hypothesis:
            return {
                'success': False,
                'alpha_design': None,
                'error': 'No hypothesis provided'
            }
        
        # 加载 hopeful_alphas.json（成功案例参考）
        hopeful_alphas_text = self._load_hopeful_alphas()
        
        # 获取完整的 operators 和 fields 数据
        operators_data = context.get('operators_data', [])
        fields_data = context.get('fields_data', [])
        enabled_datasets = context.get('enabled_datasets', [])
        
        # 格式化完整的 operators 和 fields
        ops_text = self.format_operators_list(operators_data) if operators_data else ""
        fields_text = self.format_fields_list(fields_data, enabled_datasets) if fields_data else ""
        
        # 从 hypothesis 提取 recommended 信息
        hyp_text = hypothesis.get('hypothesis', '')
        hyp_operators = hypothesis.get('recommended_operators', [])
        hyp_fields = hypothesis.get('recommended_fields', [])
        hyp_params = hypothesis.get('recommended_params', {})
        
        # 构建 prompt
        prompt = f"""=== Current Hypothesis ===
{hyp_text}

Recommended Operators: {', '.join(hyp_operators) if hyp_operators else 'Any'}
Recommended Fields: {', '.join(hyp_fields) if hyp_fields else 'Any'}
Recommended Params: {', '.join([f'{k}={v}' for k, v in hyp_params.items()]) if hyp_params else 'Any'}

{hopeful_alphas_text}

{ops_text}

CRITICAL: Each operator requires EXACT number of parameters!
Examples:
- ts_corr(x, y, d) - needs 3 parameters (two series, one lookback period)
- ts_delta(x, d) - needs 2 parameters (series, lookback period)
- rank(x) - needs 1 parameter
- decay(x, d) - needs 2 parameters (series, decay period)

{fields_text}

PRIORITY: Use fields from hypothesis.recommended_fields if possible.
PRIORITY: Use operators from hypothesis.recommended_operators if possible.

Design a valid FastExpr alpha expression that tests this hypothesis.
VERIFY that all operators have correct number of parameters before outputting."""
        
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
    
    def _load_hopeful_alphas(self) -> str:
        """加载 hopeful_alphas.json 并格式化为 prompt 文本"""
        hopeful_file = Path(__file__).resolve().parents[1] / "results" / "hopeful_alphas.json"
        
        if not hopeful_file.exists():
            return ""
        
        try:
            with open(hopeful_file, 'r', encoding='utf-8') as f:
                hopeful_alphas = json.load(f)
            
            if not hopeful_alphas:
                return ""
            
            # 格式化为 prompt 文本
            text = "\n=== SUCCESSFUL ALPHAS (Learn from these patterns) ===\n"
            for i, alpha in enumerate(hopeful_alphas[-5:], 1):  # 只显示最近 5 个
                text += f"\n{i}. Expression: {alpha['expression']}\n"
                text += f"   Sharpe: {alpha['result']['sharpe']:.3f}, Fitness: {alpha['result']['fitness']:.3f}\n"
                
                analysis = alpha.get('analysis', {})
                if analysis:
                    text += f"   Why it works: {analysis.get('economic_rationale', 'N/A')[:150]}...\n"
                    
                    # 显示 recommended operators 和 fields
                    rec_ops = analysis.get('recommended_operators', [])
                    rec_fields = analysis.get('recommended_fields', [])
                    if rec_ops:
                        text += f"   Used Operators: {', '.join(rec_ops[:5])}\n"
                    if rec_fields:
                        text += f"   Used Fields: {', '.join(rec_fields[:5])}\n"
                    
                    # 显示优化建议
                    suggestions = analysis.get('optimization_suggestions', [])
                    if suggestions:
                        text += f"   Optimization ideas:\n"
                        for j, sug in enumerate(suggestions[:2], 1):  # 只显示前 2 个
                            text += f"      - {sug.get('direction', '')}: {sug.get('expression_example', '')}\n"
            
            text += "\nUse these successful patterns to inspire your design!\n"
            return text
            
        except Exception as e:
            self.log(f"Error loading hopeful_alphas: {e}")
            return ""

