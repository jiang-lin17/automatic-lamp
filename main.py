#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

WECOM_WEBHOOK = os.environ.get('WECOM_WEBHOOK', '')
EXAM_NAME = '2027\x5e74\x6c5f\x897f\x7701\x8003'
EXAM_DATE = datetime(2027, 3, 25)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive'
}

def get_target_date():
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    return yesterday

def format_date(date):
    weekdays = ['\u661f\u671f\u4e00', '\u661f\u671f\u4e8c', '\u661f\u671f\u4e09', '\u661f\u671f\u56db', '\u661f\u671f\u4e94', '\u661f\u671f\u516d', '\u661f\u671f\u65e5']
    date_str = date.strftime('%Y-%m-%d')
    date_cn = date.strftime('%Y\u5e74%m\u6708%d\u65e5')
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
                article = fetch_article_full(full_url, 'gbk')
                comments.append({
                    'title': text,
                    'column': '\u4eba\u6c11\u65f6\u8bc4',
                    'url': full_url,
                    'summary': article['summary'],
                    'content': article['content'],
                    'author': article['author'],
                    'golden': article['golden']
                })
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
                    article = fetch_article_full(full_url, 'gbk')
                    comments.append({
                        'title': text,
                        'column': '\u4eba\u6c11\u9510\u8bc4',
                        'url': full_url,
                        'summary': article['summary'],
                        'content': article['content'],
                        'author': article['author'],
                        'golden': article['golden']
                    })
                    break
        except Exception as e:
            print('fail ruiping: ' + str(e))
    except Exception as e:
        print('fail shiping: ' + str(e))
    return comments[:4]

def fetch_article_full(url, encoding='utf-8'):
    result = {'summary': '', 'content': [], 'author': '', 'golden': []}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.encoding = resp.apparent_encoding or encoding
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        author_div = soup.find('div', class_='author') or soup.find('div', class_='rm_txt_con_author') or soup.find('div', class_='info')
        if author_div:
            result['author'] = author_div.get_text(strip=True)[:50]
        
        content_div = (soup.find('div', class_='rm_txt_con') or 
                       soup.find('div', id='rwb_zw') or 
                       soup.find('div', class_='article-content') or
                       soup.find('div', id='detailContent') or
                       soup.find('div', class_='content'))
        if content_div:
            paragraphs = []
            for p in content_div.find_all('p'):
                text = p.get_text(strip=True)
                if text and len(text) > 10:
                    paragraphs.append(text)
            
            result['content'] = paragraphs
            if len(paragraphs) > 2:
                first = paragraphs[0]
                result['summary'] = first[:150] + '...' if len(first) > 150 else first
            
            for p in paragraphs:
                if len(p) < 100 and ('\u201c' in p or '\u201d' in p or '"' in p):
                    result['golden'].append(p.strip())
                if len(result['golden']) >= 5:
                    break
        
        if not result['summary']:
            result['summary'] = '\u70b9\u51fb\u67e5\u770b\u539f\u6587'
            
    except Exception as e:
        result['summary'] = '\u70b9\u51fb\u67e5\u770b\u539f\u6587'
        print('fetch article error: ' + str(e))
    
    return result

def fetch_news():
    news_list = []
    
    # Source 1: 新华网时政
    print('  [source 1] xinhuanet politics...')
    try:
        url = 'http://www.xinhuanet.com/politics/'
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = resp.apparent_encoding or 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        links = soup.find_all('a', href=True)
        count = 0
        for link in links:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            if (title and len(title) > 15 and 
                ('news.cn' in href or 'xinhuanet.com' in href) and
                '/politics/' in href and
                ('.htm' in href or '.html' in href) and
                'index' not in href):
                full_url = href if href.startswith('http') else 'http://www.xinhuanet.com' + href
                summary = fetch_news_summary(full_url, 'utf-8')
                news_list.append({
                    'title': title,
                    'url': full_url,
                    'source': '\u65b0\u534e\u7f51',
                    'category': '\u65f6\u653f\u8981\u95fb',
                    'summary': summary
                })
                count += 1
                if count >= 8:
                    break
        print('    got ' + str(count) + ' items')
    except Exception as e:
        print('    xinhuanet fail: ' + str(e))
    
    # Source 2: 人民网时政新闻（备用，可能403）
    print('  [source 2] people politics...')
    try:
        url = 'http://politics.people.com.cn/GB/1024/index.html'
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            resp.encoding = resp.apparent_encoding or 'gbk'
            soup = BeautifulSoup(resp.text, 'html.parser')
            count = 0
            for link in soup.find_all('a', href=True):
                title = link.get_text(strip=True)
                href = link.get('href', '')
                if title and len(title) > 12 and '/n1/' in href:
                    full_url = 'http://politics.people.com.cn' + href if href.startswith('/') else href
                    summary = fetch_news_summary(full_url, 'gbk')
                    news_list.append({
                        'title': title,
                        'url': full_url,
                        'source': '\u4eba\u6c11\u7f51',
                        'category': '\u65f6\u653f\u8981\u95fb',
                        'summary': summary
                    })
                    count += 1
                    if count >= 5:
                        break
            print('    got ' + str(count) + ' items')
        else:
            print('    status ' + str(resp.status_code) + ', skip')
    except Exception as e:
        print('    people fail: ' + str(e))
    
    # Source 3: 中国政府网
    print('  [source 3] gov.cn...')
    try:
        url = 'https://www.gov.cn/yaowen/'
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = soup.find_all('li')
            count = 0
            for item in items[:30]:
                link = item.find('a')
                if link:
                    title = link.get_text(strip=True)
                    href = link.get('href', '')
                    if title and len(title) > 10 and '.htm' in href:
                        full_url = href if href.startswith('http') else 'https://www.gov.cn' + href
                        news_list.append({
                            'title': title,
                            'url': full_url,
                            'source': '\u4e2d\u56fd\u653f\u5e9c\u7f51',
                            'category': '\u56fd\u5185\u8981\u95fb',
                            'summary': ''
                        })
                        count += 1
                        if count >= 5:
                            break
            print('    got ' + str(count) + ' items')
        else:
            print('    status ' + str(resp.status_code) + ', skip')
    except Exception as e:
        print('    gov fail: ' + str(e))
    
    # Source 4: 新华网要闻
    print('  [source 4] xinhuanet head...')
    try:
        url = 'http://www.news.cn/'
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = resp.apparent_encoding or 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        links = soup.find_all('a', href=True)
        count = 0
        for link in links:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            if (title and len(title) > 18 and 
                'news.cn' in href and
                ('/202609' in href or '/202610' in href) and
                ('.htm' in href or '.html' in href)):
                full_url = href if href.startswith('http') else href
                news_list.append({
                    'title': title,
                    'url': full_url,
                    'source': '\u65b0\u534e\u7f51',
                    'category': '\u56fd\u5185\u8981\u95fb',
                    'summary': ''
                })
                count += 1
                if count >= 5:
                    break
        print('    got ' + str(count) + ' items')
    except Exception as e:
        print('    news.cn fail: ' + str(e))
    
    # Remove duplicates
    seen = set()
    unique = []
    for n in news_list:
        if n['title'] not in seen:
            seen.add(n['title'])
            unique.append(n)
    return unique[:15]

def fetch_news_summary(url, encoding='utf-8'):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.encoding = resp.apparent_encoding or encoding
        soup = BeautifulSoup(resp.text, 'html.parser')
        content_div = (soup.find('div', class_='rm_txt_con') or 
                       soup.find('div', id='rwb_zw') or
                       soup.find('div', id='detailContent') or
                       soup.find('div', class_='content'))
        if content_div:
            ps = content_div.find_all('p')
            for p in ps:
                text = p.get_text(strip=True)
                if text and len(text) > 50:
                    return text[:120] + '...'
        return ''
    except:
        return ''

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
    ACCENT = HexColor('#e65100')
    QUOTE_BG = HexColor('#f3f4f6')

    styles = getSampleStyleSheet()
    s_ct = ParagraphStyle('ct', parent=styles['Title'], fontName='CN', fontSize=26, leading=36, alignment=TA_CENTER, textColor=PRIMARY)
    s_cs = ParagraphStyle('cs', parent=styles['Normal'], fontName='CN', fontSize=14, leading=22, alignment=TA_CENTER, textColor=TEXT_GRAY)
    s_cd = ParagraphStyle('cd', parent=styles['Normal'], fontName='CN', fontSize=20, leading=30, alignment=TA_CENTER, textColor=TEXT_DARK)
    s_h1 = ParagraphStyle('h1', parent=styles['Heading1'], fontName='CN', fontSize=18, leading=28, textColor=PRIMARY, spaceAfter=6)
    s_h2 = ParagraphStyle('h2', parent=styles['Heading2'], fontName='CN', fontSize=14, leading=22, textColor=TEXT_DARK, spaceAfter=4)
    s_h3 = ParagraphStyle('h3', parent=styles['Heading3'], fontName='CN', fontSize=12, leading=18, textColor=PRIMARY, spaceAfter=3)
    s_bd = ParagraphStyle('bd', parent=styles['Normal'], fontName='CN', fontSize=10.5, leading=18, textColor=TEXT_DARK, firstLineIndent=21)
    s_bdn = ParagraphStyle('bdn', parent=styles['Normal'], fontName='CN', fontSize=10.5, leading=18, textColor=TEXT_DARK)
    s_bl = ParagraphStyle('bl', parent=styles['Normal'], fontName='CN', fontSize=10.5, leading=18, textColor=TEXT_DARK, leftIndent=15)
    s_qt = ParagraphStyle('qt', parent=styles['Normal'], fontName='CN', fontSize=10, leading=17, textColor=ACCENT, leftIndent=20, rightIndent=10, backColor=QUOTE_BG, borderPadding=5)
    s_th = ParagraphStyle('th', parent=styles['Normal'], fontName='CN', fontSize=10, leading=16, textColor=white, alignment=TA_CENTER)
    s_td = ParagraphStyle('td', parent=styles['Normal'], fontName='CN', fontSize=9.5, leading=15, textColor=TEXT_DARK, alignment=TA_CENTER)
    s_mt = ParagraphStyle('mt', parent=styles['Normal'], fontName='CN', fontSize=9, leading=14, textColor=TEXT_GRAY)

    doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm, title='JiangxiGK Daily', author='GK Helper')
    story = []

    story.append(Spacer(1, 35*mm))
    story.append(Paragraph('\U0001f4da ' + EXAM_NAME + '\u6bcf\u65e5\u5907\u8003\u8d44\u6599', s_ct))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph(EXAM_NAME, s_cs))
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph(date_cn + ' ' + weekday, s_cd))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph('\u23f0 \u8ddd\u7b14\u8bd5\u8fd8\u6709 ' + str(days_left) + ' \u5929', s_cs))
    story.append(Spacer(1, 12*mm))

    ov = [
        [Paragraph('\u4eba\u6c11\u65e5\u62a5\u8bc4\u8bba', s_th), Paragraph('\u65f6\u653f\u65b0\u95fb', s_th), Paragraph('\u91d1\u53e5\u6458\u5f55', s_th)],
        [Paragraph(str(len(comments)) + '\u7bc7', s_td), Paragraph(str(len(news_list)) + '\u6761', s_td), Paragraph(str(len(comments)*3) + '\u53e5', s_td)],
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
    story.append(Spacer(1, 20*mm))
    story.append(Paragraph('\u6bcf\u5929\u8fdb\u6b65\u4e00\u70b9\u70b9\uff0c\u4e00\u6b21\u4e0a\u5cb8\u6c5f\u897f \U0001f4aa', s_cs))
    story.append(PageBreak())

    story.append(Paragraph('\U0001f4f0 \u4eba\u6c11\u65e5\u62a5\u8bc4\u8bba', s_h1))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph('\u7cbe\u9009\u5f53\u65e5\u4eba\u6c11\u65f6\u8bc4\u3001\u4eba\u6c11\u9510\u8bc4\uff0c\u5168\u6587\u5448\u73b0', s_mt))
    story.append(Spacer(1, 4*mm))

    for i, c in enumerate(comments, 1):
        story.append(Paragraph(str(i) + '. ' + c['title'], s_h2))
        author_info = (' | \u4f5c\u8005\uff1a' + c['author']) if c['author'] else ''
        story.append(Paragraph('\u680f\u76ee\uff1a' + c['column'] + author_info + ' | <a href="' + c['url'] + '" color="#1a73e8">\u67e5\u770b\u539f\u6587</a>', s_mt))
        story.append(Spacer(1, 2*mm))
        
        if c['content']:
            max_paras = min(len(c['content']), 20)
            for para in c['content'][:max_paras]:
                story.append(Paragraph(para, s_bd))
            if len(c['content']) > max_paras:
                story.append(Paragraph('...\uff08\u5269\u4f59\u5185\u5bb9\u8bf7\u67e5\u770b\u539f\u6587\uff09', s_mt))
        else:
            story.append(Paragraph(c['summary'], s_bd))
        
        if c['golden']:
            story.append(Spacer(1, 3*mm))
            story.append(Paragraph('\U0001f4a1 \u91d1\u53e5\u6458\u5f55', s_h3))
            for gs in c['golden'][:3]:
                story.append(Paragraph('\u201c' + gs + '\u201d', s_qt))
                story.append(Spacer(1, 1*mm))
        
        story.append(Spacer(1, 5*mm))
    
    story.append(PageBreak())

    story.append(Paragraph('\U0001f514 \u65f6\u653f\u70ed\u70b9', s_h1))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph('\u5f53\u65e5\u91cd\u8981\u65f6\u653f\u65b0\u95fb\u6c47\u603b\uff0c\u6765\u6e90\uff1a\u65b0\u534e\u7f51\u3001\u4eba\u6c11\u7f51\u3001\u4e2d\u56fd\u653f\u5e9c\u7f51', s_mt))
    story.append(Spacer(1, 4*mm))

    cats = {}
    for n in news_list:
        cat = n['category']
        if cat not in cats:
            cats[cat] = []
        cats[cat].append(n)
    
    for cat, items in cats.items():
        story.append(Paragraph('\u25b8 ' + cat, s_h2))
        story.append(Spacer(1, 2*mm))
        for j, n in enumerate(items, 1):
            story.append(Paragraph(str(j) + '. ' + n['title'], s_bdn))
            story.append(Paragraph('<font color="#5f6368" size=9>\u6765\u6e90\uff1a' + n['source'] + ' | <a href="' + n['url'] + '" color="#1a73e8">\u67e5\u770b\u539f\u6587</a></font>', s_mt))
            if n['summary']:
                story.append(Paragraph('<font color="#5f6368" size=9>\u6458\u8981\uff1a' + n['summary'] + '</font>', s_mt))
            story.append(Spacer(1, 2*mm))
        story.append(Spacer(1, 3*mm))
    
    story.append(PageBreak())

    story.append(Paragraph('\U0001f4ac \u7533\u8bba\u91d1\u53e5\u79ef\u7d2f', s_h1))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph('\u4ece\u5f53\u65e5\u8bc4\u8bba\u6587\u7ae0\u4e2d\u6458\u5f55\u7684\u7cbe\u5f69\u8bed\u53e5', s_mt))
    story.append(Spacer(1, 4*mm))

    all_golden = []
    for c in comments:
        all_golden.extend(c['golden'])
    
    if all_golden:
        for idx, gs in enumerate(all_golden[:15], 1):
            story.append(Paragraph(str(idx) + '. \u201c' + gs + '\u201d', s_qt))
            story.append(Spacer(1, 2*mm))
    else:
        story.append(Paragraph('\u4eca\u65e5\u91d1\u53e5\u5f85\u79ef\u7d2f\uff08\u5efa\u8bae\u9605\u8bfb\u8bc4\u8bba\u6587\u7ae0\u81ea\u884c\u6458\u6284\uff09', s_bd))
    
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph('\U0001f4a1 \u5b66\u4e60\u5c0f\u8d34\u58eb', s_h1))
    story.append(Spacer(1, 3*mm))
    tips = [
        '1. \u7cbe\u8bfb2\u7bc7\u4eba\u6c11\u65e5\u62a5\u8bc4\u8bba\uff0c\u6ce8\u610f\u6587\u7ae0\u7ed3\u6784\u548c\u8bba\u8bc1\u65b9\u6cd5',
        '2. \u6458\u62843-5\u4e2a\u91d1\u53e5\uff0c\u5c1d\u8bd5\u7528\u5728\u7533\u8bba\u5199\u4f5c\u4e2d',
        '3. \u65f6\u653f\u65b0\u95fb\u4e2d\u6ce8\u610f\u6570\u5b57\u7c7b\u3001\u4f1a\u8bae\u7c7b\u3001\u653f\u7b56\u7c7b\u8003\u70b9',
        '4. \u7ed3\u5408\u70ed\u70b9\u601d\u8003\u7533\u8bba\u4f5c\u6587\u7684\u7acb\u610f\u548c\u5206\u8bba\u70b9',
        '5. \u6bcf\u5929\u575a\u6301\u9605\u8bfb\uff0c\u57f9\u517b\u5b98\u65b9\u8bed\u611f\u548c\u653f\u7b56\u601d\u7ef4',
    ]
    for tip in tips:
        story.append(Paragraph(tip, s_bl))
        story.append(Spacer(1, 2*mm))

    story.append(Spacer(1, 10*mm))
    story.append(Paragraph('---', s_bd))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph('<font color="#5f6368" size=8>\u672c\u8d44\u6599\u7531 GitHub Actions \u81ea\u52a8\u751f\u6210 | \u6570\u636e\u6765\u6e90\uff1a\u4eba\u6c11\u7f51\u3001\u65b0\u534e\u7f51\u3001\u4e2d\u56fd\u653f\u5e9c\u7f51</font>', s_mt))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph('<font color="#5f6368" size=8>\u751f\u6210\u65f6\u95f4\uff1a' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '</font>', s_mt))

    doc.build(story)
    print('PDF OK: ' + output_path)
    return True

def send_text(content):
    if not WECOM_WEBHOOK:
        print('no webhook, skip text')
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
        print('no webhook, skip file')
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
    print('=' * 50)
    print('JiangxiGK Daily Report v2.0')
    print('=' * 50)

    target_date = get_target_date()
    date_str, date_cn, weekday, days_left = format_date(target_date)
    print('Date: ' + date_cn + ' ' + weekday)
    print('Days left: ' + str(days_left))
    print('Webhook: ' + ('YES' if WECOM_WEBHOOK else 'NO'))

    os.makedirs('./output', exist_ok=True)
    pdf_path = './output/meiriziliao_' + date_str + '.pdf'

    print('\n[1/4] Fetch comments (full text)...')
    comments = fetch_comments()
    print('  Total: ' + str(len(comments)) + ' comments')
    for c in comments:
        paras = len(c['content']) if c['content'] else 0
        print('    - ' + c['title'][:35] + ' (' + str(paras) + 'p)')

    print('\n[2/4] Fetch news (4 sources)...')
    news_list = fetch_news()
    print('  Total: ' + str(len(news_list)) + ' news items')
    for n in news_list[:8]:
        print('    - [' + n['source'] + '] ' + n['title'][:35])

    print('\n[3/4] Generate PDF...')
    ok = generate_pdf(comments, news_list, date_str, date_cn, weekday, days_left, pdf_path)
    if not ok:
        打印('PDF 失败！')
        sys.exit(1)
    fsize = os.path.getsize(pdf_path)
    print('  Size: ' + str(round(fsize/1024, 1)) + ' KB')

    print('\n[4/4] 推送到企业微信...')
    total_golden = sum(len(c['golden']) for c in comments)
    md = '## \U0001f4da ' + EXAM_NAME + '\u6bcf\u65e5\u5907\u8003\u8d44\u6599 - ' + date_cn + ' ' + weekday + '\n\n'
    md += '\u23f0 \u8ddd' + EXAM_NAME + '\u7b14\u8bd5\u8fd8\u6709 **' + str(days_left) + '** \u5929\n\n'
    md += '---\n\n'
    md += '### \U0001f4f0 \u4eca\u65e5\u5185\u5bb9\n\n'
    md += '- **\u4eba\u6c11\u65e5\u62a5\u8bc4\u8bba**\uff1a' + str(len(comments)) + '\u7bc7\uff08\u5168\u6587+\u91d1\u53e5\uff09\n'
    md += '- **\u65f6\u653f\u70ed\u70b点**\uff1a' + str(len(news_list)) + '\u6761\uff08\u65b0\u534e\u7f51+\u4e2d\u56fd\u653f\u5e9c\u7f51\uff09\n'
    md += '- **\u91d1\u53e5\u79积\u7d2f**\uff1a' + str(total_golden) + '\u53e5\n\n'
    md += '---\n\n'
    md += '### \U0001f4a1 \u5b66\u4e60\u5efa\u8bae\n\n'
    md += '1. \u7cbe\u8bfb2\u7bc7\u8bc4\u8bba\uff0c\u5206\u6790\u8bba\u8bc1\u7ed3\u6784\n'
    md += '2. \u6458\u6284\u91d1\u53e5\uff0c\u7528\u4e8e\u7533\u8bba\u5199\u4f5c\n'
    md += '3. \u65f6\u653f\u6807\u6ce8\u8003\u70b9\uff08\u6570\u5b57/\u4f1a\u8bae/\u653f\u7b56\uff09\n\n'
    md += '---\n\n'
    md += '\U0001f4c4 PDF\u5df2\u53d1\u9001\uff0c\u8bf7\u67e5\u6536\u9644\u4ef6\n\n'
    md += '> \u6bcf\u5929\u8fdb\u6b65\u4e00\u70b9\u70b9\uff0c\u4e00\u6b21\u4e0a\u5cb8\u6c5f\u897f\uff01\U0001f4aa\n'

    text_ok = send_text(md)
    file_ok = send_file(pdf_path)
    
    print('  Text: ' + ('OK' if text_ok else 'FAIL'))
    print('  File: ' + ('OK' if file_ok else 'FAIL'))

    print('\n' + '=' * 50)
    print('All done!')
    打印('=' * 50)

if __name__ == '__main__':
    main()
