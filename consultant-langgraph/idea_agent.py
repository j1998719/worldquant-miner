"""
Idea Agent - Generate alpha trading hypotheses
Uses Ollama LLM to create financially sound alpha ideas
"""

import aiohttp
from typing import List, Dict
from datetime import datetime

from base_agent import BaseAgent


class IdeaAgent(BaseAgent):
    """
    Agent for generating alpha trading hypotheses
    Can generate ideas from scratch or expand existing ideas with variants
    """

    def __init__(self, config: Dict):
        """
        Initialize idea agent

        Args:
            config: Configuration dict
        """
        super().__init__('idea_agent', config)

        self.ollama_url = config.get('ollama_url', 'https://ollama.com')
        self.ollama_model = config.get('cloud_model', 'gpt-oss:120b')
        self.ollama_api_key = config.get('ollama_api_key', '')

        self.temperature = config.get('idea_agent', {}).get('temperature', 0.8)
        self.max_retries = config.get('idea_agent', {}).get('max_retries', 3)

    async def run(self, num_ideas: int, context: Dict = None) -> List[Dict]:
        """
        Generate alpha ideas

        Args:
            num_ideas: Number of ideas to generate
            context: Optional context (hopeful_alphas, rejected_alphas)

        Returns:
            List of idea dicts
        """
        start_time = datetime.now()
        self.logger.info(f"Generating {num_ideas} alpha ideas")

        # Load prompt template
        prompt_template = self.load_prompt('idea_generation.txt')
        if not prompt_template:
            self.logger.error("Prompt template not found, using fallback")
            prompt_template = self._get_fallback_prompt()

        # Build context section
        context_text = self._build_context(context or {})

        # Generate ideas
        ideas = []
        for i in range(num_ideas):
            idea = await self._generate_single_idea(prompt_template, context_text, i)
            if idea:
                ideas.append(idea)

        self.log_execution_time(start_time, f"Idea generation ({len(ideas)} ideas)")
        return ideas

    async def expand_ideas(self, ideas: List[Dict], variants_per_idea: int = 3) -> List[Dict]:
        """
        Expand ideas into multiple variants with batch parallelization

        Args:
            ideas: List of base ideas
            variants_per_idea: Number of variants per idea

        Returns:
            List of expanded idea dicts
        """
        start_time = datetime.now()
        self.logger.info(f"Expanding {len(ideas)} ideas into {variants_per_idea} variants each")

        all_variants = []

        # Process in parallel batches to avoid overwhelming the API
        batch_size = 10  # Process 10 ideas concurrently
        total_batches = (len(ideas) + batch_size - 1) // batch_size

        for batch_num in range(total_batches):
            batch_start = batch_num * batch_size
            batch_end = min(batch_start + batch_size, len(ideas))
            batch_ideas = ideas[batch_start:batch_end]

            self.logger.info(f"Processing batch {batch_num + 1}/{total_batches} ({len(batch_ideas)} ideas)")

            # Run expansion for all ideas in this batch concurrently
            tasks = [self._expand_single_idea(idea, variants_per_idea) for idea in batch_ideas]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Collect results, handling any exceptions
            for idea, result in zip(batch_ideas, batch_results):
                if isinstance(result, Exception):
                    self.logger.error(f"Failed to expand {idea.get('idea_id')}: {result}")
                    all_variants.append(idea)  # Add original if expansion failed
                else:
                    all_variants.extend(result)

            # Small delay between batches to avoid rate limiting
            if batch_num < total_batches - 1:
                await asyncio.sleep(1)

        self.log_execution_time(start_time, f"Idea expansion ({len(all_variants)} total)")
        self.logger.info(f"Expanded {len(ideas)} ideas to {len(all_variants)} total ideas/variants")
        return all_variants

    def _build_context(self, context: Dict) -> str:
        """Build context section for prompt"""
        hopeful = context.get('hopeful_alphas', [])
        rejected = context.get('rejected_alphas', [])

        context_parts = []

        if hopeful:
            context_parts.append("**Successful Alpha Patterns** (avoid simple replication):")
            for alpha in hopeful[:5]:
                context_parts.append(f"- {alpha.get('hypothesis', alpha.get('expression', ''))[:100]}")

        if rejected:
            context_parts.append("\n**Avoid These Patterns** (recently rejected):")
            for alpha in rejected[:5]:
                reason = alpha.get('reason', 'Poor performance')
                context_parts.append(f"- {alpha.get('hypothesis', '')} [Rejected: {reason}]")

        return "\n".join(context_parts) if context_parts else "No historical context available."

    async def _generate_single_idea(self, template: str, context: str, index: int) -> Dict:
        """Generate a single alpha idea"""
        # Replace context placeholder
        prompt = template.replace('{CONTEXT}', context)

        for attempt in range(self.max_retries):
            try:
                response = await self._call_ollama(prompt, self.temperature)
                idea = self._parse_idea_response(response, index)
                if idea:
                    return idea
            except Exception as e:
                self.logger.warning(f"Idea generation attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)

        self.logger.error(f"Failed to generate idea after {self.max_retries} attempts")
        return None

    def _parse_idea_response(self, response: str, index: int) -> Dict:
        """Parse Ollama response into structured idea dict"""
        import re

        # Extract hypothesis
        hypothesis_match = re.search(r'HYPOTHESIS:\s*(.+?)(?:\n|$)', response, re.IGNORECASE)
        rationale_match = re.search(r'RATIONALE:\s*(.+?)(?:\n\n|DATASETS:|$)', response, re.IGNORECASE | re.DOTALL)
        datasets_match = re.search(r'DATASETS:\s*(.+?)(?:\n|$)', response, re.IGNORECASE)

        if not hypothesis_match:
            self.logger.warning("Could not parse hypothesis from response")
            return None

        hypothesis = hypothesis_match.group(1).strip()
        rationale = rationale_match.group(1).strip() if rationale_match else ""
        datasets_str = datasets_match.group(1).strip() if datasets_match else "pv1"

        # Parse datasets
        datasets = [ds.strip() for ds in datasets_str.split(',')]

        idea = {
            'idea_id': self.generate_id('idea', index),
            'hypothesis': hypothesis,
            'rationale': rationale,
            'datasets': datasets,
            'source': 'generated',
            'source_url': None,
            'timestamp': self.get_timestamp(),
            'parent_idea_id': None
        }

        return idea

    async def _expand_single_idea(self, idea: Dict, num_variants: int) -> List[Dict]:
        """
        Expand a single idea into variants using JSON structured output

        Args:
            idea: Base idea dict
            num_variants: Number of variants to create

        Returns:
            List of variant idea dicts
        """
        prompt = f"""You are an expert alpha researcher. Create {num_variants} variations of this alpha hypothesis.

<original_idea>
Hypothesis: {idea['hypothesis']}
Rationale: {idea['rationale']}
Datasets: {', '.join(idea['datasets'])}
</original_idea>

Create {num_variants} distinct variants by modifying:
1. Time horizons (daily → weekly, short-term → long-term)
2. Cross-sectional vs time-series approaches
3. Normalization methods (rank, zscore, scale)
4. Filtering criteria (market cap, liquidity, sector)
5. Combination with other simple factors

CRITICAL: Respond with valid JSON only. No preamble, no explanation, just the JSON array.

Output format (respond with this exact structure):
[
  {{
    "hypothesis": "Modified hypothesis for variant 1",
    "rationale": "Explanation of what changed and why",
    "datasets": ["fundamental6", "pv1"]
  }},
  {{
    "hypothesis": "Modified hypothesis for variant 2",
    "rationale": "Explanation of what changed and why",
    "datasets": ["pv1"]
  }},
  {{
    "hypothesis": "Modified hypothesis for variant 3",
    "rationale": "Explanation of what changed and why",
    "datasets": ["fundamental6", "pv1"]
  }}
]

Generate {num_variants} variants now as JSON array:"""

        try:
            response = await self._call_ollama(prompt, temperature=0.75)

            # Debug: Save raw response
            self._save_debug_response(response, idea.get('idea_id', 'unknown'))

            variants = self._parse_variants_response(response, idea)
            return variants
        except Exception as e:
            self.logger.error(f"Failed to expand idea {idea.get('idea_id')}: {e}")
            return [idea]  # Return original if expansion fails

    def _parse_variants_response(self, response: str, parent_idea: Dict) -> List[Dict]:
        """Parse variant response with JSON-first approach and flexible fallback"""
        import re
        import json

        variants = []

        # Strategy 1: Try direct JSON parsing
        try:
            data = json.loads(response)
            if isinstance(data, list):
                variants = self._convert_json_to_variants(data, parent_idea)
                if variants:
                    self.logger.debug(f"Successfully parsed {len(variants)} variants via direct JSON")
                    return variants
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract JSON from markdown code block
        json_match = re.search(r'```(?:json)?\s*(\[.+?\])\s*```', response, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, list):
                    variants = self._convert_json_to_variants(data, parent_idea)
                    if variants:
                        self.logger.debug(f"Successfully parsed {len(variants)} variants from code block")
                        return variants
            except json.JSONDecodeError:
                pass

        # Strategy 3: Look for JSON array anywhere in response
        json_array_match = re.search(r'\[[\s\S]*?\{[\s\S]*?"hypothesis"[\s\S]*?\}[\s\S]*?\]', response)
        if json_array_match:
            try:
                data = json.loads(json_array_match.group(0))
                if isinstance(data, list):
                    variants = self._convert_json_to_variants(data, parent_idea)
                    if variants:
                        self.logger.debug(f"Successfully parsed {len(variants)} variants from embedded JSON")
                        return variants
            except json.JSONDecodeError:
                pass

        # Strategy 4: Fallback to legacy text parsing (VARIANT 1: format)
        variant_blocks = re.split(r'VARIANT\s+\d+:', response)
        for i, block in enumerate(variant_blocks[1:], 1):
            hypothesis_match = re.search(r'HYPOTHESIS:\s*(.+?)(?:\n|$)', block, re.IGNORECASE)
            rationale_match = re.search(r'RATIONALE:\s*(.+?)(?:\n\n|DATASETS:|$)', block, re.IGNORECASE | re.DOTALL)
            datasets_match = re.search(r'DATASETS:\s*(.+?)(?:\n|$)', block, re.IGNORECASE)

            if hypothesis_match:
                hypothesis = hypothesis_match.group(1).strip()
                rationale = rationale_match.group(1).strip() if rationale_match else ""
                datasets_str = datasets_match.group(1).strip() if datasets_match else ', '.join(parent_idea['datasets'])
                datasets = [ds.strip() for ds in datasets_str.split(',')]

                variant = {
                    'idea_id': f"{parent_idea['idea_id']}_var{i}",
                    'hypothesis': hypothesis,
                    'rationale': rationale,
                    'datasets': datasets,
                    'source': f"variant_of_{parent_idea['idea_id']}",
                    'source_url': parent_idea.get('source_url'),
                    'timestamp': self.get_timestamp(),
                    'parent_idea_id': parent_idea['idea_id']
                }
                variants.append(variant)

        if variants:
            self.logger.debug(f"Parsed {len(variants)} variants via legacy text parsing")
            return variants

        # All strategies failed
        self.logger.warning("Could not parse any variants with any strategy, returning original idea")
        return [parent_idea]

    def _convert_json_to_variants(self, json_data: list, parent_idea: Dict) -> List[Dict]:
        """Convert JSON array to variant idea dicts"""
        variants = []
        for i, item in enumerate(json_data, 1):
            if not isinstance(item, dict):
                continue

            hypothesis = item.get('hypothesis', '').strip()
            if not hypothesis:
                continue

            rationale = item.get('rationale', '').strip()
            datasets_raw = item.get('datasets', parent_idea.get('datasets', ['pv1']))

            # Handle datasets: can be array or comma-separated string
            if isinstance(datasets_raw, list):
                datasets = [str(d).strip() for d in datasets_raw if d]
            elif isinstance(datasets_raw, str):
                datasets = [d.strip() for d in datasets_raw.split(',') if d.strip()]
            else:
                datasets = parent_idea.get('datasets', ['pv1'])

            variant = {
                'idea_id': f"{parent_idea['idea_id']}_var{i}",
                'hypothesis': hypothesis,
                'rationale': rationale,
                'datasets': datasets,
                'source': f"variant_of_{parent_idea['idea_id']}",
                'source_url': parent_idea.get('source_url'),
                'timestamp': self.get_timestamp(),
                'parent_idea_id': parent_idea['idea_id']
            }
            variants.append(variant)

        return variants

    def _save_debug_response(self, response: str, idea_id: str):
        """Save raw LLM response for debugging"""
        from pathlib import Path

        debug_dir = Path('logs/debug_responses')
        debug_dir.mkdir(parents=True, exist_ok=True)

        debug_file = debug_dir / f"{idea_id}_{self.get_timestamp()}.txt"

        try:
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(f"Idea ID: {idea_id}\n")
                f.write(f"Timestamp: {self.get_timestamp()}\n")
                f.write("="*80 + "\n")
                f.write(response)
            self.logger.debug(f"Saved debug response to {debug_file}")
        except Exception as e:
            self.logger.warning(f"Failed to save debug response: {e}")

    async def _call_ollama(self, prompt: str, temperature: float) -> str:
        """Call Ollama Cloud API"""
        url = f"{self.ollama_url}/api/chat"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.ollama_api_key}"
        }
        payload = {
            "model": self.ollama_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers, timeout=90) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Ollama API error {response.status}: {error_text}")

                result = await response.json()
                return result['message']['content']

    def _get_fallback_prompt(self) -> str:
        """Fallback prompt if template file not found"""
        return """You are a quantitative trading expert. Generate ONE creative alpha trading hypothesis.

{CONTEXT}

GUIDELINES:
1. Base on financial logic (momentum, mean reversion, value, quality, etc.)
2. Use available data: price, volume, fundamental, market data
3. Target market inefficiencies
4. Be original - avoid simple replications
5. Ensure implementability

OUTPUT FORMAT:
HYPOTHESIS: [One clear sentence describing the trading signal]
RATIONALE: [2-3 sentences explaining the financial logic]
DATASETS: [Comma-separated list, e.g., fundamental6, pv1]

Generate your hypothesis now:"""


# Add asyncio import at top of file
import asyncio
