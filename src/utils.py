"""工具模块：日志、日期、HTTP Session 等通用能力。"""

import logging
import time
from datetime import datetime, timedelta
from typing import Tuple, Optional

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .config import HttpConfig, ExamConfig


# ========== 结构化日志 ==========

def setup_logger(name: str = "automatic-lamp", level: int = logging.INFO) -> logging.Logger:
    """配置统一格式的 logger，输出到控制台和日志文件。"""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # 文件（同时输出，方便 GitHub Actions 查看）
    try:
        fh = logging.FileHandler("run.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        pass  # 某些环境可能没写权限，控制台已经够用

    return logger


log = setup_logger()


# ========== HTTP Session ==========

_session: Optional[requests.Session] = None


def get_session(cfg: Optional[HttpConfig] = None) -> requests.Session:
    """返回全局复用的 requests Session，连接池更高效。"""
    global _session
    if _session is None:
        cfg = cfg or HttpConfig()
        s = requests.Session()
        s.headers.update({
            "User-Agent": cfg.user_agent,
            **cfg.headers,
        })
        _session = s
    return _session


def close_session() -> None:
    global _session
    if _session is not None:
        _session.close()
        _session = None


@retry(
    stop=stop_after_attempt(HttpConfig().max_retries),
    wait=wait_exponential(multiplier=HttpConfig().retry_wait, min=1, max=10),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def http_get(url: str, encoding: Optional[str] = None,
             timeout: Optional[int] = None,
             session: Optional[requests.Session] = None) -> requests.Response:
    """带重试和间隔的 HTTP GET。"""
    s = session or get_session()
    cfg = HttpConfig()
    time.sleep(cfg.request_interval)  # 限速
    resp = s.get(url, timeout=timeout or cfg.timeout)
    resp.encoding = encoding or resp.apparent_encoding or "utf-8"
    resp.raise_for_status()
    return resp


# ========== 日期工具 ==========

WEEKDAYS_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def get_target_date(days_ago: int = 1) -> datetime:
    """默认取昨天，可自定义回溯天数。"""
    return datetime.now() - timedelta(days=days_ago)


def format_date(date: datetime) -> Tuple[str, str, str, int]:
    """返回 (YYYY-MM-DD, YYYY年MM月DD日, 星期X, 距考试剩余天数)"""
    date_str = date.strftime("%Y-%m-%d")
    date_cn = f"{date.year}年{date.month:02d}月{date.day:02d}日"
    weekday = WEEKDAYS_CN[date.weekday()]
    exam_date = ExamConfig().date
    days_left = (exam_date - date).days
    return date_str, date_cn, weekday, days_left


def current_year() -> int:
    return datetime.now().year
