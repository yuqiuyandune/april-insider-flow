"""Build /institutions/ (机构持仓) from data/stakes.json (13D/13G) and data/funds.json (13F), both written by
scripts/fetch_institutions.py, plus what the homepage needs. Rule-based text only.

    build(out, page)       -> "institutions/"
    summary(l, n)          -> list of HTML sentences for language l
    flags_for()            -> {ticker: ["stake13d" | "stake13g" | "fundsBuy" | "fundsSell"]} for the homepage signals
"""
import os, re, json, html, glob, datetime as dt

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
LANGS = ("zh", "tw", "en")
LOC = {"zh": "zh-CN", "tw": "zh-TW", "en": "en"}
E = lambda s: html.escape(str(s))
MON = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
RECENT = 30   # days of 13D/13G shown
# 13Gs from market makers and index-fund families say nothing about a view: their 5% comes from trading or index weights
NOISE = re.compile(r"jane street|citadel securities|g1 execution|susquehanna|virtu|hudson river|optiver|flow traders|two sigma securities|"
                   r"vanguard|blackrock|state street|global x|ishares|invesco|geode|northern trust|charles schwab|dimensional fund|first trust|vaneck|proshares|direxion", re.I)

T = {
    "zh": {"title": "机构持仓", "intro": "大资金在买什么、卖什么。13D/13G 是持股超过 5% 的大股东申报，几天内就要交，最及时；13F 是管理 1 亿美元以上的机构每季度的持仓报告，季度结束后 45 天内提交，所以看到的是一个多月前的仓位。数据全部来自 SEC，按固定规则整理，不构成投资建议。",
           "sumH": "一句话总结", "consH": "多家基金一起买、一起卖", "consP": "{q}，下面 20 家知名基金里，有两家以上新建仓或加仓（或清仓、减仓）同一只股票的。",
           "buyH": "▲ 一起买入", "sellH": "▼ 一起卖出", "funds": "{n} 家", "othbuy": "{n} 家卖出", "othsell": "{n} 家买入",
           "stakeH": "最新举牌（13D / 13G）", "stakeP": "近 {d} 天新提交的 13D（持股 5% 以上，可能要影响公司经营，常见于激进投资者）和 13G（持股 5% 以上的被动投资者）。关注名单里的公司排在前面；13D 的更新只列关注名单里的。做市商和指数基金因为交易或指数权重持有的 5% 不列。",
           "scols": ["申报日", "公司", "类型", "申报人", "持股比例", "说明"], "k13D": "13D 主动", "k13G": "13G 被动", "k13DA": "13D 更新", "watch": "关注名单",
           "fundH": "20 家基金的季度调仓（13F）", "fundP": "每家和上一季对比：新建仓、清仓、加仓（股数增加 20% 以上）和减仓（减少 20% 以上）。只含在美国上市的股票多头，不含空头、期权和债券。",
           "style": {"value": "价值", "macro": "宏观", "activist": "激进投资", "growth": "成长 / 科技", "multi": "多策略", "quality": "优质成长"},
           "tot": "持仓市值 {v} · {n} 只", "top": "前五大持仓", "new": "新建仓", "exit": "清仓", "add": "加仓", "trim": "减仓", "none": "无",
           "q": "{y} 年三季度", "qn": "{y} 年第 {q} 季度",
           "s1": "{q}，{n} 家基金新建仓或加仓 {name}（{t}），没有一家卖出。", "s1b": "{q}，{n} 家基金新建仓或加仓 {name}（{t}），{m} 家卖出。",
           "s2": "同一季度，{n} 家减持或清仓 {name}（{t}）。", "s3": "近 {d} 天有 {a} 份新的 13D 和 {b} 份新的 13G。", "s4": "关注名单里有人举牌的：{list}。",
           "howH": "怎么读", "how": [
               ("13D 和 13G", "持股超过 5% 时必须申报。打算影响公司经营（换董事、推动出售等）的交 13D，只是投资的交 13G。新的 13D 往往意味着有激进投资者进场。"),
               ("13F 的延迟", "13F 在季度结束后 45 天内提交，看到的是一个多月前的仓位，现在可能已经变了。它更适合看大方向，不适合跟单。"),
               ("13F 看不到的", "只列美国上市股票的多头。空头、大部分衍生品、海外股票和现金都不在里面，所以看不到完整的仓位和对冲。"),
               ("关注名单", "AI 和能源产业链、量价分析和期权页覆盖的公司，以及首页信号里的公司。")],
           "src": "数据来源：SEC EDGAR（13D、13G、13F 申报）；13F 里的 CUSIP 编码用 OpenFIGI 和 SEC 公司名单转换成股票代码。"},
    "tw": {"title": "機構持股", "intro": "大資金在買什麼、賣什麼。13D/13G 是持股超過 5% 的大股東申報，幾天內就要交，最及時；13F 是管理 1 億美元以上的機構每季的持股報告，季末後 45 天內提交，所以看到的是一個多月前的部位。資料全部來自 SEC，按固定規則整理，不構成投資建議。",
           "sumH": "一句話總結", "consH": "多家基金一起買、一起賣", "consP": "{q}，下面 20 家知名基金裡，有兩家以上新建倉或加碼（或出清、減碼）同一檔股票的。",
           "buyH": "▲ 一起買入", "sellH": "▼ 一起賣出", "funds": "{n} 家", "othbuy": "{n} 家賣出", "othsell": "{n} 家買入",
           "stakeH": "最新舉牌（13D / 13G）", "stakeP": "近 {d} 天新提交的 13D（持股 5% 以上，可能要影響公司經營，常見於激進投資人）和 13G（持股 5% 以上的被動投資人）。關注名單裡的公司排在前面；13D 的更新只列關注名單裡的。造市商和指數基金因為交易或指數權重持有的 5% 不列。",
           "scols": ["申報日", "公司", "類型", "申報人", "持股比例", "說明"], "k13D": "13D 主動", "k13G": "13G 被動", "k13DA": "13D 更新", "watch": "關注名單",
           "fundH": "20 家基金的季度調倉（13F）", "fundP": "每家和上一季對比：新建倉、出清、加碼（股數增加 20% 以上）和減碼（減少 20% 以上）。只含在美國上市的股票多頭，不含空頭、選擇權和債券。",
           "style": {"value": "價值", "macro": "總經", "activist": "激進投資", "growth": "成長 / 科技", "multi": "多策略", "quality": "優質成長"},
           "tot": "持股市值 {v} · {n} 檔", "top": "前五大持股", "new": "新建倉", "exit": "出清", "add": "加碼", "trim": "減碼", "none": "無",
           "q": "{y} 年第三季", "qn": "{y} 年第 {q} 季",
           "s1": "{q}，{n} 家基金新建倉或加碼 {name}（{t}），沒有一家賣出。", "s1b": "{q}，{n} 家基金新建倉或加碼 {name}（{t}），{m} 家賣出。",
           "s2": "同一季，{n} 家減碼或出清 {name}（{t}）。", "s3": "近 {d} 天有 {a} 份新的 13D 和 {b} 份新的 13G。", "s4": "關注名單裡有人舉牌的：{list}。",
           "howH": "怎麼讀", "how": [
               ("13D 和 13G", "持股超過 5% 時必須申報。打算影響公司經營（換董事、推動出售等）的交 13D，只是投資的交 13G。新的 13D 往往意味著有激進投資人進場。"),
               ("13F 的延遲", "13F 在季末後 45 天內提交，看到的是一個多月前的部位，現在可能已經變了。它更適合看大方向，不適合跟單。"),
               ("13F 看不到的", "只列美國上市股票的多頭。空頭、大部分衍生品、海外股票和現金都不在裡面，所以看不到完整的部位和避險。"),
               ("關注名單", "AI 和能源產業鏈、量價分析和選擇權頁涵蓋的公司，以及首頁信號裡的公司。")],
           "src": "資料來源：SEC EDGAR（13D、13G、13F 申報）；13F 裡的 CUSIP 編碼用 OpenFIGI 和 SEC 公司名單轉換成股票代碼。"},
    "en": {"title": "Institutional holdings", "intro": "What big money is buying and selling. 13D/13G filings come from holders of more than 5% and are due within days, so they are the most current; 13F is the quarterly holdings report of managers with $100M+, due 45 days after quarter end, so it shows positions more than a month old. All data from the SEC, sorted by fixed rules; not investment advice.",
           "sumH": "In short", "consH": "What several funds bought or sold together", "consP": "{q}: stocks that two or more of the 20 funds below opened or added to (or exited or trimmed).",
           "buyH": "▲ Bought together", "sellH": "▼ Sold together", "funds": "{n} funds", "othbuy": "{n} sold", "othsell": "{n} bought",
           "stakeH": "Latest 5%+ stakes (13D / 13G)", "stakeP": "13Ds (5%+ holders who may seek to influence the company, often activists) and 13Gs (passive 5%+ holders) filed in the last {d} days. Companies on the watch list come first; 13D amendments are listed for the watch list only. Market makers and index-fund families, whose 5% comes from trading or index weights, are left out.",
           "scols": ["Filed", "Company", "Type", "Filer", "Stake", "Note"], "k13D": "13D active", "k13G": "13G passive", "k13DA": "13D update", "watch": "Watch list",
           "fundH": "Quarterly moves of 20 funds (13F)", "fundP": "Each fund against its previous quarter: new positions, exits, adds (shares up 20%+) and trims (down 20%+). US-listed long stock positions only; no shorts, options or bonds.",
           "style": {"value": "Value", "macro": "Macro", "activist": "Activist", "growth": "Growth / tech", "multi": "Multi-strategy", "quality": "Quality growth"},
           "tot": "Holdings {v} · {n} stocks", "top": "Top five holdings", "new": "New", "exit": "Exited", "add": "Added", "trim": "Trimmed", "none": "none",
           "q": "Q3 {y}", "qn": "Q{q} {y}",
           "s1": "{q}: {n} funds opened or added to {name} ({t}) and none sold.", "s1b": "{q}: {n} funds opened or added to {name} ({t}); {m} sold.",
           "s2": "The same quarter {n} trimmed or exited {name} ({t}).", "s3": "{a} new 13Ds and {b} new 13Gs in the last {d} days.", "s4": "5%+ stakes in watch-list companies: {list}.",
           "howH": "How to read it", "how": [
               ("13D and 13G", "Required above 5% ownership. Holders who intend to influence the company (board seats, a sale) file a 13D; passive investors file a 13G. A new 13D often means an activist has arrived."),
               ("13F delay", "13Fs are due 45 days after quarter end, so the positions are more than a month old and may have changed. Good for the broad direction, not for copying trades."),
               ("What 13F leaves out", "Only long positions in US-listed stocks. Shorts, most derivatives, foreign stocks and cash are missing, so the full book and its hedges are not visible."),
               ("Watch list", "Companies in the AI and energy chains, the price-and-volume and options pages, and the homepage signals.")],
           "src": "Sources: SEC EDGAR (13D, 13G and 13F filings); 13F CUSIPs are turned into tickers with OpenFIGI and SEC's company list."},
}

def load(name):
    p = os.path.join(ROOT, "data", name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None

def watchlist():
    w = set()
    for p in ("stack/data.json", "energy/data.json"):
        d = load_path(os.path.join(ROOT, p))
        if d: w |= {c["t"] for c in d.get("companies", [])}
    for n in ("volume.json", "options.json"):
        d = load(n)
        if d: w |= {i["t"] for i in d.get("items", [])}
    return w

def load_path(p):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None

def money(v):
    v = abs(v)
    return f"${v/1e9:.1f}B" if v >= 1e9 else f"${v/1e6:.1f}M" if v >= 1e6 else f"${v/1e3:.0f}K"

def md(iso, l):
    y, m, d = map(int, iso.split("-"))
    return f"{MON[m-1]} {d}" if l == "en" else f"{m}月{d}日"

def qtxt(period, l):
    y, m, _ = map(int, period.split("-"))
    return T[l]["qn"].format(y=y, q=(m - 1) // 3 + 1)

def recent_stakes(stakes, days=RECENT):
    if not stakes: return []
    cut = (dt.date.fromisoformat(stakes["updated"]) - dt.timedelta(days=days)).isoformat()
    return [s for s in stakes["items"] if s["filed"] >= cut and not NOISE.search(s.get("filer") or "")]

def shown_stakes(stakes, watch):
    rs = recent_stakes(stakes)
    keep = [s for s in rs if s["kind"] in ("13D", "13G") or (s["kind"] == "13D/A" and s["t"] in watch)]
    keep.sort(key=lambda s: -(s["pct"] or 0))
    keep.sort(key=lambda s: s["filed"], reverse=True)
    keep.sort(key=lambda s: (s["t"] not in watch, s["kind"] != "13D"))   # stable: watch list first, then new 13Ds, newest first
    return keep[:60]

def fname(funds, cik, l):
    f = next((f for f in funds["funds"] if f["cik"] == cik), None)
    return f["n"][l].split("（")[0].split(" (")[0] if f else str(cik)

def summary(l, n=4):
    t = T[l]; out = []
    funds = load("funds.json"); stakes = load("stakes.json"); watch = watchlist()
    if funds and funds.get("period"):
        q = qtxt(funds["period"], l)
        for a in funds["buying"][:2]:
            nm = E(a["name"].title() if a["name"].isupper() else a["name"])
            out.append((t["s1"] if not a["sell"] else t["s1b"]).format(q=q, n=len(a["buy"]), m=len(a["sell"]), name=nm, t=E(a["t"])))
        if funds["selling"]:
            a = funds["selling"][0]; nm = E(a["name"].title() if a["name"].isupper() else a["name"])
            out.append(t["s2"].format(n=len(a["sell"]), name=nm, t=E(a["t"])))
    if stakes:
        rs = recent_stakes(stakes)
        out.append(t["s3"].format(d=RECENT, a=sum(s["kind"] == "13D" for s in rs), b=sum(s["kind"] == "13G" for s in rs)))
        w = sorted({s["t"] for s in rs if s["t"] in watch and s["kind"] in ("13D", "13G")})
        if w:
            more = ("等" if l != "en" else " and others") if len(w) > 8 else ""
            out.append(t["s4"].format(list=("、".join(w[:8]) if l != "en" else ", ".join(w[:8])) + more))
    return out[: n + 2]

def flags_for():
    out = {}
    stakes = load("stakes.json"); funds = load("funds.json")
    for s in recent_stakes(stakes):
        if s["kind"] in ("13D", "13G"): out.setdefault(s["t"], []).append("stake13d" if s["kind"] == "13D" else "stake13g")
    for a in (funds or {}).get("buying", []): out.setdefault(a["t"], []).append("fundsBuy")
    for a in (funds or {}).get("selling", []): out.setdefault(a["t"], []).append("fundsSell")
    return {k: sorted(set(v)) for k, v in out.items()}

def tk(r):
    return f'<a href="/s/{E(r["t"])}.html"><b>{E(r["t"])}</b></a>' if r.get("t") else f'<span class="nm">{E((r.get("name") or "").title())}</span>'

def fund_card(f, l):
    t = T[l]
    def lst(k, pct=False):
        rows = f[k][:6]
        if not rows: return f'<span class="none">{t["none"]}</span>'
        return "".join(f'<span class="it">{tk(r)}' + (f' <small>{r["chg"]*100:+.0f}%</small>' if pct and r.get("chg") is not None else "") + "</span>" for r in rows) \
               + (f'<small class="more">+{f["n_" + k] - len(rows)}</small>' if f["n_" + k] > len(rows) else "")
    top = "".join(f'<span class="it">{tk(r)} <small>{r["w"]*100:.1f}%</small></span>' for r in f["top"][:5])
    return (f'<article class="fc"><header><h3>{E(f["n"][l])}</h3><span class="st">{t["style"].get(f["style"], "")}</span></header>'
            f'<p class="ft">{t["tot"].format(v=money(f["total"]), n=f["positions"])} · {qtxt(f["period"], l)}</p>'
            f'<dl><dt>{t["top"]}</dt><dd>{top}</dd><dt class="up">{t["new"]}</dt><dd>{lst("new")}</dd><dt class="up">{t["add"]}</dt><dd>{lst("add", True)}</dd>'
            f'<dt class="dn">{t["trim"]}</dt><dd>{lst("trim", True)}</dd><dt class="dn">{t["exit"]}</dt><dd>{lst("exit")}</dd></dl></article>')

def other(a, key, l):
    o = a["sell" if key == "buy" else "buy"]
    return f'<small class="{"dn" if key == "buy" else "up"}">{T[l]["oth" + key].format(n=len(o))}</small>' if o else ""

def cons_table(rows, key, funds, l):
    t = T[l]
    return "".join(f'<tr><td>{tk(a)}<small>{E(a["name"].title() if a["name"].isupper() else a["name"])}</small></td><td class="num"><b>{t["funds"].format(n=len(a[key]))}</b>{other(a, key, l)}</td>'
                   f'<td class="fl">{E(("、" if l != "en" else ", ").join(fname(funds, c, l) for c in a[key]))}</td></tr>' for a in rows)

def stake_row(s, l, watch):
    t = T[l]
    kind = {"13D": t["k13D"], "13G": t["k13G"], "13D/A": t["k13DA"]}[s["kind"]]
    note = E((s.get("purpose") or "")[:180] + ("…" if s.get("purpose") and len(s["purpose"]) > 180 else ""))
    w = f'<span class="wl">{t["watch"]}</span>' if s["t"] in watch else ""
    filer = E(s["filer"]) + (f' <small>+{s["filers"] - 1}</small>' if s.get("filers", 1) > 1 else "")
    return (f'<tr><td class="num">{md(s["filed"], l)}</td><td><a href="/s/{E(s["t"])}.html"><b>{E(s["t"])}</b></a> {w}<small>{E(s["issuer"] or "")}</small></td>'
            f'<td><span class="kd k{s["kind"].replace("/", "")}">{kind}</span></td><td><a href="{E(s["url"])}" rel="noopener" target="_blank">{filer}</a></td>'
            f'<td class="num">{(str(s["pct"]) + "%") if s.get("pct") is not None else "–"}</td><td class="nt" lang="en">{note}</td></tr>')

CSS = """
.in-hero{margin:16px 0 18px}.in-hero p{color:var(--muted);max-width:76ch;margin:0}
.in-sum{background:var(--surface);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow);padding:18px 22px;margin:0 0 8px}
.in-sum h2,.in-lbl{margin:0 0 6px;padding:0;border:0;font-size:13px;letter-spacing:.08em;color:var(--muted);font-family:var(--body)}
.in-sum ul{margin:0;padding-left:1.1em}.in-sum li{margin:0 0 6px;line-height:1.65}
.in-g>h2{font-size:21px;margin:32px 0 6px;padding:0;border:0}.in-g>p{color:var(--muted);font-size:14px;margin:0 0 12px;max-width:84ch}
.in-two{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.in-t{overflow-x:auto;background:var(--surface);border:1px solid var(--line);border-radius:14px;-webkit-overflow-scrolling:touch}
.in-t table{font-size:14px}.in-t.wide table{min-width:900px}
.in-t th{font-size:12.5px;color:var(--muted);font-weight:600;background:var(--surface-2)}
.in-t td{vertical-align:top;padding:9px 12px}.in-t td small{display:block;color:var(--muted);font-weight:400;font-size:12.5px}
.in-t td a{text-decoration:none}.in-t .fl{font-size:13px;color:var(--muted)}.in-t .nt{font-size:12.5px;color:var(--muted);max-width:340px;line-height:1.5}
.in-t h3{margin:0;padding:10px 12px;font-size:14px;border-bottom:1px solid var(--line)}
.num{font-variant-numeric:tabular-nums;white-space:nowrap}
.up{color:#0b7a52}.dn{color:#c0362c}
@media (prefers-color-scheme:dark){.up{color:#4fd69c}.dn{color:#ff8a80}}
.kd{display:inline-block;font-size:12px;font-weight:600;border-radius:999px;padding:1px 8px;white-space:nowrap;background:var(--surface-2);color:var(--muted)}
.kd.k13D{background:color-mix(in srgb,var(--t2) 20%,transparent);color:var(--ink)}.kd.k13G{background:color-mix(in srgb,var(--accent) 12%,transparent);color:var(--ink)}
.wl{display:inline-block;font-size:11px;font-weight:700;border-radius:6px;padding:0 6px;background:var(--ink);color:var(--surface);vertical-align:1px}
.in-funds{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.fc{background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:16px 18px}
.fc header{display:flex;justify-content:space-between;align-items:baseline;gap:10px}.fc h3{margin:0;font-size:16px;line-height:1.35}
.fc .st{font-size:12px;color:var(--muted);white-space:nowrap}.fc .ft{color:var(--muted);font-size:13px;margin:2px 0 10px}
.fc dl{display:grid;grid-template-columns:max-content 1fr;gap:6px 12px;margin:0;font-size:13.5px}.fc dt{font-weight:700;white-space:nowrap}.fc dd{margin:0}
.fc .it{display:inline-block;margin:0 10px 2px 0;white-space:nowrap}.fc .it a{text-decoration:none;color:var(--ink)}.fc .it small{color:var(--muted)}
.fc .nm{color:var(--ink);font-weight:600}.fc .none{color:var(--faint)}.fc .more{color:var(--faint)}
.in-how dl{display:grid;grid-template-columns:max-content 1fr;gap:6px 18px;font-size:14.5px;color:var(--muted)}.in-how dt{font-weight:700;color:var(--ink)}
@media (max-width:760px){.in-two,.in-funds{grid-template-columns:1fr}.in-how dl{grid-template-columns:1fr}.in-how dd{margin:0 0 8px}}
.in-src{color:var(--faint);font-size:13px;margin:18px 0 40px}
"""

def build(out, page):
    funds = load("funds.json"); stakes = load("stakes.json")
    if not funds and not stakes: return None
    watch = watchlist()
    blocks = []
    for l in LANGS:
        t = T[l]; parts = []
        parts.append(f'<div class="in-hero"><h1>{t["title"]}</h1><p>{t["intro"]}</p></div>'
                     f'<div class="in-sum"><h2>{t["sumH"]}</h2><ul>' + "".join(f"<li>{s}</li>" for s in summary(l)) + "</ul></div>")
        if funds and funds.get("period"):
            q = qtxt(funds["period"], l)
            parts.append(f'<section class="in-g"><h2>{t["consH"]}</h2><p>{t["consP"].format(q=q)}</p><div class="in-two">'
                         f'<div class="in-t"><h3 class="up">{t["buyH"]}</h3><table><tbody>{cons_table(funds["buying"], "buy", funds, l)}</tbody></table></div>'
                         f'<div class="in-t"><h3 class="dn">{t["sellH"]}</h3><table><tbody>{cons_table(funds["selling"], "sell", funds, l)}</tbody></table></div></div></section>')
        if stakes:
            rows = "".join(stake_row(s, l, watch) for s in shown_stakes(stakes, watch))
            parts.append(f'<section class="in-g" id="stakes"><h2>{t["stakeH"]}</h2><p>{t["stakeP"].format(d=RECENT)}</p><div class="in-t wide"><table><thead><tr>'
                         + "".join(f"<th>{c}</th>" for c in t["scols"]) + f"</tr></thead><tbody>{rows}</tbody></table></div></section>")
        if funds:
            parts.append(f'<section class="in-g" id="funds"><h2>{t["fundH"]}</h2><p>{t["fundP"]}</p><div class="in-funds">'
                         + "".join(fund_card(f, l) for f in funds["funds"]) + "</div></section>")
        how = "".join(f"<dt>{E(a)}</dt><dd>{E(d)}</dd>" for a, d in t["how"])
        parts.append(f'<section class="in-how"><h2>{t["howH"]}</h2><dl>{how}</dl></section><p class="in-src">{t["src"]}</p>')
        blocks.append(f'<div data-l="{l}" lang="{LOC[l]}">{"".join(parts)}</div>')
    body = f'<main>{"".join(blocks)}</main><style>{CSS}</style>'
    titles = {l: f'{T[l]["title"]} · April\'s Stock Atlas' for l in LANGS}
    os.makedirs(f"{out}/institutions", exist_ok=True)
    open(f"{out}/institutions/index.html", "w", encoding="utf-8").write(page("institutions/", titles, T["zh"]["intro"], body))
    return "institutions/"
