"""集中配置：所有可配置项在此定义，避免硬编码。"""

import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict


# ========== 考试信息 ==========
@dataclass
class ExamConfig:
    """考试相关配置"""
    # 江西省考笔试日期
    date: datetime = datetime(2027, 3, 25)
    # 考试名称（PDF封面用）
    name: str = "2027年江西省考"
    # PDF标题
    pdf_title: str = "2027年江西省考每日备考资料"


# ========== 字体配置 ==========
FONT_CANDIDATES = [
    # Linux (GitHub Actions / Ubuntu)
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    # Windows
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]


# ========== HTTP 配置 ==========
@dataclass
class HttpConfig:
    """HTTP 请求相关配置"""
    # 默认 User-Agent
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    headers: Dict[str, str] = field(default_factory=lambda: {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    })
    # 请求超时秒数
    timeout: int = 20
    # 重试次数
    max_retries: int = 3
    # 重试初始等待秒数（指数退避）
    retry_wait: float = 1.5
    # 请求间隔秒数（防止对目标站点过快）
    request_interval: float = 0.5


# ========== 抓取源配置 ==========
# 每个源用 HTTPS；年份相关的用占位符 {year} 动态替换
SCRAPE_SOURCES = {
    # —— 人民日报评论 ——
    # 注：people.com.cn 的 HTTPS 证书有 hostname mismatch 问题，必须走 HTTP
    # 注：人民网已全面升级为 UTF-8（不再是历史上的 GBK），article_encoding 留空交给自动检测
    "people_shiping": {
        "name": "人民时评",
        "source": "人民网",
        "list_url": "http://opinion.people.com.cn/GB/8213/49160/49219/index.html",
        "href_contains": ["/n1/", "c461529"],
        "article_encoding": "utf-8",
        "max_items": 3,
    },
    "people_ruiping": {
        "name": "人民锐评",
        "source": "人民网",
        "list_url": "http://opinion.people.com.cn/GB/436867/index.html",
        "href_contains": ["/n1/", "c436867"],
        "article_encoding": "utf-8",
        "max_items": 2,
    },
    # —— 时政新闻 ——
    "xinhuanet_politics": {
        "name": "新华网时政",
        "source": "新华网",
        "list_url": "https://www.xinhuanet.com/politics/",
        "href_contains": ["news.cn", ".htm"],
        "path_contains": ["/politics/"],
        "article_encoding": "utf-8",
        "max_items": 6,
        "min_title_len": 15,
    },
    # 注：people.com.cn 的 HTTPS 证书有 hostname mismatch 问题，必须走 HTTP
    # 注：人民网已全面升级为 UTF-8
    "people_politics": {
        "name": "人民网时政",
        "source": "人民网",
        "list_url": "http://politics.people.com.cn/GB/1024/index.html",
        "href_contains": ["/n1/"],
        "article_encoding": "utf-8",
        "max_items": 5,
        "min_title_len": 12,
    },
    # 注：gov.cn/yaowen/ 是 SPA，requests 抓不到。改用 /zhengce/zuixin/
    "gov_policy": {
        "name": "中国政府网政策动态",
        "source": "中国政府网",
        "list_url": "https://www.gov.cn/zhengce/zuixin/",
        "href_contains": [".htm"],
        "article_encoding": "utf-8",
        "max_items": 5,
        "min_title_len": 10,
    },
    "news_cn_headlines": {
        "name": "新华网首页要闻",
        "source": "新华网",
        "list_url": "https://www.news.cn/",
        # 用 {year} 占位，运行时替换为当前年份（宽松匹配，兼容 /20260930/ 和 /2026/ 两种）
        # 注：news.cn 现代文章 URL 很多没有 .htm 后缀（如 /politics/leaders/20260930/xxx）
        "href_contains": ["news.cn", "{year}"],
        "article_encoding": "utf-8",
        "max_items": 5,
        "min_title_len": 18,
    },
}


# ========== 内容阈值 ==========
@dataclass
class ContentThresholds:
    """内容抓取的各种阈值"""
    # 评论最少标题长度
    comment_min_title_len: int = 5
    # 段落最少字符数
    para_min_len: int = 10
    # 金句提取条件：短句 + 含引号
    golden_max_len: int = 100
    # 每篇评论最多金句数
    golden_per_article: int = 3
    # PDF 中金句汇总最多条数
    golden_summary_max: int = 15
    # 每篇评论 PDF 最多展示段落数
    max_paragraphs_per_comment: int = 20
    # 新闻汇总最多条数
    news_max_total: int = 15
    # 每条新闻摘要长度
    summary_max_chars: int = 120


# ========== 输出配置 ==========
@dataclass
class OutputConfig:
    output_dir: str = "./output"
    pdf_filename_prefix: str = "meiriziliao"


# ========== 企业微信 ==========
def get_wecom_webhook() -> str:
    """从环境变量读取企业微信 Webhook URL"""
    return os.environ.get("WECOM_WEBHOOK", "")
