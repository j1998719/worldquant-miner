# Multi-Agent Alpha Mining System Design

基于 AlphaAgent 论文架构，针对 WorldQuant Brain 场景的多 Agent 系统设计

## 🎯 系统架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator Agent                        │
│              (流程控制 + Agent 调度)                          │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Idea Agent   │───▶│ Factor Agent │───▶│ Simulation   │
│              │    │              │    │ Agent        │
│ 生成假设      │    │ 构建表达式    │    │ 提交测试      │
└──────────────┘    └──────────────┘    └──────────────┘
        ▲                   ▲                   │
        │                   │                   ▼
        │           ┌──────────────┐    ┌──────────────┐
        │           │ Refine Agent │◀───│ Eval Agent   │
        └───────────│              │    │              │
                    │ 改进优化      │    │ 评估分析      │
                    └──────────────┘    └──────────────┘
```

---

## 📦 Agent 类型定义

### 1️⃣ **IdeaAgent** (想法生成 Agent)

**职责：** 基于市场知识和历史成功案例，生成 alpha 交易假设

**输入：**
- `hopeful_alphas.json` (历史成功 alphas)
- `market_insights.txt` (可选：市场知识库)
- `eval_feedback.json` (来自 EvalAgent 的反馈)

**输出：**
- `alpha_ideas.json`
  ```json
  {
    "idea_id": "idea_001",
    "hypothesis": "Stocks with increasing revenue but declining volume may indicate profit-taking before momentum reversal",
    "rationale": "Volume compression with fundamental strength suggests institutional accumulation",
    "suggested_datasets": ["fundamental6", "pv1"],
    "timestamp": "2025-11-02T10:30:00"
  }
  ```

**使用 LLM：** ✅ (Ollama)

**Prompt 模板：** `prompts/idea_generation.txt`

---

### 2️⃣ **FactorAgent** (因子构建 Agent)

**职责：** 将 alpha 假设转换为符合 WorldQuant 语法的表达式

**输入：**
- `alpha_ideas.json` (来自 IdeaAgent)
- `available_components_USA/fields/*.txt` (可用字段)
- `available_components_USA/operators.txt` (可用运算符)
- `eval_feedback.json` (语法错误反馈)

**输出：**
- `alpha_expressions.json`
  ```json
  {
    "expression_id": "expr_001",
    "idea_id": "idea_001",
    "expression": "rank(ts_corr(fn_def_tax_assets_net_q, volume, 20) * ts_std_dev(close, 10))",
    "description": "Revenue growth correlation with volume compression indicator",
    "fields_used": ["fn_def_tax_assets_net_q", "volume", "close"],
    "operators_used": ["rank", "ts_corr", "ts_std_dev"],
    "complexity_score": 3,
    "timestamp": "2025-11-02T10:31:00"
  }
  ```

**使用 LLM：** ✅ (Ollama)

**Prompt 模板：** `prompts/factor_construction.txt`

**约束条件：**
- 必须使用 available_components 中存在的 fields/operators
- 复杂度不超过 5 层嵌套
- 遵循 WorldQuant 语法规则

---

### 3️⃣ **SimulationAgent** (模拟执行 Agent)

**职责：** 提交 alpha 到 WorldQuant Brain API 并获取回测结果

**输入：**
- `alpha_expressions.json` (来自 FactorAgent)
- `simulation_settings.json` (region, universe, delay 等配置)

**输出：**
- `simulation_results.json`
  ```json
  {
    "result_id": "sim_001",
    "expression_id": "expr_001",
    "alpha_id": "US12345678",
    "sharpe": 1.25,
    "fitness": 0.82,
    "returns": 0.034,
    "turnover": 0.15,
    "drawdown": 0.08,
    "margin": 0.0021,
    "status": "success",
    "error": null,
    "timestamp": "2025-11-02T10:35:00"
  }
  ```

**使用 LLM：** ❌ (纯 API 调用)

**关键逻辑：**
- 批量提交 (multi-simulate 或单个 simulate)
- 等待结果 (轮询或异步)
- 错误处理 (语法错误、API 限制)
- 记录所有尝试到 `simulation_history.json`

---

### 4️⃣ **EvalAgent** (评估分析 Agent)

**职责：** 分析模拟结果，做出决策并生成反馈

**输入：**
- `simulation_results.json` (来自 SimulationAgent)
- `alpha_ideas.json` (原始假设，用于分析)
- `alpha_expressions.json` (表达式，用于分析)

**输出：**
1. **更新文件：**
   - `hopeful_alphas.json` (sharpe > threshold 的成功案例)
   - `rejected_alphas.json` (失败案例，用于学习)

2. **决策输出：** `eval_decisions.json`
   ```json
   {
     "decision_id": "dec_001",
     "result_id": "sim_001",
     "decision": "hopeful",  // hopeful | reject | negate | refine
     "reason": "Strong Sharpe (1.25) with acceptable fitness (0.82)",
     "next_action": null,
     "feedback_to_idea": "Revenue-volume relationship validated",
     "feedback_to_factor": "Consider adding market neutralization",
     "timestamp": "2025-11-02T10:36:00"
   }
   ```

**使用 LLM：** ✅ (用于生成深度分析和反馈)

**Prompt 模板：** `prompts/result_evaluation.txt`

**决策规则：**

| Sharpe 范围 | Fitness | 决策 | 动作 |
|------------|---------|------|------|
| sharpe > 0.5 | fitness > 0.6 | **hopeful** | 写入 `hopeful_alphas.json` |
| -0.5 < sharpe < 0.5 | any | **reject** | 写入 `rejected_alphas.json` |
| sharpe < -0.5 | any | **negate** | 取负号重新测试 |
| syntax error | - | **refine** | 反馈给 FactorAgent 修正 |

**反馈类型：**
- **Backtest Feedback**: 性能指标分析 (Sharpe, Fitness, Turnover)
- **Self-reflection**: 与历史 hopeful alphas 比较
- **Analysis Feedback**: LLM 深度分析为什么成功/失败

---

### 5️⃣ **RefineAgent** (改进优化 Agent)

**职责：** 基于反馈优化表达式或想法

**输入：**
- `eval_decisions.json` (decision = "refine" 或 "negate")
- `simulation_results.json` (错误信息或性能数据)
- `alpha_expressions.json` (原始表达式)

**输出：**
- `refined_expressions.json` → 重新进入 FactorAgent
- `refined_ideas.json` → 重新进入 IdeaAgent

**使用 LLM：** ✅ (Ollama)

**Prompt 模板：** `prompts/refinement.txt`

**优化策略：**
- **语法修正**: 修复字段不存在、运算符错误
- **取负号**: `expression` → `-1 * (expression)`
- **参数调整**: 修改 lookback 窗口、threshold
- **中和调整**: 添加 `group_neutralize`, `market_neutralize`

---

### 6️⃣ **OrchestratorAgent** (流程控制 Agent)

**职责：** 管理整个 Agent 工作流，决定谁在什么时候运行

**主要逻辑：**

```python
class OrchestratorAgent:
    def run_mining_cycle(self, num_ideas=10):
        """运行一轮完整的挖掘循环"""
        
        # Step 1: 生成想法
        ideas = self.idea_agent.generate(count=num_ideas)
        save_json(ideas, 'alpha_ideas.json')
        
        # Step 2: 构建表达式
        expressions = self.factor_agent.build(ideas)
        save_json(expressions, 'alpha_expressions.json')
        
        # Step 3: 提交模拟
        results = self.simulation_agent.simulate(expressions)
        save_json(results, 'simulation_results.json')
        
        # Step 4: 评估结果
        decisions = self.eval_agent.evaluate(results)
        save_json(decisions, 'eval_decisions.json')
        
        # Step 5: 处理决策
        for decision in decisions:
            if decision['decision'] == 'hopeful':
                self.save_hopeful_alpha(decision)
            
            elif decision['decision'] == 'negate':
                # 取负号重新测试
                negated = self.refine_agent.negate(decision)
                result = self.simulation_agent.simulate([negated])
                self.eval_agent.evaluate(result)
            
            elif decision['decision'] == 'refine':
                # 优化后重新进入流程
                refined = self.refine_agent.refine(decision)
                result = self.simulation_agent.simulate([refined])
                self.eval_agent.evaluate(result)
            
            elif decision['decision'] == 'reject':
                self.save_rejected_alpha(decision)
        
        # Step 6: 生成本轮总结
        self.generate_cycle_summary()
```

**配置文件：** `orchestrator_config.json`
```json
{
  "simulation_settings": {
    "region": "USA",
    "universe": "TOP3000",
    "delay": 1,
    "decay": 0,
    "neutralization": "SUBINDUSTRY",
    "pasteurization": "ON",
    "nan_handling": "OFF",
    "unit_handling": "VERIFY",
    "truncation": 0.08,
    "max_stock_weight": 0.1
  },
  "agent_settings": {
    "ideas_per_cycle": 10,
    "max_refinement_iterations": 3,
    "sharpe_threshold_hopeful": 0.5,
    "sharpe_threshold_negate": -0.5
  },
  "ollama_config": {
    "url": "http://localhost:11434",
    "model": "gemma2:2b",
    "temperature": 0.7
  }
}
```

---

## 📁 文件结构

```
consultant-agent/
├── agents/                         # Agent 实现
│   ├── __init__.py
│   ├── base_agent.py               # Agent 基类
│   ├── idea_agent.py               # IdeaAgent 实现
│   ├── factor_agent.py             # FactorAgent 实现
│   ├── simulation_agent.py         # SimulationAgent 实现
│   ├── eval_agent.py               # EvalAgent 实现
│   ├── refine_agent.py             # RefineAgent 实现
│   └── orchestrator_agent.py       # OrchestratorAgent 实现
│
├── prompts/                        # LLM Prompt 模板
│   ├── idea_generation.txt
│   ├── factor_construction.txt
│   ├── result_evaluation.txt
│   └── refinement.txt
│
├── data/                           # Agent 通信文件
│   ├── alpha_ideas.json            # IdeaAgent 输出
│   ├── alpha_expressions.json      # FactorAgent 输出
│   ├── simulation_results.json     # SimulationAgent 输出
│   ├── eval_decisions.json         # EvalAgent 输出
│   ├── refined_expressions.json    # RefineAgent 输出
│   ├── hopeful_alphas.json         # 成功案例
│   ├── rejected_alphas.json        # 失败案例
│   ├── expression_history.json     # 去重历史记录 (NEW)
│   └── cycle_summary.json          # 周期总结 (NEW)
│
├── logs/                           # 日志系统 (NEW)
│   ├── orchestrator.log            # 总控日志
│   ├── agents/                     # 各 Agent 日志
│   │   ├── idea_agent.log
│   │   ├── factor_agent.log
│   │   ├── simulation_agent.log
│   │   ├── eval_agent.log
│   │   └── refine_agent.log
│   ├── cycles/                     # 周期详细日志
│   │   ├── cycle_001_20251102_103000.log
│   │   └── ...
│   └── errors/                     # 错误日志
│       ├── api_errors.log
│       ├── llm_errors.log
│       └── system_errors.log
│
├── utils/                          # 工具函数 (NEW)
│   ├── __init__.py
│   ├── deduplication.py            # 去重工具
│   ├── expression_parser.py        # 表达式解析
│   └── logging_config.py           # 日志配置
│
├── available_components_USA/       # WorldQuant 组件数据
│   ├── SUMMARY.txt
│   ├── operators.txt
│   └── fields/
│       └── *.txt
│
├── config/                         # 配置文件 (NEW)
│   ├── orchestrator_config.json    # 总控配置
│   ├── deduplication_config.json   # 去重配置
│   └── simulation_settings.json    # 模拟设置
│
├── credential.txt                  # WorldQuant 认证
├── main.py                         # 主入口
├── requirements.txt                # Python 依赖
└── AGENT_DESIGN.md                 # 本设计文档
```

---

## 🔄 完整流程示例

### **场景：挖掘 10 个 alpha**

```
1. [Orchestrator] 启动新一轮挖掘周期
   ↓
2. [IdeaAgent] 读取 hopeful_alphas.json + market_insights
   → 生成 10 个 alpha ideas
   → 保存到 alpha_ideas.json
   ↓
3. [FactorAgent] 读取 alpha_ideas.json + available_components
   → 为每个 idea 生成 1-3 个表达式 (共 25 个)
   → 保存到 alpha_expressions.json
   ↓
4. [SimulationAgent] 读取 alpha_expressions.json
   → 批量提交到 WorldQuant API
   → 等待结果 (可能需要 30-60 秒)
   → 保存到 simulation_results.json
   ↓
5. [EvalAgent] 读取 simulation_results.json
   → 分析每个结果
   → 做出决策：
     - 5 个 hopeful → hopeful_alphas.json
     - 3 个 sharpe < -0.5 → 标记为 negate
     - 2 个语法错误 → 标记为 refine
     - 15 个普通失败 → rejected_alphas.json
   → 保存到 eval_decisions.json
   ↓
6. [RefineAgent] 处理 negate 和 refine
   → 取负号: 3 个
   → 修正语法: 2 个
   → 保存到 refined_expressions.json
   ↓
7. [SimulationAgent] 重新测试 5 个优化后的表达式
   ↓
8. [EvalAgent] 再次评估
   → 1 个新的 hopeful
   → 4 个最终 reject
   ↓
9. [Orchestrator] 生成本轮总结报告
   → 成功率: 6/30 = 20%
   → 总计 hopeful: 6 个
   → 保存到 cycle_summary.json
```

---

## 📝 日志系统设计

### **1. 分层日志结构**

```
logs/
├── orchestrator.log          # 总控日志 (所有周期执行记录)
├── agents/
│   ├── idea_agent.log        # IdeaAgent 运行日志
│   ├── factor_agent.log      # FactorAgent 运行日志
│   ├── simulation_agent.log  # SimulationAgent API 调用日志
│   ├── eval_agent.log        # EvalAgent 评估日志
│   └── refine_agent.log      # RefineAgent 优化日志
│
├── cycles/                   # 每轮周期的详细日志
│   ├── cycle_001_20251102_103000.log
│   ├── cycle_002_20251102_110000.log
│   └── ...
│
└── errors/
    ├── api_errors.log        # WorldQuant API 错误
    ├── llm_errors.log        # Ollama LLM 错误
    └── system_errors.log     # 系统级错误
```

### **2. 日志内容示例**

#### **orchestrator.log** (总控日志)
```log
[2025-11-02 10:30:00] [INFO] ========== Cycle 001 Started ==========
[2025-11-02 10:30:00] [INFO] Config: region=USA, universe=TOP3000, ideas=10
[2025-11-02 10:30:05] [INFO] IdeaAgent: Generated 10 ideas
[2025-11-02 10:30:15] [INFO] FactorAgent: Built 25 expressions
[2025-11-02 10:30:45] [INFO] SimulationAgent: Submitted 25 alphas
[2025-11-02 10:31:30] [INFO] SimulationAgent: Received 25 results (23 success, 2 errors)
[2025-11-02 10:31:35] [INFO] EvalAgent: 5 hopeful, 3 negate, 2 refine, 15 reject
[2025-11-02 10:31:40] [INFO] RefineAgent: Processed 5 refinements
[2025-11-02 10:32:10] [INFO] ========== Cycle 001 Completed ==========
[2025-11-02 10:32:10] [METRICS] Success Rate: 20% (6/30), Total Hopeful: 6
```

#### **simulation_agent.log** (API 调用日志)
```log
[2025-11-02 10:30:45] [INFO] Submitting batch of 25 expressions
[2025-11-02 10:30:46] [API] POST /alphas/simulate | expr_001 | 200 OK
[2025-11-02 10:30:47] [API] POST /alphas/simulate | expr_002 | 200 OK
[2025-11-02 10:30:48] [API] POST /alphas/simulate | expr_003 | 400 Bad Request
[2025-11-02 10:30:48] [ERROR] expr_003: Syntax error - "Unknown variable 'fnd6_xxx'"
[2025-11-02 10:31:30] [INFO] Batch completed: 23/25 success
[2025-11-02 10:31:30] [METRICS] API calls: 25, Errors: 2, Avg latency: 1.2s
```

#### **cycle_001_20251102_103000.log** (单轮详细日志)
```log
[10:30:00] ===== CYCLE 001 START =====

[10:30:05] IdeaAgent Output:
  - idea_001: "Revenue growth with volume compression"
  - idea_002: "Momentum reversal with low volatility"
  ...

[10:30:15] FactorAgent Output:
  - expr_001 (idea_001): rank(ts_corr(fn_def_tax_assets_net_q, volume, 20))
  - expr_002 (idea_001): ts_std_dev(close, 10) * ts_delta(volume, 5)
  ...

[10:31:30] SimulationAgent Results:
  - expr_001: Sharpe=1.25, Fitness=0.82 [SUCCESS]
  - expr_002: Sharpe=-0.35, Fitness=0.45 [REJECT]
  - expr_003: Syntax Error [REFINE]
  ...

[10:31:35] EvalAgent Decisions:
  - expr_001: HOPEFUL (Strong Sharpe with good fitness)
  - expr_002: REJECT (Negative Sharpe)
  - expr_003: REFINE (Fix field name)
  ...

[10:32:10] ===== CYCLE 001 END =====
  Total: 30 alphas tested
  Hopeful: 6 (20%)
  Rejected: 19 (63%)
  Refined: 5 (17%)
```

### **3. 日志配置**

```python
# logging_config.py
import logging
from logging.handlers import RotatingFileHandler

LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '[%(asctime)s] [%(levelname)s] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'detailed': {
            'format': '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'standard',
        },
        'orchestrator_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/orchestrator.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
            'formatter': 'detailed',
        },
        'api_error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/errors/api_errors.log',
            'maxBytes': 5242880,  # 5MB
            'backupCount': 5,
            'formatter': 'detailed',
        },
    },
    'loggers': {
        'orchestrator': {
            'handlers': ['console', 'orchestrator_file'],
            'level': 'INFO',
        },
        'simulation_agent': {
            'handlers': ['console', 'api_error_file'],
            'level': 'DEBUG',
        },
    }
}
```

### **4. 实战 Debug 场景**

#### **场景 1: 为什么没有生成 hopeful alpha？**

**问题：** 运行了 10 个周期，`hopeful_alphas.json` 还是空的

**Debug 步骤：**

```bash
# 1. 查看总控日志，看整体流程
$ tail -100 logs/orchestrator.log | grep METRICS
[METRICS] Cycle 001: Success Rate: 0% (0/30)
[METRICS] Cycle 002: Success Rate: 0% (0/28)
[METRICS] Cycle 003: Success Rate: 0% (0/32)

# 2. 查看 EvalAgent 的决策分布
$ grep "EvalAgent:" logs/orchestrator.log | tail -10
[INFO] EvalAgent: 0 hopeful, 2 negate, 5 refine, 23 reject

# 3. 检查 simulation 结果
$ grep "Sharpe" logs/cycles/cycle_001_*.log | sort -k3 -rn | head -5
  - expr_012: Sharpe=0.45, Fitness=0.62 [REJECT]  ← 接近阈值但未达标
  - expr_003: Sharpe=0.38, Fitness=0.55 [REJECT]
  - expr_021: Sharpe=-0.12, Fitness=0.48 [REJECT]

# 4. 分析：Sharpe 最高只有 0.45，未达到 0.5 阈值
# 解决方案：调整阈值或优化 IdeaAgent 的假设质量
```

---

#### **场景 2: API 频繁报错**

**问题：** `simulation_agent.log` 中大量 400/500 错误

**Debug 步骤：**

```bash
# 1. 查看 API 错误日志
$ tail -50 logs/errors/api_errors.log
[ERROR] expr_045: Syntax error - "Unknown variable 'fnd2_xxx_ib'"
[ERROR] expr_046: Syntax error - "Unknown variable 'fnd2_yyy_q'"
[ERROR] expr_047: Syntax error - "Required attribute 'lookback' must have a value"

# 2. 统计错误类型
$ grep "ERROR" logs/errors/api_errors.log | cut -d':' -f3 | sort | uniq -c
   45 Syntax error - "Unknown variable"
   12 Syntax error - "Required attribute 'lookback'"
    3 Syntax error - "Unexpected character"

# 3. 检查 FactorAgent 是否使用了不存在的字段
$ grep "fnd2_xxx_ib" logs/agents/factor_agent.log
[WARNING] Generated expression uses unavailable field: fnd2_xxx_ib

# 4. 分析：FactorAgent 从 available_components 中选择了错误的字段
# 解决方案：检查 available_components_USA/fields/ 是否正确生成
```

---

#### **场景 3: LLM 生成的表达式格式错误**

**问题：** RefineAgent 频繁触发，但修正后仍然失败

**Debug 步骤：**

```bash
# 1. 查看 RefineAgent 日志
$ tail -100 logs/agents/refine_agent.log
[INFO] Refining expr_123: "rank ts_corr(close, volume, 20)"  ← 缺少括号
[INFO] Refined to: "rank(ts_corr(close, volume, 20))"
[INFO] Refining expr_124: "ts_delta(close)"  ← 缺少 lookback 参数
[INFO] Refined to: "ts_delta(close, 1)"

# 2. 检查 FactorAgent 的 Prompt 是否清晰
$ cat prompts/factor_construction.txt | grep -A5 "Syntax Rules"

# 3. 查看 LLM 错误日志
$ grep "Ollama" logs/errors/llm_errors.log
[ERROR] Ollama timeout after 30s for model gemma2:2b
[ERROR] Ollama returned empty response

# 4. 分析：LLM 模型可能太小，理解语法规则有困难
# 解决方案：升级模型 (gemma2:2b → qwen2.5:7b) 或优化 Prompt
```

---

#### **场景 4: 系统卡住不动**

**问题：** `orchestrator.log` 停在某个步骤，没有后续输出

**Debug 步骤：**

```bash
# 1. 查看最后的日志
$ tail -20 logs/orchestrator.log
[10:30:45] [INFO] SimulationAgent: Submitted 25 alphas
[10:30:46] [INFO] SimulationAgent: Waiting for results...
# (没有后续输出)

# 2. 检查 SimulationAgent 详细日志
$ tail -50 logs/agents/simulation_agent.log
[10:30:45] [API] POST /alphas/simulate | expr_001 | 200 OK
[10:30:46] [API] POST /alphas/simulate | expr_002 | 200 OK
...
[10:30:58] [API] POST /alphas/simulate | expr_025 | 200 OK
[10:30:58] [INFO] Waiting for alpha_id: US12345678 to complete...
[10:31:00] [DEBUG] Polling status: PENDING
[10:31:05] [DEBUG] Polling status: PENDING
# (一直 PENDING)

# 3. 分析：某个 alpha 卡在 WorldQuant 后台，状态未更新
# 解决方案：
#   - 添加超时机制 (30s 后跳过)
#   - 异步处理，不阻塞其他 alphas
```

---

#### **场景 5: 去重是否正常工作？**

**问题：** 想确认去重功能是否生效

**Debug 步骤：**

```bash
# 1. 查看去重统计
$ grep "deduplication_stats" data/cycle_summary.json | tail -5
  "exact_duplicates": 5,
  "semantic_duplicates": 2,
  "high_similarity": 3,
  "skip_rate": 0.33

# 2. 查看被跳过的表达式
$ grep "Skipped duplicate" logs/agents/simulation_agent.log
[INFO] Skipped duplicate: rank(ts_corr(volume, close, 20))
[INFO] Skipped duplicate: ts_std_dev(close, 10)

# 3. 检查 expression_history.json
$ cat data/expression_history.json | jq '."a3f2d8e1c9b4f6e7"'
{
  "expression": "rank(ts_corr(volume, close, 20))",
  "first_tested": "2025-11-02T10:30:00",
  "test_count": 2,  ← 被测试了 2 次（有重复）
  "best_sharpe": 1.25,
  "status": "hopeful"
}

# 4. 分析：去重功能正常，成功拦截了重复提交
```

---

#### **场景 6: 性能分析**

**问题：** 每个周期耗时太长，想找出瓶颈

**Debug 步骤：**

```bash
# 1. 分析各 Agent 耗时
$ grep "took" logs/orchestrator.log
[INFO] IdeaAgent took 5.2s
[INFO] FactorAgent took 15.8s  ← 最慢
[INFO] SimulationAgent took 45.3s
[INFO] EvalAgent took 3.1s

# 2. 深入分析 FactorAgent
$ grep "LLM call" logs/agents/factor_agent.log | awk '{sum+=$NF} END {print "Avg:", sum/NR, "s"}'
Avg: 0.63s per expression

# 3. 计算：25 个表达式 × 0.63s = 15.75s (串行调用)
# 解决方案：并行调用 LLM (5 个线程 → 耗时降至 3.15s)
```

---

### **5. 日志查询快捷命令**

```bash
# 实时监控总控日志
$ tail -f logs/orchestrator.log

# 查看最近 5 个周期的成功率
$ grep "Success Rate" logs/orchestrator.log | tail -5

# 统计每个 Agent 的平均耗时
$ grep "took" logs/orchestrator.log | awk '{print $3, $5}' | sort | uniq

# 查看所有 API 错误
$ cat logs/errors/api_errors.log | grep ERROR | cut -d']' -f3 | sort | uniq -c

# 查看 hopeful alphas 的 Sharpe 分布
$ cat data/hopeful_alphas.json | jq '.[].sharpe' | sort -rn

# 查看某个周期的完整流程
$ cat logs/cycles/cycle_001_*.log

# 查看 LLM 调用失败率
$ grep -c "ERROR" logs/errors/llm_errors.log
$ grep -c "INFO.*LLM call" logs/agents/*.log
```

---

### **6. 日志级别建议**

| 环境 | Orchestrator | Agents | API Calls | LLM Calls |
|------|-------------|--------|-----------|-----------|
| **开发** | DEBUG | DEBUG | DEBUG | DEBUG |
| **测试** | INFO | INFO | DEBUG | INFO |
| **生产** | INFO | INFO | INFO | WARNING |

```python
# 动态调整日志级别
import logging

# 生产环境：只记录重要信息
logging.getLogger('orchestrator').setLevel(logging.INFO)
logging.getLogger('simulation_agent').setLevel(logging.INFO)

# 调试时：开启详细日志
logging.getLogger('factor_agent').setLevel(logging.DEBUG)
```

---

## 🔁 Alpha 去重机制

### **问题：为什么需要去重？**

1. **避免重复测试** → 浪费 API quota
2. **避免重复学习** → 污染 hopeful_alphas.json
3. **提高探索效率** → 专注新的假设

### **解决方案：三级去重**

#### **Level 1: 表达式指纹 (Expression Fingerprint)**

**机制：** 对表达式进行标准化后计算哈希值

```python
def normalize_expression(expr: str) -> str:
    """标准化表达式，去除空格、统一格式"""
    expr = expr.replace(' ', '')
    expr = expr.lower()
    # 标准化字段顺序 (如果是对称运算)
    # rank(a + b) == rank(b + a) → 统一为 rank(a + b)
    return expr

def get_expression_fingerprint(expr: str) -> str:
    """生成表达式指纹"""
    normalized = normalize_expression(expr)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]
```

**存储：** `expression_history.json`

```json
{
  "a3f2d8e1c9b4f6e7": {
    "expression": "rank(ts_corr(volume, close, 20))",
    "first_tested": "2025-11-02T10:30:00",
    "test_count": 1,
    "best_sharpe": 1.25,
    "status": "hopeful"
  },
  "b8c3e5f2a1d7e9f4": {
    "expression": "-1 * rank(ts_corr(volume, close, 20))",
    "first_tested": "2025-11-02T10:31:00",
    "test_count": 1,
    "best_sharpe": -0.35,
    "status": "rejected"
  }
}
```

#### **Level 2: 语义去重 (Semantic Deduplication)**

**机制：** 检测本质相同但形式不同的表达式

**示例：**
```python
# 这些表达式本质相同
expr1 = "rank(a + b)"
expr2 = "rank(b + a)"
expr3 = "rank((a + b))"

# 这些也相同
expr4 = "ts_corr(close, volume, 20)"
expr5 = "ts_corr(volume, close, 20)"  # 相关性是对称的
```

**实现：** 使用 AST (抽象语法树) 解析

```python
def get_semantic_fingerprint(expr: str) -> str:
    """基于语义的指纹"""
    # 1. 解析表达式为 AST
    ast = parse_alpha_expression(expr)
    
    # 2. 标准化 AST (排序对称运算符的子节点)
    normalized_ast = normalize_ast(ast)
    
    # 3. 序列化并计算哈希
    return hash_ast(normalized_ast)
```

#### **Level 3: 相似度检测 (Similarity Detection)**

**机制：** 检测高度相似的表达式（防止微小变化）

**示例：**
```python
# 这些表达式高度相似（只改了 lookback）
expr1 = "rank(ts_corr(close, volume, 20))"
expr2 = "rank(ts_corr(close, volume, 21))"  # 相似度 95%

# 应该标记为 "variant" 而非完全新的 alpha
```

**实现：** 编辑距离 + 结构相似度

```python
def calculate_similarity(expr1: str, expr2: str) -> float:
    """计算表达式相似度 (0-1)"""
    # 1. Token 层面的编辑距离
    tokens1 = tokenize(expr1)
    tokens2 = tokenize(expr2)
    edit_distance = levenshtein(tokens1, tokens2)
    
    # 2. 结构相似度
    ast1 = parse_alpha_expression(expr1)
    ast2 = parse_alpha_expression(expr2)
    structure_sim = ast_similarity(ast1, ast2)
    
    # 3. 综合评分
    return 0.6 * (1 - edit_distance) + 0.4 * structure_sim
```

### **去重策略在各 Agent 中的应用**

#### **FactorAgent: 生成前检查**

```python
class FactorAgent:
    def build_expression(self, idea):
        expression = self.llm_generate(idea)
        
        # 检查是否已存在
        fingerprint = get_expression_fingerprint(expression)
        
        if fingerprint in self.expression_history:
            history = self.expression_history[fingerprint]
            self.logger.warning(
                f"Duplicate expression detected: {expression}\n"
                f"First tested: {history['first_tested']}, "
                f"Status: {history['status']}, "
                f"Best Sharpe: {history['best_sharpe']}"
            )
            
            # 决策：是否跳过或变体生成
            if history['status'] == 'hopeful':
                return None  # 跳过，已经是好的 alpha
            elif history['status'] == 'rejected' and history['best_sharpe'] < -0.5:
                # 如果之前很差，可以尝试取负号
                return f"-1 * ({expression})"
            else:
                return None  # 跳过
        
        return expression
```

#### **SimulationAgent: 提交前过滤**

```python
class SimulationAgent:
    def simulate_batch(self, expressions):
        # 批量去重
        unique_expressions = []
        skipped = []
        
        for expr in expressions:
            fingerprint = get_expression_fingerprint(expr['expression'])
            
            if fingerprint not in self.expression_history:
                unique_expressions.append(expr)
            else:
                skipped.append(expr)
                self.logger.info(f"Skipped duplicate: {expr['expression']}")
        
        self.logger.info(
            f"Filtered {len(skipped)}/{len(expressions)} duplicates. "
            f"Submitting {len(unique_expressions)} unique alphas."
        )
        
        # 提交唯一的表达式
        return self._submit_to_api(unique_expressions)
```

### **去重配置**

```json
// deduplication_config.json
{
  "enabled": true,
  "levels": {
    "expression_fingerprint": true,
    "semantic_deduplication": true,
    "similarity_detection": true
  },
  "similarity_threshold": 0.9,
  "allow_negation_variants": true,
  "allow_parameter_variants": false,
  "max_test_per_expression": 1,
  "retention_days": 30
}
```

### **去重统计**

在 `cycle_summary.json` 中记录：

```json
{
  "cycle_id": "cycle_001",
  "deduplication_stats": {
    "total_generated": 30,
    "exact_duplicates": 5,
    "semantic_duplicates": 2,
    "high_similarity": 3,
    "unique_submitted": 20,
    "skip_rate": 0.33
  }
}
```

---

## 🎨 关键设计原则

### ✅ **松耦合**
- 每个 Agent 独立运行
- 通过 JSON 文件通信（可改为消息队列）

### ✅ **可追溯**
- 每个决策都有完整的 ID 链: `idea_id → expression_id → result_id → decision_id`
- 所有中间结果都保存
- 完整的日志系统记录每个操作

### ✅ **可扩展**
- 轻松添加新的 Agent (e.g., DataAgent, MarketAgent)
- Prompt 模板外部化，易于调整

### ✅ **容错性**
- API 失败 → 记录错误，继续下一个
- LLM 生成无效 → RefineAgent 处理
- 超时 → 保存状态，下次恢复

### ✅ **并行化**
- SimulationAgent 可并行提交多个 alphas
- IdeaAgent 和 FactorAgent 可使用多个 LLM 实例

### ✅ **去重机制**
- 三级去重：表达式指纹 + 语义去重 + 相似度检测
- 避免重复测试，提高 API quota 利用率
- 历史记录可追溯

---

## 🚀 与原 adaptive_alpha_miner.py 的主要区别

| 维度 | 原系统 | 新系统 (Multi-Agent) |
|------|--------|---------------------|
| **架构** | 单一脚本 | 多 Agent 协作 |
| **想法来源** | 随机选择 fields/operators | IdeaAgent 基于知识生成 |
| **表达式生成** | 单次 LLM 调用 | FactorAgent 专门构建 + 多次迭代 |
| **评估** | 简单阈值判断 | EvalAgent 深度分析 + 反馈 |
| **优化** | 无 | RefineAgent 针对性改进 |
| **可解释性** | 低 | 高 (每步都有 rationale) |
| **学习能力** | 弱 | 强 (利用 hopeful_alphas 反馈) |

---

## 📊 预期效果

1. **更高质量**: IdeaAgent 生成的假设更有金融逻辑
2. **更高成功率**: RefineAgent 可优化表达式，而非直接丢弃
3. **更好可解释性**: 每个 alpha 都有完整的 reasoning chain
4. **更易维护**: 修改某个环节不影响其他 Agent
5. **更易扩展**: 可添加 MarketAgent 实时调整策略

---

## 🛠️ 实现建议

### Phase 1: 核心 Agents (Week 1)
- [ ] BaseAgent 基类
- [ ] IdeaAgent (简化版，随机生成想法)
- [ ] FactorAgent (转换为表达式)
- [ ] SimulationAgent (API 调用)
- [ ] EvalAgent (基本决策)

### Phase 2: 优化与反馈 (Week 2)
- [ ] RefineAgent (取负号 + 语法修正)
- [ ] IdeaAgent 增强 (使用 hopeful_alphas)
- [ ] EvalAgent 增强 (LLM 分析)

### Phase 3: 流程控制 (Week 3)
- [ ] OrchestratorAgent
- [ ] 循环控制
- [ ] 错误恢复
- [ ] 日志系统

### Phase 4: 高级功能 (Week 4)
- [ ] 并行化
- [ ] 消息队列替代文件通信
- [ ] Web UI 监控
- [ ] A/B 测试不同策略

---

**下一步：开始实现 Phase 1？**

