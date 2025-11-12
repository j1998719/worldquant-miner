"""
Alpha Discovery Workflow - LangGraph StateGraph Implementation
Orchestrates the complete alpha discovery pipeline from research to production
"""

import asyncio
from typing import Dict
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from graph_state import AlphaWorkflowState, create_initial_state, update_statistics, get_state_summary
from paper_research_agent import PaperResearchAgent
from idea_agent import IdeaAgent
from factor_agent import FactorAgent
from simulation_agent import SimulationAgent
from eval_agent import EvalAgent
from refinement_agent import RefinementAgent
from utils.logging_config import get_cycle_logger
from utils.deduplication import ExpressionHistory


class AlphaDiscoveryWorkflow:
    """
    Complete LangGraph workflow for alpha discovery
    Integrates all agents and manages state transitions
    """

    def __init__(self, config: Dict):
        """
        Initialize workflow with all agents

        Args:
            config: Configuration dictionary
        """
        self.config = config

        # Initialize all agents
        self.paper_research_agent = PaperResearchAgent(config)
        self.idea_agent = IdeaAgent(config)
        self.factor_agent = FactorAgent(config)
        self.simulation_agent = SimulationAgent(
            credentials_path=config.get('credentials_path', 'config/credentials.json'),
            config=config
        )
        self.eval_agent = EvalAgent(config)
        self.refinement_agent = RefinementAgent(config)

        # Deduplication system
        self.expression_history = ExpressionHistory()

        # Build the workflow graph
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """
        Build the LangGraph StateGraph

        Returns:
            Compiled StateGraph
        """
        # Create graph
        workflow = StateGraph(AlphaWorkflowState)

        # Add nodes
        workflow.add_node("initialize", self._initialize_node)
        workflow.add_node("research_papers", self._research_papers_node)
        workflow.add_node("generate_ideas", self._generate_ideas_node)
        workflow.add_node("expand_ideas", self._expand_ideas_node)
        workflow.add_node("generate_formulas", self._generate_formulas_node)
        workflow.add_node("deduplicate", self._deduplicate_node)
        workflow.add_node("simulate", self._simulate_node)
        workflow.add_node("evaluate", self._evaluate_node)
        workflow.add_node("decide_next", self._decide_next_node)
        workflow.add_node("refine", self._refine_node)
        workflow.add_node("finalize", self._finalize_node)

        # Define edges
        workflow.set_entry_point("initialize")
        workflow.add_edge("initialize", "research_papers")
        workflow.add_edge("research_papers", "generate_ideas")
        workflow.add_edge("generate_ideas", "expand_ideas")
        workflow.add_edge("expand_ideas", "generate_formulas")
        workflow.add_edge("generate_formulas", "deduplicate")
        workflow.add_edge("deduplicate", "simulate")
        workflow.add_edge("simulate", "evaluate")
        workflow.add_edge("evaluate", "decide_next")

        # Conditional routing from decide_next
        workflow.add_conditional_edges(
            "decide_next",
            self._route_decision,
            {
                "refine": "refine",
                "continue": "research_papers",
                "end": "finalize"
            }
        )

        workflow.add_edge("refine", "simulate")  # Refined expressions go back to simulation
        workflow.add_edge("finalize", END)

        # Compile with memory
        memory = MemorySaver()
        return workflow.compile(checkpointer=memory)

    # ========================================================================
    # Node Implementations
    # ========================================================================

    async def _initialize_node(self, state: AlphaWorkflowState) -> AlphaWorkflowState:
        """Initialize the workflow"""
        cycle_logger = get_cycle_logger(state['cycle_id'])
        cycle_logger.log_phase("Initialization", "START")

        cycle_logger.info(f"Research topic: {state['research_topic']}")
        cycle_logger.info(f"Keywords: {state.get('search_keywords', [])}")
        cycle_logger.info(f"Max iterations: {state['max_iterations']}")
        cycle_logger.info(f"Ideas per cycle: {state['ideas_per_cycle']}")

        state['current_phase'] = 'research'
        state['iteration_count'] = 0
        state['refinement_iteration'] = 0

        cycle_logger.log_phase("Initialization", "COMPLETE")
        return state

    async def _research_papers_node(self, state: AlphaWorkflowState) -> AlphaWorkflowState:
        """Research papers from academic sources"""
        cycle_logger = get_cycle_logger(state['cycle_id'])
        cycle_logger.log_phase("Paper Research", "START")

        result = await self.paper_research_agent.run(
            topic=state['research_topic'],
            keywords=state.get('search_keywords', [])
        )

        state['papers_found'] = result['papers']
        state['ideas_extracted'] = result['ideas']
        state['current_phase'] = 'ideas'

        cycle_logger.info(f"Found {len(result['papers'])} papers")
        cycle_logger.info(f"Extracted {len(result['ideas'])} ideas from papers")
        cycle_logger.log_phase("Paper Research", "COMPLETE")

        return state

    async def _generate_ideas_node(self, state: AlphaWorkflowState) -> AlphaWorkflowState:
        """Generate additional alpha ideas using LLM"""
        cycle_logger = get_cycle_logger(state['cycle_id'])
        cycle_logger.log_phase("Idea Generation", "START")

        # Build context from historical alphas
        context = {
            'hopeful_alphas': state.get('hopeful_alphas', [])[:5],
            'rejected_alphas': state.get('rejected_alphas', [])[:5]
        }

        # Generate new ideas
        num_to_generate = max(0, state['ideas_per_cycle'] - len(state.get('ideas_extracted', [])))
        if num_to_generate > 0:
            generated_ideas = await self.idea_agent.run(num_to_generate, context)
            state['ideas_generated'] = generated_ideas
        else:
            state['ideas_generated'] = []

        cycle_logger.info(f"Generated {len(state['ideas_generated'])} new ideas")
        cycle_logger.log_phase("Idea Generation", "COMPLETE")

        return state

    async def _expand_ideas_node(self, state: AlphaWorkflowState) -> AlphaWorkflowState:
        """Expand ideas into variants"""
        cycle_logger = get_cycle_logger(state['cycle_id'])
        cycle_logger.log_phase("Idea Expansion", "START")

        # Combine extracted and generated ideas
        all_base_ideas = state.get('ideas_extracted', []) + state.get('ideas_generated', [])

        # Expand each idea into variants
        variants_per_idea = 3
        expanded_ideas = await self.idea_agent.expand_ideas(all_base_ideas, variants_per_idea)

        state['ideas_expanded'] = expanded_ideas
        state['all_ideas'] = all_base_ideas + expanded_ideas

        cycle_logger.info(f"Expanded {len(all_base_ideas)} ideas into {len(expanded_ideas)} variants")
        cycle_logger.info(f"Total ideas: {len(state['all_ideas'])}")
        cycle_logger.log_phase("Idea Expansion", "COMPLETE")

        return state

    async def _generate_formulas_node(self, state: AlphaWorkflowState) -> AlphaWorkflowState:
        """Generate WorldQuant Brain expressions"""
        cycle_logger = get_cycle_logger(state['cycle_id'])
        cycle_logger.log_phase("Formula Generation", "START")

        # Generate expressions for all ideas
        expressions = await self.factor_agent.run(state['all_ideas'])

        state['expressions_generated'] = expressions
        state['current_phase'] = 'simulation'

        cycle_logger.info(f"Generated {len(expressions)} alpha expressions")
        cycle_logger.log_phase("Formula Generation", "COMPLETE")

        return state

    async def _deduplicate_node(self, state: AlphaWorkflowState) -> AlphaWorkflowState:
        """Remove duplicate expressions"""
        cycle_logger = get_cycle_logger(state['cycle_id'])
        cycle_logger.log_phase("Deduplication", "START")

        expressions = state.get('expressions_generated', [])

        # Filter duplicates
        novel_expressions = self.expression_history.filter_duplicates(expressions)

        duplicates_removed = len(expressions) - len(novel_expressions)
        state['expressions_deduplicated'] = novel_expressions
        state['total_duplicates_filtered'] = state.get('total_duplicates_filtered', 0) + duplicates_removed

        cycle_logger.info(f"Filtered {duplicates_removed} duplicates")
        cycle_logger.info(f"Novel expressions: {len(novel_expressions)}")
        cycle_logger.log_phase("Deduplication", "COMPLETE")

        return state

    async def _simulate_node(self, state: AlphaWorkflowState) -> AlphaWorkflowState:
        """Run simulations on WorldQuant Brain"""
        cycle_logger = get_cycle_logger(state['cycle_id'])
        cycle_logger.log_phase("Simulation", "START")

        # Get expressions to simulate
        if state.get('refined_expressions'):
            # Simulating refined expressions
            expressions_to_test = state['refined_expressions']
            cycle_logger.info("Simulating refined expressions")
        else:
            # Simulating new expressions
            expressions_to_test = state.get('expressions_deduplicated', [])
            cycle_logger.info("Simulating new expressions")

        if not expressions_to_test:
            cycle_logger.warning("No expressions to simulate")
            state['simulation_results'] = []
            return state

        # Run simulations
        results = self.simulation_agent.run(expressions_to_test)

        # Add to history
        for result in results:
            if result.get('status') == 'success':
                self.expression_history.add_expression(
                    expression=result.get('expression', ''),
                    expression_id=result.get('expression_id', ''),
                    result=result
                )

        # Append to results (don't overwrite previous results)
        existing_results = state.get('simulation_results', [])
        state['simulation_results'] = existing_results + results
        state['current_phase'] = 'evaluation'

        cycle_logger.info(f"Completed {len(results)} simulations")
        successful = sum(1 for r in results if r.get('status') == 'success')
        cycle_logger.info(f"Successful: {successful}/{len(results)}")
        cycle_logger.log_phase("Simulation", "COMPLETE")

        return state

    async def _evaluate_node(self, state: AlphaWorkflowState) -> AlphaWorkflowState:
        """Evaluate simulation results"""
        cycle_logger = get_cycle_logger(state['cycle_id'])
        cycle_logger.log_phase("Evaluation", "START")

        # Evaluate latest results
        recent_results = state.get('simulation_results', [])
        if not recent_results:
            cycle_logger.warning("No results to evaluate")
            return state

        eval_result = await self.eval_agent.run(recent_results)

        # Update state with categorized alphas
        state['hopeful_alphas'] = state.get('hopeful_alphas', []) + eval_result['hopeful_alphas']
        state['rejected_alphas'] = state.get('rejected_alphas', []) + eval_result['rejected_alphas']
        state['refinement_candidates'] = eval_result['refinement_candidates']
        state['evaluation_decisions'] = eval_result['decisions']

        # Statistics
        stats = self.eval_agent.get_summary_statistics(eval_result['decisions'])
        cycle_logger.info(f"Hopeful: {stats.get('hopeful_count', 0)}")
        cycle_logger.info(f"Refineable: {stats.get('refine_count', 0)}")
        cycle_logger.info(f"Rejected: {stats.get('rejected_count', 0)}")
        cycle_logger.info(f"Average Sharpe: {stats.get('average_sharpe', 0):.2f}")

        cycle_logger.log_phase("Evaluation", "COMPLETE")

        return state

    async def _decide_next_node(self, state: AlphaWorkflowState) -> AlphaWorkflowState:
        """Decide the next action"""
        cycle_logger = get_cycle_logger(state['cycle_id'])
        cycle_logger.log_phase("Decision", "START")

        state['iteration_count'] += 1
        iteration = state['iteration_count']
        max_iterations = state['max_iterations']

        hopeful_count = len(state.get('hopeful_alphas', []))
        refinement_count = len(state.get('refinement_candidates', []))

        cycle_logger.info(f"Iteration {iteration}/{max_iterations}")
        cycle_logger.info(f"Hopeful alphas: {hopeful_count}")
        cycle_logger.info(f"Refinement candidates: {refinement_count}")

        # Decision logic
        if hopeful_count >= 10:
            # Found enough good alphas
            cycle_logger.info("✓ Found sufficient hopeful alphas, ending workflow")
            state['next_action'] = 'end'
            state['should_continue'] = False

        elif refinement_count > 0 and state['refinement_iteration'] < 2:
            # Try refinement
            cycle_logger.info("→ Refining candidates")
            state['next_action'] = 'refine'
            state['refinement_iteration'] += 1

        elif iteration < max_iterations:
            # Continue with new research
            cycle_logger.info("→ Starting new research iteration")
            state['next_action'] = 'continue'
            state['refinement_iteration'] = 0  # Reset refinement counter

        else:
            # Max iterations reached
            cycle_logger.info("✓ Max iterations reached, ending workflow")
            state['next_action'] = 'end'
            state['should_continue'] = False

        cycle_logger.log_phase("Decision", "COMPLETE")
        return state

    async def _refine_node(self, state: AlphaWorkflowState) -> AlphaWorkflowState:
        """Refine underperforming alphas"""
        cycle_logger = get_cycle_logger(state['cycle_id'])
        cycle_logger.log_phase("Refinement", "START")

        candidates = state.get('refinement_candidates', [])
        refined = await self.refinement_agent.run(candidates)

        state['refined_expressions'] = refined
        state['refinement_candidates'] = []  # Clear candidates after refinement

        cycle_logger.info(f"Refined {len(refined)} expressions")
        cycle_logger.log_phase("Refinement", "COMPLETE")

        return state

    async def _finalize_node(self, state: AlphaWorkflowState) -> AlphaWorkflowState:
        """Finalize the workflow"""
        cycle_logger = get_cycle_logger(state['cycle_id'])
        cycle_logger.log_phase("Finalization", "START")

        state['end_time'] = datetime.now().isoformat()
        state['current_phase'] = 'complete'

        # Update statistics
        state = update_statistics(state)

        # Save final results
        self._save_final_results(state)

        # Log summary
        summary = get_state_summary(state)
        cycle_logger.log_summary(summary)

        cycle_logger.log_phase("Finalization", "COMPLETE")

        return state

    def _route_decision(self, state: AlphaWorkflowState) -> str:
        """Route based on next_action"""
        return state.get('next_action', 'end')

    def _save_final_results(self, state: AlphaWorkflowState):
        """Save final results to JSON files"""
        from pathlib import Path
        import json

        data_dir = Path('data')
        data_dir.mkdir(exist_ok=True)

        # Save hopeful alphas
        if state.get('hopeful_alphas'):
            with open(data_dir / 'hopeful_alphas.json', 'w') as f:
                json.dump(state['hopeful_alphas'], f, indent=2)

        # Save rejected alphas
        if state.get('rejected_alphas'):
            with open(data_dir / 'rejected_alphas.json', 'w') as f:
                json.dump(state['rejected_alphas'], f, indent=2)

        # Save all simulation results
        if state.get('simulation_results'):
            with open(data_dir / 'simulation_results.json', 'w') as f:
                json.dump(state['simulation_results'], f, indent=2)

        # Save all ideas
        if state.get('all_ideas'):
            with open(data_dir / 'alpha_ideas.json', 'w') as f:
                json.dump(state['all_ideas'], f, indent=2)

    # ========================================================================
    # Public API
    # ========================================================================

    async def run_async(
        self,
        research_topic: str,
        search_keywords: list = None,
        ideas_per_cycle: int = 5,
        max_iterations: int = 3
    ) -> Dict:
        """
        Run the workflow asynchronously

        Args:
            research_topic: Main research topic
            search_keywords: Additional keywords
            ideas_per_cycle: Ideas per cycle
            max_iterations: Max iterations

        Returns:
            Final state dict
        """
        # Create initial state
        initial_state = create_initial_state(
            research_topic=research_topic,
            search_keywords=search_keywords,
            ideas_per_cycle=ideas_per_cycle,
            max_iterations=max_iterations
        )

        # Run workflow
        config = {"configurable": {"thread_id": initial_state['cycle_id']}}
        final_state = await self.workflow.ainvoke(initial_state, config)

        return final_state

    def run(
        self,
        research_topic: str,
        search_keywords: list = None,
        ideas_per_cycle: int = 5,
        max_iterations: int = 3
    ) -> Dict:
        """
        Run the workflow synchronously

        Args:
            research_topic: Main research topic
            search_keywords: Additional keywords
            ideas_per_cycle: Ideas per cycle
            max_iterations: Max iterations

        Returns:
            Final state dict
        """
        return asyncio.run(self.run_async(
            research_topic, search_keywords, ideas_per_cycle, max_iterations
        ))
