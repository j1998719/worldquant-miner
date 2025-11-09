"""
Idea Agent - Generates alpha trading hypotheses
"""

import requests
import json
import random
from typing import Dict, List, Optional
from datetime import datetime

from .base_agent import BaseAgent


class IdeaAgent(BaseAgent):
    """
    Agent responsible for generating alpha trading ideas/hypotheses
    Uses LLM (Ollama) to generate ideas based on:
    - Historical successful alphas (hopeful_alphas.json)
    - Market insights
    - Feedback from previous evaluations
    """
    
    def __init__(self, ollama_url: str = "http://localhost:11434", 
                 ollama_model: str = "gemma2:2b", config: Optional[Dict] = None):
        """
        Initialize Idea Agent
        
        Args:
            ollama_url: Ollama API URL
            ollama_model: Ollama model name
            config: Optional configuration dict
        """
        super().__init__('idea_agent', config)
        
        self.ollama_url = ollama_url
        self.ollama_model = ollama_model
        self.temperature = self.config.get('temperature', 0.8)
        self.max_retries = self.config.get('max_retries', 3)
    
    def run(self, count: int = 10) -> List[Dict]:
        """
        Main execution: generate alpha ideas
        
        Args:
            count: Number of ideas to generate
        
        Returns:
            List of idea dicts
        """
        self.logger.info(f"Generating {count} alpha ideas...")
        start_time = datetime.now()
        
        # Load historical successful alphas for inspiration
        hopeful_alphas = self.load_json('data/hopeful_alphas.json')
        
        # Load evaluation feedback (if exists)
        eval_feedback = self.load_json('data/eval_decisions.json')
        
        # Generate ideas
        ideas = []
        for i in range(count):
            idea = self._generate_single_idea(i, hopeful_alphas, eval_feedback)
            if idea:
                ideas.append(idea)
                self.logger.info(f"Idea {i+1}/{count}: {idea['hypothesis'][:80]}...")
        
        self.log_execution_time(start_time, f"Generated {len(ideas)} ideas")
        
        # Save ideas
        self.save_json(ideas, 'data/alpha_ideas.json')
        
        return ideas
    
    def _generate_single_idea(self, index: int, hopeful_alphas: List[Dict], 
                              eval_feedback: List[Dict]) -> Optional[Dict]:
        """
        Generate a single alpha idea using LLM
        
        Args:
            index: Idea index
            hopeful_alphas: List of historically successful alphas
            eval_feedback: Previous evaluation feedback
        
        Returns:
            Idea dict or None if generation failed
        """
        # Build prompt
        prompt = self._build_prompt(hopeful_alphas, eval_feedback)
        
        # Call LLM
        response_text = self._call_ollama(prompt)
        
        if not response_text:
            self.logger.warning(f"Failed to generate idea {index}")
            return None
        
        # Parse LLM response
        idea = self._parse_llm_response(response_text, index)
        
        return idea
    
    def _build_prompt(self, hopeful_alphas: List[Dict], eval_feedback: List[Dict]) -> str:
        """
        Build prompt for LLM
        
        Args:
            hopeful_alphas: Historical successful alphas
            eval_feedback: Previous evaluation feedback
        
        Returns:
            Prompt string
        """
        # Load prompt template
        template = self.load_prompt('idea_generation.txt')
        
        if not template:
            # Fallback prompt if template not found
            template = self._get_default_prompt()
        
        # Add context from hopeful alphas
        context = ""
        if hopeful_alphas and len(hopeful_alphas) > 0:
            # Sample a few successful alphas for inspiration
            samples = random.sample(hopeful_alphas, min(3, len(hopeful_alphas)))
            context += "\n=== Examples of Successful Alphas ===\n"
            for alpha in samples:
                context += f"- Expression: {alpha.get('expression', 'N/A')}\n"
                context += f"  Sharpe: {alpha.get('sharpe', 0):.2f}, Fitness: {alpha.get('fitness', 0):.2f}\n"
        
        # Add recent feedback insights
        if eval_feedback and len(eval_feedback) > 0:
            recent = eval_feedback[-3:] if len(eval_feedback) > 3 else eval_feedback
            context += "\n=== Recent Feedback ===\n"
            for feedback in recent:
                if feedback.get('decision') == 'hopeful':
                    context += f"- Success: {feedback.get('reason', 'N/A')}\n"
        
        # Fill in template
        prompt = template.replace('{CONTEXT}', context)
        
        return prompt
    
    def _get_default_prompt(self) -> str:
        """Get default prompt if template file is not found"""
        return """You are a quantitative trading expert. Generate ONE creative alpha trading hypothesis.

{CONTEXT}

Your hypothesis should:
1. Be based on sound financial logic
2. Capture market inefficiencies or patterns
3. Be implementable using price, volume, and fundamental data
4. Be original and not too similar to existing alphas

Format your response as:
HYPOTHESIS: [Your hypothesis in 1-2 sentences]
RATIONALE: [Why this might work, 2-3 sentences]
DATASETS: [Suggested datasets, e.g., fundamental6, pv1]

Generate ONE hypothesis now:"""
    
    def _call_ollama(self, prompt: str) -> Optional[str]:
        """
        Call Ollama API to generate text
        
        Args:
            prompt: Input prompt
        
        Returns:
            Generated text or None if failed
        """
        url = f"{self.ollama_url}/api/generate"
        
        payload = {
            'model': self.ollama_model,
            'prompt': prompt,
            'stream': False,
            'options': {
                'temperature': self.temperature
            }
        }
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(url, json=payload, timeout=60)
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get('response', '')
                else:
                    self.logger.warning(f"Ollama call failed (attempt {attempt+1}): {response.status_code}")
            
            except Exception as e:
                self.logger.error(f"Ollama exception (attempt {attempt+1}): {e}")
            
            if attempt < self.max_retries - 1:
                import time
                time.sleep(2)
        
        return None
    
    def _parse_llm_response(self, response_text: str, index: int) -> Dict:
        """
        Parse LLM response into structured idea dict
        
        Args:
            response_text: Raw LLM response
            index: Idea index
        
        Returns:
            Idea dict
        """
        # Extract hypothesis, rationale, and datasets
        hypothesis = ""
        rationale = ""
        datasets = []
        
        lines = response_text.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('HYPOTHESIS:'):
                hypothesis = line.replace('HYPOTHESIS:', '').strip()
            elif line.startswith('RATIONALE:'):
                rationale = line.replace('RATIONALE:', '').strip()
            elif line.startswith('DATASETS:'):
                datasets_str = line.replace('DATASETS:', '').strip()
                datasets = [d.strip() for d in datasets_str.split(',')]
        
        # Fallback: if parsing failed, use entire response as hypothesis
        if not hypothesis:
            hypothesis = response_text[:200]
            rationale = "Generated by LLM"
            datasets = ["fundamental6", "pv1"]
        
        return {
            'idea_id': self.generate_id('idea', index + 1),
            'hypothesis': hypothesis,
            'rationale': rationale,
            'suggested_datasets': datasets,
            'timestamp': self.get_timestamp()
        }


