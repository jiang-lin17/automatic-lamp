""""爬虫模块：人民日报评论 + 时政新闻。"""

from typing import List, Dict, Any, Set
from urllib.parse import urljoin
import re

from bs4 import BeautifulSoup

from . import config as cfg
from .utils import http_get, log, current_year
from .config import ContentThresholds, SCRAPE_SOURCES


# ========== 公共解析 ==========

def _abs_url(base: str, href: str) -> str:
    if href.startswith("http"):
        return href
    return urljoin(base, href)


def _text_present(text: str, keywords: List[str]) -> bool:
    year = str(current_year())
    for kw in keywords:
        k = kw.replace("{year}", year)
        if k not in text:
            return False
    return True


def _extract_paragraphs(soup: BeautifulSoup) -> List[str]:
    """通用正文提取：依次尝试常见正文容器，返回所有有效段落。

    覆盖人民网、新华网、中国政府网等主流站点的正文容器选择器。
    """
    candidates = [
        soup.find("div", class_="rm_txt_con"),         # 人民时评/锐评
        soup.find("div", id="rwb_zw"),                  # 人民网通用
        soup.find("div", id="detailContent"),           # 新华网
        soup.find("div", class_="article-content"),     # 通用
        soup.find("div", class_="content"),             # 通用
        soup.find("div", class_="TRS_Editor"),          # TRS CMS 系统（gov.cn 常用）
        soup.find("div", class_="Custom_UnionStyle"),   # 新华网另一种
        soup.find("div", id="UCAP-CONTENT"),            # 部分新闻站
        soup.find("article"),                           # HTML5 语义标签兜底
    ]
    for box in candidates:
        if box:
            paras = [p.get_text(strip=True) for p in box.find_all("p")]
            paras = [p for p in paras if len(p) > 10]
            if len(paras) >= 2:  # 至少 2 段才认为是有效正文
                return paras
    return []


def _extract_author(soup: BeautifulSoup) -> str:
    for cls in ("author", "rm_txt_con_author", "source", "editor", "p_jb"):
        div = soup.find("div", class_=cls)
        if div:
            text = div.get_text(strip=True)
            if text:
                return text[:50]
    # 兜底：meta 里的 source
    meta = soup.find("meta", attrs={"name": "author"})
    if meta and meta.get("content"):
        return meta["content"][:50]
    return ""


# ========== 评论抓取 ==========

def fetch_article_detail(url: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """抓一篇文章的详细内容：正文、摘要、作者、金句。"""
    result: Dict[str, Any] = {"summary": "", "content": [], "author": "", "golden": []}
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

        if paras:
            first = paras[0]
            result["summary"] = (
                first[:thresholds.summary_max_chars] + "..."
                if len(first) > thresholds.summary_max_chars
                else first
            )

        golden: List[str] = []
        for p in paras:
            if len(p) < thresholds.golden_max_len and ('"' in p or "\u201c" in p or "\u201d" in p):
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
    """抓取人民日报评论（人民时评 + 人民锐评）。

    所有源合并返回；如果最终评论总数 < 2，记录 WARNING 方便排查。
    """
    comments: List[Dict[str, Any]] = []
    failed_sources: List[str] = []

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
            if count == 0:
                log.warning("  [%s] 列表页未找到任何匹配链接！目标 href_contains=%s",
                             src["name"], src.get("href_contains"))
                failed_sources.append(src["name"])
        except Exception as e:
            log.error("  [%s] 抓取失败: %s", src["name"], e)
            failed_sources.append(src["name"])

    if failed_sources:
        log.warning("⚠️ 以下评论源抓取失败或返回 0 条: %s", ", ".join(failed_sources))

    if len(comments) < 2:
        log.warning("⚠️ 评论总数不足 2 条（实际 %d 条），PDF 评论内容将严重缺失！", len(comments))

    return comments


# ========== 新闻抓取 ==========

def fetch_news_summary(url: str, encoding: str = "utf-8") -> str:
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
    """抓取时政新闻。所有源合并去重，最终最多返回 news_max_total 条。"""
    raw_news: List[Dict[str, Any]] = []

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

                full_url = _abs_url(src["list_url"], href)
                # path 过滤基于绝对 URL：列表页里的相对链接（如 ./202609/content_xxx.htm）
                # 要拼成绝对地址后才能与 /zhengce/ 这类路径规则匹配
                if "path_contains" in src:
                    if not _text_present(full_url, src["path_contains"]):
                        continue

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

    thresholds = ContentThresholds()
    if len(unique) < 8:
        log.warning("⚠️ 新闻总数不足 8 条（去重后 %d 条）", len(unique))

    return unique[:thresholds.news_max_total]
