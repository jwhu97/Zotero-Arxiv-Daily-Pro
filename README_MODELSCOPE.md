# 文献追踪助手 | Zotero-arXiv-Daily-Pro

<div align="center">

**基于 Zotero 文献库的智能论文推荐系统**

[![GitHub](https://img.shields.io/badge/GitHub-HcZhe/Zotero--Arxiv--Daily--Pro-blue?logo=github)](https://github.com/HcZhe/Zotero-Arxiv-Daily-Pro)
[![License](https://img.shields.io/badge/license-AGPLv3-blue.svg)](https://github.com/HcZhe/Zotero-Arxiv-Daily-Pro/blob/main/LICENSE)

</div>

---

## 📺 演示视频

<p align="center">
  <video src="Zotero学术日报小助手演示视频.mp4" controls width="700">
    您的浏览器不支持 video 标签。
  </video>
</p>

观看完整演示视频了解系统如何工作: [点击下载视频](Zotero学术日报小助手演示视频.mp4)

## 📚 项目简介

**文献追踪助手**是一个智能论文推荐系统，每天自动从 arXiv 筛选与您研究方向最相关的论文，并通过邮件推送精美报告。

### 效果展示

<p align="center">
  <img src="图片1.jpg" alt="Zotero学术日报助手展示" width="700"/>
  <br/>
  <em>系统整体展示 - 支持PC端和移动端</em>
</p>

### 它能做什么？

1. 📖 **分析您的文献库** - 读取 Zotero 中的论文，理解您的研究兴趣
2. 🔍 **智能筛选新论文** - 使用语义相似度算法从 arXiv 每日新论文中推荐最相关的
3. 📧 **自动邮件推送** - 发送包含 AI 摘要、关键图表、代码链接的精美报告

### 邮件展示效果

<table align="center">
  <tr>
    <td align="center">
      <img src="邮件内容.jpg" alt="PC端邮件展示" width="400"/>
      <br/>
      <em>PC端邮件展示</em>
    </td>
    <td align="center">
      <img src="手机端.jpg" alt="手机端邮件展示" width="250"/>
      <br/>
      <em>手机端邮件展示</em>
    </td>
  </tr>
</table>

## ✨ 核心特性

### 完全免费
- 基于 GitHub Actions 运行，无需服务器
- 零成本部署，每月 2000 分钟免费额度

### 个性化推荐
- 语义相似度算法（sentence-transformers）
- 时间衰减权重（新文献权重更高）
- 平均推荐准确率 76%+

### AI 增强内容
- **TLDR 生成**：一句话总结论文核心（支持中英文）
- **图表提取**：自动提取关键图表（MinerU + Qwen3-VL）
- **代码识别**：自动查找 GitHub 开源实现
- **机构解析**：识别作者所属机构

### 灵活配置
- **本地 LLM**：Qwen2.5-3B（3GB，完全离线）
- **API 支持**：OpenAI、SiliconFlow（免费）、DeepSeek
- **过滤规则**：gitignore 风格的文献库过滤
- **多邮箱支持**：Gmail、QQ、163、Outlook

## 🎯 使用流程

### 步骤 1：准备 Zotero 账号

1. 注册 Zotero：https://www.zotero.org/user/register
2. 安装浏览器插件并添加至少 20 篇论文

### 步骤 2：Fork GitHub 仓库

访问：https://github.com/HcZhe/Zotero-Arxiv-Daily-Pro

点击右上角 **Fork** 按钮

### 步骤 3：使用本配置助手

在本页面的 **⚙️ 配置生成器** 标签页：
1. 填写 Zotero 和邮箱配置信息
2. 点击"生成配置指南"
3. 复制生成的配置

### 步骤 4：配置 GitHub Secrets

1. 进入您 Fork 的仓库
2. Settings → Secrets and variables → Actions
3. 点击 "New repository secret"
4. 按配置指南逐个添加 Secrets

### 步骤 5：测试运行

1. 进入 Actions 页面
2. 选择 "Test-Workflow"
3. 点击 "Run workflow"
4. 等待运行完成，检查邮箱

### 步骤 6：享受每日推荐

配置完成后，系统将每天 UTC 22:00 自动运行，推送论文到您的邮箱！

## 🛠️ 技术架构

### 推荐算法
- 嵌入模型：GIST-small-Embedding-v0（33MB）
- 相似度计算：加权余弦相似度
- 时间衰减：`w = 1 / (1 + log10(rank + 1))`

### LLM 集成
- 本地：Qwen2.5-3B-Instruct（llama.cpp）
- API：OpenAI / SiliconFlow / DeepSeek
- 生成速度：70秒/篇（本地）或 3秒/篇（API）

### 图表提取
- PDF 解析：MinerU API
- 图片评分：Qwen3-VL-8B
- 提取准确率：78%+

### 部署方式
- GitHub Actions（推荐，免费）
- Docker 容器化
- 本地定时任务（cron）

## 📊 性能指标

| 指标 | 数值 |
|------|------|
| 推荐准确率（Precision@10） | 76% |
| TLDR 质量评分（1-5分） | 4.1+ |
| 图表提取成功率 | 94% |
| 平均执行时间（50篇论文） | 60-90 分钟 |
| 内存占用（峰值） | < 7GB |

## 🎓 适用人群

- **科研人员**：跟踪最新研究进展，发现相关工作
- **研究生**：快速了解领域动态，寻找论文灵感
- **工程师**：关注技术前沿，学习最新方法
- **学术团队**：统一推送机制，团队知识共享

## 📖 常见问题

### Q: 支持哪些 arXiv 类别？

常用组合：
- AI/ML：`cs.AI+cs.LG+stat.ML`
- 计算机视觉：`cs.CV+cs.AI+cs.LG`
- NLP：`cs.CL+cs.AI+cs.LG`
- 机器人：`cs.RO+cs.AI+cs.CV`

完整列表：https://arxiv.org/category_taxonomy

### Q: GitHub Actions 会超时吗？

免费版限制：
- 单次运行最长 6 小时
- 每月总计 2000 分钟

建议：
- 设置 `MAX_PAPER_NUM=50` 限制论文数
- 使用 API 模式加速（推荐 SiliconFlow 免费额度）

### Q: 邮件收不到怎么办？

检查清单：
1. SMTP 配置是否正确（授权码不是登录密码）
2. 查看 Actions 日志是否有错误
3. 检查垃圾邮件箱
4. 确认昨日 arXiv 有新论文（周末无新论文）

### Q: 如何获取免费 LLM API？

推荐 **SiliconFlow**（免费额度充足）：
1. 注册：https://cloud.siliconflow.cn/i/b3XhBRAm
2. 创建 API Key
3. 推荐模型：`Qwen/Qwen2.5-7B-Instruct`

## 🔗 相关资源

### 项目链接
- **GitHub 仓库**：https://github.com/HcZhe/Zotero-Arxiv-Daily-Pro
- **完整文档**：README.md
- **问题反馈**：GitHub Issues

### API 获取
- Zotero API：https://www.zotero.org/settings/security
- Gmail 授权码：https://myaccount.google.com/apppasswords
- 免费 LLM API：https://cloud.siliconflow.cn/i/b3XhBRAm

### 原项目致谢
本项目基于 [TideDra/zotero-arxiv-daily](https://github.com/TideDra/zotero-arxiv-daily) 改进，感谢原作者！

## 🚀 主要改进

相比原项目，本项目增加了：

- ✅ **多模态支持**：MinerU 图片提取 + Qwen3-VL 智能评分
- ✅ **更灵活的 LLM**：支持本地模型和多种 API
- ✅ **优化的邮件**：重新设计模板，增强可读性
- ✅ **强大的过滤**：gitignore 风格的文献库过滤规则
- ✅ **完善的文档**：详细的配置指南和使用示例
- ✅ **性能优化**：懒加载机制和资源管理

## 📝 许可证

本项目采用 AGPLv3 License 开源。

---

<div align="center">

**如果这个项目对您有帮助，请给一个 ⭐️ Star！**

Made with ❤️ by [HcZhe](https://github.com/HcZhe)

</div>
