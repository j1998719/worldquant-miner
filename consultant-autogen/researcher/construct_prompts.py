"""
construct_prompts.py - Prompt builders for LLM
"""
import json
from pathlib import Path


def build_check_if_blog_helpful(post_file):
    """
    Construct prompt to check if a blog post is helpful for alpha research
    
    Args:
        post_file: Path to the processed post JSON file
    
    Returns:
        List of message dicts for LLM
    """
    # Read the post content
    with open(post_file, 'r', encoding='utf-8') as f:
        post_data = json.load(f)
    
    title = post_data.get('title', '')
    description = post_data.get('description', '')
    post_body = post_data.get('post_body', '')
    
    # Construct the prompt
    system_prompt = """You are an expert in quantitative finance and alpha factor research.
Your task is to determine if a WorldQuant community post contains useful information for alpha factor mining.

A helpful post should contain:
- Specific alpha factor ideas or expressions
- Technical discussions about factor construction
- Mathematical formulas or data operations
- Trading strategies or signal generation methods
- Performance analysis or backtesting insights
- Code examples or implementation details

A post is NOT helpful if it only contains:
- General questions without technical content
- Administrative/account issues
- Simple greetings or thank you messages
- Off-topic discussions

Please analyze the post and answer with ONLY "YES" or "NO" (one word).
Answer "YES" if the post is helpful for alpha research.
Answer "NO" if the post is not helpful.
"""

    user_prompt = f"""Post Title: {title}

Post Description: {description}

Post Body:
{post_body[:2000]}  

Is this post helpful for alpha factor research? Answer YES or NO only."""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

