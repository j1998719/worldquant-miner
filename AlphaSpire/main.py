import random
from pathlib import Path

from evaluator.backtest_with_wq import run_backtest_by_wq_api
from evaluator.backtest_with_wq_mul import run_backtest_mul_by_wq_api
from researcher.generate_alpha import generate_alphas_from_template
from researcher.generate_template import from_post_to_template
from utils.template_field_gener import generate_template_fields_v2
from utils.template_op_gener import generate_template_ops
from utils.wq_info_loader import OpAndFeature


if __name__ == "__main__":
    print("="*80)
    print("AlphaSpire - Alpha 研究和评估流程 (使用 Ollama)")
    print("="*80)
    
    # ============================================
    # 阶段 1: 准备组件库
    # ============================================
    print("\n📦 阶段 1: 加载 WorldQuant 组件...")
    opAndFeature = OpAndFeature()
    opAndFeature.get_operators()
    opAndFeature.get_data_fields()
    
    generate_template_ops()
    generate_template_fields_v2()
    print("✅ 组件库准备完成")

    # ============================================
    # 阶段 2: Alpha 研究（从 helpful_posts 开始）
    # ============================================
    print("\n🔬 阶段 2: Alpha 研究 - 从帖子生成模板...")
    POSTS_DIR = Path("data/wq_posts/helpful_posts")
    
    post_files = list(POSTS_DIR.glob("*.json"))
    print(f"找到 {len(post_files)} 个有用的帖子")
    
    generated_count = 0
    for json_file in post_files:
        print(f"\n处理: {json_file.name}")
        
        # 从帖子生成模板（使用 Ollama）
        template_file = from_post_to_template(str(json_file))
        
        if template_file is None:
            print(f"⏭️  跳过此帖子")
            continue
        
        # 从模板生成 Alpha 表达式
        alphas_file = generate_alphas_from_template(template_file)
        print(f"✅ Alpha 表达式已生成: {alphas_file}")
        
        generated_count += 1
    
    print(f"\n✅ 阶段 2 完成: 成功处理 {generated_count} 个帖子")

    # ============================================
    # 阶段 3: Alpha 评估
    # ============================================
    print("\n📈 阶段 3: Alpha 评估 - 回测...")
    ALPHA_DIR = Path("data/alpha_db_v2/all_alphas")
    json_files = list(ALPHA_DIR.glob("*.json"))
    
    if not json_files:
        print("⚠️  没有找到需要回测的 Alpha")
    else:
        print(f"找到 {len(json_files)} 个 Alpha 文件")
        random.shuffle(json_files)
        
        for i, json_file in enumerate(json_files, 1):
            print(f"\n回测 {i}/{len(json_files)}: {json_file.name}")
            backtest_result = run_backtest_mul_by_wq_api(json_file)
    
    print("\n" + "="*80)
    print("✅ AlphaSpire 流程完成！")
    print("="*80)
