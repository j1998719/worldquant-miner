"""
Main entry point for the Multi-Agent Alpha Mining System
"""

import argparse
import json
import sys
from pathlib import Path

from agents.orchestrator_agent import OrchestratorAgent
from utils.logging_config import setup_logging


def load_config(config_path: str) -> dict:
    """Load configuration from JSON file"""
    config_file = Path(config_path)
    
    if not config_file.exists():
        print(f"Warning: Config file not found: {config_path}")
        print("Using default configuration")
        return {}
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"Loaded configuration from {config_path}")
        return config
    except Exception as e:
        print(f"Error loading config: {e}")
        print("Using default configuration")
        return {}


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Multi-Agent Alpha Mining System for WorldQuant Brain'
    )
    
    parser.add_argument(
        '--credentials',
        type=str,
        default='credential.txt',
        help='Path to WorldQuant credentials file (default: credential.txt)'
    )
    
    parser.add_argument(
        '--config',
        type=str,
        default='config/orchestrator_config.json',
        help='Path to configuration file (default: config/orchestrator_config.json)'
    )
    
    parser.add_argument(
        '--mode',
        type=str,
        choices=['single', 'continuous'],
        default='single',
        help='Execution mode: single cycle or continuous (default: single)'
    )
    
    parser.add_argument(
        '--cycles',
        type=int,
        default=None,
        help='Number of cycles to run in continuous mode (default: infinite)'
    )
    
    parser.add_argument(
        '--delay',
        type=int,
        default=10,
        help='Delay between cycles in seconds (default: 10)'
    )
    
    parser.add_argument(
        '--ideas',
        type=int,
        default=None,
        help='Number of ideas per cycle (overrides config)'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    import logging
    log_level = getattr(logging, args.log_level)
    setup_logging(log_level=log_level)
    
    logger = logging.getLogger('main')
    
    # Print banner
    print("\n" + "="*70)
    print(" "*15 + "MULTI-AGENT ALPHA MINING SYSTEM")
    print(" "*20 + "WorldQuant Brain Edition")
    print("="*70 + "\n")
    
    # Check credentials file
    credentials_path = Path(args.credentials)
    if not credentials_path.exists():
        logger.error(f"Credentials file not found: {args.credentials}")
        logger.error("Please create a credential.txt file with your email and password")
        return 1
    
    # Load configuration
    config = load_config(args.config)
    
    # Override config with command-line arguments
    if args.ideas:
        config['ideas_per_cycle'] = args.ideas
        logger.info(f"Overriding ideas_per_cycle: {args.ideas}")
    
    # Display configuration
    logger.info("Configuration:")
    logger.info(f"  Mode: {args.mode}")
    logger.info(f"  Ideas per cycle: {config.get('ideas_per_cycle', 10)}")
    logger.info(f"  Ollama model: {config.get('ollama_model', 'gemma2:2b')}")
    logger.info(f"  Region: {config.get('simulation_settings', {}).get('region', 'USA')}")
    logger.info(f"  Universe: {config.get('simulation_settings', {}).get('universe', 'TOP3000')}")
    logger.info(f"  Deduplication: {config.get('enable_deduplication', True)}")
    
    if args.mode == 'continuous':
        if args.cycles:
            logger.info(f"  Max cycles: {args.cycles}")
        else:
            logger.info(f"  Max cycles: infinite")
        logger.info(f"  Delay between cycles: {args.delay}s")
    
    print()
    
    # Initialize orchestrator
    try:
        logger.info("Initializing Orchestrator Agent...")
        orchestrator = OrchestratorAgent(
            credentials_path=str(credentials_path),
            config=config
        )
        logger.info("Orchestrator initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize orchestrator: {e}")
        return 1
    
    # Run mining
    try:
        if args.mode == 'single':
            logger.info("\nStarting single cycle execution...")
            summary = orchestrator.run_single_cycle()
            
            print("\n" + "="*70)
            print("CYCLE SUMMARY")
            print("="*70)
            print(f"Total tested: {summary['total_tested']}")
            print(f"Hopeful: {summary['hopeful_count']}")
            print(f"Success rate: {summary['success_rate']*100:.1f}%")
            print(f"Duration: {summary['duration_seconds']:.1f}s")
            print(f"Status: {summary['status']}")
            print("="*70 + "\n")
        
        else:  # continuous
            logger.info("\nStarting continuous execution...")
            logger.info("Press Ctrl+C to stop\n")
            
            orchestrator.run_continuous(
                max_cycles=args.cycles,
                delay_between_cycles=args.delay
            )
    
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        print("\n" + "="*70)
        print("Execution stopped by user")
        print("="*70 + "\n")
    
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    logger.info("Execution completed successfully")
    return 0


if __name__ == '__main__':
    sys.exit(main())

