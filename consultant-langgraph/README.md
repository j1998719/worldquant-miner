# WorldQuant Alpha Brain Consultant

**LangGraph + Ollama Cloud Edition**

Automated alpha discovery pipeline that researches academic papers, generates alpha hypotheses, converts them to WorldQuant Brain expressions, and tests them using the real WorldQuant Brain API with iterative refinement.

---

## 🎯 Features

- **📚 Parallel Paper Research** - Searches arXiv, SSRN, Google Scholar simultaneously
- **💡 LLM-Powered Idea Generation** - Uses Ollama Cloud (gpt-oss:120b) to generate and expand alpha ideas
- **⚡ Formula Generation** - Converts ideas to WorldQuant Brain FASTEXPR formulas
- **🧪 Real Backtesting** - Simulates alphas on WorldQuant Brain API
- **🔄 Iterative Refinement** - Automatically improves underperforming alphas (negation, parameter tuning)
- **🔍 Deduplication** - SHA256 fingerprints prevent testing duplicate alphas
- **📊 Structured Logging** - Per-cycle and per-agent logs for complete audit trail

---

## 📋 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   LangGraph StateGraph Workflow                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
    ┌──────────────────────────────────────────────────────┐
    │  1. Research Papers (Parallel)                       │
    │     - arXiv search                                   │
    │     - SSRN search (if configured)                    │
    │     - Google Scholar (if configured)                 │
    └──────────────┬───────────────────────────────────────┘
                   ↓
    ┌──────────────────────────────────────────────────────┐
    │  2. Extract & Generate Ideas                         │
    │     - Extract ideas from papers (Ollama)             │
    │     - Generate new ideas (Ollama)                    │
    │     - Expand ideas into variants                     │
    └──────────────┬───────────────────────────────────────┘
                   ↓
    ┌──────────────────────────────────────────────────────┐
    │  3. Generate Formulas                                │
    │     - Convert ideas to FASTEXPR (Ollama)             │
    │     - Generate multiple variants per idea            │
    └──────────────┬───────────────────────────────────────┘
                   ↓
    ┌──────────────────────────────────────────────────────┐
    │  4. Deduplicate                                      │
    │     - Check expression fingerprints                  │
    │     - Filter out duplicates                          │
    └──────────────┬───────────────────────────────────────┘
                   ↓
    ┌──────────────────────────────────────────────────────┐
    │  5. Simulate (WorldQuant Brain API)                  │
    │     - Real backtesting                               │
    │     - Get Sharpe, Fitness, Turnover                  │
    └──────────────┬───────────────────────────────────────┘
                   ↓
    ┌──────────────────────────────────────────────────────┐
    │  6. Evaluate Results                                 │
    │     - Hopeful: Sharpe > 1.5  →  Save                 │
    │     - Refineable: 0.5 < Sharpe < 1.5  →  Refine      │
    │     - Poor: Sharpe < 0.5  →  Reject                  │
    └──────────────┬───────────────────────────────────────┘
                   ↓
    ┌──────────────────────────────────────────────────────┐
    │  7. Decide Next Action                               │
    │     - Found ≥10 hopeful → END                        │
    │     - Has refinement candidates → REFINE             │
    │     - Iteration < max → CONTINUE (new research)      │
    │     - Otherwise → END                                │
    └──────────────┬───────────────────────────────────────┘
                   ↓
    ┌──────────────────────────────────────────────────────┐
    │  8. Refinement (if needed)                           │
    │     - Negate signals (if Sharpe < 0)                 │
    │     - Adjust parameters (Ollama)                     │
    │     - Re-simulate refined alphas                     │
    └──────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.9+
- WorldQuant Brain account ([sign up here](https://platform.worldquantbrain.com))
- Ollama Cloud API key ([get one here](https://ollama.com))

### 2. Installation

```bash
cd consultant-langgraph/

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

Edit `config.yaml` to add your Ollama API key:

```yaml
ollama_api_key: your_api_key_here
```

WorldQuant credentials are already configured in `config/credentials.json`.

### 4. Run Your First Alpha Discovery

```bash
# Discover momentum alphas
python main.py momentum

# Value investing alphas
python main.py value --keywords "fundamental,earnings"

# Mean reversion with custom settings
python main.py "mean reversion" --ideas 10 --iterations 5

# Volatility strategies
python main.py volatility --keywords "variance,garch"
```

---

## 📖 Usage

### Command Line Interface

```bash
python main.py <topic> [OPTIONS]
```

**Arguments:**
- `topic` - Research topic (e.g., "momentum", "value", "quality", "volatility")

**Options:**
- `--keywords` - Additional search keywords (comma-separated)
- `--ideas` - Number of ideas per cycle (default: 5)
- `--iterations` - Maximum iterations (default: 3)
- `--config` - Path to config file (default: config/langgraph_config.json)
- `--log-level` - Logging level: DEBUG, INFO, WARNING, ERROR (default: INFO)
- `--no-console` - Disable console output, only log to files

### Examples

```bash
# Basic momentum research
python main.py momentum

# Deep dive into value with many ideas
python main.py value --ideas 20 --iterations 5

# Quality investing with specific factors
python main.py quality --keywords "profitability,stability,growth"

# High-frequency mean reversion
python main.py "mean reversion" --keywords "microstructure,volatility"

# Debug mode with verbose logging
python main.py momentum --log-level DEBUG
```

---

## 📁 Project Structure

```
consultant-langgraph/
├── main.py                      # CLI entry point
├── alpha_workflow.py            # LangGraph StateGraph workflow
├── graph_state.py               # State definitions
│
├── Agents/
│   ├── base_agent.py            # Base class for all agents
│   ├── paper_research_agent.py  # Paper search & analysis
│   ├── idea_agent.py            # Idea generation & expansion
│   ├── factor_agent.py          # Formula generation
│   ├── simulation_agent.py      # WorldQuant Brain API client
│   ├── eval_agent.py            # Result evaluation
│   └── refinement_agent.py      # Alpha improvement
│
├── utils/
│   ├── logging_config.py        # Structured logging
│   └── deduplication.py         # Expression history tracking
│
├── config/
│   ├── langgraph_config.json    # Main configuration
│   └── credentials.json         # WorldQuant credentials
│
├── prompts/
│   ├── idea_generation.txt      # Idea generation prompt
│   ├── formula_generation.txt   # Formula conversion prompt
│   ├── paper_analysis.txt       # Paper extraction prompt
│   └── refinement.txt           # Refinement prompt
│
├── data/                        # Generated data (auto-created)
│   ├── hopeful_alphas.json
│   ├── rejected_alphas.json
│   ├── alpha_ideas.json
│   ├── simulation_results.json
│   └── expression_history.json
│
└── logs/                        # Logs (auto-created)
    ├── main.log
    ├── cycles/
    │   └── cycle_YYYYMMDD_HHMMSS.log
    └── agents/
        ├── paper_research.log
        ├── idea_agent.log
        ├── factor_agent.log
        ├── simulation_agent.log
        ├── eval_agent.log
        └── refinement_agent.log
```

---

## ⚙️ Configuration

### Main Config: `config/langgraph_config.json`

```json
{
  "ollama_url": "https://ollama.com",
  "cloud_model": "gpt-oss:120b",

  "workflow": {
    "ideas_per_cycle": 5,
    "max_iterations": 3,
    "enable_deduplication": true,
    "enable_refinement": true,
    "max_refinement_iterations": 2
  },

  "idea_agent": {
    "temperature": 0.8,
    "max_retries": 3
  },

  "factor_agent": {
    "temperature": 0.7,
    "expressions_per_idea": 2
  },

  "eval_agent": {
    "sharpe_threshold_hopeful": 1.5,
    "fitness_threshold_hopeful": 0.6,
    "sharpe_threshold_refine": 0.5
  }
}
```

### WorldQuant Credentials: `config/credentials.json`

```json
[
  "your_email@example.com",
  "your_password"
]
```

---

## 📊 Output

### Data Files

After running, check these files:

- **`data/hopeful_alphas.json`** - Production-ready alphas (Sharpe > 1.5)
- **`data/rejected_alphas.json`** - Failed alphas for learning
- **`data/alpha_ideas.json`** - All generated ideas
- **`data/simulation_results.json`** - Complete backtest results
- **`data/expression_history.json`** - Deduplication database

### Log Files

- **`logs/main.log`** - Main application log
- **`logs/cycles/cycle_*.log`** - Per-cycle execution log
- **`logs/agents/*.log`** - Per-agent activity logs

### Example Hopeful Alpha

```json
{
  "expression_id": "idea_003_expr2",
  "expression": "rank(ts_sum(close/delay(close,1)-1,60)/ts_std(returns,60))",
  "alpha_id": "WQ_ABC123",
  "sharpe": 1.82,
  "fitness": 0.73,
  "returns": 0.18,
  "turnover": 85.3,
  "drawdown": 0.12,
  "reason": "Excellent performance: Sharpe=1.82, Fitness=0.73",
  "timestamp": "2025-01-12T10:23:45"
}
```

---

## 🔧 Troubleshooting

### Common Issues

**1. Ollama API Key Error**
```
Error: Ollama API error 401: Unauthorized
```
**Solution:** Check `config.yaml` has correct `ollama_api_key`

**2. WorldQuant Authentication Failed**
```
Error: Authentication failed: 401
```
**Solution:** Verify credentials in `config/credentials.json`

**3. No Papers Found**
```
Warning: arXiv search returned 0 papers
```
**Solution:** Try different keywords or topics, check internet connection

**4. All Expressions Duplicates**
```
Info: Filtered 25 duplicates, 0 novel expressions remain
```
**Solution:** Delete `data/expression_history.json` to reset deduplication

**5. Import Error: langgraph not found**
```
ModuleNotFoundError: No module named 'langgraph'
```
**Solution:** Run `pip install -r requirements.txt`

---

## 🎓 How It Works

### 1. Research Phase
- Generates optimized search queries using Ollama
- Searches arXiv (and optionally SSRN, Google Scholar) in parallel
- Extracts alpha ideas from paper abstracts using LLM

### 2. Idea Generation Phase
- Generates additional ideas using Ollama with context from historical performance
- Expands each idea into 3 variants (different time horizons, normalizations)

### 3. Formula Generation Phase
- Converts each idea into 2 WorldQuant Brain FASTEXPR formulas
- Uses Ollama to ensure valid syntax and proper operators
- Validates expressions (balanced parentheses, no look-ahead bias)

### 4. Deduplication
- Computes SHA256 fingerprints of normalized expressions
- Filters out duplicates to avoid wasting API quota

### 5. Simulation Phase
- Submits expressions to WorldQuant Brain API
- Polls for results (Sharpe, Fitness, Turnover, etc.)
- Stores results with metadata

### 6. Evaluation Phase
- **Hopeful:** Sharpe > 1.5 AND Fitness > 0.6 → Save to production
- **Refine:** 0.5 < Sharpe < 1.5 → Attempt refinement
- **Reject:** Sharpe < 0.5 → Discard

### 7. Refinement Phase (if needed)
- **Negate:** If Sharpe < -0.5, flip signal direction
- **Adjust:** Use Ollama to modify parameters (windows, normalization, filters)
- Re-simulate refined expressions
- Max 2 refinement iterations per alpha

### 8. Iteration Control
- Continue until: 10+ hopeful alphas found OR max iterations reached
- Can start new research iteration or refine existing candidates

---

## 🚀 Advanced Usage

### Custom Prompts

Edit prompt templates in `prompts/`:
- `idea_generation.txt` - Control idea creativity and focus
- `formula_generation.txt` - Adjust expression complexity
- `paper_analysis.txt` - Change paper extraction logic
- `refinement.txt` - Modify refinement strategies

### Adding New Data Sources

To add SSRN or Google Scholar search:

1. Implement `_search_ssrn()` or `_search_google_scholar()` in `paper_research_agent.py`
2. Enable in config: `"sources": ["arxiv", "ssrn", "google_scholar"]`
3. May require additional libraries (e.g., `scholarly` for Google Scholar)

### Batch Processing Multiple Topics

```bash
# Create a batch script
for topic in momentum value quality volatility; do
  python main.py $topic --ideas 10 --iterations 3
done
```

---

## 📈 Performance Tips

1. **Increase parallelism**: Edit `max_papers_per_source` in config
2. **Reduce API calls**: Lower `ideas_per_cycle` and `expressions_per_idea`
3. **Focus research**: Use specific, targeted keywords
4. **Monitor quota**: WorldQuant Brain has daily simulation limits
5. **Enable deduplication**: Prevents retesting same alphas

---

## 🤝 Contributing

This is a complete, production-ready system. To extend:

1. Add new agents in the same pattern as existing ones
2. Modify `alpha_workflow.py` to integrate new nodes
3. Update `graph_state.py` if new state fields needed
4. Create prompt templates for new LLM interactions

---

## 📄 License

MIT License - See consultant-agent project for details

---

## 🙏 Credits

- **LangGraph** - Workflow orchestration
- **Ollama** - LLM inference (gpt-oss:120b)
- **WorldQuant Brain** - Alpha simulation platform
- **arXiv** - Academic paper search API

---

## 📞 Support

For issues or questions:
1. Check logs in `logs/` directory
2. Review configuration in `config/langgraph_config.json`
3. Verify Ollama and WorldQuant credentials
4. Enable DEBUG logging: `python main.py <topic> --log-level DEBUG`

---

**Happy Alpha Hunting! 🎯📈**
