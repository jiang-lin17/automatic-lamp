#!/usr/bin/env python3
# -*- 编码：utf-8 -*-
"""
江西省考每日备考资料 - GitHub Actions 云端版
功能：抓取人民日报评论 + 时政热点 → 生成PDF → 推送到企业微信
"""

import os
import sys
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# ==================== 配置 ====================

WECOM_WEBHOOK = os.environ.get('WECOM_WEBHOOK', '')
EXAM_NAME = '2027年江西省考'
EXAM_DATE = datetime(2027, 3, 25)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# ==================== 日期处理 ====================

def get_target_date():
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    return yesterday

def format_date(date):
    weekdays = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
    date_str = date.strftime('%Y-%m-%d')
    date_cn = date.strftime('%Y年%m月%d日')
    weekday = weekdays[date.weekday()]
    days_left = (EXAM_DATE - date).days
    return date_str, date_cn, weekday, days_left

# ==================== 抓取人民日报评论 ====================

def fetch_people_comments(target_date):
    comments = []
    try:
        url = 'http://opinion.people.com.cn/GB/8213/49160/49219/index.html'
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = resp.apparent_encoding or 'gbk'
        soup = BeautifulSoup(resp.text, 'html.parser')
        links = soup.find_all('a', href=True)
        count = 0
        for link in links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            if '/n1/' in href and 'c461529' in href and text and len(text) > 5 and count < 3:
                full_url = 'http://opinion.people.com.cn' + href if href.startswith('/') else href
                summary = fetch_article_summary(full_url)
                comments.append({'title': text, 'column': '人民时评', 'url': full_url, 'summary': summary})
                count += 1
        url2 = 'http://opinion.people.com.cn/GB/436867/index.html'
        try:
            resp2 = requests.get(url2, headers=HEADERS, timeout=15)
            resp2.encoding = resp2.apparent_encoding or 'gbk'
            soup2 = BeautifulSoup(resp2.text, 'html.parser')
            links2 = soup2.find_all('a', href=True)
            for link in links2:
                href = link.get('href', '')
                text = link.get_text(strip=True)
                if '/n1/' in href and 'c436867' in href and text and len(text) > 5:
                    full_url = 'http://opinion.people.com.cn' + href if href.startswith('/') else href
                    summary = fetch_article_summary(full_url)
                    comments.append({'title': text, 'column': '人民锐评', 'url': full_url, 'summary': summary})
                    break
        except Exception as e:
            print(f'抓取人民锐评列表失败: {e}')
    except Exception as e:
        print(f'抓取人民时评列表失败: {e}')
    return comments[:4]

def fetch_article_summary(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = resp.apparent_encoding or 'gbk'
        soup = BeautifulSoup(resp.text, 'html.parser')
        content_div = soup.find('div', class_='rm_txt_con') or soup.find('div', id='rwb_zw') or soup.find('div', class_='article-content')
        if content_div:
            paragraphs = content_div.find_all('p')
            text = ''.join([p.get_text(strip=True) for p in paragraphs[:3] if p.get_text(strip=True)])
            if len(text) > 100:
                return text[:150] + '...'
        return '点击查看原文'
    except:
        return '点击查看原文'

# ==================== 抓取时政热点 ====================

def fetch_news(target_date):
    news_list = []
    try:
        url = 'https://www.gov.cn/yaowen.htm'
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        items = soup.find_all('li')
        for item in items[:15]:
            link = item.find('a')
            if link:
                title = link.get_text(strip=True)
                href = link.get('href', '')
                if title and len(title) > 10:
                    full_url = href if href.startswith('http') else 'https://www.gov.cn/' + href.lstrip('/')
                    news_list.append({'title': title, 'url': full_url, 'source': '中国政府网', 'category': '国内要闻'})
    except Exception as e:
        print(f'抓取中国政府网失败: {e}')
    try:
        url = 'http://politics.people.com.cn/'
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = resp.apparent_encoding or 'gbk'
        soup = BeautifulSoup(resp.text, 'html.parser')
        links = soup.find_all('a', href=True)
        for link in links[:40]:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            if title and len(title) > 12 and ('/n1/' in href or '/GB/' in href):
                full_url = 'http://politics.people.com.cn' + href if href.startswith('/') else href
                news_list.append({'title': title, 'url': full_url, 'source': '人民网', 'category': '时政要闻'})
    except Exception as e:
        print(f'抓取人民网时政失败: {e}')
    seen = set()
    unique_news = []
    for news in news_list:
        if news['title'] not in seen:
            seen.add(news['title'])
            unique_news.append(news)
    return unique_news[:12]

# ==================== 生成PDF ====================

def generate_pdf(comments, news_list, date_str, date_cn, weekday, days_left, output_path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor, white
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

    font_registered = False
    font_paths = [
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        'C:/Windows/Fonts/msyh.ttc',
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont('ChineseFont', fp))
                font_registered = True
                break
            except:
                continue

    PRIMARY = HexColor('#1a73e8')
    BG_BLUE = HexColor('#e8f0fe')
    TEXT_DARK = HexColor('#202124')
    TEXT_GRAY = HexColor('#5f6368')

    styles = getSampleStyleSheet()
    cover_title = ParagraphStyle('CoverTitle', parent=styles['Title'], fontName='ChineseFont', fontSize=26, leading=36, alignment=TA_CENTER, textColor=PRIMARY)
    cover_subtitle = ParagraphStyle('CoverSubtitle', parent=styles['Normal'], fontName='ChineseFont', fontSize=14, leading=22, alignment=TA_CENTER, textColor=TEXT_GRAY)
    cover_date = ParagraphStyle('CoverDate', parent=styles['Normal'], fontName='ChineseFont', fontSize=20, leading=30, alignment=TA_CENTER, textColor=TEXT_DARK)
    h1 = ParagraphStyle('H1', parent=styles['Heading1'], fontName='ChineseFont', fontSize=18, leading=28, textColor=PRIMARY, spaceAfter=6)
    h2 = ParagraphStyle('H2', parent=styles['Heading2'], fontName='ChineseFont', fontSize=14, leading=22, textColor=TEXT_DARK, spaceAfter=4)
    body = ParagraphStyle('Body', parent=styles['Normal'], fontName='ChineseFont', fontSize=10.5, leading=18, textColor=TEXT_DARK, firstLineIndent=21)
    bullet = ParagraphStyle('Bullet', parent=styles['Normal'], fontName='ChineseFont', fontSize=10.5, leading=18, textColor=TEXT_DARK, leftIndent=15)
    table_header = ParagraphStyle('TableHeader', parent=styles['Normal'], fontName='ChineseFont', fontSize=10, leading=16, textColor=white, alignment=TA_CENTER)
    table_cell = ParagraphStyle('TableCell', parent=styles['Normal'], fontName='ChineseFont', fontSize=9.5, leading=15, textColor=TEXT_DARK, alignment=TA_CENTER)

    doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm, title=f'江西省考每日备考资料 - {date_cn}', author='江西省考备考助手')
    story = []

    # 封面
    story.append(Spacer(1, 40*mm))
    story.append(Paragraph('📚 江西省考每日备考资料', cover_title))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph(EXAM_NAME, cover_subtitle))
    story.append(Spacer(1, 12*mm))
    story.append(Paragraph(f'{date_cn} {weekday}', cover_date))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(f'⏰ 距笔试还有 {days_left} 天', cover_subtitle))
    story.append(Spacer(1, 15*mm))

    overview_data = [
        [Paragraph('人民日报评论', table_header), Paragraph('时政热点', table_header), Paragraph('新闻来源', table_header)],
        [Paragraph(f'{len(comments)}篇', table_cell), Paragraph(f'{len(news_list)}条', table_cell), Paragraph('人民网/新华网', table_cell)],
    ]
    table = Table(overview_data, colWidths=[50*mm, 50*mm, 50*mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, -1), 'ChineseFont'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 1), (-1, 1), BG_BLUE),
        ('GRID', (0, 0), (-1, -1), 1, white),
    ]))
    story.append(table)
    story.append(Spacer(1, 25*mm))
    story.append(Paragraph('每天进步一点点，一次上岸江西 💪', cover_subtitle))
    story.append(PageBreak())

    # 人民日报评论
    story.append(Paragraph('📰 人民日报评论', h1))
    story.append(Spacer(1, 3*mm))
    for i, comment in enumerate(comments, 1):
        story.append(Paragraph(f'{i}. {comment["title"]}', h2))
        story.append(Paragraph(f'<font color="#5f6368">栏目：{comment["column"]} | <a href="{comment["url"]}" color="#1a73e8">查看原文</a></font>', bullet))
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(comment['summary'], body))
        story.append(Spacer(1, 4*mm))
    story.append(PageBreak())

    # 时政热点
    story.append(Paragraph('🔔 时政热点', h1))
    story.append(Spacer(1, 3*mm))
    categories = {}
    for news in news_list:
        cat = news['category']
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(news)
    for cat, items in categories.items():
        story.append(Paragraph(f'▸ {cat}', h2))
        story.append(Spacer(1, 2*mm))
        for j, news in enumerate(items, 1):
            story.append(Paragraph(f'{j}. {news["title"]}', bullet))
            story.append(Paragraph(f'<font color="#5f6368" size=9>来源：{news["source"]} | <a href="{news["url"]}" color="#1a73e8">查看原文</a></font>', bullet))
            story.append(Spacer(1, 2*mm))
        story.append(Spacer(1, 3*mm))
    story.append(PageBreak())

    # 学习小贴士
    story.append(Paragraph('💡 每日学习小贴士', h1))
    story.append(Spacer(1, 5*mm))
    tips = [
        '1. 精读2篇人民日报评论，摘抄金句，分析论证结构',
        '2. 浏览时政新闻，标注可能的考点（数字、会议、政策）',
        '3. 结合热点话题思考申论写作角度（是什么/为什么/怎么办）',
        '4. 每天积累3-5个金句，写作时可以直接使用',
        '5. 重要纪念日和数字类考点要重点记忆',
    ]
    for tip in tips:
        story.append(Paragraph(tip, bullet))
        story.append(Spacer(1, 3*mm))
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph('---', body))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(f'<font color="#5f6368" size=9>本资料由 GitHub Actions 自动生成 | 数据来源：人民网、新华网、中国政府网</font>', bullet))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(f'<font color="#5f6368" size=9>生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</font>', bullet))

    doc.build(story)
    print(f'PDF生成成功: {output_path}')
    return True

# ==================== 推送到企业微信 ====================

def send_wecom_text(content):
    if not WECOM_WEBHOOK:
        print('未配置 WECOM_WEBHOOK，跳过推送')
        return False
    try:
        data = {'msgtype': 'markdown', 'markdown': {'content': content}}
        resp = requests.post(WECOM_WEBHOOK, json=data, timeout=10)
        result = resp.json()
        如果结果.获取('errcode') == 0:
            print('文字消息推送成功')
            return True
        else:
            print(f'文字消息推送失败: {result}')
            return False
    except Exception as e:
        print(f'文字消息推送异常: {e}')
        return False

def send_wecom_file(file_path):
    if not WECOM_WEBHOOK:
        print('未配置 WECOM_WEBHOOK，跳过推送')
        return False
    try:
        key = WECOM_WEBHOOK.split('key=')[-1] if 'key=' in WECOM_WEBHOOK else ''
        if not key:
            print('无法提取 webhook key')
            return False
        upload_url = f'https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key={key}&type=file'
        with open(file_path, 'rb') as f:
            files = {'media': (os.path.basename(file_path), f)}
            resp = requests.post(upload_url, files=files, timeout=30)
            result = resp.json()
        如果结果.获取('errcode') == 0:
            media_id = 结果.获取('media_id')
            data = {'msgtype': 'file', 'file': {'media_id': media_id}}
            resp2 = requests.post(WECOM_WEBHOOK, json=data, timeout=10)
            result2 = resp2.json()
            if result2.get('errcode') == 0:
                print('文件推送成功')
                return True
            else:
                print(f'文件推送失败: {result2}')
                return False
        else:
            print(f'文件上传失败: {result}')
            return False
    except Exception as e:
        print(f'文件推送异常: {e}')
        return False

# ==================== 主函数 ====================

def main():
    print('=' * 50)
    print('江西省考每日备考资料 - 云端版')
    print('=' * 50)

    target_date = get_target_date()
    date_str, date_cn, weekday, days_left = format_date(target_date)
    print(f'\n目标日期: {date_cn} {weekday}')
    print(f'距{EXAM_NAME}笔试还有 {days_left} 天')

    output_dir = './output'
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, f'每日备考资料_{date_str}.pdf')

    print('\n[1/4] 抓取人民日报评论...')
    comments = fetch_people_comments(target_date)
    print(f'  抓取到 {len(comments)} 篇评论')
    用于C的注释：
        print(f'    - [{c["column"]}] {c["title"][:30]}')

    print('\n[2/4] 抓取时政热点...')
    news_list = fetch_news(target_date)
    print(f'  抓取到 {len(news_list)} 条新闻')
    for n in news_list[:5]:
        打印(f'    - {n["title"][:30]}...')

    print('\n[3/4] 生成PDF...')
    success = generate_pdf(comments, news_list, date_str, date_cn, weekday, days_left, pdf_path)
    if not success:
        打印('PDF生成失败!')
        sys.exit(1)
    file_size = os.path.getsize(pdf_path)
    print(f'  PDF大小: {file_size/1024:.1f} KB')

    print('\n[4/4] 推送到企业微信...')
    text_content = f"""## 📚 江西省考每日备考资料 - {date_cn} {weekday}

⏰ 距{EXAM_NAME}笔试还有 **{days_left}** 天

---

### 📰 今日内容

- **人民日报评论**：{len(comments)}篇精选
- **时政热点**：{len(news_list)}条重要新闻
- **学习建议**：精读评论 + 浏览热点 + 金句积累

---

### 💡 今日学习建议

1. 精读2篇人民日报评论，摘抄金句
2. 浏览时政新闻，标注考点（数字/会议/政策）
3. 结合热点思考申论写作角度
4. 积累3-5个金句

---

### 今日PDF已发送，请查收附件

内容包含：人民日报评论、时政热点、学习小贴士

---

> 💪 每天进步一点点，一次上岸江西！
"""
    send_wecom_text(text_content)
    send_wecom_file(pdf_path)

    print('\n' + '=' * 50)
    print('全部完成!')
    print('=' * 50)

if __name__ == '__main__':
    ()
