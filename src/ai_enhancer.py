"""AI 增强模块 — 基于 LiteLLM 统一接入多家大模型。

4 个功能：
  1. 新闻考点提炼 (extract_exam_points_from_news)
  2. AI 金句精选 (ai_select_golden)
  3. 申论素材生成 (generate_shenlun_material)
  4. 每日总评 (daily_summary)

设计原则：
  - 完全可选：没配 API Key 时静默降级，不影响原有流程
  - 统一 JSON 输出：所有函数返回 dict，方便 PDF 渲染
  - 带超时 + 异常保护：单篇 AI 失败不影响其他
  - 严格遵守 LiteLLM 的 provider 前缀要求（experience 教训）
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from .config import AIConfig, get_ai_key
from .utils import log


# ========== 连接探测 ==========

def is_ai_available(cfg: Optional[AIConfig] = None) -> bool:
    """检查 AI 功能是否可用：有 Key + 开关非 False。"""
    cfg = cfg or AIConfig()
    if cfg.enabled is False:
        return False
    return bool(get_ai_key())


def _resolve_api_key(model: str, base_url: str = "") -> str:
    """根据 model 前缀推断 Key 环境变量名，兜底到 AI_API_KEY。

    LiteLLM 的常见 provider 到 env 映射：
      deepseek/*      -> DEEPSEEK_API_KEY
      qwen/*          -> DASHSCOPE_API_KEY 或 QWEN_API_KEY
      openai/*        -> OPENAI_API_KEY（或兼容网关用 AI_API_KEY）
      ollama/*        -> 不需要 Key（本地）
    """
    key = get_ai_key()
    if key:
        return key

    prefix = model.split("/")[0].lower() if "/" in model else ""
    env_map = {
        "deepseek": "DEEPSEEK_API_KEY",
        "qwen": "DASHSCOPE_API_KEY",
        "openai": "OPENAI_API_KEY",
        "ark": "ARK_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "groq": "GROQ_API_KEY",
    }
    if prefix in env_map:
        return os.environ.get(env_map[prefix], "")
    return ""


# ========== 底层调用 ==========

def _call_llm(system_prompt: str, user_prompt: str,
              cfg: Optional[AIConfig] = None,
              expect_json: bool = True) -> Optional[str]:
    """调用 LiteLLM completion。失败返回 None（永不抛异常）。"""
    cfg = cfg or AIConfig()
    api_key = _resolve_api_key(cfg.model, cfg.base_url)
    if not api_key and not cfg.model.startswith("ollama/"):
        log.debug("AI Key 未配置，跳过调用 model=%s", cfg.model)
        return None

    try:
        import litellm
    except ImportError:
        log.warning("litellm 未安装，请 pip install litellm")
        return None

    try:
        kwargs: Dict[str, Any] = dict(
            model=cfg.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=cfg.temperature,
            timeout=cfg.timeout,
        )
        if api_key:
            kwargs["api_key"] = api_key
        if cfg.base_url:
            kwargs["base_url"] = cfg.base_url

        if expect_json:
            kwargs["response_format"] = {"type": "json_object"}

        log.debug("AI 调用 model=%s base_url=%s", cfg.model, cfg.base_url or "(默认)")
        resp = litellm.completion(**kwargs)
        content = resp.choices[0].message.content
        if content is None:
            return None
        # 某些模型会把 ```json ... ``` 包裹起来，剥掉
        content = content.strip()
        if content.startswith("```"):
            lines = content.split("\n")
            # 去掉首尾 ``` 行
            content = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
        return content.strip()
    except Exception as e:
        # LiteLLM 的异常类型可能是 litellm.AuthenticationError / litellm.Timeout 等
        err_type = type(e).__name__
        log.warning("AI 调用失败 [%s]: %s", err_type, str(e)[:200])
        return None


# ========== 四个 AI 功能 ==========

def extract_exam_points_from_news(news_list: List[Dict[str, Any]],
                                   cfg: Optional[AIConfig] = None) -> List[Dict[str, Any]]:
    """功能 1：为每条新闻生成 2-3 条公考考点提示。

    输入：抓取到的新闻列表（前 N 条）
    输出：每条新闻加 exam_points 字段，如 [{title, exam_points: [str,...]}, ...]
    """
    cfg = cfg or AIConfig()
    if not is_ai_available(cfg):
        return news_list

    take = news_list[:cfg.max_news_for_points]
    system = (
        "你是一位资深公务员考试研究员，熟悉行测常识和申论考点。"
        "请从给定新闻中提炼 2-3 条与公考相关的考点提示。"
        "考点可以是：政策名词解释、重要会议/文件、关键数字、重大战略、"
        "可用于申论的论点角度等。语言要精准、简洁，每条不超过 25 字。"
    )

    results: List[Dict[str, Any]] = []
    for n in take:
        title = n.get("title", "")
        summary = n.get("summary", "")
        user = f"标题：{title}\n摘要：{summary}\n" \
               "请输出 JSON：{\"exam_points\": [\"考点1\", \"考点2\", ...]}"

        raw = _call_llm(system, user, cfg)
        if raw:
            try:
                data = json.loads(raw)
                points = data.get("exam_points", [])
                points = [p.strip() for p in points if p.strip()]
            except json.JSONDecodeError:
                points = []
        else:
            points = []

        enriched = dict(n)
        enriched["exam_points"] = points[:3]
        results.append(enriched)
        log.info("  AI 考点提炼 [%s] → %d 条", title[:30], len(points))

    # 未处理的新闻原样带上
    for n in news_list[cfg.max_news_for_points:]:
        enriched = dict(n)
        enriched["exam_points"] = []
        results.append(enriched)

    return results


def ai_select_golden(comments: List[Dict[str, Any]],
                      cfg: Optional[AIConfig] = None) -> List[Dict[str, Any]]:
    """功能 2：用 AI 从评论正文里精选 2-3 条最佳金句 + 一句点评。

    输入：评论列表
    输出：每条评论加 ai_golden 字段（比规则提取的 golden 更准）+ ai_comment 字段
    """
    cfg = cfg or AIConfig()
    if not is_ai_available(cfg):
        return comments

    system = (
        "你是一位申论写作专家，擅长从时评文章中提炼金句。"
        "请从给定文章中选出 2-3 条最适合申论写作引用的精彩语句，"
        "并写一句 30 字以内的 AI 点评。"
        "金句要求：观点鲜明、表达精炼、适合作为论点或过渡。"
    )

    results: List[Dict[str, Any]] = []
    for c in comments:
        title = c.get("title", "")
        # 正文截断防止 token 爆
        content = "".join(c.get("content", []))[:cfg.max_input_chars_per_article]
        summary = c.get("summary", "")
        user = (
            f"标题：{title}\n"
            f"摘要：{summary}\n"
            f"正文：{content}\n\n"
            '请输出 JSON：{"ai_golden": ["金句1", "金句2"], "ai_comment": "一句点评"}'
        )

        raw = _call_llm(system, user, cfg)
        ai_golden: List[str] = []
        ai_comment: str = ""
        if raw:
            try:
                data = json.loads(raw)
                ai_golden = [g.strip() for g in data.get("ai_golden", []) if g.strip()][:3]
                ai_comment = data.get("ai_comment", "").strip()[:60]
            except json.JSONDecodeError:
                pass

        enriched = dict(c)
        enriched["ai_golden"] = ai_golden
        enriched["ai_comment"] = ai_comment
        results.append(enriched)
        log.info("  AI 金句 [%s] → %d 条金句 + 点评=%s",
                 title[:30], len(ai_golden), ai_comment[:20] if ai_comment else "空")

    return results


def generate_shenlun_material(comments: List[Dict[str, Any]],
                               news_list: List[Dict[str, Any]],
                               cfg: Optional[AIConfig] = None) -> Dict[str, Any]:
    """功能 3：把当日内容浓缩成一段申论可用的素材。

    输出结构：
    {
        "topic": "今日申论主题（一句话）",
        "opening": "申论开头段素材（150-200字）",
        "transition": "申论过渡句/衔接段（100字左右）",
        "conclusion": "申论结尾段素材（100字左右）",
        "key_words": ["关键词1", "关键词2", ...],
    }
    """
    cfg = cfg or AIConfig()
    empty_result: Dict[str, Any] = {
        "topic": "", "opening": "", "transition": "",
        "conclusion": "", "key_words": [],
    }
    if not is_ai_available(cfg):
        return empty_result

    # 收集摘要和标题做 prompt
    comment_titles = [c.get("title", "") for c in comments[:3]]
    news_titles = [n.get("title", "") for n in news_list[:8]]
    summaries = " | ".join(
        [c.get("summary", "") for c in comments[:2]] +
        [n.get("summary", "") for n in news_list[:3] if n.get("summary")]
    )

    system = (
        "你是一位申论写作名师，擅长把当日时政素材转化为申论可用的段落。"
        "请紧扣今日主题，给出：一个主题概括、一个开头段、一个过渡段、一个结尾段、4-6个关键词。"
        "要求语言正式、有政策高度、适合直接引用或稍作修改后使用。"
    )
    user = (
        f"今日人民日报评论标题：{comment_titles}\n"
        f"今日时政热点标题：{news_titles}\n"
        f"综合摘要：{summaries}\n\n"
        '请输出 JSON：'
        '{"topic": "...", "opening": "...", "transition": "...",'
        ' "conclusion": "...", "key_words": ["...", "..."]}'
    )

    raw = _call_llm(system, user, cfg)
    if not raw:
        return empty_result
    try:
        data = json.loads(raw)
        return {
            "topic": data.get("topic", "").strip(),
            "opening": data.get("opening", "").strip()[:600],
            "transition": data.get("transition", "").strip()[:400],
            "conclusion": data.get("conclusion", "").strip()[:300],
            "key_words": [k.strip() for k in data.get("key_words", []) if k.strip()][:8],
        }
    except json.JSONDecodeError:
        return empty_result


def daily_summary(comments: List[Dict[str, Any]],
                   news_list: List[Dict[str, Any]],
                   cfg: Optional[AIConfig] = None) -> Dict[str, str]:
    """功能 4：每日总评 — AI 一句话点评当日最重要的政策/热点。

    输出：
    {
        "headline": "今日最重磅（一句话，含事件名）",
        "summary": "总评正文（150字以内，要有立场、有高度）",
    }
    """
    cfg = cfg or AIConfig()
    empty_result = {"headline": "", "summary": ""}
    if not is_ai_available(cfg):
        return empty_result

    all_titles = ([c.get("title", "") for c in comments] +
                  [n.get("title", "") for n in news_list[:10]])

    system = (
        "你是一位资深时评家。请从今日时政要闻中选出最重要的一件，"
        "写一句重磅标题和一段 100-150 字的总评。"
        "总评要有高度，点出事件的重要性和深远影响。"
    )
    user = "今日要闻标题列表：\n" + "\n".join(f"- {t}" for t in all_titles) + \
        '\n\n请输出 JSON：{"headline": "...", "summary": "..."}'

    raw = _call_llm(system, user, cfg)
    if not raw:
        return empty_result
    try:
        data = json.loads(raw)
        return {
            "headline": data.get("headline", "").strip()[:80],
            "summary": data.get("summary", "").strip()[:300],
        }
    except json.JSONDecodeError:
        return empty_result


# ========== 顶层编排 ==========

def run_all_ai_enhance(comments: List[Dict[str, Any]],
                        news_list: List[Dict[str, Any]],
                        cfg: Optional[AIConfig] = None) -> Dict[str, Any]:
    """一键跑完全部 4 个 AI 功能。任何一个失败都不影响其他。

    返回：
    {
        "enabled": bool,
        "news_with_points": [...],        # 新闻 + exam_points
        "comments_with_ai": [...],         # 评论 + ai_golden + ai_comment
        "shenlun_material": {...},
        "daily_summary": {...},
    }
    """
    cfg = cfg or AIConfig()
    ai_ok = is_ai_available(cfg)
    result: Dict[str, Any] = {
        "enabled": ai_ok,
        "model": cfg.model,
        "news_with_points": [],
        "comments_with_ai": [],
        "shenlun_material": {
            "topic": "", "opening": "", "transition": "",
            "conclusion": "", "key_words": [],
        },
        "daily_summary": {"headline": "", "summary": ""},
    }

    if not ai_ok:
        log.info("AI 未启用（检查 AI_API_KEY 或 DEEPSEEK_API_KEY），跳过 AI 增强")
        result["news_with_points"] = news_list
        result["comments_with_ai"] = comments
        return result

    log.info("🤖 AI 增强启用，model=%s", cfg.model)

    # 功能 1 & 2 并行调用不现实（litellm 同步），串行但每个独立
    result["news_with_points"] = extract_exam_points_from_news(news_list, cfg)
    result["comments_with_ai"] = ai_select_golden(comments, cfg)
    result["shenlun_material"] = generate_shenlun_material(comments, news_list, cfg)
    result["daily_summary"] = daily_summary(comments, news_list, cfg)

    # 统计
    sp = result["shenlun_material"]
    ds = result["daily_summary"]
    n_points = sum(1 for n in result["news_with_points"] if n.get("exam_points"))
    n_golden = sum(1 for c in result["comments_with_ai"] if c.get("ai_golden"))
    log.info("✅ AI 完成：考点=%d条新闻, 金句=%d篇评论, 申论素材=%s, 总评=%s",
             n_points, n_golden,
             "OK" if sp.get("topic") else "FAIL",
             "OK" if ds.get("headline") else "FAIL")

    return result
