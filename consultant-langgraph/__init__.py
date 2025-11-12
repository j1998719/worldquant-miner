"""
WorldQuant Alpha Brain Consultant - LangGraph Implementation
Multi-agent system for automated alpha discovery using Ollama Cloud and WorldQuant Brain API
"""

__version__ = "1.0.0"

from .base_agent import BaseAgent
from .simulation_agent import SimulationAgent

__all__ = [
    "BaseAgent",
    "SimulationAgent",
]
