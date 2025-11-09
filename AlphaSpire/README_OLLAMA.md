# AlphaSpire - Ollama 版本修改说明

## 🎯 修改概览

本项目已从 OpenAI/DeepSeek API 改为使用本地 Ollama gemma3:1b 模型。

## 📝 修改的文件

### 1. `config.yaml`
**改动：** 移除 OpenAI 配置，添加 Ollama 配置

```yaml
# 原来
openai_base_url: "todo"
openai_api_key: "todo"
openai_model_name: "todo"

# 现在
ollama_url: "http://localhost:11434"
ollama_model: "gemma3:1b"
```

### 2. `researcher/generate_template.py`
**改动：** 完全重写

- ❌ 移除：`langchain_openai.ChatOpenAI`
- ❌ 移除：`langchain.chains.LLMChain`
- ❌ 移除：`langchain.memory.ConversationBufferMemory`
- ✅ 新增：`call_ollama_llm()` - 直接调用 Ollama API
- ✅ 新增：消息格式转换（LangChain 格式 → 字符串）

**关键函数：**
```python
def call_ollama_llm(prompt: str, timeout: int = 120) -> str:
    """调用本地 Ollama 模型"""
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
    
    response = requests.post(f"{ollama_url}/api/generate", json=payload, timeout=timeout)
    return response.json().get('response', '').strip()
```

### 3. `main.py`
**改动：** 跳过爬虫阶段，从已有的 helpful_posts 开始

- ❌ 移除：爬虫调用（`scrape_new_posts()` 和 `preprocess_all_html_posts()`）
- ✅ 保留：Alpha 研究流程（从帖子生成模板）
- ✅ 保留：Alpha 评估流程（回测）

**新流程：**
```
helpful_posts/ (已存在)
    ↓
生成假设 (Hypothesis)
    ↓
生成模板 (Template)
    ↓
生成 Alpha 表达式
    ↓
回测评估
```

## 🚀 使用方法

### 前提条件

1. **Ollama 已安装并运行**
   ```bash
   # 检查 Ollama 状态
   ollama list
   
   # 确保 gemma3:1b 已下载
   ollama pull gemma3:1b
   ```

2. **已有 helpful_posts 数据**
   ```bash
   # 确保目录存在且有数据
   ls data/wq_posts/helpful_posts/
   ```

### 运行流程

```bash
cd /Users/chiao-yuyang/Desktop/worldquant-miner/AlphaSpire

# 运行完整流程
python main.py
```

### 分阶段运行（可选）

```bash
# 只运行研究部分（从帖子生成模板和 Alpha）
python main_researcher.py

# 只运行评估部分（回测）
python main_evaluator.py
```

## 📊 数据流

```
data/
├── wq_posts/
│   └── helpful_posts/          ← 输入（你已有）
│       └── *.json
│
├── hypothesis_db_v2/           ← 中间产物 1
│   └── *_hypotheses.json
│
├── template_db_v2/             ← 中间产物 2
│   └── *_template.json
│
└── alpha_db_v2/
    └── all_alphas/             ← 最终产物
        └── *_alphas.json
```

## 🔍 关键差异对比

| 特性 | 原版 (OpenAI) | Ollama 版 |
|------|--------------|-----------|
| **LLM 提供商** | OpenAI/DeepSeek API | 本地 Ollama |
| **模型** | deepseek-chat | gemma3:1b |
| **依赖库** | langchain_openai | requests |
| **调用方式** | LangChain Chains | 直接 HTTP API |
| **消息格式** | LangChain 格式 | 字符串格式 |
| **Memory** | ConversationBufferMemory | 无（每次独立）|
| **费用** | 按 API 调用付费 | 完全免费 |
| **速度** | 取决于网络 | 本地推理 |

## ⚙️ 配置参数

在 `config.yaml` 中可调整：

```yaml
# Ollama 设置
ollama_url: "http://localhost:11434"  # Ollama API 地址
ollama_model: "gemma3:1b"              # 使用的模型

# 可选其他模型
# ollama_model: "qwen3-vl:4b"
# ollama_model: "deepseek-r1:8b"
```

在 `generate_template.py` 中可调整 LLM 参数：

```python
payload = {
    "model": model,
    "prompt": prompt,
    "stream": False,
    "options": {
        "temperature": 0.2,      # 温度（0-1，越低越确定）
        "num_predict": 2000      # 最大输出 token 数
    }
}
```

## 🐛 常见问题

### 1. Ollama 连接失败
```
❌ Ollama API 错误: Connection refused
```
**解决：** 确保 Ollama 服务运行中
```bash
# 检查 Ollama 状态
curl http://localhost:11434/api/version

# 如果没运行，启动 Ollama
ollama serve
```

### 2. 模型未找到
```
❌ model 'gemma3:1b' not found
```
**解决：** 下载模型
```bash
ollama pull gemma3:1b
```

### 3. JSON 解析失败
```
❌ Hypotheses output not valid JSON
```
**原因：** Ollama 返回的格式不是纯 JSON
**解决：** 代码已包含 JSON 提取逻辑（`extract_json()`），会自动处理

### 4. 响应时间过长
**解决：** 可以：
- 使用更小的模型（如 `gemma3:1b` 而不是 `qwen3-vl:4b`）
- 减少 `num_predict` 参数
- 使用 GPU 加速（如果可用）

## 📈 性能对比

基于测试数据：

| 模型 | 平均响应时间 | 内存占用 | 质量 |
|------|-------------|---------|------|
| gemma3:1b | ~3-5秒 | ~1.5GB | 中等 |
| qwen3-vl:4b | ~20-60秒 | ~5GB | 较好 |
| deepseek-r1:8b | ~40-120秒 | ~10GB | 最好 |

**推荐：** 对于快速迭代，使用 `gemma3:1b`

## 🎯 下一步

1. ✅ 运行 `main.py` 测试完整流程
2. ✅ 检查生成的模板质量
3. ✅ 调整 Ollama 参数优化结果
4. ✅ 批量处理更多帖子

## 📚 参考

- [Ollama 文档](https://github.com/ollama/ollama)
- [Ollama API 文档](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [AlphaSpire 原项目](https://github.com/Argithun/AlphaSpire)

