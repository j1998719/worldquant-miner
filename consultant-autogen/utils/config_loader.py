"""
config_loader.py - Simple configuration loader
"""
import json
import os
from pathlib import Path


class ConfigLoader:
    """Simple configuration loader with environment variable support"""
    
    _config = {}
    _config_file = None
    
    @classmethod
    def load(cls, config_file=None):
        """Load configuration from file"""
        if config_file is None:
            base_dir = Path(__file__).resolve().parents[1]
            config_file = base_dir / "config" / "scraper_config.json"
        
        cls._config_file = config_file
        
        if Path(config_file).exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                cls._config = json.load(f)
        else:
            cls._config = {}
    
    @classmethod
    def get(cls, key, default=None):
        """
        Get configuration value
        Priority: Environment variable > Config file > Default
        """
        # Check environment variable first
        env_key = key.upper()
        env_value = os.environ.get(env_key)
        if env_value is not None:
            return env_value
        
        # Check config file
        if not cls._config and cls._config_file is None:
            cls.load()
        
        return cls._config.get(key, default)
    
    @classmethod
    def set(cls, key, value):
        """Set configuration value"""
        if not cls._config:
            cls.load()
        cls._config[key] = value

