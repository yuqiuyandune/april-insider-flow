"""Market state light (市场状态灯) for /market/: one light for the whole market (SPY) and one per sector ETF.

Rules only, from daily closes and volumes that scripts/fetch_volume.py already reads. Nothing here is a forecast.

Market (SPY), seven checks:
  above200   close above the 200-day moving average
  rising200  200-day average higher than 20 sessions ago
  above50    close above the 50-day moving average
  dist       fewer than 5 distribution days in the last 25 sessions
             (a distribution day: SPY down 0.2% or more on higher volume than the session before; it drops out
              after 25 sessions or once SPY closes 5% above that day's close, as in IBD's method)
  dd         less than 10% below the 52-week closing high
  breadth    at least 6 of the 11 sector ETFs above their 200-day average
  vix        VIX close below 25 (skipped when there is no VIX data)
State:
  green   above200 and rising200 and at most two checks failed
  red     (below the 200-day and the 200-day not rising) or 20%+ below the high or at most two checks passed;
          a valid follow-through day in the last 25 sessions lifts red to yellow
  yellow  anything else
Follow-through day: after a pullback of 7% or more to the lowest close of the last 60 sessions, day 4 or later
of the rally that started there, SPY up 1.25% or more on higher volume than the day before, and no close below
that low since.

Sector ETF (and SOXX/SMH): absolute = close above the 200-day and the 200-day rising; relative = the ETF/SPY
ratio above its own 50-day average. Both: green; one: yellow; neither: red.
"""

SECTOR_ETFS = ["XLK", "XLC", "XLY", "XLP", "XLE", "XLF", "XLV", "XLI", "XLB", "XLRE", "XLU"]
THEME_ETFS = ["SOXX", "SMH"]

def _ma(c, n, end=None):
    c = c if end is None else c[:end]
    return sum(c[-n:]) / n if len(c) >= n else None

def distribution_days(rows, window=25):
    """dates of the distribution days still counting at the last session"""
    c = [r[4] for r in rows]; v = [r[5] for r in rows]; d = [r[0] for r in rows]
    n = len(c); out = []
    for i in range(max(1, n - window), n):
        if c[i] / c[i - 1] - 1 <= -0.002 and v[i] > v[i - 1] > 0:
            if max(c[i + 1:], default=0) >= c[i] * 1.05: continue   # rallied 5% past it
            out.append(d[i])
    return out

def follow_through(rows, look=60, recent=25):
    """date of a valid follow-through day in the last `recent` sessions, else None"""
    c = [r[4] for r in rows]; v = [r[5] for r in rows]; d = [r[0] for r in rows]
    n = len(c)
    if n < look + 2: return None
    lo_i = min(range(n - look, n), key=lambda i: c[i])
    prior_hi = max(c[max(0, lo_i - 252):lo_i + 1])
    if c[lo_i] > prior_hi * 0.93: return None                      # no real pullback
    for i in range(lo_i + 4, n):                                    # day 4+ counting the low as day 0... rally day 1 is lo_i+1
        if c[i] / c[i - 1] - 1 >= 0.0125 and v[i] > v[i - 1] > 0:
            if i < n - recent: return None
            return d[i]
    return None

def market(H, vix=None):
    rows = H.get("SPY")
    if not rows or len(rows) < 230: return None
    c = [r[4] for r in rows]; last = c[-1]
    m200, m200_ago, m50 = _ma(c, 200), _ma(c, 200, -20), _ma(c, 50)
    hi = max(c[-252:])
    dd = (last / hi - 1) * 100
    dist = distribution_days(rows)
    sec_above = sum(1 for s in SECTOR_ETFS if H.get(s) and len(H[s]) >= 200 and H[s][-1][4] >= _ma([r[4] for r in H[s]], 200))
    sec_n = sum(1 for s in SECTOR_ETFS if H.get(s) and len(H[s]) >= 200)
    vx = None
    if vix:
        k = rows[-1][0] if rows[-1][0] in vix else max((x for x in vix if x <= rows[-1][0]), default=None)
        if k: vx = vix[k][3] if isinstance(vix[k], (list, tuple)) else vix[k]
    checks = [
        {"k": "above200", "ok": last >= m200, "v": round((last / m200 - 1) * 100, 1)},
        {"k": "rising200", "ok": m200 > m200_ago, "v": round((m200 / m200_ago - 1) * 100, 2)},
        {"k": "above50", "ok": last >= m50, "v": round((last / m50 - 1) * 100, 1)},
        {"k": "dist", "ok": len(dist) < 5, "v": len(dist)},
        {"k": "dd", "ok": dd > -10, "v": round(dd, 1)},
        {"k": "breadth", "ok": sec_n > 0 and sec_above * 2 >= sec_n + 1, "v": f"{sec_above}/{sec_n}"},
    ]
    if vx is not None: checks.append({"k": "vix", "ok": vx < 25, "v": round(vx, 1)})
    ok = sum(x["ok"] for x in checks); bad = len(checks) - ok
    up, rising = checks[0]["ok"], checks[1]["ok"]
    ftd = follow_through(rows)
    if up and rising and bad <= 2: state = "green"
    elif (not up and not rising) or dd <= -20 or ok <= 2: state = "yellow" if ftd else "red"
    else: state = "yellow"
    return {"state": state, "ok": ok, "n": len(checks), "checks": checks, "dist": dist, "ftd": ftd, "close": round(last, 2)}

def sector(H, sym):
    rows, spy = H.get(sym), H.get("SPY")
    if not rows or not spy or len(rows) < 230: return None
    c = [r[4] for r in rows]; last = c[-1]
    m200, m200_ago = _ma(c, 200), _ma(c, 200, -20)
    sp = {r[0]: r[4] for r in spy}
    ratio = [r[4] / sp[r[0]] for r in rows if r[0] in sp and sp[r[0]]]
    if len(ratio) < 50: return None
    r50 = sum(ratio[-50:]) / 50
    absolute = last >= m200 and m200 > m200_ago
    relative = ratio[-1] >= r50
    state = "green" if absolute and relative else "red" if not absolute and not relative else "yellow"
    rs1m = (ratio[-1] / ratio[-22] - 1) * 100 if len(ratio) > 22 else None
    return {"state": state, "abs": absolute, "rel": relative, "above200": last >= m200, "rising200": m200 > m200_ago,
            "rs1m": round(rs1m, 1) if rs1m is not None else None}

def compute(H, vix=None):
    out = {"date": H["SPY"][-1][0] if H.get("SPY") else None, "market": market(H, vix), "sectors": {}}
    for s in SECTOR_ETFS + THEME_ETFS:
        r = sector(H, s)
        if r: out["sectors"][s] = r
    return out
