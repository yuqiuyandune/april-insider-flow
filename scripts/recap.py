"""The daily market recap engine: from daily OHLCV histories, work out what happened in one session and which reading
rules fire. Language-neutral: numbers and rule keys with their parameters only; build_volume.py writes the sentences.

Input (all lists sorted by date):
  H      {symbol: [(date, open, high, low, close, volume), ...]}   ETFs, the Nasdaq Composite (COMP) and the chain stocks
  VIX    {date: (open, high, low, close)}
  UST    {date: {"5": y, "10": y, "30": y}}                         Treasury par yields, percent
  CHAIN  {ticker: segment id};  SEGS {segment id: {"zh":..,"tw":..,"en":..}}

    recap(day, H, VIX, UST, CHAIN, SEGS) -> dict (see the end of recap())

Rules (each one only when its condition holds; weight decides what makes "worth remembering"):
  index  never_back / never_below / open_high_close_low / flush_rebound / spike_fade / two_day / best_day /
         drawdown (correction, bear market) / ytd_zero / streak / vix
  sector reversal / few_green / semis_big (with symmetry against the last opposite big day)
  volume broad / regime_shift / up_vs_down / amp_mismatch / thin
  flows  sell_everything / haven / liquidity_back / rotation_to_risk / haven_top_volume / gold_wild
  bonds  still / flight / big_move
  chain  summary / concentration / decoupled / all_one_way / seg_all_bear / sellers_done / sold_into_close / all_upper_half /
         new_high_low / big_mover / streak
"""
import statistics as st

ETF_SECTORS = ["XLK", "XLC", "XLY", "XLP", "XLE", "XLF", "XLV", "XLI", "XLB", "XLRE", "XLU"]
BOARD = ["SPY", "QQQ", "IWM", "DIA", "SMH", "SOXX"] + ETF_SECTORS + ["GLD", "TLT", "IBIT"]
VOL_SET = ["SPY", "QQQ", "IWM", "XLK", "XLC", "XLY", "XLP", "XLE", "XLF", "XLV", "XLI", "XLB", "XLRE", "XLU", "SMH", "SOXX", "GLD", "TLT"]
DEFENSIVE = {"XLP", "XLU", "XLV", "XLRE", "TLT", "GLD"}

def r2(x, n=2): return None if x is None else round(x, n)

class S:
    """one symbol's history with helpers by index"""
    def __init__(self, rows):
        self.d = [r[0] for r in rows]; self.o = [r[1] for r in rows]; self.h = [r[2] for r in rows]
        self.l = [r[3] for r in rows]; self.c = [r[4] for r in rows]; self.v = [r[5] for r in rows]
        self.ix = {d: i for i, d in enumerate(self.d)}
    def at(self, day): return self.ix.get(day)
    def chg(self, i): return (self.c[i] / self.c[i - 1] - 1) * 100 if i and i > 0 else None
    def pts(self, i): return self.c[i] - self.c[i - 1] if i and i > 0 else None
    def rvol(self, i):
        if i is None or i < 20 or not self.v[i]: return None
        a = sum(self.v[i - 20:i]) / 20
        return self.v[i] / a if a else None
    def rng(self, i): return (self.h[i] - self.l[i]) / self.c[i - 1] * 100 if i else None
    def pos(self, i):
        r = self.h[i] - self.l[i]
        return (self.c[i] - self.l[i]) / r if r > 0 else 0.5
    def dd(self, i, n=252):
        w = self.c[max(0, i - n + 1): i + 1]
        return (self.c[i] / max(w) - 1) * 100
    def avg_rng(self, i, n=20):
        xs = [self.rng(k) for k in range(max(1, i - n), i)]
        xs = [x for x in xs if x is not None]
        return sum(xs) / len(xs) if xs else None
    def ytd(self, i):
        y = self.d[i][:4]
        prev = [k for k in range(i) if self.d[k][:4] < y]
        return (self.c[i] / self.c[prev[-1]] - 1) * 100 if prev else None
    def streak(self, i):
        s = 0; sign = 0
        for k in range(i, 0, -1):
            c = self.c[k] - self.c[k - 1]
            sg = 1 if c > 0 else -1 if c < 0 else 0
            if sg == 0: break
            if sign == 0: sign = sg
            if sg != sign: break
            s += 1
        return s * sign
    def best_since(self, i):
        """the last earlier session with a move at least as large in the same direction: (date, sessions back) or (None, n)"""
        c = self.chg(i)
        if c is None: return None, 0
        for k in range(i - 1, 0, -1):
            ck = self.chg(k)
            if ck is not None and (ck >= c if c > 0 else ck <= c): return self.d[k], i - k
        return None, i

def spearman(a, b):
    def rank(x):
        o = sorted(range(len(x)), key=lambda i: x[i]); r = [0] * len(x)
        for k, i in enumerate(o): r[i] = k
        return r
    if len(a) < 4: return None
    ra, rb = rank(a), rank(b); n = len(a)
    d2 = sum((x - y) ** 2 for x, y in zip(ra, rb))
    return 1 - 6 * d2 / (n * (n * n - 1))

def recap(day, H, VIX, UST, CHAIN, SEGS):
    sy = {k: S(v) for k, v in H.items() if v}
    spy = sy["SPY"]; i = spy.at(day)
    if i is None or i < 25: return None
    prev = spy.d[i - 1]
    F = []
    def fact(sec, key, w, **p): F.append({"sec": sec, "k": key, "w": w, "p": p})
    def at(t, d=day):
        s = sy.get(t); k = s.at(d) if s else None
        return (s, k) if k is not None and k > 0 else (None, None)

    # ------------------------------------------------------------------ index
    idx = []
    for t in ("COMP", "SPY", "DIA", "IWM"):
        s, k = at(t)
        if not s: continue
        row = {"t": t, "close": r2(s.c[k]), "chg": r2(s.chg(k)), "pts": r2(s.pts(k)), "open": r2(s.o[k]), "high": r2(s.h[k]), "low": r2(s.l[k]),
               "prev": r2(s.c[k - 1]), "lowPct": r2((s.l[k] / s.c[k - 1] - 1) * 100), "highPct": r2((s.h[k] / s.c[k - 1] - 1) * 100),
               "offLow": r2((s.c[k] / s.l[k] - 1) * 100), "dd": r2(s.dd(k), 1), "ytd": r2(s.ytd(k), 1), "streak": s.streak(k), "rvol": r2(s.rvol(k))}
        idx.append(row)
    main = next((r for r in idx if r["t"] == "COMP"), None) or idx[0]
    s, k = at(main["t"])
    big_day = abs(main["chg"]) >= 2   # the shape of a quiet day matters less
    if s.h[k] < s.c[k - 1]: fact("index", "never_back", 8 if big_day else 4, t=main["t"], high=main["high"], prev=main["prev"])
    elif s.l[k] > s.c[k - 1]: fact("index", "never_below", 7 if big_day else 4, t=main["t"], low=main["low"], prev=main["prev"])
    rg = s.h[k] - s.l[k]
    if rg > 0 and (s.h[k] - s.o[k]) / rg <= 0.1 and s.pos(k) <= 0.15 and main["chg"] < 0:
        fact("index", "open_high_close_low", 6, t=main["t"])
    if main["lowPct"] <= -2 and (s.c[k] - s.l[k]) >= 0.6 * (s.c[k - 1] - s.l[k]):
        fact("index", "flush_rebound", 9, rows=[{"t": r["t"], "lowPct": r["lowPct"], "chg": r["chg"], "offLow": r["offLow"], "low": r["low"]} for r in idx if r["lowPct"] <= -1.5],
             green=main["chg"] > 0)
    if main["highPct"] >= 2 and main["chg"] < 0:
        fact("index", "spike_fade", 7, t=main["t"], highPct=main["highPct"], chg=main["chg"])
    yc = s.chg(k - 1)
    if yc is not None and abs(yc) >= 2.5 and abs(main["chg"]) >= 2.5 and (yc > 0) != (main["chg"] > 0):
        fact("index", "two_day", 6, t=main["t"], yPts=r2(s.pts(k - 1)), tPts=main["pts"], net=r2(s.pts(k - 1) + main["pts"]), yDay=s.d[k - 1])
    bd, back = s.best_since(k)
    if abs(main["chg"]) >= 2 and back >= 60:
        fact("index", "best_day", 8, t=main["t"], up=main["chg"] > 0, since=bd, back=back)
    for r in idx:
        if r["t"] not in ("COMP", "SPY", "DIA"): continue
        s2, k2 = at(r["t"]); ydd = s2.dd(k2 - 1)
        if r["dd"] <= -20 < ydd: fact("index", "bear", 9, t=r["t"], dd=r["dd"])
        elif r["dd"] <= -10 < ydd: fact("index", "correction", 7, t=r["t"], dd=r["dd"])
    ys = s.ytd(k - 1)
    if main["ytd"] is not None and ys is not None and (main["ytd"] <= 0 < ys or main["ytd"] > 0 >= ys):
        fact("index", "ytd_zero", 7, t=main["t"], ytd=main["ytd"], down=main["ytd"] <= 0)
    spr = next(r for r in idx if r["t"] == "SPY")
    if abs(spr["streak"]) >= 4: fact("index", "streak", 5 + min(abs(spr["streak"]) - 4, 3), t="SPY", n=spr["streak"])
    vx = None
    if day in VIX:
        dprev = max((d for d in VIX if d < day), default=None)
        o, h, l, c = VIX[day]; pc = VIX[dprev][3] if dprev else None
        vx = {"close": r2(c), "high": r2(h), "low": r2(l), "chg": r2((c / pc - 1) * 100) if pc else None, "highChg": r2((h / pc - 1) * 100) if pc else None, "prev": r2(pc)}
        if pc and (c >= 30 or h >= 30 or abs(vx["chg"]) >= 15): fact("index", "vix", 6, **vx)

    # ------------------------------------------------------------------ sectors and themes
    board = []
    for t in BOARD:
        s2, k2 = at(t)
        if s2: board.append({"t": t, "chg": r2(s2.chg(k2)), "rvol": r2(s2.rvol(k2)), "rng": r2(s2.rng(k2)), "pos": r2(s2.pos(k2))})
    by = {b["t"]: b for b in board}
    ycomp = []
    for b in board:
        s2, k2 = at(b["t"], prev)
        if s2: ycomp.append((b["t"], b["chg"], s2.chg(k2)))
    rho = spearman([x[1] for x in ycomp], [x[2] for x in ycomp]) if ycomp else None
    if rho is not None and rho <= -0.4:
        ys_ = sorted(ycomp, key=lambda x: -x[2]); ts_ = sorted(ycomp, key=lambda x: -x[1])
        fact("sector", "reversal", 6, rho=r2(rho), yUp=[x[0] for x in ys_[:2]], yDown=[x[0] for x in ys_[-2:]], tUp=[x[0] for x in ts_[:2]], tDown=[x[0] for x in ts_[-2:]])
    greens = [b["t"] for b in board if b["chg"] is not None and b["chg"] > 0]
    if spr["chg"] <= -2 and len(greens) <= 3: fact("sector", "few_green", 7, green=greens)
    reds = [b["t"] for b in board if b["chg"] is not None and b["chg"] < 0]
    if spr["chg"] >= 2 and len(reds) <= 3: fact("sector", "few_red", 6, red=reds)
    for t in ("SOXX", "SMH"):
        if t in by and abs(by[t]["chg"]) >= 5:
            s2, k2 = at(t); sym = None
            for kk in range(k2 - 1, max(0, k2 - 6), -1):
                c2 = s2.chg(kk)
                if c2 is not None and abs(c2) >= 5 and (c2 > 0) != (by[t]["chg"] > 0): sym = {"day": s2.d[kk], "chg": r2(c2)}; break
            fact("sector", "semis_big", 7, t=t, chg=by[t]["chg"], other=by.get("SMH" if t == "SOXX" else "SOXX", {}).get("chg"), sym=sym)
            break

    # ------------------------------------------------------------------ volume
    vols = sorted(({"t": t, "rvol": by[t]["rvol"]} for t in VOL_SET if t in by and by[t]["rvol"]), key=lambda x: -x["rvol"])
    med = st.median([x["rvol"] for x in vols]) if vols else None
    trail = []
    for kk in range(i - 3, i + 1):
        trail.append({"d": spy.d[kk], "chg": r2(spy.chg(kk)), "rvol": r2(spy.rvol(kk))})
    def med_on(d):
        xs = []
        for t in VOL_SET:
            s2, k2 = at(t, d)
            if s2 and s2.rvol(k2): xs.append(s2.rvol(k2))
        return st.median(xs) if xs else None
    m1, m2 = med_on(spy.d[i - 1]), med_on(spy.d[i - 2])
    if spr["rvol"] and spr["rvol"] >= 2 and med and med >= 1.8: fact("volume", "broad", 8, spy=spr["rvol"], med=r2(med), down=spr["chg"] < 0)
    if med and m1 and m2:
        if max(m1, m2) < 1.0 and med >= 1.7: fact("volume", "regime_up", 8, before=r2(max(m1, m2)), now=r2(med), down=spr["chg"] < 0)
        elif min(m1, m2) >= 1.7 and med < 1.1: fact("volume", "regime_down", 6, before=r2(min(m1, m2)), now=r2(med))
    if spr["chg"] > 0 and spr["rvol"]:
        for kk in range(i - 1, i - 6, -1):
            c2, rv2 = spy.chg(kk), spy.rvol(kk)
            if c2 is not None and c2 <= -2 and rv2 and rv2 >= 1.8:
                if spr["rvol"] <= 0.65 * rv2:
                    ups = [spy.rvol(x) for x in range(kk + 1, i + 1) if spy.chg(x) and spy.chg(x) > 0]
                    fading = len(ups) >= 2 and all(a > b for a, b in zip(ups, ups[1:]))
                    fact("volume", "up_vs_down", 8, downDay=spy.d[kk], downChg=r2(c2), downRvol=r2(rv2), upChg=spr["chg"], upRvol=spr["rvol"],
                         ratio=r2(spr["rvol"] / rv2), bigger=abs(spr["chg"]) >= abs(c2), fading=fading)
                break
    # the heaviest day of the last four was a down day, and every bounce after it traded less
    tv = [(x["d"], x["chg"], x["rvol"]) for x in trail if x["rvol"]]
    if len(tv) == 4:
        hv = max(tv, key=lambda x: x[2]); after = tv[tv.index(hv) + 1:]
        if hv[1] < -1.5 and hv[2] >= 1.8 and len(after) >= 2 and all(a[2] <= 0.65 * hv[2] for a in after) and hv[0] != day:
            fact("volume", "heavy_on_down", 7, trail=[{"d": a, "chg": b, "rvol": c} for a, b, c in tv], day=hv[0])
    srng = spy.rng(i)
    if srng and srng >= 2.5 and spr["rvol"] and spr["rvol"] <= 1.3: fact("volume", "amp_mismatch", 7, rng=r2(srng), rvol=spr["rvol"])
    if spr["rvol"] and spr["rvol"] < 0.7: fact("volume", "thin", 3, rvol=spr["rvol"])

    # ------------------------------------------------------------------ where the money went
    g = by.get("GLD", {}); tl = by.get("TLT", {}); ib = by.get("IBIT", {}); xp = by.get("XLP", {})
    sc = spr["chg"]
    if sc <= -2 and (g.get("chg") or 0) <= -1 and (ib.get("chg") or 0) <= -2 and ((tl.get("chg") or 0) > 0 or (xp.get("chg") or 0) > 0):
        fact("flows", "sell_everything", 9, gld=g.get("chg"), ibit=ib.get("chg"), green=[t for t in ("TLT", "XLP", "XLU", "XLV") if (by.get(t, {}).get("chg") or 0) > 0])
    elif sc <= -1 and ((g.get("chg") or 0) > 0 or (tl.get("chg") or 0) > 0):
        fact("flows", "haven", 7, gld=g.get("chg"), tlt=tl.get("chg"))
    if sc >= 1.5 and (g.get("chg") or 0) >= 1: fact("flows", "liquidity_back", 7, gld=g.get("chg"), spy=sc)
    elif sc >= 1 and (g.get("chg") or 0) <= -0.5 and (tl.get("chg") or 0) <= -0.3: fact("flows", "rotation_to_risk", 5, gld=g.get("chg"), tlt=tl.get("chg"))
    top2 = [x["t"] for x in vols[:2]]
    if set(top2) & {"GLD", "TLT"} and (len(set(top2) & {"GLD", "TLT"}) == 2 or vols[0]["t"] in ("GLD", "TLT")):
        fact("flows", "haven_top_volume", 7, top=[x for x in vols[:2]])
    if g.get("rng") and srng and g["rng"] >= 3 and g["rng"] >= srng: fact("flows", "gold_wild", 5, gld=g["rng"], spy=r2(srng), rvol=g.get("rvol"))

    # ------------------------------------------------------------------ bonds
    bonds = None
    if day in UST:
        dp = max((d for d in UST if d < day), default=None)
        if dp:
            cur, pv = UST[day], UST[dp]
            bonds = {k: cur.get(k) for k in ("5", "10", "30")}
            bonds.update({"d" + k: r2((cur[k] - pv[k]) * 100, 1) for k in ("5", "10", "30") if cur.get(k) is not None and pv.get(k) is not None})
            bonds.update({"tlt": tl.get("chg"), "tltRvol": tl.get("rvol")})
            d10 = bonds.get("d10")
            if d10 is not None:
                if abs(sc) >= 2 and abs(d10) <= 3: fact("bonds", "still", 7, spy=sc, d10=d10, y10=bonds["10"])
                elif sc <= -1.5 and d10 <= -8: fact("bonds", "flight", 7, d5=bonds.get("d5"), d10=d10, d30=bonds.get("d30"), tlt=tl.get("chg"), tltRvol=tl.get("rvol"))
                elif abs(d10) >= 8: fact("bonds", "big_move", 5, d10=d10, y10=bonds["10"])

    # ------------------------------------------------------------------ the AI chain
    rows = []
    for t, seg in CHAIN.items():
        s2, k2 = at(t)
        if not s2 or k2 < 21: continue
        rows.append({"t": t, "seg": seg, "chg": s2.chg(k2), "pos": s2.pos(k2), "rng": s2.rng(k2), "arng": s2.avg_rng(k2), "rvol": s2.rvol(k2),
                     "dd": s2.dd(k2), "hi": s2.c[k2] >= max(s2.c[max(0, k2 - 251):k2]), "lo": s2.c[k2] <= min(s2.c[max(0, k2 - 251):k2]), "streak": s2.streak(k2)})
    chain = None
    if rows:
        ch = [r["chg"] for r in rows]; medc = st.median(ch)
        segs = {}
        for r in rows: segs.setdefault(r["seg"], []).append(r)
        seg_rows = sorted(({"seg": sg, "n": len(v), "avg": r2(sum(x["chg"] for x in v) / len(v)), "bear": sum(x["dd"] <= -20 for x in v)} for sg, v in segs.items()), key=lambda x: -x["avg"])
        def ctrail(d):
            pp, aa, n = [], [], 0
            for t in CHAIN:
                s2, k2 = at(t, d)
                if s2 and k2 >= 21: pp.append(s2.pos(k2)); aa.append(s2.rng(k2)); n += 1
            return {"d": d, "pos": r2(sum(pp) / len(pp) * 100, 1) if pp else None, "rng": r2(sum(aa) / len(aa), 1) if aa else None}
        chain = {"n": len(rows), "up": sum(c > 0 for c in ch), "down": sum(c < 0 for c in ch), "median": r2(medc),
                 "top": [{"t": r["t"], "chg": r2(r["chg"])} for r in sorted(rows, key=lambda r: -r["chg"])[:6]],
                 "bottom": [{"t": r["t"], "chg": r2(r["chg"])} for r in sorted(rows, key=lambda r: r["chg"])[:6]],
                 "segs": seg_rows, "bear": sum(r["dd"] <= -20 for r in rows), "corr": sum(-20 < r["dd"] <= -10 for r in rows),
                 "hi": [r["t"] for r in rows if r["hi"]], "lo": [r["t"] for r in rows if r["lo"]],
                 "pos": r2(sum(r["pos"] for r in rows) / len(rows) * 100, 1), "rng": r2(sum(r["rng"] for r in rows) / len(rows), 1),
                 "upper": sum(r["pos"] >= 0.5 for r in rows), "trail": [ctrail(spy.d[kk]) for kk in range(i - 3, i + 1)]}
        fact("chain", "summary", 1, **{k: chain[k] for k in ("n", "up", "down", "median")})
        multi = [x for x in seg_rows if x["n"] >= 2]   # a one-company segment says little about the chain
        if abs(medc) >= 1.5 and len(multi) >= 3:
            lead = multi[:2] if medc > 0 else multi[-2:][::-1]
            lag = multi[-1] if medc > 0 else multi[0]
            if abs(lead[0]["avg"]) >= 2 * abs(medc):
                fact("chain", "concentration", 6, up=medc > 0, lead=lead, lag=lag, median=r2(medc))
            dec = [r for r in rows if (r["chg"] > 0) != (medc > 0) and abs(r["chg"]) >= 1]
            if dec and len(dec) <= 4: fact("chain", "decoupled", 5, names=[{"t": r["t"], "chg": r2(r["chg"])} for r in sorted(dec, key=lambda r: -abs(r["chg"]))[:3]], median=r2(medc))
        if chain["up"] >= 0.9 * len(rows) or chain["down"] >= 0.9 * len(rows):
            fact("chain", "all_one_way", 6, up=chain["up"] >= 0.9 * len(rows), n=len(rows), k=max(chain["up"], chain["down"]))
        allbear = [x for x in seg_rows if x["n"] >= 3 and x["bear"] == x["n"]]
        if allbear: fact("chain", "seg_all_bear", 3, segs=[x["seg"] for x in sorted(allbear, key=lambda x: -x["n"])], bear=chain["bear"], n=len(rows))   # a standing condition: low weight
        arng = [r["arng"] for r in rows if r["arng"]]
        amp_ratio = chain["rng"] / (sum(arng) / len(arng)) if arng else None
        avg_rv = st.median([r["rvol"] for r in rows if r["rvol"]]) if rows else None
        month_rng = max((x["rng"] or 0) for x in chain["trail"])
        if chain["pos"] >= 75 and amp_ratio and (amp_ratio >= 1.2 or chain["rng"] >= month_rng) and spr["rvol"] and spr["rvol"] <= 1.35:
            fact("chain", "sellers_done", 9, pos=chain["pos"], rng=chain["rng"], ampx=r2(amp_ratio), spyRvol=spr["rvol"], trail=chain["trail"])
        elif chain["pos"] <= 25 and amp_ratio and amp_ratio >= 1.3:
            fact("chain", "sold_into_close", 7, pos=chain["pos"], rng=chain["rng"], trail=chain["trail"])
        if chain["upper"] == len(rows) and not any(f["k"] == "sellers_done" for f in F):
            fact("chain", "all_upper_half", 6, n=len(rows), pos=chain["pos"], trail=chain["trail"])
        if len(chain["lo"]) >= 5 or len(chain["hi"]) >= 5:
            fact("chain", "new_high_low", 4, hi=len(chain["hi"]), lo=len(chain["lo"]), n=len(rows))
        big = [r for r in rows if abs(r["chg"]) >= 15]
        if big: fact("chain", "big_mover", 6, names=[{"t": r["t"], "chg": r2(r["chg"])} for r in sorted(big, key=lambda r: -abs(r["chg"]))[:3]])
        stk = sorted((r for r in rows if r["streak"] <= -5), key=lambda r: r["streak"])
        if stk: fact("chain", "streak", 4, t=stk[0]["t"], n=stk[0]["streak"])
        chain["avgRvol"] = r2(avg_rv); chain["ampx"] = r2(amp_ratio)

    # the last five sessions side by side: each ETF's change, relative volume and close in range, and its rank among them
    days5 = [spy.d[kk] for kk in range(i - 4, i + 1)]
    grid = []
    for t in BOARD:
        s2 = sy.get(t)
        if not s2: continue
        cells = []
        for d in days5:
            k2 = s2.at(d)
            cells.append({"chg": r2(s2.chg(k2)), "rvol": r2(s2.rvol(k2)), "pos": r2(s2.pos(k2))} if k2 else None)
        grid.append({"t": t, "cells": cells})
    def ranks(col):
        xs = sorted((g for g in grid if g["cells"][col] and g["cells"][col]["chg"] is not None), key=lambda g: -g["cells"][col]["chg"])
        return {g["t"]: n + 1 for n, g in enumerate(xs)}
    r_now, r_prev = ranks(4), ranks(3)
    for g in grid: g["rank"] = r_now.get(g["t"]); g["rankPrev"] = r_prev.get(g["t"])
    F.sort(key=lambda f: -f["w"])
    key = [f for f in F if f["w"] >= 6][:2]
    return {"date": day, "prev": prev, "index": idx, "vix": vx, "board": board, "volumes": vols, "volMedian": r2(med), "spyTrail": trail, "days5": days5, "grid": grid,
            "bonds": bonds, "chain": chain, "facts": F, "key": [f["k"] for f in key]}
