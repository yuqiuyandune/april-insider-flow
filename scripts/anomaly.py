#!/usr/bin/env python3
"""Sanity alarms for day files. They never block publishing.

Usage: anomaly.py HISTORY_DIR DAY.json [DAY.json ...]
  HISTORY_DIR: folder of stored day JSONs (baselines); the DAY files are the ones checked.

Two tiers:
  "!!" URGENT - probably a data error; the daily routine sends these as a push notification.
     ccy_note    the price footnote names a foreign currency, it was NOT converted, and USD is not
                 mentioned, on a trade >= $1M (a safety net for currency patterns the converter misses;
                 under the old code ASX / UMC would have fired here)
     price_jump  a trade >= $1M whose price differs >= 8x from EVERY price that company has had in
                 the other stored days (unit / currency / typo errors)
     fx_unknown  a foreign-currency trade with no FX rate (left out of totals)
  "~" REVIEW - usually real, worth a glance; printed in the run log only.
     big_eff     single effective purchase >= $10M or effective sale >= $100M
     concentrate one listed company >= 25% of the day's buys or sales and >= $100M
     day_spike   the day's total buys or sales >= 4x the median of the previous 20 days
     flagged     trades excluded as likely filer errors (> $1B or > $10k/share)
Prints "DATE: U urgent, R to review" then the alarm lines. Exit code 0 always.
"""
import glob, json, os, statistics, sys

URGENT_MIN_USD = 1_000_000
PRICE_X = 8.0
BIG_EFF_BUY, BIG_EFF_SELL = 10_000_000, 100_000_000
CONC_SHARE, CONC_MIN = 0.25, 100_000_000
SPIKE_X = 4.0
NOT_STOCK = {"fund", "nontraded", "offering", "spac"}


def load(p):
    d = json.load(open(p, encoding="utf-8"))
    return d["data"] if isinstance(d, dict) and "sectors" not in d and "data" in d else d


def fmt(v):
    return f"${v/1e6:.1f}M" if abs(v) >= 1e6 else f"${v/1e3:.0f}K"


def url(f):
    return "https://www.sec.gov/Archives/" + f["path"]


def company_prices(d, min_usd=0):
    out = {}
    for c in d["companies"]:
        for f in c.get("filings") or []:
            for usd, sh in ((f.get("buy", 0), f.get("buy_sh", 0)), (f.get("sell", 0), f.get("sell_sh", 0))):
                if usd and sh and usd >= min_usd:
                    out.setdefault(c.get("cik") or c.get("ticker"), []).append(usd / sh)
    return out


def check(day, hist):
    date = day["date"]; urgent, review = [], []
    tb = sum(s["buy_usd"] for s in day["sectors"]); ts = sum(s["sell_usd"] for s in day["sectors"])
    for c in day["companies"]:
        tk = c.get("ticker") or c.get("name", "")[:30]
        fs = c.get("filings") or []
        for f in fs:
            val = f.get("buy", 0) + f.get("sell", 0)
            if "ccy_note" in (f.get("flags") or []) and val >= URGENT_MIN_USD:
                urgent.append(f"ccy_note {tk}: price footnote names a foreign currency but the price was taken as USD "
                              f"({fmt(val)}) - check the footnote {url(f)}")
            if f.get("eff_buy", 0) >= BIG_EFF_BUY:
                review.append(f"big_eff {tk}: effective purchase {fmt(f['eff_buy'])} by {f.get('who','')[:60]} {url(f)}")
            if f.get("eff_sell", 0) >= BIG_EFF_SELL:
                review.append(f"big_eff {tk}: effective sale {fmt(f['eff_sell'])} by {f.get('who','')[:60]} {url(f)}")
        if fs and all(set(f.get("flags") or []) & NOT_STOCK for f in fs):
            continue
        for k, tot, lab in (("buy_usd", tb, "buys"), ("sell_usd", ts, "sales")):
            if tot and c.get(k, 0) >= CONC_MIN and c[k] / tot >= CONC_SHARE:
                review.append(f"concentrate {tk}: {fmt(c[k])} = {c[k]/tot:.0%} of the day's {lab}")
    prev = sorted((h for h in hist if h["date"] < date), key=lambda h: h["date"])[-20:]
    if len(prev) >= 5:
        for k, tot, lab in (("buy_usd", tb, "buys"), ("sell_usd", ts, "sales")):
            med = statistics.median(sum(s[k] for s in h["sectors"]) for h in prev)
            if med and tot >= SPIKE_X * med:
                review.append(f"day_spike total {lab} {fmt(tot)} = {tot/med:.1f}x the 20-day median {fmt(med)}")
    base = {}
    for h in hist:
        if h["date"] != date:
            for k, v in company_prices(h).items():
                base.setdefault(k, []).extend(v)
    tick = {c.get("cik") or c.get("ticker"): c.get("ticker") or c.get("name", "")[:30] for c in day["companies"]}
    for k, v in company_prices(day, URGENT_MIN_USD).items():
        if len(base.get(k, [])) >= 2:
            now = statistics.median(v)
            refs = [r for r in base[k] if r > 0]
            # compare with the CLOSEST earlier price, so a second share class / ADS level seen before
            # (e.g. PAM ordinary ~$3 vs ADS ~$80) does not alarm every time
            near = min(refs, key=lambda r: max(now / r, r / now)) if refs and now > 0 else None
            if near and max(now / near, near / now) >= PRICE_X:
                urgent.append(f"price_jump {tick.get(k, k)}: avg price ${now:,.2f} vs its usual "
                              f"${statistics.median(refs):,.2f} (closest earlier ${near:,.2f})")
    for f in day.get("flagged") or []:
        if str(f.get("reason", "")).startswith("price in foreign currency"):
            urgent.append(f"fx_unknown {f.get('ticker')}: {f.get('shares')} sh @ {f.get('price')} {f.get('ccy')} "
                          f"left out of totals {f.get('url')}")
        else:
            review.append(f"flagged {f.get('ticker')}: {f.get('code')} {fmt(f.get('usd') or 0)} excluded as likely error {f.get('url')}")
    return urgent, review


def main():
    hdir, files = sys.argv[1], sys.argv[2:]
    hist = [load(p) for p in glob.glob(os.path.join(hdir, "*.json"))]
    hist = [h for h in hist if isinstance(h, dict) and h.get("sectors")]
    for p in files:
        d = load(p)
        u, r = check(d, hist)
        print(f"{d['date']}: {len(u)} urgent, {len(r)} to review")
        for a in u: print("  !!", a)
        for a in r: print("  ~", a)


if __name__ == "__main__":
    main()
