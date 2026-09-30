#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import re
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

WECOM_WEBHOOK = os.environ.get('WECOM_WEBHOOK', '')
EXAM_NAME = '2027年江西省考'
EXAM_DATE = datetime(2027, 3, 25)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
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
                article = fetch_article_full(full_url)
                comments.append({
                    'title': text,
                    'column': '人民时评',
                    'url': full_url,
                    'summary': article['summary'],
                    'content': article['content'],
                    'author': article['author'],
                    'golden_sentences': article['golden_sentences']
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
                    article = fetch_article_full(full_url)
                    comments.append({
                        'title': text,
                        'column': '人民锐评',
                        'url': full_url,
                        'summary': article['summary'],
                        'content': article['content'],
                        'author': article['author'],
                        'golden_sentences': article['golden_sentences']
                    })
                    break
        except Exception as e:
            print('fail ruiping: ' + str(e))
    except Exception as e:
        print('fail shiping: ' + str(e))
    return comments[:4]

def fetch_article_full(url):
    result = {'summary': '', 'content': '', 'author': '', 'golden_sentences': []}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.encoding = resp.apparent_encoding or 'gbk'
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 找作者
        author_div = soup.find('div', class_='author') or soup.find('div', class_='rm_txt_con_author')
        if author_div:
            result['author'] = author_div.get_text(strip=True)
        
        # 找正文
        content_div = soup.find('div', class_='rm_txt_con') or soup.find('div', id='rwb_zw') or soup.find('div', class_='article-content')
        if content_div:
            paragraphs = []
            for p in content_div.find_all('p'):
                text = p.get_text(strip=True)
                if text and len(text) > 10:
                    paragraphs.append(text)
            
            result['content'] = paragraphs
            if len(paragraphs) > 2:
                result['summary'] = paragraphs[0][:150] + '...' if len(paragraphs[0]) > 150 else paragraphs[0]
            
            # 提取金句（含引号或对仗工整的句子）
            for p in paragraphs:
                if ('"' in p or '"' in p) and len(p) < 100:
                    result['golden_sentences'].append(p.strip())
                elif '不是...而是' in p or '既要...也要' in p or '从...到...' in p:
                    result['golden_sentences'].append(p.strip())
                if len(result['golden_sentences']) >= 5:
                    break
        
        if not result['summary']:
            result['summary'] = '点击查看原文'
            
    except Exception as e:
        result['summary'] = '点击查看原文'
        print('fetch article error: ' + str(e))
    
    return result

def fetch_news():
    news_list = []
    try:
        url = 'http://politics.people.com.cn/'
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.encoding = resp.apparent_encoding or 'gbk'
        soup = BeautifulSoup(resp.text, 'html.parser')
        for link in soup.find_all('a', href=True)[:50]:
            title = link.get_text(strip=True)
            href = link.get('href', '')
            if title and len(title) > 12 and '/n1/' in href:
                full_url = 'http://politics.people.com.cn' + href if href.startswith('/') else href
                summary = fetch_news_summary(full_url)
                news_list.append({
                    'title': title,
                    'url': full_url,
                    'source': '人民网',
                    'category': '时政要闻',
                    'summary': summary
                })
    except Exception as e:
        print('fail news: ' + str(e))
    
    try:
        url2 = 'https://www.gov.cn/yaowen.htm'
        resp2 = requests.get(url2, headers=HEADERS, timeout=15)
        resp2.encoding = 'utf-8'
        soup2 = BeautifulSoup(resp2.text, 'html.parser')
        items = soup2.find_all('li')
        for item in items[:10]:
            link = item.find('a')
            if link:
                title = link.get_text(strip=True)
                href = link.get('href', '')
                if title and len(title) > 10:
                    full_url = href if href.startswith('http') else 'https://www.gov.cn/' + href.lstrip('/')
                    news_list.append({
                        'title': title,
                        'url': full_url,
                        'source': '中国政府网',
                        'category': '国内要闻',
                        'summary': ''
                    })
    except Exception as e:
        print('fail gov: ' + str(e))
    
    seen = set()
    unique = []
    for n in news_list:
        if n['title'] not in seen:
            seen.add(n['title'])
            unique.append(n)
    return unique[:15]

def fetch_news_summary(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.encoding = resp.apparent_encoding or 'gbk'
        soup = BeautifulSoup(resp.text, 'html.parser')
        content_div = soup.find('div', class_='rm_txt_con') or soup.find('div', id='rwb_zw')
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
    from reportlab.lib.enums import TA_CENTER, TA_LEFT

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
    s_cover_title = ParagraphStyle('ct', parent=styles['Title'], fontName='CN', fontSize=26, leading=36, alignment=TA_CENTER, textColor=PRIMARY)
    s_cover_sub = ParagraphStyle('cs', parent=styles['Normal'], fontName='CN', fontSize=14, leading=22, alignment=TA_CENTER, textColor=TEXT_GRAY)
    s_cover_date = ParagraphStyle('cd', parent=styles['Normal'], fontName='CN', fontSize=20, leading=30, alignment=TA_CENTER, textColor=TEXT_DARK)
    s_h1 = ParagraphStyle('h1', parent=styles['Heading1'], fontName='CN', fontSize=18, leading=28, textColor=PRIMARY, spaceAfter=6)
    s_h2 = ParagraphStyle('h2', parent=styles['Heading2'], fontName='CN', fontSize=14, leading=22, textColor=TEXT_DARK, spaceAfter=4)
    s_h3 = ParagraphStyle('h3', parent=styles['Heading3'], fontName='CN', fontSize=12, leading=18, textColor=PRIMARY, spaceAfter=3)
    s_body = ParagraphStyle('bd', parent=styles['Normal'], fontName='CN', fontSize=10.5, leading=18, textColor=TEXT_DARK, firstLineIndent=21)
    s_body_no_indent = ParagraphStyle('bdn', parent=styles['Normal'], fontName='CN', fontSize=10.5, leading=18, textColor=TEXT_DARK)
    s_bullet = ParagraphStyle('bl', parent=styles['Normal'], fontName='CN', fontSize=10.5, leading=18, textColor=TEXT_DARK, leftIndent=15)
    s_quote = ParagraphStyle('qt', parent=styles['Normal'], fontName='CN', fontSize=10, leading=17, textColor=ACCENT, leftIndent=20, rightIndent=10, backColor=QUOTE_BG, borderPadding=5)
    s_th = ParagraphStyle('th', parent=styles['Normal'], fontName='CN', fontSize=10, leading=16, textColor=white, alignment=TA_CENTER)
    s_td = ParagraphStyle('td', parent=styles['Normal'], fontName='CN', fontSize=9.5, leading=15, textColor=TEXT_DARK, alignment=TA_CENTER)
    s_meta = ParagraphStyle('mt', parent=styles['Normal'], fontName='CN', fontSize=9, leading=14, textColor=TEXT_GRAY)

    doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=18*mm, rightMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm, title='JiangxiGK Daily', author='GK Helper')
    story = []

    # ========== 封面 ==========
    story.append(Spacer(1, 35*mm))
    story.append(Paragraph('📚 江西省考每日备考资料', s_cover_title))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph(EXAM_NAME, s_cover_sub))
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph(date_cn + ' ' + weekday, s_cover_date))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph('⏰ 距笔试还有 ' + str(days_left) + ' 天', s_cover_sub))
    story.append(Spacer(1, 12*mm))

    ov = [
        [Paragraph('人民日报评论', s_th), Paragraph('时政新闻', s_th), Paragraph('金句摘录', s_th)],
        [Paragraph(str(len(comments)) + '篇', s_td), Paragraph(str(len(news_list)) + '条', s_td), Paragraph(str(len(comments)*3) + '句', s_td)],
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
    story.append(Paragraph('每天进步一点点，一次上岸江西 💪', s_cover_sub))
    story.append(PageBreak())

    # ========== 人民日报评论（全文） ==========
    story.append(Paragraph('📰 人民日报评论', s_h1))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph('精选当日人民时评、人民锐评，全文呈现', s_meta))
    story.append(Spacer(1, 4*mm))

    for i, c in enumerate(comments, 1):
        story.append(Paragraph(str(i) + '. ' + c['title'], s_h2))
        story.append(Paragraph('栏目：' + c['column'] + ((' | 作者：' + c['author']) if c['author'] else '') + ' | <a href="' + c['url'] + '" color="#1a73e8">查看原文</a>', s_meta))
        story.append(Spacer(1, 2*mm))
        
        # 全文内容（限制段落数，避免PDF太长）
        if c['content']:
            max_paras = min(len(c['content']), 20)
            for j, para in enumerate(c['content'][:max_paras]):
                story.append(Paragraph(para, s_body))
            if len(c['content']) > max_paras:
                story.append(Paragraph('...（剩余内容请查看原文）', s_meta))
        else:
            story.append(Paragraph(c['summary'], s_body))
        
        # 金句摘录
        if c['golden_sentences']:
            story.append(Spacer(1, 3*mm))
            story.append(Paragraph('💡 金句摘录', s_h3))
            for gs in c['golden_sentences'][:3]:
                story.append(Paragraph('"' + gs + '"', s_quote))
                story.append(Spacer(1, 1*mm))
        
        story.append(Spacer(1, 5*mm))
    
    story.append(PageBreak())

    # ========== 时政热点 ==========
    story.append(Paragraph('🔔 时政热点', s_h1))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph('当日重要时政新闻汇总，标注来源', s_meta))
    story.append(Spacer(1, 4*mm))

    cats = {}
    for n in news_list:
        cat = n['category']
        if cat not in cats:
            cats[cat] = []
        cats[cat].append(n)
    
    for cat, items in cats.items():
        story.append(Paragraph('▸ ' + cat, s_h2))
        story.append(Spacer(1, 2*mm))
        for j, n in enumerate(items, 1):
            story.append(Paragraph(str(j) + '. ' + n['title'], s_body_no_indent))
            story.append(Paragraph('<font color="#5f6368" size=9>来源：' + n['source'] + ' | <a href="' + n['url'] + '" color="#1a73e8">查看原文</a></font>', s_meta))
            if n['summary']:
                story.append(Paragraph('<font color="#5f6368" size=9>摘要：' + n['summary'] + '</font>', s_meta))
            story.append(Spacer(1, 2*mm))
        story.append(Spacer(1, 3*mm))
    
    story.append(PageBreak())

    # ========== 申论金句积累 ==========
    story.append(Paragraph('💬 申论金句积累', s_h1))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph('从当日评论文章中摘录的精彩语句', s_meta))
    story.append(Spacer(1, 4*mm))

    all_golden = []
    for c in comments:
        all_golden.extend(c['golden_sentences'])
    
    if all_golden:
        for idx, gs in enumerate(all_golden[:15], 1):
            story.append(Paragraph(str(idx) + '. "' + gs + '"', s_quote))
            story.append(Spacer(1, 2*mm))
    else:
        story.append(Paragraph('今日金句待积累（建议阅读评论文章自行摘抄）', s_body))
    
    story.append(Spacer(1, 8*mm))

    # ========== 学习小贴士 ==========
    story.append(Paragraph('💡 学习小贴士', s_h1))
    story.append(Spacer(1, 3*mm))
    tips = [
        '1. 精读2篇人民日报评论，注意文章结构和论证方法',
        '2. 摘抄3-5个金句，尝试用在申论写作中',
        '3. 时政新闻中注意数字类、会议类、政策类考点',
        '4. 结合热点思考申论作文的立意和分论点',
        '5. 每天坚持阅读，培养官方语感和政策思维',
    ]
    for tip in tips:
        story.append(Paragraph(tip, s_bullet))
        story.append(Spacer(1, 2*mm))

    story.append(Spacer(1, 10*mm))
    story.append(Paragraph('---', s_body))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph('<font color="#5f6368" size=8>本资料由 GitHub Actions 自动生成 | 数据来源：人民网、中国政府网</font>', s_meta))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph('<font color="#5f6368" size=8>生成时间：' + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '</font>', s_meta))

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
    print('JiangxiGK Daily Report (Enhanced)')
    print('=' * 40)

    target_date = get_target_date()
    date_str, date_cn, weekday, days_left = format_date(target_date)
    print('Date: ' + date_cn + ' ' + weekday)
    print('Days left: ' + str(days_left))

    os.makedirs('./output', exist_ok=True)
    pdf_path = './output/每日备考资料_' + date_str + '.pdf'

    print('\n[1/4] Fetch comments (full text)...')
    comments = fetch_comments()
    print('  Got ' + str(len(comments)) + ' comments')
    for c in comments:
        paras = len(c['content']) if c['content'] else 0
        print('    - ' + c['title'][:30] + ' (' + str(paras) + ' paragraphs)')

    print('\n[2/4] Fetch news...')
    news_list = fetch_news()
    print('  Got ' + str(len(news_list)) + ' news')
    for n in news_list[:5]:
        print('    - ' + n['title'][:30])

    print('\n[3/4] Generate PDF...')
    ok = generate_pdf(comments, news_list, date_str, date_cn, weekday, days_left, pdf_path)
    如果 不正确：
        print('PDF failed!')
        sys.exit(1)
    fsize = os.path.getsize(pdf_path)
('  大小：' + str(四舍五入(文件大小/1024, 1)) + ' KB')

    print('\n[4/4] 推送到企业微信...')
    总黄金数 = sum(len(c['golden_sentences']) for c in comments)
    md = '## 📚 江西省考每日备考资料 - ' + date_cn + ' ' + weekday + '\n\n'
    md += '⏰ 距' + EXAM_NAME + '笔试还有 **' + str(days_left) + '** 天\n\n'
    md += '---\n\n'
    md += '### 📰 今日内容\n\n'
    md += '- **人民日报评论**：' + str(len(comments)) + '篇（全文呈现+金句摘录）\n'
    md += '- **时政热点**：' + str(len(news_list)) + '条\n'
    md += '- **金句积累**：' + str(total_golden) + '句\n\n'
    md += '---\n\n'
    md += '### 💡 学习建议\n\n'
    md += '1. 精读2篇评论，分析论证结构\n'
    md += '2. 摘抄金句，用于申论写作\n'
    md += '3. 时政标注考点（数字/会议/政策）\n\n'
    md += '---\n\n'
    md += '📄 PDF已发送，请查收附件\n\n'
    md += '> 每天进步一点点，一次上岸江西！💪\n'

    send_text(md)
    send_file(pdf_path)

    print('\n' + '=' * 40)
    print('All done!')
    print('=' * 40)

if __name__ == '__main__':
    main()
