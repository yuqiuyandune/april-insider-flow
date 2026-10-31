#!/usr/bin/env python3
"""Weekly digest email for April's Stock Atlas, built from the verified day files.

Usage: weekly.py DAYS_DIR [--end YYYY-MM-DD] [--lang both|en|zh] [--out FILE.json]   (both = Chinese first, then English)
Writes {"subject", "body" (Markdown), "week_from", "week_to"}; the week is the 7 calendar days ending --end
(default: the latest filing date in DAYS_DIR), grouped by SEC filing date.  Uses only "effective" trades:
officers' and directors' open-market buys/sells, excluding 10b5-1 plans, offerings, exercise-day sales etc.
"""
import argparse, datetime as dt, glob, json, os, re

SITE = "https://april-insider-flow.com"
SEC_ZH = {"Basic Materials": "基础材料", "Communication Services": "通信服务", "Consumer Cyclical": "周期性消费",
          "Consumer Defensive": "防御性消费", "Energy": "能源", "Financial Services": "金融服务", "Healthcare": "医疗保健",
          "Industrials": "工业", "Real Estate": "房地产", "Technology": "科技", "Utilities": "公用事业", "Unclassified": "未分类"}


def money(v, sign=False):
    a = abs(v); s = "−" if v < 0 else ("+" if sign and v > 0 else "")
    if a >= 1e9: return f"{s}${a/1e9:.2f}B"
    if a >= 1e6: return f"{s}${a/1e6:.1f}M"
    if a >= 1e3: return f"{s}${a/1e3:.0f}K"
    return "$0" if a == 0 else f"{s}${a:.0f}"


def slug(c):
    t = re.split(r"[,\s]+", (c.get("ticker") or "").strip().upper())[0]
    if t and re.fullmatch(r"[A-Z0-9.\-]{1,12}", t): return t
    return f"cik-{int(c['cik'])}" if c.get("cik") else None


def first_owner(w):
    """First owner in "A (role; role); B (role)" -- splits on '; ' only outside parentheses."""
    w = w or ""; depth = 0
    for i, ch in enumerate(w):
        depth += (ch == "(") - (ch == ")")
        if depth == 0 and w.startswith("; ", i): return w[:i]
    return w


def owner(w):
    f = first_owner(w)
    m = re.match(r"^(.*?)\s*\((.*)\)\s*$", f)
    return (m.group(1).strip(), m.group(2).strip().replace("; ", ", ")) if m else (f.strip(), "")


def load(d):
    out = []
    for p in sorted(glob.glob(os.path.join(d, "*.json"))):
        x = json.load(open(p, encoding="utf-8"))
        if isinstance(x, dict) and "data" in x and "sectors" not in x: x = x["data"]
        if isinstance(x, dict) and x.get("date") and x.get("sectors"): out.append(x)
    return sorted(out, key=lambda x: x["date"])


def totals(days):
    b = sum(s.get("buy_eff_usd", 0) or 0 for d in days for s in d["sectors"])
    s_ = sum(s.get("sell_eff_usd", 0) or 0 for d in days for s in d["sectors"])
    return b, s_


def digest(all_days, end, lang, news=""):
    end_d = dt.date.fromisoformat(end)
    frm = (end_d - dt.timedelta(days=6)).isoformat()
    pfrm, pto = (end_d - dt.timedelta(days=13)).isoformat(), (end_d - dt.timedelta(days=7)).isoformat()
    wk = [d for d in all_days if frm <= d["date"] <= end]
    pw = [d for d in all_days if pfrm <= d["date"] <= pto]
    if not wk: return None
    zh = lang == "zh"
    b, s_ = totals(wk); pb, ps = totals(pw)
    # sectors
    sec = {}
    for d in wk:
        for s in d["sectors"]:
            e = sec.setdefault(s["sector"], [0, 0]); e[0] += s.get("buy_eff_usd", 0) or 0; e[1] += s.get("sell_eff_usd", 0) or 0
    sn = sorted(((v[0] - v[1], k) for k, v in sec.items() if v[0] or v[1]))
    # companies
    cos = {}
    for d in wk:
        for c in d["companies"]:
            k = c.get("cik") or c.get("ticker")
            e = cos.setdefault(k, {"c": c, "eb": 0, "es": 0, "buys": []})
            e["eb"] += c.get("eff_buy_usd", 0) or 0; e["es"] += c.get("eff_sell_usd", 0) or 0
            for f in c.get("filings") or []:
                if f.get("eff_buy"): e["buys"].append((d["date"], f))
    # clusters: >=2 different officers/directors with effective buys in the 30 days to `end`, at least one new buy this week,
    # excluding "programs" (everyone bought on the same day at the same price)
    c30 = (end_d - dt.timedelta(days=29)).isoformat()
    hist = {}
    for d in all_days:
        if not (c30 <= d["date"] <= end): continue
        for c in d["companies"]:
            for f in c.get("filings") or []:
                if f.get("eff_buy"):
                    k = c.get("cik") or c.get("ticker")
                    h = hist.setdefault(k, {"c": c, "people": {}, "usd": 0, "keys": set(), "new": False})
                    n, _ = owner(f.get("who")); h["people"][n] = h["people"].get(n, 0) + f["eff_buy"]; h["usd"] += f["eff_buy"]
                    px = round(f["eff_buy"] / f["buy_sh"], 2) if f.get("buy_sh") else None
                    h["keys"].add((f.get("tx_date") or d["date"], px))
                    if d["date"] >= frm: h["new"] = True
    clusters = sorted((h for h in hist.values() if len(h["people"]) >= 2 and h["new"] and len(h["keys"]) > 1), key=lambda h: (-len(h["people"]), -h["usd"]))
    # biggest buys and holding increases (single filings)
    fl = [(d, c, f) for d in wk for c in d["companies"] for f in c.get("filings") or [] if f.get("eff_buy")]
    big = sorted(fl, key=lambda x: -x[2]["eff_buy"])[:5]
    def hold(f):
        if f.get("hold_post") is None or not f.get("buy_sh"): return None
        pre = f.get("hold_pre")
        return float("inf") if not pre else f["buy_sh"] / pre
    inbig = {id(x[2]) for x in big}
    hold_up = sorted((x for x in fl if id(x[2]) not in inbig and (hold(x[2]) or 0) >= 0.10 and x[2]["eff_buy"] >= 100_000), key=lambda x: -(hold(x[2]) if hold(x[2]) != float("inf") else 1e9))[:5]
    sellers = sorted((e for e in cos.values() if e["es"] > e["eb"]), key=lambda e: -(e["es"] - e["eb"]))[:3]
    f144 = [x for d in wk for x in d.get("f144") or [] if not (x.get("shares") and x.get("usd") and x["usd"] / x["shares"] > 10000)]
    f144 = sorted(f144, key=lambda x: -(x.get("usd") or 0))[:3]

    L = (lambda c: f"[{c.get('ticker') or c.get('name')}]({SITE}/s/{slug(c)}.html)" if slug(c) else (c.get("ticker") or c.get("name")))
    SN = (lambda k: SEC_ZH.get(k, k)) if zh else (lambda k: k)
    def md(iso):
        x = dt.date.fromisoformat(iso); return f"{x.month}月{x.day}日" if zh else f"{x:%b} {x.day}"
    def pct(x, y): return None if not y else (x / y - 1) * 100
    def hp(f):
        h = hold(f); return ("新建仓" if zh else "new position") if h == float("inf") else f"+{h*100:.0f}%"
    net = b - s_
    rng = f"{md(frm)} – {md(end)}"
    out = []
    if zh:
        subject = f"本周内部人动向（{rng}）：有效{'净买入' if net >= 0 else '净卖出'} {money(abs(net))}"
        out.append(f"你好，这是 **{rng}** 的内部人买卖周报。只看最有信号意义的交易：高管和董事在公开市场自己掏钱的买卖，已排除计划内交易、认购、行权卖出等。")
        if news: out.append(news)
        out.append("## 一句话")
        line = f"高管和董事本周有效买入 **{money(b)}**，有效卖出 **{money(s_)}**，{'净买入' if net >= 0 else '净卖出'} **{money(abs(net))}**。"
        if pw and pb and ps: line += f" 较上周：买入 {pct(b, pb):+.0f}%，卖出 {pct(s_, ps):+.0f}%。"
        out.append(line)
        out.append("## 板块")
        if sn and sn[-1][0] > 0: out.append(f"- 净买入最多：**{SN(sn[-1][1])}** {money(sn[-1][0], True)}")
        if len(sn) > 1 and sn[-2][0] > 0: out.append(f"- 其次：{SN(sn[-2][1])} {money(sn[-2][0], True)}")
        if sn and sn[0][0] < 0: out.append(f"- 净卖出最多：**{SN(sn[0][1])}** {money(sn[0][0], True)}")
        if clusters:
            out.append("## 集群买入")
            out.append("近 30 天内有 2 位以上高管或董事各自买入，且本周有新的买入：")
            for h in clusters[:5]:
                ps_ = "、".join(list(h["people"])[:3]) + (" 等" if len(h["people"]) > 3 else "")
                out.append(f"- {L(h['c'])} {h['c'].get('name')} · **{len(h['people'])} 人**，合计 {money(h['usd'])}（{ps_}）")
        out.append("## 最大的买入")
        for d, c, f in big:
            n, r = owner(f.get("who")); h = hold(f)
            out.append(f"- {L(c)} {c.get('name')} · {n}（{r}）买入 **{money(f['eff_buy'])}**{'，持股 ' + hp(f) if h is not None and h >= 0.05 else ''}")
        if hold_up:
            out.append("## 持股大幅增加")
            for d, c, f in hold_up:
                n, r = owner(f.get("who"))
                out.append(f"- {L(c)} · {n}（{r}）" + (f"**新建仓**，买入 {money(f['eff_buy'])}" if hold(f) == float("inf") else f"持股 **{hp(f)}**，买入 {money(f['eff_buy'])}"))
        if sellers:
            out.append("## 卖出最多")
            for e in sellers:
                out.append(f"- {L(e['c'])} {e['c'].get('name')} · 有效净卖出 {money(e['es'] - e['eb'])}")
        if f144:
            out.append("## 拟出售（Form 144）")
            for x in f144:
                out.append(f"- {x.get('ticker') or x.get('name')} · {x.get('person')} 计划出售约 {money(x.get('usd') or 0)}")
        out.append(f"## 更多\n每个交易日的完整数据、各板块趋势和每家公司的逐笔申报都在网站上：**[april-insider-flow.com]({SITE}/zh/)**")
        out.append("---\n*数据来自 SEC EDGAR，每天与原始申报核对。本邮件仅供参考和研究，不构成投资建议，也不推荐买卖任何股票。内部人买卖的原因很多，请自行研究判断。*")
    else:
        subject = f"Insider flow this week ({rng}): effective net {'buying' if net >= 0 else 'selling'} {money(abs(net))}"
        out.append(f"Hi, here is the insider trading digest for **{rng}**. It covers the trades with the most signal: officers and directors buying or selling their own company's shares in the open market, excluding planned (10b5-1) trades, offerings and exercise-day sales.")
        if news: out.append(news)
        out.append("## The week in one line")
        line = f"Officers and directors made **{money(b)}** of effective purchases and **{money(s_)}** of effective sales, net **{money(net, True)}**."
        if pw and pb and ps: line += f" Versus last week: buying {pct(b, pb):+.0f}%, selling {pct(s_, ps):+.0f}%."
        out.append(line)
        out.append("## Sectors")
        if sn and sn[-1][0] > 0: out.append(f"- Most net buying: **{sn[-1][1]}** {money(sn[-1][0], True)}")
        if len(sn) > 1 and sn[-2][0] > 0: out.append(f"- Next: {sn[-2][1]} {money(sn[-2][0], True)}")
        if sn and sn[0][0] < 0: out.append(f"- Most net selling: **{sn[0][1]}** {money(sn[0][0], True)}")
        if clusters:
            out.append("## Cluster buys")
            out.append("Two or more officers or directors bought in the last 30 days, with a new purchase this week:")
            for h in clusters[:5]:
                ps_ = ", ".join(list(h["people"])[:3]) + (" and others" if len(h["people"]) > 3 else "")
                out.append(f"- {L(h['c'])} {h['c'].get('name')} · **{len(h['people'])} insiders**, {money(h['usd'])} in total ({ps_})")
        out.append("## Largest purchases")
        for d, c, f in big:
            n, r = owner(f.get("who")); h = hold(f)
            out.append(f"- {L(c)} {c.get('name')} · {n} ({r}) bought **{money(f['eff_buy'])}**{', holding ' + hp(f) if h is not None and h >= 0.05 else ''}")
        if hold_up:
            out.append("## Big holding increases")
            for d, c, f in hold_up:
                n, r = owner(f.get("who"))
                out.append(f"- {L(c)} · {n} ({r}) " + (f"opened a **new position** with a {money(f['eff_buy'])} purchase" if hold(f) == float("inf") else f"raised their holding **{hp(f)}** with a {money(f['eff_buy'])} purchase"))
        if sellers:
            out.append("## Most selling")
            for e in sellers:
                out.append(f"- {L(e['c'])} {e['c'].get('name')} · effective net sales {money(e['es'] - e['eb'])}")
        if f144:
            out.append("## Planned sales (Form 144)")
            for x in f144:
                out.append(f"- {x.get('ticker') or x.get('name')} · {x.get('person')} plans to sell about {money(x.get('usd') or 0)}")
        out.append(f"## More\nFull daily data, sector trends and every company's filings are on the website: **[april-insider-flow.com]({SITE}/en/)**")
        out.append("---\n*Data from SEC EDGAR, checked daily against the original filings. This email is for information and research only. It is not investment advice and does not recommend buying or selling any stock. Insiders trade for many reasons; please do your own research.*")
    body = "\n\n".join(out).replace("\n\n- ", "\n- ")
    return {"subject": subject, "body": body, "week_from": frm, "week_to": end}


# ---------------------------------------------------------------- email HTML (inline styles: email clients ignore <style>)
FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Hiragino Sans GB','Microsoft YaHei','Noto Sans SC',Helvetica,Arial,sans-serif"
INK, MUTED, LINE, ACCENT, BUY, SELL = "#1f2937", "#6b7280", "#e5e7eb", "#2c49c9", "#0f9f6e", "#d9473f"


def _inline(t):
    import html as _h
    t = _h.escape(t, quote=False)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: f'<a href="{m.group(2)}" style="color:{ACCENT};text-decoration:none;font-weight:600">{m.group(1)}</a>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r'<strong style="font-weight:600;color:#111827">\1</strong>', t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", t)
    return t


def to_html(md):
    out, items = [], []
    def flush():
        if items:
            lis = "".join(f'<li style="margin:0 0 10px;padding:0">{_inline(x)}</li>' for x in items)
            out.append(f'<ul style="margin:0 0 18px;padding:0 0 0 20px;font-size:15px;line-height:1.65;color:{INK}">{lis}</ul>')
            items.clear()
    for blk in re.split(r"\n\s*\n", md.strip()):
        for ln in blk.split("\n"):
            ln = ln.rstrip()
            if not ln.strip(): continue
            if ln.startswith("- "): items.append(ln[2:]); continue
            flush()
            if ln.strip() == "<br>": continue
            if ln.startswith("# "):
                out.append(f'<h1 style="margin:36px 0 6px;font-size:20px;line-height:1.35;font-weight:700;color:#111827">{_inline(ln[2:])}</h1>')
            elif ln.startswith("## "):
                out.append(f'<h2 style="margin:26px 0 10px;padding-top:16px;border-top:1px solid {LINE};font-size:16px;line-height:1.4;font-weight:700;color:#111827">{_inline(ln[3:])}</h2>')
            elif ln.strip() == "---":
                out.append(f'<hr style="border:0;border-top:1px solid {LINE};margin:28px 0 16px">')
            elif re.fullmatch(r"\*[^*].*\*", ln.strip()):
                out.append(f'<p style="margin:0 0 14px;font-size:12.5px;line-height:1.6;color:{MUTED}">{_inline(ln.strip()[1:-1])}</p>')
            else:
                out.append(f'<p style="margin:0 0 14px;font-size:15px;line-height:1.7;color:{INK}">{_inline(ln)}</p>')
    flush()
    return (f'<div style="max-width:600px;margin:0 auto;font-family:{FONT};font-size:15px;line-height:1.7;color:{INK};'
            f'-webkit-text-size-adjust:100%">' + "\n".join(out) + "</div>")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("days"); ap.add_argument("--end"); ap.add_argument("--lang", default="en"); ap.add_argument("--out")
    ap.add_argument("--news", help="NEWS.json from whatsnew.py: a 'new this week' line under the greeting")
    a = ap.parse_args()
    days = load(a.days)
    end = a.end or days[-1]["date"]
    nw = json.load(open(a.news, encoding="utf-8")) if a.news else {}
    if a.lang == "both":   # Chinese first, English after
        z, e = digest(days, end, "zh", nw.get("zh", "")), digest(days, end, "en", nw.get("en", ""))
        r = z and {"subject": z["subject"] + " | Weekly insider digest", "week_from": z["week_from"], "week_to": z["week_to"],
                   "body": "*English version below ↓*\n\n" + z["body"] + "\n\n<br>\n\n---\n\n# English\n\n" + e["body"]}
    else:
        r = digest(days, end, a.lang, nw.get(a.lang, ""))
    if not r: raise SystemExit("no filing dates in that week")
    if a.out:
        w = dict(r, body_md=r["body"], body=to_html(r["body"]))   # Buttondown gets styled HTML; Markdown kept for reference
        json.dump(w, open(a.out, "w", encoding="utf-8"), ensure_ascii=False)
    print(r["subject"]); print(); print(r["body"])
