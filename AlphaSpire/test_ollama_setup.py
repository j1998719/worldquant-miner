#!/usr/bin/env python3
"""
测试 Ollama 配置是否正确
"""

import requests
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from utils.config_loader import ConfigLoader


def test_config():
    """测试配置文件"""
    print("1️⃣  测试配置文件...")
    try:
        ollama_url = ConfigLoader.get("ollama_url")
        ollama_model = ConfigLoader.get("ollama_model")
        
        print(f"   ✅ Ollama URL: {ollama_url}")
        print(f"   ✅ Ollama Model: {ollama_model}")
        return ollama_url, ollama_model
    except Exception as e:
        print(f"   ❌ 配置文件读取失败: {e}")
        return None, None


def test_ollama_connection(ollama_url):
    """测试 Ollama 连接"""
    print("\n2️⃣  测试 Ollama 连接...")
    try:
        response = requests.get(f"{ollama_url}/api/version", timeout=5)
        if response.status_code == 200:
            version = response.json().get('version', 'Unknown')
            print(f"   ✅ Ollama 运行中 (版本: {version})")
            return True
        else:
            print(f"   ❌ Ollama 响应异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ 无法连接到 Ollama: {e}")
        print(f"   💡 提示: 确保 Ollama 正在运行 (ollama serve)")
        return False


def test_model_available(ollama_url, model):
    """测试模型是否可用"""
    print(f"\n3️⃣  测试模型 {model} 是否可用...")
    try:
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            model_names = [m.get('name') for m in models]
            
            if model in model_names:
                print(f"   ✅ 模型 {model} 已安装")
                return True
            else:
                print(f"   ❌ 模型 {model} 未找到")
                print(f"   💡 可用模型: {', '.join(model_names)}")
                print(f"   💡 安装命令: ollama pull {model}")
                return False
        else:
            print(f"   ❌ 获取模型列表失败: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ 检查模型失败: {e}")
        return False


def test_ollama_inference(ollama_url, model):
    """测试 Ollama 推理"""
    print(f"\n4️⃣  测试 Ollama 推理...")
    
    test_prompt = "Say 'Hello from Ollama' in one sentence."
    
    payload = {
        "model": model,
        "prompt": test_prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 50
        }
    }
    
    try:
        print(f"   🔄 发送测试请求...")
        response = requests.post(
            f"{ollama_url}/api/generate",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            response_text = result.get('response', '').strip()
            
            if response_text:
                print(f"   ✅ 推理成功")
                print(f"   💬 响应: {response_text[:100]}")
                return True
            else:
                print(f"   ⚠️  推理成功但返回为空")
                return False
        else:
            print(f"   ❌ 推理失败: {response.status_code}")
            print(f"   {response.text[:200]}")
            return False
    except Exception as e:
        print(f"   ❌ 推理测试失败: {e}")
        return False


def test_helpful_posts_exist():
    """测试 helpful_posts 目录是否存在"""
    print(f"\n5️⃣  测试 helpful_posts 数据...")
    
    posts_dir = Path("data/wq_posts/helpful_posts")
    
    if not posts_dir.exists():
        print(f"   ❌ 目录不存在: {posts_dir}")
        print(f"   💡 提示: 先运行爬虫获取数据")
        return False
    
    post_files = list(posts_dir.glob("*.json"))
    
    if not post_files:
        print(f"   ❌ 目录为空: {posts_dir}")
        print(f"   💡 提示: 先运行爬虫获取数据")
        return False
    
    print(f"   ✅ 找到 {len(post_files)} 个帖子文件")
    return True


def main():
    print("="*60)
    print("AlphaSpire Ollama 配置测试")
    print("="*60)
    
    # 测试 1: 配置文件
    ollama_url, ollama_model = test_config()
    if not ollama_url or not ollama_model:
        print("\n❌ 测试失败: 配置文件有问题")
        return 1
    
    # 测试 2: Ollama 连接
    if not test_ollama_connection(ollama_url):
        print("\n❌ 测试失败: 无法连接到 Ollama")
        return 1
    
    # 测试 3: 模型可用性
    if not test_model_available(ollama_url, ollama_model):
        print("\n❌ 测试失败: 模型不可用")
        return 1
    
    # 测试 4: 推理测试
    if not test_ollama_inference(ollama_url, ollama_model):
        print("\n❌ 测试失败: 推理测试失败")
        return 1
    
    # 测试 5: 数据检查
    if not test_helpful_posts_exist():
        print("\n⚠️  警告: 没有 helpful_posts 数据")
    
    print("\n" + "="*60)
    print("✅ 所有测试通过！配置正确，可以运行 main.py")
    print("="*60)
    
    return 0


if __name__ == "__main__":
    exit(main())

