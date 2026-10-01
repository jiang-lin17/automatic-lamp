# 🏮 automatic-lamp · 江西省考每日备考助手

> 每天早上 7 点，GitHub Actions 自动帮你收集前一天的 **人民日报评论 + 时政热点**，生成精美 PDF 推送到企业微信群。  
> 专为 2027 年江西省考备考设计，申论金句、权威时评、政策动态一网打尽。

---

## ✨ 功能特性

- 📰 **人民日报评论全文抓取** — 人民时评 + 人民锐评，含金句自动摘录
- 🔔 **多源时政新闻聚合** — 新华网、人民网、中国政府网，智能去重
- 📄 **精美 A4 PDF 报告** — 封面、评论、热点、金句、学习贴士，结构清晰
- 💬 **企业微信自动推送** — PDF + Markdown 消息一键送达群聊
- ⏰ **云端定时运行** — GitHub Actions 每天自动触发，无需值守
- 🔧 **模块化可配置** — 考试日期、抓取源、阈值全在 `src/config.py`

## 📊 每日报告结构

| 章节 | 内容 |
|------|------|
| 📚 封面 | 考试倒计时、当日内容统计 |
| 📰 人民日报评论 | 3 篇人民时评 + 2 篇人民锐评（全文 + 金句） |
| 🔔 时政热点 | 15 条新闻，按来源分类，附完整可点击链接 |
| 📬 申论金句 | 从评论文章中摘录的精华语句 |
| 💡 学习贴士 | 每日 5 条备考建议 |

## 🕷️ 数据来源

| 来源 | 类型 | 地址 |
|------|------|------|
| 人民网 · 人民时评 | 评论 | `opinion.people.com.cn` |
| 人民网 · 人民锐评 | 评论 | `opinion.people.com.cn` |
| 新华网 · 时政 | 新闻 | `www.xinhuanet.com/politics/` |
| 人民网 · 时政 | 新闻 | `politics.people.com.cn` |
| 中国政府网 · 政策动态 | 新闻 | `www.gov.cn/zhengce/zuixin/` |
| 新华网 · 首页要闻 | 新闻 | `www.news.cn` |

## 🗂️ 项目结构

```
automatic-lamp/
├── .github/workflows/daily.yml   # GitHub Actions 定时任务
├── src/
│   ├── config.py                 # 所有可配置项（考试日期、抓取源、阈值…）
│   ├── utils.py                  # 工具函数：结构化日志、HTTP 重试、日期
│   ├── scraper.py                # 抓取模块：评论 + 新闻
│   ├── pdf_builder.py            # PDF 生成（ReportBuilder 类）
│   ├── wecom.py                  # 企业微信推送（WeComPusher 类）
│   └── main.py                   # 业务流程编排
├── main.py                       # 顶层入口
├── requirements.txt              # Python 依赖
└── README.md
```

## 🚀 快速开始

### 方式一：GitHub Actions（推荐，云端自动跑）

1. **Fork / Clone** 本仓库
2. 在仓库 **Settings → Secrets and variables → Actions** 中添加一个 Secret：
   - **Name**: `WECOM_WEBHOOK`
   - **Value**: 你的企业微信群机器人 Webhook URL（以 `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx` 开头）
3. 进入 **Actions → DailyReport → Run workflow** 手动触发一次
4. 之后每天 **北京时间 07:00** 自动运行

> 💡 无论成功失败，每次运行的 PDF 和日志都会上传到 Artifacts，在 Actions 页面最下方下载。

### 方式二：本地运行

```bash
# 克隆仓库
git clone https://github.com/jiang-lin17/automatic-lamp.git
cd automatic-lamp

# 安装依赖（Python 3.11+）
pip install -r requirements.txt

# 设置企业微信 Webhook（可选，不配也能生成 PDF）
# Windows PowerShell:
$env:WECOM_WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key"
# macOS / Linux:
export WECOM_WEBHOOK="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key"

# 运行
python main.py
```

PDF 会生成在 `./output/meiriziliao_YYYY-MM-DD.pdf`。

## ⚙️ 配置说明

所有可配置项集中在 [src/config.py](src/config.py)，常用的几个：

```python
# 考试日期（自动计算倒计时）
ExamConfig.date = datetime(2027, 3, 25)

# 抓取数量阈值
ContentThresholds.comment_min_title_len = 5   # 评论标题最少字符
ContentThresholds.news_max_total = 15         # 新闻最多条数
ContentThresholds.golden_per_article = 3      # 每篇评论最多金句数

# HTTP 限速（秒）
HttpConfig.request_interval = 0.5

# 字体（按顺序尝试，第一个存在的生效）
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",   # Linux / GitHub Actions
    "C:/Windows/Fonts/msyh.ttc",                         # Windows
    "/System/Library/Fonts/PingFang.ttc",                # macOS
]
```

## 🤖 企业微信机器人 Webhook 获取

1. 企业微信群聊 → 右上角群设置 → **群机器人**
2. 添加机器人 → **自定义**（关键词可以不填，选"接收全部消息"）
3. 创建完成后会得到一个 `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx` 的 URL
4. 这个 URL 就是 `WECOM_WEBHOOK` 的值

## 🧪 手动测试

```bash
# 只跑一遍，不依赖企业微信
python main.py
# 日志会同时输出到控制台和 run.log
```

## ❓ 常见问题

**Q: PDF 里中文乱码？**  
A: 大概率是系统没有中文字体。GitHub Actions 已经自动安装 `fonts-wqy-microhei`，本地 Windows 用的是微软雅黑（`msyh.ttc`）。如果其他系统跑，装一个中文字体就行。

**Q: 某个新闻源抓不到内容？**  
A: 目标网站偶尔改版是正常的。去 [src/config.py](src/config.py) 找到对应的抓取源（`SCRAPE_SOURCES` 字典），调整 `list_url` 和 `href_contains` 过滤条件即可。编码一般不用管，代码会自动读 HTML `<meta charset>`。

**Q: 想改考试日期？**  
A: 改 `ExamConfig.date`，所有倒计时会自动更新。

**Q: 企业微信推送没收到？**  
A: 检查 Secret 里的 `WECOM_WEBHOOK` 是否正确，Webhook URL 是否以 `https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=` 开头。查看 Actions 运行日志里 `[4/4]` 的输出。

## 📦 依赖

| 包 | 用途 |
|----|------|
| `requests` | HTTP 请求 |
| `beautifulsoup4` | HTML 解析 |
| `reportlab` | PDF 生成 |
| `tenacity` | 请求重试（指数退避） |

## 📄 许可证

MIT License — 随便用、随便改，上岸记得回来 Star ⭐ 一下就行～

---

> 每天进步一点点，一次上岸江西！ 🎯
