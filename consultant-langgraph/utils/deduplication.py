"""
Expression deduplication and history tracking
Prevents wasting API quota by testing duplicate or semantically equivalent alphas
"""

import hashlib
import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime


class ExpressionHistory:
    """
    Tracks tested alpha expressions to avoid duplicates
    Uses normalized fingerprints to detect semantically equivalent expressions
    """

    def __init__(self, history_file: str = "data/expression_history.json"):
        """
        Initialize expression history tracker

        Args:
            history_file: Path to JSON file storing expression history
        """
        self.history_file = Path(history_file)
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger('deduplication')

        # Load existing history
        self.history: List[Dict] = self._load_history()

        # Create fingerprint index for fast lookup
        self.fingerprints: Set[str] = {
            entry.get('fingerprint') for entry in self.history if entry.get('fingerprint')
        }

    def _load_history(self) -> List[Dict]:
        """Load expression history from file"""
        if not self.history_file.exists():
            self.logger.info("No existing history file, starting fresh")
            return []

        try:
            with open(self.history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            self.logger.info(f"Loaded {len(history)} historical expressions")
            return history
        except Exception as e:
            self.logger.error(f"Failed to load history: {e}")
            return []

    def _save_history(self):
        """Save expression history to file"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.history, f, indent=2, ensure_ascii=False)
            self.logger.debug(f"Saved history ({len(self.history)} entries)")
        except Exception as e:
            self.logger.error(f"Failed to save history: {e}")

    def normalize_expression(self, expression: str) -> str:
        """
        Normalize an alpha expression for comparison

        Args:
            expression: Raw alpha expression

        Returns:
            Normalized expression string
        """
        # Convert to lowercase
        expr = expression.lower()

        # Remove all whitespace
        expr = re.sub(r'\s+', '', expr)

        # Normalize common variations
        # e.g., "delay(x, 1)" vs "delay(x,1)"
        expr = re.sub(r',\s*', ',', expr)

        # Sort commutative operations (future enhancement)
        # For now, keep as-is

        return expr

    def compute_fingerprint(self, expression: str) -> str:
        """
        Compute a unique fingerprint for an expression

        Args:
            expression: Alpha expression string

        Returns:
            SHA256 fingerprint (hex string)
        """
        normalized = self.normalize_expression(expression)
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    def is_duplicate(self, expression: str) -> bool:
        """
        Check if an expression has already been tested

        Args:
            expression: Alpha expression to check

        Returns:
            True if duplicate, False if novel
        """
        fingerprint = self.compute_fingerprint(expression)
        return fingerprint in self.fingerprints

    def add_expression(
        self,
        expression: str,
        expression_id: str,
        result: Optional[Dict] = None
    ):
        """
        Add an expression to the history

        Args:
            expression: Alpha expression string
            expression_id: Unique expression ID
            result: Optional simulation result dict
        """
        fingerprint = self.compute_fingerprint(expression)

        # Check if already exists
        if fingerprint in self.fingerprints:
            self.logger.warning(f"Expression {expression_id} is a duplicate (fingerprint exists)")
            return

        # Add to history
        entry = {
            'expression_id': expression_id,
            'expression': expression,
            'fingerprint': fingerprint,
            'timestamp': datetime.now().isoformat(),
            'result': result
        }

        self.history.append(entry)
        self.fingerprints.add(fingerprint)

        # Save to disk
        self._save_history()

        self.logger.debug(f"Added expression {expression_id} to history")

    def filter_duplicates(self, expressions: List[Dict]) -> List[Dict]:
        """
        Filter out duplicate expressions from a list

        Args:
            expressions: List of expression dicts (must have 'expression' key)

        Returns:
            Filtered list with only novel expressions
        """
        novel_expressions = []
        duplicate_count = 0

        for expr_dict in expressions:
            expression = expr_dict.get('expression', '')
            if not expression:
                continue

            if not self.is_duplicate(expression):
                novel_expressions.append(expr_dict)
            else:
                duplicate_count += 1
                self.logger.debug(
                    f"Filtered duplicate: {expr_dict.get('expression_id', 'unknown')}"
                )

        if duplicate_count > 0:
            self.logger.info(
                f"Filtered {duplicate_count} duplicates, "
                f"{len(novel_expressions)} novel expressions remain"
            )

        return novel_expressions

    def get_statistics(self) -> Dict:
        """
        Get statistics about expression history

        Returns:
            Dict with statistics (total_expressions, unique_fingerprints, etc.)
        """
        # Count successful vs failed expressions
        successful = sum(
            1 for entry in self.history
            if entry.get('result') and entry['result'].get('sharpe', 0) > 0.5
        )

        return {
            'total_expressions': len(self.history),
            'unique_fingerprints': len(self.fingerprints),
            'successful_alphas': successful,
            'success_rate': successful / len(self.history) if self.history else 0
        }

    def clear_history(self):
        """Clear all expression history (use with caution)"""
        self.history = []
        self.fingerprints = set()
        self._save_history()
        self.logger.warning("Expression history cleared")
