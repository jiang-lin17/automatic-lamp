""""src.main: 业务流程编排入口。"""

import os
import sys
import time
from datetime import datetime
from typing import Tuple

from .config import (
    ExamConfig, OutputConfig, ContentThresholds,
    get_wecom_webhook, AIConfig, get_ai_key,
)
from .utils import (
    get_target_date, format_date, close_session, log,
)
from .scraper import fetch_comments, fetch_news
from .ai_enhancer import run_all_ai_enhance
from .pdf_builder import ReportBuilder
from .wecom import WeComPusher, build_markdown_message
from .dedup import get_seen_store, commit_seen


MIN_COMMENTS_REQUIRED = 2   # 评论低于此值视为严重缺失
MIN_NEWS_REQUIRED = 6       # 新闻低于此值视为不足
MAX_RETRY_ROUNDS = 2        # 最多重试 2 次


def run() -> Tuple[int, int]:
    log.info("=" * 50)
    log.info("automatic-lamp v6 — 江西省考每日备考资料  [AI LiteLLM]")
    log.info("=" * 50)

    target_date = get_target_date()
    date_str, date_cn, weekday, days_left = format_date(target_date)
    exam_name = ExamConfig().name
    log.info("目标日期: %s %s", date_str, weekday)
    log.info("距考试: %d 天", days_left)
    log.info("企业微信 Webhook: %s", "已配置" if get_wecom_webhook() else "未配置")

    ai_key = get_ai_key()
    ai_cfg = AIConfig()
    if ai_cfg.enabled is False:
        log.info("AI 已被强制禁用 (AI_ENABLED=False)")
    elif ai_key:
        log.info("🤖 AI API Key 已检测到，将启用 AI 增强 (model=%s)", ai_cfg.model)
    else:
        log.info("AI 未启用（设置 AI_API_KEY 或 DEEPSEEK_API_KEY 即可开启）")

    out_cfg = OutputConfig()
    os.makedirs(out_cfg.output_dir, exist_ok=True)
    pdf_path = os.path.join(
        out_cfg.output_dir,
        f"{out_cfg.pdf_filename_prefix}_{date_str}.pdf",
    )

    # ========== 抓取（含质量校验 + 自动重试） ==========
    comments, news_list = _fetch_with_retries()

    # ========== AI 增强 ==========
    log.info("[3/5] AI 增强处理...")
    ai_result = run_all_ai_enhance(comments, news_list, ai_cfg)
    comments_with_ai = ai_result["comments_with_ai"]
    news_with_points = ai_result["news_with_points"]

    # ========== PDF 生成 ==========
    log.info("[4/5] 生成 PDF...")
    try:
        builder = ReportBuilder()
        builder.build(
            comments_with_ai, news_with_points,
            ai_result,
            date_str, date_cn, weekday,
            days_left, pdf_path,
        )
        fsize_kb = round(os.path.getsize(pdf_path) / 1024, 1)
        log.info("  完成: %.1f KB", fsize_kb)
        # PDF 生成成功后才把文章记入去重状态，避免生成失败时白白消耗掉它们
        _mark_seen(comments_with_ai, news_with_points, date_str)
    except Exception as e:
        log.error("PDF 生成失败: %s", e)
        raise

    # ========== 企业微信推送 ==========
    log.info("[5/5] 推送到企业微信...")
    total_golden = sum(len(c.get("ai_golden", []) or c.get("golden", []))
                       for c in comments_with_ai)
    ds = ai_result.get("daily_summary", {})
    markdown = build_markdown_message(
        exam_name=exam_name,
        date_cn=date_cn,
        weekday=weekday,
        days_left=days_left,
        comments_len=len(comments_with_ai),
        news_len=len(news_list),
        golden_len=total_golden,
        ai_summary_headline=ds.get("headline", ""),
        ai_summary_text=ds.get("summary", ""),
        ai_enabled=ai_result.get("enabled", False),
    )
    webhook = get_wecom_webhook()
    if webhook:
        try:
            pusher = WeComPusher(webhook)
            text_ok, file_ok = pusher.send_report(markdown, pdf_path)
            log.info("  文本推送: %s | 文件推送: %s",
                     "OK" if text_ok else "FAIL",
                     "OK" if file_ok else "FAIL")
        except Exception as e:
            log.error("  推送异常: %s", e)
    else:
        log.warning("  未配置 webhook，跳过推送（PDF 已生成在本地）")

    return len(comments), len(news_list)


def _mark_seen(comments: list, news_list: list, date_str: str) -> None:
    """把本次推送过的文章写入跨天去重状态（下一次运行就会跳过它们）。"""
    store = get_seen_store()
    urls = [c.get("url", "") for c in comments] + [n.get("url", "") for n in news_list]
    added = store.mark(urls, date_str)
    commit_seen()
    log.info("去重状态：本次新增 %d 条（累计 %d 条）", added, len(store))


def _fetch_with_retries() -> Tuple[list, list]:
    """执行抓取 + 质量校验 + 自动重试。

    重试触发条件：评论 < 2 条。新闻少暂时不重试（源的问题难临时修），但会 WARNING。
    """
    comments: list = []
    news_list: list = []

    for attempt in range(1, MAX_RETRY_ROUNDS + 1):
        log.info("[1/5] 抓取人民日报评论（第 %d 轮）...", attempt)
        comments = fetch_comments()
        log.info("  共 %d 篇", len(comments))

        log.info("[2/5] 抓取时政新闻（第 %d 轮）...", attempt)
        news_list = fetch_news()
        log.info("  共 %d 条", len(news_list))

        # 质量校验
        comments_ok = len(comments) >= MIN_COMMENTS_REQUIRED
        news_ok = len(news_list) >= MIN_NEWS_REQUIRED

        if comments_ok and news_ok:
            break

        if not comments_ok:
            log.error("❌ 评论仅 %d 条（至少需要 %d 条），将进行第 %d 轮重试",
                      len(comments), MIN_COMMENTS_REQUIRED, attempt + 1)
        if not news_ok:
            log.warning("⚠️ 新闻仅 %d 条（期望 ≥ %d 条）", len(news_list), MIN_NEWS_REQUIRED)

        if attempt < MAX_RETRY_ROUNDS:
            log.info("等待 5 秒后重试...")
            time.sleep(5)
            close_session()  # 重置 Session，避免连接池残留

    # 最终结果校验
    if len(comments) < MIN_COMMENTS_REQUIRED:
        log.error("⚠️⚠️⚠️ 评论抓取最终仍不足 %d 条！PDF 评论内容将严重缺失！"
                  "请查看 run.log 排查具体抓取失败的源。", MIN_COMMENTS_REQUIRED)

    return comments, news_list
