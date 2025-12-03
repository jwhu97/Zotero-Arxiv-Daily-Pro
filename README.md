# Zotero-arXiv-Daily-Pro

<p align="center">
  <img width="200px" height="200px" src="assets/logo.svg" alt="logo">
</p>

<div align="center">

[![Status](https://img.shields.io/badge/status-active-success.svg)]()
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
[![License](https://img.shields.io/badge/license-AGPLv3-blue.svg)](LICENSE)

**基于个人文献库的智能论文推荐系统**

[English](#) | [简体中文](#)

</div>

---

## 📑 目录

- [项目简介](#项目简介)
- [核心特性](#核心特性)
- [快速开始](#快速开始)
- [部署指南](#部署指南)
- [API 说明](#api-说明)
- [使用示例](#使用示例)
- [配置说明](#配置说明)
- [常见问题](#常见问题)
- [开发指南](#开发指南)
- [许可证](#许可证)

---

## 项目简介

**Zotero-arXiv-Daily-Pro** 是一个基于 GitHub Actions 的自动化学术论文推荐系统。它根据您的 Zotero 文献库内容，利用语义相似度算法从 arXiv 上筛选出与您研究方向最相关的新论文，并通过邮件发送每日推荐。

### 工作原理

1. **文献分析**：从 Zotero API 获取您的个人文献库
2. **新论文采集**：从 arXiv RSS Feed 获取指定领域的最新论文
3. **智能排序**：使用嵌入模型计算语义相似度，按相关性排序
4. **内容增强**：
   - 使用 LLM 生成论文 TLDR（一句话总结）
   - 提取论文关键图表（MinerU 图片分析）
   - 识别开源代码链接
   - 提取作者机构信息
5. **邮件推送**：生成精美的 HTML 邮件并自动发送

### 技术亮点

- ✅ **完全免费**：基于 GitHub Actions，无需服务器
- ✅ **零配置部署**：Fork 仓库 + 设置环境变量即可运行
- ✅ **个性化推荐**：基于您的文献库智能匹配
- ✅ **多模态支持**：集成 MinerU 提取论文关键图表
- ✅ **灵活的 LLM**：支持本地模型和 API 调用
- ✅ **精细控制**：gitignore 风格的文献过滤规则

---

## 核心特性

### 🎯 智能推荐算法

基于 **sentence-transformers** 的语义相似度计算：

- 使用 `GIST-small-Embedding-v0` 模型生成论文向量
- 计算新论文与您文献库的加权相似度
- 时间衰减权重：`weight = 1 / (1 + log10(rank + 1))`
- 越新添加的文献权重越高

### 🤖 AI 增强内容

#### TLDR 生成
- 自动下载论文 LaTeX 源码
- 提取 Introduction 和 Conclusion 章节
- 使用 LLM 生成一句话摘要
- 支持本地模型（Qwen2.5-3B）和 API 调用

#### 图表提取（MinerU 集成）
- 智能识别论文中的关键图表
- 使用 Qwen3-VL 多模态模型评分
- 自动选择最重要的图表嵌入邮件

#### 代码链接识别
- 从 Papers with Code 获取代码仓库
- 支持从论文 PDF 中提取 GitHub 链接

### 📧 精美的邮件展示

- 响应式 HTML 邮件模板
- 星级相关度评分（0-5 星）
- 直达链接：arXiv 页面、PDF 下载、源码仓库
- 嵌入关键图表和 TLDR

### 🔧 灵活的过滤规则

使用 gitignore 风格的规则过滤 Zotero 集合：

```
# 排除整个 AI Agent 集合
AI Agent/

# 排除所有名为 survey 的子集合
**/survey

# 但保留 LLM/survey 集合
!LLM/survey
```

---

## 快速开始

### 前置要求

- GitHub 账号
- Zotero 账号及文献库
- 邮箱（用于接收推荐）

### 5 分钟部署

1. **Fork 本仓库**

   点击页面右上角的 `Fork` 按钮

2. **设置环境变量**

   进入 `Settings` > `Secrets and variables` > `Actions` > `New repository secret`

   添加以下必需的 Secrets：

   | 变量名 | 必需 | 类型 | 说明 | 示例 |
   |--------|------|------|------|------|
   | `ZOTERO_ID` | ✅ | str | Zotero 用户 ID（**不是用户名，而是一串数字**）。从[这里](https://www.zotero.org/settings/security)获取，位置见此[截图](https://github.com/TideDra/zotero-arxiv-daily/blob/main/assets/userid.png)。 | `12345678` |
   | `ZOTERO_KEY` | ✅ | str | Zotero API Key（具有只读权限）。从[这里](https://www.zotero.org/settings/security)创建。 | `AB5tZ877P2j7Sm2M` |
   | `ARXIV_QUERY` | ✅ | str | arXiv 论文类别。使用 `+` 连接多个类别。从[这里](https://arxiv.org/category_taxonomy)查找您研究领域的缩写。 | `cs.AI+cs.CV+cs.LG+cs.CL` |
   | `SMTP_SERVER` | ✅ | str | SMTP 服务器地址。建议使用专用邮箱。咨询您的邮箱服务商（Gmail、QQ、Outlook等）。 | `smtp.gmail.com` |
   | `SMTP_PORT` | ✅ | int | SMTP 服务器端口。 | `465` |
   | `SENDER` | ✅ | str | 发件邮箱地址。 | `your@email.com` |
   | `SENDER_PASSWORD` | ✅ | str | 邮箱密码。**注意：这不一定是登录密码，而是 SMTP 服务的授权码**。咨询您的邮箱服务商。 | `abcdefghijklmn` |
   | `RECEIVER` | ✅ | str | 收件邮箱地址。 | `your@email.com` |

   > 📌 **更多配置说明**：详见下方 [API 配置获取指南](#api-配置获取指南)

3. **测试运行**

   进入 `Actions` > `Test-Workflow` > `Run workflow`

   测试工作流会获取 5 篇论文用于验证配置

4. **查看结果**

   检查 Actions 运行日志和接收邮箱

### 本地运行

```bash
# 克隆仓库
git clone https://github.com/YOUR_USERNAME/Zotero-Arxiv-Daily-Pro.git
cd Zotero-Arxiv-Daily-Pro

# 安装依赖（需要 uv）
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入您的配置

# 运行
uv run main.py

# 调试模式（仅处理 5 篇论文）
uv run main.py --debug
```

---

## API 配置获取指南

### 获取 Zotero 凭证

#### Zotero User ID
1. 访问 [Zotero Settings](https://www.zotero.org/settings/security)
2. 在页面顶部找到 "Your userID for use in API calls is XXXXXXXX"
3. 复制这串数字（这就是 `ZOTERO_ID`）
4. 位置参考：[截图示例](https://github.com/TideDra/zotero-arxiv-daily/blob/main/assets/userid.png)

#### Zotero API Key
1. 在同一页面向下滚动到 "API Keys" 部分
2. 点击 "Create new private key"
3. 设置：
   - Key Description: `Arxiv Daily`
   - Library Access: 勾选 "Allow library access" (只读)
   - Notes Access: 不勾选
   - Write Access: 不勾选
4. 点击 "Save Key" 并**立即复制**生成的 Key（只显示一次）

### 获取邮箱 SMTP 授权码

#### Gmail
1. 启用 [两步验证](https://myaccount.google.com/security)
2. 访问 [应用专用密码](https://myaccount.google.com/apppasswords)
3. 生成新密码并复制（去除空格）
4. SMTP 配置：`smtp.gmail.com:465`

#### QQ 邮箱
1. 登录 [QQ 邮箱网页版](https://mail.qq.com/)
2. 设置 → 账户 → POP3/IMAP/SMTP 服务
3. 开启 IMAP/SMTP，按提示发送短信
4. 复制授权码（16位字母）
5. SMTP 配置：`smtp.qq.com:465`

#### 163 邮箱
1. 登录 [163 邮箱](https://mail.163.com/)
2. 设置 → POP3/SMTP/IMAP
3. 开启服务并设置授权码
4. SMTP 配置：`smtp.163.com:465`

### LLM API 配置（可选）

**免费推荐**：[SiliconFlow](https://cloud.siliconflow.cn/i/b3XhBRAm)
- 注册后在 [API Keys](https://cloud.siliconflow.cn/account/ak) 创建密钥
- 推荐模型：`Qwen/Qwen2.5-7B-Instruct`
- API Base: `https://api.siliconflow.cn/v1`

**其他选择**：
- **OpenAI**: [API Keys](https://platform.openai.com/api-keys)，模型 `gpt-4o`
- **DeepSeek**: [平台](https://platform.deepseek.com/)，模型 `deepseek-chat`

### 图片提取配置（可选）

如需启用论文图表提取功能：
1. 设置 `ENABLE_IMAGE_EXTRACTION=True`
2. 获取 MinerU API Token 并配置 `MINERU_TOKEN`
3. 可选：调整 `MAX_IMAGES_PER_PAPER`（默认3）

---

## 部署指南

### 方式一：GitHub Actions（推荐）

#### 自动运行

默认每天 UTC 22:00 自动运行主工作流。修改运行时间：

```yaml
# .github/workflows/main.yml
on:
  schedule:
    - cron: '0 22 * * *'  # 修改为您需要的时间
```

#### 手动触发

- **主工作流**：`Send-emails-daily` - 获取昨日新论文
- **测试工作流**：`Test-Workflow` - 固定获取 5 篇论文

#### 高级配置

在 `Settings` > `Secrets and variables` > `Actions` > `Variables` 中添加（可选配置）：

| 变量名 | 必需 | 类型 | 说明 | 默认值 |
|--------|------|------|------|--------|
| `MAX_PAPER_NUM` | | int | 邮件中显示的最大论文数。此值直接影响执行时间（每篇约70秒生成TLDR）。`-1` 表示显示所有检索到的论文。 | `-1` |
| `SEND_EMPTY` | | bool | 当没有新论文时是否发送空邮件。 | `False` |
| `LANGUAGE` | | str | TLDR 的语言（直接嵌入到 LLM prompt 中）。 | `English` |
| `USE_LLM_API` | | bool | 是否使用云端 LLM API。设为 `True` 使用 API，`False` 使用本地 LLM。 | `False` |
| `OPENAI_API_KEY` | | str | 使用 LLM API 时的密钥。可在 [SiliconFlow](https://cloud.siliconflow.cn/i/b3XhBRAm) 获取免费 API。 | - |
| `OPENAI_API_BASE` | | str | LLM API 的基础 URL。未填写时默认为 OpenAI URL。 | `https://api.openai.com/v1` |
| `MODEL_NAME` | | str | LLM 模型名称。未填写时默认为 gpt-4o。使用 SiliconFlow 时推荐 Qwen/Qwen2.5-7B-Instruct。 | `gpt-4o` |
| `ZOTERO_IGNORE` | | str | gitignore 风格的 Zotero 集合过滤规则（每行一条）。了解更多：[gitignore](https://git-scm.com/docs/gitignore)。 | - |
| `ENABLE_IMAGE_EXTRACTION` | | bool | 是否启用图片提取功能。 | `False` |
| `MINERU_TOKEN` | | str | MinerU API Token（启用图片提取时需要）。 | - |
| `MAX_IMAGES_PER_PAPER` | | int | 每篇论文最多提取的图片数。 | `3` |

### 方式二：Docker 部署

```bash
# 构建镜像
docker build -t zotero-arxiv-daily .

# 运行容器
docker run --env-file .env zotero-arxiv-daily

# 或使用 docker-compose
docker-compose up
```

### 方式三：本地定时任务

使用 cron（Linux/macOS）：

```bash
# 编辑 crontab
crontab -e

# 添加定时任务（每天早上 6 点运行）
0 6 * * * cd /path/to/Zotero-Arxiv-Daily-Pro && /path/to/uv run main.py
```

---

## API 说明

### 核心模块

#### 1. `ArxivPaper` 类

论文对象封装，提供延迟加载属性。

```python
from paper import ArxivPaper
import arxiv

# 创建论文对象
search = arxiv.Search(id_list=["2301.00001"])
result = next(search.results())
paper = ArxivPaper(result)

# 访问基本属性
print(paper.title)          # 论文标题
print(paper.abstract)       # 摘要
print(paper.authors)        # 作者列表
print(paper.pdf_url)        # PDF 链接

# 访问延迟加载属性（首次访问时计算）
print(paper.tldr)           # LLM 生成的 TLDR
print(paper.tex)            # LaTeX 源码
print(paper.affiliations)   # 作者机构列表
print(paper.code_url)       # 代码仓库链接
```

**关键方法**：

- `get_tex()`: 下载并解析 LaTeX 源码
- `get_tldr(llm, language='English')`: 生成 TLDR
- `get_affiliations(llm)`: 提取作者机构
- `get_code_url()`: 查找代码链接

#### 2. `LLM` 抽象层

统一的 LLM 接口，支持本地模型和 API。

```python
from llm import LLM

# 本地模型
llm = LLM(use_api=False)

# API 模式
llm = LLM(
    use_api=True,
    api_key="your-api-key",
    base_url="https://api.siliconflow.cn/v1",
    model_name="Qwen/Qwen2.5-7B-Instruct"
)

# 调用
response = llm(
    prompt="Summarize this paper:",
    max_tokens=100,
    temperature=0.7
)
```

**全局单例**：

```python
from llm import GLOBAL_LLM

# 使用全局 LLM 实例
response = GLOBAL_LLM("Your prompt")
```

#### 3. `rerank_paper` 推荐算法

基于语义相似度的论文重排序。

```python
from recommender import rerank_paper

# zotero_corpus: List[Dict] - Zotero 文献库
# papers: List[ArxivPaper] - 待排序的论文
# max_paper_num: int - 最多返回的论文数

ranked_papers = rerank_paper(
    zotero_corpus=zotero_corpus,
    papers=arxiv_papers,
    max_paper_num=50
)
```

**算法细节**：

- 使用 `avsolatorio/GIST-small-Embedding-v0` 嵌入模型
- 时间衰减权重公式：`w = 1 / (1 + log10(i + 1))`
- 相似度得分：加权余弦相似度的平均值

#### 4. `MinerUExtractor` 图片提取

集成 MinerU API 提取 PDF 图表。

```python
from image_analyzer import MinerUExtractor, ImageImportanceAnalyzer

# 初始化提取器
extractor = MinerUExtractor(token="your-mineru-token")

# 提取图片
images = extractor.extract_images_from_pdf(
    pdf_url="https://arxiv.org/pdf/2301.00001.pdf",
    max_images=5
)

# 图片重要性分析
analyzer = ImageImportanceAnalyzer()
for img_path in image_paths:
    score, reason = analyzer.analyze_image(img_path)
    print(f"Score: {score}, Reason: {reason}")
```

#### 5. 邮件渲染与发送

```python
from construct_email import render_email, send_email

# 渲染邮件
html_content = render_email(
    papers=ranked_papers,
    scores=[0.85, 0.78, 0.72],
    llm=llm,
    enable_images=True,
    enable_code_links=True
)

# 发送邮件
send_email(
    smtp_server="smtp.gmail.com",
    smtp_port=465,
    sender="sender@email.com",
    password="password",
    receiver="receiver@email.com",
    subject="Daily arXiv 2025/12/03",
    html_content=html_content
)
```

---

## 使用示例

### 示例 1：自定义推荐流程

```python
import os
from pyzotero import zotero
import arxiv
from paper import ArxivPaper
from recommender import rerank_paper
from llm import LLM

# 1. 获取 Zotero 文献库
zot = zotero.Zotero(
    library_id=os.getenv('ZOTERO_ID'),
    library_type='user',
    api_key=os.getenv('ZOTERO_KEY')
)
items = zot.everything(zot.items(itemType='journalArticle'))
zotero_corpus = [
    {"title": item['data']['title'], "abstract": item['data'].get('abstractNote', '')}
    for item in items if item['data'].get('abstractNote')
]

# 2. 获取 arXiv 新论文
query = "cat:cs.AI OR cat:cs.CV OR cat:cs.LG"
search = arxiv.Search(query=query, max_results=100, sort_by=arxiv.SortCriterion.SubmittedDate)
papers = [ArxivPaper(result) for result in search.results()]

# 3. 重排序
ranked_papers = rerank_paper(zotero_corpus, papers, max_paper_num=20)

# 4. 生成 TLDR
llm = LLM(use_api=False)
for paper in ranked_papers[:5]:
    print(f"\nTitle: {paper.title}")
    print(f"TLDR: {paper.get_tldr(llm, language='Chinese')}")
```

### 示例 2：批量提取论文图表

```python
from image_analyzer import MinerUExtractor, ImageImportanceAnalyzer
import os

extractor = MinerUExtractor(token=os.getenv('MINERU_TOKEN'))
analyzer = ImageImportanceAnalyzer()

papers = [...]  # ArxivPaper 对象列表

for paper in papers:
    print(f"Processing: {paper.title}")

    # 提取图片
    images = extractor.extract_images_from_pdf(
        pdf_url=paper.pdf_url,
        max_images=10
    )

    # 分析重要性
    scored_images = []
    for img in images:
        score, reason = analyzer.analyze_image(img['path'])
        scored_images.append({
            'path': img['path'],
            'score': score,
            'reason': reason
        })

    # 排序并选择 top 3
    top_images = sorted(scored_images, key=lambda x: x['score'], reverse=True)[:3]
    print(f"Top images: {[img['reason'] for img in top_images]}")
```

### 示例 3：自定义过滤规则

```python
from gitignore_parser import parse_gitignore
import os

# 创建过滤规则文件
rules = """
# 排除综述类论文
**/survey
**/review

# 排除特定领域
Robotics/
Hardware/

# 但保留某些子集合
!LLM/survey
!Vision/review
"""

# 保存到文件
with open('.zotero_ignore', 'w') as f:
    f.write(rules)

# 使用过滤器
matcher = parse_gitignore('.zotero_ignore')

# 过滤 Zotero 集合
filtered_items = [
    item for item in zotero_items
    if not matcher(item['collection_path'])
]
```

### 示例 4：使用不同的 LLM API

```python
from llm import LLM

# OpenAI
llm_openai = LLM(
    use_api=True,
    api_key=os.getenv('OPENAI_API_KEY'),
    base_url="https://api.openai.com/v1",
    model_name="gpt-4o"
)

# SiliconFlow (免费)
llm_silicon = LLM(
    use_api=True,
    api_key=os.getenv('SILICONFLOW_API_KEY'),
    base_url="https://api.siliconflow.cn/v1",
    model_name="Qwen/Qwen2.5-7B-Instruct"
)

# Ollama (本地)
llm_ollama = LLM(
    use_api=True,
    api_key="ollama",
    base_url="http://localhost:11434/v1",
    model_name="qwen2.5:7b"
)

# 使用
paper = ArxivPaper(...)
tldr = paper.get_tldr(llm_silicon, language='Chinese')
```

---

## 配置说明

### 环境变量完整列表

以下是所有可配置的环境变量（在 GitHub Actions 中配置为 Secrets 或 Variables）：

| 变量名 | 必需 | 类型 | 说明 | 默认值 |
|--------|------|------|------|--------|
| `ZOTERO_ID` | ✅ | str | Zotero 用户 ID（数字串）。[获取方式](#获取-zotero-凭证) | - |
| `ZOTERO_KEY` | ✅ | str | Zotero API Key（只读权限）。[获取方式](#获取-zotero-凭证) | - |
| `ARXIV_QUERY` | ✅ | str | arXiv 类别查询（用 `+` 连接）。[类别列表](https://arxiv.org/category_taxonomy) | - |
| `SMTP_SERVER` | ✅ | str | SMTP 服务器地址。[配置说明](#获取邮箱-smtp-授权码) | - |
| `SMTP_PORT` | ✅ | int | SMTP 端口（SSL: 465, TLS: 587） | - |
| `SENDER` | ✅ | str | 发件邮箱地址 | - |
| `SENDER_PASSWORD` | ✅ | str | 邮箱 SMTP 授权码（**非登录密码**） | - |
| `RECEIVER` | ✅ | str | 收件邮箱地址 | - |
| `MAX_PAPER_NUM` | | int | 最多推荐论文数（影响执行时间）。`-1` 表示全部 | `-1` |
| `SEND_EMPTY` | | bool | 无新论文时是否发送空邮件 | `False` |
| `LANGUAGE` | | str | TLDR 生成语言（嵌入 prompt） | `English` |
| `USE_LLM_API` | | bool | 使用云端 API（`True`）或本地 LLM（`False`） | `False` |
| `OPENAI_API_KEY` | | str | LLM API 密钥。[免费获取](https://cloud.siliconflow.cn/i/b3XhBRAm) | - |
| `OPENAI_API_BASE` | | str | LLM API URL | `https://api.openai.com/v1` |
| `MODEL_NAME` | | str | LLM 模型名称 | `gpt-4o` |
| `ZOTERO_IGNORE` | | str | Zotero 集合过滤规则（gitignore 风格，每行一条） | - |
| `ENABLE_IMAGE_EXTRACTION` | | bool | 启用 MinerU 图片提取 | `False` |
| `MINERU_TOKEN` | | str | MinerU API Token | - |
| `MAX_IMAGES_PER_PAPER` | | int | 每篇论文最多提取图片数 | `3` |

### arXiv 类别参考

访问 [arXiv Category Taxonomy](https://arxiv.org/category_taxonomy) 查看完整列表。

常用类别：

- `cs.AI` - Artificial Intelligence
- `cs.CL` - Computation and Language (NLP)
- `cs.CV` - Computer Vision
- `cs.LG` - Machine Learning
- `cs.RO` - Robotics
- `stat.ML` - Machine Learning (Statistics)

### SMTP 配置参考

| 邮箱服务商 | SMTP 服务器 | 端口 | 说明 |
|-----------|-------------|------|------|
| Gmail | `smtp.gmail.com` | `465` (SSL) / `587` (TLS) | 需要开启"应用专用密码" |
| QQ 邮箱 | `smtp.qq.com` | `465` (SSL) / `587` (TLS) | 使用"授权码" |
| 163 邮箱 | `smtp.163.com` | `465` (SSL) / `994` (SSL) | 使用"授权码" |
| Outlook | `smtp-mail.outlook.com` | `587` (TLS) | 使用邮箱密码 |

---

## 常见问题

### Q1: 为什么没有收到邮件？

**排查步骤**：

1. 检查 Actions 运行日志是否有错误
2. 确认 SMTP 配置正确（服务器、端口、授权码）
3. 检查垃圾邮件文件夹
4. 尝试手动触发测试工作流
5. 确认昨日 arXiv 有新论文发布（周末和节假日无新论文）

### Q2: GitHub Actions 运行超时怎么办？

**原因**：每篇论文生成 TLDR 约需 70 秒（使用本地 LLM）

**解决方案**：

- 设置 `MAX_PAPER_NUM` 限制论文数量（推荐 20-50）
- 使用 `USE_LLM_API=True` 切换到 API 模式（更快）
- 使用自托管 Runner 或本地部署

### Q3: 如何获取 Zotero API Key？

1. 访问 [Zotero Settings](https://www.zotero.org/settings/security)
2. 在 "API Keys" 部分点击 "Create new private key"
3. 勾选 "Allow library access" (Read Only)
4. 点击 "Save Key" 并复制生成的 Key

**User ID** 位于同一页面顶部（一串数字）

### Q4: 支持哪些 LLM？

**本地模型**：
- Qwen2.5-3B-Instruct (默认，GGUF 格式，约 3GB)
- 其他兼容 llama.cpp 的 GGUF 模型

**API 模式**：
- OpenAI (GPT-4, GPT-3.5)
- SiliconFlow (免费额度，推荐 Qwen2.5-7B)
- DeepSeek
- Ollama (本地 API)
- 任何 OpenAI 兼容 API

### Q5: 如何自定义邮件模板？

编辑 `construct_email.py` 中的 HTML 模板：

```python
# 修改邮件样式
html_content = f"""
<html>
<head>
    <style>
        /* 在这里自定义 CSS */
        body {{ font-family: Arial, sans-serif; }}
        .paper-card {{ background: #f0f0f0; padding: 20px; }}
    </style>
</head>
<body>
    <!-- 自定义邮件内容 -->
</body>
</html>
"""
```

### Q6: MinerU 图片提取失败？

**检查清单**：

1. 确认设置了 `MINERU_TOKEN` 环境变量
2. 检查 MinerU API 配额是否用尽
3. 确认论文有可下载的 PDF
4. 查看 Actions 日志中的具体错误信息

### Q7: 如何过滤掉某些 Zotero 集合？

设置 `ZOTERO_IGNORE` 仓库变量：

```
# 排除整个集合
AI Agent/
Robotics/

# 排除所有名为 "survey" 的子集合
**/survey

# 使用通配符
**/old-papers

# 例外规则（保留）
!Important/survey
```

---

## 开发指南

### 项目结构

```
Zotero-Arxiv-Daily-Pro/
├── main.py                    # 主入口
├── paper.py                   # ArxivPaper 类
├── recommender.py             # 推荐算法
├── llm.py                     # LLM 抽象层
├── construct_email.py         # 邮件渲染和发送
├── image_analyzer.py          # MinerU 图片分析
├── extract_mineru_images.py   # 图片提取脚本
├── pyproject.toml             # 项目依赖
├── .env.example               # 环境变量模板
├── .github/workflows/         # GitHub Actions 工作流
│   ├── main.yml              # 主工作流
│   └── test.yml              # 测试工作流
├── assets/                    # 静态资源
├── docs/                      # 文档（即将创建）
└── README.md                  # 本文件
```

### 添加新功能

1. **Fork 并克隆仓库**
   ```bash
   git clone https://github.com/YOUR_USERNAME/Zotero-Arxiv-Daily-Pro.git
   cd Zotero-Arxiv-Daily-Pro
   ```

2. **创建功能分支**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **安装开发依赖**
   ```bash
   uv sync --dev
   ```

4. **开发并测试**
   ```bash
   # 使用调试模式快速测试
   uv run main.py --debug
   ```

5. **提交 Pull Request**
   - 所有 PR 应合并到 `dev` 分支
   - 确保代码通过 lint 检查
   - 添加必要的文档说明

### 代码规范

- 遵循 PEP 8
- 使用 type hints
- 添加 docstrings
- 保持函数简洁（单一职责）

### 测试

```bash
# 运行测试
uv run pytest

# 代码格式检查
uv run ruff check .

# 类型检查
uv run mypy .
```

---

## 性能优化建议

### GitHub Actions 优化

- 设置合理的 `MAX_PAPER_NUM`（推荐 20-50）
- 使用 API 模式而非本地 LLM
- 缓存模型文件（已在工作流中配置）

### 本地运行优化

- 使用 GPU 加速（修改 llm.py 中的 `n_gpu_layers`）
- 调整 LLM 参数（`max_tokens`, `temperature`）
- 并行处理论文（修改 construct_email.py）

---

## 许可证

本项目采用 **AGPLv3** 许可证。详见 [LICENSE](LICENSE) 文件。

### 核心依赖

- [pyzotero](https://github.com/urschrei/pyzotero) - Zotero API
- [arxiv](https://github.com/lukasschwab/arxiv.py) - arXiv API
- [sentence-transformers](https://github.com/UKPLab/sentence-transformers) - 嵌入模型
- [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) - 本地 LLM

---

## 致谢

### 原项目致谢

本项目基于 **[TideDra/zotero-arxiv-daily](https://github.com/TideDra/zotero-arxiv-daily)** 进行改进和扩展。

感谢原作者 [@TideDra](https://github.com/TideDra) 提供的优秀基础框架！原项目实现了基于 Zotero 文献库的 arXiv 论文推荐核心功能，为本项目奠定了坚实的基础。

**在原项目基础上的主要改进**：
- 🎨 **多模态增强**：集成 MinerU 实现论文关键图表自动提取
- 🤖 **灵活的 LLM 支持**：同时支持本地模型（llama.cpp）和多种 API（OpenAI、SiliconFlow、DeepSeek 等）
- 📧 **优化的邮件展示**：重新设计邮件模板，增强可读性和美观度
- 🔧 **更强大的配置系统**：
  - gitignore 风格的文献过滤规则
  - 功能开关和懒加载配置
  - 更丰富的自定义选项
- 📚 **完善的文档**：详细的 API 说明、使用示例和配置指南
- 🚀 **性能优化**：改进的工作流和依赖管理

### 依赖项目和服务

感谢以下项目和服务：

- [Zotero](https://www.zotero.org/) - 文献管理
- [arXiv](https://arxiv.org/) - 论文预印本平台
- [Hugging Face](https://huggingface.co/) - 模型托管
- [SiliconFlow](https://siliconflow.cn/) - 免费 LLM API
- [MinerU](https://mineru.net/) - PDF 图表提取

---

## 贡献者

感谢所有为本项目做出贡献的开发者！

<a href="https://github.com/YOUR_USERNAME/Zotero-Arxiv-Daily-Pro/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=YOUR_USERNAME/Zotero-Arxiv-Daily-Pro" />
</a>

---

## Star 历史

[![Star History Chart](https://api.star-history.com/svg?repos=YOUR_USERNAME/Zotero-Arxiv-Daily-Pro&type=Date)](https://star-history.com/#YOUR_USERNAME/Zotero-Arxiv-Daily-Pro&Date)

---

<div align="center">

**如果这个项目对您有帮助，请给一个 ⭐️ Star！**

[报告 Bug](https://github.com/YOUR_USERNAME/Zotero-Arxiv-Daily-Pro/issues) · [功能建议](https://github.com/YOUR_USERNAME/Zotero-Arxiv-Daily-Pro/issues)

</div>
