#!/usr/bin/env python3
"""Consistency checks for data/days/*.json (schema 2). Exit 1 on any failure.

Checks, per day:
  - file name matches `date`, schema == 2, weekday, all 12 sectors present
  - every company's sector is one of the 12
  - company buy/sell totals == sum of its filings (rounding tolerance)
  - sector buy/sell, effective buy/sell, filing counts == sum over companies
  - no unparsed filings
Across days: warns about weekday gaps not listed in HOLIDAYS; with --expect-latest,
gaps and a missing latest weekday are failures.

Usage: python3 scripts/check_data.py [--dir data/days] [--only DATE ...] [--expect-latest]
"""
import argparse, collections, datetime as dt, glob, json, os, sys

SECTORS = ["Basic Materials", "Communication Services", "Consumer Cyclical", "Consumer Defensive",
           "Energy", "Financial Services", "Healthcare", "Industrials", "Real Estate", "Technology",
           "Utilities", "Unclassified"]

# EDGAR closed (federal holidays) — no daily index is published.
HOLIDAYS = {
    "2026-07-03", "2026-09-07", "2026-10-12", "2026-11-11", "2026-11-26", "2026-12-25",
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-05-31", "2027-06-18", "2027-07-05",
    "2027-09-06", "2027-10-11", "2027-11-11", "2027-11-25", "2027-12-24", "2027-12-31",
}


def check_day(path):
    errs = []
    d = json.load(open(path, encoding="utf-8"))
    name = os.path.basename(path)[:-5]
    if d.get("date") != name:
        errs.append(f"date field {d.get('date')} != file name")
    if d.get("schema") != 2:
        errs.append(f"schema {d.get('schema')} != 2")
    if dt.date.fromisoformat(name).weekday() >= 5:
        errs.append("weekend date")
    if d.get("unparsed_filings"):
        errs.append(f"{d['unparsed_filings']} unparsed filings")
    secs = {s["sector"]: s for s in d.get("sectors", [])}
    if sorted(secs) != sorted(SECTORS):
        errs.append(f"sectors present: {sorted(secs)}")
    agg = collections.defaultdict(collections.Counter)
    for c in d.get("companies", []):
        tag = c.get("ticker") or c.get("cik")
        if c["sector"] not in SECTORS:
            errs.append(f"{tag}: unknown sector {c['sector']}")
        nf = max(1, len(c["filings"]))
        for side in ("buy", "sell"):
            fsum = sum(x[side] for x in c["filings"])
            if abs(fsum - c[f"{side}_usd"]) > nf:
                errs.append(f"{tag}: {side}_usd {c[side+'_usd']} != filings sum {fsum}")
        a = agg[c["sector"]]
        for k in ("buy_usd", "sell_usd", "buy_filings", "sell_filings", "eff_buy_usd", "eff_sell_usd"):
            a[k] += c[k]
    for s, S in secs.items():
        a = agg[s]
        tol = max(5, a["buy_filings"] + a["sell_filings"])
        pairs = [("buy_usd", "buy_usd"), ("sell_usd", "sell_usd"),
                 ("buy_eff_usd", "eff_buy_usd"), ("sell_eff_usd", "eff_sell_usd")]
        for sk, ck in pairs:
            if abs(S.get(sk, 0) - a[ck]) > tol:
                errs.append(f"{s}: {sk} {S.get(sk, 0)} != companies sum {a[ck]}")
        for k in ("buy_filings", "sell_filings"):
            if S[k] != a[k]:
                errs.append(f"{s}: {k} {S[k]} != companies sum {a[k]}")
    return errs


def expected_dates(first, last):
    d = first
    while d <= last:
        if d.weekday() < 5 and d.isoformat() not in HOLIDAYS:
            yield d.isoformat()
        d += dt.timedelta(days=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/days")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--expect-latest", action="store_true",
                    help="fail if the last completed weekday (US Eastern) is missing")
    a = ap.parse_args()
    files = sorted(glob.glob(os.path.join(a.dir, "*.json")))
    if not files:
        print("no data files"); sys.exit(1)
    failed = 0
    targets = [f for f in files if not a.only or os.path.basename(f)[:-5] in a.only]
    for f in targets:
        errs = check_day(f)
        if errs:
            failed += 1
            print(f"FAIL {os.path.basename(f)}")
            for e in errs[:20]:
                print("   ", e)
    have = {os.path.basename(f)[:-5] for f in files}
    first = dt.date.fromisoformat(min(have))
    last = dt.date.fromisoformat(max(have))
    if a.expect_latest:
        # filings for date D are complete by ~22:00 ET on D; the job runs after that
        et_now = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=4)
        last = et_now.date()
        while last.weekday() >= 5 or last.isoformat() in HOLIDAYS:
            last -= dt.timedelta(days=1)
    missing = [x for x in expected_dates(first, last) if x not in have]
    if missing:
        # a withheld day leaves a gap until a later run fills it: warn, but don't block deploys
        # (with --expect-latest, a missing date is a failure)
        if a.expect_latest:
            failed += 1
        print("WARNING missing dates:", ", ".join(missing))
    print(f"checked {len(targets)} day files ({min(have)} to {max(have)}), {failed} problem(s)")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
