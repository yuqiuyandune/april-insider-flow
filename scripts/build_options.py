"""Build /options/ (期权异动) from data/options.json (written by scripts/fetch_options.py), and the short summary
the homepage shows. Rule-based text over the numbers; nothing written by hand.

    build(out, page)    -> "options/"   (page = build_articles.page, the shared site template)
    summary(data, l, n) -> list of HTML sentences for language l
    flags_for(data)     -> {ticker: [flags]} for the homepage's signals
"""
import os, json, html, datetime as dt

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data", "options.json")
LANGS = ("zh", "tw", "en")
LOC = {"zh": "zh-CN", "tw": "zh-TW", "en": "en"}
E = lambda s: html.escape(str(s))
MON = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

T = {
    "zh": {"title": "期权异动", "intro": "每个交易日收盘后，看大盘、主要资产、重点个股，以及内部人正在买入的公司的期权成交：看涨和看跌哪边多、钱花在哪些合约上、有没有大额新开仓。数据来自 Nasdaq 公开的期权链，按固定规则自动生成，不构成投资建议。",
           "sumH": "一句话总结", "topH": "今天最大的新开仓合约", "topP": "成交量是原有未平仓量 5 倍以上、金额够大、到期在 7 天到一年之间、价外（或价内不超过 10%）的合约。成交远超原有仓位，说明是新资金进场，而不是平掉旧仓。",
           "groups": {"index": "大盘", "asset": "主题与资产", "stock": "重点个股", "insider": "内部人正在买入的公司"},
           "cols": ["代码", "现价", "看涨成交", "看跌成交", "看跌/看涨比", "看涨金额", "看跌金额", "成交/未平仓", "比上个交易日", "标记"],
           "vsTot": "成交 {v}", "vsPcr": "比值 {a} → {b}", "fH": "昨天的大单，今天还在吗",
           "fP": "未平仓量每天收盘后才统计，所以今天的未平仓量包含了昨天的交易。昨天成交的合约，如果今天未平仓量增加了差不多同样多，说明是新开的仓位而且留下来了；如果几乎没增加，说明当天就平掉了，或者是一买一卖的对倒。",
           "fcols": ["代码", "方向", "行权价", "到期", "昨天成交", "昨天之前的未平仓", "今天的未平仓", "留下"],
           "kept_hi": "大部分留下了，是新开的仓位", "kept_mid": "留下了一部分", "kept_lo": "几乎没留下，当天就平掉了或是对倒",
           "fNone": "从下一个交易日开始，这里会显示前一天大单的去向。",
           "sFollow": "昨天 {t} {exp} 到期、行权价 {k} 的{cp}成交 {vol} 张，今天未平仓增加了 {added} 张（{kept}）：{verdict}。", "sPcr": "（上个交易日 {p}）",
           "ucols": ["代码", "方向", "行权价", "到期", "价外", "成交量", "原未平仓", "金额"],
           "call": "看涨", "put": "看跌", "days": "{n} 天", "date": "{m}月{d}日（{wd}）收盘", "wd": "周日,周一,周二,周三,周四,周五,周六",
           "mkt": "{date}：标普 500（SPY）期权的看跌/看涨比是 {a}{pa}，纳指 100（QQQ）是 {b}{pb}。",
           "line": "{n}（{t}）：{fl}", "biggest": "，最大一笔是 {exp} 到期、行权价 {k} 的{cp}，金额 {prem}", "quiet": "其余没有明显的异动。",
           "f": {"callHeavy": "看涨成交明显偏多", "putHeavy": "看跌成交明显偏多", "newCalls": "有大额新开看涨", "newPuts": "有大额新开看跌", "volSpike": "期权成交是平时的两倍以上"},
           "hist": "成交量和 20 日平均的比较需要先积累 10 个交易日的历史（目前 {n} 天），之后会自动加上。",
           "howH": "怎么读", "how": [
               ("看跌/看涨比", "看跌期权成交量除以看涨期权成交量。个股低于 0.4 偏看涨，高于 1.2 偏看跌；大盘 ETF 平时就有很多对冲，所以门槛放宽到 0.8 和 2.0。"),
               ("金额", "成交量 × 最新价 × 100，粗略代表花在期权上的钱。比单看张数更能看出大资金押在哪边。"),
               ("成交/未平仓", "当天成交量除以前一天的未平仓量。越高说明当天换手越多、新开的仓位越多。"),
               ("新开仓", "免费数据看不到每笔交易是买方还是卖方主动，所以「大额新开看涨」只说明有很多新看涨仓位，不保证是看涨的人在买。和内部人买卖、量价一起看更可靠。")],
           "src": "数据来源：Nasdaq 期权链（各合约的最新价、成交量、未平仓量）。每个交易日收盘后自动更新。"},
    "tw": {"title": "選擇權異動", "intro": "每個交易日收盤後，看大盤、主要資產、重點個股，以及內部人正在買入的公司的選擇權成交：買權和賣權哪邊多、錢花在哪些合約上、有沒有大額新建倉。資料來自 Nasdaq 公開的選擇權鏈，按固定規則自動產生，不構成投資建議。",
           "sumH": "一句話總結", "topH": "今天最大的新建倉合約", "topP": "成交量是原有未平倉量 5 倍以上、金額夠大、到期在 7 天到一年之間、價外（或價內不超過 10%）的合約。成交遠超原有部位，說明是新資金進場，而不是平掉舊倉。",
           "groups": {"index": "大盤", "asset": "主題與資產", "stock": "重點個股", "insider": "內部人正在買入的公司"},
           "cols": ["代碼", "現價", "買權成交", "賣權成交", "賣權/買權比", "買權金額", "賣權金額", "成交/未平倉", "比上個交易日", "標記"],
           "vsTot": "成交 {v}", "vsPcr": "比值 {a} → {b}", "fH": "昨天的大單，今天還在嗎",
           "fP": "未平倉量每天收盤後才統計，所以今天的未平倉量包含了昨天的交易。昨天成交的合約，如果今天未平倉量增加了差不多同樣多，說明是新建的部位而且留下來了；如果幾乎沒增加，說明當天就平掉了，或者是一買一賣的對敲。",
           "fcols": ["代碼", "方向", "履約價", "到期", "昨天成交", "昨天之前的未平倉", "今天的未平倉", "留下"],
           "kept_hi": "大部分留下了，是新建的部位", "kept_mid": "留下了一部分", "kept_lo": "幾乎沒留下，當天就平掉了或是對敲",
           "fNone": "從下一個交易日開始，這裡會顯示前一天大單的去向。",
           "sFollow": "昨天 {t} {exp} 到期、履約價 {k} 的{cp}成交 {vol} 口，今天未平倉增加了 {added} 口（{kept}）：{verdict}。", "sPcr": "（上個交易日 {p}）",
           "ucols": ["代碼", "方向", "履約價", "到期", "價外", "成交量", "原未平倉", "金額"],
           "call": "買權", "put": "賣權", "days": "{n} 天", "date": "{m}月{d}日（{wd}）收盤", "wd": "週日,週一,週二,週三,週四,週五,週六",
           "mkt": "{date}：標普 500（SPY）選擇權的賣權/買權比是 {a}{pa}，那指 100（QQQ）是 {b}{pb}。",
           "line": "{n}（{t}）：{fl}", "biggest": "，最大一筆是 {exp} 到期、履約價 {k} 的{cp}，金額 {prem}", "quiet": "其餘沒有明顯的異動。",
           "f": {"callHeavy": "買權成交明顯偏多", "putHeavy": "賣權成交明顯偏多", "newCalls": "有大額新建倉買權", "newPuts": "有大額新建倉賣權", "volSpike": "選擇權成交是平時的兩倍以上"},
           "hist": "成交量和 20 日平均的比較需要先累積 10 個交易日的歷史（目前 {n} 天），之後會自動加上。",
           "howH": "怎麼讀", "how": [
               ("賣權/買權比", "賣權成交量除以買權成交量。個股低於 0.4 偏看漲，高於 1.2 偏看跌；大盤 ETF 平時就有很多避險，所以門檻放寬到 0.8 和 2.0。"),
               ("金額", "成交量 × 最新價 × 100，粗略代表花在選擇權上的錢。比單看口數更能看出大資金押在哪邊。"),
               ("成交/未平倉", "當天成交量除以前一天的未平倉量。越高說明當天換手越多、新建的部位越多。"),
               ("新建倉", "免費資料看不到每筆交易是買方還是賣方主動，所以「大額新建倉買權」只說明有很多新買權部位，不保證是看漲的人在買。和內部人買賣、量價一起看更可靠。")],
           "src": "資料來源：Nasdaq 選擇權鏈（各合約的最新價、成交量、未平倉量）。每個交易日收盤後自動更新。"},
    "en": {"title": "Options activity", "intro": "After every session: options trading in the index, the main assets, key stocks and the companies insiders are buying. Calls or puts, where the money went, and whether large new positions were opened. Data from Nasdaq's public option chains, written by fixed rules; not investment advice.",
           "sumH": "In short", "topH": "Today's largest new positions", "topP": "Contracts that traded 5x or more their existing open interest, in real size, 7 days to a year out, out of the money (or at most 10% in it). Volume far above the existing position means new money, not old positions being closed.",
           "groups": {"index": "Index", "asset": "Themes and assets", "stock": "Key stocks", "insider": "Companies insiders are buying"},
           "cols": ["Ticker", "Price", "Call vol.", "Put vol.", "Put/call", "Call premium", "Put premium", "Vol./OI", "vs previous session", "Flags"],
           "vsTot": "volume {v}", "vsPcr": "ratio {a} → {b}", "fH": "Are yesterday's big trades still open?",
           "fP": "Open interest is counted after each close, so today's figure includes yesterday's trades. If a contract that traded heavily yesterday shows open interest up by about as much today, those were new positions and they stayed; if it barely moved, they were closed the same day or traded back and forth.",
           "fcols": ["Ticker", "Side", "Strike", "Expiry", "Yesterday's volume", "Open interest before", "Open interest now", "Kept"],
           "kept_hi": "mostly kept: new positions", "kept_mid": "partly kept", "kept_lo": "barely kept: closed the same day or crossed",
           "fNone": "From the next session on, this shows where the previous day's big trades went.",
           "sFollow": "Yesterday {t}'s {exp} {k} {cp}s traded {vol}; today open interest is up {added} ({kept}): {verdict}.", "sPcr": " (previous session {p})",
           "ucols": ["Ticker", "Side", "Strike", "Expiry", "OTM", "Volume", "Prior OI", "Premium"],
           "call": "call", "put": "put", "days": "{n}d", "date": "Close of {wd}, {M} {d}", "wd": "Sun,Mon,Tue,Wed,Thu,Fri,Sat",
           "mkt": "{date}: the put/call ratio was {a} on SPY{pa} and {b} on QQQ{pb}.",
           "line": "{n} ({t}): {fl}", "biggest": "; the largest was the {exp} {k} {cp} for {prem}", "quiet": "Nothing else stood out.",
           "f": {"callHeavy": "calls clearly outweighed puts", "putHeavy": "puts clearly outweighed calls", "newCalls": "large new call positions", "newPuts": "large new put positions", "volSpike": "options volume twice its usual level"},
           "hist": "Comparing volume with its 20-day average needs 10 sessions of history first (now {n}); it will appear automatically.",
           "howH": "How to read it", "how": [
               ("Put/call", "Put volume divided by call volume. For stocks below 0.4 leans bullish, above 1.2 leans bearish; index ETFs always carry a lot of hedging, so their thresholds are 0.8 and 2.0."),
               ("Premium", "Volume × last price × 100, roughly the money spent on the options. It shows where big money went better than contract counts."),
               ("Vol./OI", "The day's volume divided by the prior day's open interest. Higher means more turnover and more new positions."),
               ("New positions", "Free data does not show whether a trade was bought or sold, so \"large new call positions\" means many new call contracts, not that bulls were the buyers. It is more reliable next to insider trades and price and volume.")],
           "src": "Source: Nasdaq option chains (last price, volume and open interest of every contract). Updated automatically after every session."},
}

def load():
    return json.load(open(DATA, encoding="utf-8")) if os.path.exists(DATA) else None

def money(v):
    v = abs(v)
    return f"${v/1e9:.1f}B" if v >= 1e9 else f"${v/1e6:.1f}M" if v >= 1e6 else f"${v/1e3:.0f}K"

def md(iso, l):
    y, m, d = map(int, iso.split("-"))
    return f"{MON[m-1]} {d}" if l == "en" else f"{m}月{d}日"

def date_txt(day, l):
    y, m, d = map(int, day.split("-"))
    wd = T[l]["wd"].split(",")[(dt.date(y, m, d).weekday() + 1) % 7]
    return T[l]["date"].format(m=m, d=d, M=MON[m - 1], wd=wd)

def k_txt(k): return f"{k:g}"

def summary(data, l, n=4):
    t = T[l]; items = [i for i in data["items"] if i["date"] == data["date"]]
    by = {i["t"]: i for i in items}
    out = []
    if "SPY" in by and "QQQ" in by:
        pp = lambda x: t["sPcr"].format(p=x["vsPrev"]["pcr"]) if x.get("vsPrev") and x["vsPrev"].get("pcr") is not None else ""
        out.append(t["mkt"].format(date=date_txt(data["date"], l), a=by["SPY"]["pcr"], b=by["QQQ"]["pcr"], pa=pp(by["SPY"]), pb=pp(by["QQQ"])))
    fl = [f for f in data.get("follow", []) if f.get("kept") is not None]
    if fl:
        f = max(fl, key=lambda f: f["prem"])
        verdict = t["kept_hi"] if f["kept"] >= 0.5 else t["kept_mid"] if f["kept"] >= 0.2 else t["kept_lo"]
        out.append(t["sFollow"].format(t=E(f["t"]), exp=md(f["exp"], l), k=k_txt(f["k"]), cp=t["call"] if f["cp"] == "c" else t["put"],
                                       vol=f"{f['vol']:,}", added=f"{f['added']:,}", kept=f"{f['kept']:.0%}", verdict=verdict))
    picks = [i for i in sorted(items, key=lambda i: -i["score"]) if i["flags"]][:n]
    for i in picks:
        s = t["line"].format(n=E(i["n"][l]), t=E(i["t"]), fl=("、" if l != "en" else ", ").join(t["f"][f] for f in i["flags"]))
        u = next((u for u in i["unusual"] if ("newPuts" in i["flags"]) == (u["cp"] == "p")), i["unusual"][0] if i["unusual"] else None)
        if u: s += t["biggest"].format(exp=md(u["exp"], l), k=k_txt(u["k"]), cp=t["call"] if u["cp"] == "c" else t["put"], prem=money(u["prem"]))
        out.append(s + ("。" if l != "en" else "."))
    if len(picks) < n: out.append(t["quiet"])
    return out

def flags_for(data):
    return {i["t"]: i["flags"] for i in (data or {}).get("items", []) if i["date"] == data["date"]}

def urow(u, l):
    t = T[l]; c = u["cp"] == "c"
    return (f'<tr><td><b>{E(u["t"])}</b><small>{E(u["n"][l])}</small></td><td class="{"up" if c else "dn"}">{t["call"] if c else t["put"]}</td>'
            f'<td class="num">{k_txt(u["k"])}</td><td class="num">{md(u["exp"], l)} · {t["days"].format(n=u["dte"])}</td><td class="num">{u["otm"]:+.1f}%</td>'
            f'<td class="num">{u["vol"]:,}</td><td class="num">{u["oi"]:,}</td><td class="num"><b>{money(u["prem"])}</b></td></tr>')

def row(i, l):
    t = T[l]
    pcr = i["pcr"]; pw = min((pcr or 0) / 3, 1) * 100
    flags = "".join(f'<span class="vf {f}">{E(t["f"][f])}</span>' for f in i["flags"])
    tot = i["cprem"] + i["pprem"] or 1
    return (f'<tr><td><b>{E(i["t"])}</b><small>{E(i["n"][l])}</small></td><td class="num">{i["px"]:,.2f}</td>'
            f'<td class="num">{i["cv"]:,}</td><td class="num">{i["pv"]:,}</td>'
            f'<td><span class="pc"><span style="width:{pw:.0f}%"></span></span><span class="num">{pcr if pcr is not None else "–"}</span></td>'
            f'<td class="num up">{money(i["cprem"])}</td><td class="num dn">{money(i["pprem"])}</td>'
            f'<td class="num">{i["voi"] if i["voi"] is not None else "–"}</td><td class="vs">{vs_cell(i, l)}</td><td class="fl">{flags}</td></tr>')

def vs_cell(i, l):
    t = T[l]; v = i.get("vsPrev")
    if not v: return "–"
    tot = "–" if v.get("vol") is None else f'<b class="{"up" if v["vol"] >= 0 else "dn"}">{v["vol"]:+.0f}%</b>'
    pcr = t["vsPcr"].format(a=v["pcr"], b=i["pcr"]) if v.get("pcr") is not None and i.get("pcr") is not None else ""
    return f'<span class="num">{t["vsTot"].format(v=tot)}</span><small class="num">{pcr}</small>'

def frow(f, l):
    t = T[l]; c = f["cp"] == "c"; k = f.get("kept") or 0
    verdict = t["kept_hi"] if k >= 0.5 else t["kept_mid"] if k >= 0.2 else t["kept_lo"]
    cls = "up" if k >= 0.5 else "dn" if k < 0.2 else ""
    side = t["call"] if c else t["put"]
    return (f'<tr><td><b>{E(f["t"])}</b><small>{E(f["n"][l])}</small></td><td class="{"up" if c else "dn"}">{side}</td>'
            f'<td class="num">{k_txt(f["k"])}</td><td class="num">{md(f["exp"], l)}</td><td class="num">{f["vol"]:,}</td><td class="num">{f["oi"]:,}</td>'
            f'<td class="num">{f["oiNow"]:,}</td><td><b class="num {cls}">{k:.0%}</b><small>{verdict}</small></td></tr>')

CSS = """
.op-hero{margin:16px 0 18px}.op-hero p{color:var(--muted);max-width:72ch;margin:0}
.op-sum{background:var(--surface);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow);padding:18px 22px;margin:0 0 8px}
.op-sum h2{margin:0 0 6px;padding:0;border:0;font-size:13px;letter-spacing:.08em;color:var(--muted);font-family:var(--body)}
.op-sum ul{margin:0;padding-left:1.1em}.op-sum li{margin:0 0 6px;line-height:1.65}
.op-g h2{font-size:20px;margin:28px 0 6px;padding:0;border:0}.op-g>p{color:var(--muted);font-size:14px;margin:0 0 10px;max-width:80ch}
.op-t{overflow-x:auto;background:var(--surface);border:1px solid var(--line);border-radius:14px;-webkit-overflow-scrolling:touch}
.op-t table{min-width:960px;font-size:14px}
.op-t th{font-size:12.5px;color:var(--muted);font-weight:600;background:var(--surface-2)}
.op-t td{vertical-align:middle;padding:9px 12px}
.op-t td:first-child{white-space:nowrap}.op-t td:first-child small{display:block;color:var(--muted);font-weight:400;font-size:12.5px}
.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.up{color:#0b7a52}.dn{color:#c0362c}
@media (prefers-color-scheme:dark){.up{color:#4fd69c}.dn{color:#ff8a80}}
.pc{display:inline-block;width:56px;height:6px;border-radius:3px;background:color-mix(in srgb,#0b7a52 30%,transparent);vertical-align:middle;margin-right:8px;overflow:hidden}
.pc span{display:block;height:100%;background:#c0362c}
.op-t td small{display:block;color:var(--muted);font-size:12px;font-weight:400}.op-t td.vs b{font-weight:600}
.fl{min-width:150px}.vf{display:inline-block;font-size:12px;font-weight:600;border-radius:999px;padding:1px 8px;margin:2px 4px 2px 0;background:var(--surface-2);color:var(--muted);white-space:nowrap}
.vf.callHeavy,.vf.newCalls{background:color-mix(in srgb,#0b7a52 14%,transparent);color:inherit}
.vf.putHeavy,.vf.newPuts{background:color-mix(in srgb,#c0362c 14%,transparent);color:inherit}
.vf.volSpike{background:color-mix(in srgb,var(--accent) 14%,transparent);color:inherit}
.op-note{color:var(--faint);font-size:13px;margin:10px 0 0}
.op-how dl{display:grid;grid-template-columns:max-content 1fr;gap:6px 18px;font-size:14.5px;color:var(--muted)}.op-how dt{font-weight:700;color:var(--ink)}
@media (max-width:560px){.op-how dl{grid-template-columns:1fr}.op-how dd{margin:0 0 8px}}
.op-src{color:var(--faint);font-size:13px;margin:18px 0 40px}
"""

def build(out, page):
    data = load()
    if not data: return None
    blocks = []
    for l in LANGS:
        t = T[l]
        top = (f'<section class="op-g"><h2>{t["topH"]}</h2><p>{t["topP"]}</p><div class="op-t"><table><thead><tr>' + "".join(f"<th>{c}</th>" for c in t["ucols"]) +
               "</tr></thead><tbody>" + "".join(urow(u, l) for u in data["unusual"]) + "</tbody></table></div></section>") if data["unusual"] else ""
        fl = data.get("follow") or []
        ftable = ('<div class="op-t"><table><thead><tr>' + "".join(f"<th>{c}</th>" for c in t["fcols"]) + "</tr></thead><tbody>"
                  + "".join(frow(f, l) for f in fl) + "</tbody></table></div>") if fl else f'<p class="op-note">{t["fNone"]}</p>'
        follow = f'<section class="op-g"><h2>{t["fH"]}</h2><p>{t["fP"]}</p>{ftable}</section>'
        groups = "".join(
            f'<section class="op-g"><h2>{t["groups"][g]}</h2><div class="op-t"><table><thead><tr>' + "".join(f"<th>{c}</th>" for c in t["cols"]) +
            "</tr></thead><tbody>" + "".join(row(i, l) for i in sorted((i for i in data["items"] if i["g"] == g), key=lambda i: -(i["cprem"] + i["pprem"]))) + "</tbody></table></div></section>"
            for g in ("index", "asset", "stock", "insider") if any(i["g"] == g for i in data["items"]))
        how = "".join(f"<dt>{E(a)}</dt><dd>{E(d)}</dd>" for a, d in t["how"])
        hist = f'<p class="op-note">{t["hist"].format(n=data.get("histDays", 0))}</p>' if data.get("histDays", 0) < 10 else ""
        blocks.append(f'<div data-l="{l}" lang="{LOC[l]}"><div class="op-hero"><h1>{t["title"]}</h1><p>{t["intro"]}</p></div>'
                      f'<div class="op-sum"><h2>{t["sumH"]}</h2><ul>' + "".join(f"<li>{s}</li>" for s in summary(data, l)) + f"</ul></div>{hist}"
                      f'{top}{follow}{groups}<section class="op-how"><h2>{t["howH"]}</h2><dl>{how}</dl></section><p class="op-src">{t["src"]}</p></div>')
    body = f'<main>{"".join(blocks)}</main><style>{CSS}</style>'
    titles = {l: f'{T[l]["title"]} · April\'s Stock Atlas' for l in LANGS}
    os.makedirs(f"{out}/options", exist_ok=True)
    open(f"{out}/options/index.html", "w", encoding="utf-8").write(page("options/", titles, T["zh"]["intro"], body))
    with open(f"{out}/options/data.json", "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    return "options/"
