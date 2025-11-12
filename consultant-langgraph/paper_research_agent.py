"""
Paper Research Agent - Parallel search across academic databases
Uses Ollama for query generation and paper analysis
"""

import asyncio
import aiohttp
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
from datetime import datetime

from base_agent import BaseAgent


class PaperResearchAgent(BaseAgent):
    """
    Agent for searching and analyzing academic papers
    Searches arXiv, SSRN, and Google Scholar in parallel
    Uses Ollama LLM for intelligent query generation and idea extraction
    """

    def __init__(self, config: Dict):
        """
        Initialize paper research agent

        Args:
            config: Configuration dict with ollama_url, cloud_model, etc.
        """
        super().__init__('paper_research', config)

        self.ollama_url = config.get('ollama_url', 'https://ollama.com')
        self.ollama_model = config.get('cloud_model', 'gpt-oss:120b')
        self.ollama_api_key = config.get('ollama_api_key', '')

        self.max_papers_per_source = config.get('max_papers_per_source', 10)
        self.temperature = config.get('paper_research', {}).get('temperature', 0.7)

    async def run(self, topic: str, keywords: List[str]) -> Dict:
        """
        Main execution: search papers and extract alpha ideas

        Args:
            topic: Research topic (e.g., "momentum")
            keywords: Additional keywords

        Returns:
            Dict with 'papers' and 'ideas' keys
        """
        start_time = datetime.now()
        self.logger.info(f"Starting paper research: topic='{topic}', keywords={keywords}")

        # Step 1: Generate optimized search queries using Ollama
        search_queries = await self._generate_search_queries(topic, keywords)
        self.logger.info(f"Generated {len(search_queries)} search queries")

        # Step 2: Parallel search across multiple sources
        papers = await self._parallel_search(search_queries)
        self.logger.info(f"Found {len(papers)} total papers")

        # Step 3: Extract alpha ideas from papers
        ideas = await self._extract_ideas_from_papers(papers, topic)
        self.logger.info(f"Extracted {len(ideas)} alpha ideas")

        self.log_execution_time(start_time, "Paper research")

        return {
            'papers': papers,
            'ideas': ideas
        }

    async def _generate_search_queries(self, topic: str, keywords: List[str]) -> List[Dict]:
        """
        Use Ollama to generate optimized search queries

        Args:
            topic: Research topic
            keywords: Additional keywords

        Returns:
            List of query dicts with 'query' and 'rationale'
        """
        prompt = f"""You are a quantitative finance research expert. Generate 5-7 optimized search queries to find academic papers about {topic} alpha strategies.

Topic: {topic}
Additional keywords: {', '.join(keywords) if keywords else 'None'}

Your queries should cover:
1. Direct research on {topic} anomalies and factors
2. Methodological papers (statistical methods, machine learning)
3. Empirical studies and market microstructure
4. Behavioral finance aspects
5. Recent developments (2020-2025)

Output ONLY a JSON array with this structure:
[
  {{"query": "momentum anomaly cross-sectional equity", "rationale": "Find cross-sectional momentum research"}},
  {{"query": "{topic} factor machine learning prediction", "rationale": "Find ML applications"}},
  ...
]

Generate the queries now:"""

        try:
            response = await self._call_ollama(prompt, temperature=0.7)
            import json
            # Extract JSON from response
            response_text = response.strip()
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()

            queries = json.loads(response_text)
            return queries
        except Exception as e:
            self.logger.error(f"Failed to generate search queries: {e}")
            # Fallback to simple queries
            return [
                {"query": f"{topic} anomaly", "rationale": "Basic anomaly search"},
                {"query": f"{topic} factor investing", "rationale": "Factor research"},
                {"query": f"{topic} trading strategy", "rationale": "Trading strategies"}
            ]

    async def _parallel_search(self, queries: List[Dict]) -> List[Dict]:
        """
        Search papers in parallel across multiple sources

        Args:
            queries: List of search query dicts

        Returns:
            Combined list of paper dicts
        """
        tasks = []

        # Create search tasks for each source
        for query_obj in queries[:3]:  # Limit to 3 queries to avoid rate limiting
            query = query_obj['query']
            tasks.append(self._search_arxiv(query))
            # Note: SSRN and Google Scholar require additional setup
            # For now, focusing on arXiv which has a public API

        # Execute all searches in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Combine and deduplicate papers
        all_papers = []
        seen_titles = set()

        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Search failed: {result}")
                continue

            for paper in result:
                title_lower = paper['title'].lower().strip()
                if title_lower not in seen_titles:
                    seen_titles.add(title_lower)
                    all_papers.append(paper)

        return all_papers[:self.max_papers_per_source * 3]

    async def _search_arxiv(self, query: str) -> List[Dict]:
        """
        Search arXiv using their API

        Args:
            query: Search query string

        Returns:
            List of paper dicts
        """
        base_url = "http://export.arxiv.org/api/query"
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": self.max_papers_per_source,
            "sortBy": "relevance",
            "sortOrder": "descending"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(base_url, params=params, timeout=30) as response:
                    xml_data = await response.text()

            # Parse XML
            root = ET.fromstring(xml_data)
            namespace = {'atom': 'http://www.w3.org/2005/Atom'}

            papers = []
            for entry in root.findall('atom:entry', namespace):
                title_elem = entry.find('atom:title', namespace)
                summary_elem = entry.find('atom:summary', namespace)
                id_elem = entry.find('atom:id', namespace)
                published_elem = entry.find('atom:published', namespace)

                if title_elem is None or summary_elem is None:
                    continue

                paper = {
                    'title': title_elem.text.strip().replace('\n', ' '),
                    'authors': [author.find('atom:name', namespace).text
                               for author in entry.findall('atom:author', namespace)],
                    'abstract': summary_elem.text.strip().replace('\n', ' '),
                    'url': id_elem.text if id_elem is not None else '',
                    'published_date': published_elem.text if published_elem is not None else '',
                    'source': 'arxiv'
                }
                papers.append(paper)

            self.logger.debug(f"arXiv search '{query}' returned {len(papers)} papers")
            return papers

        except Exception as e:
            self.logger.error(f"arXiv search failed for '{query}': {e}")
            return []

    async def _extract_ideas_from_papers(self, papers: List[Dict], topic: str) -> List[Dict]:
        """
        Extract alpha ideas from papers using Ollama

        Args:
            papers: List of paper dicts
            topic: Research topic for context

        Returns:
            List of alpha idea dicts
        """
        # Process papers in parallel (batches of 5 to avoid overwhelming the API)
        batch_size = 5
        all_ideas = []

        for i in range(0, len(papers), batch_size):
            batch = papers[i:i+batch_size]
            tasks = [self._extract_ideas_from_single_paper(paper, topic) for paper in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    self.logger.error(f"Idea extraction failed: {result}")
                    continue
                all_ideas.extend(result)

        return all_ideas

    async def _extract_ideas_from_single_paper(self, paper: Dict, topic: str) -> List[Dict]:
        """
        Extract alpha ideas from a single paper

        Args:
            paper: Paper dict with title, abstract, etc.
            topic: Research topic

        Returns:
            List of idea dicts
        """
        prompt = f"""You are a quantitative finance expert specializing in alpha strategy development.

Paper Title: {paper['title']}
Authors: {', '.join(paper['authors'][:5])}
Abstract: {paper['abstract'][:1500]}...

Topic of Interest: {topic}

Task: Extract 1-3 actionable alpha ideas from this paper that can be implemented using price, volume, and fundamental data.

For each idea, provide:

Output as JSON array:
[
  {{
    "hypothesis": "Clear one-sentence trading signal description",
    "rationale": "2-3 sentences explaining the financial logic and why it might be profitable",
    "datasets": ["pv1", "fundamental6"],
    "source_paper": "{paper['title']}"
  }}
]

Requirements:
- Only extract ideas that use publicly available data (price, volume, fundamentals)
- Ensure no look-ahead bias
- Focus on implementable quantitative signals
- If the paper doesn't contain implementable ideas, return []

Extract ideas now:"""

        try:
            response = await self._call_ollama(prompt, temperature=0.7)
            import json

            # Extract JSON
            response_text = response.strip()
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()

            ideas = json.loads(response_text)

            # Add metadata and generate IDs
            for i, idea in enumerate(ideas):
                idea['source_url'] = paper.get('url', '')
                idea['timestamp'] = datetime.now().isoformat()
                idea['source'] = 'paper_research'
                idea['parent_idea_id'] = None
                # Generate unique ID based on paper title and index
                paper_slug = paper['title'][:30].replace(' ', '_').replace('/', '_')
                idea['idea_id'] = self.generate_id(f'paper_{paper_slug}', i)

            self.logger.debug(f"Extracted {len(ideas)} ideas from: {paper['title'][:50]}...")
            return ideas

        except Exception as e:
            error_str = str(e)
            self.logger.error(f"Failed to extract ideas from paper: {e}")

            # Check for API rate limit (429 error)
            if "429" in error_str or "usage limit" in error_str.lower():
                self.logger.error("API rate limit reached. Exiting to avoid long wait times.")
                self.logger.error("Please wait for the API limit to reset or upgrade your plan.")
                import sys
                sys.exit(1)

            return []

    async def _call_ollama(self, prompt: str, temperature: float = 0.7) -> str:
        """
        Call Ollama Cloud API

        Args:
            prompt: Prompt string
            temperature: Sampling temperature

        Returns:
            Response text
        """
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

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=60) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Ollama API error {response.status}: {error_text}")

                    result = await response.json()
                    return result['message']['content']

        except Exception as e:
            self.logger.error(f"Ollama API call failed: {e}")
            raise
