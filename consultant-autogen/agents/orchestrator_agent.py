"""
Orchestrator Agent - Coordinates the entire multi-agent workflow
"""

import json
import time
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

from .base_agent import BaseAgent
from .idea_agent import IdeaAgent
from .factor_agent import FactorAgent
from .simulation_agent import SimulationAgent
from .eval_agent import EvalAgent

from utils.logging_config import CycleLogger
from utils.deduplication import ExpressionHistory


class OrchestratorAgent(BaseAgent):
    """
    Main orchestrator that coordinates all agents in the alpha mining pipeline
    """
    
    def __init__(self, credentials_path: str, config: Optional[Dict] = None):
        """
        Initialize Orchestrator Agent
        
        Args:
            credentials_path: Path to WorldQuant credentials
            config: Configuration dict
        """
        super().__init__('orchestrator', config)
        
        self.credentials_path = credentials_path
        
        # Initialize all agents
        ollama_url = self.config.get('ollama_url', 'http://localhost:11434')
        ollama_model = self.config.get('ollama_model', 'gemma2:2b')
        
        self.idea_agent = IdeaAgent(ollama_url, ollama_model, self.config.get('idea_agent', {}))
        self.factor_agent = FactorAgent(ollama_url, ollama_model, self.config.get('factor_agent', {}))
        self.simulation_agent = SimulationAgent(credentials_path, self.config.get('simulation_agent', {}))
        self.eval_agent = EvalAgent(ollama_url, ollama_model, self.config.get('eval_agent', {}))
        
        # Expression history for deduplication
        self.expression_history = ExpressionHistory()
        
        # Cycle settings
        self.ideas_per_cycle = self.config.get('ideas_per_cycle', 10)
        self.enable_deduplication = self.config.get('enable_deduplication', True)
        self.enable_refinement = self.config.get('enable_refinement', True)
        
        self.cycle_count = 0
    
    def run_single_cycle(self) -> Dict:
        """
        Run a single mining cycle
        
        Returns:
            Cycle summary dict
        """
        self.cycle_count += 1
        cycle_id = self.cycle_count
        
        self.logger.info("="*60)
        self.logger.info(f"STARTING CYCLE {cycle_id}")
        self.logger.info("="*60)
        
        # Create cycle logger
        cycle_logger = CycleLogger(cycle_id)
        cycle_logger.section(f"CYCLE {cycle_id} START")
        
        start_time = datetime.now()
        
        try:
            # Step 1: Generate Ideas
            self.logger.info(f"[Step 1/5] Generating {self.ideas_per_cycle} ideas...")
            step_start = datetime.now()
            ideas = self.idea_agent.run(count=self.ideas_per_cycle)
            cycle_logger.info(f"IdeaAgent: Generated {len(ideas)} ideas")
            for idea in ideas[:3]:  # Log first 3
                cycle_logger.info(f"  - {idea['idea_id']}: {idea['hypothesis'][:80]}...")
            self.logger.info(f"  Completed in {(datetime.now() - step_start).total_seconds():.1f}s")
            
            if not ideas:
                self.logger.warning("No ideas generated, skipping cycle")
                return self._create_cycle_summary(cycle_id, start_time, 0, 0, 0, "No ideas generated")
            
            # Step 2: Build Expressions
            self.logger.info(f"[Step 2/5] Building expressions...")
            step_start = datetime.now()
            expressions = self.factor_agent.run(ideas)
            cycle_logger.info(f"FactorAgent: Built {len(expressions)} expressions")
            for expr in expressions[:3]:  # Log first 3
                cycle_logger.info(f"  - {expr['expression_id']}: {expr['expression'][:80]}...")
            self.logger.info(f"  Completed in {(datetime.now() - step_start).total_seconds():.1f}s")
            
            if not expressions:
                self.logger.warning("No expressions built, skipping cycle")
                return self._create_cycle_summary(cycle_id, start_time, 0, 0, 0, "No expressions built")
            
            # Step 2.5: Deduplication (optional)
            if self.enable_deduplication:
                self.logger.info(f"[Step 2.5/5] Deduplicating expressions...")
                expressions = self._deduplicate_expressions(expressions)
                cycle_logger.info(f"After deduplication: {len(expressions)} unique expressions")
                self.logger.info(f"  {len(expressions)} unique expressions remain")
                
                if not expressions:
                    self.logger.warning("All expressions were duplicates, skipping cycle")
                    return self._create_cycle_summary(cycle_id, start_time, 0, 0, 0, "All duplicates")
            
            # Step 3: Simulate
            self.logger.info(f"[Step 3/5] Simulating {len(expressions)} expressions...")
            step_start = datetime.now()
            results = self.simulation_agent.run(expressions)
            cycle_logger.info(f"SimulationAgent: Completed {len(results)} simulations")
            for result in results[:3]:  # Log first 3
                cycle_logger.info(
                    f"  - {result['expression_id']}: "
                    f"Sharpe={result.get('sharpe', -999):.3f}, "
                    f"Fitness={result.get('fitness', 0):.3f}, "
                    f"Status={result.get('status', 'unknown')}"
                )
            self.logger.info(f"  Completed in {(datetime.now() - step_start).total_seconds():.1f}s")
            
            # Update expression history
            for result in results:
                self.expression_history.add(result.get('expression', ''), result)
            
            # Step 4: Evaluate
            self.logger.info(f"[Step 4/5] Evaluating results...")
            step_start = datetime.now()
            decisions = self.eval_agent.run(results)
            cycle_logger.info(f"EvalAgent: Made {len(decisions)} decisions")
            
            # Count decisions
            decision_stats = self._count_decisions(decisions)
            cycle_logger.info(
                f"  Hopeful: {decision_stats['hopeful']}, "
                f"Negate: {decision_stats['negate']}, "
                f"Refine: {decision_stats['refine']}, "
                f"Reject: {decision_stats['reject']}"
            )
            self.logger.info(f"  Completed in {(datetime.now() - step_start).total_seconds():.1f}s")
            
            # Step 5: Handle Refinements (optional)
            refined_count = 0
            if self.enable_refinement and decision_stats['negate'] > 0:
                self.logger.info(f"[Step 5/5] Processing {decision_stats['negate']} negations...")
                refined_count = self._process_negations(decisions, results)
                cycle_logger.info(f"Processed {refined_count} negations")
            
            # Create cycle summary
            summary = self._create_cycle_summary(
                cycle_id, start_time, 
                len(expressions), 
                decision_stats['hopeful'], 
                refined_count,
                "Completed successfully"
            )
            
            cycle_logger.section(f"CYCLE {cycle_id} END")
            cycle_logger.info(f"Total expressions tested: {len(expressions)}")
            cycle_logger.info(f"Hopeful: {decision_stats['hopeful']} ({decision_stats['hopeful']/len(expressions)*100:.1f}%)")
            cycle_logger.info(f"Rejected: {decision_stats['reject']} ({decision_stats['reject']/len(expressions)*100:.1f}%)")
            cycle_logger.info(f"Duration: {(datetime.now() - start_time).total_seconds():.1f}s")
            
            cycle_logger.close()
            
            self.logger.info("="*60)
            self.logger.info(f"CYCLE {cycle_id} COMPLETED")
            self.logger.info(f"Success Rate: {decision_stats['hopeful']}/{len(expressions)} = {decision_stats['hopeful']/len(expressions)*100:.1f}%")
            self.logger.info("="*60)
            
            return summary
        
        except Exception as e:
            self.logger.error(f"Cycle {cycle_id} failed: {e}")
            cycle_logger.error(f"CYCLE FAILED: {e}")
            cycle_logger.close()
            
            return self._create_cycle_summary(cycle_id, start_time, 0, 0, 0, f"Error: {str(e)}")
    
    def run_continuous(self, max_cycles: Optional[int] = None, delay_between_cycles: int = 10):
        """
        Run continuous mining cycles
        
        Args:
            max_cycles: Maximum number of cycles (None for infinite)
            delay_between_cycles: Delay between cycles in seconds
        """
        self.logger.info(f"Starting continuous mining (max_cycles={max_cycles})")
        
        cycle = 0
        while max_cycles is None or cycle < max_cycles:
            try:
                summary = self.run_single_cycle()
                
                # Save cycle summary
                self._save_cycle_summary(summary)
                
                cycle += 1
                
                if max_cycles is None or cycle < max_cycles:
                    self.logger.info(f"Waiting {delay_between_cycles}s before next cycle...")
                    time.sleep(delay_between_cycles)
            
            except KeyboardInterrupt:
                self.logger.info("Interrupted by user, stopping...")
                break
            
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                time.sleep(delay_between_cycles)
        
        self.logger.info(f"Completed {cycle} cycles")
        self._print_final_statistics()
    
    def _deduplicate_expressions(self, expressions: List[Dict]) -> List[Dict]:
        """
        Remove duplicate expressions
        
        Args:
            expressions: List of expression dicts
        
        Returns:
            Filtered list of unique expressions
        """
        unique = []
        skipped = 0
        
        for expr in expressions:
            expression = expr.get('expression', '')
            
            if not self.expression_history.exists(expression):
                unique.append(expr)
            else:
                history = self.expression_history.get(expression)
                self.logger.debug(
                    f"Skipped duplicate: {expression[:50]}... "
                    f"(first tested: {history.get('first_tested')}, status: {history.get('status')})"
                )
                skipped += 1
        
        self.logger.info(f"Deduplication: Skipped {skipped} duplicates, {len(unique)} unique")
        return unique
    
    def _process_negations(self, decisions: List[Dict], results: List[Dict]) -> int:
        """
        Process expressions marked for negation
        
        Args:
            decisions: List of decision dicts
            results: List of result dicts
        
        Returns:
            Number of negations processed
        """
        result_lookup = {r['expression_id']: r for r in results}
        
        negations = [d for d in decisions if d['decision'] == 'negate']
        
        if not negations:
            return 0
        
        self.logger.info(f"Processing {len(negations)} negations...")
        
        # Create negated expressions
        negated_expressions = []
        for decision in negations:
            expr_id = decision['expression_id']
            result = result_lookup.get(expr_id)
            
            if result:
                original_expr = result.get('expression', '')
                negated_expr = f"-1 * ({original_expr})"
                
                negated_expressions.append({
                    'expression_id': f"{expr_id}_neg",
                    'expression': negated_expr,
                    'description': f"Negated version of {expr_id}"
                })
        
        # Simulate negated expressions
        if negated_expressions:
            negated_results = self.simulation_agent.run(negated_expressions)
            
            # Evaluate negated results
            negated_decisions = self.eval_agent.run(negated_results)
            
            # Update history
            for result in negated_results:
                self.expression_history.add(result.get('expression', ''), result)
            
            hopeful_count = sum(1 for d in negated_decisions if d['decision'] == 'hopeful')
            self.logger.info(f"Negations: {hopeful_count}/{len(negated_expressions)} became hopeful")
        
        return len(negated_expressions)
    
    def _count_decisions(self, decisions: List[Dict]) -> Dict:
        """Count decisions by type"""
        stats = {'hopeful': 0, 'reject': 0, 'negate': 0, 'refine': 0}
        for decision in decisions:
            decision_type = decision.get('decision', 'reject')
            if decision_type in stats:
                stats[decision_type] += 1
        return stats
    
    def _create_cycle_summary(self, cycle_id: int, start_time: datetime,
                              total_tested: int, hopeful_count: int, 
                              refined_count: int, status: str) -> Dict:
        """Create cycle summary dict"""
        duration = (datetime.now() - start_time).total_seconds()
        success_rate = hopeful_count / total_tested if total_tested > 0 else 0
        
        return {
            'cycle_id': cycle_id,
            'timestamp': start_time.isoformat(),
            'duration_seconds': duration,
            'total_tested': total_tested,
            'hopeful_count': hopeful_count,
            'refined_count': refined_count,
            'success_rate': success_rate,
            'status': status
        }
    
    def _save_cycle_summary(self, summary: Dict):
        """Save cycle summary to file"""
        summaries = self.load_json('data/cycle_summary.json')
        if not isinstance(summaries, list):
            summaries = []
        summaries.append(summary)
        self.save_json(summaries, 'data/cycle_summary.json')
    
    def _print_final_statistics(self):
        """Print final statistics"""
        self.logger.info("\n" + "="*60)
        self.logger.info("FINAL STATISTICS")
        self.logger.info("="*60)
        
        # Expression history stats
        hist_stats = self.expression_history.get_stats()
        self.logger.info(f"Total expressions tested: {hist_stats['total']}")
        self.logger.info(f"  Hopeful: {hist_stats['hopeful']}")
        self.logger.info(f"  Rejected: {hist_stats['rejected']}")
        self.logger.info(f"  Errors: {hist_stats['error']}")
        
        # Cycle summaries
        summaries = self.load_json('data/cycle_summary.json')
        if summaries:
            avg_success_rate = sum(s.get('success_rate', 0) for s in summaries) / len(summaries)
            self.logger.info(f"\nCycles completed: {len(summaries)}")
            self.logger.info(f"Average success rate: {avg_success_rate*100:.1f}%")
        
        self.logger.info("="*60 + "\n")


