"""
Alpha Miner - 主循环
协调所有 Agents 实现迭代优化
"""
import logging
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from core.wq_api import WorldQuantAPI, SimulationSettings, AlphaResult
from core.data_loader import DataLoader
from agents.hypothesis_agent import HypothesisAgent
from agents.alpha_designer_agent import AlphaDesignerAgent
from agents.evaluator_agent import EvaluatorAgent
from utils.config_loader import ConfigLoader

# 设置日志
logging.basicConfig(
    level=logging.INFO,  # 使用 INFO 级别（如需调试可改为 DEBUG）
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('alpha_miner.log')
    ]
)
logger = logging.getLogger(__name__)


class AlphaMiner:
    """
    Alpha Miner 主类
    实现迭代优化循环：生成假设 -> 设计表达式 -> 模拟 -> 评估 -> 优化/重新生成
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化 Alpha Miner
        
        Args:
            config: 配置字典，如果为 None 则从 config.yaml 加载
        """
        if config is None:
            config = ConfigLoader.all()
        
        self.config = config
        
        # 初始化 WQ API
        self.wq_api = WorldQuantAPI(
            username=config['worldquant_account'],
            password=config['worldquant_password']
        )
        
        # 初始化数据加载器
        self.data_loader = DataLoader(
            enabled_datasets=config.get('enabled_field_datasets', [])
        )
        
        # 加载 operators 和 fields（完整数据）
        logger.info("Loading operators and fields...")
        self.operators_data = self.data_loader.load_operators()  # 完整的 operators.json 数据
        self.fields_data = self.data_loader.load_fields()  # 根据 enabled_field_datasets 加载的完整 fields 数据
        self.enabled_datasets = config.get('enabled_field_datasets', [])
        
        logger.info(f"📚 Loaded {len(self.operators_data)} operators")
        logger.info(f"📚 Loaded {len(self.fields_data)} fields from datasets: {', '.join(self.enabled_datasets)}")
        
        # 初始化 Agents
        ollama_config = {
            'ollama_url': config.get('ollama_url', 'http://localhost:11434'),
            'ollama_model': config.get('ollama_model', 'gemma3:1b'),
            'temperature': 0.2
        }
        
        self.hypothesis_agent = HypothesisAgent(**ollama_config)
        self.designer_agent = AlphaDesignerAgent(**ollama_config)
        self.evaluator_agent = EvaluatorAgent(**ollama_config)
        
        # 结果目录
        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)
        
        # 文件路径（都在 results/ 下）
        self.hypothesis_file = self.results_dir / "hypothesis.json"
        self.history_file = self.results_dir / "history.json"
        self.hopeful_alphas_file = self.results_dir / "hopeful_alphas.json"
        
        # 模拟设置
        self.sim_settings = SimulationSettings(
            region=config.get('worldquant_region', 'USA'),
            universe=config.get('worldquant_universe', 'TOP3000'),
            delay=1,
            neutralization="SUBINDUSTRY",
            truncation=0.08
        )
        
        # 成功标准（WorldQuant Brain's criteria - for reference only）
        self.success_criteria = {
            'min_sharpe': config.get('min_sharpe', 1.25),
            'min_fitness': config.get('min_fitness', 1.0),
            'max_turnover': config.get('max_turnover', 0.7),
            'min_turnover': config.get('min_turnover', 0.01),
            'min_returns': config.get('min_returns', 0.0)
        }
        
        # 历史记录
        self.history = []
        self.all_hypotheses = []  # 所有生成过的 hypothesis
        self.all_expressions = []  # 所有尝试过的 expression（防重复）
        
        # 加载已有的历史记录（防重复）
        self._load_existing_history()
    
    def _validate_recommendations(self, data: Dict, data_type: str = "hypothesis") -> Dict[str, Any]:
        """
        Rule-based 验证 recommended_fields 和 recommended_operators
        
        Args:
            data: hypothesis 或 analysis 字典
            data_type: "hypothesis" 或 "analysis"
        
        Returns:
            {
                'valid': bool,
                'reason': str (if invalid),
                'invalid_fields': List[str],
                'invalid_operators': List[str]
            }
        """
        # 从完整数据中提取 field IDs 和 operator names
        available_fields = set(f.get('id', f.get('name', '')) for f in self.fields_data)
        available_operators = set(op.get('name', '') for op in self.operators_data)
        
        recommended_fields = data.get('recommended_fields', [])
        recommended_operators = data.get('recommended_operators', [])
        
        # 检查 fields
        invalid_fields = [f for f in recommended_fields if f not in available_fields]
        
        # 检查 operators
        invalid_operators = [op for op in recommended_operators if op not in available_operators]
        
        if invalid_fields or invalid_operators:
            reason = []
            if invalid_fields:
                reason.append(f"{len(invalid_fields)}/{len(recommended_fields)} fields not found")
            if invalid_operators:
                reason.append(f"{len(invalid_operators)}/{len(recommended_operators)} operators not found")
            
            return {
                'valid': False,
                'reason': ', '.join(reason),
                'invalid_fields': invalid_fields,
                'invalid_operators': invalid_operators
            }
        
        return {'valid': True}
    
    def _validate_hypothesis(self, hypothesis: Dict) -> Dict[str, Any]:
        """
        验证 hypothesis（使用通用验证方法）
        """
        return self._validate_recommendations(hypothesis, "hypothesis")
    
    def _validate_analysis(self, analysis: Dict) -> Dict[str, Any]:
        """
        验证 evaluator 生成的 analysis（使用通用验证方法）
        """
        return self._validate_recommendations(analysis, "analysis")
    
    def _load_existing_history(self):
        """
        从 history.json 和 hypothesis.json 加载已有数据（防重复）
        """
        # 加载 history.json
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    existing_history = json.load(f)
                
                # 加载到 self.history（用于继续 iteration 计数）
                self.history = existing_history
                
                # 提取所有已尝试过的 expressions
                for record in existing_history:
                    expr = record.get('expression')
                    if expr and expr not in self.all_expressions:
                        self.all_expressions.append(expr)
                
                logger.info(f"📋 Loaded {len(existing_history)} history records, {len(self.all_expressions)} unique expressions")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load history.json: {e}")
        
        # 加载 hypothesis.json
        if self.hypothesis_file.exists():
            try:
                with open(self.hypothesis_file, 'r', encoding='utf-8') as f:
                    existing_hypotheses = json.load(f)
                
                self.all_hypotheses = existing_hypotheses
                logger.info(f"📋 Loaded {len(existing_hypotheses)} existing hypotheses")
            except Exception as e:
                logger.warning(f"⚠️ Failed to load hypothesis.json: {e}")
    
    def run(self, max_iterations: int = 100):
        """
        运行主循环：不断生成和测试 alphas
        
        Rule-based 策略：
        - Sharpe > 1.0 → 加入 hopeful_alphas.json，继续搜索
        - Sharpe < -1.0 → 反转后加入 hopeful_alphas.json，继续搜索
        - abs(Sharpe) < 1.0 → 放弃，生成新假设
        
        Args:
            max_iterations: 最大迭代次数
        """
        logger.info("=" * 80)
        logger.info("🚀 Alpha Miner Started (Rule-based Strategy)")
        logger.info("=" * 80)
        logger.info("📋 Decision Rules:")
        logger.info("   ✅ Sharpe > 1.0  → Add to hopeful_alphas.json")
        logger.info("   🔄 Sharpe < -1.0 → Reverse & add to hopeful_alphas.json")
        logger.info("   ❌ |Sharpe| < 1.0 → Abandon, generate new hypothesis")
        logger.info("")
        logger.info(f"🎯 WorldQuant Success Criteria (for reference):")
        logger.info(f"   Sharpe >= {self.success_criteria['min_sharpe']}")
        logger.info(f"   Fitness >= {self.success_criteria['min_fitness']}")
        logger.info(f"   {self.success_criteria['min_turnover']} <= Turnover <= {self.success_criteria['max_turnover']}")
        logger.info("=" * 80)
        
        # 从现有 history 继续（如果有）
        iteration = len(self.history)
        current_hypothesis = None
        current_expression = None
        previous_failures = []
        
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"\n{'=' * 80}")
            logger.info(f"📍 Iteration {iteration}/{max_iterations}")
            logger.info(f"{'=' * 80}")
            
            try:
                # 收集之前尝试过的 expressions（用于避免重复）
                previous_expressions = [h['expression'] for h in self.history if 'expression' in h]
                
                # Step 1: 生成或使用现有假设
                if current_hypothesis is None:
                    logger.info("\n🧠 Step 1: Generating Hypothesis...")
                    
                    hypothesis_result = self.hypothesis_agent.execute({
                        'previous_failures': previous_failures,
                        'operators_data': self.operators_data,
                        'fields_data': self.fields_data,
                        'enabled_datasets': self.enabled_datasets
                    })
                    
                    if not hypothesis_result['success']:
                        logger.error(f"Hypothesis generation failed: {hypothesis_result['error']}")
                        continue
                    
                    current_hypothesis = hypothesis_result['hypothesis']
                    logger.info(f"✅ Hypothesis: {current_hypothesis['hypothesis']}")
                    
                    # Rule-based 验证：检查 recommended fields 和 operators 是否真实存在
                    validation_result = self._validate_hypothesis(current_hypothesis)
                    if not validation_result['valid']:
                        logger.warning(f"⚠️ Hypothesis validation failed: {validation_result['reason']}")
                        logger.warning(f"   Invalid fields: {validation_result.get('invalid_fields', [])}")
                        logger.warning(f"   Invalid operators: {validation_result.get('invalid_operators', [])}")
                        logger.warning("   Regenerating hypothesis...")
                        current_hypothesis = None
                        continue
                    
                    # 保存 hypothesis
                    self.save_hypothesis(current_hypothesis)
                
                # Step 2: 设计 Alpha 表达式
                logger.info("\n🎨 Step 2: Designing Alpha Expression...")
                
                design_result = self.designer_agent.execute({
                    'hypothesis': current_hypothesis,
                    'previous_attempts': self.all_expressions[-20:],
                    'operators_data': self.operators_data,
                    'fields_data': self.fields_data,
                    'enabled_datasets': self.enabled_datasets
                })
                
                if not design_result['success']:
                    logger.error(f"Alpha design failed: {design_result['error']}")
                    current_hypothesis = None
                    continue
                
                alpha_design = design_result['alpha_design']
                current_expression = alpha_design['expression']
                
                # 检查重复
                if current_expression in self.all_expressions:
                    logger.warning(f"⚠️ Expression already tried: {current_expression}")
                    logger.warning("   Generating new hypothesis...")
                    current_hypothesis = None
                    current_expression = None
                    continue
                
                self.all_expressions.append(current_expression)
                logger.info(f"✅ Expression: {current_expression} (unique)")
                
                # 验证表达式
                validation = self.data_loader.validate_expression(current_expression)
                if not validation['valid']:
                    logger.warning(f"⚠️ Invalid expression:")
                    logger.warning(f"  Unknown operators: {validation['unknown_operators']}")
                    logger.warning(f"  Unknown fields: {validation['unknown_fields']}")
                    # 继续执行，让 WQ API 返回具体错误
                
                # Step 3: 提交模拟
                logger.info("\n⚙️ Step 3: Submitting Simulation...")
                result = self.wq_api.simulate_alpha(current_expression, self.sim_settings)
                
                if result is None:
                    logger.error("❌ Simulation failed to submit")
                    # 放弃当前 hypothesis，生成新的
                    current_hypothesis = None
                    current_expression = None
                    previous_failures.append(current_expression if current_expression else "simulation_failed")
                    continue
                
                # 显示结果
                logger.info(f"\n📊 Results:")
                logger.info(f"  Sharpe:   {result.sharpe:.3f}")
                logger.info(f"  Fitness:  {result.fitness:.3f}")
                logger.info(f"  Turnover: {result.turnover:.3f}")
                logger.info(f"  Returns:  {result.returns:.3f}")
                
                # 预判决策
                if result.sharpe > 1.0:
                    logger.info(f"  ✅ Sharpe > 1.0 → Will add to hopeful!")
                elif result.sharpe < -1.0:
                    logger.info(f"  🔄 Sharpe < -1.0 → Will reverse & add to hopeful!")
                else:
                    logger.info(f"  ❌ |Sharpe| < 1.0 → Will abandon")
                
                # Step 4: Rule-based 决策
                logger.info("\n📈 Step 4: Rule-based Decision...")
                
                sharpe = result.sharpe
                
                # 保存当前的 hypothesis 和 expression（用于记录 history）
                record_hypothesis = current_hypothesis
                record_expression = current_expression
                
                # Rule 1: Sharpe > 1.0 → Hopeful alpha!
                if sharpe > 1.0:
                    logger.info("✅ HOPEFUL! Sharpe > 1.0")
                    logger.info("   Analyzing alpha...")
                    
                    # 调用 Evaluator 生成分析
                    eval_result = self.evaluator_agent.execute({
                        'expression': current_expression,
                        'result': result,
                        'hypothesis': current_hypothesis,
                        'operators_data': self.operators_data,
                        'fields_data': self.fields_data,
                        'enabled_datasets': self.enabled_datasets
                    })
                    
                    if eval_result['success']:
                        analysis = eval_result['analysis']
                        
                        # Rule-based 验证 analysis 的 recommended fields 和 operators
                        validation_result = self._validate_analysis(analysis)
                        if not validation_result['valid']:
                            logger.warning(f"⚠️ Analysis validation failed: {validation_result['reason']}")
                            logger.warning(f"   Invalid fields: {validation_result.get('invalid_fields', [])}")
                            logger.warning(f"   Invalid operators: {validation_result.get('invalid_operators', [])}")
                            logger.warning("   Saving without invalid recommendations...")
                            # 移除无效的 recommendations（从完整数据中提取）
                            valid_fields = set(f.get('id', f.get('name', '')) for f in self.fields_data)
                            valid_operators = set(op.get('name', '') for op in self.operators_data)
                            analysis['recommended_fields'] = [f for f in analysis.get('recommended_fields', []) 
                                                             if f in valid_fields]
                            analysis['recommended_operators'] = [op for op in analysis.get('recommended_operators', []) 
                                                                if op in valid_operators]
                        
                        self.add_to_hopeful_alphas(current_expression, result, analysis)
                    
                    # 继续搜索更好的 alpha
                    current_hypothesis = None
                    current_expression = None
                
                # Rule 2: Sharpe < -1.0 → Reverse and add to hopeful!
                elif sharpe < -1.0:
                    logger.info(f"🔄 REVERSE! Sharpe={sharpe:.3f} < -1.0")
                    logger.info(f"   Multiplying by -1 would give Sharpe≈{-sharpe:.3f}")
                    
                    reversed_expression = f"(-1 * ({current_expression}))"
                    logger.info(f"   Reversed: {reversed_expression}")
                    
                    # 调用 Evaluator 生成分析（使用反转后的 Sharpe）
                    eval_result = self.evaluator_agent.execute({
                        'expression': reversed_expression,
                        'result': result,
                        'hypothesis': current_hypothesis,
                        'operators_data': self.operators_data,
                        'fields_data': self.fields_data,
                        'enabled_datasets': self.enabled_datasets
                    })
                    
                    if eval_result['success']:
                        analysis = eval_result['analysis']
                        
                        # Rule-based 验证 analysis 的 recommended fields 和 operators
                        validation_result = self._validate_analysis(analysis)
                        if not validation_result['valid']:
                            logger.warning(f"⚠️ Analysis validation failed: {validation_result['reason']}")
                            logger.warning(f"   Invalid fields: {validation_result.get('invalid_fields', [])}")
                            logger.warning(f"   Invalid operators: {validation_result.get('invalid_operators', [])}")
                            logger.warning("   Saving without invalid recommendations...")
                            # 移除无效的 recommendations（从完整数据中提取）
                            valid_fields = set(f.get('id', f.get('name', '')) for f in self.fields_data)
                            valid_operators = set(op.get('name', '') for op in self.operators_data)
                            analysis['recommended_fields'] = [f for f in analysis.get('recommended_fields', []) 
                                                             if f in valid_fields]
                            analysis['recommended_operators'] = [op for op in analysis.get('recommended_operators', []) 
                                                                if op in valid_operators]
                        
                        # 创建反转后的虚拟 result
                        reversed_result_data = AlphaResult(
                            alpha_id=result.alpha_id,
                            expression=reversed_expression,
                            sharpe=-result.sharpe,
                            fitness=-result.fitness,  # fitness 通常也会反转
                            turnover=result.turnover,
                            returns=-result.returns,
                            drawdown=result.drawdown,
                            margin=result.margin,
                            longCount=result.shortCount,
                            shortCount=result.longCount,
                            success=True
                        )
                        self.add_to_hopeful_alphas(reversed_expression, reversed_result_data, analysis)
                    
                    # 继续搜索
                    current_hypothesis = None
                    current_expression = None
                
                # Rule 3: abs(Sharpe) < 1.0 → Abandon, try new hypothesis
                else:
                    logger.info(f"❌ ABANDON! abs(Sharpe)={abs(sharpe):.3f} < 1.0")
                    logger.info("   Generating new hypothesis...")
                    
                    # 放弃，生成新假设
                    previous_failures.append(record_hypothesis['hypothesis'] if record_hypothesis else record_expression)
                    current_hypothesis = None
                    current_expression = None
                
                # 记录历史（详细记录）
                self.history.append({
                    'iteration': iteration,
                    'hypothesis': record_hypothesis,  # 包含 recommended_operators, fields, params
                    'expression': record_expression,
                    'result': {
                        'sharpe': result.sharpe,
                        'fitness': result.fitness,
                        'turnover': result.turnover,
                        'returns': result.returns,
                        'alpha_id': result.alpha_id,
                        'success': result.success,
                        'error_message': result.error_message
                    },
                    'decision': 'HOPEFUL' if sharpe > 1.0 else ('REVERSE' if sharpe < -1.0 else 'ABANDON'),
                    'timestamp': datetime.now().isoformat()
                })
                
                # 实时保存 history
                self.save_history()
            
            except KeyboardInterrupt:
                logger.info("\n⚠️ Interrupted by user")
                self.save_history()
                break
            
            except Exception as e:
                logger.error(f"❌ Error in iteration {iteration}: {e}", exc_info=True)
                # 继续下一次迭代
                current_hypothesis = None
                current_expression = None
                continue
        
        # 循环结束
        if iteration >= max_iterations:
            logger.info("\n" + "=" * 80)
            logger.info(f"⏱️ Reached maximum iterations ({max_iterations})")
            logger.info("=" * 80)
        
        self.print_summary()
    
    def add_to_hopeful_alphas(self, expression: str, result: AlphaResult, analysis: Dict):
        """
        添加 alpha 到 hopeful_alphas.json
        
        Args:
            expression: Alpha 表达式
            result: 模拟结果
            analysis: Evaluator 的分析
        """
        # 加载现有数据
        hopeful_alphas = []
        if self.hopeful_alphas_file.exists():
            with open(self.hopeful_alphas_file, 'r', encoding='utf-8') as f:
                hopeful_alphas = json.load(f)
        
        # 添加新数据
        hopeful_alpha = {
            'expression': expression,
            'result': {
                'sharpe': result.sharpe,
                'fitness': result.fitness,
                'turnover': result.turnover,
                'returns': result.returns,
                'alpha_id': result.alpha_id
            },
            'analysis': analysis,
            'timestamp': datetime.now().isoformat()
        }
        
        hopeful_alphas.append(hopeful_alpha)
        
        # 保存
        with open(self.hopeful_alphas_file, 'w', encoding='utf-8') as f:
            json.dump(hopeful_alphas, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Added to hopeful_alphas.json (total: {len(hopeful_alphas)})")
    
    def save_hypothesis(self, hypothesis: Dict):
        """
        保存 hypothesis 到 hypothesis.json
        """
        # 加载现有 hypotheses
        if self.hypothesis_file.exists():
            with open(self.hypothesis_file, 'r', encoding='utf-8') as f:
                hypotheses = json.load(f)
        else:
            hypotheses = []
        
        # 添加时间戳
        hypothesis['timestamp'] = datetime.now().isoformat()
        
        # 添加到列表
        hypotheses.append(hypothesis)
        self.all_hypotheses.append(hypothesis)
        
        # 保存
        with open(self.hypothesis_file, 'w', encoding='utf-8') as f:
            json.dump(hypotheses, f, indent=2, ensure_ascii=False)
    
    def save_history(self):
        """
        实时保存 history 到 history.json
        """
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)
    
    def print_summary(self):
        """打印总结"""
        logger.info("\n" + "=" * 80)
        logger.info("📊 Summary")
        logger.info("=" * 80)
        logger.info(f"Total iterations: {len(self.history)}")
        logger.info(f"Unique expressions tried: {len(self.all_expressions)}")
        logger.info(f"Hypotheses generated: {len(self.all_hypotheses)}")
        
        # 读取 hopeful alphas
        if self.hopeful_alphas_file.exists():
            with open(self.hopeful_alphas_file, 'r', encoding='utf-8') as f:
                hopeful_alphas = json.load(f)
            logger.info(f"Hopeful alphas: {len(hopeful_alphas)}")
        else:
            logger.info(f"Hopeful alphas: 0")
        
        # 结果文件
        logger.info("\n📁 Results saved to:")
        logger.info(f"   - {self.history_file}")
        logger.info(f"   - {self.hypothesis_file}")
        logger.info(f"   - {self.hopeful_alphas_file}")
        
        # 显示最佳尝试
        if self.history:
            # 从 history 中找最高 Sharpe
            valid_history = [h for h in self.history if h.get('result', {}).get('success', False)]
            if valid_history:
                best = max(valid_history, key=lambda x: abs(x['result']['sharpe']))
                logger.info(f"\n📈 Best Sharpe in this run:")
                logger.info(f"   Expression: {best['expression']}")
                logger.info(f"   Sharpe: {best['result']['sharpe']:.3f}")
                logger.info(f"   Decision: {best.get('decision', 'N/A')}")


def preload_model(model_name: str = "gemma3:1b"):
    """
    预加载 Ollama 模型
    通过运行模型然后立即退出来确保模型已加载到内存
    """
    import subprocess
    
    logger.info(f"🔄 Preloading model: {model_name}...")
    try:
        # 使用 echo '/bye' | ollama run 来自动启动并退出
        process = subprocess.Popen(
            ['ollama', 'run', model_name],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # 发送 /bye 命令并等待退出
        stdout, stderr = process.communicate(input='/bye\n', timeout=30)
        
        if process.returncode == 0 or 'bye' in stdout.lower():
            logger.info(f"✅ Model {model_name} loaded and ready")
        else:
            logger.warning(f"⚠️ Model preload completed with return code {process.returncode}")
    
    except subprocess.TimeoutExpired:
        process.kill()
        logger.warning(f"⚠️ Model preload timed out, but continuing...")
    except FileNotFoundError:
        logger.warning(f"⚠️ 'ollama' command not found. Model will be loaded on first use.")
    except Exception as e:
        logger.warning(f"⚠️ Could not preload model: {e}. Model will be loaded on first use.")


def main():
    """主入口"""
    try:
        # 加载配置以获取模型名称
        config = ConfigLoader.all()
        model_name = config.get('ollama_model', 'gemma3:1b')
        
        # 预加载模型
        preload_model(model_name)
        
        # 初始化并运行 miner
        miner = AlphaMiner()
        miner.run(max_iterations=100)
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

