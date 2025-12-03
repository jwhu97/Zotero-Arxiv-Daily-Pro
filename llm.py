from llama_cpp import Llama
from openai import OpenAI
from loguru import logger
from time import sleep
import base64

GLOBAL_LLM = None
GLOBAL_VISION_LLM = None

class LLM:
    def __init__(self, api_key: str = None, base_url: str = None, model: str = None,lang: str = "English"):
        if api_key:
            self.llm = OpenAI(api_key=api_key, base_url=base_url, timeout=120.0)  # 添加120秒超时
        else:
            self.llm = Llama.from_pretrained(
                repo_id="Qwen/Qwen2.5-3B-Instruct-GGUF",
                filename="qwen2.5-3b-instruct-q4_k_m.gguf",
                n_ctx=5_000,
                n_threads=4,
                verbose=False,
            )
        self.model = model
        self.lang = lang

    def generate(self, messages: list[dict]) -> str:
        if isinstance(self.llm, OpenAI):
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.llm.chat.completions.create(messages=messages, temperature=0, model=self.model)
                    break
                except Exception as e:
                    logger.error(f"Attempt {attempt + 1} failed: {e}")
                    if attempt == max_retries - 1:
                        raise
                    # 使用指数退避策略，特别是对于 429 错误
                    # 第1次重试等待 5 秒，第2次等待 10 秒
                    wait_time = 5 * (2 ** attempt)
                    logger.info(f"Waiting {wait_time} seconds before retry...")
                    sleep(wait_time)
            return response.choices[0].message.content
        else:
            response = self.llm.create_chat_completion(messages=messages,temperature=0)
            return response["choices"][0]["message"]["content"]

    def generate_with_vision(self, text_prompt: str, image_base64: str) -> str:
        """
        使用vision模型分析图片并生成文本描述
        :param text_prompt: 文本提示
        :param image_base64: base64编码的图片数据
        :return: LLM生成的描述
        """
        if not isinstance(self.llm, OpenAI):
            logger.warning("Vision mode is only supported with OpenAI API. Returning empty string.")
            return ""

        max_retries = 3
        for attempt in range(max_retries):
            try:
                logger.debug(f"Vision API attempt {attempt + 1}/{max_retries} - Calling with timeout=120s, image size={len(image_base64)} chars")
                response = self.llm.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": text_prompt
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{image_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    temperature=0,
                    timeout=120.0  # 显式设置超时
                )
                logger.debug(f"Vision API attempt {attempt + 1} succeeded")
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"Vision API attempt {attempt + 1} failed: {type(e).__name__}: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"All {max_retries} attempts failed, giving up")
                    raise
                wait_time = 5 * (2 ** attempt)
                logger.info(f"Waiting {wait_time} seconds before retry...")
                sleep(wait_time)

def set_global_llm(api_key: str = None, base_url: str = None, model: str = None, lang: str = "English"):
    global GLOBAL_LLM
    GLOBAL_LLM = LLM(api_key=api_key, base_url=base_url, model=model, lang=lang)

def set_global_vision_llm(api_key: str, base_url: str, model: str, lang: str = "English"):
    """
    设置全局vision LLM（需要使用支持vision的模型）
    """
    global GLOBAL_VISION_LLM
    GLOBAL_VISION_LLM = LLM(api_key=api_key, base_url=base_url, model=model, lang=lang)

def get_llm() -> LLM:
    if GLOBAL_LLM is None:
        logger.info("No global LLM found, creating a default one. Use `set_global_llm` to set a custom one.")
        set_global_llm()
    return GLOBAL_LLM

def get_vision_llm() -> LLM:
    """
    获取vision LLM，如果未设置则使用普通LLM
    """
    if GLOBAL_VISION_LLM is None:
        logger.info("No global vision LLM found, using regular LLM.")
        return get_llm()
    return GLOBAL_VISION_LLM