"""Build /market/volume/ (量价分析) from data/volume.json (written by scripts/fetch_volume.py), and the short
summary the homepage shows. Everything here is rule-based text over the numbers; nothing is written by hand.

    build(out, page)    -> "market/volume/"   (page = build_articles.page, the shared site template)
    summary(data, l, n) -> list of HTML sentences for language l (the market line first, then the n strongest)
"""
import os, json, html

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data", "volume.json")
LANGS = ("zh", "tw", "en")
LOC = {"zh": "zh-CN", "tw": "zh-TW", "en": "en"}
E = lambda s: html.escape(str(s))
MON = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

T = {
    "zh": {"title": "量价分析", "back": "← 市场观察",
           "intro": "每个交易日收盘后的复盘：先看盘中真正发生了什么，再看板块、成交量、资金去向、债市和 AI 产业链。每一句都来自固定的读盘规则，只在条件成立时才写，所以平淡的日子短、剧烈的日子长。数据来自 Nasdaq、CBOE 和美国财政部，不构成投资建议。",
           "sumH": "一句话总结", "groups": {"index": "大盘", "sector": "板块", "asset": "主题与资产", "stock": "重点个股"},
           "cols": ["代码", "收盘", "涨跌", "量比", "当日位置", "均线 20 · 50 · 200", "距一年高点", "近 30 日", "标记"],
           "breadth": "{u}/{s} 个板块上涨 · {a50}/{n} 站上 50 日线 · {a200}/{n} 站上 200 日线",
           "date": "{m}月{d}日（{wd}）收盘", "wd": "周日,周一,周二,周三,周四,周五,周六",
           "mkt": "{date}：标普 500 {dir} {chg}%，成交量是 20 日均量的 {rv} 倍；11 个板块里 {u} 个上涨。",
           "up": "涨", "down": "跌", "line": "{n}（{t}）{dir} {chg}%，量比 {rv}：{fl}。", "line0": "{n}（{t}）{dir} {chg}%，量比 {rv}。",
           "sep": "，", "quiet": "其余没有明显的放量或突破。",
           "f": {"volUp": "放量上涨", "volDown": "放量下跌", "thinUp": "缩量上涨，跟进的买盘不多", "above50": "站上 50 日线", "below50": "跌破 50 日线",
                 "above200": "站上 200 日线", "below200": "跌破 200 日线", "high52": "创一年新高", "low52": "创一年新低", "weakClose": "收在当天低位", "strongClose": "收在当天高位"},
           "howH": "怎么读", "how": [
               ("量比", "当天成交量除以前 20 个交易日的平均成交量。1.5 倍以上算放量，0.7 倍以下算缩量。放量说明参与的资金多，涨跌更有分量。"),
               ("当日位置", "收盘价在当天最高价和最低价之间的位置。靠右是收在高位，买盘撑到收盘；靠左是收在低位，卖压持续到收盘。"),
               ("均线", "三个圆点依次是 20 日、50 日、200 日均线，实心表示收盘价在均线之上。200 日线常被看作长期牛熊分界。"),
               ("标记", "放量上涨或下跌：涨跌幅超过门槛（ETF 1%，个股 2%）且量比 1.5 倍以上。站上或跌破：当天收盘从均线一侧穿到另一侧。一年新高或新低按收盘价算。")],
           "miss": "这些代码今天没有拿到数据：", "src": "数据来源：Nasdaq（每日开高低收和成交量）。每个交易日收盘后自动更新。"},
    "tw": {"title": "量價分析", "back": "← 市場觀察",
           "intro": "每個交易日收盤後的復盤：先看盤中真正發生了什麼，再看板塊、成交量、資金去向、債市和 AI 產業鏈。每一句都來自固定的讀盤規則，只在條件成立時才寫，所以平淡的日子短、劇烈的日子長。資料來自 Nasdaq、CBOE 和美國財政部，不構成投資建議。",
           "sumH": "一句話總結", "groups": {"index": "大盤", "sector": "板塊", "asset": "主題與資產", "stock": "重點個股"},
           "cols": ["代碼", "收盤", "漲跌", "量比", "當日位置", "均線 20 · 50 · 200", "距一年高點", "近 30 日", "標記"],
           "breadth": "{u}/{s} 個板塊上漲 · {a50}/{n} 站上 50 日線 · {a200}/{n} 站上 200 日線",
           "date": "{m}月{d}日（{wd}）收盤", "wd": "週日,週一,週二,週三,週四,週五,週六",
           "mkt": "{date}：標普 500 {dir} {chg}%，成交量是 20 日均量的 {rv} 倍；11 個板塊裡 {u} 個上漲。",
           "up": "漲", "down": "跌", "line": "{n}（{t}）{dir} {chg}%，量比 {rv}：{fl}。", "line0": "{n}（{t}）{dir} {chg}%，量比 {rv}。",
           "sep": "，", "quiet": "其餘沒有明顯的放量或突破。",
           "f": {"volUp": "放量上漲", "volDown": "放量下跌", "thinUp": "縮量上漲，跟進的買盤不多", "above50": "站上 50 日線", "below50": "跌破 50 日線",
                 "above200": "站上 200 日線", "below200": "跌破 200 日線", "high52": "創一年新高", "low52": "創一年新低", "weakClose": "收在當天低位", "strongClose": "收在當天高位"},
           "howH": "怎麼讀", "how": [
               ("量比", "當天成交量除以前 20 個交易日的平均成交量。1.5 倍以上算放量，0.7 倍以下算縮量。放量說明參與的資金多，漲跌更有分量。"),
               ("當日位置", "收盤價在當天最高價和最低價之間的位置。靠右是收在高位，買盤撐到收盤；靠左是收在低位，賣壓持續到收盤。"),
               ("均線", "三個圓點依次是 20 日、50 日、200 日均線，實心表示收盤價在均線之上。200 日線常被看作長期多空分界。"),
               ("標記", "放量上漲或下跌：漲跌幅超過門檻（ETF 1%，個股 2%）且量比 1.5 倍以上。站上或跌破：當天收盤從均線一側穿到另一側。一年新高或新低按收盤價算。")],
           "miss": "這些代碼今天沒有拿到資料：", "src": "資料來源：Nasdaq（每日開高低收和成交量）。每個交易日收盤後自動更新。"},
    "en": {"title": "Price and volume", "back": "← Market watch",
           "intro": "A recap after every session: first what really happened during the day, then sectors, volume, where the money went, bonds and the AI supply chain. Every sentence comes from a fixed reading rule and appears only when its condition holds, so quiet days are short and wild days are long. Data from Nasdaq, CBOE and the US Treasury; not investment advice.",
           "sumH": "In short", "groups": {"index": "Index", "sector": "Sectors", "asset": "Themes and assets", "stock": "Key stocks"},
           "cols": ["Ticker", "Close", "Change", "Rel. volume", "Close in range", "MA 20 · 50 · 200", "From 1-yr high", "30 days", "Flags"],
           "breadth": "{u}/{s} sectors up · {a50}/{n} above the 50-day · {a200}/{n} above the 200-day",
           "date": "Close of {wd}, {M} {d}", "wd": "Sun,Mon,Tue,Wed,Thu,Fri,Sat",
           "mkt": "{date}: the S&P 500 {dir} {chg}% on {rv}× its 20-day average volume; {u} of 11 sectors rose.",
           "up": "rose", "down": "fell", "line": "{n} ({t}) {dir} {chg}% on {rv}× volume: {fl}.", "line0": "{n} ({t}) {dir} {chg}% on {rv}× volume.",
           "sep": ", ", "quiet": "Nothing else stood out on volume or the moving averages.",
           "f": {"volUp": "up on heavy volume", "volDown": "down on heavy volume", "thinUp": "up on light volume, little follow-through", "above50": "back above the 50-day",
                 "below50": "below the 50-day", "above200": "back above the 200-day", "below200": "below the 200-day", "high52": "a one-year high", "low52": "a one-year low",
                 "weakClose": "closed near the day's low", "strongClose": "closed near the day's high"},
           "howH": "How to read it", "how": [
               ("Relative volume", "The day's volume divided by the average of the previous 20 sessions. 1.5× or more is heavy, under 0.7× is light. Heavy volume means more money took part, so the move carries more weight."),
               ("Close in range", "Where the close sits between the day's high and low. Right: closed near the high, buyers held on; left: closed near the low, selling lasted into the close."),
               ("Moving averages", "The three dots are the 20-, 50- and 200-day averages; filled means the close is above it. The 200-day is often read as the long-term trend line."),
               ("Flags", "Up or down on heavy volume: a move past the threshold (1% for ETFs, 2% for stocks) on 1.5× volume or more. Above or below: the close crossed the average that day. One-year highs and lows use closing prices.")],
           "miss": "No data today for: ", "src": "Source: Nasdaq daily open, high, low, close and volume. Updated automatically after every session."},
}

def load():
    return json.load(open(DATA, encoding="utf-8")) if os.path.exists(DATA) else None

def date_txt(day, l):
    y, m, d = map(int, day.split("-"))
    import datetime as dt
    wd = T[l]["wd"].split(",")[(dt.date(y, m, d).weekday() + 1) % 7]
    return T[l]["date"].format(m=m, d=d, M=MON[m - 1], wd=wd)

def summary(data, l, n=4):
    t = T[l]; items = [i for i in data["items"] if i["date"] == data["date"]]
    spy = next((i for i in items if i["t"] == "SPY"), None)
    out = []
    if spy:
        out.append(t["mkt"].format(date=date_txt(data["date"], l), dir=t["up"] if spy["chg"] >= 0 else t["down"], chg=f'{abs(spy["chg"]):.1f}',
                                   rv=f'{spy["rvol"]:.1f}', u=data["breadth"]["sectorsUp"]))
    picks = [i for i in sorted(items, key=lambda i: -i["score"]) if i["t"] != "SPY" and i["flags"]][:n]
    for i in picks:
        out.append(t["line"].format(n=E(i["n"][l]), t=E(i["t"]), dir=t["up"] if i["chg"] >= 0 else t["down"], chg=f'{abs(i["chg"]):.1f}',
                                    rv=f'{i["rvol"]:.1f}', fl=t["sep"].join(t["f"][f] for f in i["flags"])))
    if len(picks) < n: out.append(t["quiet"])
    return out

def spark(s):
    c = [x[1] for x in s]
    if len(c) < 2: return ""
    lo, hi = min(c), max(c); w, h = 88, 26
    pts = " ".join(f"{i * w / (len(c) - 1):.1f},{h - 2 - (x - lo) / ((hi - lo) or 1) * (h - 4):.1f}" for i, x in enumerate(c))
    cls = "up" if c[-1] >= c[0] else "dn"
    return f'<svg class="spk {cls}" width="{w}" height="{h}" viewBox="0 0 {w} {h}" aria-hidden="true"><polyline points="{pts}" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/></svg>'

def row(i, l):
    t = T[l]; up = i["chg"] >= 0
    rv = i["rvol"] or 0
    rvw = min(rv / 3, 1) * 100
    rvc = "hot" if rv >= 1.5 else "cold" if rv < 0.7 else ""
    dots = "".join(f'<i class="{"on" if str(n) in i["ma"] and i["ma"][str(n)] == 1 or i["ma"].get(n) == 1 else ""}" title="{n}"></i>' for n in (20, 50, 200))
    flags = "".join(f'<span class="vf {f}">{E(t["f"][f])}</span>' for f in i["flags"])
    return (f'<tr><td><b>{E(i["t"])}</b><small>{E(i["n"][l])}</small></td><td class="num">{i["close"]:,.2f}</td>'
            f'<td class="num {"up" if up else "dn"}">{"▲" if up else "▼"} {abs(i["chg"]):.2f}%</td>'
            f'<td><span class="rv {rvc}"><span style="width:{rvw:.0f}%"></span></span><span class="num">{rv:.2f}×</span></td>'
            f'<td><span class="ps"><span style="left:{i["pos"] * 100:.0f}%"></span></span></td>'
            f'<td><span class="ma">{dots}</span></td><td class="num">{i["hi52"]:+.1f}%</td><td>{spark(i["spark"])}</td><td class="fl">{flags}</td></tr>')

CSS = """
.vl-hero{margin:16px 0 18px}.vl-hero p{color:var(--muted);max-width:70ch;margin:0}
.vl-sum{background:var(--surface);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow);padding:18px 22px;margin:0 0 14px}
.vl-sum h2{margin:0 0 6px;padding:0;border:0;font-size:13px;letter-spacing:.08em;color:var(--muted);font-family:var(--body)}
.vl-sum ul{margin:0;padding-left:1.1em}.vl-sum li{margin:0 0 6px;line-height:1.65}
.vl-br{color:var(--muted);font-size:14px;margin:0 0 22px}
.vl-g h2{font-size:20px;margin:26px 0 10px;padding:0;border:0}
.vl-t{overflow-x:auto;background:var(--surface);border:1px solid var(--line);border-radius:14px;-webkit-overflow-scrolling:touch}
.vl-t table{min-width:900px;font-size:14px}
.vl-t th{font-size:12.5px;color:var(--muted);font-weight:600;background:var(--surface-2)}
.vl-t td{vertical-align:middle;padding:9px 12px}
.vl-t td:first-child{white-space:nowrap}.vl-t td:first-child small{display:block;color:var(--muted);font-weight:400;font-size:12.5px}
.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.up{color:#0b7a52}.dn{color:#c0362c}
@media (prefers-color-scheme:dark){.up{color:#4fd69c}.dn{color:#ff8a80}}
.rv{display:inline-block;width:56px;height:6px;border-radius:3px;background:var(--surface-2);vertical-align:middle;margin-right:8px;overflow:hidden}
.rv span{display:block;height:100%;background:var(--faint)}.rv.hot span{background:var(--accent)}.rv.cold span{background:var(--line)}
.ps{display:inline-block;position:relative;width:64px;height:6px;border-radius:3px;background:var(--surface-2);vertical-align:middle}
.ps span{position:absolute;top:-3px;width:12px;height:12px;margin-left:-6px;border-radius:50%;background:var(--ink)}
.ma{display:inline-flex;gap:6px}.ma i{width:11px;height:11px;border-radius:50%;border:2px solid var(--faint);box-sizing:border-box}.ma i.on{background:var(--accent);border-color:var(--accent)}
.spk{display:block}
.fl{min-width:150px}.vf{display:inline-block;font-size:12px;font-weight:600;border-radius:999px;padding:1px 8px;margin:2px 4px 2px 0;background:var(--surface-2);color:var(--muted);white-space:nowrap}
.vf.volUp,.vf.above50,.vf.above200,.vf.high52,.vf.strongClose{background:color-mix(in srgb,#0b7a52 14%,transparent);color:inherit}
.vf.volDown,.vf.below50,.vf.below200,.vf.low52,.vf.weakClose{background:color-mix(in srgb,#c0362c 14%,transparent);color:inherit}
.vl-how dl{display:grid;grid-template-columns:max-content 1fr;gap:6px 18px;font-size:14.5px;color:var(--muted)}.vl-how dt{font-weight:700;color:var(--ink)}
@media (max-width:560px){.vl-how dl{grid-template-columns:1fr}.vl-how dd{margin:0 0 8px}}
.vl-src{color:var(--faint);font-size:13px;margin:18px 0 40px}
"""

RECAPS = os.path.join(ROOT, "data", "recaps")
NOTES = os.path.join(ROOT, "data", "notes")

def _rt():
    import importlib.util
    spec = importlib.util.spec_from_file_location("recap_text", os.path.join(os.path.dirname(os.path.abspath(__file__)), "recap_text.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def recaps():
    """[(date, recap)] newest first"""
    if not os.path.isdir(RECAPS): return []
    out = []
    for f in sorted(os.listdir(RECAPS), reverse=True):
        if f.endswith(".json"): out.append((f[:-5], json.load(open(os.path.join(RECAPS, f), encoding="utf-8"))))
    return out

def note(day, l, md):
    """April's own notes for a day: data/notes/<date>.md (Simplified Chinese), optional .tw.md and .en.md; Simplified is used when a language is missing"""
    for name in ([f"{day}.{l}.md"] if l != "zh" else []) + [f"{day}.md"]:
        p = os.path.join(NOTES, name)
        if os.path.exists(p) and md: return md(open(p, encoding="utf-8").read())
    return ""

def home_points(l):
    """the homepage's price-and-volume box: the latest recap's points worth remembering"""
    rs = recaps()
    if not rs: return []
    rt = _rt(); d, r = rs[0]
    return [html.escape(x) for x in rt.key_points(r, l)]

RC_CSS = """
.rc-date{color:var(--muted);font-size:15px;margin:-4px 0 18px}
.rc-key{background:var(--surface);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow);padding:18px 22px;margin:0 0 10px}
.rc-key h2{margin:0 0 8px;padding:0;border:0;font-size:13px;letter-spacing:.08em;color:var(--muted);font-family:var(--body)}
.rc-key ol{margin:0;padding-left:1.3em}.rc-key li{margin:0 0 8px;line-height:1.7;font-weight:600}
.rc-s{margin:26px 0 0}.rc-s>h2{font-size:20px;margin:0 0 10px;padding:14px 0 0;border-top:1px solid var(--line)}
.rc-s h3{font-size:14px;margin:14px 0 6px;color:var(--muted)}
.rc-s p{margin:8px 0;line-height:1.75;max-width:80ch}
.rc-t{overflow-x:auto;background:var(--surface);border:1px solid var(--line);border-radius:14px;margin:0 0 6px}
.rc-t table{min-width:720px;font-size:14px}.rc-t td{padding:8px 12px}.rc-t td small{color:var(--muted);margin-left:6px;font-size:12px}
.rc-board{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:2px 24px;max-width:640px}
.bd{display:flex;gap:8px;align-items:baseline;padding:5px 0;border-bottom:1px solid var(--line);font-size:14px}.bd i{margin-left:auto;font-style:normal;font-weight:600}
.rc-chips{display:flex;flex-wrap:wrap;gap:6px 8px}
.vb{display:inline-flex;gap:6px;align-items:baseline;background:var(--surface);border:1px solid var(--line);border-radius:999px;padding:3px 10px;font-size:13.5px}
.vb i{font-style:normal}.vb i.hot{color:var(--accent);font-weight:700}.vb i.cold{color:var(--faint)}.vb a{text-decoration:none;color:var(--ink)}
.rc-two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px 24px}
.rc-notes{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:6px 18px}
.rc-note{color:var(--faint);font-size:12.5px;margin:18px 0 0}
.rc-small{color:var(--muted);font-size:13.5px;margin:0 0 8px}
.rc-five table{min-width:760px;font-size:13.5px}.rc-five th{white-space:nowrap}.rc-five thead th small{display:block;font-weight:400;color:var(--faint);font-size:11.5px}
.rc-five tbody th{text-align:left;font-weight:400}.rc-five tbody th b{display:block}.rc-five tbody th small{color:var(--muted);font-size:12px}
.rc-five td{text-align:right;padding:6px 10px;vertical-align:top}.rc-five td b{display:block;font-weight:600}.rc-five td i{display:block;font-style:normal;color:var(--muted);font-size:12.5px}
.rc-five td i.hot{color:var(--accent);font-weight:700}.rc-five td i.cold{color:var(--faint)}
.rc-five td:last-child,.rc-five tr>*:nth-last-child(2){border-right:0}.rc-five tbody td:nth-last-child(2){background:color-mix(in srgb,var(--accent) 5%,transparent)}
.rc-five .rk b{display:inline;margin-right:6px}.rc-five .rk i{display:inline;font-size:12px}
.rc-arch{margin:28px 0 0}.rc-arch h2{font-size:16px;margin:0 0 8px;padding:12px 0 0;border-top:1px solid var(--line)}
.rc-arch a{display:inline-block;margin:0 10px 6px 0;font-size:14px}.rc-arch b{display:inline-block;margin:0 10px 6px 0;font-size:14px}
.rc-all{margin:40px 0 0}.rc-all>h2{font-size:22px;padding-top:18px;border-top:2px solid var(--line)}
@media (max-width:560px){.rc-board,.rc-two{grid-template-columns:1fr}}
"""

def build(out, page, md=None):
    data = load(); rs = recaps()
    if not data and not rs: return None
    rt = _rt() if rs else None
    def archive(l, cur):
        u = rt.UI[l]
        links = "".join(f'<b>{rt.day_lbl(d, l)}</b>' if d == cur else f'<a href="/market/volume/{"" if i == 0 else d + "/"}">{rt.day_lbl(d, l)}</a>' for i, (d, _) in enumerate(rs[:30]))
        return f'<nav class="rc-arch" aria-label="{u["archive"]}"><h2>{u["archive"]}</h2>{links}</nav>'
    def recap_block(l, d, r):
        u = rt.UI[l]
        return f'<p class="rc-date">{rt.day_lbl(d, l)} · {u["title"]}</p>' + rt.sections(r, l, note(d, l, md)) + archive(l, d)
    blocks = []
    for l in LANGS:
        t = T[l]
        hero = f'<div class="vl-hero"><p class="crumb"><a href="/market/">{t["back"]}</a></p><h1>{t["title"]}</h1><p>{t["intro"]}</p></div>'
        rec = recap_block(l, rs[0][0], rs[0][1]) if rs else ""
        tables = ""
        if data:
            b = data["breadth"]
            groups = "".join(
                f'<section class="vl-g"><h2>{t["groups"][g]}</h2><div class="vl-t"><table><thead><tr>' + "".join(f"<th>{c}</th>" for c in t["cols"]) +
                "</tr></thead><tbody>" + "".join(row(i, l) for i in data["items"] if i["g"] == g) + "</tbody></table></div></section>"
                for g in ("index", "sector", "asset", "stock"))
            how = "".join(f"<dt>{E(a)}</dt><dd>{E(d)}</dd>" for a, d in t["how"])
            miss = f'<p class="vl-src">{t["miss"]}{E(", ".join(data["missing"]))}</p>' if data.get("missing") else ""
            tables = (f'<section class="rc-all"><h2>{(rt.UI[l]["table"] if rt else "")}</h2>'
                      f'<p class="vl-br">{t["breadth"].format(u=b["sectorsUp"], s=b["sectors"], a50=b["above50"], a200=b["above200"], n=b["n"])}</p>'
                      f'{groups}<section class="vl-how"><h2>{t["howH"]}</h2><dl>{how}</dl></section>{miss}</section>')
        blocks.append(f'<div data-l="{l}" lang="{LOC[l]}">{hero}{rec}{tables}<p class="vl-src">{t["src"]}</p></div>')
    body = f'<main>{"".join(blocks)}</main><style>{CSS}{RC_CSS}</style>'
    titles = {l: f'{T[l]["title"]} · April\'s Stock Atlas' for l in LANGS}
    os.makedirs(f"{out}/market/volume", exist_ok=True)
    open(f"{out}/market/volume/index.html", "w", encoding="utf-8").write(page("market/volume/", titles, T["zh"]["intro"], body))
    if data:
        with open(f"{out}/market/volume/data.json", "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    # one page per earlier recap
    for d, r in rs[1:60]:
        blocks = []
        for l in LANGS:
            t = T[l]
            blocks.append(f'<div data-l="{l}" lang="{LOC[l]}"><div class="vl-hero"><p class="crumb"><a href="/market/volume/">← {t["title"]}</a></p>'
                          f'<h1>{t["title"]}</h1></div>{recap_block(l, d, r)}<p class="vl-src">{t["src"]}</p></div>')
        titles = {l: f'{rt.day_lbl(d, l)} · {T[l]["title"]} · April\'s Stock Atlas' for l in LANGS}
        os.makedirs(f"{out}/market/volume/{d}", exist_ok=True)
        open(f"{out}/market/volume/{d}/index.html", "w", encoding="utf-8").write(
            page(f"market/volume/{d}/", titles, T["zh"]["intro"], f'<main>{"".join(blocks)}</main><style>{CSS}{RC_CSS}</style>'))
    return "market/volume/"
