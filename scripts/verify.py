#!/usr/bin/env python3
"""Independent check of a day JSON produced by form4_sector.py.

1. Internal reconciliation: filings -> companies -> sectors totals must agree.
2. Source check: for every filing behind the top-10 effective net buyers/sellers, plus a random
   sample, read SEC's own rendered Form 4 page (xslF345 HTML, a different code path from our XML
   parser) and compare open-market P/S shares and dollar values.
Usage: verify.py --ua "Name email" DAY.json [DAY.json ...] [--sample 30]
Exit code 1 if any check fails.
"""
import argparse, json, random, re, html, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from form4_sector import Fetcher, FX, index_paths
import datetime as _dt

def num(s):
    m = re.search(r"-?[\d,]*\.?\d+", s.replace("$", ""))
    return float(m.group(0).replace(",", "")) if m else None

def rendered_ps(f, path):
    m = re.match(r"edgar/data/(\d+)/([\d-]+)\.txt$", path)
    cik, acc = m.group(1), m.group(2).replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/"
    idx = f.get(base + "index.json")
    if idx:
        xmls = [i["name"] for i in json.loads(idx)["directory"]["item"] if i["name"].lower().endswith(".xml")]
        bases = [base]
    else:   # folder may live only under another filer's CIK: read names from the .txt header
        txt = f.get("https://www.sec.gov/Archives/" + path)
        if not txt: return None, "filing not found"
        xmls = [x for x in re.findall(r"<FILENAME>\s*(\S+)", txt) if x.lower().endswith(".xml")]
        ciks = list(dict.fromkeys(re.findall(r"CENTRAL INDEX KEY:\s*(\d+)", txt)))
        bases = [f"https://www.sec.gov/Archives/edgar/data/{int(c)}/{acc}/" for c in ciks]
    if not xmls: return None, "no xml in filing"
    page = None
    for b in bases:
        for v in ("X06", "X05"):
            page = f.get(f"{b}xslF345{v}/{xmls[0]}")
            if page and "Table I" in page: base = b; break
            page = None
        if page: break
    if not page:   # SEC has no rendered page for some filings: fall back to a regex read of the raw XML
        txt = f.get("https://www.sec.gov/Archives/" + path)
        if not txt: return None, "rendered page and raw filing not found"
        out = {"P": [0.0, 0.0], "S": [0.0, 0.0], "rows": []}
        for blk in re.findall(r"<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>", txt, re.S):
            code = re.search(r"<transactionCode>\s*(\w)\s*</transactionCode>", blk)
            sh = re.search(r"<transactionShares>.*?<value>\s*([^<]+?)\s*</value>", blk, re.S)
            px = re.search(r"<transactionPricePerShare>.*?<value>\s*([^<]+?)\s*</value>", blk, re.S)
            if not code or code.group(1) not in out or not sh or not px: continue
            try: shv, pxv = float(sh.group(1)), float(px.group(1))
            except ValueError: continue
            if not shv: continue
            out[code.group(1)][0] += shv; out[code.group(1)][1] += shv * pxv
            out["rows"].append((code.group(1), shv, pxv))
        return out, "https://www.sec.gov/Archives/" + path + " (raw XML; no rendered page)"
    seg = page[page.find("Table I"):page.find("Table II")]
    out = {"P": [0.0, 0.0], "S": [0.0, 0.0], "rows": []}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", seg, re.S):
        cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
                 for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) < 8: continue
        code = re.sub(r"\(\d+\)", "", cells[3]).strip().split("/")[0].strip()
        if code not in ("P", "S"): continue
        cells[3] = code
        sh = num(re.sub(r"\(\d+\)", "", cells[5])); px = num(re.sub(r"\(\d+\)", "", cells[7]))
        if not sh or px is None: continue
        out[cells[3]][0] += sh; out[cells[3]][1] += sh * px
        out["rows"].append((cells[3], sh, px))
    return out, base + f"xslF345X06/{xmls[0]}"

def _v(blk, tag):
    m = re.search(r"<%s>.*?<value>\s*([^<]*?)\s*</value>" % tag, blk, re.S)
    return m.group(1) if m else None

def raw_hold(txt):
    """Independent (regex) recomputation of holdings before/after the filing's purchases."""
    lines, bought, titles = {}, 0.0, set()
    def key(blk):
        return ((_v(blk, "securityTitle") or "").strip().lower(), _v(blk, "directOrIndirectOwnership") or "",
                (_v(blk, "natureOfOwnership") or "").strip().lower())
    for blk in re.findall(r"<nonDerivativeTransaction>(.*?)</nonDerivativeTransaction>", txt, re.S):
        try:
            sh = float(_v(blk, "transactionShares") or 0); post = float(_v(blk, "sharesOwnedFollowingTransaction"))
        except (TypeError, ValueError):
            return None
        code = re.search(r"<transactionCode>\s*(\w)", blk); ad = _v(blk, "transactionAcquiredDisposedCode")
        k = key(blk)
        if code and code.group(1) == "P" and sh: bought += sh; titles.add(k[0])
        if k not in lines: lines[k] = [post - (sh if ad == "A" else -sh), post]
        else: lines[k][1] = post
    for blk in re.findall(r"<nonDerivativeHolding>(.*?)</nonDerivativeHolding>", txt, re.S):
        k = key(blk)
        try: post = float(_v(blk, "sharesOwnedFollowingTransaction"))
        except (TypeError, ValueError): continue
        if k not in lines: lines[k] = [post, post]
    rel = [v for k, v in lines.items() if k[0] in titles]
    if not bought or not rel: return None
    return max(0.0, sum(v[0] for v in rel)), sum(v[1] for v in rel)

def raw_144(txt):
    """Independent regex read of a Form 144: total units to be sold and aggregate market value."""
    m = re.search(r"<XML>(.*?)</XML>", txt or "", re.S)
    if not m: return None
    x = m.group(1)
    if not re.search(r"<(?:\w+:)?submissionType>\s*144\s*</(?:\w+:)?submissionType>", x): return None
    sh = sum(float(v) for v in re.findall(r"<(?:\w+:)?noOfUnitsSold>\s*([\d.]+)\s*</(?:\w+:)?noOfUnitsSold>", x))
    usd = sum(float(v) for v in re.findall(r"<(?:\w+:)?aggregateMarketValue>\s*([\d.]+)\s*</(?:\w+:)?aggregateMarketValue>", x))
    return sh, usd

def check_144(f, d, rng, errs, sample=15):
    """Form 144 notices: none unfetched, none missing from the index, sampled values re-read from source."""
    if "f144" not in d: return 0, 0
    date = d["date"]
    if d.get("f144_unfetched"):
        errs.append(f"{date} {d['f144_unfetched']} Form 144 notice(s) could not be fetched - day is incomplete")
    have = {x["path"] for x in d["f144"]}
    idx = index_paths(f, _dt.date.fromisoformat(date), "144") or []
    for p in idx:
        if p in have: continue
        r = raw_144(f.get("https://www.sec.gov/Archives/" + p))
        if r and r[0] > 0: errs.append(f"{date} Form 144 missing from data: https://www.sec.gov/Archives/{p}")
    pick = sorted(d["f144"], key=lambda x: -x["usd"])[:5]
    rest = [x for x in d["f144"] if x not in pick]
    pick += rng.sample(rest, min(sample, len(rest)))
    ok = 0
    for x in pick:
        r = raw_144(f.get("https://www.sec.gov/Archives/" + x["path"]))
        if r is None: errs.append(f"{date} Form 144 {x['ticker']} {x['path']}: not re-readable"); continue
        if abs(r[0] - x["shares"]) > 1 or abs(r[1] - x["usd"]) > 1:
            errs.append(f"{date} Form 144 {x['ticker']} https://www.sec.gov/Archives/{x['path']}: ours {x['shares']} sh ${x['usd']} vs source {round(r[0])} sh ${round(r[1])}")
        else: ok += 1
    return ok, len(pick)

def close(a, b):
    return abs(a - b) <= max(2.0, 0.001 * max(abs(a), abs(b)))

def check_day(f, path, sample, rng):
    d = json.load(open(path)); errs = []; date = d["date"]
    if d.get("unparsed_filings"):
        errs.append(f"{date} {d['unparsed_filings']} Form 4 filing(s) could not be fetched/parsed - day is incomplete")
    # 1. internal reconciliation
    for k_sec, k_co in (("buy_usd", "buy_usd"), ("sell_usd", "sell_usd"), ("buy_eff_usd", "eff_buy_usd"), ("sell_eff_usd", "eff_sell_usd")):
        a = sum(s.get(k_sec, 0) for s in d["sectors"]); b = sum(c.get(k_co, 0) for c in d["companies"])
        if not close(a, b): errs.append(f"{date} reconcile sectors.{k_sec}={a} vs companies.{k_co}={b}")
    for c in d["companies"]:
        for k_co, k_f in (("buy_usd", "buy"), ("sell_usd", "sell"), ("eff_buy_usd", "eff_buy"), ("eff_sell_usd", "eff_sell")):
            if "eff_buy" in k_f and "eff_buy" not in (c["filings"] or [{}])[0]: continue
            a = c[k_co]; b = sum(x.get(k_f, 0) for x in c["filings"])
            if not close(a, b): errs.append(f"{date} {c['ticker']} reconcile {k_co}={a} vs filings={b}")
    if sample < 0:   # offline: internal reconciliation only
        return 0, 0, errs
    # 2. source check
    cos = d["companies"]
    top = sorted(cos, key=lambda c: c["eff_buy_usd"] - c["eff_sell_usd"])
    chosen = {id(c) for c in top[:10] + top[-10:] if c["eff_buy_usd"] or c["eff_sell_usd"]}
    fl = [(c, x) for c in cos for x in c["filings"] if id(c) in chosen]
    rest = [(c, x) for c in cos for x in c["filings"] if id(c) not in chosen]
    # every foreign-currency filing and every effective purchase is always checked
    fxrest = [(c, x) for c, x in rest if x.get("fx") or x.get("eff_buy")]
    rest = [(c, x) for c, x in rest if not (x.get("fx") or x.get("eff_buy"))]
    fl += fxrest + rng.sample(rest, min(sample, len(rest)))
    ok = 0
    for c, x in fl:
        r, src = rendered_ps(f, x["path"])
        if r is None: errs.append(f"{date} {c['ticker']} {x['path']}: {src}"); continue
        if x.get("fx"):   # foreign-currency prices: convert those SEC rows with an independently fetched rate
            for e in x["fx"]:
                rate = 0.0 if e["usd_per_unit"] == 0 else FXR.usd_per(e["ccy"], e["date"])
                if rate is None or (e["usd_per_unit"] and abs(rate / e["usd_per_unit"] - 1) > 0.002):
                    errs.append(f"{date} {c['ticker']} fx {e['ccy']} {e['date']}: ours={e['usd_per_unit']} check={rate}")
                    rate = e["usd_per_unit"]
                for i, (k, sh, px) in enumerate(r["rows"]):
                    if px is not None and k == e["code"] and close(sh, e["shares"]) and abs(px - e["price_local"]) < 1e-6:
                        r[k][1] += sh * px * (rate - 1); r["rows"][i] = (k, sh, None); break
                else:
                    errs.append(f"{date} {c['ticker']} fx row {e['code']} {e['shares']}@{e['price_local']} {e['ccy']} not found on SEC page")
            sh_unknown = {k: sum(e["shares"] for e in x["fx"] if e["code"] == k and not e["usd_per_unit"]) for k in "PS"}
            r["P"][0] -= sh_unknown["P"]; r["S"][0] -= sh_unknown["S"]
        exp_b = r["P"][1] - x.get("removed_buy", 0); exp_s = r["S"][1] - x.get("removed_sell", 0)
        bad = []
        if not close(exp_b, x["buy"]): bad.append(f"buy ours={x['buy']} sec={round(exp_b)}")
        if not close(exp_s, x["sell"]): bad.append(f"sell ours={x['sell']} sec={round(exp_s)}")
        if not x.get("removed_buy") and not close(r["P"][0], x["buy_sh"]): bad.append(f"buy_sh ours={x['buy_sh']} sec={r['P'][0]}")
        if not x.get("removed_sell") and not close(r["S"][0], x["sell_sh"]): bad.append(f"sell_sh ours={x['sell_sh']} sec={r['S'][0]}")
        if x.get("hold_post") is not None:   # holdings before/after the purchase
            raw = f.get("https://www.sec.gov/Archives/" + x["path"])
            h = raw_hold(raw) if raw else None
            if h is None: bad.append("holdings not recomputable")
            elif abs(h[0] - x["hold_pre"]) > 1 or abs(h[1] - x["hold_post"]) > 1:
                bad.append(f"holdings ours={x['hold_pre']}->{x['hold_post']} check={round(h[0])}->{round(h[1])}")
        if bad: errs.append(f"{date} {c['ticker']} {src}: " + "; ".join(bad))
        else: ok += 1
    return ok, len(fl), errs

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--ua", required=True); ap.add_argument("--sample", type=int, default=30)
    ap.add_argument("--seed", type=int, default=None); ap.add_argument("--only144", action="store_true"); ap.add_argument("files", nargs="+")
    a = ap.parse_args(); f = Fetcher(a.ua); rng = random.Random(a.seed)
    FXR = FX()
    allerr = []
    for p in a.files:
        if a.only144: ok, n, errs = 0, 0, []
        else: ok, n, errs = check_day(f, p, a.sample, rng)
        o144, n144 = check_144(f, json.load(open(p)), rng, errs)
        allerr += errs
        print(f"{os.path.basename(p)}: {ok}/{n} filings match SEC rendered pages; Form 144 {o144}/{n144} match; {len(errs)} problem(s)", flush=True)
        for e in errs: print("  !", e, flush=True)
    sys.exit(1 if allerr else 0)
