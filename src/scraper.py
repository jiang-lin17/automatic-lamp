"""爬虫模块：人民日报评论 + 时政新闻。"""

from typing import List, Dict, Any, Set
from urllib.parse import urljoin
import re

from bs4 import BeautifulSoup

from . import config as cfg
from .utils import http_get, log, current_year
from .config import ContentThresholds, SCRAPE_SOURCES


# ========== 公共解析 ==========

def _abs_url(base: str, href: str) -> str:
    """把相对 URL 转成绝对 URL。"""
    if href.startswith("http"):
        return href
    # 规范化：人民网部分 href 以 / 开头，需用原域名拼接
    return urljoin(base, href)


def _text_present(text: str, keywords: List[str]) -> bool:
    """检查字符串是否**同时**包含所有关键词（支持 {year} 占位符）。"""
    year = str(current_year())
    for kw in keywords:
        k = kw.replace("{year}", year)
        if k not in text:
            return False
    return True


def _extract_paragraphs(soup: BeautifulSoup) -> List[str]:
    """通用正文提取：依次尝试常见正文容器。"""
    candidates = [
        soup.find("div", class_="rm_txt_con"),
        soup.find("div", id="rwb_zw"),
        soup.find("div", id="detailContent"),
        soup.find("div", class_="article-content"),
        soup.find("div", class_="content"),
    ]
    for box in candidates:
        if box:
            return [p.get_text(strip=True) for p in box.find_all("p")]
    return []


def _extract_author(soup: BeautifulSoup) -> str:
    """提取作者。"""
    for cls in ("author", "rm_txt_con_author", "source"):
        div = soup.find("div", class_=cls)
        if div:
            text = div.get_text(strip=True)
            if text:
                return text[:50]
    return ""


# ========== 评论抓取 ==========

def fetch_article_detail(url: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """抓一篇文章的详细内容：正文、摘要、作者、金句。"""
    result = {"summary": "", "content": [], "author": "", "golden": []}
    thresholds = ContentThresholds()
    try:
        resp = http_get(url, encoding=encoding)
        soup = BeautifulSoup(resp.text, "html.parser")

        result["author"] = _extract_author(soup)

        paras = [
            p for p in _extract_paragraphs(soup)
            if p and len(p) > thresholds.para_min_len
        ]
        result["content"] = paras

        # 摘要：第一段前若干字
        if paras:
            first = paras[0]
            result["summary"] = (
                first[:thresholds.summary_max_chars] + "..."
                if len(first) > thresholds.summary_max_chars
                else first
            )

        # 金句：短 + 含引号
        golden: List[str] = []
        for p in paras:
            if len(p) < thresholds.golden_max_len and ('"' in p or "\u201c" in p):
                golden.append(p.strip())
            if len(golden) >= thresholds.golden_per_article:
                break
        result["golden"] = golden

        if not result["summary"]:
            result["summary"] = "点击查看原文"

    except Exception as e:
        log.warning("文章抓取失败 %s: %s", url, e)
        result["summary"] = "点击查看原文"

    return result


def fetch_comments() -> List[Dict[str, Any]]:
    """抓取人民日报评论（人民时评 + 人民锐评）。"""
    comments: List[Dict[str, Any]] = []

    for key in ("people_shiping", "people_ruiping"):
        src = SCRAPE_SOURCES[key]
        log.info("抓取评论源 [%s] %s", src["source"], src["name"])
        try:
            resp = http_get(src["list_url"], encoding=src.get("article_encoding", "utf-8"))
            soup = BeautifulSoup(resp.text, "html.parser")
            count = 0
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                title = link.get_text(strip=True)
                if not title or len(title) < cfg.ContentThresholds.comment_min_title_len:
                    continue
                if not _text_present(href, src.get("href_contains", [])):
                    continue

                full_url = _abs_url(src["list_url"], href)
                detail = fetch_article_detail(full_url, src.get("article_encoding", "utf-8"))
                comments.append({
                    "title": title,
                    "column": src["name"],
                    "url": full_url,
                    **detail,
                })
                count += 1
                if count >= src["max_items"]:
                    break
            log.info("  [%s] 共 %d 篇", src["name"], count)
        except Exception as e:
            log.error("  [%s] 抓取失败: %s", src["name"], e)

    return comments


# ========== 新闻抓取 ==========

def fetch_news_summary(url: str, encoding: str = "utf-8") -> str:
    """抓新闻摘要（首段）。"""
    thresholds = ContentThresholds()
    try:
        resp = http_get(url, encoding=encoding)
        soup = BeautifulSoup(resp.text, "html.parser")
        paras = _extract_paragraphs(soup)
        for p in paras:
            if len(p) > 50:
                return (
                    p[:thresholds.summary_max_chars] + "..."
                    if len(p) > thresholds.summary_max_chars
                    else p
                )
    except Exception as e:
        log.debug("摘要抓取失败 %s: %s", url, e)
    return ""


def fetch_news() -> List[Dict[str, Any]]:
    """抓取时政新闻。"""
    raw_news: List[Dict[str, Any]] = []

    # source_key -> 展示分类
    category_map = {
        "xinhuanet_politics": "时政要闻",
        "people_politics": "时政要闻",
        "gov_policy": "政策动态",
        "news_cn_headlines": "国内要闻",
    }

    for key in ("xinhuanet_politics", "people_politics", "gov_policy", "news_cn_headlines"):
        src = SCRAPE_SOURCES[key]
        log.info("抓取新闻源 [%s] %s", src["source"], src["name"])
        try:
            resp = http_get(src["list_url"], encoding=src.get("article_encoding", "utf-8"))
            soup = BeautifulSoup(resp.text, "html.parser")
            count = 0
            min_title = src.get("min_title_len", 10)
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                title = link.get_text(strip=True)
                if not title or len(title) < min_title:
                    continue
                if not _text_present(href, src.get("href_contains", [])):
                    continue
                # 额外路径限制
                if "path_contains" in src:
                    if not _text_present(href, src["path_contains"]):
                        continue

                full_url = _abs_url(src["list_url"], href)
                summary = fetch_news_summary(full_url, src.get("article_encoding", "utf-8"))
                raw_news.append({
                    "title": title,
                    "url": full_url,
                    "source": src["source"],
                    "category": category_map.get(key, "时政要闻"),
                    "summary": summary,
                })
                count += 1
                if count >= src["max_items"]:
                    break
            log.info("  [%s] 共 %d 条", src["name"], count)
        except Exception as e:
            log.error("  [%s] 抓取失败: %s", src["name"], e)

    # 去重：优先 URL，其次标题
    seen_urls: Set[str] = set()
    seen_titles: Set[str] = set()
    unique: List[Dict[str, Any]] = []
    for n in raw_news:
        norm_url = re.sub(r"^https?://", "", n["url"].rstrip("/"))
        title_key = n["title"][:20]
        if norm_url in seen_urls or title_key in seen_titles:
            continue
        seen_urls.add(norm_url)
        seen_titles.add(title_key)
        unique.append(n)

    # 限制总数
    thresholds = ContentThresholds()
    return unique[:thresholds.news_max_total]
