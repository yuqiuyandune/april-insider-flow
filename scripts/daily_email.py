#!/usr/bin/env python3
"""The daily brief email (April 早报): Chinese first, English below, sent around 20:00 Beijing time on weekdays
to subscribers tagged "daily" only (see bd_daily.py). Everything comes from data the site already publishes:

  1. worth remembering   the latest market recap's key points (data/recaps/<date>.json)
  2. today's signals     the homepage's insider signals, with the options and institutions tags
  3. coming up           the next events of the macro calendar, ET first, then Beijing
  4. options / institutions   one or two lines each

    daily_email.py [--out daily.json] [--today YYYY-MM-DD]
Writes {"subject", "body" (Markdown), "session", "expected", "ok", "problems"}. "ok" is false when the data is not
for the latest US session (the daily data run failed or is late); the workflow then saves a draft instead of sending.
"""
import argparse, datetime as dt, glob, html, importlib.util, json, os, sys
from zoneinfo import ZoneInfo

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SITE = "https://april-insider-flow.com"
ET, BJ = ZoneInfo("America/New_York"), ZoneInfo("Asia/Shanghai")

def mod(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

SHORT = {  # subject lines: what the session was about, from its top rule
    "zh": {"flush_rebound": "盘中下杀后收复", "sell_everything": "什么都卖", "never_back": "全天没回到昨收", "never_below": "全天没跌破昨收",
           "best_day": "多年最大单日波动", "up_vs_down": "涨了但量不够", "semis_big": "半导体大幅波动", "broad": "整个指数放量",
           "regime_up": "ETF 成交突然放大", "sellers_done": "卖盘走完了", "heavy_on_down": "量集中在下跌日", "correction": "进入技术性回调",
           "bear": "进入熊市", "ytd_zero": "年内涨幅归零", "haven_top_volume": "钱往避险资产跑", "liquidity_back": "流动性回来了",
           "flight": "钱跑进国债", "amp_mismatch": "振幅大、量不足", "open_high_close_low": "开盘即最高", "spike_fade": "冲高回落"},
    "en": {"flush_rebound": "a selloff bought back", "sell_everything": "sell everything", "never_back": "never back to the prior close",
           "never_below": "never below the prior close", "best_day": "the biggest day in a long time", "up_vs_down": "up on light volume",
           "semis_big": "a big day for chips", "broad": "index-wide volume", "regime_up": "ETF volume jumps", "sellers_done": "sellers ran out",
           "heavy_on_down": "volume on the down day", "correction": "into a correction", "bear": "into a bear market", "ytd_zero": "the year's gain gone",
           "haven_top_volume": "money to safety", "liquidity_back": "liquidity is back", "flight": "money into Treasuries",
           "amp_mismatch": "a big range on thin volume", "open_high_close_low": "opened at the high", "spike_fade": "spike and fade"},
}
T = {
    "zh": {"brand": "April 早报", "key": "今天值得记住的", "sig": "今日信号：内部人在买什么", "cal": "接下来", "opt": "期权", "inst": "机构",
           "more": "完整复盘", "sigAll": "全部信号", "calAll": "完整日历", "tags": {"opt": "期权", "inst": "机构"}, "bj": "北京", "next": "次日", "allday": "全天",
           "foot": "每个交易日北京时间晚上 8 点左右发出，内容全部来自 April's Stock Atlas 的公开数据和固定规则，不构成投资建议。不想再收早报：在 Buttondown 的订阅设置里取消 daily 标签，或直接退订。",
           "session": "{m}月{d}日收盘"},
    "en": {"brand": "April's daily brief", "key": "Worth remembering", "sig": "Today's signals: what insiders are buying", "cal": "Coming up", "opt": "Options",
           "inst": "Institutions", "more": "Full recap", "sigAll": "All signals", "calAll": "Full calendar", "tags": {"opt": "options", "inst": "institutions"},
           "bj": "Beijing", "next": "next day", "allday": "all day",
           "foot": "Sent around 8pm Beijing time on trading days. Everything comes from April's Stock Atlas public data and fixed rules; not investment advice. To stop the daily brief, remove the daily tag in your Buttondown subscription settings, or unsubscribe.",
           "session": "close of {M} {d}"},
}
MON = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

def expected_session(today_et, closed):
    """the latest US session that has finished before today's US morning: the last weekday before today that is not a holiday"""
    d = today_et - dt.timedelta(days=1)
    while d.weekday() >= 5 or d.isoformat() in closed: d -= dt.timedelta(days=1)
    return d.isoformat()

def ev_time(e, l, rt, cal):
    t = T[l]
    if not e.get("time"): return t["allday"]
    y, m, d = map(int, e["date"].split("-")); hh, mm = map(int, e["time"].split(":"))
    et = dt.datetime(y, m, d, hh, mm, tzinfo=ET); bj = et.astimezone(BJ)
    nxt = (t["next"] + " ") if bj.date() > et.date() else ""
    early = (cal.T[l]["earlyT"] + " ") if e["kind"] == "early" else ""
    return f"{early}{e['time']} ET（{t['bj']} {nxt}{bj:%H:%M}）" if l != "en" else f"{early}{e['time']} ET ({t['bj']} {nxt}{bj:%H:%M})"

def ev_name(e, l, cal):
    c = cal.T[l]; n = c["k"][e["kind"]]
    if e["kind"] in ("cpi", "jobs", "ppi", "pce") and e.get("ref"):
        m = int(e["ref"][5:7]); n += c["ref"].format(m=m, M=MON[m - 1])
    elif e["kind"] == "closed" and e.get("name"): n += ("：" if l != "en" else ": ") + c["hol"].get(e["name"], e["name"])
    elif e["kind"] == "fomc" and e.get("sep"): n += " · " + c["sep"]
    return n

def section(l, r, rt, sigs, of, ol, inf, il, events, cal, opt_lines, inst_lines):
    t = T[l]; out = []
    y, m, d = map(int, r["date"].split("-"))
    out.append(f"## {t['key']}\n")
    out += [f"{i}. {s}" for i, s in enumerate(rt.key_points(r, l), 1)]
    out.append(f"\n[{t['more']} →]({SITE}/market/volume/)\n")
    if sigs:
        out.append(f"## {t['sig']}\n")
        for s in sigs[:3]:
            tags = [s["kind"][l]] + ([s["tag"][l]] if s.get("tag") else [])
            tags += [f"{t['tags']['opt']}：{ol[l][f]}" if l != "en" else f"{t['tags']['opt']}: {ol[l][f]}" for f in of.get(s["t"], [])] if ol else []
            tags += [f"{t['tags']['inst']}：{il[l][f]}" if l != "en" else f"{t['tags']['inst']}: {il[l][f]}" for f in inf.get(s["t"], [])] if il else []
            out.append(f"- **[{s['t']}]({SITE}/s/{s['t']}.html)** {s['title'][l]}（{s['amt']}）" if l != "en" else f"- **[{s['t']}]({SITE}/s/{s['t']}.html)** {s['title'][l]} ({s['amt']})")
            out.append(f"  {s['why'][l]} · " + " · ".join(tags))
        out.append(f"\n[{t['sigAll']} →]({SITE}/)\n")
    if events:
        out.append(f"## {t['cal']}\n")
        for e in events:
            ey, em, ed = map(int, e["date"].split("-"))
            day = f"{em}月{ed}日" if l != "en" else f"{MON[em-1]} {ed}"
            out.append(f"- **{day}** {ev_name(e, l, cal)} · {ev_time(e, l, rt, cal)}")
        out.append(f"\n[{t['calAll']} →]({SITE}/calendar/)\n")
    if opt_lines:
        out.append(f"## {t['opt']}\n"); out += [f"- {x}" for x in opt_lines]; out.append("")
    if inst_lines:
        out.append(f"## {t['inst']}\n"); out += [f"- {x}" for x in inst_lines]; out.append("")
    out.append(f"*{t['foot']}*")
    return "\n".join(out)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="daily.json"); ap.add_argument("--today")
    a = ap.parse_args()
    rt = mod("recap_text"); bh = mod("build_home"); bo = mod("build_options"); bi = mod("build_institutions"); cal = mod("build_calendar")
    today = dt.date.fromisoformat(a.today) if a.today else dt.datetime.now(ET).date()
    macro = json.load(open(os.path.join(ROOT, "data", "macro.json"), encoding="utf-8")) if os.path.exists(os.path.join(ROOT, "data", "macro.json")) else {"events": []}
    closed = {e["date"] for e in macro["events"] if e["kind"] == "closed"}
    expected = expected_session(today, closed)
    recs = sorted(glob.glob(os.path.join(ROOT, "data", "recaps", "*.json")))
    problems = []
    if not recs: sys.exit("no recaps")
    r = json.load(open(recs[-1], encoding="utf-8"))
    if r["date"] != expected: problems.append(f"latest recap is for {r['date']}, expected {expected}")
    days = [json.load(open(p, encoding="utf-8")) for p in sorted(glob.glob(os.path.join(ROOT, "data", "days", "*.json")))[-bh.SIGNAL_DAYS:]]
    _, sigs, _, _ = bh.insider(days)
    od = bo.load(); of = bo.flags_for(od) if od else {}; ol = {l: bo.T[l]["f"] for l in ("zh", "en")} if od else None
    inf = bi.flags_for(); il = {l: bh.T[l]["inst"] for l in ("zh", "en")}
    now_et = dt.datetime.now(ET).date().isoformat() if not a.today else a.today
    events = [e for e in macro["events"] if e["date"] >= now_et and e["kind"] in ("fomc", "cpi", "jobs", "pce", "closed", "early")][:4]
    strip = lambda s: html.unescape(s).replace("<b>", "**").replace("</b>", "**")
    body = []
    for l in ("zh", "en"):
        opt_lines = [strip(x) for x in bo.summary(od, l, 2)] if od else []
        inst_lines = [strip(x) for x in bi.summary(l, 1)][:3]
        body.append(section(l, r, rt, sigs, of, ol, inf, il, events, cal, opt_lines, inst_lines))
    y, m, d = map(int, r["date"].split("-"))
    top = next((k for k in r.get("key", []) if k in SHORT["zh"]), None)
    subj = f"{T['zh']['brand']} · {T['zh']['session'].format(m=m, d=d)}" + (f"：{SHORT['zh'][top]}" if top else "") \
           + f" | {T['en']['session'].format(M=MON[m-1], d=d)[0].upper()}{T['en']['session'].format(M=MON[m-1], d=d)[1:]}" + (f": {SHORT['en'][top]}" if top else "")
    out = {"subject": subj, "body": "\n\n---\n\n".join(body), "session": r["date"], "expected": expected, "ok": not problems, "problems": problems}
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(subj); print("ok" if out["ok"] else "NOT OK: " + "; ".join(problems))

if __name__ == "__main__":
    main()
