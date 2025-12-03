  📋 完整工作流程

  1. 初始化阶段 (main.py:1-173)

  - 设置 Hugging Face 镜像源
  - 对 arxiv 包进行 monkey patch 修复 PDF URL 获取问题
  - 解析命令行参数和环境变量(支持 Zotero、SMTP、LLM 等配置)
  - 配置日志级别(调试模式或正常模式)

  2. 获取 Zotero 文献库 (main.py:175-181)

  get_zotero_corpus() → filter_corpus()
  - 连接 Zotero API 获取用户的会议论文、期刊论文、预印本
  - 过滤掉没有摘要的文献
  - 构建每篇文献的集合路径
  - 应用 gitignore 风格的过滤规则(可选)

  3. 获取 arXiv 新论文 (main.py:182-183)

  get_arxiv_paper()
  - 从 arXiv RSS feed 获取指定类别的论文
  - 正常模式:获取昨日所有标记为"new"的论文(分批 20 篇获取)
  - 调试模式:只获取 5 篇论文用于测试

  4. 智能重排序 (main.py:189-192, recommender.py)

  rerank_paper()
  - 使用 GIST-small-Embedding-v0 模型对论文和文献库进行向量编码
  - 计算每篇候选论文与 Zotero 文献库中所有论文的语义相似度
  - 应用时间衰减权重:
  weight = 1 / (1 + log10(论文排名 + 1))
  - 越新添加的文献权重越高
  - 计算加权相似度分数并排序
  - 限制推荐数量(可通过 MAX_PAPER_NUM 设置)

  5. 初始化 LLM (main.py:193-198, llm.py)

  两种模式:
  - 本地模式(默认):下载 Qwen2.5-3B-Instruct GGUF 模型(约 3GB)
  - API 模式:使用 OpenAI 兼容 API(如 SiliconFlow)

  6. 生成邮件内容 (main.py:200, construct_email.py)

  render_email()
  对每篇论文依次处理:

  6.1 获取 LaTeX 源码 (paper.py:78-161)

  - 下载论文源码压缩包(.tar.gz)
  - 处理 404 错误(源码不存在属于正常情况)
  - 识别主 tex 文件:
    a. 优先通过 .bbl 文件推断
    b. 其次查找包含 \begin{document} 的文件
  - 预处理 LaTeX:
    - 移除注释(%、\begin{comment}等)
    - 处理 \input{} 和 \include{} 指令
    - 清理多余空白

  6.2 生成 TLDR (paper.py:164-214)

  - 从 LaTeX 中提取 Introduction 和 Conclusion 章节
  - 移除引用(\cite)、图表(\begin{figure})等
  - 构建 prompt(包含标题、摘要、introduction、conclusion)
  - 截断到 4000 tokens(使用 gpt-4o tokenizer 估算)
  - 调用 LLM 生成一句话摘要(语言可配置)

  6.3 提取作者单位 (paper.py:217-256)

  - 从 LaTeX 的 \author 或 \begin{document} 到 \begin{abstract} 区域提取
  - 使用 LLM 解析出 Python 列表格式的单位列表
  - 注意:当前版本中此功能在 construct_email.py:143 被临时禁用

  6.4 查找开源代码 (paper.py:54-75)

  - 通过 Papers with Code API 查询论文的 GitHub 仓库
  - 注意:当前版本在 construct_email.py:144 被临时禁用

  6.5 渲染 HTML (construct_email.py:62-102)

  - 星级评分系统:根据相似度分数(6-8 区间)映射到 0-5 星
  - 显示作者(超过 5 人时显示前 3 人和后 2 人)
  - 包含 arXiv ID、TLDR、PDF 链接、Code 链接(如果有)
  - 每篇论文处理完后等待 2 秒(construct_email.py:146)

  7. 发送邮件 (main.py:201-203, construct_email.py:151-178)

  send_email()
  - 自动根据端口选择加密方式:
    - 465 端口:使用 SMTP_SSL
    - 其他端口:尝试 STARTTLS,失败则回退到 SSL
  - 邮件主题格式:Daily arXiv YYYY/MM/DD
  - 发送 HTML 格式邮件

  8. GitHub Actions 自动化

  - 主工作流:每天 UTC 22:00 自动运行
  - 测试工作流:手动触发,使用调试模式

  ⚙️ 关键设计特点

  1. 延迟计算:使用 @cached_property 装饰器,论文的 tex、tldr、affiliations、code_url 只在首次访问时计算
  2. 错误容错:LaTeX 源码下载失败不会中断流程,LLM API 调用有 3 次重试机制
  3. Token 控制:所有 LLM prompt 都截断到 4000 tokens 以控制成本
  4. 时间优化:每篇论文生成 TLDR 约需 70 秒(本地 LLM),因此限制 MAX_PAPER_NUM 很重要

  🔍 性能瓶颈

  从代码注释可以看出,当前版本为加速测试:
  - construct_email.py:143 临时禁用了单位提取(需要调用 LLM)
  - construct_email.py:144 临时禁用了代码链接查询(网络请求)
  - construct_email.py:146 将等待时间从 10 秒减少到 2 秒


12.1修改_hcz
  🎯 修改总结

  | 文件                | 行号      | 修改内容                           | 原因                     |
  |--------------------|---------|--------------------------------|------------------------|
  | main.py            | 1-3     | 新增 HF 镜像设置                     | 加速国内下载 Hugging Face 模型 |
  | construct_email.py | 135-146 | 跳过 affiliations 和 code_url     | 避免网络超时,减少 LLM 调用       |
  | construct_email.py | 146     | time.sleep(10) → time.sleep(2) | 加速测试流程                 |
  | construct_email.py | 162-174 | 改进 SMTP 连接逻辑                   | 根据端口智能选择,添加超时保护        |