#!/usr/bin/env python3
"""
使用MinerU API提取PDF文档中的图片
获取样例PDF中的前5张图片
"""

import requests
import json
import time
import zipfile
import os
import base64
from pathlib import Path
from urllib.parse import urlparse
from openai import OpenAI
from typing import List, Dict, Optional


class ImageImportanceAnalyzer:
    """使用Qwen3-VL模型分析图片重要性"""

    def __init__(self):
        # Qwen3-VL API配置
        self.api_key = "ms-aae063e6-8ecf-4fa1-ad66-24a5b11d38bb"
        self.base_url = "https://api-inference.modelscope.cn/v1/"
        self.model_id = "Qwen/Qwen3-VL-8B-Instruct"

        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def image_to_data_url(self, image_path: str) -> str:
        """将本地图片转换为data URL格式"""
        try:
            with open(image_path, "rb") as image_file:
                encoded = base64.b64encode(image_file.read()).decode("utf-8")
            # 根据文件扩展名确定MIME类型
            ext = Path(image_path).suffix.lower()
            mime_type = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.bmp': 'image/bmp'
            }.get(ext, 'image/jpeg')
            return f"data:{mime_type};base64,{encoded}"
        except Exception as e:
            print(f"转换图片失败 {image_path}: {e}")
            return None

    def analyze_single_image(self, image_path: str) -> Optional[Dict]:
        """分析单张图片的重要性和内容"""
        try:
            # 转换图片格式
            image_url = self.image_to_data_url(image_path)
            if not image_url:
                return None

            # 构造分析消息
            messages = [
                {
                    "role": "system",
                    "content": "你是一个专业的图片分析助手。请从学术角度分析图片的重要性，重点关注其在学术论文中的价值。"
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": """请分析这张图片的重要性并给出评分（1-10分），并从以下几个方面进行评价：
1. 内容复杂度（是否包含重要信息、数据、图表等）
2. 学术价值（是否展示研究结果、方法论、关键数据等）
3. 直观性（是否清晰地传达了重要概念）
4. 独特性（是否包含难以用文字替代的信息）

请按以下JSON格式返回结果：
{
    "score": 数字评分(1-10),
    "complexity": 复杂度评分(1-10),
    "academic_value": 学术价值评分(1-10),
    "clarity": 直观性评分(1-10),
    "uniqueness": 独特性评分(1-10),
    "description": "详细描述图片内容",
    "key_points": ["要点1", "要点2", "要点3"],
    "reason": "重要性评估的理由"
}"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url}
                        }
                    ]
                }
            ]

            # 调用API
            response = self.client.chat.completions.create(
                model=self.model_id,
                messages=messages,
                stream=False
            )

            # 解析结果
            content = response.choices[0].message.content.strip()

            # 尝试解析JSON
            try:
                # 提取JSON部分
                start_idx = content.find('{')
                end_idx = content.rfind('}') + 1
                if start_idx != -1 and end_idx != -1:
                    json_str = content[start_idx:end_idx]
                    result = json.loads(json_str)
                    result['image_path'] = image_path
                    return result
                else:
                    # 如果无法解析JSON，创建基本结果
                    return {
                        'score': 5,
                        'complexity': 5,
                        'academic_value': 5,
                        'clarity': 5,
                        'uniqueness': 5,
                        'description': content,
                        'key_points': [],
                        'reason': 'AI返回内容无法解析为JSON',
                        'image_path': image_path
                    }
            except json.JSONDecodeError as e:
                print(f"JSON解析失败: {e}")
                print(f"原始内容: {content}")
                return {
                    'score': 5,
                    'complexity': 5,
                    'academic_value': 5,
                    'clarity': 5,
                    'uniqueness': 5,
                    'description': content,
                    'key_points': [],
                    'reason': 'JSON解析失败',
                    'image_path': image_path
                }

        except Exception as e:
            print(f"分析图片失败 {image_path}: {e}")
            return None

    def rank_images(self, images: List[Dict]) -> List[Dict]:
        """对图片列表进行重要性排序"""
        print("开始分析图片重要性...")

        analyzed_results = []
        total_images = len(images)

        for i, img_info in enumerate(images, 1):
            print(f"正在分析第 {i}/{total_images} 张图片: {img_info['extracted_name']}")

            result = self.analyze_single_image(img_info['path'])
            if result:
                # 合并原始图片信息和分析结果
                merged_info = {**img_info, **result}
                analyzed_results.append(merged_info)
                print(f"  评分: {result.get('score', 'N/A')}/10 - {result.get('description', '')[:50]}...")
            else:
                print(f"  分析失败")

        # 按score降序排序
        analyzed_results.sort(key=lambda x: x.get('score', 0), reverse=True)

        print(f"\n图片重要性排序完成：")
        for i, result in enumerate(analyzed_results, 1):
            score = result.get('score', 0)
            desc = result.get('description', '')[:50]
            print(f"{i}. 图片: {result['extracted_name']} - 评分: {score}/10 - {desc}...")

        return analyzed_results

    def get_top_n_images(self, images: List[Dict], n: int = 3) -> List[Dict]:
        """获取最重要的N张图片"""
        ranked_images = self.rank_images(images)
        return ranked_images[:n]


class MinerUImageExtractor:
    def __init__(self, token, pdf_url):
        self.token = token
        self.pdf_url = pdf_url
        self.base_url = "https://mineru.net/api/v4/extract"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        # 初始化图片重要性分析器
        self.importance_analyzer = ImageImportanceAnalyzer()

    def submit_task(self):
        """提交提取任务到MinerU API"""
        url = f"{self.base_url}/task/batch"
        data = {
            "files": [
                {"url": self.pdf_url, "data_id": "example_pdf"}
            ],
            "model_version": "vlm"
        }

        try:
            print("正在提交MinerU任务...")
            response = requests.post(url, headers=self.headers, json=data)

            if response.status_code == 200:
                result = response.json()
                print(f"任务提交成功: {result}")

                if result.get("code") == 0:
                    batch_id = result["data"]["batch_id"]
                    print(f"获取到batch_id: {batch_id}")
                    return batch_id
                else:
                    print(f"任务提交失败: {result.get('msg')}")
                    return None
            else:
                print(f"API请求失败: {response.status_code}, {response}")
                return None

        except Exception as err:
            print(f"提交任务时发生错误: {err}")
            return None

    def check_result(self, batch_id, max_attempts=60, check_interval=15):
        """查询任务处理结果"""
        url = f"{self.base_url}-results/batch/{batch_id}"

        for attempt in range(max_attempts):
            try:
                print(f"第{attempt + 1}次查询任务状态...")
                response = requests.get(url, headers=self.headers)

                if response.status_code == 200:
                    result = response.json()
                    print(f"查询结果: {json.dumps(result, indent=2, ensure_ascii=False)}")

                    if result.get("code") == 0:
                        extract_results = result["data"]["extract_result"]

                        # 检查处理状态
                        for extract_result in extract_results:
                            if extract_result.get("state") == "done":
                                if "full_zip_url" in extract_result:
                                    print(f"任务完成，下载链接: {extract_result['full_zip_url']}")
                                    return extract_result['full_zip_url']
                            elif extract_result.get("state") == "running":
                                progress = extract_result.get("extract_progress", {})
                                extracted = progress.get("extracted_pages", 0)
                                total = progress.get("total_pages", 0)
                                print(f"任务进行中... 已处理: {extracted}/{total} 页")
                            elif extract_result.get("state") == "failed":
                                print(f"任务失败: {extract_result.get('err_msg', '未知错误')}")
                                return None

                        # 处理不同的状态
                        state = extract_result.get("state")
                        if state == "running":
                            progress = extract_result.get("extract_progress", {})
                            extracted = progress.get("extracted_pages", 0)
                            total = progress.get("total_pages", 0)
                            print(f"任务进行中... 已处理: {extracted}/{total} 页")
                            time.sleep(check_interval)
                            continue
                        elif state == "pending":
                            print("任务等待中，等待系统开始处理...")
                            time.sleep(check_interval)
                            continue
                        elif state == "done":
                            if "full_zip_url" in extract_result:
                                print(f"任务完成，下载链接: {extract_result['full_zip_url']}")
                                return extract_result['full_zip_url']
                            else:
                                print("任务完成但缺少下载链接")
                                return None
                        elif state == "failed":
                            print(f"任务失败: {extract_result.get('err_msg', '未知错误')}")
                            return None
                        else:
                            print(f"未知状态: {state}，等待后继续查询...")
                            time.sleep(check_interval)
                            continue
                    else:
                        print(f"查询失败: {result.get('msg')}")
                        return None
                else:
                    print(f"查询API失败: {response.status_code}, {response}")
                    return None

            except Exception as err:
                print(f"查询任务状态时发生错误: {err}")
                return None

        print("任务处理超时")
        return None

    def download_and_extract_images(self, zip_url, output_dir="extracted_images", max_images=5):
        """下载zip文件并提取前N张图片"""
        try:
            print(f"正在下载提取结果: {zip_url}")
            response = requests.get(zip_url, stream=True)
            response.raise_for_status()

            # 创建输出目录
            output_path = Path(output_dir)
            output_path.mkdir(exist_ok=True)

            # 保存zip文件
            zip_path = output_path / "mineru_result.zip"
            print(f"保存zip文件到: {zip_path}")

            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print("正在解压文件...")
            extracted_images = []

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(output_path)

                # 查找图片文件
                for file_info in zip_ref.infolist():
                    if len(extracted_images) >= max_images:
                        break

                    file_path = Path(file_info.filename)
                    # 检查是否为图片文件
                    if file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
                        # 提取图片到输出目录
                        image_name = f"image_{len(extracted_images) + 1}{file_path.suffix}"
                        image_path = output_path / image_name

                        with zip_ref.open(file_info) as source, open(image_path, 'wb') as target:
                            target.write(source.read())

                        extracted_images.append({
                            'original_name': file_path.name,
                            'extracted_name': image_name,
                            'path': str(image_path),
                            'size': file_info.file_size
                        })
                        print(f"提取图片 {len(extracted_images)}: {image_name}")

            # 删除临时zip文件
            zip_path.unlink()

            print(f"\n成功提取 {len(extracted_images)} 张图片到 {output_path}")
            return extracted_images

        except Exception as err:
            print(f"下载和提取图片时发生错误: {err}")
            return []

    def run(self, output_dir="extracted_images", analyze_importance=False, top_n=None):
        """运行完整的提取流程"""
        print("=== MinerU图片提取器 ===")

        # 步骤1: 提交任务
        batch_id = self.submit_task()
        if not batch_id:
            print("任务提交失败，退出")
            return []

        # 步骤2: 查询结果
        zip_url = self.check_result(batch_id)
        if not zip_url:
            print("无法获取处理结果，退出")
            return []

        # 步骤3: 下载并提取图片
        images = self.download_and_extract_images(zip_url, output_dir, max_images=10)  # 提取更多图片用于分析

        # 步骤4: 可选的图片重要性分析
        if analyze_importance and images:
            print("\n=== 开始图片重要性分析 ===")
            if top_n:
                # 只返回最重要的N张图片
                important_images = self.importance_analyzer.get_top_n_images(images, n=top_n)
                print(f"\n筛选出最重要的 {len(important_images)} 张图片：")
                for i, img in enumerate(important_images, 1):
                    score = img.get('score', 0)
                    desc = img.get('description', '')[:100]
                    print(f"{i}. {img['extracted_name']} - 评分: {score}/10")
                    print(f"   描述: {desc}...")
                return important_images
            else:
                # 返回所有排序后的图片
                ranked_images = self.importance_analyzer.rank_images(images)
                return ranked_images

        return images

    def extract_and_analyze(self, output_dir="extracted_images", top_n=3):
        """专门的方法：提取图片并进行重要性分析，返回最重要的N张图片"""
        return self.run(output_dir=output_dir, analyze_importance=True, top_n=top_n)

def main():
    """主函数"""
    # MinerU API配置
    token = "eyJ0eXBlIjoiSldUIiwiYWxnIjoiSFM1MTIifQ.eyJqdGkiOiI1MDE5OTg1OCIsInJvbCI6IlJPTEVfUkVHSVNURVIiLCJpc3MiOiJPcGVuWExhYiIsImlhdCI6MTc2NDY4NTMxNCwiY2xpZW50SWQiOiJsa3pkeDU3bnZ5MjJqa3BxOXgydyIsInBob25lIjoiIiwib3BlbklkIjpudWxsLCJ1dWlkIjoiZTM4ZTY5YzctNmU2MS00MjhkLWIxN2MtZmNjNDAwOGU3MDQ4IiwiZW1haWwiOiIiLCJleHAiOjE3NjU4OTQ5MTR9.eoXeO10J7Z3a3vRJmYpzFBwnL1-hDshuTDLyvBNE1tx8hXtrCbuLXi_NEbrQ1iHV9xnSGM_zXhmF38Ur0LZfyg"
    pdf_url = "https://cdn-mineru.openxlab.org.cn/demo/example.pdf"

    # 创建提取器实例
    extractor = MinerUImageExtractor(token, pdf_url)

    # 运行提取流程
    images = extractor.run()

    # 显示结果
    if images:
        print("\n=== 提取的图片列表 ===")
        for i, img in enumerate(images, 1):
            print(f"{i}. {img['extracted_name']} ({img['original_name']})")
            print(f"   路径: {img['path']}")
            print(f"   大小: {img['size']} 字节")
    else:
        print("未能提取到图片")

def demo_extract_and_analyze():
    """演示新功能的简化版本"""
    # MinerU API配置
    token = "eyJ0eXBlIjoiSldUIiwiYWxnIjoiSFM1MTIifQ.eyJqdGkiOiI1MDE5OTg1OCIsInJvbCI6IlJPTEVfUkVHSVNURVIiLCJpc3MiOiJPcGVuWExhYiIsImlhdCI6MTc2NDY4NTMxNCwiY2xpZW50SWQiOiJsa3pkeDU3bnZ5MjJqa3BxOXgydyIsInBob25lIjoiIiwib3BlbklkIjpudWxsLCJ1dWlkIjoiZTM4ZTY5YzctNmU2MS00MjhkLWIxN2MtZmNjNDAwOGU3MDQ4IiwiZW1haWwiOiIiLCJleHAiOjE3NjU4OTQ5MTR9.eoXeO10J7Z3a3vRJmYpzFBwnL1-hDshuTDLyvBNE1tx8hXtrCbuLXi_NEbrQ1iHV9xnSGM_zXhmF38Ur0LZfyg"
    pdf_url = "https://cdn-mineru.openxlab.org.cn/demo/example.pdf"

    # 创建提取器实例
    extractor = MinerUImageExtractor(token, pdf_url)

    print("=== 演示：提取图片并筛选最重要的3张图片 ===")

    # 提取图片并进行重要性分析
    important_images = extractor.extract_and_analyze(top_n=3)

    # 显示结果
    if important_images:
        print(f"\n=== 最重要的3张图片分析结果 ===")
        for i, img in enumerate(important_images, 1):
            score = img.get('score', 0)
            description = img.get('description', '无描述')
            key_points = img.get('key_points', [])
            reason = img.get('reason', '')

            print(f"\n第{i}重要图片: {img['extracted_name']}")
            print(f"重要性评分: {score}/10")
            print(f"图片描述: {description}")
            if key_points:
                print(f"关键要点: {', '.join(key_points)}")
            if reason:
                print(f"评估理由: {reason}")
            print(f"文件路径: {img['path']}")
            print("-" * 80)
        return important_images
    else:
        print("未能提取或分析图片")
        return []

if __name__ == "__main__":
    # 直接运行演示新功能
    demo_extract_and_analyze()