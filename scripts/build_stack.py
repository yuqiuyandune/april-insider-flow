#!/usr/bin/env python3
"""Build stack/data.json for the five-layer AI supply-chain chart (stack/index.html).

  python3 scripts/build_stack.py            # reads stack/*.csv, stack/taxonomy.json, data/days/*.json
  python3 scripts/build_stack.py energy     # same files under energy/ -> energy/data.json (the energy chain)

Sources
  stack/company_master.csv  the company list (edit this): layer, segment, type (核心 / 热门), reason, extra layers
  stack/company_i18n.csv    Traditional-Chinese name/reason and English reason per ticker
  stack/taxonomy.json       layer and segment names (zh / tw / en), layer hues, not-yet-listed tickers
  data/days/*.json          the site's own verified Form 4 data (effective trades only)

Insider overlay = the last 30 days (filing dates) up to the newest day in data/days:
  buy / sell = sum of effective buy / sell USD (the site's definition: excludes 10b5-1 plans, option exercises,
  tax sales, IPO/offering and SPAC purchases); filed = number of filing days that mention the company.
"""
import csv, glob, json, os, re, sys, datetime as dt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THEMES = {"stack": "energy", "energy": "stack"}   # theme folder -> the other theme (for "also in" links)
THEME = sys.argv[1] if len(sys.argv) > 1 else "stack"
if THEME not in THEMES:
    sys.exit(f"unknown theme {THEME!r}; expected one of {sorted(THEMES)}")
S = lambda *p: os.path.join(ROOT, THEME, *p)
WINDOW_DAYS = 30


def read_csv(path):
    return list(csv.DictReader(open(path, encoding="utf-8-sig")))


def main():
    tax = json.load(open(S("taxonomy.json"), encoding="utf-8"))
    layer_by_zh = {l["zh"]: l["id"] for l in tax["layers"]}
    seg_by_zh = {s["zh"]: s for s in tax["segments"]}
    master = read_csv(S("company_master.csv"))
    i18n = {r["ticker"]: r for r in read_csv(S("company_i18n.csv"))}

    files = sorted(glob.glob(os.path.join(ROOT, "data", "days", "*.json")))
    days = [json.load(open(f, encoding="utf-8")) for f in files]
    asof = max(d["date"] for d in days)
    start = (dt.date.fromisoformat(asof) - dt.timedelta(days=WINDOW_DAYS - 1)).isoformat()
    first = min(d["date"] for d in days)

    mine = {r["ticker"] for r in master}
    other_path = os.path.join(ROOT, THEMES[THEME], "company_master.csv")
    other = {r["ticker"] for r in read_csv(other_path)} if os.path.exists(other_path) else set()
    agg = {t: {"seen": False, "filed": 0, "buy": 0, "sell": 0, "page": None} for t in mine}
    for d in days:
        for c in d.get("companies") or []:
            toks = [t for t in re.split(r"[,\s]+", (c.get("ticker") or "").strip().upper()) if t]
            for t in toks:
                if t in mine:
                    a = agg[t]; a["seen"] = True; a["page"] = a["page"] or toks[0]
                    if d["date"] >= start:
                        a["filed"] += 1
                        a["buy"] += c.get("eff_buy_usd", 0) or 0
                        a["sell"] += c.get("eff_sell_usd", 0) or 0

    comps = []
    for r in master:
        t = r["ticker"]; x = i18n.get(t)
        if x is None:
            sys.exit(f"company_i18n.csv has no row for {t}")
        seg = seg_by_zh.get(r["环节"])
        if seg is None:
            sys.exit(f"{t}: unknown segment {r['环节']!r} (add it to taxonomy.json)")
        if layer_by_zh.get(r["层"]) != seg["layer"]:
            sys.exit(f"{t}: segment {r['环节']!r} belongs to layer {seg['layer']}, not {r['层']!r}")
        also = [layer_by_zh[n] for n in re.split(r"[;；]", r["涉及层"]) if n.strip()]
        a = agg[t]
        comps.append({
            "t": t,
            "name": {"zh": r["中文名"], "tw": x["name_tw"], "en": r["英文名"]},
            "seg": seg["id"], "type": "core" if r["类型"] == "核心" else "hot",
            "reason": {"zh": r["入选理由"], "tw": x["reason_tw"], "en": x["reason_en"]},
            "also": also,
            **({"cross": THEMES[THEME]} if t in other else {}),
            "listed": t not in tax.get("unlisted", []),
            "seen": a["seen"],
            "page": a["page"] if a["seen"] else None,
            "ins": {"filed": a["filed"], "buy": a["buy"], "sell": a["sell"]},
        })

    out = {"asof": asof, "first": first, "window": {"from": start, "to": asof, "days": WINDOW_DAYS},
           "layers": [{k: l[k] for k in ("id", "hue", "name", "sub")} for l in tax["layers"]],
           "segments": [{"id": s["id"], "layer": s["layer"], "name": s["name"]} for s in tax["segments"]],
           "companies": comps}
    json.dump(out, open(S("data.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"{THEME}/data.json: {len(comps)} companies, insider window {start}..{asof}, "
          f"{sum(1 for c in comps if c['ins']['filed'])} with filings in window")


if __name__ == "__main__":
    main()
