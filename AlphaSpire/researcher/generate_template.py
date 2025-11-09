import random
import json
import requests
import time
from pathlib import Path

from researcher.construct_prompts import (
    build_wq_knowledge_prompt, 
    build_blog_to_hypothesis, 
    build_hypothesis_to_template, 
    build_check_if_blog_helpful
)
from utils.config_loader import ConfigLoader
from utils.json_dealer import extract_json

# --- 路径 ---
BASE_DIR = Path(__file__).resolve().parents[1]
POSTS_DIR = BASE_DIR / "data" / "wq_posts" / "helpful_posts"
HYPOTHESIS_DB = BASE_DIR / "data" / "hypothesis_db_v2"
TEMPLATE_DB = BASE_DIR / "data" / "template_db_v2"

HYPOTHESIS_DB.mkdir(parents=True, exist_ok=True)
TEMPLATE_DB.mkdir(parents=True, exist_ok=True)


# === Ollama LLM 调用 ===
def call_ollama_llm(prompt: str, timeout: int = 120) -> str:
    """
    调用本地 Ollama 模型（参考 adaptive_alpha_miner.py）
    
    Args:
        prompt: 提示词（包含 system + user 内容）
        timeout: 超时时间（秒）
    
    Returns:
        模型的响应文本
    """
    ollama_url = ConfigLoader.get("ollama_url")
    model = ConfigLoader.get("ollama_model")
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 2000
        }
    }
    
    try:
        print(f"🤖 调用 Ollama 模型: {model}")
        start_time = time.time()
        
        response = requests.post(
            f"{ollama_url}/api/generate", 
            json=payload, 
            timeout=timeout
        )
        
        elapsed_time = time.time() - start_time
        print(f"⏱️  Ollama 响应时间: {elapsed_time:.2f}s")
        
        if response.status_code == 200:
            result = response.json()
            response_text = result.get('response', '').strip()
            return response_text
        else:
            print(f"❌ Ollama API 错误: {response.status_code}")
            print(f"   {response.text[:200]}")
            return ""
            
    except requests.exceptions.Timeout:
        print(f"⏱️  Ollama 请求超时（{timeout}s）")
        return ""
    except Exception as e:
        print(f"❌ 调用 Ollama 失败: {e}")
        return ""


def init_system_prompt():
    """初始化系统提示词"""
    return build_wq_knowledge_prompt()


# === 随机选择有用的 Blog Post ===
def select_valid_post():
    post_files = list(POSTS_DIR.glob("*.json"))
    if not post_files:
        raise FileNotFoundError("❌ No blog post found in processed_posts folder")
    return random.choice(post_files)


def check_if_post_helpful(system_prompt: str, post_file) -> bool:
    """检查帖子是否有帮助"""
    # 构建用户 prompt（已经是字符串了）
    user_prompt = build_check_if_blog_helpful(post_file)
    
    # 构建完整 prompt
    full_prompt = f"System: {system_prompt}\n\nUser: {user_prompt}"
    
    # 调用 Ollama
    output = call_ollama_llm(full_prompt)
    
    return output.upper().startswith("Y") if output else False


# === 生成 Hypotheses ===
def generate_hypotheses(system_prompt: str, post_file):
    """从帖子生成假设"""
    user_prompt = build_blog_to_hypothesis(post_file)
    
    # 构建完整 prompt（已经是字符串了）
    full_prompt = f"System: {system_prompt}\n\nUser: {user_prompt}"
    
    # 调用 Ollama
    output = call_ollama_llm(full_prompt)
    
    if not output:
        raise ValueError(f"❌ Ollama 返回空响应")

    try:
        hypotheses = extract_json(output)
    except Exception as e:
        print(f"❌ Hypotheses output not valid JSON: {output}")
        raise ValueError(f"❌ Failed to extract JSON: {e}")

    out_file = HYPOTHESIS_DB / f"{Path(post_file).stem}_hypotheses.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(hypotheses, f, indent=2, ensure_ascii=False)

    print(f"✅ Hypotheses saved: {out_file}")
    return out_file


# === 生成 Template ===
def generate_template(system_prompt: str, hypotheses_file):
    """从假设生成模板"""
    user_prompt = build_hypothesis_to_template(hypotheses_file)
    
    # 构建完整 prompt（已经是字符串了）
    full_prompt = f"System: {system_prompt}\n\nUser: {user_prompt}"
    
    # 调用 Ollama
    output = call_ollama_llm(full_prompt)
    
    if not output:
        print(f"❌ Ollama 返回空响应")
        return None

    try:
        template_json = extract_json(output)
    except Exception:
        print(f"❌ Template output not valid JSON: {output}")
        return None

    out_file = TEMPLATE_DB / f"{Path(hypotheses_file).stem}_template.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(template_json, f, indent=2, ensure_ascii=False)

    print(f"✅ Template saved: {out_file}")
    return out_file


# === 主流程 ===
def from_post_to_template(post_file: str = None):
    """
    从帖子到模板的完整流程
    
    Args:
        post_file: 帖子文件路径，如果为 None 则随机选择
    
    Returns:
        模板文件路径或 None
    """
    # 初始化系统提示词
    system_prompt = init_system_prompt()

    # Step 1: 选择 blog
    if post_file:
        post_stem = Path(post_file).stem
        existing_template = TEMPLATE_DB / f"{post_stem}_hypotheses_template.json"
        if existing_template.exists():
            print(f"✅ Template already exists for {post_file}, skipping.")
            return None
        blog_file = post_file
    else:
        blog_file = select_valid_post()

    print(f"\n{'='*60}")
    print(f"📄 处理帖子: {blog_file}")
    print(f"{'='*60}")

    # Step 2: 生成 Hypotheses
    try:
        hypotheses_file = generate_hypotheses(system_prompt, blog_file)
    except Exception as e:
        print(f"❌ 生成假设失败: {e}")
        return None

    # Step 3: 生成 Template
    try:
        template_file = generate_template(system_prompt, hypotheses_file)
    except Exception as e:
        print(f"❌ 生成模板失败: {e}")
        return None

    if template_file:
        print(f"🎯 完成: 从 {blog_file} 成功生成模板")
    
    return template_file


if __name__ == "__main__":
    from_post_to_template()
