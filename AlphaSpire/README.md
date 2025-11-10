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

## 📊 工作流程

```
生成假设 → 设计表达式 → 提交模拟 → 评估结果 → 决策
   ↑                                              ↓
   └──────── 重新生成 ←──── 优化 ←────────────────┘
```

### 决策逻辑

1. **✅ ACCEPT** - 达到 WorldQuant 标准 → 停止
2. **🔧 OPTIMIZE** - Hopeful (Sharpe ≥ 0.5, Fitness ≥ 0.6) → 优化
3. **🔄 NEW_HYPOTHESIS** - 表现不佳 → 重新生成

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
│   ├── hypothesis_agent.py
│   ├── alpha_designer_agent.py
│   ├── evaluator_agent.py
│   └── optimizer_agent.py
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

## 🎬 预期输出

```
🔄 Preloading model: gemma3:1b...
✅ Model gemma3:1b loaded and ready

🚀 Alpha Miner Started
🎯 WorldQuant Success Criteria:
   Sharpe >= 1.25
   Fitness >= 1.0
   0.01 <= Turnover <= 0.7
================================================================================

📍 Iteration 1/100
================================================================================

🧠 Step 1: Generating Hypothesis...
✅ Hypothesis: Stocks with strong earnings revisions outperform

🎨 Step 2: Designing Alpha Expression...
✅ Expression: rank(ts_delta(est_netprofit, 21))

⚙️ Step 3: Submitting Simulation...
📊 Results:
  Sharpe:   0.723 (target >= 1.25)
  Fitness:  0.651 (target >= 1.00)
  Turnover: 0.185 (target 0.01-0.70)
  🔧 Hopeful - worth optimizing

📈 Step 4: Evaluating Results...
✅ Decision: OPTIMIZE

...

🎉 SUCCESS! Found a good alpha!
Expression: zscore(rank(ts_delta(est_netprofit, 21)))
Sharpe: 1.287
Fitness: 1.034
Iterations: 8
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

## 🤖 Multi-Agent 架构

### Hypothesis Agent
生成投资假设，避免重复失败的想法

### Alpha Designer Agent
将假设转换为 FastExpr 表达式，只使用有效的 operators/fields

### Evaluator Agent
评估结果并决定：ACCEPT / OPTIMIZE / NEW_HYPOTHESIS

### Optimizer Agent
针对性优化表达式（turnover → 加 rank, sharpe → 加 zscore）

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
