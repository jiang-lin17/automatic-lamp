""""爬虫模块：人民日报评论 + 时政新闻。"""

from typing import List, Dict, Any, Optional, Set, Tuple
from urllib.parse import urljoin
import re

from bs4 import BeautifulSoup

from . import config as cfg
from .utils import http_get, log, current_year, get_target_date
from .config import ContentThresholds, SCRAPE_SOURCES, DedupConfig
from .dedup import (
    get_seen_store, normalize_url,
    extract_date_from_url, extract_date_from_text, within_window,
)


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


# ========== 列表页候选链接 ==========

def _collect_links(src: Dict[str, Any]) -> List[Dict[str, str]]:
    """抓列表页并收集候选链接。

    过滤顺序：标题长度 → href_contains → path_contains（基于绝对 URL）→ 按 URL 去重。
    返回顺序保持页面原序（通常是「由新到旧」）。
    """
    resp = http_get(src["list_url"], encoding=src.get("article_encoding", "utf-8"))
    soup = BeautifulSoup(resp.text, "html.parser")
    min_title = src.get("min_title_len", cfg.ContentThresholds().comment_min_title_len)

    out: List[Dict[str, str]] = []
    seen: Set[str] = set()
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
        if "path_contains" in src and not _text_present(full_url, src["path_contains"]):
            continue
        key = normalize_url(full_url)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append({"title": title, "url": full_url})
    return out


def _select_pool(pool: List[Dict[str, Any]], need: int, target,
                 window: int, fallback_window: int) -> List[Dict[str, Any]]:
    """从已抓取条目池里挑 need 条：先在窗口内挑，再放宽到 fallback 窗口。"""
    strict = [p for p in pool if within_window(p.get("date"), target, window)]
    if len(strict) >= need:
        return strict[:need]
    relaxed = [p for p in pool if within_window(p.get("date"), target, fallback_window)]
    return relaxed[:need]



def fetch_article_detail(url: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """抓一篇文章的详细内容：正文、摘要、作者、金句、发布日期。"""
    result: Dict[str, Any] = {
        "summary": "", "content": [], "author": "", "golden": [], "date": "",
    }
    thresholds = ContentThresholds()
    try:
        resp = http_get(url, encoding=encoding)
        soup = BeautifulSoup(resp.text, "html.parser")

        result["author"] = _extract_author(soup)
        # 发布日期：URL 里的日期最可靠（人民网 /n1/2026/1001/），否则从页面正文找
        result["date"] = (
            extract_date_from_url(url)
            or extract_date_from_text(resp.text[:20000])
            or ""
        )

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
    """抓取人民日报评论（人民时评 + 人民锐评），只取「目标日期附近且没推送过」的文章。

    挑选优先级：
      1. 未推送过 + 落在源配置的日期窗口内
      2. 未推送过 + 放宽到 DedupConfig.fallback_window_days
      3. 确实没有新的了，才回退到已推送过的，保证 PDF 评论区不空白
    """
    store = get_seen_store()
    fallback_days = DedupConfig().fallback_window_days
    target = get_target_date()
    comments: List[Dict[str, Any]] = []
    failed_sources: List[str] = []

    for key in ("people_shiping", "people_ruiping"):
        src = SCRAPE_SOURCES[key]
        need = src["max_items"]
        window = src.get("date_window_days", 14)
        max_fetches = src.get("max_fetches", 12)
        enc = src.get("article_encoding", "utf-8")
        log.info("抓取评论源 [%s] %s（日期窗口 %d 天，最多抓 %d 篇正文）",
                 src["source"], src["name"], window, max_fetches)
        try:
            cands = _collect_links(src)
        except Exception as e:
            log.error("  [%s] 列表页抓取失败: %s", src["name"], e)
            failed_sources.append(src["name"])
            continue

        if not cands:
            log.warning("  [%s] 列表页未找到任何匹配链接！目标 href_contains=%s",
                         src["name"], src.get("href_contains"))
            failed_sources.append(src["name"])
            continue

        unseen = [c for c in cands if not store.is_seen(c["url"])]
        seen_before = [c for c in cands if store.is_seen(c["url"])]
        log.info("  [%s] 候选 %d 条（未推送 %d / 已推送 %d）",
                 src["name"], len(cands), len(unseen), len(seen_before))

        # 第一遍：抓「未推送过」的候选（页面顺序即由新到旧）
        pool: List[Dict[str, Any]] = []
        for cand in unseen:
            if len(_select_pool(pool, need, target, window, fallback_days)) >= need:
                break
            if len(pool) >= max_fetches:
                break
            detail = fetch_article_detail(cand["url"], enc)
            pool.append({
                "title": cand["title"],
                "column": src["name"],
                "url": cand["url"],
                **detail,
            })

        picked = _select_pool(pool, need, target, window, fallback_days)

        # 第二遍：新的已用完 → 用最近几条已推送过的兜底，避免评论区空白
        if len(picked) < need:
            for cand in seen_before[: max_fetches]:
                if len(picked) >= need:
                    break
                detail = fetch_article_detail(cand["url"], enc)
                picked.append({
                    "title": cand["title"],
                    "column": src["name"],
                    "url": cand["url"],
                    **detail,
                })

        for p in picked:
            log.info("  [%s] 选中《%s》日期=%s",
                     src["name"], p["title"][:24], p.get("date") or "?")
        if not picked:
            failed_sources.append(src["name"])
        comments.extend(picked)

    if failed_sources:
        log.warning("⚠️ 以下评论源抓取失败或返回 0 条: %s", ", ".join(failed_sources))

    if len(comments) < 2:
        log.warning("⚠️ 评论总数不足 2 条（实际 %d 条），PDF 评论内容将严重缺失！", len(comments))

    return comments


# ========== 新闻抓取 ==========

def _probe_news_article(cand: Dict[str, str], src: Dict[str, Any],
                        category: str) -> Dict[str, Any]:
    """抓一条新闻的摘要 + 发布日期（URL 里有日期就用 URL 的）。"""
    thresholds = ContentThresholds()
    url = cand["url"]
    date = extract_date_from_url(url)
    summary = ""
    try:
        resp = http_get(url, encoding=src.get("article_encoding", "utf-8"))
        soup = BeautifulSoup(resp.text, "html.parser")
        if not date:
            date = extract_date_from_text(resp.text[:20000])
        for p in _extract_paragraphs(soup):
            if len(p) > 50:
                summary = (
                    p[:thresholds.summary_max_chars] + "..."
                    if len(p) > thresholds.summary_max_chars
                    else p
                )
                break
    except Exception as e:
        log.debug("新闻正文抓取失败 %s: %s", url, e)
    return {
        "title": cand["title"],
        "url": url,
        "source": src["source"],
        "category": category,
        "summary": summary,
        "date": date or "",
    }


def fetch_news() -> List[Dict[str, Any]]:
    """抓取时政新闻：只取「目标日期附近且没推送过」的条目，跨源去重后返回。"""
    store = get_seen_store()
    fallback_days = DedupConfig().fallback_window_days
    target = get_target_date()
    raw_news: List[Dict[str, Any]] = []

    category_map = {
        "xinhuanet_politics": "时政要闻",
        "people_politics": "时政要闻",
        "gov_policy": "政策动态",
        "news_cn_headlines": "国内要闻",
    }

    for key in ("xinhuanet_politics", "people_politics", "gov_policy", "news_cn_headlines"):
        src = SCRAPE_SOURCES[key]
        need = src["max_items"]
        window = src.get("date_window_days", 14)
        max_fetches = src.get("max_fetches", 16)
        category = category_map.get(key, "时政要闻")
        log.info("抓取新闻源 [%s] %s（日期窗口 %d 天）", src["source"], src["name"], window)
        try:
            cands = _collect_links(src)
        except Exception as e:
            log.error("  [%s] 列表页抓取失败: %s", src["name"], e)
            continue
        if not cands:
            log.warning("  [%s] 列表页未找到任何匹配链接！href_contains=%s",
                         src["name"], src.get("href_contains"))
            continue

        unseen = [c for c in cands if not store.is_seen(c["url"])]
        log.info("  [%s] 候选 %d 条（未推送 %d）", src["name"], len(cands), len(unseen))

        pool: List[Dict[str, Any]] = []
        for cand in unseen:
            if len(_select_pool(pool, need, target, window, fallback_days)) >= need:
                break
            if len(pool) >= max_fetches:
                break
            pool.append(_probe_news_article(cand, src, category))

        picked = _select_pool(pool, need, target, window, fallback_days)
        for p in picked:
            log.info("  [%s] %s | %s", src["name"], p.get("date") or "?", p["title"][:30])
        raw_news.extend(picked)

    seen_urls: Set[str] = set()
    seen_titles: Set[str] = set()
    unique: List[Dict[str, Any]] = []
    for n in raw_news:
        norm_url = normalize_url(n["url"])
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
