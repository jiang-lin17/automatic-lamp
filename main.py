#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

WECOM_WEBHOOK = os.environ.get('WECOM_WEBHOOK', '')
EXAM_NAME = '2027年江西省考'
EXAM_DATE = datetime(2027, 3, 25)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

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

def fetch_comments():
    comments = []
    try:
        url = 'http://opinion.people.com.cn/GB/8213/49160/49219/index.html'
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = resp.apparent_encoding or 'gbk'
        soup = BeautifulSoup(resp.text, 'html.parser')
        count = 0
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            text = link.get_text(strip=True)
            if '/n1/' in href and 'c461529' in href and text and len(text) > 5 and count < 3:
                full_url = 'http://opinion.people.com.cn' + href if href.startswith('/') else href
                comments.append({'title': text, 'column': '人民时评', 'url': full_url, 'summary': fetch_summary(full_url)})
                count += 1
        try:
            url2 = 'http://opinion.people.com.cn/GB/436867/index.html'
            resp2 = requests.get(url2, headers=HEADERS, timeout=15)
            resp2.encoding = resp2.apparent_encoding or 'gbk'
            soup2 = BeautifulSoup(resp2.text, 'html.parser')
            for link in soup2.find_all('a', href=True):
                href = link.get('href', '')
                text = link.get_text(strip=True)
                if '/n1/' in href and 'c436867' in href and text and len(text) > 5:
                    full_url = 'http://opinion.people.com.cn' + href if href.startswith('/') else href
                    comments.append({'title': text, 'column': '人民锐评', 'url': full_url, 'summary': fetch_summary(full_url)})
                    break
        except Exception as e:
            print('fail ruiping: ' + str(e))
    except Exception as e:
        print('fail shiping: ' + str(e))
    return comments[:4]

def fetch_summary(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = resp.apparent_encoding or 'gbk'
        soup = BeautifulSoup(resp.text, 'html.parser')
        div = soup.find('div', class_='rm_txt_con') or soup.find('div', id='rwb_zw')
        if div:
            ps = div.find_all('p')
            text = ''.join([p.get_text(strip=True) for p in ps[:3] if p.get_text(strip=True)])
            if len(text) > 100:
                return text[:150] + '...'
        return '点击查看原文'
    except:
        return '点击查看原文'

def fetch_news():
    news_list = []
    try:
        url = 'http://politics.people.com.cn/'
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = resp.apparent_encoding or 'gbk'
        soup = BeautifulSoup(resp.text, 'html.parser')
        for link in soup.find_all('a', href=True)[:40]:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            if title and len(title) > 12 and '/n1/' in href:
                full_url = 'http://politics.people.com.cn' + href if href.startswith('/') else href
                news_list.append({'title': title, 'url': full_url, 'source': '人民网', 'category': '时政要闻'})
    except Exception as e:
        print('fail news: ' + str(e))
    seen = set()
    unique = []
    for n in news_list:
        if n['title'] not in seen:
            seen.add(n['title'])
            unique.append(n)
    return unique[:12]

def generate_pdf(comments, news_list, date_str, date_cn, weekday, days_left, output_path):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.lib.colors import HexColor, white
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.enums import TA_CENTER

    font_ok = False
    for fp in ['/usr/share/fonts/truetype/wqy/wqy-microhei.ttc', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', 'C:/Windows/Fonts/msyh.ttc']:
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont('CN', fp))
                font_ok = True
                break
            except:
                continue

    PRIMARY = HexColor('#1a73e8')
    BG_BLUE = HexColor('#e8f0fe')
    TEXT_DARK = HexColor('#202124')
    TEXT_GRAY = HexColor('#5f6368')

    styles = getSampleStyleSheet()
    s_cover_title = ParagraphStyle('ct', parent=styles['Title'], fontName='CN', fontSize=26, leading=36, alignment=TA_CENTER, textColor=PRIMARY)
    s_cover_sub = ParagraphStyle('cs', parent=styles['Normal'], fontName='CN', fontSize=14, leading=22, alignment=TA_CENTER, textColor=TEXT_GRAY)
    s_cover_date = ParagraphStyle('cd', parent=styles['Normal'], fontName='CN', fontSize=20, leading=30, alignment=TA_CENTER, textColor=TEXT_DARK)
    s_h1 = ParagraphStyle('h1', parent=styles['Heading1'], fontName='CN', fontSize=18, leading=28, textColor=PRIMARY, spaceAfter=6)
    s_h2 = ParagraphStyle('h2', parent=styles['Heading2'], fontName='CN', fontSize=14, leading=22, textColor=TEXT_DARK, spaceAfter=4)
    s_body = ParagraphStyle('bd', parent=styles['Normal'], fontName='CN', fontSize=10.5, leading=18, textColor=TEXT_DARK, firstLineIndent=21)
    s_bullet = ParagraphStyle('bl', parent=styles['Normal'], fontName='CN', fontSize=10.5, leading=18, textColor=TEXT_DARK, leftIndent=15)
    s_th = ParagraphStyle('th', parent=styles['Normal'], fontName='CN', fontSize=10, leading=16, textColor=white, alignment=TA_CENTER)
    s_td = ParagraphStyle('td', parent=styles['Normal'], fontName='CN', fontSize=9.5, leading=15, textColor=TEXT_DARK, alignment=TA_CENTER)

    doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm, title='JiangxiGK Daily', author='GK Helper')
    story = []

    story.append(Spacer(1, 40*mm))
    story.append(Paragraph('江西省考每日备考资料', s_cover_title))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph(EXAM_NAME, s_cover_sub))
    story.append(Spacer(1, 12*mm))
    story.append(Paragraph(date_cn + ' ' + weekday, s_cover_date))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph('距笔试还有 ' + str(days_left) + ' 天', s_cover_sub))
    story.append(Spacer(1, 15*mm))

    ov = [
        [Paragraph('人民日报评论', s_th), Paragraph('时政热点', s_th), Paragraph('新闻来源', s_th)],
        [Paragraph(str(len(comments)) + '篇', s_td), Paragraph(str(len(news_list)) + '条', s_td), Paragraph('人民网/新华网', s_td)],
    ]
    t = Table(ov, colWidths=[50*mm, 50*mm, 50*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, -1), 'CN'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 1), (-1, 1), BG_BLUE),
        ('GRID', (0, 0), (-1, -1), 1, white),
    ]))
    story.append(t)
    story.append(Spacer(1, 25*mm))
    story.append(Paragraph('每天进步一点点，一次上岸江西', s_cover_sub))
    story.append(PageBreak())

    story.append(Paragraph('一、人民日报评论', s_h1))
    story.append(Spacer(1, 3*mm))
    for i, c in enumerate(comments, 1):
        story.append(Paragraph(str(i) + '. ' + c['title'], s_h2))
        story.append(Paragraph('<font color="#5f6368">栏目：' + c['column'] + ' | <a href="' + c['url'] + '" color="#1a73e8">查看原文</a></font>', s_bullet))
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(c['summary'], s_body))
        story.append(Spacer(1, 4*mm))
    story.append(PageBreak())

    story.append(Paragraph('二、时政热点', s_h1))
    story.append(Spacer(1, 3*mm))
    cats = {}
    for n in news_list:
        cat = n['category']
        if cat not in cats:
            cats[cat] = []
        cats[cat].append(n)
    for cat, items in cats.items():
        story.append(Paragraph(cat, s_h2))
        story.append(Spacer(1, 2*mm))
        for j, n in enumerate(items, 1):
            story.append(Paragraph(str(j) + '. ' + n['title'], s_bullet))
            story.append(Paragraph('<font color="#5f6368" size=9>来源：' + n['source'] + ' | <a href="' + n['url'] + '" color="#1a73e8">查看原文</a></font>', s_bullet))
            story.append(Spacer(1, 2*mm))
        story.append(Spacer(1, 3*mm))
    story.append(PageBreak())

    story.append(Paragraph('三、学习小贴士', s_h1))
    story.append(Spacer(1, 5*mm))
    tips = [
        '1. 精读2篇人民日报评论，摘抄金句，分析论证结构',
        '2. 浏览时政新闻，标注可能的考点（数字、会议、政策）',
        '3. 结合热点话题思考申论写作角度（是什么/为什么/怎么办）',
        '4. 每天积累3-5个金句，写作时可以直接使用',
        '5. 重要纪念日和数字类考点要重点记忆',
    ]
    for tip in tips:
        story.append(Paragraph(tip, s_bullet))
        story.append(Spacer(1, 3*mm))
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph('---', s_body))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph('<font color="#5f6368" size=9>本资料由 GitHub Actions 自动生成 | 数据来源：人民网、中国政府网</font>', s_bullet))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph('<font color="#5f6368" size=9>生成时间：' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '</font>', s_bullet))

    doc.build(story)
    print('PDF OK: ' + output_path)
    return True

def send_text(content):
    if not WECOM_WEBHOOK:
        print('no webhook, skip')
        return False
    try:
        data = {'msgtype': 'markdown', 'markdown': {'content': content}}
        r = requests.post(WECOM_WEBHOOK, json=data, timeout=10)
        res = r.json()
        if res.get('errcode') == 0:
            print('text ok')
            return True
        else:
            print('text fail: ' + str(res))
            return False
    except Exception as e:
        print('text error: ' + str(e))
        return False

def send_file(file_path):
    if not WECOM_WEBHOOK:
        print('no webhook, skip')
        return False
    try:
        key = WECOM_WEBHOOK.split('key=')[-1] if 'key=' in WECOM_WEBHOOK else ''
        if not key:
            print('no key')
            return False
        upload_url = 'https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key=' + key + '&type=file'
        with open(file_path, 'rb') as f:
            files = {'media': (os.path.basename(file_path), f)}
            r = requests.post(upload_url, files=files, timeout=30)
            res = r.json()
        if res.get('errcode') == 0:
            mid = res.get('media_id')
            data = {'msgtype': 'file', 'file': {'media_id': mid}}
            r2 = requests.post(WECOM_WEBHOOK, json=data, timeout=10)
            res2 = r2.json()
            if res2.get('errcode') == 0:
                print('file ok')
                return True
            else:
                print('file fail: ' + str(res2))
                return False
        else:
            print('upload fail: ' + str(res))
            return False
    except Exception as e:
        print('file error: ' + str(e))
        return False

def main():
    print('=' * 40)
    print('JiangxiGK Daily Report')
    print('=' * 40)

    target_date = get_target_date()
    date_str, date_cn, weekday, days_left = format_date(target_date)
    print('Date: ' + date_cn + ' ' + weekday)
    print('Days left: ' + str(days_left))

    os.makedirs('./output', exist_ok=True)
    pdf_path = './output/每日备考资料_' + date_str + '.pdf'

    print('\n[1/4] Fetch comments...')
    comments = fetch_comments()
    print('  Got ' + str(len(comments)) + ' comments')
    for c in comments:
        print('    - ' + c['title'][:30])

    print('\n[2/4] Fetch news...')
    news_list = fetch_news()
    print('  Got ' + str(len(news_list)) + ' news')
    for n in news_list[:5]:
        print('    - ' + n['title'][:30])

    print('\n[3/4] Generate PDF...')
    ok = generate_pdf(comments, news_list, date_str, date_cn, weekday, days_left, pdf_path)
    if not ok:
        print('PDF failed!')
        sys.exit(1)
    fsize = os.path.getsize(pdf_path)
    print('  Size: ' + str(fsize/1024) + ' KB')

    print('\n[4/4] 推送到企业微信...')
    md = '## 江西省考每日备考资料 - ' + date_cn + ' ' + weekday + '\n\n'
    md += '距' + EXAM_NAME + '笔试还有 **' + str(days_left) + '** 天\n\n'
    md += '---\n\n'
    md += '### 今日内容\n\n'
    md += '- 人民日报评论：' + str(len(comments)) + '篇精选\n'
    md += '- 时政热点：' + str(len(news_list)) + '条重要新闻\n\n'
    md += '---\n\n'
    md += '### 学习建议\n\n'
    md += '1. 精读2篇人民日报评论，摘抄金句\n'
    md += '2. 浏览时政新闻，标注考点\n'
    md += '3. 结合热点思考申论写作角度\n\n'
    md += '---\n\n'
    md += 'PDF已发送，请查收附件。\n\n'
    md += '> 每天进步一点点，一次上岸江西！\n'

    send_text(md)
    send_file(pdf_path)

    print('\n' + '=' * 40)
    print('All done!')
    print('=' * 40)

if __name__ == '__main__':
    main()
