# AlphaSpire - 智能 Alpha 挖掘系统

🤖 基于 Multi-Agent 架构的迭代式 Alpha 生成系统，持续优化直到找到高质量的 Alpha。

---

## 🚀 快速开始

### 1. 启动 Ollama（另开终端）
```bash
ollama serve
```

### 2. 配置账号
编辑 `config.yaml`：
```yaml
worldquant_account: "your_email@example.com"
worldquant_password: "your_password"
```

### 3. 运行程序
```bash
cd /Users/chiao-yuyang/Desktop/worldquant-miner/AlphaSpire
python alpha_miner.py
```

**就这么简单！** 程序会自动：
- ✅ 预加载 Ollama 模型（`gemma3:1b`）
- ✅ 加载数据和配置
- ✅ 开始迭代寻找 Alpha

---

## 📊 工作流程（迭代优化版）

```
从 hopeful_alphas 选择表达式 → 提交模拟 → 检查结果 → 决策
   ↑                                                 ↓
   └─────────────────────────────────────────────────┘
```

### 🔄 **核心改进：不再依赖 LLM 生成假设！**

- **旧方式**：LLM 生成假设 → LLM 设计表达式（创造力不足，重复率高）
- **新方式**：从 `hopeful_alphas.json` 的优化建议中**直接提取表达式**（基于成功案例的迭代优化）

每个 `hopeful_alphas.json` 的 alpha 都包含多个 `optimization_suggestions`，例如：
```json
{
  "direction": "Add volume confirmation",
  "expression_example": "-ts_rank(close, 5) * rank(ts_delta(volume, 5))"
}
```

系统会从所有 `expression_example` 中随机选择，确保多样性和可行性。

### 决策逻辑（Rule-based）

1. **✅ Sharpe > 1.0** → 调用 `EvaluatorAgent` 分析，添加到 `hopeful_alphas.json`
2. **🔄 Sharpe < -1.0** → 反转表达式 (`-1 * expr`)，调用 `EvaluatorAgent` 分析，添加到 `hopeful_alphas.json`
3. **❌ |Sharpe| < 1.0** → 放弃，选择新表达式

### 防重复机制

- ✅ 所有尝试过的 `expression` 记录在 `all_expressions`
- ✅ 重复 expression 会被立即过滤
- ✅ 所有提交记录在 `results/history.json`

---

## 🎯 成功标准

基于 WorldQuant Brain 评分系统：

| 指标 | 目标 | 说明 |
|------|------|------|
| **Sharpe** | ≥ 1.25 | 风险调整后收益 |
| **Fitness** | ≥ 1.0 | 综合表现 |
| **Turnover** | 0.01 - 0.7 | 换手率范围 |
| **Returns** | > 0 | 收益为正 |

**Hopeful 阈值**（值得优化）：Sharpe ≥ 0.5, Fitness ≥ 0.6

---

## 📁 项目结构

```
AlphaSpire/
├── alpha_miner.py          # ⭐ 主程序
├── config.yaml             # ⚙️  配置
├── run.sh                  # 🏃 启动脚本
│
├── agents/                 # 🤖 Multi-Agent 系统
│   ├── alpha_designer_agent.py    # 从 hopeful_alphas 提取表达式
│   ├── metrics_analyzer.py        # 分析性能指标
│   ├── expression_analyzer.py     # 分析表达式结构
│   └── suggestion_generator.py    # 生成优化建议
│
├── core/                   # 🏗️  核心组件
│   ├── wq_api.py          # WorldQuant API
│   └── data_loader.py     # 数据加载
│
└── data/                   # 📊 数据 (JSON)
    ├── wq_fields/
    └── wq_operators/
```

---

## 💻 运行方式

### 方法 1：直接运行（推荐）
```bash
python alpha_miner.py
```

### 方法 2：使用脚本
```bash
chmod +x run.sh
./run.sh
```

### 方法 3：后台运行
    ```bash
nohup python alpha_miner.py > output.log 2>&1 &
tail -f alpha_miner.log
```

---

## 📁 输出文件

程序运行后会生成以下文件：

### 核心输出文件（都在 `results/` 目录下）

1. **`results/hopeful_alphas.json`** ⭐ **最重要的文件**
   - 记录所有 Sharpe > 1.0 或 Sharpe < -1.0 的 alphas
   - 新的简化格式（3-Stage 分析结果）：
     ```json
     {
       "expression": "alpha expression",
       "result": {...},
       "analysis": {
         "metrics": {
           "performance_grade": "excellent|good|fair|poor",
           "key_strengths": [...],
           "key_weaknesses": [...],
           "improvement_priority": "sharpe|fitness|turnover"
         },
         "expression": {
           "strategy_type": "momentum|mean_reversion|...",
           "signal_mechanism": "...",
           "economic_rationale": "...",
           "key_operators": [...],
           "key_fields": [...]
         },
         "suggested_expressions": [
           {
             "direction": "What to improve",
             "expression": "Concrete alpha expression",
             "rationale": "Why this helps"
           }
         ]
       }
     }
     ```
   - **系统从 `suggested_expressions` 中提取新表达式进行测试**（迭代优化的核心）

2. **`results/history.json`** - 完整历史记录
   - 实时保存每个 iteration 的详细信息
   - 包含：expression、result、decision
   - 可用于复盘和分析

---

## 🎬 预期输出

```
🔄 Preloading model: gemma3:1b...
✅ Model gemma3:1b loaded and ready

🚀 Alpha Miner Started
🎯 WorldQuant Success Criteria (MUST meet ALL to stop):
   Sharpe >= 1.25
   Fitness >= 1.0
   0.1 <= Turnover <= 0.7
   Returns >= 0.1

♾️  Unlimited iterations (will run until success)
================================================================================

📍 Iteration 1
================================================================================

🎨 Step 1: Selecting Expression from Hopeful Alphas...
✅ Expression selected: -ts_rank(close, 5) * rank(ts_delta(volume, 5))
   Source: hopeful_alphas_optimization_suggestions

⚙️ Step 2: Submitting Simulation...
⏳ Waiting for simulation to complete...
✅ Simulation complete: mL36OVEp

📊 Results:
  Sharpe:   1.423 (target >= 1.25)
  Fitness:  1.201 (target >= 1.00)
  Turnover: 0.612 (target 0.01-0.70)
  Returns:  0.115
  ✅ Sharpe > 1.0 → HOPEFUL!

📈 Step 4: Rule-based Decision...
✅ HOPEFUL! Sharpe > 1.0
   Analyzing alpha...
✅ Added to hopeful_alphas.json (total: 5)

...

🎉 SUCCESS! Multiple hopeful alphas found!
Check results/hopeful_alphas.json for details.
```

---

## ⚙️ 配置说明

### 基本配置

    ```yaml
# Ollama 模型
ollama_model: "gemma3:1b"      # 默认（快）
# ollama_model: "qwen2.5:14b"  # 推荐（质量好）
# ollama_model: "llama3.1:8b"  # 平衡

# WorldQuant 账号（必填）
worldquant_account: "your_email@example.com"
worldquant_password: "your_password"

# 模拟参数
worldquant_region: "USA"
worldquant_universe: "TOP3000"

# 成功标准
min_sharpe: 1.25
min_fitness: 1.0
max_turnover: 0.7
min_turnover: 0.01

# 优化阈值
optimize_min_sharpe: 0.5
optimize_min_fitness: 0.6

# 启用的数据集
enabled_field_datasets:
  - pv1
      - fundamental6
      - analyst4
      - model16
      - news12   
    ```

---

## 🔄 模型预加载

程序启动时会**自动预加载模型**：

       ```bash
# 自动执行（无需手动操作）
ollama run gemma3:1b
# 发送 /bye 命令
# 自动退出
```

**好处：**
- ✅ 避免首次调用超时
- ✅ 确保模型已在内存
- ✅ 更快的响应速度

**使用其他模型：**
1. 编辑 `config.yaml` 修改 `ollama_model`
2. 程序会自动预加载你指定的模型

---

## ⏱️ 运行时间

| 阶段 | 时间 |
|------|------|
| 预加载模型 | 5-10 秒 |
| 每次迭代 | 2-6 分钟 |
| 找到成功 Alpha | 30 分钟 - 2 小时 |

---

## 📈 结果文件

运行后在 `results/` 目录生成：

### `history_YYYYMMDD_HHMMSS.json`
完整迭代历史（每 5 次迭代自动保存）

### `successful_alphas_YYYYMMDD_HHMMSS.json`
成功的 Alphas：
```json
{
  "expression": "zscore(rank(ts_delta(est_netprofit, 21)))",
  "result": {
    "sharpe": 1.287,
    "fitness": 1.034,
    "alpha_id": "ABC123"
  },
  "iteration": 8
}
```

---

## 🤖 Agent 架构（3-Stage 分析流水线）

### Alpha Designer Agent（表达式选择器）
- **不再使用 LLM 生成**，直接从 `hopeful_alphas.json` 提取表达式
- 从所有 `suggested_expressions` 中随机选择
- 确保不重复已尝试的表达式
- **优势**：基于成功案例的迭代优化，避免 LLM 创造力不足

### 分析流水线（仅在 Sharpe > 1.0 或 < -1.0 时触发）

#### Stage 1: Metrics Analyzer（性能指标分析）
- 分析 Sharpe, Fitness, Turnover, Returns
- **理解 Fitness 公式**：`Fitness = Sharpe * abs(Returns) / Turnover`
- 对比实际值与 `config.yaml` 中的成功标准
- 识别优势和劣势
- 确定优化优先级（sharpe|fitness|turnover）
- 输出：`performance_grade`, `key_strengths`, `key_weaknesses`, `improvement_priority`

#### Stage 2: Expression Analyzer（表达式结构分析）
- 分析表达式的 operators 和 fields 组合
- 识别策略类型（momentum, mean_reversion, value, etc.）
- 推测信号生成机制和经济原理
- 输出：`strategy_type`, `signal_mechanism`, `economic_rationale`, `key_operators`, `key_fields`

#### Stage 3: Suggestion Generator（优化建议生成）
- 综合前两阶段的分析结果
- 生成 3-5 个具体的优化建议
- 每个建议包含：优化方向、具体表达式、优化原理
- 输出：`suggested_expressions` (数组，每个包含 `direction`, `expression`, `rationale`)

### 决策逻辑（Rule-based，不使用 LLM）
- `Sharpe > 1.0` → 3-Stage 分析 → 添加到 hopeful_alphas → **检查是否满足所有 criteria**
- `Sharpe < -1.0` → 反转 → 3-Stage 分析 → 添加到 hopeful_alphas → **检查是否满足所有 criteria**
- `|Sharpe| < 1.0` → 放弃

### 停止条件（自动成功检测）
程序会**无限循环**，直到找到满足**所有**成功标准的 alpha：
```python
✅ Sharpe   >= 1.25
✅ Fitness  >= 1.0
✅ Turnover: 0.1 - 0.7
✅ Returns  >= 0.1
```
一旦找到，程序自动停止并显示成功消息 🎉

---

## 🐛 故障排除

### "ConnectionRefusedError"
→ Ollama 未运行，运行 `ollama serve`

### "ModuleNotFoundError"
→ 安装依赖：`pip install -r requirements.txt`

### "Authentication failed"
→ 检查 `config.yaml` 中的账号密码

### "Unknown operators" 或表达式无效
→ 使用更强的模型：`ollama_model: "qwen2.5:14b"`

### 预加载失败
→ 不用担心，程序会继续运行，模型会在首次使用时加载

### 找不到成功 Alpha
→ 正常现象，可能需要 50-100 次迭代，或降低标准

---

## 🔧 高级用法

### 自定义迭代参数

编辑 `alpha_miner.py` 的 `main()` 函数：
```python
miner.run(
    max_iterations=50,          # 最大迭代次数
    max_optimize_attempts=2     # 每个假设最多优化次数
)
```

### 监控进度
       ```bash
# 实时日志
tail -f alpha_miner.log

# 检查结果
ls -lh results/

# 查看成功的 Alpha
cat results/successful_alphas_*.json
```

### 批量运行
```bash
for i in {1..5}; do
  python alpha_miner.py
  sleep 10
done
```

---

## 📊 与原版对比

| 方面 | 原 AlphaSpire | 新版 |
|------|--------------|------|
| 策略 | 批量生成测试 | 迭代优化 |
| 停止条件 | 测试完所有 | 找到就停 |
| 反馈 | 无 | 每次分析 |
| 优化 | 无 | 自动优化 |
| 成功率 | 5-10% | 20-40% |

---

## 💡 最佳实践

### 模型选择
- **快速迭代** → `gemma3:1b` (默认)
- **质量优先** → `qwen2.5:14b` (推荐)
- **平衡方案** → `llama3.1:8b`

### 数据集选择
- **短期策略** → pv1, news12
- **长期策略** → fundamental6, analyst4
- **综合策略** → 启用所有数据集

### 标准设置
- **宽松（验证）** → min_sharpe: 1.0
- **标准（默认）** → min_sharpe: 1.25
- **严格（高质量）** → min_sharpe: 2.0

---

## 📚 相关资源

- [WorldQuant Brain](https://platform.worldquantbrain.com/)
- [Ollama](https://ollama.ai/)
- [FastExpr 文档](https://platform.worldquantbrain.com/learn/documentation/en/data-and-operators)

---

## 🎓 技术细节

### 表达式验证
自动验证操作符、字段和语法是否正确

### 状态管理
- 内存维护当前状态
- 每 5 次迭代自动保存
- 支持中断恢复

### 错误处理
- LLM 失败 → 规则基础 fallback
- API 超时 → 自动重试
- 认证过期 → 自动重新认证

---

## 🔄 更新日志

### v2.0 (2024-11-10)
- ✅ 重构为 Multi-Agent 架构
- ✅ 实现迭代优化循环
- ✅ 添加 WorldQuant 标准
- ✅ 自动预加载模型
- ✅ 所有数据改用 JSON
- ✅ 简化项目结构

---

## 📝 License

MIT License

---

**Happy Alpha Hunting! 🚀**

运行命令：
```bash
python alpha_miner.py
```
