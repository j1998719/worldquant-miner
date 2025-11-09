"""
Logging configuration for the multi-agent system
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path


def setup_logging(log_level=logging.INFO, log_dir='logs'):
    """
    Setup logging configuration for all agents
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_dir: Directory to store log files
    """
    # Create log directories if they don't exist
    log_dir = Path(log_dir)
    (log_dir / 'agents').mkdir(parents=True, exist_ok=True)
    (log_dir / 'cycles').mkdir(parents=True, exist_ok=True)
    (log_dir / 'errors').mkdir(parents=True, exist_ok=True)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    root_logger.handlers = []
    
    # Console handler (INFO level)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (all logs)
    file_handler = RotatingFileHandler(
        log_dir / 'orchestrator.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_formatter = logging.Formatter(
        '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    return root_logger


def get_logger(name, log_file=None, log_level=logging.INFO):
    """
    Get a logger for a specific agent
    
    Args:
        name: Logger name (e.g., 'idea_agent')
        log_file: Optional specific log file path
        log_level: Logging level
    
    Returns:
        Logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Add agent-specific file handler if log_file is provided
    if log_file:
        handler = RotatingFileHandler(
            log_file,
            maxBytes=5*1024*1024,  # 5MB
            backupCount=5,
            encoding='utf-8'
        )
        handler.setLevel(log_level)
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger


class CycleLogger:
    """Logger for individual mining cycles"""
    
    def __init__(self, cycle_id, log_dir='logs/cycles'):
        self.cycle_id = cycle_id
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.log_file = self.log_dir / f'cycle_{cycle_id:03d}_{timestamp}.log'
        
        self.logger = logging.getLogger(f'cycle_{cycle_id}')
        self.logger.setLevel(logging.DEBUG)
        
        # Remove existing handlers
        self.logger.handlers = []
        
        # File handler for this cycle
        handler = logging.FileHandler(self.log_file, encoding='utf-8')
        formatter = logging.Formatter(
            '[%(asctime)s] %(message)s',
            datefmt='%H:%M:%S'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def info(self, message):
        """Log info message"""
        self.logger.info(message)
    
    def error(self, message):
        """Log error message"""
        self.logger.error(message)
    
    def section(self, title):
        """Log a section header"""
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"{title}")
        self.logger.info(f"{'='*60}\n")
    
    def close(self):
        """Close handlers"""
        for handler in self.logger.handlers:
            handler.close()
            self.logger.removeHandler(handler)

