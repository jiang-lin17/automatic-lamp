"""src.main: 业务流程编排入口。

只做"调步骤"，具体逻辑在各子模块中。顶层 main.py 只负责启动。
"""

import os
import sys
from datetime import datetime
from typing import Tuple

from .config import (
    ExamConfig, OutputConfig, ContentThresholds,
    get_wecom_webhook,
)
from .utils import (
    get_target_date, format_date, close_session, log,
)
from .scraper import fetch_comments, fetch_news
from .pdf_builder import ReportBuilder
from .wecom import WeComPusher, build_markdown_message


def run() -> Tuple[int, int]:
    """执行完整流程。

    返回 (comments_count, news_count)，供调用方参考。
    失败时抛异常由顶层捕获。
    """
    log.info("=" * 50)
    log.info("automatic-lamp v5 — 江西省考每日备考资料")
    log.info("=" * 50)

    # 1. 日期
    target_date = get_target_date()
    date_str, date_cn, weekday, days_left = format_date(target_date)
    exam_name = ExamConfig().name
    log.info("目标日期: %s %s", date_str, weekday)
    log.info("距考试: %d 天", days_left)
    log.info("企业微信 Webhook: %s", "已配置" if get_wecom_webhook() else "未配置")

    # 2. 准备输出目录
    out_cfg = OutputConfig()
    os.makedirs(out_cfg.output_dir, exist_ok=True)
    pdf_path = os.path.join(
        out_cfg.output_dir,
        f"{out_cfg.pdf_filename_prefix}_{date_str}.pdf",
    )

    # 3. 抓取评论
    log.info("[1/4] 抓取人民日报评论...")
    comments = fetch_comments()
    log.info("  共 %d 篇", len(comments))
    for c in comments:
        paras = len(c.get("content", []))
        log.debug("  - %s (%d段)", c["title"][:40], paras)

    # 4. 抓取新闻
    log.info("[2/4] 抓取时政新闻...")
    news_list = fetch_news()
    log.info("  共 %d 条", len(news_list))
    for n in news_list[:5]:
        log.debug("  - [%s] %s", n["source"], n["title"][:50])

    # 5. 生成 PDF
    log.info("[3/4] 生成 PDF...")
    try:
        builder = ReportBuilder()
        builder.build(comments, news_list, date_str, date_cn, weekday,
                      days_left, pdf_path)
        fsize_kb = round(os.path.getsize(pdf_path) / 1024, 1)
        log.info("  完成: %.1f KB", fsize_kb)
    except Exception as e:
        log.error("PDF 生成失败: %s", e)
        raise

    # 6. 企业微信推送
    log.info("[4/4] 推送到企业微信...")
    total_golden = sum(len(c.get("golden", [])) for c in comments)
    markdown = build_markdown_message(
        exam_name=exam_name,
        date_cn=date_cn,
        weekday=weekday,
        days_left=days_left,
        comments_len=len(comments),
        news_len=len(news_list),
        golden_len=total_golden,
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
