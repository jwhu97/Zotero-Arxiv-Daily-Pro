import base64
from openai import OpenAI

# ===== 配置 =====
API_KEY = "ms-aae063e6-8ecf-4fa1-ad66-24a5b11d38bb"  # 替换为你的 ModelScope Token
BASE_URL = "https://api-inference.modelscope.cn/v1/"
MODEL_ID = "Qwen/Qwen3-VL-8B-Instruct"

# 选择一种方式：本地图片 或 网络图片 URL
IMAGE_PATH = "./example.jpg"      # 本地图片路径（取消注释使用）
IMAGE_URL = "https://example.com/image.jpg"  # 或使用网络图片 URL

# ===== 工具函数：将本地图片转为 data URL =====
def image_to_data_url(image_path):
    with open(image_path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"

# ===== 构造多模态消息 =====
messages = [
    {"role": "system", "content": "You are a helpful assistant that can analyze images."},
    {"role": "user", "content": []}
]

# 添加文本指令
messages[1]["content"].append({
    "type": "text",
    "text": "请描述这张图片的内容。"
})

# 添加图片（二选一）
if 'IMAGE_PATH' in locals() and IMAGE_PATH:
    image_url = image_to_data_url(IMAGE_PATH)
elif 'IMAGE_URL' in locals() and IMAGE_URL:
    image_url = IMAGE_URL
else:
    raise ValueError("请提供 IMAGE_PATH 或 IMAGE_URL")

messages[1]["content"].append({
    "type": "image_url",
    "image_url": {"url": image_url}
})

# ===== 调用 API =====
client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL
)

try:
    response = client.chat.completions.create(
        model=MODEL_ID,
        messages=messages,
        stream=True
    )

    print("模型输出：", end="", flush=True)
    for chunk in response:
        content = chunk.choices[0].delta.content
        if content:
            print(content, end="", flush=True)
    print("\n")
except Exception as e:
    print(f"\n❌ 请求失败: {e}")