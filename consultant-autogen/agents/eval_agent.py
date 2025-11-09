"""
Eval Agent - Evaluates simulation results and makes decisions
"""

import json
import requests
from typing import Dict, List, Optional
from datetime import datetime

from .base_agent import BaseAgent


class EvalAgent(BaseAgent):
    """
    Agent responsible for evaluating simulation results and deciding:
    - hopeful: Good alpha, save to hopeful_alphas.json
    - reject: Poor alpha, save to rejected_alphas.json
    - negate: Try negating the expression
    - refine: Fix syntax errors
    """
    
    def __init__(self, ollama_url: str = "http://localhost:11434",
                 ollama_model: str = "gemma2:2b", config: Optional[Dict] = None):
        """
        Initialize Eval Agent
        
        Args:
            ollama_url: Ollama API URL (for deep analysis)
            ollama_model: Ollama model name
            config: Optional configuration dict
        """
        super().__init__('eval_agent', config)
        
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model
        
        # Decision thresholds
        self.sharpe_threshold_hopeful = self.config.get('sharpe_threshold_hopeful', 0.5)
        self.fitness_threshold_hopeful = self.config.get('fitness_threshold_hopeful', 0.6)
        self.sharpe_threshold_negate = self.config.get('sharpe_threshold_negate', -0.5)
        
        self.use_llm_analysis = self.config.get('use_llm_analysis', False)
    
    def run(self, results: List[Dict]) -> List[Dict]:
        """
        Main execution: evaluate simulation results
        
        Args:
            results: List of simulation result dicts
        
        Returns:
            List of decision dicts
        """
        self.logger.info(f"Evaluating {len(results)} simulation results...")
        start_time = datetime.now()
        
        decisions = []
        stats = {'hopeful': 0, 'reject': 0, 'negate': 0, 'refine': 0}
        
        for result in results:
            decision = self._evaluate_single(result)
            decisions.append(decision)
            
            decision_type = decision['decision']
            stats[decision_type] += 1
            
            self.logger.info(
                f"{result.get('expression_id')}: {decision_type.upper()} - {decision['reason']}"
            )
        
        self.log_execution_time(start_time, "Evaluation")
        self.logger.info(
            f"Decisions: {stats['hopeful']} hopeful, {stats['negate']} negate, "
            f"{stats['refine']} refine, {stats['reject']} reject"
        )
        
        # Save decisions
        self.save_json(decisions, 'data/eval_decisions.json')
        
        # Update hopeful and rejected alphas
        self._update_alpha_databases(decisions, results)
        
        return decisions
    
    def _evaluate_single(self, result: Dict) -> Dict:
        """
        Evaluate a single simulation result
        
        Args:
            result: Simulation result dict
        
        Returns:
            Decision dict
        """
        expr_id = result.get('expression_id')
        expression = result.get('expression')
        
        # Check for errors
        if result.get('status') == 'error':
            error_msg = result.get('error', '')
            
            # Determine if this is a fixable syntax error
            if any(keyword in error_msg.lower() for keyword in 
                   ['syntax', 'unknown variable', 'required attribute', 'unexpected']):
                return {
                    'decision_id': self.generate_id('dec', hash(expr_id) % 10000),
                    'expression_id': expr_id,
                    'decision': 'refine',
                    'reason': f'Syntax error: {error_msg[:100]}',
                    'next_action': 'Fix expression and retry',
                    'timestamp': self.get_timestamp()
                }
            else:
                return {
                    'decision_id': self.generate_id('dec', hash(expr_id) % 10000),
                    'expression_id': expr_id,
                    'decision': 'reject',
                    'reason': f'API error: {error_msg[:100]}',
                    'next_action': None,
                    'timestamp': self.get_timestamp()
                }
        
        # Extract metrics
        sharpe = result.get('sharpe', -999)
        fitness = result.get('fitness', 0)
        
        # Decision logic
        if sharpe > self.sharpe_threshold_hopeful and fitness > self.fitness_threshold_hopeful:
            decision = 'hopeful'
            reason = f'Strong performance: Sharpe={sharpe:.3f}, Fitness={fitness:.3f}'
            next_action = None
        
        elif sharpe < self.sharpe_threshold_negate:
            decision = 'negate'
            reason = f'Very negative Sharpe ({sharpe:.3f}), try negation'
            next_action = 'Negate expression and retest'
        
        else:
            decision = 'reject'
            reason = f'Insufficient performance: Sharpe={sharpe:.3f}, Fitness={fitness:.3f}'
            next_action = None
        
        # Optional: Deep analysis with LLM
        analysis = ""
        if self.use_llm_analysis and decision in ['hopeful', 'negate']:
            analysis = self._llm_deep_analysis(result)
        
        return {
            'decision_id': self.generate_id('dec', hash(expr_id) % 10000),
            'expression_id': expr_id,
            'decision': decision,
            'reason': reason,
            'next_action': next_action,
            'analysis': analysis,
            'timestamp': self.get_timestamp()
        }
    
    def _llm_deep_analysis(self, result: Dict) -> str:
        """
        Use LLM to provide deep analysis of the result
        
        Args:
            result: Simulation result
        
        Returns:
            Analysis text
        """
        prompt = f"""Analyze this alpha factor result:

Expression: {result.get('expression', 'N/A')}
Sharpe Ratio: {result.get('sharpe', 0):.3f}
Fitness: {result.get('fitness', 0):.3f}
Returns: {result.get('returns', 0):.3f}
Turnover: {result.get('turnover', 0):.3f}

Provide a brief analysis (2-3 sentences):
1. Why this alpha might be successful/unsuccessful
2. Potential improvements or concerns

Analysis:"""
        
        try:
            url = f"{self.ollama_url}/api/generate"
            payload = {
                'model': self.ollama_model,
                'prompt': prompt,
                'stream': False
            }
            
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return data.get('response', '')
        
        except Exception as e:
            self.logger.warning(f"LLM analysis failed: {e}")
        
        return ""
    
    def _update_alpha_databases(self, decisions: List[Dict], results: List[Dict]):
        """
        Update hopeful_alphas.json and rejected_alphas.json
        
        Args:
            decisions: List of decision dicts
            results: List of simulation result dicts
        """
        # Create lookup dict
        result_lookup = {r['expression_id']: r for r in results}
        
        # Load existing databases
        hopeful_alphas = self.load_json('data/hopeful_alphas.json')
        rejected_alphas = self.load_json('data/rejected_alphas.json')
        
        # Update based on decisions
        for decision in decisions:
            expr_id = decision['expression_id']
            result = result_lookup.get(expr_id)
            
            if not result:
                continue
            
            if decision['decision'] == 'hopeful':
                # Add to hopeful alphas
                alpha_entry = {
                    'expression': result.get('expression'),
                    'expression_id': expr_id,
                    'sharpe': result.get('sharpe'),
                    'fitness': result.get('fitness'),
                    'returns': result.get('returns'),
                    'turnover': result.get('turnover'),
                    'timestamp': self.get_timestamp(),
                    'decision_reason': decision.get('reason')
                }
                hopeful_alphas.append(alpha_entry)
                self.logger.info(f"Added {expr_id} to hopeful_alphas")
            
            elif decision['decision'] == 'reject':
                # Add to rejected alphas
                alpha_entry = {
                    'expression': result.get('expression'),
                    'expression_id': expr_id,
                    'sharpe': result.get('sharpe', -999),
                    'fitness': result.get('fitness', 0),
                    'timestamp': self.get_timestamp(),
                    'rejection_reason': decision.get('reason')
                }
                rejected_alphas.append(alpha_entry)
        
        # Save updated databases
        self.save_json(hopeful_alphas, 'data/hopeful_alphas.json')
        self.save_json(rejected_alphas, 'data/rejected_alphas.json')
        
        self.logger.info(
            f"Updated databases: {len(hopeful_alphas)} hopeful, {len(rejected_alphas)} rejected"
        )


