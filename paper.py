from typing import Optional
from functools import cached_property
from tempfile import TemporaryDirectory
import arxiv
import tarfile
import re
import time
from llm import get_llm, get_vision_llm
import requests
from requests.adapters import HTTPAdapter, Retry
from loguru import logger
import tiktoken
from contextlib import ExitStack
from urllib.error import HTTPError
import base64
import io
from PIL import Image
import subprocess



class ArxivPaper:
    def __init__(self,paper:arxiv.Result):
        self._paper = paper
        self.score = None
    
    @property
    def title(self) -> str:
        return self._paper.title
    
    @property
    def summary(self) -> str:
        return self._paper.summary
    
    @property
    def authors(self) -> list[str]:
        return self._paper.authors
    
    @cached_property
    def arxiv_id(self) -> str:
        return re.sub(r'v\d+$', '', self._paper.get_short_id())
    
    @property
    def pdf_url(self) -> str:
        if self._paper.pdf_url is not None:
            return self._paper.pdf_url

        pdf_url = f"https://arxiv.org/pdf/{self.arxiv_id}.pdf"
        if self._paper.links is not None:
            pdf_url = self._paper.links[0].href.replace('abs','pdf')

        ## Assign pdf_url to self._paper.pdf_url for pdf downloading (Issue #119)
        self._paper.pdf_url = pdf_url

        return pdf_url

    @property
    def categories(self) -> list[str]:
        """
        获取论文的所有类别标签
        """
        return self._paper.categories

    @property
    def primary_category(self) -> str:
        """
        获取论文的主要类别标签
        """
        return self._paper.primary_category

    def _extract_code_url_from_text(self, text: str, source: str = "text") -> Optional[str]:
        r"""
        从文本中提取代码链接 (GitHub 或 Hugging Face)
        优先级: GitHub 仓库 > GitHub Pages > Hugging Face > 项目主页

        策略：
        1. 优先提取 LaTeX 结构化命令 \url{} 和 \href{} 中的 GitHub/HF 链接
        2. 使用通用正则匹配 GitHub/HF 链接
        3. 查找带有 "open-source"/"code"/"implementation" 等关键词的项目主页链接（兜底）
        """
        # 定义 GitHub/Hugging Face 的匹配模式
        code_platforms = [
            # GitHub repository patterns (优先匹配)
            (r'github\.com/[\w\-\.]+/[\w\-\.]+', 'GitHub repo'),
            # GitHub Pages patterns
            (r'[\w\-\.]+\.github\.io(?:/[\w\-\.]+)?', 'GitHub Pages'),
            # Hugging Face patterns
            (r'huggingface\.co/[\w\-\.]+/[\w\-\.]+', 'Hugging Face'),
        ]

        # 策略 1: 优先从 LaTeX 结构化命令中提取 GitHub/HF 链接
        structured_urls = []
        structured_urls.extend(re.findall(r'\\url\{([^}]+)\}', text, re.IGNORECASE))
        structured_urls.extend(re.findall(r'\\href\{([^}]+)\}', text, re.IGNORECASE))

        for url in structured_urls:
            for pattern, platform in code_platforms:
                if re.search(pattern, url, re.IGNORECASE):
                    if not url.startswith('http'):
                        url = 'https://' + url
                    url = re.sub(r'[.,;:)\]}]+$', '', url)
                    logger.debug(f"Found code URL in {source} (from LaTeX command) for {self.arxiv_id}: {url}")
                    return url

        # 策略 2: 通用正则匹配 GitHub/HF 链接（兜底）
        general_patterns = [
            r'https?://github\.com/[\w\-\.]+/[\w\-\.]+',
            r'https?://[\w\-\.]+\.github\.io(?:/[\w\-\.]+)?',
            r'https?://huggingface\.co/[\w\-\.]+/[\w\-\.]+',
        ]

        for pattern in general_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                url = matches[0]
                url = re.sub(r'[.,;:)\]}]+$', '', url)
                logger.debug(f"Found code URL in {source} (from general regex) for {self.arxiv_id}: {url}")
                return url

        # 策略 3: 查找带有代码相关关键词的项目主页链接
        # 关键词: open-source, code, implementation, available at, project page
        code_keywords = [
            r'open-source\s+(?:code|implementation)',  # "open-source implementation"
            r'(?:code|implementation)\s+(?:is\s+)?available',  # "code available"
            r'project\s+page',  # "project page"
            r'(?:code|implementation)\s+at',  # "code at"
        ]

        # 在关键词附近查找 URL
        for keyword in code_keywords:
            # 查找关键词后面 100 个字符内的 URL
            pattern = keyword + r'.{0,100}?(https?://[^\s\)}\]]+)'
            matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)
            if matches:
                url = matches[0]
                url = re.sub(r'[.,;:)\]}]+$', '', url)  # 移除末尾标点
                logger.debug(f"Found project page in {source} (with keyword '{keyword}') for {self.arxiv_id}: {url}")
                return url

        return None

    @cached_property
    def code_url(self) -> Optional[str]:
        # 1. 优先从 abstract 中提取
        url = self._extract_code_url_from_text(self.summary, "abstract")
        if url:
            return url

        # 2. 如果 abstract 中没有，尝试从 LaTeX 源码的前面部分提取
        if self.tex is not None:
            content = self.tex.get("all")
            if content is None:
                content = "\n".join(self.tex.values())

            # 简化策略：直接搜索文档前面 8000 字符
            # 这通常覆盖 preamble、title、author、abstract、introduction 开头
            # 足够找到第一页的代码链接
            front_text = content[:8000]
            logger.debug(f"Searching in LaTeX front matter ({len(front_text)} chars) for {self.arxiv_id}")
            url = self._extract_code_url_from_text(front_text, "LaTeX front matter")
            if url:
                return url

        # 3. 如果都没有找到，返回 None
        logger.debug(f"No code URL found for {self.arxiv_id}")
        return None
    
    @cached_property
    def tex(self) -> dict[str,str]:
        with ExitStack() as stack:
            tmpdirname = stack.enter_context(TemporaryDirectory())
            # file = self._paper.download_source(dirpath=tmpdirname)
            try:
                # 尝试下载源文件
                file = self._paper.download_source(dirpath=tmpdirname)
            except HTTPError as e:
                # 捕获 HTTP 错误
                if e.code == 404:
                    # 如果是 404 Not Found，说明源文件不存在，这是正常情况
                    logger.warning(f"Source for {self.arxiv_id} not found (404). Skipping source analysis.")
                    return None # 直接返回 None，后续依赖 tex 的代码会安全地处理
                else:
                    # 如果是其他 HTTP 错误 (如 503)，这可能是临时性问题，值得记录下来
                    logger.error(f"HTTP Error {e.code} when downloading source for {self.arxiv_id}: {e.reason}")
                    raise # 重新抛出异常，因为这可能是个需要关注的严重问题
            except Exception as e:
                logger.error(f"Error when downloading source for {self.arxiv_id}: {e}")
                return None
            try:
                tar = stack.enter_context(tarfile.open(file))
            except tarfile.ReadError:
                logger.debug(f"Failed to find main tex file of {self.arxiv_id}: Not a tar file.")
                return None
 
            tex_files = [f for f in tar.getnames() if f.endswith('.tex')]
            if len(tex_files) == 0:
                logger.debug(f"Failed to find main tex file of {self.arxiv_id}: No tex file.")
                return None
            
            bbl_file = [f for f in tar.getnames() if f.endswith('.bbl')]
            match len(bbl_file) :
                case 0:
                    if len(tex_files) > 1:
                        logger.debug(f"Cannot find main tex file of {self.arxiv_id} from bbl: There are multiple tex files while no bbl file.")
                        main_tex = None
                    else:
                        main_tex = tex_files[0]
                case 1:
                    main_name = bbl_file[0].replace('.bbl','')
                    main_tex = f"{main_name}.tex"
                    if main_tex not in tex_files:
                        logger.debug(f"Cannot find main tex file of {self.arxiv_id} from bbl: The bbl file does not match any tex file.")
                        main_tex = None
                case _:
                    logger.debug(f"Cannot find main tex file of {self.arxiv_id} from bbl: There are multiple bbl files.")
                    main_tex = None
            if main_tex is None:
                logger.debug(f"Trying to choose tex file containing the document block as main tex file of {self.arxiv_id}")
            #read all tex files
            file_contents = {}
            for t in tex_files:
                f = tar.extractfile(t)
                content = f.read().decode('utf-8',errors='ignore')
                #remove comments
                content = re.sub(r'%.*\n', '\n', content)
                content = re.sub(r'\\begin{comment}.*?\\end{comment}', '', content, flags=re.DOTALL)
                content = re.sub(r'\\iffalse.*?\\fi', '', content, flags=re.DOTALL)
                #remove redundant \n
                content = re.sub(r'\n+', '\n', content)
                content = re.sub(r'\\\\', '', content)
                #remove consecutive spaces
                content = re.sub(r'[ \t\r\f]{3,}', ' ', content)
                if main_tex is None and re.search(r'\\begin\{document\}', content):
                    main_tex = t
                    logger.debug(f"Choose {t} as main tex file of {self.arxiv_id}")
                file_contents[t] = content
            
            if main_tex is not None:
                main_source:str = file_contents[main_tex]
                #find and replace all included sub-files
                include_files = re.findall(r'\\input\{(.+?)\}', main_source) + re.findall(r'\\include\{(.+?)\}', main_source)
                for f in include_files:
                    if not f.endswith('.tex'):
                        file_name = f + '.tex'
                    else:
                        file_name = f
                    main_source = main_source.replace(f'\\input{{{f}}}', file_contents.get(file_name, ''))
                file_contents["all"] = main_source
            else:
                logger.debug(f"Failed to find main tex file of {self.arxiv_id}: No tex file containing the document block.")
                file_contents["all"] = None
        return file_contents
    
    @cached_property
    def tldr(self) -> str:
        introduction = ""
        conclusion = ""
        if self.tex is not None:
            content = self.tex.get("all")
            if content is None:
                content = "\n".join(self.tex.values())
            #remove cite
            content = re.sub(r'~?\\cite.?\{.*?\}', '', content)
            #remove figure
            content = re.sub(r'\\begin\{figure\}.*?\\end\{figure\}', '', content, flags=re.DOTALL)
            #remove table
            content = re.sub(r'\\begin\{table\}.*?\\end\{table\}', '', content, flags=re.DOTALL)
            #find introduction and conclusion
            # end word can be \section or \end{document} or \bibliography or \appendix
            match = re.search(r'\\section\{Introduction\}.*?(\\section|\\end\{document\}|\\bibliography|\\appendix|$)', content, flags=re.DOTALL)
            if match:
                introduction = match.group(0)
            match = re.search(r'\\section\{Conclusion\}.*?(\\section|\\end\{document\}|\\bibliography|\\appendix|$)', content, flags=re.DOTALL)
            if match:
                conclusion = match.group(0)
        llm = get_llm()
        prompt = """Given the title, abstract, introduction and the conclusion (if any) of a paper in latex format, generate a one-sentence TLDR summary in __LANG__:

        \\title{__TITLE__}
        \\begin{abstract}__ABSTRACT__\\end{abstract}
        __INTRODUCTION__
        __CONCLUSION__
        """
        prompt = prompt.replace('__LANG__', llm.lang)
        prompt = prompt.replace('__TITLE__', self.title)
        prompt = prompt.replace('__ABSTRACT__', self.summary)
        prompt = prompt.replace('__INTRODUCTION__', introduction)
        prompt = prompt.replace('__CONCLUSION__', conclusion)

        # use gpt-4o tokenizer for estimation
        enc = tiktoken.encoding_for_model("gpt-4o")
        prompt_tokens = enc.encode(prompt)
        prompt_tokens = prompt_tokens[:4000]  # truncate to 4000 tokens
        prompt = enc.decode(prompt_tokens)

        tldr = llm.generate(
            messages=[
                {
                    "role": "system",
                    "content": "You are an assistant who perfectly summarizes scientific paper, and gives the core idea of the paper to the user.",
                },
                {"role": "user", "content": prompt},
            ]
        )
        return tldr

    @cached_property
    def tags(self) -> list[str]:
        """
        从论文中提取关键技术词汇作为标签
        """
        llm = get_llm()

        # 准备用于提取标签的内容（标题+摘要，如果有tex则加上introduction的前部分）
        content_for_tags = f"Title: {self.title}\n\nAbstract: {self.summary}"

        if self.tex is not None:
            tex_content = self.tex.get("all")
            if tex_content is None:
                tex_content = "\n".join(self.tex.values())

            # 提取introduction的前1000个字符
            match = re.search(r'\\section\{Introduction\}(.*?)(\\section|\\end\{document\}|\\bibliography|\\appendix|$)', tex_content, flags=re.DOTALL)
            if match:
                intro = match.group(1)[:1000]
                content_for_tags += f"\n\nIntroduction (excerpt): {intro}"

        prompt = f"""Given the following research paper information, extract 5-8 key technical terms or concepts as tags. The tags should be in {llm.lang} and represent the main techniques, methods, datasets, or concepts discussed in the paper.

{content_for_tags}

Please return ONLY a Python list of strings (e.g., ['tag1', 'tag2', 'tag3']), without any additional explanation. Each tag should be concise (2-6 words)."""

        # use gpt-4o tokenizer for estimation
        enc = tiktoken.encoding_for_model("gpt-4o")
        prompt_tokens = enc.encode(prompt)
        prompt_tokens = prompt_tokens[:2000]  # 标签提取用更少的tokens
        prompt = enc.decode(prompt_tokens)

        try:
            tags_response = llm.generate(
                messages=[
                    {
                        "role": "system",
                        "content": f"You are an expert at extracting key technical terms from research papers. You always return results in {llm.lang}. You return ONLY a Python list format, nothing else.",
                    },
                    {"role": "user", "content": prompt},
                ]
            )

            # 提取返回结果中的列表
            tags_match = re.search(r'\[.*?\]', tags_response, flags=re.DOTALL)
            if tags_match:
                tags_list = eval(tags_match.group(0))
                tags_list = [str(tag).strip() for tag in tags_list]
                # 限制标签数量为5-8个
                return tags_list[:8]
            else:
                logger.debug(f"Failed to extract tags from LLM response for {self.arxiv_id}")
                return []
        except Exception as e:
            logger.debug(f"Failed to extract tags for {self.arxiv_id}: {e}")
            return []

    @cached_property
    def affiliations(self) -> Optional[list[str]]:
        if self.tex is not None:
            content = self.tex.get("all")
            if content is None:
                content = "\n".join(self.tex.values())
            #search for affiliations
            possible_regions = [r'\\author.*?\\maketitle',r'\\begin{document}.*?\\begin{abstract}']
            matches = [re.search(p, content, flags=re.DOTALL) for p in possible_regions]
            match = next((m for m in matches if m), None)
            if match:
                information_region = match.group(0)
            else:
                logger.debug(f"Failed to extract affiliations of {self.arxiv_id}: No author information found.")
                return None
            prompt = f"Given the author information of a paper in latex format, extract the affiliations of the authors in a python list format, which is sorted by the author order. If there is no affiliation found, return an empty list '[]'. Following is the author information:\n{information_region}"
            # use gpt-4o tokenizer for estimation
            enc = tiktoken.encoding_for_model("gpt-4o")
            prompt_tokens = enc.encode(prompt)
            prompt_tokens = prompt_tokens[:4000]  # truncate to 4000 tokens
            prompt = enc.decode(prompt_tokens)
            llm = get_llm()
            affiliations = llm.generate(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an assistant who perfectly extracts affiliations of authors from the author information of a paper. You should return a python list of affiliations sorted by the author order, like ['TsingHua University','Peking University']. If an affiliation is consisted of multi-level affiliations, like 'Department of Computer Science, TsingHua University', you should return the top-level affiliation 'TsingHua University' only. Do not contain duplicated affiliations. If there is no affiliation found, you should return an empty list [ ]. You should only return the final list of affiliations, and do not return any intermediate results.",
                    },
                    {"role": "user", "content": prompt},
                ]
            )

            try:
                affiliations = re.search(r'\[.*?\]', affiliations, flags=re.DOTALL).group(0)
                affiliations = eval(affiliations)
                affiliations = list(set(affiliations))
                affiliations = [str(a) for a in affiliations]
            except Exception as e:
                logger.debug(f"Failed to extract affiliations of {self.arxiv_id}: {e}")
                return None
            return affiliations

    @cached_property
    def overview_figure(self) -> Optional[dict]:
        """
        提取论文的overview/architecture图片并生成描述
        返回: {"image_base64": str, "caption": str, "description": str} 或 None
        """
        if self.tex is None:
            logger.debug(f"No LaTeX source available for {self.arxiv_id}, skipping overview figure extraction.")
            return None

        with ExitStack() as stack:
            try:
                tmpdirname = stack.enter_context(TemporaryDirectory())

                # 重新下载源文件以访问图片
                try:
                    file = self._paper.download_source(dirpath=tmpdirname)
                except HTTPError as e:
                    if e.code == 404:
                        logger.debug(f"Source for {self.arxiv_id} not found (404).")
                        return None
                    else:
                        logger.error(f"HTTP Error {e.code} when downloading source for {self.arxiv_id}: {e.reason}")
                        return None
                except Exception as e:
                    logger.error(f"Error downloading source for {self.arxiv_id}: {e}")
                    return None

                try:
                    tar = stack.enter_context(tarfile.open(file))
                except tarfile.ReadError:
                    logger.debug(f"Failed to open tar file for {self.arxiv_id}")
                    return None

                # 从LaTeX中找到包含关键词的figure
                content = self.tex.get("all")
                if content is None:
                    content = "\n".join(self.tex.values())

                # 匹配figure环境，查找包含关键词的caption
                # 定义关键词优先级（分数越高优先级越高）
                keyword_priorities = {
                    "overview": 10,           # 最高优先级
                    "architecture": 8,        # 架构图
                    "framework": 8,           # 框架图
                    "system": 6,              # 系统图
                    "pipeline": 6,            # 流程图
                    "proposed": 5,            # 提出的方法（常见）
                    "method": 4,              # 方法图
                    "approach": 4,            # 方案图
                    "workflow": 3,            # 工作流
                    "model": 2,               # 模型图（优先级较低，太泛）
                }

                figure_pattern = r'\\begin\{figure\*?\}(.*?)\\end\{figure\*?\}'
                figures = re.findall(figure_pattern, content, flags=re.DOTALL | re.IGNORECASE)

                # 收集所有匹配的figures及其优先级
                matched_figures = []

                for fig in figures:
                    # 提取caption
                    caption_match = re.search(r'\\caption\{(.*?)\}', fig, flags=re.DOTALL)
                    if caption_match:
                        caption = caption_match.group(1)
                        # 计算这个figure的优先级（累加所有匹配关键词的分数）
                        priority = 0
                        matched_keywords = []
                        for keyword, score in keyword_priorities.items():
                            if keyword in caption.lower():
                                priority += score
                                matched_keywords.append(keyword)

                        if priority > 0:  # 至少匹配了一个关键词
                            matched_figures.append({
                                'figure': fig,
                                'caption': caption,
                                'priority': priority,
                                'keywords': matched_keywords
                            })

                if not matched_figures:
                    # 降级策略：如果没有架构图，尝试找实验结果图
                    logger.debug(f"No architecture figure found for {self.arxiv_id}, trying fallback to result figures")

                    fallback_keywords = {
                        "result": 3,
                        "performance": 3,
                        "comparison": 2,
                        "evaluation": 2,
                        "experiment": 2,
                    }

                    for fig in figures:
                        caption_match = re.search(r'\\caption\{(.*?)\}', fig, flags=re.DOTALL)
                        if caption_match:
                            caption = caption_match.group(1)
                            priority = 0
                            matched_keywords = []
                            for keyword, score in fallback_keywords.items():
                                if keyword in caption.lower():
                                    priority += score
                                    matched_keywords.append(keyword)

                            if priority > 0:
                                matched_figures.append({
                                    'figure': fig,
                                    'caption': caption,
                                    'priority': priority,
                                    'keywords': matched_keywords,
                                    'is_fallback': True  # 标记为降级图片
                                })

                if not matched_figures:
                    logger.debug(f"No overview or result figure found in {self.arxiv_id}")
                    return None

                # 按优先级排序，取最高的
                matched_figures.sort(key=lambda x: x['priority'], reverse=True)
                best_match = matched_figures[0]
                target_figure = best_match['figure']
                target_caption = best_match['caption']

                logger.debug(f"Selected figure for {self.arxiv_id} with priority {best_match['priority']} (keywords: {best_match['keywords']})")

                # 提取图片文件名
                image_patterns = [
                    r'\\includegraphics(?:\[.*?\])?\{([^}]+)\}',
                    r'\\includegraphics\[.*?\]\{([^}]+)\}'
                ]

                image_file = None
                for pattern in image_patterns:
                    match = re.search(pattern, target_figure)
                    if match:
                        image_file = match.group(1)
                        break

                if image_file is None:
                    logger.debug(f"No image file found in target figure for {self.arxiv_id}")
                    return None

                # 清理文件名（移除路径、添加常见扩展名）
                image_file = image_file.strip().replace('./', '')
                logger.debug(f"Looking for image file: {image_file}")

                # 列出tar中所有文件用于调试和模糊匹配
                all_files = tar.getnames()
                image_files_in_tar = [f for f in all_files if any(f.lower().endswith(ext) for ext in ['.png', '.pdf', '.jpg', '.jpeg', '.eps'])]
                logger.debug(f"Available image files in tar: {image_files_in_tar[:10]}")  # 只显示前10个

                # 尝试多种可能的路径和扩展名
                possible_paths = []

                # 1. 原始路径 + 各种扩展名
                base_name = re.sub(r'\.\w+$', '', image_file)  # 移除现有扩展名
                for ext in ['', '.png', '.pdf', '.jpg', '.jpeg', '.PNG', '.PDF', '.JPG']:
                    possible_paths.append(base_name + ext if ext else image_file)

                # 2. 只保留文件名（去掉所有路径）
                filename_only = image_file.split('/')[-1]
                base_filename = re.sub(r'\.\w+$', '', filename_only)
                for ext in ['', '.png', '.pdf', '.jpg', '.jpeg', '.PNG', '.PDF', '.JPG']:
                    possible_paths.append(base_filename + ext if ext else filename_only)

                # 3. 模糊匹配：在tar中查找包含文件名的图片
                for tar_file in image_files_in_tar:
                    if base_filename.lower() in tar_file.lower():
                        possible_paths.append(tar_file)

                image_data = None
                found_file = None

                for try_filename in possible_paths:
                    try:
                        extracted_file = tar.extractfile(try_filename)
                        if extracted_file:
                            image_data = extracted_file.read()
                            found_file = try_filename
                            logger.debug(f"Successfully extracted {try_filename} for {self.arxiv_id}")
                            break
                    except KeyError:
                        continue

                if image_data is None:
                    logger.warning(f"Image file {image_file} not found in tar for {self.arxiv_id}. Tried {len(possible_paths)} variations.")
                    return None

                # 如果是PDF，转换为PNG
                if found_file and found_file.lower().endswith('.pdf'):
                    try:
                        # 保存PDF到临时文件
                        pdf_path = f"{tmpdirname}/temp.pdf"
                        with open(pdf_path, 'wb') as f:
                            f.write(image_data)

                        # 使用pdftoppm转换（如果可用）
                        png_path = f"{tmpdirname}/temp.png"
                        subprocess.run(['pdftoppm', '-png', '-singlefile', pdf_path, f"{tmpdirname}/temp"],
                                      check=True, capture_output=True)

                        with open(png_path, 'rb') as f:
                            image_data = f.read()
                    except (subprocess.CalledProcessError, FileNotFoundError) as e:
                        logger.warning(f"Failed to convert PDF to PNG for {self.arxiv_id}: {e}. Skipping this figure.")
                        return None

                # 转换为base64
                image_base64 = base64.b64encode(image_data).decode('utf-8')

                # 使用vision LLM生成描述
                vision_llm = get_vision_llm()
                prompt = f"""Please analyze this figure from a research paper and provide a brief description (2-3 sentences) in {vision_llm.lang}.

Focus on:
1. The main components or modules shown
2. The data/information flow
3. The key technical approach

Keep it concise and technical."""

                # 检查是否禁用 Vision LLM（用于调试）
                import os
                skip_vision = os.getenv('SKIP_VISION_LLM', 'false').lower() == 'true'

                if skip_vision:
                    logger.warning(f"SKIP_VISION_LLM is enabled, skipping vision description for {self.arxiv_id}")
                    description = target_caption  # 直接使用 caption
                else:
                    try:
                        logger.debug(f"Calling Vision LLM for {self.arxiv_id}")
                        description = vision_llm.generate_with_vision(prompt, image_base64)
                        logger.debug(f"Vision LLM succeeded for {self.arxiv_id}")
                    except Exception as e:
                        logger.error(f"Failed to generate vision description for {self.arxiv_id}: {e}")
                        description = target_caption  # 回退到使用原始caption

                # 清理caption（移除LaTeX命令）
                # 清理 caption：移除 LaTeX 命令和引用
                clean_caption = target_caption
                # 移除引用命令（\cite{...}, \citep{...}, \citet{...} 等）
                clean_caption = re.sub(r'\\cite[a-z]*\{[^}]*\}', '', clean_caption)
                # 移除 ~ 符号（LaTeX 中的不间断空格）
                clean_caption = re.sub(r'~', ' ', clean_caption)
                # 移除其他 LaTeX 命令，保留内容
                clean_caption = re.sub(r'\\[a-zA-Z]+\{([^}]*)\}', r'\1', clean_caption)
                # 移除剩余的 LaTeX 命令
                clean_caption = re.sub(r'\\[a-zA-Z]+', '', clean_caption)
                # 清理多余空格
                clean_caption = re.sub(r'\s+', ' ', clean_caption).strip()

                return {
                    "image_base64": image_base64,
                    "caption": clean_caption,
                    "description": description
                }

            except Exception as e:
                logger.error(f"Unexpected error extracting overview figure for {self.arxiv_id}: {e}")
                return None
