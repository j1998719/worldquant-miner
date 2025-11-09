"""
Factor Agent - Converts alpha ideas into valid WorldQuant expressions
"""

import requests
import json
import random
import re
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

from .base_agent import BaseAgent


class FactorAgent(BaseAgent):
    """
    Agent responsible for converting alpha ideas/hypotheses into
    valid WorldQuant Brain alpha expressions
    """
    
    def __init__(self, ollama_url: str = "http://localhost:11434",
                 ollama_model: str = "gemma2:2b", config: Optional[Dict] = None):
        """
        Initialize Factor Agent
        
        Args:
            ollama_url: Ollama API URL
            ollama_model: Ollama model name
            config: Optional configuration dict
        """
        super().__init__('factor_agent', config)
        
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model
        self.temperature = self.config.get('temperature', 0.7)
        self.max_retries = self.config.get('max_retries', 3)
        self.expressions_per_idea = self.config.get('expressions_per_idea', 2)
        
        # Load available components
        self.available_fields = self._load_available_fields()
        self.available_operators = self._load_available_operators()
    
    def run(self, ideas: List[Dict]) -> List[Dict]:
        """
        Main execution: convert ideas to expressions
        
        Args:
            ideas: List of idea dicts from IdeaAgent
        
        Returns:
            List of expression dicts
        """
        self.logger.info(f"Building expressions for {len(ideas)} ideas...")
        start_time = datetime.now()
        
        expressions = []
        expr_index = 1
        
        for idea in ideas:
            # Generate multiple expressions per idea
            for i in range(self.expressions_per_idea):
                expr = self._build_single_expression(idea, expr_index)
                if expr:
                    expressions.append(expr)
                    self.logger.info(f"Expr {expr_index}: {expr['expression'][:80]}...")
                    expr_index += 1
        
        self.log_execution_time(start_time, f"Built {len(expressions)} expressions")
        
        # Save expressions
        self.save_json(expressions, 'data/alpha_expressions.json')
        
        return expressions
    
    def _build_single_expression(self, idea: Dict, index: int) -> Optional[Dict]:
        """
        Build a single alpha expression from an idea
        
        Args:
            idea: Idea dict
            index: Expression index
        
        Returns:
            Expression dict or None if failed
        """
        # Build prompt with idea and available components
        prompt = self._build_prompt(idea)
        
        # Call LLM
        response_text = self._call_ollama(prompt)
        
        if not response_text:
            self.logger.warning(f"Failed to generate expression for idea {idea['idea_id']}")
            return None
        
        # Extract expression from response
        expression = self._extract_expression(response_text)
        
        if not expression:
            self.logger.warning(f"Could not extract valid expression from LLM response")
            return None
        
        # Fix common syntax issues
        expression = self._fix_expression_syntax(expression)
        
        return {
            'expression_id': self.generate_id('expr', index),
            'idea_id': idea['idea_id'],
            'expression': expression,
            'description': idea.get('hypothesis', ''),
            'timestamp': self.get_timestamp()
        }
    
    def _build_prompt(self, idea: Dict) -> str:
        """
        Build prompt for LLM
        
        Args:
            idea: Idea dict
        
        Returns:
            Prompt string
        """
        # Load prompt template
        template = self.load_prompt('factor_construction.txt')
        
        if not template:
            template = self._get_default_prompt()
        
        # Sample available fields and operators
        sample_fields = random.sample(self.available_fields, min(10, len(self.available_fields)))
        sample_operators = random.sample(self.available_operators, min(15, len(self.available_operators)))
        
        fields_str = "\n".join([f"- {f}" for f in sample_fields])
        operators_str = "\n".join([f"- {op}" for op in sample_operators])
        
        # Fill in template
        prompt = template.replace('{HYPOTHESIS}', idea.get('hypothesis', ''))
        prompt = prompt.replace('{RATIONALE}', idea.get('rationale', ''))
        prompt = prompt.replace('{AVAILABLE_FIELDS}', fields_str)
        prompt = prompt.replace('{AVAILABLE_OPERATORS}', operators_str)
        
        return prompt
    
    def _get_default_prompt(self) -> str:
        """Get default prompt if template file is not found"""
        return """You are a quantitative analyst. Convert this trading hypothesis into a WorldQuant alpha expression.

HYPOTHESIS: {HYPOTHESIS}
RATIONALE: {RATIONALE}

Available data fields (examples):
{AVAILABLE_FIELDS}

Available operators (examples):
{AVAILABLE_OPERATORS}

Rules:
1. Use ONLY fields and operators from the lists above
2. Follow WorldQuant syntax: operator(field, lookback) or operator(expr1, expr2)
3. Common wrappers: rank(), ts_rank(), ts_std_dev(), ts_delta(), ts_corr()
4. Keep complexity low (2-3 layers maximum)
5. Output ONLY the expression, no explanation

Generate the alpha expression now:
EXPRESSION:"""
    
    def _call_ollama(self, prompt: str) -> Optional[str]:
        """
        Call Ollama API
        
        Args:
            prompt: Input prompt
        
        Returns:
            Generated text or None if failed
        """
        url = f"{self.ollama_url}/api/generate"
        
        payload = {
            'model': self.ollama_model,
            'prompt': prompt,
            'stream': False,
            'options': {
                'temperature': self.temperature
            }
        }
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(url, json=payload, timeout=60)
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get('response', '')
                else:
                    self.logger.warning(f"Ollama call failed (attempt {attempt+1}): {response.status_code}")
            
            except Exception as e:
                self.logger.error(f"Ollama exception (attempt {attempt+1}): {e}")
            
            if attempt < self.max_retries - 1:
                import time
                time.sleep(2)
        
        return None
    
    def _extract_expression(self, response_text: str) -> Optional[str]:
        """
        Extract alpha expression from LLM response
        
        Args:
            response_text: Raw LLM response
        
        Returns:
            Extracted expression or None
        """
        # Look for EXPRESSION: prefix
        if 'EXPRESSION:' in response_text:
            parts = response_text.split('EXPRESSION:')
            if len(parts) > 1:
                expr = parts[1].strip().split('\n')[0].strip()
                return expr
        
        # Otherwise, try to find expression-like patterns
        lines = response_text.split('\n')
        for line in lines:
            line = line.strip()
            # Look for lines with operators and parentheses
            if '(' in line and ')' in line and any(op in line for op in ['rank', 'ts_', 'group_']):
                # Remove markdown code blocks
                line = line.replace('```', '').strip()
                return line
        
        # If all else fails, return the first non-empty line
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                return line
        
        return None
    
    def _fix_expression_syntax(self, expression: str) -> str:
        """
        Fix common syntax issues in expressions
        
        Args:
            expression: Raw expression
        
        Returns:
            Fixed expression
        """
        # Remove quotes
        expression = expression.replace('"', '').replace("'", '')
        
        # Remove markdown code blocks
        expression = expression.replace('```', '').strip()
        
        # Remove "python" or "fastexpr" tags
        expression = re.sub(r'^(python|fastexpr)\s+', '', expression, flags=re.IGNORECASE)
        
        # Strip whitespace
        expression = expression.strip()
        
        # Remove trailing punctuation
        expression = expression.rstrip(';.,')
        
        return expression
    
    def _load_available_fields(self) -> List[str]:
        """
        Load available data fields
        
        Returns:
            List of field names
        """
        fields = []
        
        # Load from available_components if exists
        fields_dir = Path('available_components_USA/fields')
        if fields_dir.exists():
            for file in fields_dir.glob('*.txt'):
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Extract field IDs (simple pattern matching)
                        matches = re.findall(r'\b(fn_\w+|fnd\d+_\w+|pv1_\w+)\b', content)
                        fields.extend(matches)
                except Exception as e:
                    self.logger.warning(f"Failed to load fields from {file}: {e}")
        
        # Fallback: common fields
        if not fields:
            fields = ['close', 'open', 'high', 'low', 'volume', 'vwap', 'adv20', 
                     'cap', 'returns', 'sharesout']
        
        # Remove duplicates
        fields = list(set(fields))
        
        self.logger.info(f"Loaded {len(fields)} available fields")
        return fields
    
    def _load_available_operators(self) -> List[str]:
        """
        Load available operators
        
        Returns:
            List of operator names
        """
        operators = []
        
        # Load from available_components if exists
        operators_file = Path('available_components_USA/operators.txt')
        if operators_file.exists():
            try:
                with open(operators_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Extract operator names
                    matches = re.findall(r'^\s*\d+\.\s+(\w+)', content, re.MULTILINE)
                    operators.extend(matches)
            except Exception as e:
                self.logger.warning(f"Failed to load operators: {e}")
        
        # Fallback: common operators
        if not operators:
            operators = [
                'rank', 'ts_rank', 'ts_std_dev', 'ts_delta', 'ts_corr',
                'ts_sum', 'ts_mean', 'ts_max', 'ts_min', 'ts_decay_linear',
                'group_rank', 'group_mean', 'group_neutralize',
                'winsorize', 'ts_backfill', 'sign', 'abs', 'log'
            ]
        
        # Remove duplicates
        operators = list(set(operators))
        
        self.logger.info(f"Loaded {len(operators)} available operators")
        return operators

