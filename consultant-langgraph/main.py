#!/usr/bin/env python3
"""
WorldQuant Alpha Brain Consultant - Main Entry Point
LangGraph + Ollama Cloud implementation for automated alpha discovery
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

from alpha_workflow import AlphaDiscoveryWorkflow
from utils.logging_config import setup_logging


def load_config(config_path: str = "config/langgraph_config.json") -> dict:
    """
    Load configuration from JSON file

    Args:
        config_path: Path to config file

    Returns:
        Configuration dictionary
    """
    config_file = Path(config_path)
    if not config_file.exists():
        print(f"Error: Configuration file not found: {config_path}")
        sys.exit(1)

    with open(config_file, 'r') as f:
        config = json.load(f)

    # Load Ollama API key from config.yaml if needed
    yaml_config_path = Path("config.yaml")
    if yaml_config_path.exists():
        import yaml
        with open(yaml_config_path, 'r') as f:
            yaml_config = yaml.safe_load(f)
            config['ollama_api_key'] = yaml_config.get('ollama_api_key', '')

    return config


def print_banner():
    """Print ASCII banner"""
    banner = """
╔═══════════════════════════════════════════════════════════════════════╗
║                                                                       ║
║   WorldQuant Alpha Brain Consultant                                  ║
║   LangGraph + Ollama Cloud Edition                                   ║
║                                                                       ║
║   Automated Alpha Discovery Pipeline                                 ║
║   Research → Ideas → Formulas → Simulation → Refinement              ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_final_summary(final_state: dict):
    """
    Print final workflow summary

    Args:
        final_state: Final workflow state
    """
    print("\n" + "=" * 80)
    print("WORKFLOW COMPLETE")
    print("=" * 80)

    print(f"\nCycle ID: {final_state.get('cycle_id', 'N/A')}")
    print(f"Duration: {final_state.get('start_time', 'N/A')} → {final_state.get('end_time', 'N/A')}")

    print("\n--- Research Phase ---")
    print(f"Papers searched: {final_state.get('total_papers_searched', 0)}")
    print(f"Ideas generated: {final_state.get('total_ideas_generated', 0)}")

    print("\n--- Testing Phase ---")
    print(f"Expressions tested: {final_state.get('total_expressions_tested', 0)}")
    print(f"Duplicates filtered: {final_state.get('total_duplicates_filtered', 0)}")

    print("\n--- Results ---")
    hopeful_count = len(final_state.get('hopeful_alphas', []))
    rejected_count = len(final_state.get('rejected_alphas', []))
    print(f"✓ Hopeful alphas: {hopeful_count}")
    print(f"✗ Rejected alphas: {rejected_count}")

    if hopeful_count > 0:
        print("\n--- Top Hopeful Alphas ---")
        hopeful = final_state.get('hopeful_alphas', [])
        # Sort by Sharpe ratio
        hopeful_sorted = sorted(hopeful, key=lambda x: x.get('sharpe', 0), reverse=True)

        for i, alpha in enumerate(hopeful_sorted[:5], 1):
            print(f"\n{i}. Expression ID: {alpha.get('expression_id', 'N/A')}")
            print(f"   Sharpe: {alpha.get('sharpe', 0):.3f}")
            print(f"   Fitness: {alpha.get('fitness', 0):.3f}")
            print(f"   Returns: {alpha.get('returns', 0):.2%}")
            print(f"   Turnover: {alpha.get('turnover', 0):.1f}%")
            print(f"   Expression: {alpha.get('expression', 'N/A')[:100]}...")

    print("\n--- Data Files ---")
    print(f"Hopeful alphas: data/hopeful_alphas.json")
    print(f"Rejected alphas: data/rejected_alphas.json")
    print(f"All ideas: data/alpha_ideas.json")
    print(f"Simulation results: data/simulation_results.json")

    print("\n--- Logs ---")
    print(f"Cycle log: logs/cycles/{final_state.get('cycle_id', 'N/A')}.log")
    print(f"Agent logs: logs/agents/")

    print("\n" + "=" * 80)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="WorldQuant Alpha Brain Consultant - Automated Alpha Discovery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Discover momentum alphas
  python main.py momentum --keywords "trend,price"

  # Value investing alphas with custom settings
  python main.py value --keywords "fundamental,earnings" --ideas 10 --iterations 5

  # Mean reversion with specific config
  python main.py "mean reversion" --config config/custom_config.json

  # Volatility strategies
  python main.py volatility --keywords "variance,garch,realized_vol"
        """
    )

    parser.add_argument(
        "topic",
        type=str,
        help="Research topic (e.g., 'momentum', 'value', 'volatility', 'quality')"
    )

    parser.add_argument(
        "--keywords",
        type=str,
        default="",
        help="Additional search keywords (comma-separated)"
    )

    parser.add_argument(
        "--ideas",
        type=int,
        default=None,
        help="Number of ideas per cycle (default: from config)"
    )

    parser.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="Maximum iterations (default: from config)"
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config/langgraph_config.json",
        help="Path to configuration file"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )

    parser.add_argument(
        "--no-console",
        action="store_true",
        help="Disable console logging (only log to files)"
    )

    args = parser.parse_args()

    # Print banner
    print_banner()

    # Setup logging
    setup_logging(
        log_level=args.log_level,
        enable_console=not args.no_console
    )

    print(f"📚 Research Topic: {args.topic}")
    if args.keywords:
        print(f"🔍 Keywords: {args.keywords}")

    # Load configuration
    print(f"\n⚙️  Loading configuration from {args.config}...")
    config = load_config(args.config)

    # Override config with CLI arguments
    ideas_per_cycle = args.ideas if args.ideas else config.get('workflow', {}).get('ideas_per_cycle', 5)
    max_iterations = args.iterations if args.iterations else config.get('workflow', {}).get('max_iterations', 3)

    print(f"   Ideas per cycle: {ideas_per_cycle}")
    print(f"   Max iterations: {max_iterations}")
    print(f"   Ollama model: {config.get('cloud_model', 'N/A')}")

    # Parse keywords
    keywords = [k.strip() for k in args.keywords.split(',')] if args.keywords else []

    # Initialize workflow
    print("\n🚀 Initializing workflow...")
    workflow = AlphaDiscoveryWorkflow(config)

    # Run workflow
    print(f"\n▶️  Starting alpha discovery for topic: '{args.topic}'")
    print("=" * 80)

    try:
        final_state = workflow.run(
            research_topic=args.topic,
            search_keywords=keywords,
            ideas_per_cycle=ideas_per_cycle,
            max_iterations=max_iterations
        )

        # Print summary
        print_final_summary(final_state)

        # Check for hopeful alphas
        hopeful_count = len(final_state.get('hopeful_alphas', []))
        if hopeful_count > 0:
            print(f"\n✅ SUCCESS: Found {hopeful_count} hopeful alpha(s)!")
            return 0
        else:
            print(f"\n⚠️  No hopeful alphas found. Try:")
            print("   - Different research topic")
            print("   - More iterations (--iterations)")
            print("   - More ideas per cycle (--ideas)")
            return 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Workflow interrupted by user")
        return 130

    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
