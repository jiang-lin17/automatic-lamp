"""PDF 生成模块 — 精美 A4 报告。

设计主题：「温暖红 · 学术蓝」，庄重又不失灵动。
  - 封面顶部彩带、大标题居中
  - 每页顶部页眉 + 底部页码
  - 章节标题带左侧色条（用 Table 模拟 accent bar）
  - 金句用带背景和左侧粗边的引用框
  - 评论卡片加分隔线、新闻列表分级呈现
"""

import os
from datetime import datetime
from typing import List, Dict, Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_LEFT


# ========== 调色板 ==========
class Palette:
    # 主色：沉稳中国红
    PRIMARY = HexColor("#C62828")         # 深红（封面彩带、章节色条）
    PRIMARY_LIGHT = HexColor("#FFEBEE")    # 浅红（卡片背景）
    # 辅色：学术蓝
    ACCENT = HexColor("#1565C0")          # 深蓝（金句引用边、强调）
    ACCENT_LIGHT = HexColor("#E3F2FD")     # 浅蓝（金句框背景）
    # 中性色
    INK = HexColor("#1A1A1A")              # 主文字
    TEXT = HexColor("#333333")             # 正文
    MUTED = HexColor("#666666")            # 次要文字（来源、元信息）
    FAINT = HexColor("#9E9E9E")            # 更次要
    RULE = HexColor("#E0E0E0")             # 分隔线
    PAGE_BG = HexColor("#FAFAFA")          # 页面底

    COVER_BAND_TOP = HexColor("#C62828")   # 封面顶部彩带
    COVER_BAND_BOT = HexColor("#1565C0")   # 封面底部彩带


# ========== 页面模板 ==========
def _make_page_template(font_name: str):
    """创建带页眉页脚的页面模板。"""

    class _CoverFirstPage(canvas.Canvas):
        """封面：顶部彩条、底部彩条，无页眉页脚。"""
        def __init__(self, *args, **kwargs):
            self._exam_title = kwargs.pop("exam_title", "")
            self._today_info = kwargs.pop("today_info", "")
            self._days_left = kwargs.pop("days_left", "")
            super().__init__(*args, **kwargs)

        def showPage(self):
            w, h = A4
            # 顶部彩带
            self.setFillColor(Palette.COVER_BAND_TOP)
            self.rect(0, h - 28 * mm, w, 28 * mm, fill=1, stroke=0)
            self.setFillColor(white)
            self.setFont(font_name, 9)
            self.drawRightString(w - 20 * mm, h - 18 * mm, self._exam_title)

            # 底部彩带
            self.setFillColor(Palette.COVER_BAND_BOT)
            self.rect(0, 0, w, 18 * mm, fill=1, stroke=0)
            self.setFillColor(white)
            self.setFont(font_name, 8)
            self.drawCentredString(w / 2, 6 * mm, "每天进步一点点，一次上岸江西 🎯")
            super().showPage()

        def save(self):
            super().save()

    class _BodyPage(canvas.Canvas):
        """正文页：页眉 + 页脚页码。"""
        def __init__(self, *args, **kwargs):
            self._exam_title = kwargs.pop("exam_title", "")
            super().__init__(*args, **kwargs)
            self._page_num = 0

        def showPage(self):
            self._page_num += 1
            w, h = A4
            # 页眉顶细线
            self.setStrokeColor(Palette.PRIMARY)
            self.setLineWidth(1.5)
            self.line(18 * mm, h - 15 * mm, w - 18 * mm, h - 15 * mm)
            self.setFillColor(Palette.PRIMARY)
            self.setFont(font_name, 9)
            self.drawString(18 * mm, h - 14 * mm, "📚 每日备考资料")
            self.setFillColor(Palette.MUTED)
            self.setFont(font_name, 8)
            self.drawRightString(w - 18 * mm, h - 14 * mm, self._exam_title)

            # 页脚
            self.setStrokeColor(Palette.RULE)
            self.setLineWidth(0.5)
            self.line(18 * mm, 14 * mm, w - 18 * mm, 14 * mm)
            self.setFillColor(Palette.FAINT)
            self.setFont(font_name, 8)
            self.drawString(18 * mm, 8 * mm, "数据来源：人民网 · 新华网 · 中国政府网")
            self.drawCentredString(w / 2, 8 * mm, f"— {self._page_num} —")
            super().showPage()

        def save(self):
            super().save()

    return _CoverFirstPage, _BodyPage


class ReportBuilder:
    """江西省考每日备考资料 PDF 构建器。"""

    def __init__(self, exam_cfg=None):
        from .config import ExamConfig
        self.exam_cfg = exam_cfg or ExamConfig()
        self.font_name = self._register_font()
        self.styles = self._build_styles()

    # ========== 初始化 ==========
    def _register_font(self) -> str:
        from .config import FONT_CANDIDATES
        for fp in FONT_CANDIDATES:
            if os.path.exists(fp):
                try:
                    pdfmetrics.registerFont(TTFont("CN", fp))
                    log.info("字体: %s", fp)
                    return "CN"
                except Exception as e:
                    log.debug("字体注册失败 %s: %s", fp, e)
        log.warning("未找到中文字体，回退默认")
        return "Helvetica"

    def _build_styles(self) -> Dict[str, ParagraphStyle]:
        fn = self.font_name
        base = getSampleStyleSheet()

        def mk(name, parent, **kw):
            d = dict(fontName=fn)
            d.update(kw)
            return ParagraphStyle(name, parent=base[parent], **d)

        return {
            # 封面
            "cover_title": mk("ct", "Title", fontSize=30, leading=42,
                              alignment=TA_CENTER, textColor=Palette.INK),
            "cover_sub": mk("cs", "Normal", fontSize=13, leading=22,
                            alignment=TA_CENTER, textColor=Palette.MUTED),
            "cover_date": mk("cd", "Normal", fontSize=22, leading=34,
                             alignment=TA_CENTER, textColor=Palette.INK),
            "cover_days": mk("cv", "Normal", fontSize=12, leading=18,
                             alignment=TA_CENTER, textColor=Palette.PRIMARY),
            # 章节标题（带色条，由 Table 包裹）
            "h1_title": mk("h1t", "Heading1", fontSize=17, leading=26,
                           textColor=Palette.INK, spaceAfter=0),
            "h2_title": mk("h2t", "Heading2", fontSize=13, leading=20,
                           textColor=Palette.INK, spaceAfter=0),
            # 评论
            "art_title": mk("art", "Heading3", fontSize=12.5, leading=19,
                            textColor=Palette.INK, spaceAfter=0),
            "art_meta": mk("am", "Normal", fontSize=8.5, leading=13,
                           textColor=Palette.MUTED),
            "bd": mk("bd", "Normal", fontSize=10.5, leading=19,
                     textColor=Palette.TEXT, firstLineIndent=21),
            # 新闻
            "news_item": mk("ni", "Normal", fontSize=10.5, leading=17,
                            textColor=Palette.INK),
            "news_link": mk("nl", "Normal", fontSize=8, leading=12,
                            textColor=Palette.FAINT),
            "news_src": mk("ns", "Normal", fontSize=8.5, leading=12,
                           textColor=Palette.MUTED),
            "news_sum": mk("nsum", "Normal", fontSize=9, leading=14,
                           textColor=Palette.MUTED),
            # 金句引用
            "quote_text": mk("qt", "Normal", fontSize=11, leading=18,
                             textColor=Palette.ACCENT),
            # 学习贴士
            "tip": mk("tp", "Normal", fontSize=10.5, leading=18,
                      textColor=Palette.TEXT, leftIndent=8),
            # 页脚小字
            "tiny": mk("ty", "Normal", fontSize=7.5, leading=11,
                       textColor=Palette.FAINT),
        }

    # ========== 章节标题组件 ==========
    def _section_header(self, title: str, subtitle: str = ""):
        """带左侧色条的章节标题（单列表 + LINEBEFORE）。"""
        fn = self.font_name
        title_para = Paragraph(title, self.styles["h1_title"])
        # 表格宽度直接设为页面可用宽度（A4 170mm 左右，去掉左右边距）
        t = Table([[title_para]], colWidths=[170 * mm])
        t.setStyle(TableStyle([
            ("LINEBEFORE", (0, 0), (0, 0), 3.5, Palette.PRIMARY),
            ("TOPPADDING", (0, 0), (0, 0), 3),
            ("BOTTOMPADDING", (0, 0), (0, 0), 3),
            ("LEFTPADDING", (0, 0), (0, 0), 8),
        ]))
        story = [t]
        if subtitle:
            story.append(Paragraph(subtitle, self.styles["art_meta"]))
        story.append(Spacer(1, 2 * mm))
        return story

    # ========== 封面 ==========
    def _cover(self, date_cn, weekday, days_left, comments_count, news_count, golden_count):
        s = self.styles
        story = []
        story.append(Spacer(1, 45 * mm))
        story.append(Paragraph(f"📚 {self.exam_cfg.pdf_title}", s["cover_title"]))
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(self.exam_cfg.name, s["cover_sub"]))
        story.append(Spacer(1, 18 * mm))
        story.append(Paragraph(f"{date_cn}  {weekday}", s["cover_date"]))
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(f"⏰ 距笔试还有 <b>{days_left}</b> 天", s["cover_days"]))
        story.append(Spacer(1, 20 * mm))

        # 统计卡片（三栏表格）
        fn = self.font_name
        card_data = [
            [Paragraph("📰<br/><b style='font-size:16px'>" + str(comments_count) + "</b><br/><font size=7 color='#666'>人民日报评论</font>",
                       ParagraphStyle("scard", parent=s["h2_title"], alignment=TA_CENTER, leading=16)),
             Paragraph("🔔<br/><b style='font-size:16px'>" + str(news_count) + "</b><br/><font size=7 color='#666'>时政新闻</font>",
                       ParagraphStyle("scard2", parent=s["h2_title"], alignment=TA_CENTER, leading=16)),
             Paragraph("💬<br/><b style='font-size:16px'>" + str(golden_count) + "</b><br/><font size=7 color='#666'>申论金句</font>",
                       ParagraphStyle("scard3", parent=s["h2_title"], alignment=TA_CENTER, leading=16))],
        ]
        t = Table(card_data, colWidths=[50 * mm, 50 * mm, 50 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), Palette.ACCENT_LIGHT),
            ("GRID", (0, 0), (-1, -1), 0.3, Palette.RULE),
            ("TOPPADDING", (0, 0), (-1, -1), 14),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ("FONTNAME", (0, 0), (-1, -1), fn),
        ]))
        story.append(t)
        story.append(PageBreak())
        return story

    # ========== 评论区 ==========
    def _comments_section(self, comments, ai_result=None):
        from .config import ContentThresholds
        s = self.styles
        thresholds = ContentThresholds()
        ai_on = bool(ai_result and ai_result.get("enabled"))
        subtitle = "人民时评 + 人民锐评 · 全文呈现"
        if ai_on:
            subtitle += " · 🤖 AI 金句精选"
        story = self._section_header("📰 人民日报评论", subtitle)

        for i, c in enumerate(comments, 1):
            card = []
            # 序号 + 标题 + 栏目
            title_html = (
                f'<font color="#999" size=11>{i:02d}</font>  '
                f'<b>{c["title"]}</b>'
            )
            card.append(Paragraph(title_html, s["art_title"]))
            # 栏目 / 作者 / 链接
            author_info = f" · 作者：{c['author']}" if c.get("author") else ""
            # AI 评论小徽章
            ai_badge = ""
            if ai_on and c.get("ai_comment"):
                ai_badge = f' · <font color="#1565C0">🤖 AI点评：{c["ai_comment"]}</font>'
            meta = (
                f"<font color='#C62828'>▸ {c['column']}</font>{author_info}{ai_badge} · "
                f'<a href="{c["url"]}" color="#1565C0" size=8>查看原文 →</a>'
            )
            card.append(Paragraph(meta, s["art_meta"]))
            card.append(Spacer(1, 1.5 * mm))

            # 正文
            if c["content"]:
                max_p = min(len(c["content"]), thresholds.max_paragraphs_per_comment)
                for para in c["content"][:max_p]:
                    card.append(Paragraph(para, s["bd"]))
                if len(c["content"]) > max_p:
                    card.append(Paragraph(
                        '<font color="#999" size=8>……剩余内容请查看原文</font>', s["bd"]))
            else:
                card.append(Paragraph(c["summary"], s["bd"]))

            # 金句引用框：优先 AI，兜底规则
            golden_list = (c.get("ai_golden") if ai_on else None) or c.get("golden") or []
            if golden_list:
                card.append(Spacer(1, 2 * mm))
                tag = "🤖 AI 精选金句" if (ai_on and c.get("ai_golden")) else "📬 本文金句"
                card.append(Paragraph(
                    f'<font color="#1565C0" size=9><b>{tag}</b></font>', s["art_meta"]))
                golden_paras = []
                for gs in golden_list[:thresholds.golden_per_article]:
                    golden_paras.append(Paragraph(f"\u201c{gs}\u201d", s["quote_text"]))
                quote_inner = [[p] for p in golden_paras]
                quote_table = Table(quote_inner, colWidths=[160 * mm])
                quote_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), Palette.ACCENT_LIGHT),
                    ("LINEBEFORE", (0, 0), (0, -1), 2.5, Palette.ACCENT),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ]))
                card.append(quote_table)

            # 卡片分隔线
            card.append(Spacer(1, 1.5 * mm))
            card.append(HRFlowable(width="100%", thickness=0.4, color=Palette.RULE,
                                    spaceAfter=4 * mm, spaceBefore=0))
            story.append(KeepTogether(card))

        story.append(PageBreak())
        return story

    # ========== 新闻区（带考点） ==========
    def _news_section(self, news_list):
        s = self.styles
        # 检测是否有 AI 考点
        has_points = any(n.get("exam_points") for n in news_list)
        sub = "来源：新华网 · 人民网 · 中国政府网"
        if has_points:
            sub += " · 🤖 AI 考点提炼"
        story = self._section_header("🔔 时政热点", sub)

        # 按分类聚合
        cats: Dict[str, List] = {}
        for n in news_list:
            cats.setdefault(n["category"], []).append(n)

        for cat, items in cats.items():
            # 子分类标题
            story.append(Paragraph(f"▸ {cat}", ParagraphStyle(
                "cat", parent=s["h2_title"], fontSize=12, leading=18,
                textColor=Palette.ACCENT, leftIndent=2)))
            story.append(Spacer(1, 1.5 * mm))

            for j, n in enumerate(items, 1):
                story.append(Paragraph(f"{j:02d}. {n['title']}", s["news_item"]))
                meta = f'<font color="#999" size=8.5>来源：{n["source"]}</font>'
                story.append(Paragraph(meta, s["news_src"]))
                story.append(Paragraph(
                    f'<a href="{n["url"]}" color="#1565C0" size=8>{n["url"]}</a>',
                    s["news_link"]))
                if n.get("summary"):
                    story.append(Paragraph(
                        f'<font color="#888" size=8.5>摘要：{n["summary"]}</font>', s["news_sum"]))
                # 🤖 AI 考点提示
                if n.get("exam_points"):
                    pts_html = "  ".join(
                        f'<font color="#C62828">▸ {p}</font>' for p in n["exam_points"]
                    )
                    story.append(Paragraph(
                        f'<font size=8 color="#1565C0"><b>🤖 公考考点提示：</b></font>'
                        f'{pts_html}', s["news_src"]))
                story.append(Spacer(1, 1.2 * mm))
            story.append(Spacer(1, 3 * mm))

        story.append(PageBreak())
        return story

    # ========== AI 每日总评 ==========
    def _ai_daily_summary(self, ai_result):
        s = self.styles
        ds = ai_result.get("daily_summary", {})
        if not ds.get("headline"):
            return []

        story = self._section_header("🤖 AI 每日总评",
                                     "LiteLLM 多模型驱动 · 一句话抓住最重要的事")

        # 重磅大标题
        hl_html = f'<font color="#C62828"><b style="font-size:16px">{ds["headline"]}</b></font>'
        story.append(Paragraph(hl_html, ParagraphStyle(
            "hl", parent=s["h1_title"], fontSize=15, leading=22,
            textColor=Palette.PRIMARY)))
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(ds["summary"], s["bd"]))
        story.append(Spacer(1, 3 * mm))
        story.append(PageBreak())
        return story

    # ========== AI 申论素材 ==========
    def _ai_shenlun_material(self, ai_result):
        s = self.styles
        sp = ai_result.get("shenlun_material", {})
        if not sp.get("topic"):
            return []

        story = self._section_header("✍️ AI 申论素材生成",
                                     "开头段 · 过渡段 · 结尾段 · 关键词")

        # 主题行
        story.append(Paragraph(
            f'<font color="#1565C0" size=12><b>📌 今日主题：{sp["topic"]}</b></font>',
            s["news_item"]))
        story.append(Spacer(1, 2 * mm))

        # 四个素材模块
        modules = [
            ("🟢 申论开头段", sp.get("opening", "")),
            ("🔵 申论过渡/衔接段", sp.get("transition", "")),
            ("🔴 申论结尾段", sp.get("conclusion", "")),
        ]
        for label, text in modules:
            if not text:
                continue
            story.append(Paragraph(
                f'<font color="#C62828" size=10><b>{label}</b></font>', s["art_meta"]))
            story.append(Paragraph(text, s["bd"]))
            story.append(Spacer(1, 2.5 * mm))

        # 关键词
        keys = sp.get("key_words", [])
        if keys:
            story.append(Paragraph(
                '<font color="#1565C0" size=10><b>🏷️ 今日关键词</b></font>',
                s["art_meta"]))
            # 用表格做胶囊标签（3 列）
            tag_cells = [[Paragraph(f'<font color="#1565C0">{k}</font>',
                                    ParagraphStyle("tag", fontSize=9, leading=12,
                                                   alignment=TA_CENTER))]
                         for k in keys]
            t = Table(tag_cells, colWidths=[55 * mm, 55 * mm, 55 * mm])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), Palette.ACCENT_LIGHT),
                ("GRID", (0, 0), (-1, -1), 0.3, Palette.ACCENT),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]))
            story.append(t)

        story.append(PageBreak())
        return story

    # ========== 金句汇总 ==========
    def _golden_summary(self, comments, ai_result=None):
        from .config import ContentThresholds
        s = self.styles
        thresholds = ContentThresholds()
        ai_on = bool(ai_result and ai_result.get("enabled"))
        sub = "从当日评论中摘录的精彩语句"
        if ai_on:
            sub += " · 🤖 优先 AI 精选"
        story = self._section_header("📬 申论金句积累", sub)

        # 优先 AI 金句
        all_golden = []
        for c in comments:
            if ai_on and c.get("ai_golden"):
                all_golden.extend(c["ai_golden"])
            elif c.get("golden"):
                all_golden.extend(c["golden"])

        if all_golden:
            for idx, gs in enumerate(all_golden[:thresholds.golden_summary_max], 1):
                box_inner = [[Paragraph(f"\u201c{gs}\u201d", s["quote_text"])]]
                t = Table(box_inner, colWidths=[170 * mm])
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), Palette.ACCENT_LIGHT),
                    ("LINEBEFORE", (0, 0), (0, -1), 2.5, Palette.ACCENT),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ]))
                story.append(Paragraph(
                    f'<font color="#C62828" size=9><b>{idx:02d}</b></font> ',
                    ParagraphStyle("gn", fontSize=9, leading=14)))
                story.append(t)
                story.append(Spacer(1, 1.8 * mm))
        else:
            story.append(Paragraph("今日金句待积累，建议阅读评论文章自行摘抄", s["bd"]))

        story.append(Spacer(1, 8 * mm))
        return story

    # ========== 学习贴士 ==========
    def _tips_section(self, ai_result=None):
        s = self.styles
        ai_on = bool(ai_result and ai_result.get("enabled"))
        sub = ""
        if ai_on:
            sub = "（AI 已部分覆盖时政考点 + 申论素材）"
        story = self._section_header("💡 每日学习贴士", sub)
        tips = [
            ("📖", "精读 2 篇人民日报评论，注意文章结构和论证方法"),
            ("✍️", "摘抄 3–5 个金句，尝试用在申论写作中"),
            ("🔢", "时政新闻中注意数字类、会议类、政策类考点"),
            ("💭", "结合热点思考申论作文的立意和分论点"),
            ("📝", "每天坚持阅读，培养官方语感和政策思维"),
        ]
        for icon, tip in tips:
            tip_html = f"<b>{icon}</b>  {tip}"
            story.append(Paragraph(tip_html, s["tip"]))
            story.append(Spacer(1, 2.2 * mm))

        if ai_on:
            story.append(HRFlowable(width="60%", thickness=0.4, color=Palette.RULE,
                                     spaceAfter=2 * mm, spaceBefore=4 * mm))
            story.append(Paragraph(
                f'<font color="#1565C0" size=8.5>🤖 AI 增强由 LiteLLM 提供 · '
                f'model={ai_result.get("model", "?")}</font>', s["tiny"]))

        story.append(Spacer(1, 12 * mm))
        story.append(HRFlowable(width="40%", thickness=0.6, color=Palette.PRIMARY,
                                 spaceAfter=2 * mm))
        story.append(Paragraph(
            '<font color="#888" size=7.5>生成时间：'
            f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | '
            "由 GitHub Actions 自动生成</font>", s["tiny"]))
        return story

    # ========== 入口 ==========
    def build(self, comments, news_list, ai_result,
              date_str, date_cn, weekday,
              days_left, output_path) -> bool:
        from .config import ContentThresholds

        thresholds = ContentThresholds()
        # 优先 AI 金句，兜底规则金句
        total_golden = sum(
            len(c.get("ai_golden") or c.get("golden", []))
            for c in comments
        )

        cover_cls, body_cls = _make_page_template(self.font_name)

        doc = SimpleDocTemplate(
            output_path, pagesize=A4,
            leftMargin=18 * mm, rightMargin=18 * mm,
            topMargin=18 * mm, bottomMargin=18 * mm,
            title=self.exam_cfg.pdf_title, author="GK Helper",
        )

        story = []
        story += self._cover(date_cn, weekday, days_left,
                             len(comments), len(news_list), total_golden)
        story += self._comments_section(comments, ai_result)
        story += self._news_section(news_list)
        # AI 板块：每日总评 → 考点（已嵌在新闻里）→ 申论素材 → 金句汇总
        if ai_result and ai_result.get("enabled"):
            story += self._ai_daily_summary(ai_result)
            story += self._ai_shenlun_material(ai_result)
        story += self._golden_summary(comments, ai_result)
        story += self._tips_section(ai_result)

        doc.build(story, canvasmaker=body_cls)
        log.info("PDF 已生成: %s", output_path)
        return True


# 避免循环引用：utils 在 config 之前 log 的定义
from .utils import log  # noqa: E402
