import base64
import requests
import time
import json
import os
from typing import List, Dict, Optional, Tuple
from openai import OpenAI
from pathlib import Path
from loguru import logger
import zipfile


class MinerUExtractor:
    """MinerU图片提取器"""

    def __init__(self, token: str, api_url: str = "https://mineru.net/api/v4/extract"):
        self.token = token
        self.base_url = api_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        # 根据test_mineU.py中的正确URL格式配置
        self.task_submit_url = f"{self.base_url}/task/batch"
        self.result_query_url = f"{self.base_url}-results/batch/{{batch_id}}"

    def extract_images_from_pdf(self, pdf_url: str, max_images: int = 5,
                               max_attempts: int = 60, check_interval: int = 15) -> List[Dict]:
        """
        从PDF中提取图片

        Args:
            pdf_url: PDF文件URL
            max_images: 最大提取图片数
            max_attempts: 最大查询尝试次数
            check_interval: 查询间隔（秒）

        Returns:
            List[Dict]: 提取的图片信息列表，每个元素包含路径、分数等信息
        """
        try:
            # 步骤1: 提交任务
            batch_id = self._submit_task(pdf_url)
            if not batch_id:
                logger.error(f"无法提交MinerU任务: {pdf_url}")
                return []

            # 步骤2: 查询结果
            zip_url = self._check_result(batch_id, max_attempts, check_interval)
            if not zip_url:
                logger.error(f"无法获取MinerU处理结果: {pdf_url}")
                return []

            # 步骤3: 下载并提取图片
            output_dir = os.path.join(os.getcwd(), "extracted_images")
            os.makedirs(output_dir, exist_ok=True)
            images = self._download_and_extract_images(zip_url, output_dir, max_images)
            return images

        except Exception as e:
            logger.error(f"MinerU图片提取失败: {e}")
            return []

    def _submit_task(self, pdf_url: str) -> Optional[str]:
        """提交MinerU任务"""
        # 使用正确的URL格式（根据test_mineU.py）
        data = {
            "files": [
                {"url": pdf_url, "data_id": f"pdf_{int(time.time())}"}
            ],
            "model_version": "vlm"
        }

        try:
            logger.debug(f"提交MinerU任务到: {self.task_submit_url}")
            response = requests.post(self.task_submit_url, headers=self.headers, json=data, timeout=30)

            if response.status_code == 200:
                result = response.json()
                logger.debug(f"MinerU响应: {result}")
                if result.get("code") == 0:
                    batch_id = result["data"]["batch_id"]
                    logger.debug(f"MinerU任务提交成功，batch_id: {batch_id}")
                    return batch_id
                else:
                    logger.error(f"MinerU任务提交失败: {result.get('msg')}")
                    return None
            else:
                logger.error(f"MinerU API请求失败: {response.status_code}, 响应: {response.text}")
                return None

        except Exception as e:
            logger.error(f"提交MinerU任务异常: {e}")
            return None

    def _check_result(self, batch_id: str, max_attempts: int, check_interval: int) -> Optional[str]:
        """查询任务处理结果"""
        # 使用正确的URL格式（根据test_mineU.py）
        url = self.result_query_url.format(batch_id=batch_id)

        for attempt in range(max_attempts):
            try:
                logger.debug(f"第{attempt + 1}次查询MinerU任务状态: {url}")
                response = requests.get(url, headers=self.headers, timeout=30)

                if response.status_code == 200:
                    result = response.json()
                    logger.debug(f"MinerU查询响应: {result}")

                    if result.get("code") == 0:
                        extract_results = result["data"]["extract_result"]

                        for extract_result in extract_results:
                            state = extract_result.get("state")
                            file_name = extract_result.get("file_name", "unknown")

                            logger.debug(f"文件 {file_name} 状态: {state}")

                            if state == "done":
                                if "full_zip_url" in extract_result:
                                    zip_url = extract_result['full_zip_url']
                                    logger.success(f"MinerU任务完成: {file_name} -> {zip_url}")
                                    return zip_url
                                else:
                                    logger.error(f"MinerU任务完成但缺少下载链接: {file_name}")
                                    return None

                            elif state == "running":
                                progress = extract_result.get("extract_progress", {})
                                extracted = progress.get("extracted_pages", 0)
                                total = progress.get("total_pages", 0)
                                start_time = progress.get("start_time", "")
                                logger.debug(f"MinerU任务进行中... {file_name}: {extracted}/{total} 页 (开始时间: {start_time})")

                            elif state == "pending":
                                logger.debug(f"MinerU任务等待中... {file_name}")

                            elif state == "failed":
                                error_msg = extract_result.get('err_msg', '未知错误')
                                logger.error(f"MinerU任务失败: {file_name} - {error_msg}")
                                return None
                            else:
                                logger.debug(f"MinerU未知状态: {file_name} - {state}")

                        # 如果任务还在进行中，继续等待
                        running_tasks = [r for r in extract_results if r.get("state") in ["running", "pending"]]
                        if running_tasks:
                            logger.debug(f"仍有 {len(running_tasks)} 个任务在处理中，等待 {check_interval} 秒...")
                            time.sleep(check_interval)
                            continue
                        else:
                            return None
                    else:
                        logger.error(f"MinerU查询失败: {result.get('msg')}")
                        return None
                else:
                    logger.error(f"MinerU查询API失败: {response.status_code}, 响应: {response.text}")
                    return None

            except Exception as e:
                logger.error(f"查询MinerU状态异常: {e}")
                time.sleep(check_interval)
                continue

        logger.error(f"MinerU任务处理超时: {batch_id} (尝试了 {max_attempts} 次)")
        return None

    def _download_and_extract_images(self, zip_url: str, output_dir: str, max_images: int) -> List[Dict]:
        """下载zip文件并提取图片"""
        try:
            # 下载zip文件
            response = requests.get(zip_url, stream=True, timeout=300)
            response.raise_for_status()

            zip_path = Path(output_dir) / "mineru_result.zip"
            with open(zip_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # 解压并提取图片
            extracted_images = []
            images_dir = Path(output_dir) / "extracted_images"
            images_dir.mkdir(exist_ok=True)

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(output_dir)

                # 首先获取所有文件信息用于排序和筛选
                all_files = zip_ref.infolist()
                image_files = []

                # 收集所有图片文件
                for file_info in all_files:
                    file_path = Path(file_info.filename)
                    if file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']:
                        # 检查文件大小，过滤太小的图片（可能是装饰性图片）
                        if file_info.file_size < 2000:  # 小于2KB的图片跳过
                            continue

                        image_files.append((file_info, file_info.file_size))

                # 按文件大小排序，优先选择大图片
                image_files.sort(key=lambda x: x[1], reverse=True)

                # 提取前N张最大的图片
                for idx, (file_info, file_size) in enumerate(image_files[:max_images]):
                    file_path = Path(file_info.filename)

                    # 提取图片到指定目录
                    original_name = file_path.name
                    extension = file_path.suffix.lower()
                    image_name = f"key_image_{idx + 1}{extension}"
                    target_path = images_dir / image_name

                    try:
                        with zip_ref.open(file_info) as source, open(target_path, 'wb') as target:
                            target.write(source.read())

                        logger.debug(f"成功提取图片: {image_name} (来源: {file_path}, 大小: {file_size} 字节)")

                        extracted_images.append({
                            'original_name': original_name,
                            'extracted_name': image_name,
                            'path': str(target_path),
                            'size': file_size,
                            'score': None,  # 稍后由Qwen3-VL评分
                            'description': None  # 稍后由Qwen3-VL描述
                        })

                    except Exception as e:
                        logger.warning(f"提取图片失败 {file_path}: {e}")
                        continue

            # 删除zip文件节省空间
            zip_path.unlink(missing_ok=True)

            logger.info(f"成功提取 {len(extracted_images)} 张图片到 {images_dir}")
            for i, img in enumerate(extracted_images):
                logger.debug(f"  {i+1}. {img['extracted_name']} - {img['size']} 字节")

            return extracted_images

        except Exception as e:
            logger.error(f"下载和提取图片失败: {e}")
            return []


class Qwen3VLImageScorer:
    """Qwen3-VL图片评分器"""

    def __init__(self, api_key: str, base_url: str = "https://api-inference.modelscope.cn/v1/",
                 model_id: str = "Qwen/Qwen3-VL-8B-Instruct"):
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model_id = model_id

    def score_images(self, images: List[Dict], paper_title: str, paper_abstract: str) -> List[Dict]:
        """
        对图片进行重要性评分和描述

        Args:
            images: 图片信息列表
            paper_title: 论文标题
            paper_abstract: 论文摘要

        Returns:
            List[Dict]: 更新后的图片信息列表，包含分数和描述
        """
        if not images:
            return images

        logger.debug(f"开始使用Qwen3-VL评分 {len(images)} 张图片")

        # 构建评分提示
        system_prompt = """你是一个专业的学术论文图片分析助手。请分析给定的图片，评估其在学术论文中的重要性和代表性。

评分标准（1-10分）：
- 9-10分：核心结果图，展示了论文的主要贡献和关键发现
- 7-8分：重要的实验结果或架构图，对理解论文有帮助
- 5-6分：辅助性图表，提供支持性信息
- 3-4分：一般性图示，装饰性或次要内容
- 1-2分：不重要的图片，与论文主旨关系不大

请为每张图片：
1. 简要描述图片内容
2. 评估其重要性并给出分数（1-10）
3. 说明评分理由

输出格式（严格JSON格式）：
{
    "description": "图片内容描述",
    "score": 数字分数,
    "reason": "评分理由"
}"""

        user_prompt = f"""论文标题：{paper_title}
论文摘要：{paper_abstract[:800]}...

请分析以下图片在该论文中的重要性。"""

        # 对每张图片进行评分
        for i, image in enumerate(images):
            try:
                image_path = image['path']
                if not os.path.exists(image_path):
                    logger.warning(f"图片文件不存在: {image_path}")
                    continue

                # 将图片转为base64
                image_data_url = self._image_to_data_url(image_path)

                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": image_data_url}}
                    ]}
                ]

                response = self.client.chat.completions.create(
                    model=self.model_id,
                    messages=messages,
                    stream=False,
                    max_tokens=500,
                    temperature=0.1
                )

                response_text = response.choices[0].message.content.strip()

                # 解析JSON响应
                try:
                    result = json.loads(response_text)
                    image['description'] = result.get('description', '')
                    image['score'] = result.get('score', 5)
                    image['reason'] = result.get('reason', '')
                    logger.debug(f"图片 {image['extracted_name']} 评分: {image['score']}/10")
                except json.JSONDecodeError:
                    logger.warning(f"无法解析Qwen3-VL响应: {response_text}")
                    # 给予默认分数
                    image['description'] = response_text
                    image['score'] = 5
                    image['reason'] = 'API响应解析失败'

                # 添加延迟避免API限制
                time.sleep(2)

            except Exception as e:
                logger.error(f"图片 {image['extracted_name']} 评分失败: {e}")
                # 给予默认分数
                image['description'] = f"评分失败: {str(e)}"
                image['score'] = 3
                image['reason'] = 'API调用失败'

        # 按分数排序
        images.sort(key=lambda x: x.get('score', 0), reverse=True)
        logger.debug(f"图片评分完成，最高分: {images[0].get('score', 0) if images else 0}")

        return images

    def _image_to_data_url(self, image_path: str) -> str:
        """将本地图片转为data URL"""
        with open(image_path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode("utf-8")
        return f"data:image/jpeg;base64,{encoded}"

    def get_top_image(self, images: List[Dict], min_score: int = 6) -> Optional[Dict]:
        """
        获取最重要的一张图片

        Args:
            images: 图片信息列表
            min_score: 最低分数要求

        Returns:
            Optional[Dict]: 最重要图片的信息，如果没有满足条件的图片则返回None
        """
        if not images:
            return None

        # 找到分数最高的图片
        top_image = images[0]

        # 检查是否满足最低分数要求
        if top_image.get('score', 0) >= min_score:
            return top_image
        else:
            logger.debug(f"没有图片满足最低分数要求 {min_score}，最高分: {top_image.get('score', 0)}")
            return None

    def get_top_images(self, images: List[Dict], top_k: int = 3, min_score: int = 6) -> List[Dict]:
        """
        获取最重要的前K张图片

        Args:
            images: 图片信息列表（已按分数排序）
            top_k: 需要返回的图片数量
            min_score: 最低分数要求

        Returns:
            List[Dict]: 最重要图片的信息列表，按重要性排序
        """
        if not images:
            return []

        # 过滤满足最低分数要求的图片
        qualified_images = [img for img in images if img.get('score', 0) >= min_score]

        # 返回前K张图片
        top_images = qualified_images[:top_k]

        logger.debug(f"选择了 {len(top_images)} 张重要图片，最低分数要求: {min_score}")
        for i, img in enumerate(top_images):
            logger.debug(f"  第{i+1}张: {img.get('extracted_name', 'unknown')} - {img.get('score', 0)}/10")

        return top_images


class ImageAnalyzer:
    """图片分析器主类，整合MinerU和Qwen3-VL"""

    def __init__(self, mineru_token: str, qwen_api_key: str):
        # 从环境变量读取API配置
        mineru_api_url = os.getenv('MINERU_API_URL', 'https://mineru.net/api/v4/extract')
        qwen_base_url = os.getenv('QWEN_BASE_URL', 'https://api-inference.modelscope.cn/v1/')
        qwen_model = os.getenv('QWEN_MODEL', 'Qwen/Qwen3-VL-8B-Instruct')

        self.mineru = MinerUExtractor(mineru_token, mineru_api_url)
        self.qwen_scorer = Qwen3VLImageScorer(qwen_api_key, qwen_base_url, qwen_model)

        # 创建永久目录存储图片
        self.image_storage_dir = Path(os.getcwd()) / "extracted_images"
        self.image_storage_dir.mkdir(exist_ok=True)

    def extract_and_score_images(self, pdf_url: str, paper_title: str,
                               paper_abstract: str, max_images: int = 10) -> Optional[Dict]:
        """
        提取图片并评分，返回最重要的图片（保持向后兼容的单张图片接口）

        Args:
            pdf_url: PDF文件URL
            paper_title: 论文标题
            paper_abstract: 论文摘要
            max_images: 最大提取图片数

        Returns:
            Optional[Dict]: 最重要图片的信息，包含base64编码用于邮件显示
        """
        result = self.extract_and_score_multiple_images(pdf_url, paper_title, paper_abstract, max_images, top_k=1)
        if result and result.get('images'):
            return result['images'][0]  # 返回第一张（最重要的）图片
        return None

    def extract_and_score_multiple_images(self, pdf_url: str, paper_title: str,
                                         paper_abstract: str, max_images: int = 10,
                                         top_k: int = 3, cleanup_after: bool = False) -> Optional[Dict]:
        """
        提取图片并评分，返回最重要的前K张图片

        Args:
            pdf_url: PDF文件URL
            paper_title: 论文标题
            paper_abstract: 论文摘要
            max_images: 最大提取图片数
            top_k: 需要返回的图片数量
            cleanup_after: 处理完成后是否清理图片文件

        Returns:
            Optional[Dict]: 包含重要图片列表的信息
        """
        try:
            # 步骤1: 使用MinerU提取图片
            images = self.mineru.extract_images_from_pdf(pdf_url, max_images)
            if not images:
                logger.debug("未能提取到任何图片")
                return None

            # 步骤2: 使用Qwen3-VL对图片评分
            scored_images = self.qwen_scorer.score_images(images, paper_title, paper_abstract)
            if not scored_images:
                logger.debug("图片评分失败")
                return None

            # 步骤3: 获取最重要的前K张图片
            top_images = self.qwen_scorer.get_top_images(scored_images, top_k, min_score=6)
            if not top_images:
                logger.debug(f"没有满足条件的图片，最高分: {scored_images[0].get('score', 0) if scored_images else 0}")
                return None

            # 步骤4: 将图片转为base64用于邮件显示
            processed_images = []
            for img in top_images:
                image_base64 = self._image_to_base64(img['path'])
                processed_images.append({
                    'filename': img['extracted_name'],
                    'description': img.get('description', ''),
                    'score': img.get('score', 0),
                    'reason': img.get('reason', ''),
                    'base64_data': image_base64,
                    'size': img.get('size', 0)
                })

            logger.debug(f"选择 {len(processed_images)} 张重要图片")
            for i, img in enumerate(processed_images):
                logger.debug(f"  第{i+1}张: {img['filename']} - {img['score']}/10")

            # 可选：处理完成后清理图片文件
            if cleanup_after:
                self.cleanup()

            return {
                'images': processed_images,
                'count': len(processed_images),
                'total_extracted': len(images)
            }

        except Exception as e:
            logger.error(f"图片提取和评分过程失败: {e}")
            return None

    def _image_to_base64(self, image_path: str) -> str:
        """将图片转为base64字符串"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    def cleanup(self):
        """手动清理图片文件（可选）"""
        try:
            if self.image_storage_dir.exists():
                # 可选择删除图片文件，但保留目录
                for file in self.image_storage_dir.glob("*"):
                    if file.is_file():
                        file.unlink()
                logger.debug("图片文件已清理")
        except Exception as e:
            logger.error(f"清理图片文件失败: {e}")


# 全局单例实例（如果需要的话）
_global_image_analyzer = None

def get_image_analyzer(mineru_token: str = None, qwen_api_key: str = None) -> ImageAnalyzer:
    """获取图片分析器实例"""
    global _global_image_analyzer

    # 从环境变量获取默认值
    if mineru_token is None:
        mineru_token = os.getenv('MINERU_TOKEN')
    if qwen_api_key is None:
        qwen_api_key = os.getenv('QWEN_API_KEY')

    # 如果没有现有实例或配置不同，创建新实例
    if (_global_image_analyzer is None or
        mineru_token != os.getenv('MINERU_TOKEN') or
        qwen_api_key != os.getenv('QWEN_API_KEY')):

        if not mineru_token or not qwen_api_key:
            raise ValueError("需要提供mineru_token和qwen_api_key")

        # 可选：清理旧实例的图片文件
        if _global_image_analyzer:
            _global_image_analyzer.cleanup()

        _global_image_analyzer = ImageAnalyzer(mineru_token, qwen_api_key)

    return _global_image_analyzer