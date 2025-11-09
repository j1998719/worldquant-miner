"""
Expression deduplication utilities
"""

import hashlib
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional


def normalize_expression(expr: str) -> str:
    """
    Normalize an alpha expression for comparison
    
    Args:
        expr: Raw alpha expression
    
    Returns:
        Normalized expression string
    """
    # Remove all whitespace
    normalized = re.sub(r'\s+', '', expr)
    
    # Convert to lowercase
    normalized = normalized.lower()
    
    # Remove extra parentheses
    # normalized = re.sub(r'\(\(([^()]+)\)\)', r'(\1)', normalized)
    
    return normalized


def get_expression_fingerprint(expr: str) -> str:
    """
    Generate a unique fingerprint for an expression
    
    Args:
        expr: Alpha expression
    
    Returns:
        16-character hex fingerprint
    """
    normalized = normalize_expression(expr)
    hash_obj = hashlib.sha256(normalized.encode('utf-8'))
    return hash_obj.hexdigest()[:16]


class ExpressionHistory:
    """
    Manages historical record of tested expressions
    """
    
    def __init__(self, history_file='data/expression_history.json'):
        self.history_file = Path(history_file)
        self.history: Dict = {}
        self.load()
    
    def load(self):
        """Load expression history from file"""
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
            except Exception as e:
                print(f"Warning: Failed to load expression history: {e}")
                self.history = {}
        else:
            self.history = {}
    
    def save(self):
        """Save expression history to file"""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Warning: Failed to save expression history: {e}")
    
    def add(self, expression: str, result: Dict) -> str:
        """
        Add an expression to history
        
        Args:
            expression: Alpha expression
            result: Simulation result dict containing sharpe, fitness, etc.
        
        Returns:
            Fingerprint of the expression
        """
        fingerprint = get_expression_fingerprint(expression)
        
        timestamp = datetime.now().isoformat()
        
        if fingerprint in self.history:
            # Update existing entry
            entry = self.history[fingerprint]
            entry['test_count'] += 1
            entry['last_tested'] = timestamp
            
            # Update best sharpe if better
            if result.get('sharpe', -999) > entry.get('best_sharpe', -999):
                entry['best_sharpe'] = result.get('sharpe')
                entry['best_fitness'] = result.get('fitness')
                entry['status'] = self._determine_status(result)
        else:
            # Create new entry
            self.history[fingerprint] = {
                'expression': expression,
                'first_tested': timestamp,
                'last_tested': timestamp,
                'test_count': 1,
                'best_sharpe': result.get('sharpe', -999),
                'best_fitness': result.get('fitness', 0),
                'status': self._determine_status(result)
            }
        
        self.save()
        return fingerprint
    
    def get(self, expression: str) -> Optional[Dict]:
        """
        Get history entry for an expression
        
        Args:
            expression: Alpha expression
        
        Returns:
            History entry dict or None if not found
        """
        fingerprint = get_expression_fingerprint(expression)
        return self.history.get(fingerprint)
    
    def exists(self, expression: str) -> bool:
        """
        Check if expression has been tested before
        
        Args:
            expression: Alpha expression
        
        Returns:
            True if expression exists in history
        """
        fingerprint = get_expression_fingerprint(expression)
        return fingerprint in self.history
    
    def _determine_status(self, result: Dict) -> str:
        """
        Determine status based on result
        
        Args:
            result: Simulation result
        
        Returns:
            Status string: hopeful, rejected, error
        """
        if result.get('error'):
            return 'error'
        
        sharpe = result.get('sharpe', -999)
        fitness = result.get('fitness', 0)
        
        if sharpe > 0.5 and fitness > 0.6:
            return 'hopeful'
        else:
            return 'rejected'
    
    def get_stats(self) -> Dict:
        """
        Get statistics about expression history
        
        Returns:
            Stats dict with counts by status
        """
        stats = {
            'total': len(self.history),
            'hopeful': 0,
            'rejected': 0,
            'error': 0
        }
        
        for entry in self.history.values():
            status = entry.get('status', 'rejected')
            if status in stats:
                stats[status] += 1
        
        return stats

