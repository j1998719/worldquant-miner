# Multi-Agent Alpha Mining System

A sophisticated multi-agent system for automated alpha factor discovery using WorldQuant Brain API and LLM-powered agents.

## 🎯 System Architecture

```
IdeaAgent → FactorAgent → SimulationAgent → EvalAgent
    ↑            ↑                              ↓
    └────────────┴──────── RefineAgent ◄───────┘
    
           (Coordinated by OrchestratorAgent)
```

## 📦 Components

### **Agents**
- **IdeaAgent**: Generates trading hypotheses using LLM
- **FactorAgent**: Converts ideas into WorldQuant expressions
- **SimulationAgent**: Submits alphas to WorldQuant Brain API
- **EvalAgent**: Evaluates results and makes decisions
- **OrchestratorAgent**: Coordinates the entire workflow

### **Utilities**
- **Deduplication**: Prevents testing duplicate expressions
- **Logging**: Comprehensive logging system for debugging
- **Expression History**: Tracks all tested expressions

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Activate conda environment
conda activate worldquant

# Install dependencies
pip install requests
```

### 2. Create Credentials File

Create `credential.txt` with your WorldQuant credentials (supports two formats):

**Format 1: JSON Array** (recommended)
```json
["your_email@example.com", "your_password"]
```

**Format 2: Line-by-line**
```
your_email@example.com
your_password
```

### 3. Start Ollama

```bash
# Start Ollama service
ollama serve

# Or on Windows
"/c/Users/jordenyang/AppData/Local/Programs/Ollama/ollama.exe" serve &
```

### 4. Run the System

**Single Cycle** (5 ideas, test once):
```bash
python main.py --mode single --ideas 5
```

**Continuous Mode** (10 cycles):
```bash
python main.py --mode continuous --cycles 10 --ideas 5 --delay 30
```

**Infinite Mode** (until Ctrl+C):
```bash
python main.py --mode continuous --ideas 10
```

## ⚙️ Configuration

Edit `config/orchestrator_config.json`:

```json
{
  "ollama_model": "gemma3:4b",
  "ideas_per_cycle": 5,
  "enable_deduplication": true,
  "simulation_settings": {
    "instrumentType": "EQUITY",
    "region": "USA",
    "universe": "TOP3000",
    "delay": 1,
    "decay": 0,
    "neutralization": "SUBINDUSTRY",
    "truncation": 0.08,
    "pasteurization": "ON",
    "unitHandling": "VERIFY",
    "nanHandling": "OFF",
    "language": "FASTEXPR",
    "visualization": false
  },
  "eval_agent": {
    "sharpe_threshold_hopeful": 0.5,
    "fitness_threshold_hopeful": 0.6,
    "sharpe_threshold_negate": -0.5
  }
}
```

## 📊 Output Files

### **Data Files**
- `data/alpha_ideas.json` - Generated trading hypotheses
- `data/alpha_expressions.json` - Converted expressions
- `data/simulation_results.json` - API test results
- `data/eval_decisions.json` - Agent decisions
- `data/hopeful_alphas.json` - Successful alphas (Sharpe > 0.5)
- `data/rejected_alphas.json` - Failed alphas
- `data/expression_history.json` - Deduplication history
- `data/cycle_summary.json` - Cycle statistics

### **Log Files**
- `logs/orchestrator.log` - Main system log
- `logs/agents/*.log` - Individual agent logs
- `logs/cycles/cycle_*.log` - Detailed cycle logs
- `logs/errors/*.log` - Error logs

## 🔍 Monitoring

### Real-time Monitoring
```bash
# Watch main log
tail -f logs/orchestrator.log

# Watch a specific agent
tail -f logs/agents/simulation_agent.log

# Watch current cycle
tail -f logs/cycles/cycle_*.log | tail -1
```

### Check Success Rate
```bash
# View cycle summaries
cat data/cycle_summary.json | jq '.[] | {cycle_id, success_rate, hopeful_count}'

# Count hopeful alphas
cat data/hopeful_alphas.json | jq '. | length'

# View top alphas
cat data/hopeful_alphas.json | jq 'sort_by(-.sharpe) | .[:5]'
```

## 🎛️ Command-Line Options

```bash
python main.py --help

Options:
  --credentials PATH    Credentials file (default: credential.txt)
  --config PATH         Config file (default: config/orchestrator_config.json)
  --mode {single,continuous}  Execution mode (default: single)
  --cycles N            Number of cycles (default: infinite)
  --delay SECONDS       Delay between cycles (default: 10)
  --ideas N             Ideas per cycle (overrides config)
  --log-level LEVEL     Logging level: DEBUG, INFO, WARNING, ERROR
```

## 📝 Examples

### Example 1: Quick Test (5 ideas, single cycle)
```bash
python main.py --mode single --ideas 5 --log-level DEBUG
```

### Example 2: Production Run (10 cycles, 10 ideas each)
```bash
python main.py --mode continuous --cycles 10 --ideas 10 --delay 60
```

### Example 3: Custom Configuration
```bash
python main.py --mode continuous \
  --config my_config.json \
  --credentials my_creds.txt \
  --ideas 15 \
  --cycles 20 \
  --delay 120
```

## 🐛 Troubleshooting

### 1. Ollama Not Running
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Start Ollama
ollama serve &

# List available models
ollama list
```

**Error:** `Ollama call failed: 404`
- **Cause:** Model specified in config doesn't exist
- **Fix:** Update `orchestrator_config.json` with an available model
  ```bash
  ollama list  # Check available models
  # Update config: "ollama_model": "gemma3:4b"
  ```

### 2. Authentication Failed (401)
```bash
# Test credentials
curl -u "your_email:your_password" \
  https://api.worldquantbrain.com/users/self
```

**Error:** `Submit failed: 401 Unauthorized`
- **Cause:** Missing authentication step or invalid credentials
- **Fix:** 
  - Verify credentials in `credential.txt`
  - System now auto-calls `/authentication` endpoint
  - Check if account has API access

### 3. API Quota Exceeded (429)
**Error:** `Submit failed: 429 Too Many Requests`

- **Cause:** Daily simulation quota exceeded
- **Quota Reset:** 00:00 UTC (08:00 AM Taiwan time)
- **Solutions:**
  - Wait until quota resets (tomorrow morning)
  - Reduce `ideas_per_cycle` in config
  - Add longer `--delay` between cycles
  - Check how many simulations you've done today:
    ```bash
    ls -l logs/cycles/*.log | wc -l
    ```

### 4. Rate Limit Detection
If you see **Sharpe = -999**, check the error:
```bash
# View detailed errors
tail -20 logs/agents/simulation_agent.log

# Common error codes:
# - 401: Authentication issue
# - 403: Permission denied
# - 429: Rate limit (quota exceeded)
# - 400: Syntax error in expression
# - 405: Wrong API endpoint
```

### 5. No Hopeful Alphas
- **Lower thresholds:** Edit `sharpe_threshold_hopeful` in config (default: 0.5)
- **Check Sharpe distribution:**
  ```bash
  cat logs/cycles/*.log | grep "Sharpe=" | sort
  ```
- **Try better LLM models:** `gemma3:4b` → `qwen2.5:7b`
- **Review generated expressions:**
  ```bash
  cat data/alpha_expressions.json | jq '.[] | .expression'
  ```

### 6. Expression Syntax Errors
**Error:** `Syntax error: Unknown variable "xxx"`

- **Cause:** Field not available in selected region/universe
- **Fix:**
  - Check available fields: `ls available_components_USA/fields/`
  - Verify FactorAgent is loading components correctly:
    ```bash
    grep "Loaded.*fields" logs/agents/factor_agent.log
    ```
  - Expected output: `Loaded 1262 available fields, 66 operators`

### 7. Credential Format Issues
**Error:** `Failed to setup authentication: list index out of range`

- **Cause:** Incorrect credential file format
- **Fix:** Use JSON format:
  ```json
  ["your_email@example.com", "your_password"]
  ```

### 8. Missing Components Directory
**Error:** Few fields loaded or using fallback defaults

- **Cause:** `available_components_USA/` directory missing
- **Fix:** Run the export script:
  ```bash
  python export_available_components.py
  ```
  This will create the directory with all available fields/operators

## 📈 Performance Tips

1. **Use Better LLM Models**
   - `gemma3:4b` - Fast, good quality (recommended for testing)
   - `qwen2.5:7b` - Balanced performance
   - `qwen2.5:14b` - Best quality, slower
   - `deepseek-r1:8b` - Good for reasoning

2. **Adjust Temperature**
   - Lower (0.5-0.7): More conservative, fewer syntax errors
   - Higher (0.8-1.0): More creative, more diversity, but more errors
   - **IdeaAgent:** 0.8 (creative ideas)
   - **FactorAgent:** 0.7 (balance creativity & correctness)

3. **Enable Deduplication**
   - **Saves API quota** by skipping duplicate expressions
   - Tracks history in `data/expression_history.json`
   - Check dedup stats: `cat data/cycle_summary.json | jq '.deduplication_stats'`

4. **Batch Processing**
   - **Small batches (5-10 ideas):** Good for testing, faster iteration
   - **Large batches (20-30 ideas):** More efficient, but slower per cycle
   - **Balance with rate limits:** Don't exceed daily quota

5. **Monitor System Performance**
   ```bash
   # Check Agent timing
   grep "took" logs/orchestrator.log | tail -10
   
   # Expected timing (approximate):
   # - IdeaAgent: 5-15s (depends on LLM model)
   # - FactorAgent: 5-15s (depends on LLM model)
   # - SimulationAgent: 1-60s (depends on API response)
   # - EvalAgent: < 1s
   ```

6. **Optimize for API Quota**
   - **Track daily usage:**
     ```bash
     grep "Completed.*simulations" logs/orchestrator.log | wc -l
     ```
   - **Use deduplication** to avoid re-testing same expressions
   - **Test locally first:** Use `--ideas 1` for initial testing

## 📚 File Structure

```
consultant-agent/
├── agents/                  # Agent implementations
│   ├── base_agent.py
│   ├── idea_agent.py
│   ├── factor_agent.py
│   ├── simulation_agent.py
│   ├── eval_agent.py
│   └── orchestrator_agent.py
│
├── prompts/                 # LLM prompt templates
│   ├── idea_generation.txt
│   └── factor_construction.txt
│
├── utils/                   # Utility functions
│   ├── logging_config.py
│   └── deduplication.py
│
├── config/                  # Configuration files
│   ├── orchestrator_config.json
│   └── deduplication_config.json
│
├── data/                    # Output data files
├── logs/                    # Log files
├── available_components_USA/  # WorldQuant fields/operators
│
├── main.py                  # Main entry point
├── credential.txt           # WorldQuant credentials
└── README.md               # This file
```

## 🎓 Design Philosophy

Based on the [AlphaAgent paper](https://arxiv.org/abs/2502.16789), this system implements:

- **Multi-Agent Collaboration**: Specialized agents for each task
  - IdeaAgent: Creative hypothesis generation
  - FactorAgent: Expression construction with syntax validation
  - SimulationAgent: API interaction and result retrieval
  - EvalAgent: Performance analysis and decision-making
  - OrchestratorAgent: Workflow coordination

- **LLM-Powered Generation**: Uses Ollama for creative alpha discovery
  - Generates financially sound hypotheses
  - Converts ideas into valid WorldQuant expressions
  - Learns from successful patterns

- **Iterative Refinement**: Learning from failures
  - Tracks expression history for deduplication
  - Marks expressions for negation (Sharpe < -0.5)
  - Identifies syntax errors for refinement

- **Comprehensive Logging**: Full traceability for debugging
  - Agent-level logs for detailed debugging
  - Cycle logs for each mining round
  - Error logs for API/LLM issues
  - Performance metrics and timing

## ✅ System Status

**Last Tested:** 2025-11-02  
**Test Result:** ✅ All agents working correctly

### Component Status
- ✅ IdeaAgent: Generating high-quality financial hypotheses
- ✅ FactorAgent: Building valid WorldQuant expressions
- ✅ SimulationAgent: API authentication and submission working
- ✅ EvalAgent: Correct decision logic (hopeful/reject/negate)
- ✅ Deduplication: Expression history tracking functional
- ✅ Logging: Complete traceability across all agents

### Known Limitations
- ⚠️ **API Rate Limit:** WorldQuant has daily simulation quotas (429 error when exceeded)
- ⚠️ **LLM Dependency:** Requires Ollama running with appropriate models
- ⚠️ **Field Availability:** Some fields may not exist in all regions/universes

## 🔬 Testing

### Quick System Check
```bash
# Test all components without consuming API quota
python -c "
from agents.idea_agent import IdeaAgent
from agents.factor_agent import FactorAgent

print('Testing IdeaAgent...')
idea_agent = IdeaAgent()
ideas = idea_agent.run(count=1)
print(f'✓ Generated {len(ideas)} idea(s)')

print('Testing FactorAgent...')
factor_agent = FactorAgent()
expressions = factor_agent.run(ideas)
print(f'✓ Generated {len(expressions)} expression(s)')

print('✓ All agents functional!')
"
```

### Full System Test (consumes API quota)
```bash
# Single idea test
python main.py --mode single --ideas 1

# Check results
cat data/cycle_summary.json | jq '.[-1]'
```

### Verify Components
```bash
# Check available fields and operators
ls -lh available_components_USA/
# Expected: SUMMARY.txt, operators.txt, fields/ directory

# Count available components
cat available_components_USA/SUMMARY.txt | grep "Total"
# Expected: 1000+ fields, 60+ operators
```

## 📄 License

MIT License

## 🤝 Contributing

This is a research prototype. Feel free to customize for your needs!

### Customization Ideas
- Add new agents (e.g., BacktestAgent, PortfolioAgent)
- Implement different LLM prompts for specific strategies
- Add template-based alpha generation
- Integrate with different alpha platforms
- Build a Web UI for monitoring

## 📞 Support

**Common Issues:**
- Check `logs/orchestrator.log` for overall system flow
- Check `logs/agents/*.log` for specific agent issues
- Check `logs/cycles/*.log` for detailed cycle execution
- Review `data/simulation_results.json` for API responses

**Debugging Commands:**
```bash
# Real-time monitoring
tail -f logs/orchestrator.log

# Check last error
tail -20 logs/errors/*.log

# View last cycle details
cat logs/cycles/cycle_*.log | tail -100
```

---

**Happy Alpha Mining! 🚀📈**

