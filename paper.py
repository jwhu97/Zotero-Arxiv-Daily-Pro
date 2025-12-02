from typing import Optional
from functools import cached_property
from tempfile import TemporaryDirectory
import arxiv
import tarfile
import re
import time
from llm import get_llm
import requests
from requests.adapters import HTTPAdapter, Retry
from loguru import logger
import tiktoken
from contextlib import ExitStack
from urllib.error import HTTPError



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
