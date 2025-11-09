"""
Base Agent class for all agents
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional


class BaseAgent:
    """
    Base class for all agents in the system
    """
    
    def __init__(self, name: str, config: Optional[Dict] = None):
        """
        Initialize base agent
        
        Args:
            name: Agent name (e.g., 'idea_agent')
            config: Optional configuration dict
        """
        self.name = name
        self.config = config or {}
        self.logger = logging.getLogger(name)
        
        # Setup agent-specific log file
        log_file = Path('logs') / 'agents' / f'{name}.log'
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        if not any(isinstance(h, logging.FileHandler) and h.baseFilename == str(log_file.absolute()) 
                   for h in self.logger.handlers):
            handler = logging.FileHandler(log_file, encoding='utf-8')
            handler.setFormatter(logging.Formatter(
                '[%(asctime)s] [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            self.logger.addHandler(handler)
    
    def load_json(self, file_path: str) -> Any:
        """
        Load data from JSON file
        
        Args:
            file_path: Path to JSON file
        
        Returns:
            Loaded data (dict, list, etc.)
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            self.logger.warning(f"File not found: {file_path}, returning empty list")
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.logger.debug(f"Loaded {file_path}")
            return data
        except Exception as e:
            self.logger.error(f"Failed to load {file_path}: {e}")
            return []
    
    def save_json(self, data: Any, file_path: str, indent: int = 2):
        """
        Save data to JSON file
        
        Args:
            data: Data to save
            file_path: Path to JSON file
            indent: JSON indentation
        """
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=indent, ensure_ascii=False)
            self.logger.debug(f"Saved {file_path}")
        except Exception as e:
            self.logger.error(f"Failed to save {file_path}: {e}")
            raise
    
    def load_prompt(self, prompt_file: str) -> str:
        """
        Load prompt template from file
        
        Args:
            prompt_file: Prompt file name (e.g., 'idea_generation.txt')
        
        Returns:
            Prompt template string
        """
        prompt_path = Path('prompts') / prompt_file
        
        if not prompt_path.exists():
            self.logger.error(f"Prompt file not found: {prompt_path}")
            return ""
        
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt = f.read()
            self.logger.debug(f"Loaded prompt: {prompt_file}")
            return prompt
        except Exception as e:
            self.logger.error(f"Failed to load prompt {prompt_file}: {e}")
            return ""
    
    def generate_id(self, prefix: str, index: int) -> str:
        """
        Generate a unique ID
        
        Args:
            prefix: ID prefix (e.g., 'idea', 'expr', 'sim')
            index: Sequential index
        
        Returns:
            ID string (e.g., 'idea_001')
        """
        return f"{prefix}_{index:03d}"
    
    def get_timestamp(self) -> str:
        """
        Get current timestamp in ISO format
        
        Returns:
            ISO formatted timestamp string
        """
        return datetime.now().isoformat()
    
    def log_execution_time(self, start_time: datetime, task_name: str):
        """
        Log execution time for a task
        
        Args:
            start_time: Task start time
            task_name: Name of the task
        """
        duration = (datetime.now() - start_time).total_seconds()
        self.logger.info(f"{task_name} took {duration:.2f}s")
    
    def run(self, *args, **kwargs):
        """
        Main execution method (to be implemented by subclasses)
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement run() method")

