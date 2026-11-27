"""Daily options read -> data/options.json (the /options/ page and the homepage read it), plus a running
history of daily totals in data/options_hist.json (for "volume vs its 20-day average" once enough days exist).

Source: Nasdaq's public option-chain API (every listed contract: last price, volume, open interest). Volume is
the last session's; open interest is as of the session before, so volume far above open interest means new
positions were opened that day. The free data does not say whether a trade was bought or sold, so nothing
here claims a direction beyond the call/put split.

Symbols: a fixed list (index and asset ETFs, key stocks) plus the companies on the homepage's insider signals
and the largest insider buys of the last 5 filing days, so the two sources can be read together.

Per symbol: call and put volume, put/call ratio, premium traded (volume x last x 100), volume / open interest,
the unusual contracts (see UNUSUAL) and rule-based flags. Rules only.

    python3 -I scripts/fetch_options.py [--offline DIR]   (DIR holds <SYM>.json Nasdaq responses, for testing)
Standard library only.
"""
import argparse, datetime as dt, glob, importlib.util, json, os, re, sys, time, urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "data", "options.json")
HIST = os.path.join(ROOT, "data", "options_hist.json")
WORK = os.path.join(ROOT, "work")
KEEP_HIST = 60

# (symbol, Nasdaq asset class, group, zh, tw, en)
FIXED = [
    ("SPY", "etf", "index", "标普 500", "標普 500", "S&P 500"), ("QQQ", "etf", "index", "纳指 100", "那指 100", "Nasdaq 100"),
    ("IWM", "etf", "index", "罗素 2000", "羅素 2000", "Russell 2000"), ("SMH", "etf", "asset", "半导体", "半導體", "Semiconductors"),
    ("TLT", "etf", "asset", "20 年以上美债", "20 年以上美債", "20+ year Treasuries"), ("GLD", "etf", "asset", "黄金", "黃金", "Gold"),
    ("USO", "etf", "asset", "原油", "原油", "Crude oil"), ("IBIT", "stocks", "asset", "比特币", "比特幣", "Bitcoin"),
    ("AAPL", "stocks", "stock", "苹果", "蘋果", "Apple"), ("MSFT", "stocks", "stock", "微软", "微軟", "Microsoft"),
    ("NVDA", "stocks", "stock", "英伟达", "輝達", "NVIDIA"), ("AMZN", "stocks", "stock", "亚马逊", "亞馬遜", "Amazon"),
    ("GOOGL", "stocks", "stock", "谷歌", "谷歌", "Alphabet"), ("META", "stocks", "stock", "Meta", "Meta", "Meta"),
    ("TSLA", "stocks", "stock", "特斯拉", "特斯拉", "Tesla"), ("AVGO", "stocks", "stock", "博通", "博通", "Broadcom"),
    ("TSM", "stocks", "stock", "台积电", "台積電", "TSMC"), ("AMD", "stocks", "stock", "AMD", "AMD", "AMD"),
    ("MU", "stocks", "stock", "美光", "美光", "Micron"), ("PLTR", "stocks", "stock", "Palantir", "Palantir", "Palantir"),
]
MAX_INSIDER = 8          # extra symbols taken from the insider data
BIG = {"index": 1_000_000, "asset": 250_000, "stock": 250_000, "insider": 100_000}   # premium for an "unusual" contract
PCR = {"index": (0.8, 2.0), "asset": (0.4, 1.5), "stock": (0.4, 1.2), "insider": (0.4, 1.2)}  # (call-heavy below, put-heavy above)
MON = {m: i for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}

def num(s):
    s = str(s if s is not None else "").replace("$", "").replace(",", "").strip()
    try: return float(s)
    except ValueError: return 0.0

def fetch(sym, cls, offline=None):
    if offline:
        p = os.path.join(offline, f"{sym}.json")
        if not os.path.exists(p): raise FileNotFoundError(p)
        return json.load(open(p, encoding="utf-8"))
    url = (f"https://api.nasdaq.com/api/quote/{sym}/option-chain?assetclass={cls}&limit=12000&fromdate=all&todate=undefined"
           "&excode=oprac&callput=callput&money=all&type=all")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; april-stock-atlas daily data)", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8"))

def parse(j):
    """-> (session date, underlying price, [(cp, strike, expiry date, last, volume, open interest)])"""
    d = j.get("data") or {}
    m = re.search(r"\$([\d,.]+)\s*\(AS OF ([A-Z]{3}) (\d{1,2}), (\d{4})\)", d.get("lastTrade") or "", re.I)
    if not m: raise ValueError("no last trade line")
    px = num(m.group(1)); day = dt.date(int(m.group(4)), MON[m.group(2).lower()], int(m.group(3)))
    rows, exp = [], None
    for r in (d.get("table") or {}).get("rows") or []:
        if r.get("expirygroup"):
            exp = dt.datetime.strptime(r["expirygroup"], "%B %d, %Y").date(); continue
        if exp is None or r.get("strike") in (None, "--"): continue
        k = num(r["strike"])
        for cp in ("c", "p"):
            v = num(r.get(f"{cp}_Volume"))
            rows.append((cp, k, exp, num(r.get(f"{cp}_Last")), v, num(r.get(f"{cp}_Openinterest"))))
    if not rows: raise ValueError("empty chain")
    return day, px, rows

def analyse(group, day, px, rows, hist):
    cv = sum(r[4] for r in rows if r[0] == "c"); pv = sum(r[4] for r in rows if r[0] == "p")
    coi = sum(r[5] for r in rows if r[0] == "c"); poi = sum(r[5] for r in rows if r[0] == "p")
    cprem = sum(r[4] * r[3] * 100 for r in rows if r[0] == "c"); pprem = sum(r[4] * r[3] * 100 for r in rows if r[0] == "p")
    pcr = pv / cv if cv else None
    unusual = []
    for cp, k, exp, last, v, oi in rows:
        prem = v * last * 100
        otm = (k / px - 1) * 100 if cp == "c" else (1 - k / px) * 100
        # new money in a directional contract: volume well above existing open interest, real size, out of the money
        # (or at most 10% in it), 7 days to a year out; deep in-the-money and far-dated trades are mostly hedges, rolls or financing,
        # and contracts expiring within a week always trade far above their open interest
        if v >= 500 and v >= 5 * max(oi, 100) and prem >= BIG[group] and -10 <= otm <= 60 and 7 <= (exp - day).days <= 365:
            unusual.append({"cp": cp, "k": k, "exp": exp.isoformat(), "dte": (exp - day).days, "last": last, "vol": int(v), "oi": int(oi),
                            "prem": round(prem), "otm": round(otm, 1)})
    unusual.sort(key=lambda u: -u["prem"])
    past = [h for h in hist if h[0] < day.isoformat()][-20:]
    avg = sum(h[1] + h[2] for h in past) / len(past) if len(past) >= 10 else None
    rvol = (cv + pv) / avg if avg else None
    lo, hi = PCR[group]
    flags = []
    enough = cprem + pprem >= 20 * BIG[group]   # a call/put tilt on a thinly traded chain says little
    if enough and pcr is not None and pcr <= lo and cprem >= 2 * pprem: flags.append("callHeavy")
    if enough and pcr is not None and pcr >= hi and pprem >= 1.5 * cprem: flags.append("putHeavy")
    ucp = sum(u["prem"] for u in unusual if u["cp"] == "c"); upp = sum(u["prem"] for u in unusual if u["cp"] == "p")
    share = (ucp + upp) / (cprem + pprem) if cprem + pprem else 0   # how much of the day's premium went into those contracts
    if ucp >= 3 * BIG[group] and ucp >= 2 * upp and ucp >= 0.05 * cprem: flags.append("newCalls")
    if upp >= 3 * BIG[group] and upp >= 2 * ucp and upp >= 0.05 * pprem: flags.append("newPuts")
    if rvol and rvol >= 2: flags.append("volSpike")
    tot = cv + pv
    score = 20 * share + 2 * len(flags) + (2 if rvol and rvol >= 2 else 0)
    return {"px": px, "cv": int(cv), "pv": int(pv), "coi": int(coi), "poi": int(poi), "pcr": round(pcr, 2) if pcr is not None else None,
            "cprem": round(cprem), "pprem": round(pprem), "voi": round(tot / (coi + poi), 3) if coi + poi else None,
            "rvol": round(rvol, 2) if rvol else None, "share": round(share, 3), "unusual": unusual[:6], "nUnusual": len(unusual), "flags": flags, "score": round(score, 2)}

def insider_symbols():
    """Companies on the homepage's insider signals and the largest insider buys (same rules as build_home)."""
    try:
        spec = importlib.util.spec_from_file_location("build_home", os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_home.py"))
        bh = importlib.util.module_from_spec(spec); spec.loader.exec_module(bh)
        days = [json.load(open(p, encoding="utf-8")) for p in sorted(glob.glob(os.path.join(ROOT, "data", "days", "*.json")))[-bh.SIGNAL_DAYS:]]
        _, sigs, buys, _ = bh.insider(days)
        out = []
        for t, n in [(s["t"], s["title"]) for s in sigs] + [(b["t"], {"zh": b["n"], "tw": b["n"], "en": b["n"]}) for b in buys]:
            name = {l: re.split(r"[：:]", n[l])[0] for l in ("zh", "tw", "en")}
            if t not in {x[0] for x in out}: out.append((t, name))
        return out[:MAX_INSIDER]
    except Exception as ex:
        print(f"insider symbols: {ex}", file=sys.stderr); return []

def compare(day, hist, cv, pv, cprem, pprem):
    """against the previous stored session: volumes, premiums and the put/call ratio"""
    past = [h for h in hist if h[0] < day.isoformat()]
    if not past: return None
    d0, cv0, pv0, cp0, pp0 = past[-1]
    pct = lambda a, b: round((a / b - 1) * 100, 1) if b else None
    return {"day": d0, "vol": pct(cv + pv, cv0 + pv0), "cv": pct(cv, cv0), "pv": pct(pv, pv0), "cprem": pct(cprem, cp0), "pprem": pct(pprem, pp0),
            "pcr": round(pv0 / cv0, 2) if cv0 else None}

def follow(prev_unusual, rows):
    """did yesterday's unusual contracts stay open? today's open interest against yesterday's volume
    (open interest is counted overnight, so today's figure includes yesterday's trades)"""
    oi = {(cp, k, e.isoformat()): o for cp, k, e, last, v, o in rows}
    out = []
    for u in prev_unusual:
        now = oi.get((u["cp"], u["k"], u["exp"]))
        if now is None: continue
        added = now - u["oi"]
        out.append({**{k: u[k] for k in ("cp", "k", "exp", "vol", "oi", "prem")}, "oiNow": int(now), "added": int(added),
                    "kept": round(max(added, 0) / u["vol"], 2) if u["vol"] else None})
    return out

def in_session():
    """US trading hours on a weekday (ET, with a margin): option volumes are then only part of a day"""
    from zoneinfo import ZoneInfo
    now = dt.datetime.now(ZoneInfo("America/New_York"))
    return now.weekday() < 5 and (9, 25) <= (now.hour, now.minute) < (16, 30)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--offline"); a = ap.parse_args()
    if not a.offline and in_session():
        print("US market is open: option volumes would be a partial day; keeping the previous read"); return
    hist = json.load(open(HIST, encoding="utf-8")) if os.path.exists(HIST) else {}
    prev = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    prev_u = {i["t"]: (i["date"], i["unusual"]) for i in prev.get("items", [])}
    fixed = {f[0] for f in FIXED}
    universe = [(s, c, g, {"zh": zh, "tw": tw, "en": en}) for s, c, g, zh, tw, en in FIXED]
    universe += [(t, "stocks", "insider", n) for t, n in insider_symbols() if t not in fixed]
    items, missing = [], []
    # Nasdaq stamps the chain with today's date even when the market was closed; use the last session the price data saw
    vp = os.path.join(ROOT, "data", "volume.json")
    last_session = json.load(open(vp, encoding="utf-8")).get("date") if os.path.exists(vp) else None
    for sym, cls, group, name in universe:
        try:
            day, px, rows = parse(fetch(sym, cls, a.offline))
            if last_session and day.isoformat() > last_session: day = dt.date.fromisoformat(last_session)
            it = {"t": sym, "g": group, "n": name, "date": day.isoformat(), **analyse(group, day, px, rows, hist.get(sym, []))}
            it["vsPrev"] = compare(day, hist.get(sym, []), it["cv"], it["pv"], it["cprem"], it["pprem"])
            pd_, pu = prev_u.get(sym, (None, []))
            it["follow"] = follow(pu, rows) if pd_ and pd_ < day.isoformat() and pu else []
            it["followDay"] = pd_ if it["follow"] else None
            items.append(it)
            h = [x for x in hist.get(sym, []) if x[0] != it["date"]] + [[it["date"], it["cv"], it["pv"], it["cprem"], it["pprem"]]]
            hist[sym] = sorted(h)[-KEEP_HIST:]
        except Exception as ex:
            if group == "insider" and "no last trade" in str(ex): print(f"{sym}: no listed options", file=sys.stderr)
            else: missing.append(sym); print(f"{sym}: FAILED {ex}", file=sys.stderr)
        if not a.offline: time.sleep(0.8)
    fixed_ok = sum(i["t"] in fixed for i in items)
    if fixed_ok < len(FIXED) // 2: sys.exit(f"too many symbols failed: {missing}")
    day = max({i["date"] for i in items}, key=lambda d: (sum(i["date"] == d for i in items), d))

    allu = sorted(({"t": i["t"], "n": i["n"], **u} for i in items if i["date"] == day for u in i["unusual"]), key=lambda u: -u["prem"])[:15]
    allf = sorted(({"t": i["t"], "n": i["n"], "day": i["followDay"], **f} for i in items if i["date"] == day for f in i.get("follow", [])), key=lambda f: -f["prem"])[:15]
    out = {"date": day, "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "missing": missing,
           "histDays": max((len(v) for v in hist.values()), default=0), "items": items, "unusual": allu, "follow": allf}
    old = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    changed = old.get("date") != out["date"] or old.get("items") != out["items"]
    if changed:
        with open(OUT, "w", encoding="utf-8") as f: json.dump(out, f, ensure_ascii=False, separators=(",", ":")); f.write("\n")
        with open(HIST, "w", encoding="utf-8") as f: json.dump(hist, f, separators=(",", ":")); f.write("\n")
        os.makedirs(WORK, exist_ok=True); open(os.path.join(WORK, "options_changed"), "w").write("1")
    print(f"{day}: {len(items)} symbols ({len(items) - fixed_ok} from insider data), missing {missing}, {len(allu)} unusual, changed={changed}")

if __name__ == "__main__":
    main()
