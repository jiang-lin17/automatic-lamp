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
        "max_items": 2,
        # 只在目标日期往前 N 天内挑文章（解析不到日期的条目保留）
        "date_window_days": 20,
        # 每个源最多为多少条候选抓正文（控成本，避免一次跑几十个请求）
        "max_fetches": 12,
    },
    "people_ruiping": {
        "name": "人民锐评",
        "source": "人民网",
        "list_url": "http://opinion.people.com.cn/GB/436867/index.html",
        "href_contains": ["/n1/", "c436867"],
        "article_encoding": "utf-8",
        "max_items": 1,
        "date_window_days": 20,
        "max_fetches": 10,
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
        "date_window_days": 14,
        "max_fetches": 16,
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
        "date_window_days": 14,
        "max_fetches": 16,
    },
    # 注：gov.cn/yaowen/ 是 SPA，requests 抓不到；/zhengce/zuixin/ 的列表由 JS 渲染，
    #     静态 HTML 里只剩页脚链接（会误抓成「中国政府网微博、微信」），故改用 /zhengce/ 栏目页
    "gov_policy": {
        "name": "中国政府网政策动态",
        "source": "中国政府网",
        "list_url": "https://www.gov.cn/zhengce/",
        "href_contains": ["content_"],
        "path_contains": ["/zhengce/"],
        "article_encoding": "utf-8",
        "max_items": 5,
        "min_title_len": 10,
        # gov.cn 的 URL 只有年月（/202609/），日期只能从正文里取，故窗口放宽
        "date_window_days": 20,
        "max_fetches": 14,
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
        "date_window_days": 14,
        "max_fetches": 16,
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


# ========== 跨天去重配置 ==========
@dataclass
class DedupConfig:
    """解决「每天推同一批文章」：记录已推送 URL，只在没推过的里面挑。

    状态文件由 CI 的 actions/cache 跨天带回；本地跑则落在 state/seen.json。
    """
    # 去重状态文件路径
    state_path: str = "state/seen.json"
    # 状态保留天数（超期自动清理，控制体积）
    keep_days: int = 30
    # 日期窗口解析不到时的兜底窗口
    fallback_window_days: int = 30


# ========== 输出配置 ==========
@dataclass
class OutputConfig:
    output_dir: str = "./output"
    pdf_filename_prefix: str = "meiriziliao"


# ========== 企业微信 ==========
def get_wecom_webhook() -> str:
    """从环境变量读取企业微信 Webhook URL"""
    return os.environ.get("WECOM_WEBHOOK", "")


# ========== AI 增强配置 ==========
@dataclass
class AIConfig:
    """LiteLLM 统一接入配置。

    LiteLLM 的 model 字段必须带 provider 前缀，以让 SDK 正确识别：
      - DeepSeek:      deepseek/deepseek-chat
      - 硅基流动:      openai/deepseek-chat, base_url=https://api.siliconflow.cn/v1
      - 通义千问:      qwen/qwen-plus
      - 火山方舟:      openai/ark-code-latest, base_url=https://ark.cn-beijing.volces.com/api/v3
      - 阿里 DashScope: qwen/qwen-turbo, base_url=https://dashscope.aliyuncs.com/compatible-mode/v1
      - 本地 Ollama:   ollama/qwen2.5:7b, base_url=http://localhost:11434

    API Key 只从环境变量读取（AI_API_KEY 或各 provider 自己的，如 DEEPSEEK_API_KEY）。
    """
    # 开关：None = 自动（有 Key 才启用），True = 强制启用，False = 强制禁用
    enabled: bool | None = None
    # model 必须带 provider 前缀（LiteLLM 要求）
    model: str = os.environ.get("AI_MODEL", "deepseek/deepseek-chat")
    # 可选：自定义 base_url（硅基流动等兼容网关用）
    base_url: str = os.environ.get("AI_BASE_URL", "")
    # 调用超时秒数。方舟/gpt 类接口单次响应常在 30~60s，30s 会把「慢但能成功」的
    # 请求直接判超时，故放宽到 90s
    timeout: int = 90
    # litellm 层重试次数。置 0 关掉 OpenAI SDK 默认的 2 次内部重试，
    # 否则一次失败最坏耗时 = timeout × 3，会瞬间吃掉整个时间预算
    num_retries: int = 0
    # 温度（0=稳定，1=创意）
    temperature: float = 0.3
    # 单篇最大输入字符（防止 token 爆）
    max_input_chars_per_article: int = 4000
    # 最多处理多少条新闻做考点提炼（直接决定 AI 调用次数与总耗时）
    max_news_for_points: int = 6
    # 最多处理多少篇评论做金句精选（单次批量调用，全塞进去会超 token）
    max_comments_for_golden: int = 4
    # 申论素材的目标字数
    target_shenlun_chars: int = 300


def get_ai_key() -> str:
    """从环境变量读取 AI API Key。支持多种命名。"""
    for name in ("AI_API_KEY", "DEEPSEEK_API_KEY", "SILICONFLOW_API_KEY",
                 "DASHSCOPE_API_KEY", "ARK_API_KEY", "OPENAI_API_KEY"):
        val = os.environ.get(name, "")
        if val:
            return val
    return ""

