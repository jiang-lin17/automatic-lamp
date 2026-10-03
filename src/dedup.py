"""跨天去重与发布日期识别。

解决「每天推同一批文章」的问题：抓取层过去只取列表页前 N 条，
既不看发布日期、也不记录历史，导致连续多天内容高度重叠。

两条机制配合：
  1. 发布日期过滤 —— 只保留目标日期附近的新文章（解析不到日期时保留，避免误杀）
  2. SeenStore   —— 记录已推送过的 URL，哪怕放宽日期窗口也不会重复
"""

import json
import os
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from .config import DedupConfig
from .utils import log


# ========== 日期提取 ==========

# 正文/页面里的「发布日期：2026年09月30日」「成文日期：2026年09月25日」
_DATE_PATTERNS = [
    re.compile(r"发布日期[：:]\s*(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
    re.compile(r"成文日期[：:]\s*(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
    # 人民日报评论页眉： 《 人民日报 》（ 2026年09月30日 05 版）
    re.compile(r"《\s*人民日报\s*》\s*[（(]\s*(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
    # 破折号格式：发布时间：2026-09-30 / 发布日期：2026-09-30（gov.cn 常见）
    re.compile(r"(?:发布日期|发布时间|成文日期)[：:]\s*(20\d{2})-(\d{1,2})-(\d{1,2})"),
    re.compile(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
]


def _ymd(year: str, month: str, day: str) -> Optional[str]:
    """校验并归一化成 YYYYMMDD。"""
    try:
        datetime(int(year), int(month), int(day))
    except (TypeError, ValueError):
        return None
    return f"{int(year):04d}{int(month):02d}{int(day):02d}"


def extract_date_from_url(url: str) -> Optional[str]:
    """从 URL 的路径段里提取发布日期，返回 YYYYMMDD；只有年月或取不到时返回 None。

    只认被 ``/`` 隔开的完整路径段，避免误匹配 hash 里的数字串：
      - news.cn/politics/20260929/8d7fa5.../c.html   -> 20260929
      - people.com.cn/n1/2026/1001/c1001-40808476.html -> 20261001
      - gov.cn/zhengce/content/202609/content_xxx.htm  -> None（只有年月）
    """
    if not url:
        return None
    path = url.split("?", 1)[0].split("#", 1)[0]
    segments = [s for s in path.split("/") if s]

    prev_year: Optional[str] = None
    for seg in segments:
        # 人民网格式：/n1/2026/1001/ —— 年段后面紧跟 MMDD 段
        if prev_year and re.fullmatch(r"\d{4}", seg):
            got = _ymd(prev_year, seg[:2], seg[2:])
            if got:
                return got

        if re.fullmatch(r"20\d{2}", seg):
            prev_year = seg
            continue
        prev_year = None

        # YYYYMMDD
        if re.fullmatch(r"\d{8}", seg):
            got = _ymd(seg[:4], seg[4:6], seg[6:])
            if got:
                return got

    return None


def extract_date_from_text(text: str) -> Optional[str]:
    """从页面正文里提取发布日期，返回 YYYYMMDD。"""
    if not text:
        return None
    for pattern in _DATE_PATTERNS:
        m = pattern.search(text)
        if m:
            got = _ymd(m.group(1), m.group(2), m.group(3))
            if got:
                return got
    return None


def parse_ymd(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str or len(date_str) != 8 or not date_str.isdigit():
        return None
    try:
        return datetime(int(date_str[:4]), int(date_str[4:6]), int(date_str[6:]))
    except ValueError:
        return None


def within_window(date_str: Optional[str], target: datetime,
                  window_days: int) -> bool:
    """判断发布日期是否落在 [target - (window_days - 1), target] 内。

    日期解析不到时返回 True（保留并标记），宁可多带一条也不误杀。
    """
    parsed = parse_ymd(date_str)
    if parsed is None:
        return True
    delta = (target.replace(hour=0, minute=0, second=0, microsecond=0) - parsed).days
    return 0 <= delta <= max(0, window_days - 1)


def normalize_url(url: str) -> str:
    """归一化 URL 作为去重键：去掉协议、查询串和结尾斜杠。"""
    if not url:
        return ""
    key = url.split("#", 1)[0].split("?", 1)[0].strip()
    key = re.sub(r"^https?://", "", key, flags=re.IGNORECASE)
    return key.rstrip("/").lower()


# ========== 跨天去重状态 ==========

class SeenStore:
    """记录已推送过的文章 URL。

    状态文件由 CI 的 actions/cache 跨天带回；本地跑则落在 state/seen.json。
    """

    def __init__(self, cfg: Optional[DedupConfig] = None):
        self.cfg = cfg or DedupConfig()
        self._urls: Dict[str, str] = {}
        self._dirty = False
        self._load()

    # ---- 读写 ----

    def _load(self) -> None:
        try:
            with open(self.cfg.state_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            urls = raw.get("urls", {})
            if isinstance(urls, dict):
                self._urls = {str(k): str(v) for k, v in urls.items()}
        except FileNotFoundError:
            log.debug("去重状态文件不存在，按空状态开始：%s", self.cfg.state_path)
        except (OSError, ValueError) as e:
            log.warning("去重状态文件读取失败（按空状态继续）：%s", e)

    def save(self, today: Optional[datetime] = None) -> None:
        """落盘。即使没有新增也写一次，保证 CI 里路径存在。"""
        self._prune(today)
        directory = os.path.dirname(self.cfg.state_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        try:
            with open(self.cfg.state_path, "w", encoding="utf-8") as f:
                json.dump({"urls": self._urls}, f, ensure_ascii=False, indent=1)
            log.info("去重状态已保存：%d 条记录 -> %s", len(self._urls), self.cfg.state_path)
        except OSError as e:
            log.warning("去重状态保存失败：%s", e)

    def _prune(self, today: Optional[datetime] = None) -> None:
        """清理超过 keep_days 的旧记录，控制体积。"""
        today = today or datetime.now()
        cutoff = (today - timedelta(days=self.cfg.keep_days)).strftime("%Y%m%d")
        before = len(self._urls)
        self._urls = {
            k: v for k, v in self._urls.items()
            if not v or v >= cutoff
        }
        if before != len(self._urls):
            log.debug("去重状态清理 %d 条过期记录", before - len(self._urls))

    # ---- 查询与标记 ----

    def is_seen(self, url: str) -> bool:
        return normalize_url(url) in self._urls

    def mark(self, urls: Iterable[str], date_str: str = "") -> int:
        # 日期统一成 YYYYMMDD，否则 _prune 的字符串比较会把 "2026-10-02" 误判为过期
        day = re.sub(r"\D", "", date_str or "")[:8]
        added = 0
        for url in urls:
            key = normalize_url(url)
            if key and key not in self._urls:
                self._urls[key] = day
                self._dirty = True
                added += 1
        return added

    def __len__(self) -> int:
        return len(self._urls)


_store: Optional[SeenStore] = None


def get_seen_store(cfg: Optional[DedupConfig] = None) -> SeenStore:
    """进程内共享同一个 SeenStore，避免多处读写互相覆盖。"""
    global _store
    if _store is None:
        _store = SeenStore(cfg)
    return _store


def commit_seen(today: Optional[datetime] = None) -> None:
    """把本次运行的结果落盘（在 PDF 生成成功之后调用）。"""
    if _store is not None:
        _store.save(today)
