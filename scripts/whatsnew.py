#!/usr/bin/env python3
"""The "launched this week" lines at the top of the weekly email.

Usage: whatsnew.py WEEK.json --out NEWS.json [--today YYYY-MM-DD] [--index URL_OR_FILE]

- Earnings: compares the live Earnings Lens index (april-insider-flow.com/earnings/data/index.json)
  with data/earnings_seen.json (what earlier emails already announced). A company is listed if it is
  new or its latest quarter changed. If the index can't be fetched, the earnings part is left out
  (the email still goes) and earnings_seen.json is not touched, so next week catches up.
- Features: entries in data/whatsnew.json dated from the week's first day to today.
  Format: [{"date": "YYYY-MM-DD", "zh": "...", "en": "..."}]

Writes {"zh": markdown, "en": markdown, "seen": {ticker: quarter}}; "seen" is what earnings_seen.json
should become once the email is sent (weekly-email.yml writes it back only after a real send).
"""
import argparse, datetime as dt, json, os, urllib.request

SITE = "https://april-insider-flow.com"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEEN = os.path.join(ROOT, "data", "earnings_seen.json")
NOTES = os.path.join(ROOT, "data", "whatsnew.json")


def load_index(src):
    if os.path.exists(src):
        return json.load(open(src, encoding="utf-8"))
    req = urllib.request.Request(src, headers={"User-Agent": "april-stock-atlas weekly email", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("week"); ap.add_argument("--out", required=True)
    ap.add_argument("--today", default=dt.date.today().isoformat())
    ap.add_argument("--index", default=SITE + "/earnings/data/index.json")
    a = ap.parse_args()
    week = json.load(open(a.week, encoding="utf-8"))
    seen = json.load(open(SEEN, encoding="utf-8")) if os.path.exists(SEEN) else {}

    new, new_seen = [], dict(seen)
    try:
        idx = load_index(a.index)
        for c in idx.get("companies", []):
            t, q = c.get("t"), c.get("latest")
            if not t or not q: continue
            new_seen[t] = q
            if seen.get(t) != q:
                new.append(c)
        new.sort(key=lambda c: (c.get("latestDate") or "", c["t"]))
    except Exception as e:  # never block the email on this
        print("earnings index not available:", e)
        new_seen = None

    notes = json.load(open(NOTES, encoding="utf-8")) if os.path.exists(NOTES) else []
    feats = [n for n in notes if week["week_from"] <= n.get("date", "") <= a.today]

    link = lambda c, name: f"[{name}]({SITE}/earnings/#{c['t']})"
    zh, en = [], []
    if new:
        zh.append(f"财报解读新增 {len(new)} 家：" + "、".join(link(c, c.get("n") or c["t"]) for c in new) + "。")
        en.append(f"{len(new)} new earnings reports: " + ", ".join(link(c, c.get("en") or c.get("n") or c["t"]) for c in new) + ".")
    if feats:
        zh.append("新功能：" + "；".join(n["zh"].rstrip("。；") for n in feats) + "。")
        en.append("New features: " + "; ".join(n["en"].rstrip(".;") for n in feats) + ".")
    out = {"zh": ("**本周上线**　" + "".join(zh)) if zh else "",
           "en": ("**New this week.** " + " ".join(en)) if en else "",
           "seen": new_seen}
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(out["zh"]); print(out["en"])


if __name__ == "__main__":
    main()
