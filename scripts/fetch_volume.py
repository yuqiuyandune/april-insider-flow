"""Daily price-and-volume read of key ETFs and stocks -> data/volume.json (the /market/volume/ page and the homepage read it).

For each symbol: one year of daily open/high/low/close/volume from Nasdaq's public quote API, then
  chg       % change on the last session
  rvol      volume / average volume of the 20 sessions before it ("量比")
  pos       where the close sits in the day's range (0 = low, 1 = high)
  ma        close above (1) or below (0) the 20/50/200-day moving averages, and crosses on the last session
  hi52/lo52 distance from the 52-week closing high/low
  flags     rule-based labels (see FLAGS): heavy-volume up/down, light-volume rise, MA crosses, new highs/lows, weak close
and a short summary picked from the strongest flags. Rules only, nothing written by hand.

A symbol that fails keeps nothing for that run (it is listed under "missing"); the run fails only if most fail.

    python3 -I scripts/fetch_volume.py [--offline DIR]   (DIR holds <SYM>.json Nasdaq responses, for testing)
Standard library only.
"""
import argparse, csv, datetime as dt, importlib.util, io, json, os, sys, time, urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "data", "volume.json")
WORK = os.path.join(ROOT, "work")

# (symbol, Nasdaq asset class, group, zh, tw, en); Nasdaq files some ETFs (IBIT) under "stocks"
UNIVERSE = [
    ("SPY", "etf", "index", "标普 500", "標普 500", "S&P 500"), ("QQQ", "etf", "index", "纳指 100", "那指 100", "Nasdaq 100"),
    ("IWM", "etf", "index", "罗素 2000 小盘股", "羅素 2000 小型股", "Russell 2000 small caps"), ("DIA", "etf", "index", "道琼斯", "道瓊", "Dow Jones"),
    ("XLK", "etf", "sector", "科技", "科技", "Technology"), ("XLC", "etf", "sector", "通信服务", "通訊服務", "Communication services"),
    ("XLY", "etf", "sector", "可选消费", "非必需消費", "Consumer discretionary"), ("XLP", "etf", "sector", "必需消费", "必需消費", "Consumer staples"),
    ("XLE", "etf", "sector", "能源", "能源", "Energy"), ("XLF", "etf", "sector", "金融", "金融", "Financials"),
    ("XLV", "etf", "sector", "医疗保健", "醫療保健", "Health care"), ("XLI", "etf", "sector", "工业", "工業", "Industrials"),
    ("XLB", "etf", "sector", "基础材料", "基礎材料", "Materials"), ("XLRE", "etf", "sector", "房地产", "房地產", "Real estate"),
    ("XLU", "etf", "sector", "公用事业", "公用事業", "Utilities"),
    ("SMH", "etf", "asset", "半导体", "半導體", "Semiconductors"), ("SOXX", "etf", "asset", "费城半导体", "費城半導體", "PHLX Semiconductor"), ("TLT", "etf", "asset", "20 年以上美债", "20 年以上美債", "20+ year Treasuries"),
    ("GLD", "etf", "asset", "黄金", "黃金", "Gold"), ("USO", "etf", "asset", "原油", "原油", "Crude oil"), ("IBIT", "stocks", "asset", "比特币", "比特幣", "Bitcoin"),
    ("AAPL", "stocks", "stock", "苹果", "蘋果", "Apple"), ("MSFT", "stocks", "stock", "微软", "微軟", "Microsoft"),
    ("NVDA", "stocks", "stock", "英伟达", "輝達", "NVIDIA"), ("AMZN", "stocks", "stock", "亚马逊", "亞馬遜", "Amazon"),
    ("GOOGL", "stocks", "stock", "谷歌", "谷歌", "Alphabet"), ("META", "stocks", "stock", "Meta", "Meta", "Meta"),
    ("TSLA", "stocks", "stock", "特斯拉", "特斯拉", "Tesla"), ("AVGO", "stocks", "stock", "博通", "博通", "Broadcom"),
    ("TSM", "stocks", "stock", "台积电", "台積電", "TSMC"), ("AMD", "stocks", "stock", "AMD", "AMD", "AMD"),
    ("MU", "stocks", "stock", "美光", "美光", "Micron"), ("PLTR", "stocks", "stock", "Palantir", "Palantir", "Palantir"),
]
# a "big move" for flags: 1% for broad and sector ETFs, 2% for single stocks and the more volatile assets
BIG = {"index": 1.0, "sector": 1.0, "asset": 1.5, "stock": 2.0}

def num(s):
    s = str(s or "").replace("$", "").replace(",", "").strip()
    try: return float(s)
    except ValueError: return None   # "N/A", "--"

def fetch(sym, cls, offline=None, days=400):
    if offline:
        j = json.load(open(os.path.join(offline, f"{sym}.json"), encoding="utf-8"))
    else:
        to = dt.date.today(); fr = to - dt.timedelta(days=days)
        url = f"https://api.nasdaq.com/api/quote/{sym}/historical?assetclass={cls}&fromdate={fr}&todate={to}&limit={days}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; april-stock-atlas daily data)", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            j = json.loads(r.read().decode("utf-8"))
    rows = ((j.get("data") or {}).get("tradesTable") or {}).get("rows") or []
    out = []
    for r in rows:
        m, d, y = r["date"].split("/")
        o, h, l, c, v = num(r.get("open")), num(r.get("high")), num(r.get("low")), num(r.get("close")), num(r.get("volume"))
        if c is None: continue
        if v is None: v = 0.0   # indices carry no volume
        out.append((f"{y}-{m}-{d}", o or c, h or c, l or c, c, v))
    out.sort()
    # a run during US trading hours sees today's unfinished session: leave it out until after the close
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=-5)))   # ET (EST; an hour early in summer, still after 16:00 EDT)
    if out and out[-1][0] == now.date().isoformat() and now.hour < 17: out = out[:-1]
    if len(out) < 60: raise ValueError(f"only {len(out)} sessions")
    return out

def ma(closes, n): return sum(closes[-n:]) / n if len(closes) >= n else None

def analyse(sym, group, rows):
    dates = [r[0] for r in rows]; o, h, l, c, v = ([r[i] for r in rows] for i in range(1, 6))
    last, prev = c[-1], c[-2]
    chg = (last / prev - 1) * 100
    avgv = sum(v[-21:-1]) / 20
    rvol = v[-1] / avgv if avgv else None
    rng = h[-1] - l[-1]
    pos = (last - l[-1]) / rng if rng > 0 else 0.5
    mas, cross = {}, {}
    for n in (20, 50, 200):
        now, before = ma(c, n), ma(c[:-1], n)
        if now is None: continue
        mas[n] = 1 if last >= now else 0
        if before is not None:
            was = 1 if prev >= before else 0
            if was != mas[n]: cross[n] = "up" if mas[n] else "down"
    yr = c[-252:]
    hi, lo = max(yr[:-1]), min(yr[:-1])
    flags = []
    big = BIG[group]
    if rvol and rvol >= 1.5 and chg >= big: flags.append("volUp")
    if rvol and rvol >= 1.5 and chg <= -big: flags.append("volDown")
    if rvol and rvol < 0.7 and chg >= big * 0.5: flags.append("thinUp")
    for n in (50, 200):
        if cross.get(n) == "up": flags.append(f"above{n}")
        if cross.get(n) == "down": flags.append(f"below{n}")
    if last > hi: flags.append("high52")
    if last < lo: flags.append("low52")
    if rvol and rvol >= 1.2 and pos <= 0.2 and chg < 0: flags.append("weakClose")
    if rvol and rvol >= 1.2 and pos >= 0.8 and chg > 0: flags.append("strongClose")
    # how much this line deserves a place in the summary
    score = abs(chg) / big * (rvol or 1) + 1.5 * sum(f in ("high52", "low52", "below200", "above200") for f in flags) + 0.8 * len(flags)
    spark = [[d, round(x, 2), int(y)] for d, x, y in zip(dates[-30:], c[-30:], v[-30:])]
    return {"date": dates[-1], "close": round(last, 2), "chg": round(chg, 2), "vol": int(v[-1]), "rvol": round(rvol, 2) if rvol else None,
            "pos": round(pos, 2), "ma": mas, "cross": cross, "hi52": round((last / hi - 1) * 100, 1), "lo52": round((last / lo - 1) * 100, 1),
            "flags": flags, "score": round(score, 2), "spark": spark}

RECAPS = os.path.join(ROOT, "data", "recaps")
CACHE = os.path.join(WORK, "px.json")

def http(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; april-stock-atlas daily data)"})
    with urllib.request.urlopen(req, timeout=60) as r: return r.read().decode("utf-8", "replace")

def vix_history():
    out = {}
    for r in csv.DictReader(io.StringIO(http("https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv"))):
        m, d, y = r["DATE"].split("/")
        if y < "2025": continue
        out[f"{y}-{m}-{d}"] = tuple(float(r[k]) for k in ("OPEN", "HIGH", "LOW", "CLOSE"))
    return out

def ust_history():
    out = {}
    for y in sorted({dt.date.today().year - 1, dt.date.today().year}):
        url = (f"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/daily-treasury-rates.csv/{y}/all"
               f"?type=daily_treasury_yield_curve&field_tdr_date_value={y}&page&_format=csv")
        for r in csv.DictReader(io.StringIO(http(url))):
            m, d, yy = r["Date"].split("/")
            out[f"{yy}-{m}-{d}"] = {k: float(r[c]) for k, c in (("5", "5 Yr"), ("10", "10 Yr"), ("30", "30 Yr")) if r.get(c)}
    return out

def chain():
    d = json.load(open(os.path.join(ROOT, "stack", "data.json"), encoding="utf-8"))
    return {c["t"]: c["seg"] for c in d["companies"] if c.get("listed")}, {s["id"]: s["name"] for s in d["segments"]}

def run_recaps(H, vix, ust, ch, segs, days):
    spec = importlib.util.spec_from_file_location("recap", os.path.join(os.path.dirname(os.path.abspath(__file__)), "recap.py"))
    rc = importlib.util.module_from_spec(spec); spec.loader.exec_module(rc)
    os.makedirs(RECAPS, exist_ok=True); done = []
    for d in days:
        out = rc.recap(d, H, vix, ust, ch, {str(k): v for k, v in segs.items()})
        if not out: continue
        out["segNames"] = {str(k): v for k, v in segs.items()}
        p = os.path.join(RECAPS, f"{d}.json")
        old = open(p, encoding="utf-8").read() if os.path.exists(p) else None
        new = json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n"
        if old != new:
            open(p, "w", encoding="utf-8").write(new); done.append(d)
    return done

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--offline"); ap.add_argument("--cache", action="store_true", help="reuse work/px.json (testing)")
    ap.add_argument("--recap-days", type=int, default=3, help="recompute the recap of the last N sessions")
    a = ap.parse_args()
    items, missing, H = [], [], {}
    cached = json.load(open(CACHE)) if a.cache and os.path.exists(CACHE) else None
    def rows_for(sym, cls, days=400):
        if cached and sym in cached: return [tuple(r) for r in cached[sym]]
        r = fetch(sym, cls, a.offline, days)
        if not a.offline: time.sleep(0.6)
        return r
    for sym, cls, group, zh, tw, en in UNIVERSE:
        try:
            rows = rows_for(sym, cls, 1100 if group == "index" else 400); H[sym] = rows
            items.append({"t": sym, "g": group, "n": {"zh": zh, "tw": tw, "en": en}, **analyse(sym, group, rows)})
        except Exception as ex:
            missing.append(sym); print(f"{sym}: FAILED {ex}", file=sys.stderr)
    # for the recap: the Nasdaq Composite itself, the Dow ETF, and every listed company in the AI chain
    ch, segs = chain()
    for sym, cls in [("COMP", "index"), ("DIA", "etf")] + [(t, "stocks") for t in ch]:
        if sym in H: continue
        try: H[sym] = rows_for(sym, cls, 1100 if sym == "COMP" else 400)
        except Exception as ex: print(f"{sym}: FAILED {ex}", file=sys.stderr)
    os.makedirs(WORK, exist_ok=True)
    if not cached: json.dump(H, open(CACHE, "w"))
    if len(items) < len(UNIVERSE) // 2: sys.exit(f"too many symbols failed: {missing}")
    # the session everything should be on: the latest date most symbols share
    dates = sorted({i["date"] for i in items})
    day = max(dates, key=lambda d: (sum(i["date"] == d for i in items), d))
    stale = [i["t"] for i in items if i["date"] != day]
    sectors = [i for i in items if i["g"] == "sector" and i["date"] == day]
    # the market state light (scripts/regime.py); VIX is read here once and reused by the recap below
    try:
        vix = cached.get("_vix") if cached and "_vix" in cached else vix_history()
    except Exception as ex:
        vix = None; print(f"VIX: FAILED {ex}", file=sys.stderr)
    try:
        _rs = importlib.util.spec_from_file_location("regime", os.path.join(os.path.dirname(os.path.abspath(__file__)), "regime.py"))
        _rg = importlib.util.module_from_spec(_rs); _rs.loader.exec_module(_rg)
        regime = _rg.compute(H, {k: tuple(v) for k, v in vix.items()} if vix else None)
    except Exception as ex:
        import traceback; traceback.print_exc(); regime = None; print(f"regime: FAILED {ex}", file=sys.stderr)
    out = {"date": day, "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "missing": missing, "stale": stale,
           "breadth": {"sectorsUp": sum(i["chg"] > 0 for i in sectors), "sectors": len(sectors),
                       "above50": sum(i["ma"].get(50) == 1 for i in items), "above200": sum(i["ma"].get(200) == 1 for i in items), "n": len(items)},
           "items": items}
    if regime: out["regime"] = regime
    old = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    changed = old.get("date") != out["date"] or old.get("items") != out["items"] or old.get("regime") != out.get("regime")
    if changed:
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, separators=(",", ":")); f.write("\n")
        os.makedirs(WORK, exist_ok=True); open(os.path.join(WORK, "volume_changed"), "w").write("1")
    if missing or stale:
        os.makedirs(WORK, exist_ok=True)
        with open(os.path.join(WORK, "volume_problems.md"), "w", encoding="utf-8") as f:
            f.write(f"Price-and-volume read for {day}: " + (f"no data for {', '.join(missing)}. " if missing else "") + (f"older session for {', '.join(stale)}." if stale else "") + "\n")
    try:
        if vix is None: vix = vix_history()
        ust = cached.get("_ust") if cached and "_ust" in cached else ust_history()
        if not cached: H2 = dict(H); H2["_vix"] = vix; H2["_ust"] = ust; json.dump(H2, open(CACHE, "w"))
        sessions = [r[0] for r in H["SPY"]][-a.recap_days:]
        vix = {k: tuple(v) for k, v in vix.items()}
        done = run_recaps(H, vix, ust, ch, segs, sessions)
        if done:
            os.makedirs(WORK, exist_ok=True); open(os.path.join(WORK, "volume_changed"), "w").write("1")
        print(f"recap: {len(done)} written ({', '.join(done)})")
    except Exception as ex:
        import traceback; traceback.print_exc(); print(f"recap: FAILED {ex}", file=sys.stderr)
    print(f"{day}: {len(items)} symbols, missing {missing}, stale {stale}, changed={changed}")

if __name__ == "__main__":
    main()
