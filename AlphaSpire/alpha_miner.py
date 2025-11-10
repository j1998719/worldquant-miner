"""
Alpha Miner - 主循环
协调所有 Agents 实现迭代优化
"""
import logging
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

from core.wq_api import WorldQuantAPI, SimulationSettings, AlphaResult
from core.data_loader import DataLoader
from agents.hypothesis_agent import HypothesisAgent
from agents.alpha_designer_agent import AlphaDesignerAgent
from agents.evaluator_agent import EvaluatorAgent
from agents.optimizer_agent import OptimizerAgent
from utils.config_loader import ConfigLoader

# 设置日志
logging.basicConfig(
    level=logging.INFO,
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
            config = ConfigLoader.get_all()
        
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
        
        # 加载 operators 和 fields
        logger.info("Loading operators and fields...")
        self.data_loader.load_operators()
        self.data_loader.load_fields()
        
        # 初始化 Agents
        ollama_config = {
            'ollama_url': config.get('ollama_url', 'http://localhost:11434'),
            'ollama_model': config.get('ollama_model', 'gemma3:1b'),
            'temperature': 0.2
        }
        
        self.hypothesis_agent = HypothesisAgent(**ollama_config)
        self.designer_agent = AlphaDesignerAgent(**ollama_config)
        self.evaluator_agent = EvaluatorAgent(**ollama_config)
        self.optimizer_agent = OptimizerAgent(**ollama_config)
        
        # 模拟设置
        self.sim_settings = SimulationSettings(
            region=config.get('worldquant_region', 'USA'),
            universe=config.get('worldquant_universe', 'TOP3000'),
            delay=1,
            neutralization="SUBINDUSTRY",
            truncation=0.08
        )
        
        # 成功标准（WorldQuant Brain's criteria）
        self.success_criteria = {
            'min_sharpe': config.get('min_sharpe', 1.25),
            'min_fitness': config.get('min_fitness', 1.0),
            'max_turnover': config.get('max_turnover', 0.7),
            'min_turnover': config.get('min_turnover', 0.01),
            'min_returns': config.get('min_returns', 0.0)
        }
        
        # 优化阈值（值得继续优化的"hopeful" alphas）
        self.optimize_criteria = {
            'min_sharpe': config.get('optimize_min_sharpe', 0.5),
            'min_fitness': config.get('optimize_min_fitness', 0.6)
        }
        
        # 历史记录
        self.history = []
        self.successful_alphas = []
        
        # 结果目录
        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)
    
    def run(self, max_iterations: int = 100, max_optimize_attempts: int = 3):
        """
        运行主循环直到找到成功的 alpha 或达到最大迭代次数
        
        Args:
            max_iterations: 最大迭代次数
            max_optimize_attempts: 每个假设最多优化次数
        """
        logger.info("=" * 80)
        logger.info("🚀 Alpha Miner Started")
        logger.info(f"🎯 WorldQuant Success Criteria:")
        logger.info(f"   Sharpe >= {self.success_criteria['min_sharpe']}")
        logger.info(f"   Fitness >= {self.success_criteria['min_fitness']}")
        logger.info(f"   {self.success_criteria['min_turnover']} <= Turnover <= {self.success_criteria['max_turnover']}")
        logger.info(f"🔧 Optimization Threshold (Hopeful):")
        logger.info(f"   Sharpe >= {self.optimize_criteria['min_sharpe']}, Fitness >= {self.optimize_criteria['min_fitness']}")
        logger.info("=" * 80)
        
        iteration = 0
        current_hypothesis = None
        current_expression = None
        optimize_count = 0
        previous_failures = []
        
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"\n{'=' * 80}")
            logger.info(f"📍 Iteration {iteration}/{max_iterations}")
            logger.info(f"{'=' * 80}")
            
            try:
                # Step 1: 生成或使用现有假设
                if current_hypothesis is None:
                    logger.info("\n🧠 Step 1: Generating Hypothesis...")
                    
                    hypothesis_result = self.hypothesis_agent.execute({
                        'previous_failures': previous_failures,
                        'focus_area': ''
                    })
                    
                    if not hypothesis_result['success']:
                        logger.error(f"Hypothesis generation failed: {hypothesis_result['error']}")
                        continue
                    
                    current_hypothesis = hypothesis_result['hypothesis']
                    optimize_count = 0
                    logger.info(f"✅ Hypothesis: {current_hypothesis['hypothesis']}")
                
                # Step 2: 设计或优化 Alpha 表达式
                if optimize_count == 0:
                    logger.info("\n🎨 Step 2: Designing Alpha Expression...")
                    
                    design_result = self.designer_agent.execute({
                        'hypothesis': current_hypothesis,
                        'available_operators': self.data_loader.get_operator_names(),
                        'available_fields': self.data_loader.get_field_ids(),
                        'previous_attempts': []
                    })
                    
                    if not design_result['success']:
                        logger.error(f"Alpha design failed: {design_result['error']}")
                        current_hypothesis = None
                        continue
                    
                    alpha_design = design_result['alpha_design']
                    current_expression = alpha_design['expression']
                    logger.info(f"✅ Expression: {current_expression}")
                
                else:
                    logger.info(f"\n🔧 Step 2: Optimizing Expression (Attempt {optimize_count}/{max_optimize_attempts})...")
                    
                    # 获取上一次的结果
                    last_result = self.history[-1]['result'] if self.history else None
                    last_evaluation = self.history[-1]['evaluation'] if self.history else {}
                    
                    optimize_result = self.optimizer_agent.execute({
                        'expression': current_expression,
                        'result': last_result,
                        'evaluation': last_evaluation,
                        'available_operators': self.data_loader.get_operator_names()
                    })
                    
                    if not optimize_result['success']:
                        logger.error(f"Optimization failed: {optimize_result['error']}")
                        # 优化失败，生成新假设
                        current_hypothesis = None
                        current_expression = None
                        continue
                    
                    optimization = optimize_result['optimization']
                    current_expression = optimization['optimized_expression']
                    logger.info(f"✅ Optimized: {current_expression}")
                
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
                    optimize_count += 1
                    if optimize_count >= max_optimize_attempts:
                        # 达到最大优化次数，生成新假设
                        current_hypothesis = None
                        current_expression = None
                        previous_failures.append(current_hypothesis['hypothesis'] if current_hypothesis else current_expression)
                    continue
                
                # 显示结果
                logger.info(f"\n📊 Results:")
                logger.info(f"  Sharpe:   {result.sharpe:.3f} (target >= {self.success_criteria['min_sharpe']:.2f})")
                logger.info(f"  Fitness:  {result.fitness:.3f} (target >= {self.success_criteria['min_fitness']:.2f})")
                logger.info(f"  Turnover: {result.turnover:.3f} (target {self.success_criteria['min_turnover']:.2f}-{self.success_criteria['max_turnover']:.2f})")
                logger.info(f"  Returns:  {result.returns:.3f}")
                
                # 判断是否达标
                passes = result.passes_criteria(**self.success_criteria)
                hopeful = result.is_hopeful(**self.optimize_criteria)
                if passes:
                    logger.info(f"  ✅ PASSES all WorldQuant criteria!")
                elif hopeful:
                    logger.info(f"  🔧 Hopeful - worth optimizing")
                else:
                    logger.info(f"  ❌ Below threshold")
                
                # Step 4: 评估结果
                logger.info("\n📈 Step 4: Evaluating Results...")
                
                eval_result = self.evaluator_agent.execute({
                    'result': result,
                    'expression': current_expression,
                    'hypothesis': current_hypothesis,
                    'iteration': optimize_count
                })
                
                if not eval_result['success']:
                    logger.error(f"Evaluation failed: {eval_result['error']}")
                    continue
                
                evaluation = eval_result['evaluation']
                decision = evaluation['decision']
                
                logger.info(f"✅ Decision: {decision}")
                logger.info(f"   Analysis: {evaluation.get('analysis', '')}")
                
                # 记录历史
                self.history.append({
                    'iteration': iteration,
                    'hypothesis': current_hypothesis,
                    'expression': current_expression,
                    'result': result,
                    'evaluation': evaluation,
                    'timestamp': datetime.now().isoformat()
                })
                
                # Step 5: 根据决策执行下一步
                if decision == "ACCEPT":
                    # 🎉 成功！找到好的 alpha
                    logger.info("\n" + "=" * 80)
                    logger.info("🎉 SUCCESS! Found a good alpha!")
                    logger.info("=" * 80)
                    logger.info(f"Expression: {current_expression}")
                    logger.info(f"Sharpe: {result.sharpe:.3f}")
                    logger.info(f"Fitness: {result.fitness:.3f}")
                    logger.info(f"Iterations: {iteration}")
                    
                    # 保存成功的 alpha
                    self.successful_alphas.append({
                        'expression': current_expression,
                        'hypothesis': current_hypothesis,
                        'result': {
                            'sharpe': result.sharpe,
                            'fitness': result.fitness,
                            'turnover': result.turnover,
                            'returns': result.returns,
                            'alpha_id': result.alpha_id
                        },
                        'iteration': iteration,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    self.save_results()
                    break
                
                elif decision == "OPTIMIZE":
                    # 尝试优化
                    optimize_count += 1
                    
                    if optimize_count >= max_optimize_attempts:
                        logger.info(f"⚠️ Reached max optimization attempts ({max_optimize_attempts})")
                        previous_failures.append(current_hypothesis['hypothesis'])
                        current_hypothesis = None
                        current_expression = None
                    
                else:  # NEW_HYPOTHESIS
                    # 生成新假设
                    logger.info("🔄 Starting fresh with new hypothesis...")
                    previous_failures.append(current_hypothesis['hypothesis'] if current_hypothesis else current_expression)
                    current_hypothesis = None
                    current_expression = None
                
                # 保存中间结果
                if iteration % 5 == 0:
                    self.save_results()
            
            except KeyboardInterrupt:
                logger.info("\n⚠️ Interrupted by user")
                self.save_results()
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
        
        self.save_results()
        self.print_summary()
    
    def save_results(self):
        """保存结果到文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存历史
        history_file = self.results_dir / f"history_{timestamp}.json"
        with open(history_file, 'w', encoding='utf-8') as f:
            # 转换 AlphaResult 为字典
            history_serializable = []
            for record in self.history:
                record_copy = record.copy()
                if 'result' in record_copy:
                    result = record_copy['result']
                    record_copy['result'] = {
                        'sharpe': result.sharpe,
                        'fitness': result.fitness,
                        'turnover': result.turnover,
                        'returns': result.returns,
                        'success': result.success,
                        'error_message': result.error_message
                    }
                history_serializable.append(record_copy)
            
            json.dump(history_serializable, f, indent=2, ensure_ascii=False)
        
        logger.info(f"💾 Saved history to {history_file}")
        
        # 保存成功的 alphas
        if self.successful_alphas:
            success_file = self.results_dir / f"successful_alphas_{timestamp}.json"
            with open(success_file, 'w', encoding='utf-8') as f:
                json.dump(self.successful_alphas, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 Saved successful alphas to {success_file}")
    
    def print_summary(self):
        """打印总结"""
        logger.info("\n" + "=" * 80)
        logger.info("📊 Summary")
        logger.info("=" * 80)
        logger.info(f"Total iterations: {len(self.history)}")
        logger.info(f"Successful alphas: {len(self.successful_alphas)}")
        
        if self.successful_alphas:
            logger.info("\n🎉 Successful Alphas:")
            for i, alpha in enumerate(self.successful_alphas, 1):
                logger.info(f"\n{i}. {alpha['expression']}")
                logger.info(f"   Sharpe: {alpha['result']['sharpe']:.3f}")
                logger.info(f"   Fitness: {alpha['result']['fitness']:.3f}")
                logger.info(f"   Found at iteration: {alpha['iteration']}")
        else:
            logger.info("\n⚠️ No successful alphas found")
            
            # 显示最佳尝试
            if self.history:
                best = max(self.history, key=lambda x: x['result'].sharpe if x['result'].success else 0)
                logger.info(f"\n📈 Best attempt:")
                logger.info(f"   Expression: {best['expression']}")
                logger.info(f"   Sharpe: {best['result'].sharpe:.3f}")
                logger.info(f"   Fitness: {best['result'].fitness:.3f}")


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
        config = ConfigLoader.get_all()
        model_name = config.get('ollama_model', 'gemma3:1b')
        
        # 预加载模型
        preload_model(model_name)
        
        # 初始化并运行 miner
        miner = AlphaMiner()
        miner.run(max_iterations=100, max_optimize_attempts=3)
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

