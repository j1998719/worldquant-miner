"""
Refinement Agent - Improve underperforming alphas
Applies modifications to alpha expressions based on evaluation decisions
"""

import re
import aiohttp
from typing import List, Dict
from datetime import datetime

from base_agent import BaseAgent


class RefinementAgent(BaseAgent):
    """
    Agent for refining alpha expressions that show potential but need improvement
    Can negate signals, adjust parameters, add normalizations, etc.
    """

    def __init__(self, config: Dict):
        """
        Initialize refinement agent

        Args:
            config: Configuration dict
        """
        super().__init__('refinement_agent', config)

        self.ollama_url = config.get('ollama_url', 'https://ollama.com')
        self.ollama_model = config.get('cloud_model', 'gpt-oss:120b')
        self.ollama_api_key = config.get('ollama_api_key', '')

        self.temperature = 0.6  # Lower temperature for more conservative refinements
        self.max_refinement_iterations = config.get('refinement', {}).get('max_iterations', 2)

    async def run(self, refinement_candidates: List[Dict]) -> List[Dict]:
        """
        Refine alpha expressions

        Args:
            refinement_candidates: List of candidates with modification suggestions

        Returns:
            List of refined expression dicts
        """
        start_time = datetime.now()
        self.logger.info(f"Refining {len(refinement_candidates)} alpha expressions")

        refined_expressions = []

        for candidate in refinement_candidates:
            refined = await self._refine_single_expression(candidate)
            if refined:
                refined_expressions.extend(refined)

        self.logger.info(f"Generated {len(refined_expressions)} refined expressions")
        self.log_execution_time(start_time, "Refinement")

        return refined_expressions

    async def _refine_single_expression(self, candidate: Dict) -> List[Dict]:
        """
        Refine a single expression

        Args:
            candidate: Refinement candidate dict

        Returns:
            List of refined expression dicts
        """
        expression = candidate.get('expression', '')
        expression_id = candidate.get('expression_id', '')
        decision_type = candidate.get('decision_type', '')
        modifications = candidate.get('modifications', [])

        self.logger.info(
            f"Refining {expression_id}: decision={decision_type}, "
            f"modifications={modifications}"
        )

        refined_expressions = []

        # Handle negation (simple rule-based)
        if decision_type == 'refine_negate' or 'negate_signal' in modifications:
            negated = self._negate_expression(expression, expression_id)
            if negated:
                refined_expressions.append(negated)

        # Handle adjustments (use LLM for complex modifications)
        if decision_type == 'refine_adjust':
            adjusted = await self._adjust_expression_with_llm(
                expression, expression_id, modifications, candidate
            )
            refined_expressions.extend(adjusted)

        return refined_expressions

    def _negate_expression(self, expression: str, expression_id: str) -> Dict:
        """
        Negate an expression (multiply by -1 or flip signal)

        Args:
            expression: Original expression
            expression_id: Expression ID

        Returns:
            Refined expression dict
        """
        # Simple negation: wrap in -(...) or negate rank
        negated = None

        if expression.strip().startswith('rank('):
            # rank(x) → rank(-x)
            negated = expression.replace('rank(', 'rank(-(', 1)
            # Add closing paren
            negated = negated[:-1] + '))'
        elif expression.strip().startswith('scale('):
            # scale(x) → scale(-x)
            negated = expression.replace('scale(', 'scale(-(', 1)
            negated = negated[:-1] + '))'
        else:
            # General negation: -(expression)
            negated = f"-({expression})"

        self.logger.debug(f"Negated: {expression} → {negated}")

        return {
            'expression_id': f"{expression_id}_negated",
            'expression': negated,
            'parent_idea_id': expression_id,
            'variant_type': 'negated',
            'description': 'Negated signal based on negative Sharpe',
            'parameters': {'refinement_type': 'negate'},
            'timestamp': self.get_timestamp()
        }

    async def _adjust_expression_with_llm(
        self,
        expression: str,
        expression_id: str,
        modifications: List[str],
        candidate: Dict
    ) -> List[Dict]:
        """
        Use LLM to adjust expression based on suggested modifications

        Args:
            expression: Original expression
            expression_id: Expression ID
            modifications: List of modification types
            candidate: Full candidate dict with performance data

        Returns:
            List of refined expression dicts
        """
        prompt = self._build_refinement_prompt(expression, modifications, candidate)

        try:
            response = await self._call_ollama(prompt, self.temperature)
            refined_exprs = self._parse_refinement_response(response, expression_id)
            return refined_exprs
        except Exception as e:
            self.logger.error(f"LLM refinement failed: {e}")
            return []

    def _build_refinement_prompt(
        self,
        expression: str,
        modifications: List[str],
        candidate: Dict
    ) -> str:
        """Build refinement prompt for LLM"""
        sharpe = candidate.get('sharpe', 0)
        fitness = candidate.get('fitness', 0)
        turnover = candidate.get('turnover', 0)

        modification_guidance = {
            'increase_windows': "Increase lookback windows (e.g., 20 → 60, 5 → 10) to reduce turnover",
            'add_normalization': "Add or improve normalization (rank, zscore, scale, winsorize)",
            'try_different_neutralization': "Change the cross-sectional aspect (try different ranking schemes)",
            'reduce_complexity': "Simplify the expression to avoid overfitting"
        }

        guidance_text = "\n".join([
            f"- {modification_guidance.get(mod, mod)}"
            for mod in modifications
        ])

        prompt = f"""You are a WorldQuant Brain alpha refinement expert.

Original Expression: {expression}

Performance Issues:
- Sharpe: {sharpe:.2f}
- Fitness: {fitness:.2f}
- Turnover: {turnover:.0f}

Suggested Modifications:
{guidance_text}

Task: Generate 2-3 refined versions of this expression that address the issues.

Requirements:
1. Keep the core logic but adjust parameters
2. Maintain valid FASTEXPR syntax
3. Avoid look-ahead bias
4. Make meaningful changes (not just minor tweaks)

Output as JSON:
{{
  "refined_expressions": [
    {{
      "expression": "refined formula here",
      "description": "What was changed",
      "rationale": "Why this might improve performance"
    }}
  ]
}}

Generate refined expressions now:"""

        return prompt

    def _parse_refinement_response(self, response: str, base_expression_id: str) -> List[Dict]:
        """Parse LLM refinement response"""
        import json

        try:
            # Extract JSON
            response_text = response.strip()
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()

            data = json.loads(response_text)
            refined_list = data.get('refined_expressions', [])

            results = []
            for i, ref_dict in enumerate(refined_list):
                refined_expr = {
                    'expression_id': f"{base_expression_id}_refined{i+1}",
                    'expression': ref_dict.get('expression', ''),
                    'parent_idea_id': base_expression_id,
                    'variant_type': 'refined',
                    'description': ref_dict.get('description', ''),
                    'parameters': {
                        'refinement_type': 'adjust',
                        'rationale': ref_dict.get('rationale', '')
                    },
                    'timestamp': self.get_timestamp()
                }

                if refined_expr['expression']:
                    results.append(refined_expr)

            return results

        except Exception as e:
            self.logger.error(f"Failed to parse refinement response: {e}")
            return []

    async def _call_ollama(self, prompt: str, temperature: float) -> str:
        """Call Ollama Cloud API"""
        url = f"{self.ollama_url}/api/chat"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.ollama_api_key}"
        }
        payload = {
            "model": self.ollama_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=90) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Ollama API error {response.status}: {error_text}")

                result = await response.json()
                return result['message']['content']
