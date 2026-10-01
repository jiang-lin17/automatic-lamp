"""企业微信 Webhook 推送模块：文本消息 + 文件上传。"""

import os
from typing import Tuple

import requests

from .utils import log


class WeComPusher:
    """企业微信群机器人 Webhook 客户端。"""

    UPLOAD_URL_TEMPLATE = "https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key={key}&type=file"

    def __init__(self, webhook_url: str):
        if not webhook_url:
            raise ValueError("未配置 WECOM_WEBHOOK 环境变量")
        self.webhook_url = webhook_url
        self._key = self._extract_key(webhook_url)

    @staticmethod
    def _extract_key(url: str) -> str:
        """从 webhook URL 中提取 key 参数。

        格式：https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxxx
        """
        try:
            # 优先用 urlparse，比 split 更健壮
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(url)
            params = parse_qs(parsed.query)
            key = params.get("key", [""])[0]
            if key:
                return key
        except Exception:
            pass
        # 兜底
        if "key=" in url:
            return url.split("key=")[-1].split("&")[0]
        return ""

    # ========== 发送文本 ==========
    def send_text(self, markdown_content: str) -> bool:
        """发送 markdown 格式文本消息。"""
        try:
            payload = {"msgtype": "markdown", "markdown": {"content": markdown_content}}
            resp = requests.post(self.webhook_url, json=payload, timeout=10)
            data = resp.json()
            if data.get("errcode") == 0:
                log.info("企业微信文本推送: OK")
                return True
            log.error("企业微信文本推送失败: %s", data)
            return False
        except Exception as e:
            log.error("企业微信文本推送异常: %s", e)
            return False

    # ========== 发送文件 ==========
    def send_file(self, file_path: str) -> bool:
        """先上传文件拿 media_id，再以 file 消息类型推送。"""
        if not self._key:
            log.error("无法从 webhook URL 提取 key")
            return False

        try:
            upload_url = self.UPLOAD_URL_TEMPLATE.format(key=self._key)
            with open(file_path, "rb") as f:
                files = {"media": (os.path.basename(file_path), f)}
                resp = requests.post(upload_url, files=files, timeout=30)
                data = resp.json()

            if data.get("errcode") != 0:
                log.error("文件上传失败: %s", data)
                return False

            media_id = data["media_id"]
            payload = {"msgtype": "file", "file": {"media_id": media_id}}
            resp2 = requests.post(self.webhook_url, json=payload, timeout=10)
            data2 = resp2.json()
            if data2.get("errcode") == 0:
                log.info("企业微信文件推送: OK")
                return True
            log.error("文件消息推送失败: %s", data2)
            return False
        except Exception as e:
            log.error("企业微信文件推送异常: %s", e)
            return False

    # ========== 便捷方法 ==========
    def send_report(self, markdown_content: str, file_path: str) -> Tuple[bool, bool]:
        """一次性推送文本 + 文件，返回 (文本是否成功, 文件是否成功)。"""
        t = self.send_text(markdown_content)
        f = self.send_file(file_path)
        return t, f


def build_markdown_message(
    exam_name: str,
    date_cn: str,
    weekday: str,
    days_left: int,
    comments_len: int,
    news_len: int,
    golden_len: int,
    ai_summary_headline: str = "",
    ai_summary_text: str = "",
    ai_enabled: bool = False,
) -> str:
    """构造企业微信 Markdown 消息体。"""
    lines = [
        f"## 📚 {exam_name}每日备考资料 - {date_cn} {weekday}",
        "",
        f"⏰ 距{exam_name}笔试还有 **{days_left}** 天",
        "",
        "---",
        "",
        "### 📰 今日内容",
        "",
        f"- **人民日报评论**: {comments_len}篇（全文+金句）",
        f"- **时政热点**: {news_len}条（新华网+人民网）",
        f"- **金句积累**: {golden_len}句",
    ]
    if ai_enabled:
        lines += [
            f"- **🤖 AI 增强**: 已启用（考点提炼+AI金句+申论素材+每日总评）",
        ]
    lines += [
        "",
        "---",
        "",
    ]
    # AI 总评（短的话放 markdown 里，太长就省略）
    if ai_summary_headline and ai_summary_text:
        summary = ai_summary_text.strip()
        if len(summary) > 180:
            summary = summary[:177] + "..."
        lines += [
            "### 🤖 AI 每日总评",
            "",
            f"**{ai_summary_headline}**",
            "",
            summary,
            "",
            "---",
            "",
        ]
    lines += [
        "### 💡 学习建议",
        "",
        "1. 精读2篇评论，分析论证结构",
        "2. 摘抄金句，用于申论写作",
        "3. 时政标注考点（数字/会议/政策）",
        "",
        "---",
        "",
        "📎 PDF已发送，请查收附件",
        "",
        "> 每天进步一点点，一次上岸江西！💪",
    ]
    return "\n".join(lines)
