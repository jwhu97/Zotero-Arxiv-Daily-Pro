from paper import ArxivPaper
import math
from tqdm import tqdm
from email.header import Header
from email.mime.text import MIMEText
from email.utils import parseaddr, formataddr
import smtplib
import datetime
import time
from loguru import logger

framework = """
<!DOCTYPE HTML>
<html>
<head>
  <style>
    .star-wrapper {
      font-size: 1.3em; /* 调整星星大小 */
      line-height: 1; /* 确保垂直对齐 */
      display: inline-flex;
      align-items: center; /* 保持对齐 */
    }
    .half-star {
      display: inline-block;
      width: 0.5em; /* 半颗星的宽度 */
      overflow: hidden;
      white-space: nowrap;
      vertical-align: middle;
    }
    .full-star {
      vertical-align: middle;
    }
    /* 图片响应式布局 */
    .overview-image {
      border: 1px solid #ddd;
      border-radius: 4px;
      cursor: pointer;
      transition: opacity 0.2s;
    }
    .overview-image:hover {
      opacity: 0.9;
    }

    /* 手机端：图片占满宽度 */
    @media only screen and (max-width: 600px) {
      .overview-image {
        width: 100% !important;
        height: auto !important;
        max-width: 100% !important;
        display: block !important;
        margin: 0 !important;
      }
      .image-container {
        text-align: left !important;
      }
    }

    /* 电脑端：图片左对齐，限制高度 */
    @media only screen and (min-width: 601px) {
      .overview-image {
        max-height: 250px !important;
        width: auto !important;
        max-width: 100% !important;
        display: block !important;
        margin: 0 !important;
      }
      .image-container {
        text-align: left !important;
      }
    }
  </style>
</head>
<body>

<div>
    __CONTENT__
</div>

<br><br>
<div>
To unsubscribe, remove your email in your Github Action setting.
</div>

</body>
</html>
"""

def get_empty_html():
  block_template = """
  <table border="0" cellpadding="0" cellspacing="0" width="100%" style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 16px; background-color: #f9f9f9;">
  <tr>
    <td style="font-size: 20px; font-weight: bold; color: #333;">
        No Papers Today. Take a Rest!
    </td>
  </tr>
  </table>
  """
  return block_template

def get_block_html(title:str, authors:str, rate:str,arxiv_id:str, abstract:str, pdf_url:str, code_url:str=None, affiliations:str=None, tags:list[str]=None, overview_figure:dict=None):
    # 缩小按钮尺寸：减小字号、padding
    code = f'<a href="{code_url}" style="display: inline-block; text-decoration: none; font-size: 12px; font-weight: bold; color: #fff; background-color: #5bc0de; padding: 5px 10px; border-radius: 3px; margin-left: 6px;">Code</a>' if code_url else ''

    # 处理 affiliations：如果是 Unknown Affiliation，不显示
    affiliation_html = ''
    if affiliations and affiliations.strip() and affiliations.strip().lower() != 'unknown affiliation':
        affiliation_html = f'<br><i>{affiliations}</i>'

    # 生成tags的HTML（badge样式 - 更精致）
    tags_html = ''
    if tags:
        tag_badges = [f'<span style="display: inline-block; background-color: #f0f0f0; color: #333; padding: 2px 8px; border-radius: 10px; font-size: 11px; margin-right: 5px; margin-top: 3px;">{tag}</span>' for tag in tags]
        tags_html = ''.join(tag_badges)

    # 构建 arXiv 论文页面 URL（用于图片点击跳转）
    arxiv_abs_url = f'https://arxiv.org/abs/{arxiv_id}'

    # 生成overview figure的HTML（缩略图 + 点击跳转到论文页面）
    overview_html = ''
    if overview_figure:
        image_base64 = overview_figure.get('image_base64', '')
        caption = overview_figure.get('caption', '')
        description = overview_figure.get('description', '')

        # 清理 caption：去除大括号和可能的英文前缀
        caption_clean = caption.strip()
        if caption_clean.startswith('{') and caption_clean.endswith('}'):
            caption_clean = caption_clean[1:-1].strip()
        # 如果有 "Figure X." 或类似前缀，保留它；只去除 "{ " 这样的异常字符

        overview_html = f'''
    <tr>
        <td style="padding: 12px 0;">
            <div style="background-color: #fff; padding: 12px; border: 1px solid #e0e0e0; border-radius: 6px;">
                <strong style="font-size: 14px; color: #333;">Architecture Overview:</strong>
                <div style="margin-top: 8px; text-align: left; max-width: 100%; overflow: hidden;">
                    <a href="{arxiv_abs_url}" target="_blank" title="点击查看论文完整版" style="display: inline-block; position: relative; max-width: 100%;">
                        <img src="data:image/png;base64,{image_base64}" alt="Architecture" style="width: 100%; max-width: 100%; height: auto; max-height: 250px; object-fit: contain; display: block; border: 1px solid #ddd; border-radius: 4px; cursor: pointer;">
                        <div style="position: absolute; bottom: 8px; right: 8px; background-color: rgba(0,0,0,0.6); color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px; pointer-events: none;">点击查看论文</div>
                    </a>
                </div>
                <div style="margin-top: 8px; font-size: 12px; color: #555; word-wrap: break-word;">
                    <strong>Caption:</strong> {caption_clean}
                </div>
                <div style="margin-top: 6px; font-size: 12px; color: #555; font-style: italic; word-wrap: break-word;">
                    {description}
                </div>
            </div>
        </td>
    </tr>'''

    block_template = """
    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="font-family: Arial, sans-serif; border: 1px solid #ddd; border-radius: 8px; padding: 16px; background-color: #f9f9f9; max-width: 100%; table-layout: fixed; box-sizing: border-box;">
    <tr>
        <td style="font-size: 20px; font-weight: bold; color: #333; word-wrap: break-word;">
            {title}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #666; padding: 8px 0;">
            {authors}{affiliation_html}
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>Relevance:</strong> {rate}
            <span style="margin-left: 12px;">
                <a href="{pdf_url}" style="display: inline-block; text-decoration: none; font-size: 12px; font-weight: bold; color: #fff; background-color: #d9534f; padding: 5px 10px; border-radius: 3px;">PDF</a>
                {code}
            </span>
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>arXiv ID:</strong> <a href="https://arxiv.org/abs/{arxiv_id}" target="_blank">{arxiv_id}</a>
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 4px 0;">
            <strong>Tags:</strong><br>
            <div style="margin-top: 4px;">{tags}</div>
        </td>
    </tr>
    <tr>
        <td style="font-size: 14px; color: #333; padding: 8px 0;">
            <strong>TLDR:</strong> {abstract}
        </td>
    </tr>
{overview}
</table>
"""
    return block_template.format(title=title, authors=authors, rate=rate, arxiv_id=arxiv_id, abstract=abstract, pdf_url=pdf_url, code=code, affiliation_html=affiliation_html, tags=tags_html, overview=overview_html)

def get_stars(score:float):
    full_star = '<span class="full-star">⭐</span>'
    half_star = '<span class="half-star">⭐</span>'
    low = 6
    high = 8
    if score <= low:
        return ''
    elif score >= high:
        return full_star * 5
    else:
        interval = (high-low) / 10
        star_num = math.ceil((score-low) / interval)
        full_star_num = int(star_num/2)
        half_star_num = star_num - full_star_num * 2
        return '<div class="star-wrapper">'+full_star * full_star_num + half_star * half_star_num + '</div>'


def render_email(papers:list[ArxivPaper]):
    parts = []
    if len(papers) == 0 :
        return framework.replace('__CONTENT__', get_empty_html())
    
    for p in tqdm(papers,desc='Rendering Email'):
        rate = get_stars(p.score)
        author_list = [a.name for a in p.authors]
        num_authors = len(author_list)
        
        if num_authors <= 5:
            authors = ', '.join(author_list)
        else:
            authors = ', '.join(author_list[:3] + ['...'] + author_list[-2:])
        # 临时注释掉 affiliations 以加速测试
        # if p.affiliations is not None:
        #     affiliations = p.affiliations[:5]
        #     affiliations = ', '.join(affiliations)
        #     if len(p.affiliations) > 5:
        #         affiliations += ', ...'
        # else:
        #     affiliations = 'Unknown Affiliation'
        affiliations = 'Unknown Affiliation'  # 临时跳过 LLM 提取
        code_url = p.code_url  # 从 abstract 中提取代码链接（GitHub/Hugging Face）
        tags = p.tags  # 从论文中提取关键技术词汇作为标签
        overview_figure = p.overview_figure  # 提取论文的架构图及描述
        parts.append(get_block_html(p.title, authors,rate,p.arxiv_id ,p.tldr, p.pdf_url, code_url, affiliations, tags, overview_figure))
        time.sleep(2)  # 临时改为 2 秒，加速测试（原来是 10 秒）

    content = '<br>' + '</br><br>'.join(parts) + '</br>'
    return framework.replace('__CONTENT__', content)

def send_email(sender:str, receiver:str, password:str,smtp_server:str,smtp_port:int, html:str,):
    def _format_addr(s):
        name, addr = parseaddr(s)
        return formataddr((Header(name, 'utf-8').encode(), addr))

    msg = MIMEText(html, 'html', 'utf-8')
    msg['From'] = _format_addr('Github Action <%s>' % sender)
    msg['To'] = _format_addr('You <%s>' % receiver)
    today = datetime.datetime.now().strftime('%Y/%m/%d')
    msg['Subject'] = Header(f'Daily arXiv {today}', 'utf-8').encode()

    # 根据端口自动选择 SSL 或 TLS
    if smtp_port == 465:
        logger.debug("Using SMTP_SSL for port 465")
        server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)
    else:
        logger.debug("Using SMTP with STARTTLS for other ports")
        try:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
            server.starttls()
        except Exception as e:
            logger.warning(f"Failed to use TLS: {e}")
            logger.warning("Trying SSL fallback...")
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)

    server.login(sender, password)
    server.sendmail(sender, [receiver], msg.as_string())
    server.quit()
