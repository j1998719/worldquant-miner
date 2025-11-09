# 🚀 AlphaSpire 快速启动指南 (Ollama 版)

## ✅ 当前状态

```
✅ 配置文件已修改（使用 Ollama）
✅ 代码已更新（移除 LangChain）
✅ Ollama 连接正常
✅ gemma3:1b 模型可用
✅ helpful_posts 数据就绪（26 个帖子）
```

## 📊 项目流程

```
helpful_posts/ (26 个帖子) ← 已完成
    ↓
生成假设 (Hypothesis)        ← 使用 Ollama gemma3:1b
    ↓
生成模板 (Template)          ← 使用 Ollama gemma3:1b
    ↓
生成 Alpha 表达式
    ↓
回测评估                     ← 使用 WorldQuant API
```

## 🎯 运行方式

### 方式 1: 运行完整流程（推荐）

```bash
cd /Users/chiao-yuyang/Desktop/worldquant-miner/AlphaSpire
python main.py
```

**这会：**
1. 加载 WorldQuant 组件（operators, fields）
2. 从 26 个 helpful_posts 生成模板
3. 从模板生成 Alpha 表达式
4. 回测所有生成的 Alpha

**预计时间：** 
- 每个帖子处理：2-5 分钟（取决于 Ollama 速度）
- 26 个帖子：~1-2 小时
- 回测：取决于生成的 Alpha 数量

### 方式 2: 只运行研究部分

```bash
python main_researcher.py
```

**这会：**
- 只生成模板和 Alpha 表达式
- 不进行回测

### 方式 3: 只运行评估部分

```bash
python main_evaluator.py
```

**这会：**
- 对已生成的 Alpha 进行回测

## 📁 输出文件位置

```
AlphaSpire/
├── data/
│   ├── wq_posts/
│   │   └── helpful_posts/              ← 输入（26 个帖子）
│   │
│   ├── hypothesis_db_v2/               ← Ollama 生成的假设
│   │   └── *_hypotheses.json
│   │
│   ├── template_db_v2/                 ← Ollama 生成的模板
│   │   └── *_template.json
│   │
│   └── alpha_db_v2/
│       └── all_alphas/                 ← 最终的 Alpha 表达式
│           └── *_alphas.json
```

## 🔍 监控进度

### 查看生成的假设
```bash
ls -lh data/hypothesis_db_v2/
```

### 查看生成的模板
```bash
ls -lh data/template_db_v2/
```

### 查看生成的 Alpha
```bash
ls -lh data/alpha_db_v2/all_alphas/
```

### 查看日志
```bash
tail -f adaptive_alpha_miner.log  # 如果运行 adaptive_alpha_miner
```

## ⚙️ 调优建议

### 如果处理太慢

**选项 1: 使用更小的模型**
```yaml
# config.yaml
ollama_model: "gemma3:1b"  # 最快
# ollama_model: "qwen3-vl:4b"  # 中速
# ollama_model: "deepseek-r1:8b"  # 最慢但质量最好
```

**选项 2: 减少 num_predict**
```python
# researcher/generate_template.py, line ~45
"num_predict": 1000  # 改为更小的值，如 1000
```

**选项 3: 只处理部分帖子**
```python
# main.py, 修改为：
for json_file in list(post_files)[:5]:  # 只处理前 5 个
```

### 如果质量不够好

**选项 1: 使用更好的模型**
```yaml
# config.yaml
ollama_model: "qwen3-vl:4b"  # 或 "deepseek-r1:8b"
```

**选项 2: 调整温度**
```python
# researcher/generate_template.py
"temperature": 0.1,  # 更低 = 更确定，更高 = 更创造性
```

## 🐛 常见问题

### 1. JSON 解析失败
```
❌ Hypotheses output not valid JSON
```
**解决：** 代码已包含 JSON 提取和修复逻辑，会自动重试

### 2. Ollama 超时
```
⏱️ Ollama 请求超时
```
**解决：** 
- 增加 timeout（在 `generate_template.py`）
- 或使用更快的模型

### 3. 模板已存在
```
✅ Template already exists, skipping
```
**说明：** 这是正常的，避免重复处理

**如果想重新处理：**
```bash
rm -rf data/hypothesis_db_v2/*
rm -rf data/template_db_v2/*
```

## 📈 预期结果

### 成功的输出示例

```
找到 26 个有用的帖子

处理: 20251109_223041_19137620283415.json
============================================================
📄 处理帖子: data/wq_posts/helpful_posts/20251109_223041_19137620283415.json
============================================================
🤖 调用 Ollama 模型: gemma3:1b
⏱️  Ollama 响应时间: 3.45s
✅ Hypotheses saved: data/hypothesis_db_v2/20251109_223041_19137620283415_hypotheses.json
🤖 调用 Ollama 模型: gemma3:1b
⏱️  Ollama 响应时间: 4.21s
✅ Template saved: data/template_db_v2/20251109_223041_19137620283415_hypotheses_template.json
🎯 完成: 从 data/wq_posts/helpful_posts/20251109_223041_19137620283415.json 成功生成模板
✅ Generated 150 alphas saved to data/alpha_db_v2/all_alphas/20251109_223041_19137620283415_hypotheses_template_alphas.json
✅ Alpha 表达式已生成
```

## 🎓 理解模板示例

一个典型的模板可能长这样：

```json
{
  "TemplateExpression": "ts_rank(</operator:ts_operator/>...</value:FUNDAMENTAL:fundamental6/>, 60), 120)",
  "Hypothesis": "使用基本面数据的时间序列排名..."
}
```

- `</operator:ts_operator/>` - 会被替换为 ts_delta, ts_mean 等
- `</value:FUNDAMENTAL:fundamental6/>` - 会被替换为具体的基本面字段
- 一个模板可以生成几十到几百个具体的 Alpha 表达式

## 🎯 下一步

1. ✅ 运行 `python main.py`
2. ✅ 等待处理完成（1-2 小时）
3. ✅ 查看生成的 Alpha
4. ✅ 分析回测结果
5. ✅ 根据结果调整参数

## 📞 需要帮助？

查看详细文档：
- `README_OLLAMA.md` - 完整的修改说明
- `test_ollama_setup.py` - 测试配置
- `config.yaml` - 配置文件

---

**Good luck! 🚀**

