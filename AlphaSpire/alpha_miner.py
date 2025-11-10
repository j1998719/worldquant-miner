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
from agents.alpha_designer_agent import AlphaDesignerAgent
from agents.metrics_analyzer import MetricsAnalyzer
from agents.expression_analyzer import ExpressionAnalyzer
from agents.suggestion_generator import SuggestionGenerator
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
            enabled_datasets=config.get('enabled_field_datasets', []),
            enabled_operators=config.get('enabled_operators', [])
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
            'temperature': 0.5  # 提高创造力，避免重复
        }
        
        # Agent 系统（简化为 4 个专注的 agents）
        self.designer_agent = AlphaDesignerAgent(**ollama_config)  # 从 hopeful_alphas 选择表达式
        self.metrics_analyzer = MetricsAnalyzer(**ollama_config)    # 分析性能指标
        self.expression_analyzer = ExpressionAnalyzer(**ollama_config)  # 分析表达式结构
        self.suggestion_generator = SuggestionGenerator(**ollama_config)  # 生成优化建议
        
        # 结果目录
        self.results_dir = Path("results")
        self.results_dir.mkdir(exist_ok=True)
        
        # 文件路径（都在 results/ 下）
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
            'min_turnover': config.get('min_turnover', 0.1),
            'min_returns': config.get('min_returns', 0.1)
        }
        
        # 历史记录
        self.history = []
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
    
    def _check_success_criteria(self, result: AlphaResult) -> bool:
        """
        检查 alpha 是否满足所有成功标准
        
        Args:
            result: AlphaResult object
        
        Returns:
            bool: True if meets all criteria, False otherwise
        """
        meets_sharpe = result.sharpe >= self.success_criteria['min_sharpe']
        meets_fitness = result.fitness >= self.success_criteria['min_fitness']
        meets_turnover_min = result.turnover >= self.success_criteria['min_turnover']
        meets_turnover_max = result.turnover <= self.success_criteria['max_turnover']
        meets_returns = result.returns >= self.success_criteria['min_returns']
        
        return all([meets_sharpe, meets_fitness, meets_turnover_min, meets_turnover_max, meets_returns])
    
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
    
    def run(self, max_iterations: int = None):
        """
        运行主循环：不断生成和测试 alphas，直到找到满足所有 criteria 的 alpha
        
        Rule-based 策略：
        - Sharpe > 1.0 → 加入 hopeful_alphas.json，检查是否满足所有 criteria
        - Sharpe < -1.0 → 反转后加入 hopeful_alphas.json，检查是否满足所有 criteria
        - abs(Sharpe) < 1.0 → 放弃，选择新表达式
        
        Args:
            max_iterations: 最大迭代次数（None = 无限循环直到成功）
        """
        logger.info("=" * 80)
        logger.info("🚀 Alpha Miner Started (Rule-based Strategy)")
        logger.info("=" * 80)
        logger.info("📋 Decision Rules:")
        logger.info("   ✅ Sharpe > 1.0  → Add to hopeful_alphas.json")
        logger.info("   🔄 Sharpe < -1.0 → Reverse & add to hopeful_alphas.json")
        logger.info("   ❌ |Sharpe| < 1.0 → Abandon, select new expression")
        logger.info("")
        logger.info(f"🎯 WorldQuant Success Criteria (MUST meet ALL to stop):")
        logger.info(f"   Sharpe >= {self.success_criteria['min_sharpe']}")
        logger.info(f"   Fitness >= {self.success_criteria['min_fitness']}")
        logger.info(f"   {self.success_criteria['min_turnover']} <= Turnover <= {self.success_criteria['max_turnover']}")
        logger.info(f"   Returns >= {self.success_criteria['min_returns']}")
        if max_iterations:
            logger.info(f"\n⏱️  Max iterations: {max_iterations}")
        else:
            logger.info(f"\n♾️  Unlimited iterations (will run until success)")
        logger.info("=" * 80)
        
        # 从现有 history 继续（如果有）
        iteration = len(self.history)
        current_expression = None
        
        while True:  # 无限循环，直到找到成功的 alpha 或达到 max_iterations
            iteration += 1
            
            # 检查是否达到最大迭代次数
            if max_iterations and iteration > max_iterations:
                logger.info("\n" + "=" * 80)
                logger.info(f"⏱️ Reached maximum iterations ({max_iterations})")
                logger.info("=" * 80)
                break
            
            logger.info(f"\n{'=' * 80}")
            if max_iterations:
                logger.info(f"📍 Iteration {iteration}/{max_iterations}")
            else:
                logger.info(f"📍 Iteration {iteration}")
            logger.info(f"{'=' * 80}")
            
            try:
                # 收集之前尝试过的 expressions（用于避免重复）
                previous_expressions = [h['expression'] for h in self.history if 'expression' in h]
                
                # Step 1: 从 hopeful_alphas.json 中选择表达式
                logger.info("\n🎨 Step 1: Selecting Expression from Hopeful Alphas...")
                
                design_result = self.designer_agent.execute({
                    'previous_attempts': self.all_expressions
                })
                
                if not design_result['success']:
                    logger.error(f"Expression selection failed: {design_result['error']}")
                    continue
                
                alpha_design = design_result['alpha_design']
                current_expression = alpha_design['expression']
                
                # 检查重复
                if current_expression in self.all_expressions:
                    logger.warning(f"⚠️ Expression already tried: {current_expression}")
                    logger.warning("   This should not happen, but continuing...")
                    continue
                
                self.all_expressions.append(current_expression)
                logger.info(f"✅ Expression selected: {current_expression}")
                logger.info(f"   Source: {alpha_design.get('source', 'unknown')}")
                
                # 验证表达式
                validation = self.data_loader.validate_expression(current_expression)
                if not validation['valid']:
                    logger.warning(f"⚠️ Invalid expression:")
                    logger.warning(f"  Unknown operators: {validation['unknown_operators']}")
                    logger.warning(f"  Unknown fields: {validation['unknown_fields']}")
                    # 继续执行，让 WQ API 返回具体错误
                
                # Step 2: 提交模拟
                logger.info("\n⚙️ Step 2: Submitting Simulation...")
                result = self.wq_api.simulate_alpha(current_expression, self.sim_settings)
                
                if result is None:
                    logger.error("❌ Simulation failed to submit")
                    current_expression = None
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
                
                # 保存当前的 expression（用于记录 history）
                record_expression = current_expression
                
                # Rule 1: Sharpe > 1.0 → Hopeful alpha!
                if sharpe > 1.0:
                    logger.info("✅ HOPEFUL! Sharpe > 1.0")
                    logger.info("   Analyzing alpha with 3-stage pipeline...")
                    
                    # Stage 1: 分析性能指标
                    logger.info("   📊 Stage 1: Metrics Analysis...")
                    metrics_result = self.metrics_analyzer.execute({
                        'result': result,
                        'criteria': self.success_criteria
                    })
                    
                    # Stage 2: 分析表达式结构
                    logger.info("   🔍 Stage 2: Expression Analysis...")
                    expression_result = self.expression_analyzer.execute({
                        'expression': current_expression,
                        'operators_data': self.operators_data,
                        'fields_data': self.fields_data,
                        'enabled_datasets': self.enabled_datasets
                    })
                    
                    # Stage 3: 生成优化建议
                    if metrics_result['success'] and expression_result['success']:
                        logger.info("   💡 Stage 3: Generating Suggestions...")
                        suggestion_result = self.suggestion_generator.execute({
                            'expression': current_expression,
                            'metrics_analysis': metrics_result['analysis'],
                            'expression_analysis': expression_result['analysis'],
                            'operators_data': self.operators_data,
                            'fields_data': self.fields_data,
                            'enabled_datasets': self.enabled_datasets
                        })
                        
                        if suggestion_result['success']:
                            # 组合分析结果
                            analysis = {
                                'metrics': metrics_result['analysis'],
                                'expression': expression_result['analysis'],
                                'suggested_expressions': suggestion_result['suggestions']
                            }
                            
                            self.add_to_hopeful_alphas(current_expression, result, analysis)
                            logger.info(f"   ✅ Added with {len(suggestion_result['suggestions'])} suggestions")
                            
                            # 检查是否满足所有成功标准
                            if self._check_success_criteria(result):
                                logger.info("\n" + "🎉" * 40)
                                logger.info("🎉 SUCCESS! Found alpha that meets ALL criteria!")
                                logger.info("🎉" * 40)
                                logger.info(f"\n✅ Expression: {current_expression}")
                                logger.info(f"   Sharpe:   {result.sharpe:.3f} (>= {self.success_criteria['min_sharpe']}) ✅")
                                logger.info(f"   Fitness:  {result.fitness:.3f} (>= {self.success_criteria['min_fitness']}) ✅")
                                logger.info(f"   Turnover: {result.turnover:.3f} ({self.success_criteria['min_turnover']}-{self.success_criteria['max_turnover']}) ✅")
                                logger.info(f"   Returns:  {result.returns:.3f} (>= {self.success_criteria['min_returns']}) ✅")
                                logger.info(f"   Alpha ID: {result.alpha_id}")
                                logger.info("\n" + "🎉" * 40)
                                self.save_history()
                                self.print_summary()
                                return  # 成功！停止循环
                        else:
                            logger.warning(f"   ⚠️ Suggestion generation failed: {suggestion_result['error']}")
                    else:
                        logger.warning("   ⚠️ Analysis failed, skipping...")
                    
                    # 继续搜索更好的 alpha
                    current_expression = None
                
                # Rule 2: Sharpe < -1.0 → Reverse and add to hopeful!
                elif sharpe < -1.0:
                    logger.info(f"🔄 REVERSE! Sharpe={sharpe:.3f} < -1.0")
                    logger.info(f"   Multiplying by -1 would give Sharpe≈{-sharpe:.3f}")
                    
                    reversed_expression = f"(-1 * ({current_expression}))"
                    logger.info(f"   Reversed: {reversed_expression}")
                    logger.info("   Analyzing reversed alpha with 3-stage pipeline...")
                    
                    # 创建反转后的虚拟 result
                    reversed_result_data = AlphaResult(
                        alpha_id=result.alpha_id,
                        expression=reversed_expression,
                        sharpe=-result.sharpe,
                        fitness=-result.fitness,
                        turnover=result.turnover,
                        returns=-result.returns,
                        drawdown=result.drawdown,
                        margin=result.margin,
                        longCount=result.shortCount,
                        shortCount=result.longCount,
                        success=True
                    )
                    
                    # Stage 1: 分析性能指标
                    logger.info("   📊 Stage 1: Metrics Analysis...")
                    metrics_result = self.metrics_analyzer.execute({
                        'result': reversed_result_data,
                        'criteria': self.success_criteria
                    })
                    
                    # Stage 2: 分析表达式结构
                    logger.info("   🔍 Stage 2: Expression Analysis...")
                    expression_result = self.expression_analyzer.execute({
                        'expression': reversed_expression,
                        'operators_data': self.operators_data,
                        'fields_data': self.fields_data,
                        'enabled_datasets': self.enabled_datasets
                    })
                    
                    # Stage 3: 生成优化建议
                    if metrics_result['success'] and expression_result['success']:
                        logger.info("   💡 Stage 3: Generating Suggestions...")
                        suggestion_result = self.suggestion_generator.execute({
                            'expression': reversed_expression,
                            'metrics_analysis': metrics_result['analysis'],
                            'expression_analysis': expression_result['analysis'],
                            'operators_data': self.operators_data,
                            'fields_data': self.fields_data,
                            'enabled_datasets': self.enabled_datasets
                        })
                        
                        if suggestion_result['success']:
                            # 组合分析结果
                            analysis = {
                                'metrics': metrics_result['analysis'],
                                'expression': expression_result['analysis'],
                                'suggested_expressions': suggestion_result['suggestions']
                            }
                            
                            self.add_to_hopeful_alphas(reversed_expression, reversed_result_data, analysis)
                            logger.info(f"   ✅ Added reversed alpha with {len(suggestion_result['suggestions'])} suggestions")
                            
                            # 检查是否满足所有成功标准
                            if self._check_success_criteria(reversed_result_data):
                                logger.info("\n" + "🎉" * 40)
                                logger.info("🎉 SUCCESS! Found alpha that meets ALL criteria!")
                                logger.info("🎉" * 40)
                                logger.info(f"\n✅ Expression: {reversed_expression}")
                                logger.info(f"   Sharpe:   {reversed_result_data.sharpe:.3f} (>= {self.success_criteria['min_sharpe']}) ✅")
                                logger.info(f"   Fitness:  {reversed_result_data.fitness:.3f} (>= {self.success_criteria['min_fitness']}) ✅")
                                logger.info(f"   Turnover: {reversed_result_data.turnover:.3f} ({self.success_criteria['min_turnover']}-{self.success_criteria['max_turnover']}) ✅")
                                logger.info(f"   Returns:  {reversed_result_data.returns:.3f} (>= {self.success_criteria['min_returns']}) ✅")
                                logger.info(f"   Alpha ID: {reversed_result_data.alpha_id}")
                                logger.info("\n" + "🎉" * 40)
                                self.save_history()
                                self.print_summary()
                                return  # 成功！停止循环
                        else:
                            logger.warning(f"   ⚠️ Suggestion generation failed: {suggestion_result['error']}")
                    else:
                        logger.warning("   ⚠️ Analysis failed, skipping...")
                    
                    # 继续搜索
                    current_expression = None
                
                # Rule 3: abs(Sharpe) < 1.0 → Abandon, try new expression
                else:
                    logger.info(f"❌ ABANDON! abs(Sharpe)={abs(sharpe):.3f} < 1.0")
                    logger.info("   Selecting new expression...")
                    
                    # 放弃，选择新表达式
                    current_expression = None
                
                # 记录历史（详细记录）
                self.history.append({
                    'iteration': iteration,
                    'hypothesis': None,  # 不再使用 hypothesis
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
                current_expression = None
                continue
        
        # 循环结束（只有在达到 max_iterations 或用户中断时才会到达这里）
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
        
        # 初始化并运行 miner（无限循环直到成功）
        miner = AlphaMiner()
        miner.run()  # 无限循环，直到找到满足所有 criteria 的 alpha
    
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

