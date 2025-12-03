"""测试特定论文的图片提取功能"""
import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

from dotenv import load_dotenv
load_dotenv(override=True)

import sys
import arxiv
from paper import ArxivPaper
from llm import set_global_llm, set_global_vision_llm
from loguru import logger

# 配置日志为DEBUG级别
logger.remove()
logger.add(sys.stdout, level="DEBUG")

# 设置LLM
use_api = os.getenv("USE_LLM_API", "0") == "1"
if use_api:
    api_key = os.getenv("OPENAI_API_KEY")
    api_base = os.getenv("OPENAI_API_BASE")
    model_name = os.getenv("MODEL_NAME")
    vision_model = os.getenv("VISION_MODEL_NAME")

    set_global_llm(api_key=api_key, base_url=api_base, model=model_name, lang="Chinese")
    set_global_vision_llm(api_key=api_key, base_url=api_base, model=vision_model, lang="Chinese")
    print(f"✓ 已设置API模式: {model_name} / {vision_model}")
else:
    print("✗ 需要API模式才能测试vision功能")
    exit(1)

# 测试的论文ID
test_papers = [
    "2512.01996",  # 第四篇
    "2512.02019",  # 第五篇
]

print("\n" + "="*80)
print("开始测试论文图片提取功能")
print("="*80 + "\n")

client = arxiv.Client()

for paper_id in test_papers:
    print(f"\n{'='*80}")
    print(f"📄 测试论文: {paper_id}")
    print(f"{'='*80}\n")

    # 获取论文
    search = arxiv.Search(id_list=[paper_id])
    result = next(client.results(search))
    paper = ArxivPaper(result)

    print(f"标题: {paper.title}\n")

    # 测试图片提取
    print("开始提取overview图片...\n")

    try:
        overview = paper.overview_figure

        if overview:
            print("✅ 成功提取图片!")
            print(f"  - Caption: {overview['caption'][:100]}...")
            print(f"  - Description: {overview['description'][:150]}...")
            print(f"  - Image size: {len(overview['image_base64'])} bytes (base64)")
        else:
            print("❌ 未找到合适的图片")

    except Exception as e:
        print(f"❌ 提取失败: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "="*80)
print("测试完成")
print("="*80)
