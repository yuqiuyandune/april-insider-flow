"""Build the homepage (/) of April's Stock Atlas: one entry point to every section.

Top to bottom: the site header (one bar: brand, sections, ticker search, language, subscribe), today's
overview (date, market-holiday note, five market tiles), today's signals, the next macro events,
the latest earnings reviews, the largest insider buys and sells, a grid of every section, the
subscribe band.

Built here from local data (so the page works without JavaScript for the parts that matter):
  - signals and the insider lists: the last SIGNAL_DAYS filing days in data/days (effective trades only,
    the same definition as /insider/)
  - chain tags: stack/data.json (AI) and energy/data.json
  - macro events: data/macro.json (the browser picks the next ones by US Eastern date)
Market tiles: SPY, QQQ, IWM, TLT and USO from data/volume.json (last session). Read in the browser from the
earnings site: /earnings/data/index.json (latest earnings reviews).

    build(out, days, pages, page_bits)   pages = [(slug, lastmod)] from company_pages
"""
import os, re, json, html, glob

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SITE = "https://april-insider-flow.com"
SIGNAL_DAYS = 5
DAILY_OPTIN = False   # the daily-brief checkbox needs Buttondown tags (a paid plan); off until that is sorted out
LANGS = ("zh", "tw", "en")
LOC = {"zh": "zh-CN", "tw": "zh-TW", "en": "en"}

# ------------------------------------------------------------------ the shared header (nav order = site structure)
NAV = [  # (key, href, zh, tw, en)
    ("home", "/", "今日", "今日", "Today"),
    ("ins", "/insider/", "内部人", "內部人", "Insiders"),
    ("inst", "/institutions/", "机构", "機構", "Funds"),
    ("earn", "/earnings/", "财报", "財報", "Earnings"),
    ("cal", "/calendar/", "日历", "日曆", "Calendar"),
    ("mkt", "/market/", "市场", "市場", "Markets"),
    ("chain", "/themes/", "产业链", "產業鏈", "Themes"),
]
LOGO = ('<span class="logo" aria-hidden="true"><svg width="18" height="18" viewBox="0 0 18 18"><rect x="2" y="9" width="3" height="7" rx="1.5" fill="#ff7b72"/>'
        '<rect x="7.5" y="5" width="3" height="11" rx="1.5" fill="#3ddc9b"/><rect x="13" y="2" width="3" height="14" rx="1.5" fill="#3ddc9b"/></svg></span>')
SEARCH_PH = {"zh": "搜索代码，如 NVDA", "tw": "搜尋代碼，如 NVDA", "en": "Search ticker, e.g. NVDA"}
SUB = {"zh": "订阅", "tw": "訂閱", "en": "Subscribe"}

def header(cur):
    def tri(z, t, e): return f'<span data-l="zh">{z}</span><span data-l="tw">{t}</span><span data-l="en">{e}</span>'
    nav = "".join(f'<a href="{h}"{" aria-current=page class=cur" if k == cur else ""}>{tri(z, t, e)}</a>' for k, h, z, t, e in NAV)
    return f"""<header class="hd"><div class="hd-in">
<a class="brand" href="/" aria-label="April's Stock Atlas">{LOGO}<b><i>April's</i> Stock Atlas</b></a>
<nav class="nav" aria-label="Sections">{nav}</nav>
<form class="srch" id="srch" role="search"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
<input id="srch-q" type="search" autocomplete="off" autocapitalize="characters" spellcheck="false" aria-label="Ticker" placeholder="{SEARCH_PH['zh']}"><span class="srch-msg" id="srch-msg" role="status"></span></form>
<div class="lang" role="group" aria-label="Language / 语言">
<button type="button" id="lang-zh" aria-pressed="true" lang="zh-CN">简</button><button type="button" id="lang-tw" aria-pressed="false" lang="zh-TW">繁</button><button type="button" id="lang-en" aria-pressed="false">EN</button>
</div>
<button type="button" class="subbtn" id="hd-sub">{tri(SUB['zh'], SUB['tw'], SUB['en'])}</button>
</div></header>"""

HEADER_CSS = """
.hd{background:var(--surface);border-bottom:1px solid var(--line);position:relative;z-index:5}
.hd-in{max-width:1200px;margin:0 auto;padding:0 16px;min-height:64px;display:flex;align-items:center;gap:16px}
.hd .brand{flex:none}
.nav{display:flex;gap:16px;align-items:center;flex:1;min-width:0}
.nav a{color:var(--muted);text-decoration:none;font-size:14.5px;font-weight:500;padding:20px 1px 18px;border-bottom:2px solid transparent;white-space:nowrap}
.nav a:hover{color:var(--ink)}.nav a.cur{color:var(--ink);font-weight:700;border-bottom-color:var(--accent)}
.nav [data-l]{display:none}html.l-zh .nav [data-l=zh],html.l-tw .nav [data-l=tw],html.l-en .nav [data-l=en]{display:inline}
.subbtn [data-l]{display:none}html.l-zh .subbtn [data-l=zh],html.l-tw .subbtn [data-l=tw],html.l-en .subbtn [data-l=en]{display:inline}
.srch{position:relative;display:flex;align-items:center;gap:8px;background:var(--surface-2);border:1px solid var(--line);border-radius:10px;padding:0 12px;height:38px;width:170px;flex:none;color:var(--faint)}
.srch input{border:0;background:transparent;outline:none;font:inherit;font-size:14px;width:100%;color:var(--ink);min-width:0}
.srch:focus-within{border-color:var(--accent)}
.srch-msg{position:absolute;left:0;top:42px;font-size:12.5px;color:var(--muted);white-space:nowrap}
.hd .lang button{padding:5px 10px}
.subbtn{border:0;background:var(--accent);color:#fff;font-weight:700;font-size:14px;border-radius:10px;padding:9px 16px;cursor:pointer;flex:none}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]) .subbtn{color:#0b111b}}
@media (max-width:1260px){
 .hd-in{display:grid;grid-template-columns:minmax(0,1fr) auto;grid-template-areas:"brand sub" "srch lang" "nav nav";gap:10px 10px;padding-top:10px;min-height:0}
 .hd .brand{grid-area:brand}.subbtn{grid-area:sub;justify-self:end}.srch{grid-area:srch;width:auto}.hd .lang{grid-area:lang;align-self:center}
 .nav{grid-area:nav;gap:18px;overflow-x:auto;scrollbar-width:none;margin:0 -16px;padding:0 16px}
 .nav::-webkit-scrollbar{display:none}
 .nav a{padding:8px 1px 9px}
}
@media (max-width:420px){.subbtn{padding:8px 12px}}
"""

HEADER_JS = r"""<script>
(function(){
var T=__TICKERS__,PH=__PH__,MSG={zh:"没有找到 ",tw:"沒有找到 ",en:"No page for "};
var f=document.getElementById("srch"),q=document.getElementById("srch-q"),m=document.getElementById("srch-msg");
var set=new Set(T);
f.addEventListener("submit",function(e){e.preventDefault();var v=q.value.trim().toUpperCase().replace(/^\$/,"");if(!v)return;
 if(set.has(v)){location.href="/s/"+encodeURIComponent(v)+".html";return}
 m.textContent=(MSG[window.PAGE_LANG]||MSG.zh)+v});
q.addEventListener("input",function(){m.textContent=""});
var prev=window.onPageLang;window.onPageLang=function(l){q.placeholder=PH[l]||PH.zh;if(prev)prev(l)};
var s=document.getElementById("hd-sub");s.addEventListener("click",function(){var t=document.getElementById("subscribe");if(!t){location.href="/#subscribe";return}
 t.scrollIntoView({behavior:"smooth",block:"center"});var e=document.querySelector("html.l-"+(window.PAGE_LANG||"zh")+" .js-em")||document.querySelector(".js-em");if(e)setTimeout(function(){e.focus({preventScroll:true})},350)});
})();
</script>"""

# ------------------------------------------------------------------ texts
T = {
    "zh": {"title": "April's Stock Atlas · 美股内部人、财报、日历", "desc": "美股的内部人买卖、财报解读、宏观日历和市场观察，每天更新。只做公开数据的整理，不构成投资建议。",
           "wd": "周日,周一,周二,周三,周四,周五,周六", "md": "{m}月{d}日", "closed": "美股休市", "early": "美股半日市 · 13:00 ET 收盘", "open": "美股交易日",
           "asof": "内部人数据截至 {a}", "mkAsof": "行情截至 {a}", 
           "d1": "上个交易日",
           "sigL": "今日信号", "sigH": "内部人在买什么", "sigAll": "打开内部人页面 →",
           "sigP": "近 5 个交易日，多位高管和董事同时买入的公司排在最前。同一家公司的机构持仓如果也有动静，对应的标签会亮起。",
           "srcIns": "内部人", "srcOpt": "期权", "srcEarn": "财报", "srcInst": "机构",
           "calL": "本周与接下来", "calAll": "完整日历 →", "earnL": "最新财报解读", "earnAll": "全部 →", "volL": "昨日量价", "volAll": "量价分析 →", "optL": "昨日期权", "optAll": "期权异动 →", "instL": "机构动向", "instAll": "机构持仓 →", "inst": {"stake13d": "有人 13D 举牌", "stake13g": "新的 5% 大股东", "fundsBuy": "多家基金买入", "fundsSell": "多家基金卖出"},
           "insL": "内部人动向", "insH": "近 5 个交易日的有效买卖", "buy": "▲ 最大的买入", "sell": "▼ 最大的卖出",
           "expL": "探索 Stock Atlas", "soon": "即将上线",
           "subH": "每周一封周报", "subP": "每个周末汇总一周的内部人买卖要点和新上线的财报解读。中文在前，英文在后。免费，随时退订。", "daily": "也每天收早报（已订阅的读者勾选后再提交一次即可）", "subB": "订阅", "em": "你的邮箱",
           "foot": "只做公开数据的整理，不构成投资建议。", "src": "数据来源：SEC EDGAR · 美联储 · BLS · BEA · NYSE",
           "noData": "暂时读不到行情数据。", "nobody": "这几天没有多人同时买入的公司。", "allday": "全天", "bj": "北京", "next": "次日",
           },
    "tw": {"title": "April's Stock Atlas · 美股內部人、財報、日曆", "desc": "美股的內部人買賣、財報解讀、總經日曆和市場觀察，每天更新。只做公開資料的整理，不構成投資建議。",
           "wd": "週日,週一,週二,週三,週四,週五,週六", "md": "{m}月{d}日", "closed": "美股休市", "early": "美股半日市 · 13:00 ET 收盤", "open": "美股交易日",
           "asof": "內部人資料截至 {a}", "mkAsof": "行情截至 {a}", 
           "d1": "上個交易日",
           "sigL": "今日信號", "sigH": "內部人在買什麼", "sigAll": "打開內部人頁面 →",
           "sigP": "近 5 個交易日，多位高管和董事同時買入的公司排在最前。同一家公司的機構持股如果也有動靜，對應的標籤會亮起。",
           "srcIns": "內部人", "srcOpt": "選擇權", "srcEarn": "財報", "srcInst": "機構",
           "calL": "本週與接下來", "calAll": "完整日曆 →", "earnL": "最新財報解讀", "earnAll": "全部 →", "volL": "昨日量價", "volAll": "量價分析 →", "optL": "昨日選擇權", "optAll": "選擇權異動 →", "instL": "機構動向", "instAll": "機構持股 →", "inst": {"stake13d": "有人 13D 舉牌", "stake13g": "新的 5% 大股東", "fundsBuy": "多家基金買入", "fundsSell": "多家基金賣出"},
           "insL": "內部人動向", "insH": "近 5 個交易日的有效買賣", "buy": "▲ 最大的買入", "sell": "▼ 最大的賣出",
           "expL": "探索 Stock Atlas", "soon": "即將上線",
           "subH": "每週一封週報", "subP": "每個週末彙總一週的內部人買賣要點和新上線的財報解讀。中文在前，英文在後。免費，隨時退訂。", "daily": "也每天收早報（已訂閱的讀者勾選後再提交一次即可）", "subB": "訂閱", "em": "你的郵箱",
           "foot": "只做公開資料的整理，不構成投資建議。", "src": "資料來源：SEC EDGAR · 聯準會 · BLS · BEA · NYSE",
           "noData": "暫時讀不到行情資料。", "nobody": "這幾天沒有多人同時買入的公司。", "allday": "全天", "bj": "北京", "next": "次日",
           },
    "en": {"title": "April's Stock Atlas · US insider trades, earnings, calendar", "desc": "US insider buying and selling, earnings reviews, the macro calendar and market watch, updated daily. A summary of public data, not investment advice.",
           "wd": "Sun,Mon,Tue,Wed,Thu,Fri,Sat", "md": "{M} {d}", "closed": "US market closed", "early": "US early close · 13:00 ET", "open": "US trading day",
           "asof": "Insider data through {a}", "mkAsof": "Prices as of {a}", 
           "d1": "last session",
           "sigL": "Today's signals", "sigH": "What insiders are buying", "sigAll": "Open the insider page →",
           "sigP": "Companies where several officers and directors bought in the last 5 trading days come first. When the same company's institutional holders also moved, that tag lights up.",
           "srcIns": "Insiders", "srcOpt": "Options", "srcEarn": "Earnings", "srcInst": "Institutions",
           "calL": "This week and next", "calAll": "Full calendar →", "earnL": "Latest earnings reviews", "earnAll": "All →", "volL": "Price and volume", "volAll": "Full table →", "optL": "Options", "optAll": "Options activity →", "instL": "Institutions", "instAll": "Holdings →", "inst": {"stake13d": "new 13D stake", "stake13g": "new 5% holder", "fundsBuy": "several funds bought", "fundsSell": "several funds sold"},
           "insL": "Insider activity", "insH": "Effective buying and selling, last 5 trading days", "buy": "▲ Largest buys", "sell": "▼ Largest sells",
           "expL": "Explore Stock Atlas", "soon": "Coming soon",
           "subH": "A weekly email", "subP": "Every weekend: the week's insider trading highlights and new earnings reviews. Chinese first, English below. Free, unsubscribe anytime.", "daily": "Also send me the daily brief (already subscribed? tick it and submit again)", "subB": "Subscribe", "em": "you@example.com",
           "foot": "A summary of public data, not investment advice.", "src": "Sources: SEC EDGAR · Federal Reserve · BLS · BEA · NYSE",
           "noData": "Market data is not available right now.", "nobody": "No company had several insiders buying in these days.", "allday": "All day", "bj": "Beijing", "next": "next day",
           },
}
MODULES = [  # (href or None, zh name, zh desc, tw name, tw desc, en name, en desc)
    ("/insider/", "内部人", "高管和董事在公开市场的真实买卖，每天更新。", "內部人", "高管和董事在公開市場的真實買賣，每天更新。", "Insiders", "Open-market buying and selling by officers and directors, daily."),
    ("/earnings/", "财报", "重点公司的季度财报解读和三情景估值。", "財報", "重點公司的季度財報解讀和三情境估值。", "Earnings", "Quarterly earnings reviews with three valuation scenarios."),
    ("/calendar/", "日历", "CPI、议息、PCE 和休市，美东和北京时间。", "日曆", "CPI、利率決議、PCE 和休市，美東和北京時間。", "Calendar", "CPI, the Fed, PCE and holidays, in ET and Beijing time."),
    ("/market/volume/", "量价分析", "每天收盘后，大盘、板块和重点个股的涨跌和成交量。", "量價分析", "每天收盤後，大盤、板塊和重點個股的漲跌和成交量。", "Price and volume", "After every close: moves and volume for the index, sectors and key stocks."),
    ("/market/", "市场", "宏观仪表盘、板块轮动和长文研究。", "市場", "總經儀表板、板塊輪動和長文研究。", "Markets", "Macro dashboard, sector rotation and research notes."),
    ("/themes/", "产业链", "AI 和能源两条产业链，每一环最重要的美股公司。", "產業鏈", "AI 和能源兩條產業鏈，每一環最重要的美股公司。", "Supply chains", "The AI and energy chains: the key US-listed companies in each link."),
    ("/institutions/", "机构持仓", "13F 季度持仓和 13D 举牌，大资金在买什么。", "機構持股", "13F 季度持股和 13D 舉牌，大資金在買什麼。", "Institutions", "13F holdings and 13D stakes: what big money is buying."),
]
ROLE = [  # (pattern, zh, tw, en), in display order
    (r"chief executive|\bceo\b", "CEO", "CEO", "the CEO"),
    (r"chief financial|\bcfo\b", "CFO", "CFO", "the CFO"),
    (r"\bpresident\b", "总裁", "總裁", "the president"),
    (r"vice ?president|\bvp\b|\bevp\b|\bsvp\b", "副总裁", "副總裁", "vice presidents"),
    (r"chief|officer|general counsel|coo\b|cto\b", "高管", "高管", "officers"),
    (r"director|chair", "董事", "董事", "directors"),
    (r"10% owner", "大股东", "大股東", "10% owners"),
]

# ------------------------------------------------------------------ data
def money(v):
    v = abs(v)
    return f"${v/1e9:.1f}B" if v >= 1e9 else f"${v/1e6:.1f}M" if v >= 1e6 else f"${v/1e3:.0f}K"

def short_name(n):
    n = re.sub(r"[,.]?\s+(inc|corp|corporation|co|ltd|plc|lp|l\.p|n\.v|s\.a|llc|holdings?|group|/new|/de)\.?$", "", n.strip(), flags=re.I)
    n = re.sub(r"[,.]?\s+(inc|corp|corporation|ltd|plc|lp)\.?$", "", n, flags=re.I)
    return n if not n.isupper() or len(n) <= 5 else n.title()

def person(s):
    nm = s.split(" (")[0].strip()
    parts = nm.split()
    if nm.isupper() or nm.istitle():
        parts = [p.capitalize() if len(p) > 1 else p for p in parts]
        if len(parts) >= 2: parts = parts[1:] + parts[:1]  # SEC files "LAST FIRST M"
    return " ".join(p for p in parts if len(p) > 1 or p.isalpha())

def roles(buyers):
    text = " ".join(b.lower() for b in buyers)
    got, used = [], set()
    for pat, z, t, e in ROLE:
        if re.search(pat, text) and z not in used and not (z == "高管" and used & {"CEO", "CFO", "总裁", "副总裁"}):
            got.append((z, t, e)); used.add(z)
    return got[:3]

def chain_tags():
    tags = {}
    for path, zt, tt, et in ((os.path.join(ROOT, "stack", "data.json"), "AI 产业链", "AI 產業鏈", "AI chain"),
                             (os.path.join(ROOT, "energy", "data.json"), "能源产业链", "能源產業鏈", "Energy chain")):
        if not os.path.exists(path): continue
        d = json.load(open(path, encoding="utf-8"))
        seg = {s["id"]: s["name"] for s in d["segments"]}
        for c in d["companies"]:
            s = seg.get(c["seg"], {})
            tags.setdefault(c["t"], {"zh": f'{zt} · {s.get("zh", "")}', "tw": f'{tt} · {s.get("tw", "")}', "en": f'{et} · {s.get("en", "")}',
                                     "href": "/themes/ai/" if zt.startswith("AI") else "/themes/energy/"})
    return tags

def insider(days):
    recent = sorted(days, key=lambda d: d["date"])[-SIGNAL_DAYS:]
    agg = {}
    for d in recent:
        for c in d["companies"]:
            if not c.get("ticker"): continue
            a = agg.setdefault(c["ticker"], {"t": c["ticker"], "name": short_name(c["name"]), "b": 0, "s": 0, "buyers": {}, "sellers": set()})
            a["b"] += c.get("eff_buy_usd", 0); a["s"] += c.get("eff_sell_usd", 0)
            for b in c.get("buyers") or []: a["buyers"][str(b).split(" (")[0]] = str(b)
            for s in c.get("sellers") or []: a["sellers"].add(str(s))
    tags = chain_tags()
    clusters = sorted((a for a in agg.values() if len(a["buyers"]) >= 2 and a["b"] >= 100_000), key=lambda a: (-len(a["buyers"]), -a["b"]))[:3]
    top = max(agg.values(), key=lambda a: a["b"], default=None)
    sig = [dict(a, kind="cluster") for a in clusters]
    if top and top["b"] > 0 and top["t"] not in {a["t"] for a in clusters}: sig.append(dict(top, kind="big"))
    out = []
    for a in sig:
        buyers = list(a["buyers"].values())
        rs = roles(buyers)
        n = len(buyers)
        if a["kind"] == "cluster":
            title = {"zh": f'{a["name"]}：{n} 位内部人买入', "tw": f'{a["name"]}：{n} 位內部人買入', "en": f'{a["name"]}: {n} insiders bought'}
            zr = "、".join(r[0] for r in rs); tr = "、".join(r[1] for r in rs)
            er = ", ".join(r[2] for r in rs[:-1]) + (" and " if len(rs) > 1 else "") + (rs[-1][2] if rs else "")
            why = {"zh": f"近 5 个交易日在公开市场买入" + (f"，包括{zr}" if zr else "") + "。几个人同时买，比一个人买更值得留意。",
                   "tw": f"近 5 個交易日在公開市場買入" + (f"，包括{tr}" if tr else "") + "。幾個人同時買，比一個人買更值得留意。",
                   "en": "Open-market buys in the last 5 trading days" + (f", including {er}" if er else "") + ". Several insiders buying together means more than one."}
            kind = {"zh": "集群买入", "tw": "集群買入", "en": "Cluster buy"}
        else:
            who = person(buyers[0]) if buyers else ""
            rz = rs[0] if rs else ("内部人", "內部人", "an insider")
            title = {"zh": f'{a["name"]}：近 5 日最大的一笔买入', "tw": f'{a["name"]}：近 5 日最大的一筆買入', "en": f'{a["name"]}: the largest buy in 5 days'}
            why = {"zh": f"{rz[0]} {who} 在公开市场买入，是近 5 个交易日金额最大的有效买入。",
                   "tw": f"{rz[1]} {who} 在公開市場買入，是近 5 個交易日金額最大的有效買入。",
                   "en": f"{who} ({rz[2].replace('the ', '').rstrip('s')}) bought in the open market, the largest effective buy of the last 5 trading days."}
            kind = {"zh": "最大买入", "tw": "最大買入", "en": "Largest buy"}
        out.append({"t": a["t"], "title": title, "why": why, "kind": kind, "amt": money(a["b"]), "tag": tags.get(a["t"])})
    buys = [{"t": a["t"], "n": a["name"], "v": money(a["b"])} for a in sorted(agg.values(), key=lambda a: -a["b"])[:5] if a["b"] > 0]
    sells = [{"t": a["t"], "n": a["name"], "v": money(a["s"])} for a in sorted(agg.values(), key=lambda a: -a["s"])[:5] if a["s"] > 0]
    return recent[-1]["date"] if recent else "", out, buys, sells

# ------------------------------------------------------------------ page
CSS = """
.home{max-width:1200px;margin:0 auto;padding:24px 16px 48px;display:flex;flex-direction:column;gap:24px}
.lbl,h2.lbl{font-size:12px;font-weight:700;letter-spacing:.08em;color:var(--muted);text-transform:uppercase;margin:0;padding:0;border:0;line-height:1.5;font-family:var(--body)}
.box{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:20px 22px}
.box-h{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.box-h a,.more{font-size:14px;font-weight:700;text-decoration:none;white-space:nowrap}
.h2{margin:2px 0 4px;font:700 22px/1.3 var(--display);letter-spacing:-.01em;border:0;padding:0}
.num{font-variant-numeric:tabular-nums}
.up{color:#0b7a52}.dn{color:#c0362c}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]) .up{color:#4fd69c}:root:not([data-theme=light]) .dn{color:#ff8a80}}
.today{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap}
.today h1{margin:0;font:700 clamp(26px,3.4vw,34px)/1.15 var(--display)}
.pill{display:inline-flex;align-items:center;font-size:12.5px;font-weight:600;border-radius:999px;padding:3px 10px;line-height:1.4}
.pill.mk{background:color-mix(in srgb,var(--t2) 16%,transparent);color:var(--ink)}
.asof{color:var(--muted);font-size:13.5px}
.tiles{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin-top:12px}
.tile{display:block;background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:12px 14px;min-width:0;color:var(--ink);text-decoration:none}a.tile:hover{border-color:var(--accent)}
.tile .n{font-size:13px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tile .v{font-size:21px;font-weight:700;line-height:1.3}
.tile .c{font-size:13px;font-weight:600}.tile .c span{color:var(--faint);font-weight:400}
.tiles-msg{color:var(--muted);font-size:14px;margin:10px 0 0}
.grid{display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr);gap:24px;align-items:start}
.side{display:flex;flex-direction:column;gap:24px}
.sig-p{color:var(--muted);font-size:14px;margin:0 0 4px}
.sig{display:grid;grid-template-columns:64px minmax(0,1fr) auto;gap:16px;align-items:start;padding:16px 0;border-top:1px solid var(--line);color:var(--ink);text-decoration:none}
.sig:hover .st{color:var(--accent)}
.tk{font-weight:700;font-size:14.5px;background:var(--ink);color:var(--surface);border-radius:10px;text-align:center;padding:7px 0}
.st{font-weight:700;font-size:16px;line-height:1.45;display:block}
.sw{color:var(--muted);font-size:14px;line-height:1.6;display:block;margin:2px 0 6px}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{display:inline-flex;font-size:12px;font-weight:600;border-radius:999px;padding:2px 9px;line-height:1.5}
.chip.on{background:color-mix(in srgb,var(--accent) 14%,transparent);color:var(--accent)}
.chip.off{background:var(--surface-2);color:var(--faint)}
.chip.tag{background:var(--surface-2);color:var(--muted)}
.amt{font-weight:700;font-size:16px;white-space:nowrap}
.ev{display:grid;grid-template-columns:50px minmax(0,1fr);gap:12px;padding:11px 0;border-top:1px solid var(--line);margin-top:8px}
.ev .dt{text-align:center;border-radius:10px;padding:5px 0;line-height:1.25;background:color-mix(in srgb,var(--accent) 10%,transparent)}
.ev.mkt .dt{background:color-mix(in srgb,var(--t2) 16%,transparent)}
.ev .m{font-size:11.5px;color:var(--muted)}.ev .d{font-size:18px;font-weight:700}
.ev b{display:block;font-size:14.5px;line-height:1.45}.ev small{font-size:13px;color:var(--muted)}
.box.wide .vsum{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));column-gap:28px}
.earn3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0 28px}
.er{display:block;padding:11px 0;border-top:1px solid var(--line);margin-top:8px;color:var(--ink);text-decoration:none}
.er small{font-size:12.5px;color:var(--faint)}.er small b{color:var(--ink)}
.er span{display:block;font-weight:600;font-size:14.5px;line-height:1.5}.er:hover span{color:var(--accent)}
.two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:40px;margin-top:8px}
.lh{font-weight:700;font-size:14px;padding:6px 0}
.ir{display:flex;justify-content:space-between;align-items:baseline;gap:12px;padding:10px 0;border-top:1px solid var(--line);color:var(--ink);text-decoration:none}
.ir span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ir em{font-style:normal;color:var(--muted);font-size:14px}
.ir:hover b{color:var(--accent)}
.mods{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:12px}
.mod{display:flex;flex-direction:column;gap:3px;padding:15px 17px;background:var(--surface);border:1px solid var(--line);border-radius:14px;color:var(--ink);text-decoration:none;min-height:96px}
a.mod:hover{border-color:var(--accent)}
.mod b{font-size:15.5px}.mod span{color:var(--muted);font-size:13.5px;line-height:1.5}
.mod.soon{background:transparent;border-style:dashed}.mod.soon b::after{content:attr(data-soon);font-size:11.5px;font-weight:600;color:var(--faint);margin-left:8px}
.subband{background:var(--hero);color:#e8edf4;border-radius:18px;padding:24px 26px;display:flex;align-items:center;justify-content:space-between;gap:20px;flex-wrap:wrap}
.subband h2{margin:0 0 4px;font:700 21px/1.3 var(--display);color:#fff;border:0;padding:0}
.subband p{margin:0;color:#b8c3d4;font-size:14.5px;max-width:60ch}
.subf{display:flex;gap:8px;flex-wrap:wrap;max-width:440px}
.subf .dly{flex:1 1 100%;color:#b8c3d4;font-size:13.5px;display:flex;gap:8px;align-items:flex-start;cursor:pointer}.subf .dly input{margin-top:4px;width:auto;height:auto}
.subf input{height:44px;border-radius:10px;border:1px solid #2a3a55;background:#16243a;color:#fff;padding:0 14px;font:inherit;width:240px;max-width:100%}
.subf button{height:44px;border:0;border-radius:10px;background:#8ea6ff;color:#0e1726;font:inherit;font-weight:700;padding:0 22px;cursor:pointer}
.vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
@media (max-width:560px){.subf{width:100%}.subf input{flex:1 1 100%;width:auto}.subf button{flex:1 1 100%}}
.foot{max-width:1200px;margin:0 auto;padding:0 16px 40px;color:var(--faint);font-size:13px;display:flex;justify-content:space-between;gap:8px 16px;flex-wrap:wrap}
.pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px;align-items:start}
.chip.tag.up{color:#0b7a52}.chip.tag.dn{color:#c0362c}
.vsum{margin:8px 0 0;padding:0;list-style:none}.vsum li{padding:10px 0;border-top:1px solid var(--line);font-size:14px;line-height:1.6}
.empty{color:var(--muted);font-size:14px;padding:12px 0;border-top:1px solid var(--line)}
@media (max-width:900px){.box.wide .vsum{grid-template-columns:1fr}.earn3{grid-template-columns:1fr}.pair{grid-template-columns:1fr}.grid{grid-template-columns:1fr}.mods{grid-template-columns:repeat(2,minmax(0,1fr))}.two{grid-template-columns:1fr;gap:16px}}
@media (max-width:700px){.tiles{display:flex;overflow-x:auto;scrollbar-width:none;margin-inline:-16px;padding-inline:16px}.tiles::-webkit-scrollbar{display:none}.tile{flex:0 0 136px}}
@media (max-width:560px){.box{padding:16px}.sig{grid-template-columns:minmax(0,1fr) auto;gap:6px 12px}.tk{grid-column:1/-1;justify-self:start;padding:3px 10px;font-size:13px}.home{gap:18px;padding-top:18px}}
"""

def block(l, inner): return f'<div data-l="{l}" lang="{LOC[l]}">{inner}</div>'
def tri(fn): return "".join(block(l, fn(l)) for l in LANGS)
def E(s): return html.escape(str(s))

def sig_html(l, sigs, of=None, ol=None, inf=None):
    t = T[l]; of = of or {}; inf = inf or {}
    if not sigs: return f'<p class="empty">{t["nobody"]}</p>'
    out = []
    for s in sigs:
        tag = f'<span class="chip tag">{E(s["tag"][l])}</span>' if s.get("tag") else ""
        fl = of.get(s["t"], []); il = inf.get(s["t"], [])
        inst = (f'<span class="chip on">{t["srcInst"]}</span>' if il else f'<span class="chip off">{t["srcInst"]}</span>')
        intag = "".join(f'<span class="chip tag {"dn" if f == "fundsSell" else "up" if f == "fundsBuy" else ""}">{E(t["inst"][f])}</span>' for f in il)
        opt = ((f'<span class="chip on">{t["srcOpt"]}</span>' if fl else f'<span class="chip off">{t["srcOpt"]}</span>') if ol else "")
        optag = "".join(f'<span class="chip tag {"up" if f in ("callHeavy", "newCalls") else "dn" if f in ("putHeavy", "newPuts") else ""}">{E(ol[l][f])}</span>' for f in fl) if ol else ""
        out.append(f'<a class="sig" href="/s/{E(s["t"])}.html"><span class="tk">{E(s["t"])}</span><span><span class="st">{E(s["title"][l])}</span>'
                   f'<span class="sw">{E(s["why"][l])}</span><span class="chips"><span class="chip on">{t["srcIns"]}</span>{opt}'
                   f'<span class="chip off">{t["srcEarn"]}</span>{inst}<span class="chip tag">{E(s["kind"][l])}</span>{tag}{optag}{intag}</span></span>'
                   f'<span class="amt num up">{E(s["amt"])}</span></a>')
    return "".join(out)

def list_html(rows, cls):
    return "".join(f'<a class="ir" href="/s/{E(r["t"])}.html"><span><b>{E(r["t"])}</b> <em>{E(r["n"])}</em></span><b class="num {cls}">{E(r["v"])}</b></a>' for r in rows)

def body(asof, sigs, buys, sells, vol="", opt="", of=None, ol=None, inst="", inf=None):
    def today(l):
        t = T[l]
        a = asof.split("-")
        ad = (f"{int(a[1])}月{int(a[2])}日" if l != "en" else f"{'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()[int(a[1]) - 1]} {int(a[2])}") if len(a) == 3 else asof
        return (f'<div class="today"><h1 class="td-date">&nbsp;</h1><span class="pill mk td-mk" hidden></span>'
                f'<span class="asof">{t["asof"].format(a=ad)}<span class="td-mkasof"></span></span></div>')
    sig_box = tri(lambda l: f'<div class="box-h"><div><p class="lbl">{T[l]["sigL"]}</p><h2 class="h2">{T[l]["sigH"]}</h2></div><a href="/insider/">{T[l]["sigAll"]}</a></div>'
                            f'<p class="sig-p">{T[l]["sigP"]}</p>{sig_html(l, sigs, of, ol, inf)}')
    cal_h = tri(lambda l: f'<div class="box-h"><h2 class="lbl">{T[l]["calL"]}</h2><a href="/calendar/">{T[l]["calAll"]}</a></div>')
    earn_h = tri(lambda l: f'<div class="box-h"><h2 class="lbl">{T[l]["earnL"]}</h2><a href="/earnings/">{T[l]["earnAll"]}</a></div>')
    ins = tri(lambda l: f'<div class="box-h"><div><p class="lbl">{T[l]["insL"]}</p><h2 class="h2">{T[l]["insH"]}</h2></div><a href="/insider/">{T[l]["sigAll"]}</a></div>'
                        f'<div class="two"><div><div class="lh up">{T[l]["buy"]}</div>{list_html(buys, "up")}</div><div><div class="lh dn">{T[l]["sell"]}</div>{list_html(sells, "dn")}</div></div>')
    idx = {"zh": (1, 2), "tw": (3, 4), "en": (5, 6)}
    mods = tri(lambda l: f'<h2 class="lbl">{T[l]["expL"]}</h2><div class="mods">' + "".join(
        (f'<a class="mod" href="{m[0]}"><b>{m[idx[l][0]]}</b><span>{m[idx[l][1]]}</span></a>' if m[0]
         else f'<div class="mod soon"><b data-soon="{T[l]["soon"]}">{m[idx[l][0]]}</b><span>{m[idx[l][1]]}</span></div>') for m in MODULES) + "</div>")
    sub = tri(lambda l: f'<section class="subband"><div><h2>{T[l]["subH"]}</h2><p>{T[l]["subP"]}</p></div>'
                        f'<form class="subf" action="https://buttondown.com/api/emails/embed-subscribe/april-insider-stock" method="post" target="_blank" rel="noopener">'
                        f'<label class="vh" for="em-{l}">{T[l]["em"]}</label><input id="em-{l}" class="js-em" type="email" name="email" required autocomplete="email" placeholder="{T[l]["em"]}">'
                        f'<input type="hidden" name="embed" value="1"><button type="submit">{T[l]["subB"]}</button>'
                        + (f'<label class="dly"><input type="checkbox" name="tag" value="daily"> {T[l]["daily"]}</label>' if DAILY_OPTIN else "") + '</form></section>')
    foot = tri(lambda l: f'<footer class="foot"><span>April\'s Stock Atlas · {T[l]["foot"]}</span><span>{T[l]["src"]}</span></footer>')
    return (f'<main class="home"><section aria-label="Today">{tri(today)}<div class="tiles" id="tiles"></div><p class="tiles-msg" id="tiles-msg" hidden></p></section>'
            f'<div class="grid"><section class="box">{sig_box}</section><div class="side">'
            f'<section class="box">{cal_h}<div id="cal"></div></section></div></div>'
            + (f'<div class="pair">{vol}{opt}</div>' if vol and opt else (vol or opt).replace('<section class="box">', '<section class="box wide">', 1)) + inst.replace('<section class="box">', '<section class="box wide">', 1) +
            f'<section class="box">{ins}</section><section class="box">{earn_h}<div id="earn" class="earn3"></div></section>'
            f'<section>{mods}</section><div id="subscribe">{sub}</div></main>{foot}')

def inst_box(bi):
    if not bi: return ""
    rows = {l: bi.summary(l, 2) for l in LANGS}
    if not rows["zh"]: return ""
    inner = tri(lambda l: f'<div class="box-h"><h2 class="lbl">{T[l]["instL"]}</h2><a href="/institutions/">{T[l]["instAll"]}</a></div>'
                          '<ul class="vsum">' + "".join(f"<li>{x}</li>" for x in rows[l]) + "</ul>")
    return f'<section class="box">{inner}</section>'

def opt_box(bo):
    data = bo.load() if bo else None
    if not data: return ""
    inner = tri(lambda l: f'<div class="box-h"><h2 class="lbl">{T[l]["optL"]}</h2><a href="/options/">{T[l]["optAll"]}</a></div>'
                          '<ul class="vsum">' + "".join(f"<li>{x}</li>" for x in bo.summary(data, l, 3)) + "</ul>")
    return f'<section class="box">{inner}</section>'

def vol_box(bv):
    data = bv.load() if bv else None
    if not data: return ""
    inner = tri(lambda l: f'<div class="box-h"><h2 class="lbl">{T[l]["volL"]}</h2><a href="/market/volume/">{T[l]["volAll"]}</a></div>'
                          '<ul class="vsum">' + "".join(f"<li>{x}</li>" for x in (bv.home_points(l) or bv.summary(data, l, 3))) + "</ul>")
    return f'<section class="box">{inner}</section>'

JS = r"""<script>
(function(){
var T=__T__,EV=__EV__,CK=__CK__,VT=__VT__,VD=__VD__,MON=["January","February","March","April","May","June","July","August","September","October","November","December"];
function f(s,o){return s.replace(/\{(\w+)\}/g,function(_,k){return o[k]})}
function parts(ms,tz){var o={};new Intl.DateTimeFormat("en-US",{timeZone:tz,hourCycle:"h23",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"}).formatToParts(new Date(ms)).forEach(function(p){o[p.type]=p.value});return {d:o.year+"-"+o.month+"-"+o.day,t:(o.hour==="24"?"00":o.hour)+":"+o.minute}}
function etMs(d,t){var a=d.split("-").map(Number),b=t.split(":").map(Number),w=Date.UTC(a[0],a[1]-1,a[2],b[0],b[1]),u=w;for(var i=0;i<3;i++){var p=parts(u,"America/New_York"),x=p.d.split("-").map(Number),y=p.t.split(":").map(Number);u+=w-Date.UTC(x[0],x[1]-1,x[2],y[0],y[1])}return u}
function dow(d){var a=d.split("-").map(Number);return new Date(Date.UTC(a[0],a[1]-1,a[2])).getUTCDay()}
function md(l,d){var a=d.split("-").map(Number);return f(T[l].md,{m:a[1],d:a[2],M:MON[a[1]-1].slice(0,3)})}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
var TODAY=parts(Date.now(),"America/New_York").d,EIDX=null;
function evName(l,e){var c=CK[l],n=c.k[e.kind],a;
 if((e.kind==="cpi"||e.kind==="jobs"||e.kind==="ppi"||e.kind==="pce")&&e.ref){a=e.ref.split("-").map(Number);n+=f(c.ref,{m:a[1],M:MON[a[1]-1]})}
 else if(e.kind==="closed"&&e.name){n+=(l==="en"?": ":"：")+(c.hol[e.name]||e.name)}
 else if(e.kind==="fomc"&&e.sep){n+=" · "+c.sep}
 return n}
function evTime(l,e){var t=T[l];if(!e.time)return t.allday;var bj=parts(etMs(e.date,e.time),"Asia/Shanghai"),o=l==="en"?" (":"（",c=l==="en"?")":"）";
 return (e.kind==="early"?CK[l].earlyT+" ":"")+e.time+" ET"+o+t.bj+" "+(bj.d>e.date?t.next+" ":"")+bj.t+c}
function render(l){l=l||"zh";var t=T[l];
 document.querySelectorAll(".td-date").forEach(function(x){x.textContent=md(l,TODAY)+(l==="en"?", ":" ")+t.wd.split(",")[dow(TODAY)]});
 var mk=EV.filter(function(e){return e.date===TODAY&&(e.kind==="closed"||e.kind==="early")})[0];
 document.querySelectorAll(".td-mk").forEach(function(x){if(mk){x.hidden=false;x.textContent=mk.kind==="closed"?t.closed+(mk.name?" · "+(CK[l].hol[mk.name]||mk.name):""):t.early}else x.hidden=true});
 var up=EV.filter(function(e){return e.date>=TODAY}).slice(0,4);
 document.getElementById("cal").innerHTML=up.map(function(e){var a=e.date.split("-").map(Number);
  return '<div class="ev'+(e.kind==="closed"||e.kind==="early"?" mkt":"")+'"><div class="dt"><div class="m">'+(l==="en"?MON[a[1]-1].slice(0,3):a[1]+(l==="en"?"":"月"))+'</div><div class="d num">'+a[2]+'</div></div><div><b>'+esc(evName(l,e))+'</b><small class="num">'+esc(evTime(l,e))+'</small></div></div>'}).join("");
 var tb=document.getElementById("tiles"),tm=document.getElementById("tiles-msg");
 if(!VT.length){tb.innerHTML="";tm.hidden=false;tm.textContent=t.noData}
 else{tm.hidden=true;tb.innerHTML=VT.map(function(x){var cl=x.chg>=0?"up":"dn";
   return '<a class="tile" href="/market/volume/"><div class="n">'+esc(x.n[l])+' · '+esc(x.t)+'</div><div class="v num">'+x.close.toFixed(2)+'</div><div class="c num '+cl+'">'+(x.chg>=0?"▲ ":"▼ ")+Math.abs(x.chg).toFixed(2)+'% <span>'+t.d1+'</span></div></a>'}).join("");
  document.querySelectorAll(".td-mkasof").forEach(function(x){x.textContent=" · "+f(t.mkAsof,{a:md(l,VD)})})}
 var eb=document.getElementById("earn");
 if(EIDX){eb.innerHTML=EIDX.companies.slice().sort(function(a,b){return a.latestDate<b.latestDate?1:-1}).slice(0,3).map(function(c){var q=c.latest||"";
   return '<a class="er" href="/earnings/#'+encodeURIComponent(c.t)+'"><small><b>'+esc(c.t)+'</b> · '+esc(l==="en"?c.en:c.n)+' · '+esc(q.replace(/(\d{4})Q(\d)/,"$1 Q$2"))+'</small><span>'+esc(l==="en"?(c.en+" "+q.replace(/(\d{4})Q(\d)/,"Q$2 $1")+" earnings review"):c.headline)+'</span></a>'}).join("")}
}
window.onPageLang=(function(prev){return function(l){render(l);if(prev)prev(l)}})(window.onPageLang);
render(window.PAGE_LANG);
fetch("/earnings/data/index.json",{cache:"no-cache"}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(j){EIDX=j;render(window.PAGE_LANG)}).catch(function(){});
})();
</script>"""

# old homepage links: /#layer-3, /#NVDA (the AI chain lived at /) now go to /ai/
HASH_JS = """<script>(function(){var h=location.hash;if(/^#(layer-[\\w-]+|[A-Z][A-Z0-9.\\-]{0,11})$/.test(h))location.replace("/themes/ai/"+h)})();</script>"""

def build(out, days, pages, ba, bc, bv=None, bo=None, bi=None):
    """ba = build_articles module (FONTS, CSS, JS), bc = build_calendar module (event labels), bv = build_volume (summary)."""
    asof, sigs, buys, sells = insider(days)
    md = os.path.join(ROOT, "data", "macro.json")
    ev = json.load(open(md, encoding="utf-8"))["events"] if os.path.exists(md) else []
    ev = [e for e in ev if e["kind"] in ("fomc", "cpi", "jobs", "pce", "closed", "early")]
    ck = {l: {k: bc.T[l][k] for k in ("k", "ref", "hol", "sep", "earlyT")} for l in LANGS}
    tickers = sorted(s for s, _ in pages if not s.startswith("cik-"))
    titles = {l: T[l]["title"] for l in LANGS}
    asof_txt = asof
    vdata = bv.load() if bv else None
    vt = [{k: i[k] for k in ("t", "n", "close", "chg")} for s in ("SPY", "QQQ", "IWM", "TLT", "USO") for i in (vdata or {}).get("items", []) if i["t"] == s]
    vd = (vdata or {}).get("date", "")
    page = f"""<!doctype html>
<html lang="zh-CN" class="l-zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{E(titles['zh'])}</title>
{HASH_JS}
<meta name="description" content="{E(T['zh']['desc'])}">
<meta property="og:type" content="website"><meta property="og:site_name" content="April's Stock Atlas"><meta property="og:title" content="{E(titles['zh'])}">
<meta property="og:description" content="{E(T['zh']['desc'])}"><meta property="og:url" content="{SITE}/"><meta property="og:image" content="{SITE}/og.png">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{SITE}/og.png">
<link rel="canonical" href="{SITE}/"><link rel="alternate" type="application/rss+xml" title="April's Stock Atlas" href="{SITE}/feed.xml">
<link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)"><meta name="theme-color" content="#131c2a" media="(prefers-color-scheme: dark)">
<style>{ba.FONTS}{ba.CSS}{HEADER_CSS}{CSS}</style>
</head>
<body>
{header("home")}
{body(asof_txt, sigs, buys, sells, vol_box(bv), opt_box(bo), bo.flags_for(bo.load()) if bo and bo.load() else {}, {l: bo.T[l]["f"] for l in LANGS} if bo else None, inst_box(bi), bi.flags_for() if bi else {})}
{JS.replace("__VT__", json.dumps(vt, ensure_ascii=False)).replace("__VD__", json.dumps(vd)).replace("__T__", json.dumps(T, ensure_ascii=False)).replace("__EV__", json.dumps(ev, ensure_ascii=False, separators=(",", ":"))).replace("__CK__", json.dumps(ck, ensure_ascii=False))}
{HEADER_JS.replace("__TICKERS__", json.dumps(tickers, separators=(",", ":"))).replace("__PH__", json.dumps(SEARCH_PH, ensure_ascii=False))}
{ba.JS % json.dumps(titles, ensure_ascii=False)}
</body>
</html>
"""
    open(f"{out}/index.html", "w", encoding="utf-8").write(page)
    # the shared header (earnings repo switcher.js) checks searched tickers against this list
    with open(f"{out}/tickers.json", "w") as fh: json.dump(tickers, fh, separators=(",", ":"))
    return len(sigs)
