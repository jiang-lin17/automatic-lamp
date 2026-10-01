"""PDF 生成模块：负责把抓取到的评论、新闻渲染成一份精美的 A4 报告。"""

import os
from datetime import datetime
from typing import List, Dict, Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER

from .config import FONT_CANDIDATES, ExamConfig, ContentThresholds
from .utils import log


class ReportBuilder:
    """江西省考每日备考资料 PDF 构建器。"""

    # —— 颜色 ——
    PRIMARY = HexColor("#1a73e8")
    BG_BLUE = HexColor("#e8f0fe")
    TEXT_DARK = HexColor("#202124")
    TEXT_GRAY = HexColor("#5f6368")
    ACCENT = HexColor("#e65100")
    QUOTE_BG = HexColor("#f3f4f6")

    def __init__(self, exam_cfg: ExamConfig | None = None):
        self.exam_cfg = exam_cfg or ExamConfig()
        self.font_name = self._register_font()
        self.styles = self._build_styles()

    # ========== 初始化 ==========
    def _register_font(self) -> str:
        for fp in FONT_CANDIDATES:
            if os.path.exists(fp):
                try:
                    pdfmetrics.registerFont(TTFont("CN", fp))
                    log.info("使用字体: %s", fp)
                    return "CN"
                except Exception as e:
                    log.debug("字体 %s 注册失败: %s", fp, e)
        log.warning("未找到中文字体，回退到默认字体（可能导致中文乱码）")
        return "Helvetica"

    def _build_styles(self) -> Dict[str, ParagraphStyle]:
        fn = self.font_name
        base = getSampleStyleSheet()
        return {
            "ct": ParagraphStyle("ct", parent=base["Title"],
                                 fontName=fn, fontSize=26, leading=36,
                                 alignment=TA_CENTER, textColor=self.PRIMARY),
            "cs": ParagraphStyle("cs", parent=base["Normal"],
                                 fontName=fn, fontSize=14, leading=22,
                                 alignment=TA_CENTER, textColor=self.TEXT_GRAY),
            "cd": ParagraphStyle("cd", parent=base["Normal"],
                                 fontName=fn, fontSize=20, leading=30,
                                 alignment=TA_CENTER, textColor=self.TEXT_DARK),
            "h1": ParagraphStyle("h1", parent=base["Heading1"],
                                 fontName=fn, fontSize=18, leading=28,
                                 textColor=self.PRIMARY, spaceAfter=6),
            "h2": ParagraphStyle("h2", parent=base["Heading2"],
                                 fontName=fn, fontSize=14, leading=22,
                                 textColor=self.TEXT_DARK, spaceAfter=4),
            "h3": ParagraphStyle("h3", parent=base["Heading3"],
                                 fontName=fn, fontSize=12, leading=18,
                                 textColor=self.PRIMARY, spaceAfter=3),
            "bd": ParagraphStyle("bd", parent=base["Normal"],
                                 fontName=fn, fontSize=10.5, leading=18,
                                 textColor=self.TEXT_DARK, firstLineIndent=21),
            "bdn": ParagraphStyle("bdn", parent=base["Normal"],
                                  fontName=fn, fontSize=10.5, leading=18,
                                  textColor=self.TEXT_DARK),
            "bl": ParagraphStyle("bl", parent=base["Normal"],
                                 fontName=fn, fontSize=10.5, leading=18,
                                 textColor=self.TEXT_DARK, leftIndent=15),
            "qt": ParagraphStyle("qt", parent=base["Normal"],
                                 fontName=fn, fontSize=10, leading=17,
                                 textColor=self.ACCENT, leftIndent=20, rightIndent=10,
                                 backColor=self.QUOTE_BG, borderPadding=5),
            "th": ParagraphStyle("th", parent=base["Normal"],
                                 fontName=fn, fontSize=10, leading=16,
                                 textColor=white, alignment=TA_CENTER),
            "td": ParagraphStyle("td", parent=base["Normal"],
                                 fontName=fn, fontSize=9.5, leading=15,
                                 textColor=self.TEXT_DARK, alignment=TA_CENTER),
            "mt": ParagraphStyle("mt", parent=base["Normal"],
                                 fontName=fn, fontSize=9, leading=14,
                                 textColor=self.TEXT_GRAY),
        }

    # ========== 渲染部件 ==========
    def _cover(self, date_cn: str, weekday: str, days_left: int,
               comments_count: int, news_count: int, golden_count: int):
        s = self.styles
        story = []
        story.append(Spacer(1, 35 * mm))
        story.append(Paragraph(f"📚 {self.exam_cfg.pdf_title}", s["ct"]))
        story.append(Spacer(1, 5 * mm))
        story.append(Paragraph(self.exam_cfg.name, s["cs"]))
        story.append(Spacer(1, 10 * mm))
        story.append(Paragraph(f"{date_cn} {weekday}", s["cd"]))
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(f"⏰ 距笔试还有 {days_left} 天", s["cs"]))
        story.append(Spacer(1, 12 * mm))

        ov_data = [
            [Paragraph("人民日报评论", s["th"]),
             Paragraph("时政新闻", s["th"]),
             Paragraph("金句摘录", s["th"])],
            [Paragraph(f"{comments_count}篇", s["td"]),
             Paragraph(f"{news_count}条", s["td"]),
             Paragraph(f"{golden_count}句", s["td"])],
        ]
        t = Table(ov_data, colWidths=[50 * mm, 50 * mm, 50 * mm])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), self.PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), white),
            ("FONTNAME", (0, 0), (-1, -1), self.font_name),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("BACKGROUND", (0, 1), (-1, 1), self.BG_BLUE),
            ("GRID", (0, 0), (-1, -1), 1, white),
        ]))
        story.append(t)
        story.append(Spacer(1, 20 * mm))
        story.append(Paragraph("每天进步一点点，一次上岸江西 💪", s["cs"]))
        story.append(PageBreak())
        return story

    def _comments_section(self, comments: List[Dict[str, Any]]):
        s = self.styles
        thresholds = ContentThresholds()
        story = []
        story.append(Paragraph("📰 人民日报评论", s["h1"]))
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph("精选当日人民时评、人民锐评，全文呈现", s["mt"]))
        story.append(Spacer(1, 4 * mm))

        for i, c in enumerate(comments, 1):
            story.append(Paragraph(f"{i}. {c['title']}", s["h2"]))
            author_info = f" | 作者：{c['author']}" if c["author"] else ""
            meta_html = (
                f"栏目：{c['column']}{author_info} | "
                f'<a href="{c["url"]}" color="#1a73e8">查看原文</a>'
            )
            story.append(Paragraph(meta_html, s["mt"]))
            story.append(Spacer(1, 2 * mm))

            if c["content"]:
                max_paras = min(len(c["content"]), thresholds.max_paragraphs_per_comment)
                for para in c["content"][:max_paras]:
                    story.append(Paragraph(para, s["bd"]))
                if len(c["content"]) > max_paras:
                    story.append(Paragraph("...（剩余内容请查看原文）", s["mt"]))
            else:
                story.append(Paragraph(c["summary"], s["bd"]))

            if c["golden"]:
                story.append(Spacer(1, 3 * mm))
                story.append(Paragraph("💡 金句摘录", s["h3"]))
                for gs in c["golden"][:thresholds.golden_per_article]:
                    story.append(Paragraph(f"\u201c{gs}\u201d", s["qt"]))
                    story.append(Spacer(1, 1 * mm))

            story.append(Spacer(1, 5 * mm))

        story.append(PageBreak())
        return story

    def _news_section(self, news_list: List[Dict[str, Any]]):
        s = self.styles
        story = []
        story.append(Paragraph("🔔 时政热点", s["h1"]))
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(
            "当日重要时政新闻汇总，来源：新华网、人民网、中国政府网", s["mt"]))
        story.append(Spacer(1, 4 * mm))

        # 按分类聚合
        cats: Dict[str, List[Dict[str, Any]]] = {}
        for n in news_list:
            cats.setdefault(n["category"], []).append(n)

        for cat, items in cats.items():
            story.append(Paragraph(f"▸ {cat}", s["h2"]))
            story.append(Spacer(1, 2 * mm))
            for j, n in enumerate(items, 1):
                story.append(Paragraph(f"{j}. {n['title']}", s["bdn"]))
                # 直接显示完整网址（可点击超链接）
                meta_html = (
                    f'<font color="#5f6368" size=9>来源：{n["source"]}</font>'
                )
                link_html = (
                    f'<a href="{n["url"]}" color="#1a73e8">'
                    f'<font size=8>{n["url"]}</font></a>'
                )
                story.append(Paragraph(meta_html, s["mt"]))
                story.append(Paragraph(link_html, s["mt"]))
                if n.get("summary"):
                    story.append(Paragraph(
                        f'<font color="#5f6368" size=9>摘要：{n["summary"]}</font>', s["mt"]))
                story.append(Spacer(1, 2 * mm))
            story.append(Spacer(1, 3 * mm))

        story.append(PageBreak())
        return story

    def _golden_section(self, comments: List[Dict[str, Any]]):
        s = self.styles
        thresholds = ContentThresholds()
        story = []
        story.append(Paragraph("📬 申论金句积累", s["h1"]))
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph("从当日评论文章中摘录的精彩语句", s["mt"]))
        story.append(Spacer(1, 4 * mm))

        all_golden: List[str] = []
        for c in comments:
            all_golden.extend(c.get("golden", []))

        if all_golden:
            for idx, gs in enumerate(all_golden[:thresholds.golden_summary_max], 1):
                story.append(Paragraph(f"{idx}. \u201c{gs}\u201d", s["qt"]))
                story.append(Spacer(1, 2 * mm))
        else:
            story.append(Paragraph(
                "今日金句待积累（建议阅读评论文章自行摘抄）", s["bd"]))
        return story

    def _tips_section(self):
        s = self.styles
        story = []
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph("💡 学习小贴士", s["h1"]))
        story.append(Spacer(1, 3 * mm))
        tips = [
            "1. 精读2篇人民日报评论，注意文章结构和论证方法",
            "2. 摘抄3-5个金句，尝试用在申论写作中",
            "3. 时政新闻中注意数字类、会议类、政策类考点",
            "4. 结合热点思考申论作文的立意和分论点",
            "5. 每天坚持阅读，培养官方语感和政策思维",
        ]
        for tip in tips:
            story.append(Paragraph(tip, s["bl"]))
            story.append(Spacer(1, 2 * mm))
        return story

    def _footer(self):
        s = self.styles
        story = []
        story.append(Spacer(1, 10 * mm))
        story.append(Paragraph("---", s["bd"]))
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph(
            '<font color="#5f6368" size=8>'
            f"本资料由 GitHub Actions 自动生成 | "
            f"数据来源：人民网、新华网、中国政府网</font>",
            s["mt"],
        ))
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(
            f'<font color="#5f6368" size=8>生成时间：'
            f'{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</font>',
            s["mt"],
        ))
        return story

    # ========== 入口 ==========
    def build(self, comments: List[Dict[str, Any]],
              news_list: List[Dict[str, Any]],
              date_str: str, date_cn: str, weekday: str,
              days_left: int, output_path: str) -> bool:
        """生成 PDF 文件。"""
        # 精确统计金句数量（之前的 bug 是用 len(comments)*3 粗略估算）
        total_golden = sum(len(c.get("golden", [])) for c in comments)

        doc = SimpleDocTemplate(
            output_path, pagesize=A4,
            leftMargin=18 * mm, rightMargin=18 * mm,
            topMargin=18 * mm, bottomMargin=18 * mm,
            title=self.exam_cfg.pdf_title,
            author="GK Helper",
        )
        story = []
        story += self._cover(date_cn, weekday, days_left,
                             len(comments), len(news_list), total_golden)
        story += self._comments_section(comments)
        story += self._news_section(news_list)
        story += self._golden_section(comments)
        story += self._tips_section()
        story += self._footer()

        doc.build(story)
        log.info("PDF 已生成: %s", output_path)
        return True
