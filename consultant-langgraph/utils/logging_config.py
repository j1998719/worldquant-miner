"""
Logging configuration for the WorldQuant Alpha Consultant system
Provides structured logging with cycle-based and agent-based log files
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional


class CycleLogger:
    """
    Logger that creates per-cycle log files for tracking complete workflow executions
    """

    def __init__(self, cycle_id: str):
        """
        Initialize cycle logger

        Args:
            cycle_id: Unique cycle identifier (e.g., 'cycle_001')
        """
        self.cycle_id = cycle_id
        self.log_file = Path('logs') / 'cycles' / f'{cycle_id}.log'
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger(f'cycle.{cycle_id}')
        self.logger.setLevel(logging.DEBUG)

        # File handler for this cycle
        if not any(isinstance(h, logging.FileHandler) for h in self.logger.handlers):
            handler = logging.FileHandler(self.log_file, encoding='utf-8')
            handler.setFormatter(logging.Formatter(
                '[%(asctime)s] [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            self.logger.addHandler(handler)

    def info(self, msg: str):
        """Log info message"""
        self.logger.info(msg)

    def error(self, msg: str):
        """Log error message"""
        self.logger.error(msg)

    def warning(self, msg: str):
        """Log warning message"""
        self.logger.warning(msg)

    def debug(self, msg: str):
        """Log debug message"""
        self.logger.debug(msg)

    def log_phase(self, phase_name: str, status: str = "START"):
        """
        Log the start or completion of a workflow phase

        Args:
            phase_name: Name of the phase (e.g., 'Research', 'Simulation')
            status: 'START' or 'COMPLETE'
        """
        separator = "=" * 80
        self.logger.info(f"\n{separator}")
        self.logger.info(f"{status}: {phase_name}")
        self.logger.info(f"{separator}\n")

    def log_summary(self, summary_dict: dict):
        """
        Log a summary dictionary at the end of a cycle

        Args:
            summary_dict: Dictionary with cycle statistics
        """
        self.logger.info("\n" + "=" * 80)
        self.logger.info("CYCLE SUMMARY")
        self.logger.info("=" * 80)
        for key, value in summary_dict.items():
            self.logger.info(f"{key}: {value}")
        self.logger.info("=" * 80 + "\n")


def setup_logging(log_level: str = "INFO", enable_console: bool = True):
    """
    Setup global logging configuration

    Args:
        log_level: Logging level ('DEBUG', 'INFO', 'WARNING', 'ERROR')
        enable_console: Whether to also log to console (default: True)
    """
    # Create logs directory structure
    Path('logs/agents').mkdir(parents=True, exist_ok=True)
    Path('logs/cycles').mkdir(parents=True, exist_ok=True)
    Path('logs/errors').mkdir(parents=True, exist_ok=True)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler (if enabled)
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter(
            '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        ))
        root_logger.addHandler(console_handler)

    # Main log file handler
    main_log_file = Path('logs') / 'main.log'
    file_handler = logging.FileHandler(main_log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    root_logger.addHandler(file_handler)

    # Error log file handler
    error_log_file = Path('logs/errors') / f'errors_{datetime.now().strftime("%Y%m%d")}.log'
    error_handler = logging.FileHandler(error_log_file, encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s\n'
        'File: %(pathname)s:%(lineno)d\n'
        'Function: %(funcName)s\n',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    root_logger.addHandler(error_handler)

    logging.info("Logging system initialized")


def get_cycle_logger(cycle_id: Optional[str] = None) -> CycleLogger:
    """
    Get or create a cycle logger

    Args:
        cycle_id: Optional cycle ID. If None, generates one based on timestamp

    Returns:
        CycleLogger instance
    """
    if cycle_id is None:
        cycle_id = f"cycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    return CycleLogger(cycle_id)
