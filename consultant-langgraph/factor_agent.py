"""
Factor Agent - Convert alpha ideas into WorldQuant Brain expressions
Uses Ollama LLM to generate valid FASTEXPR formulas
"""

import aiohttp
import asyncio
from typing import List, Dict
from datetime import datetime

from base_agent import BaseAgent


class FactorAgent(BaseAgent):
    """
    Agent for converting alpha ideas into executable WorldQuant Brain expressions
    Generates multiple formula variants per idea
    """

    def __init__(self, config: Dict):
        """
        Initialize factor agent

        Args:
            config: Configuration dict
        """
        super().__init__('factor_agent', config)

        self.ollama_url = config.get('ollama_url', 'https://ollama.com')
        self.ollama_model = config.get('cloud_model', 'gpt-oss:120b')
        self.ollama_api_key = config.get('ollama_api_key', '')

        self.temperature = config.get('factor_agent', {}).get('temperature', 0.7)
        self.max_retries = config.get('factor_agent', {}).get('max_retries', 3)
        self.expressions_per_idea = config.get('factor_agent', {}).get('expressions_per_idea', 2)

        # Load WorldQuant operators reference
        self.operators_ref = self._load_operators_reference()

    def _load_operators_reference(self) -> str:
        """Load WorldQuant operators reference for prompts"""
        return """
WorldQuant Brain FASTEXPR Operators:

TIME-SERIES OPERATORS:
- ts_sum(x, d): Sum over past d days
- ts_mean(x, d): Average over past d days
- ts_std(x, d): Standard deviation over past d days
- ts_rank(x, d): Rank over past d days [0-1]
- ts_max(x, d): Maximum over past d days
- ts_min(x, d): Minimum over past d days
- ts_delta(x, d): x - delay(x, d)
- ts_corr(x, y, d): Correlation over past d days
- delay(x, d): Value d days ago

CROSS-SECTIONAL OPERATORS:
- rank(x): Cross-sectional rank [0-1]
- zscore(x): Cross-sectional z-score
- scale(x): Scale to [-1, 1]

MATHEMATICAL OPERATORS:
- abs(x), log(x), sign(x), sqrt(x)
- power(x, n), exp(x)
- max(x, y), min(x, y)

LOGICAL OPERATORS:
- if(condition, then_value, else_value)
- x > y, x < y, x == y

DATA FIELDS:
- close, open, high, low, vwap
- volume, returns
- fundamental fields (see datasets)
"""

    async def run(self, ideas: List[Dict]) -> List[Dict]:
        """
        Generate WorldQuant Brain expressions from ideas

        Args:
            ideas: List of idea dicts

        Returns:
            List of expression dicts
        """
        start_time = datetime.now()
        self.logger.info(f"Generating expressions for {len(ideas)} ideas")

        # Load prompt template
        prompt_template = self.load_prompt('formula_generation.txt')
        if not prompt_template:
            self.logger.warning("Prompt template not found, using fallback")
            prompt_template = self._get_fallback_prompt()

        # Generate expressions for all ideas
        all_expressions = []
        for idea in ideas:
            expressions = await self._generate_expressions_for_idea(idea, prompt_template)
            all_expressions.extend(expressions)

        self.log_execution_time(start_time, f"Formula generation ({len(all_expressions)} formulas)")
        return all_expressions

    async def _generate_expressions_for_idea(self, idea: Dict, template: str) -> List[Dict]:
        """
        Generate multiple expressions for a single idea

        Args:
            idea: Idea dict
            template: Prompt template

        Returns:
            List of expression dicts
        """
        # Build the prompt
        prompt = template.replace('{HYPOTHESIS}', idea.get('hypothesis', ''))
        prompt = prompt.replace('{RATIONALE}', idea.get('rationale', ''))
        prompt = prompt.replace('{DATASETS}', ', '.join(idea.get('datasets', ['pv1'])))
        prompt = prompt.replace('{NUM_EXPRESSIONS}', str(self.expressions_per_idea))
        prompt = prompt.replace('{OPERATORS_REF}', self.operators_ref)

        for attempt in range(self.max_retries):
            try:
                response = await self._call_ollama(prompt, self.temperature)
                expressions = self._parse_expression_response(response, idea)
                if expressions:
                    return expressions
            except Exception as e:
                error_str = str(e)
                self.logger.warning(f"Expression generation attempt {attempt + 1} failed: {e}")

                # Check for API rate limit (429 error)
                if "429" in error_str or "usage limit" in error_str.lower():
                    self.logger.error("API rate limit reached. Exiting to avoid long wait times.")
                    self.logger.error("Please wait for the API limit to reset or upgrade your plan.")
                    import sys
                    sys.exit(1)

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)

        self.logger.error(f"Failed to generate expressions for idea {idea.get('idea_id')}")
        return []

    def _parse_expression_response(self, response: str, idea: Dict) -> List[Dict]:
        """Parse Ollama response into expression dicts"""
        import re
        import json

        expressions = []

        # Try JSON format first
        if '```json' in response or '{' in response:
            try:
                # Extract JSON
                response_text = response.strip()
                if '```json' in response_text:
                    response_text = response_text.split('```json')[1].split('```')[0].strip()
                elif '```' in response_text:
                    response_text = response_text.split('```')[1].split('```')[0].strip()

                data = json.loads(response_text)
                if isinstance(data, dict) and 'expressions' in data:
                    expr_list = data['expressions']
                elif isinstance(data, list):
                    expr_list = data
                else:
                    expr_list = []

                for i, expr_dict in enumerate(expr_list):
                    expression = {
                        'expression_id': f"{idea['idea_id']}_expr{i+1}",
                        'expression': expr_dict.get('expression', ''),
                        'parent_idea_id': idea['idea_id'],
                        'variant_type': expr_dict.get('variant_type', f'v{i+1}'),
                        'description': expr_dict.get('description', ''),
                        'parameters': expr_dict.get('parameters', {}),
                        'timestamp': self.get_timestamp()
                    }

                    if expression['expression']:
                        expressions.append(expression)

                return expressions

            except json.JSONDecodeError as e:
                self.logger.warning(f"JSON parsing failed: {e}, trying text format")

        # Fallback: Parse text format
        # Look for EXPRESSION markers
        expr_blocks = re.findall(r'EXPRESSION\s*\d*:?\s*(.+?)(?:\n|$)', response, re.IGNORECASE)

        for i, expr_text in enumerate(expr_blocks):
            expression = {
                'expression_id': f"{idea['idea_id']}_expr{i+1}",
                'expression': expr_text.strip(),
                'parent_idea_id': idea['idea_id'],
                'variant_type': f'v{i+1}',
                'description': '',
                'parameters': {},
                'timestamp': self.get_timestamp()
            }
            expressions.append(expression)

        return expressions

    def validate_expression(self, expression: str) -> bool:
        """
        Basic validation of WorldQuant expression syntax

        Args:
            expression: Expression string

        Returns:
            True if valid, False otherwise
        """
        # Basic checks
        if not expression or len(expression) < 5:
            return False

        # Check for balanced parentheses
        if expression.count('(') != expression.count(')'):
            self.logger.warning(f"Unbalanced parentheses in: {expression}")
            return False

        # Check for common operators
        valid_operators = [
            'ts_', 'rank', 'zscore', 'scale', 'delay', 'if',
            'abs', 'log', 'sign', 'sqrt', 'power', 'max', 'min',
            'close', 'open', 'high', 'low', 'volume', 'returns'
        ]

        has_operator = any(op in expression.lower() for op in valid_operators)
        if not has_operator:
            self.logger.warning(f"No valid operators found in: {expression}")
            return False

        return True

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

    def _get_fallback_prompt(self) -> str:
        """Fallback prompt if template not found"""
        return """You are a WorldQuant Brain alpha expression expert.

Alpha Idea:
Hypothesis: {HYPOTHESIS}
Rationale: {RATIONALE}
Datasets: {DATASETS}

{OPERATORS_REF}

Task: Convert this idea into {NUM_EXPRESSIONS} WorldQuant Brain FASTEXPR formulas.

Requirements:
1. Use valid FASTEXPR syntax
2. Avoid look-ahead bias (use delay())
3. Normalize output (use rank() or scale())
4. Keep complexity reasonable
5. Vary the implementations (different windows, normalizations)

Output as JSON:
{{
  "expressions": [
    {{
      "expression": "rank(ts_sum(close/delay(close, 1) - 1, 20))",
      "variant_type": "base",
      "description": "20-day momentum ranked",
      "parameters": {{"window": 20}}
    }}
  ]
}}

Generate expressions now:"""
