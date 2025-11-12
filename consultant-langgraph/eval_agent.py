"""
Evaluation Agent - Analyze simulation results and make decisions
Decides whether alphas are hopeful, should be rejected, or need refinement
"""

from typing import List, Dict
from datetime import datetime

from base_agent import BaseAgent


class EvalAgent(BaseAgent):
    """
    Agent for evaluating simulation results and making refinement decisions
    Uses rule-based logic (can optionally use LLM for analysis)
    """

    def __init__(self, config: Dict):
        """
        Initialize evaluation agent

        Args:
            config: Configuration dict
        """
        super().__init__('eval_agent', config)

        # Thresholds from config
        eval_config = config.get('eval_agent', {})
        self.sharpe_threshold_hopeful = eval_config.get('sharpe_threshold_hopeful', 1.5)
        self.fitness_threshold_hopeful = eval_config.get('fitness_threshold_hopeful', 0.6)
        self.sharpe_threshold_refine = eval_config.get('sharpe_threshold_refine', 0.5)
        self.sharpe_threshold_negate = eval_config.get('sharpe_threshold_negate', -0.5)
        self.use_llm_analysis = eval_config.get('use_llm_analysis', False)

    async def run(self, simulation_results: List[Dict]) -> Dict:
        """
        Evaluate simulation results and categorize alphas

        Args:
            simulation_results: List of simulation result dicts

        Returns:
            Dict with 'hopeful', 'rejected', 'refine' lists and decisions
        """
        start_time = datetime.now()
        self.logger.info(f"Evaluating {len(simulation_results)} simulation results")

        hopeful_alphas = []
        rejected_alphas = []
        refinement_candidates = []
        decisions = []

        for result in simulation_results:
            decision = self._evaluate_single_result(result)
            decisions.append(decision)

            # Categorize based on decision
            if decision['decision'] == 'hopeful':
                hopeful_alphas.append(self._create_hopeful_alpha(result, decision))
            elif decision['decision'] in ['refine_negate', 'refine_adjust']:
                refinement_candidates.append(self._create_refinement_candidate(result, decision))
            else:  # reject
                rejected_alphas.append(self._create_rejected_alpha(result, decision))

        # Log summary
        self.logger.info(
            f"Evaluation complete: {len(hopeful_alphas)} hopeful, "
            f"{len(refinement_candidates)} refine, {len(rejected_alphas)} rejected"
        )

        self.log_execution_time(start_time, "Evaluation")

        return {
            'hopeful_alphas': hopeful_alphas,
            'rejected_alphas': rejected_alphas,
            'refinement_candidates': refinement_candidates,
            'decisions': decisions
        }

    def _evaluate_single_result(self, result: Dict) -> Dict:
        """
        Evaluate a single simulation result

        Args:
            result: Simulation result dict

        Returns:
            Decision dict
        """
        expression_id = result.get('expression_id', 'unknown')
        sharpe = result.get('sharpe', -999)
        fitness = result.get('fitness', 0)
        status = result.get('status', 'error')

        # Handle errors
        if status == 'error':
            return {
                'expression_id': expression_id,
                'decision': 'reject',
                'reason': f"Simulation error: {result.get('error', 'Unknown error')}",
                'sharpe': sharpe,
                'fitness': fitness,
                'suggested_modifications': [],
                'timestamp': self.get_timestamp()
            }

        # Decision logic
        decision, reason, modifications = self._apply_decision_rules(sharpe, fitness, result)

        return {
            'expression_id': expression_id,
            'decision': decision,
            'reason': reason,
            'sharpe': sharpe,
            'fitness': fitness,
            'suggested_modifications': modifications,
            'timestamp': self.get_timestamp()
        }

    def _apply_decision_rules(self, sharpe: float, fitness: float, result: Dict) -> tuple:
        """
        Apply decision rules based on performance metrics

        Args:
            sharpe: Sharpe ratio
            fitness: Fitness score
            result: Full result dict

        Returns:
            Tuple of (decision, reason, modifications)
        """
        turnover = result.get('turnover', 0)
        returns = result.get('returns', 0)

        # Excellent alpha (hopeful)
        if sharpe >= self.sharpe_threshold_hopeful and fitness >= self.fitness_threshold_hopeful:
            return (
                'hopeful',
                f"Excellent performance: Sharpe={sharpe:.2f}, Fitness={fitness:.2f}",
                []
            )

        # Good alpha with reasonable turnover (hopeful)
        if sharpe >= self.sharpe_threshold_hopeful and turnover < 150:
            return (
                'hopeful',
                f"Good Sharpe with acceptable turnover: Sharpe={sharpe:.2f}, Turnover={turnover:.0f}",
                []
            )

        # Negative sharpe - try negating the signal
        if sharpe < self.sharpe_threshold_negate:
            return (
                'refine_negate',
                f"Negative Sharpe={sharpe:.2f}, try negating signal",
                ['negate_signal']
            )

        # Mediocre performance - try refinements
        if self.sharpe_threshold_refine <= sharpe < self.sharpe_threshold_hopeful:
            modifications = []

            # High turnover - suggest longer windows
            if turnover > 150:
                modifications.append('increase_windows')

            # Low fitness - suggest normalization
            if fitness < 0.5:
                modifications.append('add_normalization')

            # Low returns - suggest different neutralization
            if returns < 0.05:
                modifications.append('try_different_neutralization')

            if modifications:
                return (
                    'refine_adjust',
                    f"Moderate performance (Sharpe={sharpe:.2f}), refineable",
                    modifications
                )

        # Poor performance - reject
        return (
            'reject',
            f"Poor performance: Sharpe={sharpe:.2f}, Fitness={fitness:.2f}",
            []
        )

    def _create_hopeful_alpha(self, result: Dict, decision: Dict) -> Dict:
        """Create hopeful alpha record"""
        return {
            'expression_id': result.get('expression_id'),
            'expression': result.get('expression'),
            'alpha_id': result.get('alpha_id'),
            'sharpe': result.get('sharpe'),
            'fitness': result.get('fitness'),
            'returns': result.get('returns'),
            'turnover': result.get('turnover'),
            'drawdown': result.get('drawdown'),
            'reason': decision['reason'],
            'timestamp': self.get_timestamp(),
            'status': 'hopeful'
        }

    def _create_refinement_candidate(self, result: Dict, decision: Dict) -> Dict:
        """Create refinement candidate record"""
        return {
            'expression_id': result.get('expression_id'),
            'expression': result.get('expression'),
            'parent_idea_id': result.get('parent_idea_id'),
            'sharpe': result.get('sharpe'),
            'fitness': result.get('fitness'),
            'decision_type': decision['decision'],
            'modifications': decision['suggested_modifications'],
            'reason': decision['reason'],
            'timestamp': self.get_timestamp()
        }

    def _create_rejected_alpha(self, result: Dict, decision: Dict) -> Dict:
        """Create rejected alpha record"""
        return {
            'expression_id': result.get('expression_id'),
            'expression': result.get('expression'),
            'sharpe': result.get('sharpe'),
            'fitness': result.get('fitness'),
            'reason': decision['reason'],
            'error': result.get('error'),
            'timestamp': self.get_timestamp(),
            'status': 'rejected'
        }

    def get_summary_statistics(self, decisions: List[Dict]) -> Dict:
        """
        Get summary statistics from decisions

        Args:
            decisions: List of decision dicts

        Returns:
            Summary statistics dict
        """
        total = len(decisions)
        if total == 0:
            return {}

        hopeful = sum(1 for d in decisions if d['decision'] == 'hopeful')
        refine = sum(1 for d in decisions if d['decision'].startswith('refine'))
        rejected = sum(1 for d in decisions if d['decision'] == 'reject')

        sharpes = [d['sharpe'] for d in decisions if d['sharpe'] != -999]
        avg_sharpe = sum(sharpes) / len(sharpes) if sharpes else 0

        return {
            'total_evaluated': total,
            'hopeful_count': hopeful,
            'refine_count': refine,
            'rejected_count': rejected,
            'hopeful_rate': hopeful / total if total > 0 else 0,
            'average_sharpe': avg_sharpe,
            'best_sharpe': max(sharpes) if sharpes else 0,
            'worst_sharpe': min(sharpes) if sharpes else 0
        }
