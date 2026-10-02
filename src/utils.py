""""工具模块：日志、日期、HTTP Session 等通用能力。"""

import logging
import time
from datetime import datetime, timedelta
from typing import Tuple, Optional

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
)

from .config import HttpConfig, ExamConfig


# ========== 结构化日志 ==========

def setup_logger(name: str = "automatic-lamp", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    try:
        fh = logging.FileHandler("run.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        pass
    return logger

log = setup_logger()


# ========== HTTP Session ==========

_session: Optional[requests.Session] = None

def get_session(cfg: Optional[HttpConfig] = None) -> requests.Session:
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


def _detect_html_charset(raw_bytes: bytes) -> Optional[str]:
    import re
    m = re.search(rb'<meta\s+[^>]*charset\s*=\s*["\']?([^\s"\'>]+)', raw_bytes, re.IGNORECASE)
    if m:
        enc = m.group(1).decode("ascii", errors="ignore")
        if enc and enc.lower() != "iso-8859-1":
            return enc
    m = re.search(rb'<meta\s+[^>]*http-equiv\s*=\s*["\']content-type["\'][^>]*>', raw_bytes, re.IGNORECASE)
    if m:
        m2 = re.search(rb'charset\s*=\s*["\']?([^\s"\'>;]+)', m.group(0), re.IGNORECASE)
        if m2:
            enc = m2.group(1).decode("ascii", errors="ignore")
            if enc and enc.lower() != "iso-8859-1":
                return enc
    return None


def _should_retry(exc: BaseException) -> bool:
    """判断异常是否值得重试。

    ConnectionError/Timeout: 全部重试
    HTTPError: 5xx/429/403 重试，其他 4xx 不重试
    """
    if isinstance(exc, (requests.ConnectionError, requests.Timeout)):
        return True
    if isinstance(exc, requests.HTTPError):
        resp = exc.response
        if resp is None:
            return True
        code = resp.status_code
        if code >= 500 or code == 429 or code == 403:
            return True
    return False


def _try_single_url(url: str, encoding: Optional[str] = None,
                    timeout: Optional[int] = None,
                    session: Optional[requests.Session] = None) -> requests.Response:
    s = session or get_session()
    cfg = HttpConfig()
    time.sleep(cfg.request_interval)
    resp = s.get(url, timeout=timeout or cfg.timeout)
    detected = _detect_html_charset(resp.content)
    if detected:
        resp.encoding = detected
    elif resp.apparent_encoding and resp.apparent_encoding.lower() != "iso-8859-1":
        resp.encoding = resp.apparent_encoding
    else:
        resp.encoding = encoding or "utf-8"
    resp.raise_for_status()
    return resp


def _build_fallback_url(url: str) -> Optional[str]:
    if url.startswith("http://"):
        return "https://" + url[len("http://"):]
    return None


def http_get(url: str, encoding: Optional[str] = None,
             timeout: Optional[int] = None,
             session: Optional[requests.Session] = None) -> requests.Response:
    """带重试 + 协议兜底的 HTTP GET。

    先试原 URL（内部重试最多 3 次），http 全挂则自动试 https 兜底。
    两个都失败 → 抛最后一次异常。
    """
    cfg = HttpConfig()

    @retry(
        stop=stop_after_attempt(cfg.max_retries),
        wait=wait_exponential(multiplier=cfg.retry_wait, min=1, max=10),
        retry=retry_if_exception(_should_retry),
        reraise=True,
    )
    def _attempt(try_url: str) -> requests.Response:
        return _try_single_url(try_url, encoding, timeout, session)

    last_exc: Optional[Exception] = None
    try:
        return _attempt(url)
    except Exception as e:
        last_exc = e
        log.warning("  主 URL 失败 (HTTP %s): %s", type(e).__name__, url)

    fallback = _build_fallback_url(url)
    if fallback:
        log.info("  尝试 HTTPS 兜底: %s", fallback)
        try:
            return _attempt(fallback)
        except Exception as e:
            last_exc = e
            log.warning("  HTTPS 兜底也失败 (HTTP %s)", type(e).__name__)

    if last_exc:
        raise last_exc
    raise requests.ConnectionError(f"All attempts failed for {url}")


# ========== 日期工具 ==========

WEEKDAYS_CN = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

def get_target_date(days_ago: int = 1) -> datetime:
    return datetime.now() - timedelta(days=days_ago)

def format_date(date: datetime) -> Tuple[str, str, str, int]:
    date_str = date.strftime("%Y-%m-%d")
    date_cn = f"{date.year}年{date.month:02d}月{date.day:02d}日"
    weekday = WEEKDAYS_CN[date.weekday()]
    exam_date = ExamConfig().date
    days_left = (exam_date - date).days
    return date_str, date_cn, weekday, days_left

def current_year() -> int:
    return datetime.now().year
