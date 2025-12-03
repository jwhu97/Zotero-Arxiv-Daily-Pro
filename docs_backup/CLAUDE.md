# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Zotero-arXiv-Daily 是一个基于 GitHub Actions 的自动化论文推荐系统，根据用户的 Zotero 文献库推荐 arXiv 上的新论文，并通过邮件发送推荐结果。

## 常用命令

### 运行项目
```bash
# 本地运行（需要先设置环境变量）
uv run main.py

# 调试模式（仅获取 5 篇论文）
uv run main.py --debug
```

### 依赖管理
- 项目使用 `uv` 进行包管理
- 依赖定义在 `pyproject.toml` 中
- Python 版本要求: >= 3.11

## 核心架构

### 主要模块

1. **main.py** - 主入口
   - 参数解析（支持命令行参数和环境变量）
   - 协调整个工作流：获取 Zotero 文献 → 获取 arXiv 论文 → 重排序 → 生成 TLDR → 发送邮件

2. **paper.py** - ArxivPaper 类
   - 封装单篇 arXiv 论文的所有信息和操作
   - `@cached_property` 用于延迟计算和缓存：
     - `tex`: 下载并解析论文源码（.tar.gz）
     - `tldr`: 使用 LLM 生成论文摘要
     - `affiliations`: 从 LaTeX 源码提取作者单位
     - `code_url`: 从 PapersWithCode 获取代码链接
   - 重要：在 paper.py:14 中对 arxiv 包进行了 monkey patch 以修复 PDF URL 获取问题

3. **recommender.py** - 推荐算法
   - 使用 sentence-transformers 计算论文与 Zotero 文献库的相似度
   - 时间衰减权重：越新的文献权重越高（基于对数衰减）
   - 默认使用 `avsolatorio/GIST-small-Embedding-v0` 模型

4. **llm.py** - LLM 抽象层
   - 支持两种模式：
     - 本地模型：Qwen2.5-3B-Instruct (GGUF 格式，约 3GB)
     - API 模式：OpenAI 兼容 API（如 SiliconFlow）
   - 全局单例模式 (`GLOBAL_LLM`)

5. **construct_email.py** - 邮件渲染和发送
   - 渲染 HTML 邮件，包含论文信息、相关度星级、PDF/Code 链接
   - 支持 SMTP (TLS/SSL)

### 工作流程

1. 从 Zotero API 获取用户文献库（支持 gitignore 风格的过滤规则）
2. 从 arXiv RSS feed 获取昨日新提交的论文
3. 使用嵌入模型计算新论文与文献库的语义相似度，按相关度排序
4. 对每篇论文：
   - 下载 LaTeX 源码（如果可用）
   - 提取 introduction 和 conclusion 部分
   - 使用 LLM 生成 TLDR
   - 提取作者单位信息
   - 查找开源代码链接
5. 渲染 HTML 邮件并发送

### 环境变量

必需的环境变量：
- `ZOTERO_ID`, `ZOTERO_KEY`: Zotero API 认证
- `ARXIV_QUERY`: arXiv 类别（如 `cs.AI+cs.CV+cs.LG`）
- `SMTP_SERVER`, `SMTP_PORT`, `SENDER`, `SENDER_PASSWORD`, `RECEIVER`: 邮件配置

可选的环境变量：
- `USE_LLM_API`: 是否使用 API 而非本地 LLM（默认 False）
- `OPENAI_API_KEY`, `OPENAI_API_BASE`, `MODEL_NAME`: API 配置
- `MAX_PAPER_NUM`: 最多推荐的论文数（-1 表示无限制）
- `LANGUAGE`: TLDR 的语言（默认 English）
- `ZOTERO_IGNORE`: gitignore 风格的 Zotero 集合过滤规则

### GitHub Actions

- **主工作流** (`.github/workflows/main.yml`): 每天 22:00 UTC 自动运行
- **测试工作流** (`.github/workflows/test.yml`): 手动触发，固定获取 5 篇论文用于调试
- 支持通过 `REPOSITORY` 和 `REF` 变量从上游拉取最新代码

## 重要实现细节

### LaTeX 源码处理
- 主 tex 文件识别：优先通过 .bbl 文件推断，其次查找 `\begin{document}` 块
- 预处理：移除注释、多余空白、引用、图表等
- 递归处理 `\input{}` 和 `\include{}` 指令

### 错误处理
- arXiv 源码下载失败（404）被视为正常情况，不中断流程
- LLM API 调用失败有重试机制（最多 3 次，间隔 3 秒）
- SMTP 连接优先尝试 TLS，失败时回退到 SSL

### 性能考虑
- 每篇论文生成 TLDR 约需 70 秒（使用本地 LLM）
- GitHub Actions 限制：公共仓库 6 小时/次，2000 分钟/月
- `MAX_PAPER_NUM` 应根据实际情况设置以避免超时

## 贡献规范

- 所有 PR 应合并到 `dev` 分支而非 `main` 分支
- 项目采用 AGPLv3 许可证
