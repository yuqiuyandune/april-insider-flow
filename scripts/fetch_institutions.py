"""Institutional holdings -> data/stakes.json (13D/13G) and data/funds.json (13F); the /institutions/ page reads both.

13D / 13G (daily): every new Schedule 13D, 13D/A and 13G in SEC's daily form index (structured XML since 2024): the
company, who filed, the percent of the class and the shares, the event date and, for 13D, the stated purpose.
A 13D is filed by a holder of 5%+ who may seek to influence the company (activists); a 13G by a passive holder.
Only companies with a ticker in SEC's company_tickers.json are kept. Rolling KEEP_DAYS days.

13F (quarterly): the latest two 13F-HR reports of a fixed list of well-known fundamental managers (FUNDS), compared
position by position: new, exited, added (+20% shares or more), trimmed (-20% or more), and the largest holdings.
Option rows (put/call) are left out. A fund is re-read only when it has filed a new report. CUSIPs are turned
into tickers with OpenFIGI's public mapping API and cached in data/cusip_tickers.json.

    python3 -I scripts/fetch_institutions.py --ua "$SEC_UA" [--days N] [--skip-13f] [--skip-13d]
Standard library only.
"""
import argparse, datetime as dt, json, os, re, sys, time, urllib.request, html as H

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
STAKES = os.path.join(ROOT, "data", "stakes.json")
FUNDS = os.path.join(ROOT, "data", "funds.json")
CUSIPS = os.path.join(ROOT, "data", "cusip_tickers.json")
WORK = os.path.join(ROOT, "work")
KEEP_DAYS = 60

# (CIK, zh, tw, en, style) — fundamental managers whose 13F says something about their views; quant and market-making books are left out
FUNDS_LIST = [
    (1067983, "伯克希尔·哈撒韦（巴菲特）", "波克夏·海瑟威（巴菲特）", "Berkshire Hathaway (Buffett)", "value"),
    (1350694, "桥水基金（达利欧创办）", "橋水基金（達利歐創辦）", "Bridgewater Associates", "macro"),
    (1536411, "Duquesne 家族办公室（德鲁肯米勒）", "Duquesne 家族辦公室（杜肯米勒）", "Duquesne Family Office (Druckenmiller)", "macro"),
    (1029160, "索罗斯基金管理", "索羅斯基金管理", "Soros Fund Management", "macro"),
    (1656456, "Appaloosa（泰珀）", "Appaloosa（泰珀）", "Appaloosa (Tepper)", "value"),
    (1061768, "Baupost（卡拉曼）", "Baupost（卡拉曼）", "Baupost (Klarman)", "value"),
    (1040273, "Third Point（勒布）", "Third Point（勒布）", "Third Point (Loeb)", "activist"),
    (1791786, "Elliott（埃利奥特）", "Elliott（艾略特）", "Elliott Investment Management", "activist"),
    (921669, "伊坎", "伊坎", "Carl Icahn", "activist"),
    (1418814, "ValueAct", "ValueAct", "ValueAct", "activist"),
    (1167483, "老虎环球", "老虎環球", "Tiger Global", "growth"),
    (1135730, "Coatue", "Coatue", "Coatue", "growth"),
    (1061165, "Lone Pine", "Lone Pine", "Lone Pine", "growth"),
    (1103804, "Viking Global", "Viking Global", "Viking Global", "growth"),
    (1747057, "D1 Capital", "D1 Capital", "D1 Capital", "growth"),
    (1541617, "Altimeter（格斯特纳）", "Altimeter（格斯特納）", "Altimeter (Gerstner)", "growth"),
    (1387322, "Whale Rock", "Whale Rock", "Whale Rock", "growth"),
    (1697748, "ARK（木头姐）", "ARK（木頭姐）", "ARK Invest (Cathie Wood)", "growth"),
    (1603466, "Point72（科恩）", "Point72（科恩）", "Point72 (Cohen)", "multi"),
    (1569205, "Fundsmith（特里·史密斯）", "Fundsmith（特里·史密斯）", "Fundsmith (Terry Smith)", "quality"),
]
CHANGE = 0.20      # +/-20% in shares counts as added / trimmed
TOP = 12           # largest holdings kept per fund
CHG_TOP = 8        # changes kept per kind per fund

class SEC:
    def __init__(self, ua, rate=8.0):
        self.ua, self.gap, self.last = ua, 1.0 / rate, 0.0
    def get(self, url, tries=4):
        for i in range(tries):
            wait = self.gap - (time.time() - self.last)
            if wait > 0: time.sleep(wait)
            self.last = time.time()
            try:
                req = urllib.request.Request(url, headers={"User-Agent": self.ua, "Accept-Encoding": "identity"})
                with urllib.request.urlopen(req, timeout=60) as r: return r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                if e.code == 404: return None
                time.sleep(2 * (i + 1))
            except Exception:
                time.sleep(2 * (i + 1))
        raise RuntimeError(f"failed: {url}")

def tag(t, name, default=None):
    m = re.search(r"<(?:\w+:)?" + name + r">(.*?)</(?:\w+:)?" + name + ">", t, re.S)
    return H.unescape(re.sub(r"\s+", " ", m.group(1)).strip()) if m else default

def tags(t, name):
    return [H.unescape(re.sub(r"\s+", " ", x).strip()) for x in re.findall(r"<(?:\w+:)?" + name + r">(.*?)</(?:\w+:)?" + name + ">", t, re.S)]

def fnum(s):
    try: return float(str(s).replace(",", ""))
    except (TypeError, ValueError): return None

def mdy(s):
    try: return dt.datetime.strptime(s, "%m/%d/%Y").date().isoformat()
    except (TypeError, ValueError): return None

# ------------------------------------------------------------------ 13D / 13G
FORMS = {"SCHEDULE 13D": "13D", "SCHEDULE 13D/A": "13D/A", "SCHEDULE 13G": "13G"}

def ticker_map(sec):
    j = json.loads(sec.get("https://www.sec.gov/files/company_tickers.json"))
    out = {}
    for v in j.values():
        out.setdefault(int(v["cik_str"]), v["ticker"])   # first listed = primary share class
    return out

def day_filings(sec, d):
    q = (d.month - 1) // 3 + 1
    try: txt = sec.get(f"https://www.sec.gov/Archives/edgar/daily-index/{d.year}/QTR{q}/form.{d:%Y%m%d}.idx", tries=2)
    except RuntimeError: txt = None
    if txt is None: return None   # holiday, or not out yet (SEC answers 403 for an index that does not exist)
    seen, out = set(), []
    for line in txt.splitlines():
        for f, kind in FORMS.items():
            if line.startswith(f + " ") and not line.startswith(f + "/"):
                path = line.split()[-1]
                acc = path.rsplit("/", 1)[-1]   # the same filing is listed under the filer's and the company's folder
                if acc not in seen: seen.add(acc); out.append((kind, path))
    return out

def parse_stake(kind, txt):
    issuer_cik = tag(txt, "issuerCik") or tag(txt, "issuerCIK")
    pct = [fnum(x) for x in tags(txt, "classPercent") + tags(txt, "percentOfClass")]
    shs = [fnum(x) for x in tags(txt, "reportingPersonBeneficiallyOwnedAggregateNumberOfShares") + tags(txt, "aggregateAmountOwned")]
    names = tags(txt, "reportingPersonName")
    types = tags(txt, "typeOfReportingPerson")
    if not issuer_cik or not names: return None
    p = max([x for x in pct if x is not None], default=None)
    s = max([x for x in shs if x is not None], default=None)
    event = mdy(tag(txt, "dateOfEvent") or tag(txt, "eventDateRequiresFilingThisStatement"))
    purpose = tag(txt, "transactionPurpose") if kind.startswith("13D") else None
    return {"kind": kind, "issuerCik": int(issuer_cik), "issuer": tag(txt, "issuerName"), "filer": names[0], "filers": len(set(names)),
            "type": types[0] if types else None, "pct": p, "shares": s, "event": event,
            "purpose": (purpose[:600] if purpose else None)}

def run_13d(sec, days):
    old = json.load(open(STAKES, encoding="utf-8")) if os.path.exists(STAKES) else {"days": [], "items": []}
    have = set(old.get("days", []))
    tmap = ticker_map(sec)
    today = dt.date.today()
    items, done = list(old.get("items", [])), set(have)
    for k in range(days, 0, -1):
        d = today - dt.timedelta(days=k)
        if d.weekday() >= 5 or d.isoformat() in have: continue
        fl = day_filings(sec, d)
        if fl is None: continue
        n = 0
        for kind, path in fl:
            txt = sec.get("https://www.sec.gov/Archives/" + path)
            if not txt: continue
            try: st = parse_stake(kind, txt)
            except Exception as ex: print(f"{path}: {ex}", file=sys.stderr); continue
            if not st or st["issuerCik"] not in tmap: continue
            st.update({"t": tmap[st["issuerCik"]], "filed": d.isoformat(), "url": "https://www.sec.gov/Archives/" + path})
            items.append(st); n += 1
        done.add(d.isoformat())
        print(f"13D/13G {d}: {len(fl)} filings, {n} on listed companies")
    cut = (today - dt.timedelta(days=KEEP_DAYS)).isoformat()
    items = sorted({i["url"].rsplit("/", 1)[-1]: i for i in items if i["filed"] >= cut}.values(), key=lambda i: (i["filed"], i["pct"] or 0), reverse=True)
    out = {"updated": today.isoformat(), "days": sorted(x for x in done if x >= cut), "items": items}
    changed = out["items"] != old.get("items") or out["days"] != old.get("days")
    if changed:
        with open(STAKES, "w", encoding="utf-8") as f: json.dump(out, f, ensure_ascii=False, separators=(",", ":")); f.write("\n")
    return changed

# ------------------------------------------------------------------ 13F
def fund_reports(sec, cik):
    """latest 13F-HR filings, newest first: [(filed, index url)]"""
    a = sec.get(f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=13F-HR&dateb=&owner=include&count=10&output=atom") or ""
    out = []
    for e in re.findall(r"<entry>(.*?)</entry>", a, re.S):
        if tag(e, "filing-type") != "13F-HR": continue
        out.append((tag(e, "filing-date"), tag(e, "filing-href")))
    return out

def read_13f(sec, href):
    txt = sec.get(href.replace("-index.htm", ".txt"))
    period = tag(txt, "periodOfReport")
    pos = {}
    for r in re.findall(r"<(?:\w+:)?infoTable>(.*?)</(?:\w+:)?infoTable>", txt, re.S):
        if tag(r, "putCall"): continue
        if (tag(r, "sshPrnamtType") or "SH") != "SH": continue
        c = (tag(r, "cusip") or "").upper()
        p = pos.setdefault(c, {"name": tag(r, "nameOfIssuer"), "cls": tag(r, "titleOfClass"), "value": 0.0, "shares": 0.0})
        p["value"] += fnum(tag(r, "value")) or 0; p["shares"] += fnum(tag(r, "sshPrnamt")) or 0
    p = period.split("-") if period else None
    return (f"{p[2]}-{p[0]}-{p[1]}" if p and len(p) == 3 else period), pos

def compare(cur, prev):
    tot = sum(p["value"] for p in cur.values()) or 1
    rows = {"top": [], "new": [], "exit": [], "add": [], "trim": []}
    for c, p in cur.items():
        q = prev.get(c)
        w = p["value"] / tot
        rows["top"].append((c, p, w, None))
        if not q or q["shares"] <= 0: rows["new"].append((c, p, w, None))
        elif p["shares"] >= q["shares"] * (1 + CHANGE): rows["add"].append((c, p, w, p["shares"] / q["shares"] - 1))
        elif p["shares"] <= q["shares"] * (1 - CHANGE): rows["trim"].append((c, p, w, p["shares"] / q["shares"] - 1))
    ptot = sum(p["value"] for p in prev.values()) or 1
    for c, q in prev.items():
        if c not in cur: rows["exit"].append((c, q, q["value"] / ptot, -1.0))
    out = {}
    for k, v in rows.items():
        v.sort(key=lambda x: -x[1]["value"])
        out[k] = [{"cusip": c, "name": p["name"], "value": round(p["value"]), "w": round(w, 4), "chg": (round(ch, 3) if ch is not None else None)}
                  for c, p, w, ch in v[: TOP if k == "top" else CHG_TOP]]
        out["n_" + k] = len(v)
    return out, tot

US_TICKER = re.compile(r"^[A-Z]{1,6}(?:[./][A-Z])?$")

def _pick(data, us_only):
    """the US ticker from an OpenFIGI answer: the composite US listing, else the most common ticker on a US venue (codes start with U)"""
    if not data: return None
    if us_only: return data[0].get("ticker")
    from collections import Counter
    c = Counter(d["ticker"] for d in data if str(d.get("exchCode", "")).startswith("U") and US_TICKER.match(d.get("ticker") or ""))
    return c.most_common(1)[0][0] if c else None

def figi(cusips, cache):
    todo = [c for c in cusips if c and c not in cache]
    _figi(todo, cache, True)
    _figi([c for c in todo if cache.get(c) is None], cache, False)   # some listings only answer without the US filter

def _figi(todo, cache, us_only):
    for i in range(0, len(todo), 10):
        batch = todo[i:i + 10]
        body = json.dumps([dict({"idType": "ID_CUSIP", "idValue": c}, **({"exchCode": "US"} if us_only else {})) for c in batch]).encode()
        req = urllib.request.Request("https://api.openfigi.com/v3/mapping", data=body, headers={"Content-Type": "application/json"})
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=60) as r: res = json.loads(r.read().decode())
                break
            except urllib.error.HTTPError as e:
                if e.code == 429: time.sleep(15 * (attempt + 1)); continue
                raise
        else:
            print("openfigi: giving up for now", file=sys.stderr); return
        for c, r in zip(batch, res):
            cache[c] = _pick(r.get("data"), us_only)
        time.sleep(2.6)   # public limit: 25 requests a minute without a key

ABBR = {"hldngs": "holdings", "hldgs": "holdings", "hlds": "holdings", "hldg": "holding", "intl": "international", "finl": "financial",
        "inds": "industries", "techs": "technologies", "tech": "technology", "svcs": "services", "svc": "service", "sys": "systems",
        "pharma": "pharmaceuticals", "pharmaceutical": "pharmaceuticals", "mtrs": "motors", "ent": "entertainment", "grp": "group",
        "amer": "america", "natl": "national", "commun": "communications", "bancorporation": "bancorp"}
DROP = {"inc", "corp", "corporation", "co", "company", "ltd", "limited", "plc", "pl", "sa", "nv", "ag", "se", "the", "lp", "llc",
        "holdings", "holding", "group", "new", "del", "com", "cl", "class", "a", "b", "adr", "ads", "spon", "sponsored", "ord", "shs", "de", "n", "v"}

def norm(name):
    w = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower().replace("&", " and ")).split()
    w = [ABBR.get(x, x) for x in w]
    return " ".join(x for x in w if x not in DROP)

def by_name(sec, names, cache):
    """last resort for CUSIPs OpenFIGI cannot place (foreign issuers' CINS codes, crowded answers): SEC's own name list"""
    j = json.loads(sec.get("https://www.sec.gov/files/company_tickers.json"))
    idx = {}
    for v in j.values():
        idx.setdefault(norm(v["title"]), v["ticker"])
    for c, n in names.items():
        if cache.get(c): continue
        k = norm(n)
        t = idx.get(k)
        if not t and k:
            hits = {tk for nm, tk in idx.items() if nm.startswith(k + " ") or k.startswith(nm + " ")} if len(k) >= 8 else set()
            t = hits.pop() if len(hits) == 1 else None
        if t: cache[c] = t

def run_13f(sec):
    old = json.load(open(FUNDS, encoding="utf-8")) if os.path.exists(FUNDS) else {"funds": []}
    oldf = {f["cik"]: f for f in old.get("funds", [])}
    cache = json.load(open(CUSIPS, encoding="utf-8")) if os.path.exists(CUSIPS) else {}
    funds, changed = [], False
    for cik, zh, tw, en, style in FUNDS_LIST:
        try:
            reps = fund_reports(sec, cik)
            if len(reps) < 2: print(f"13F {en}: fewer than two reports"); continue
            if cik in oldf and oldf[cik].get("filed") == reps[0][0]:
                funds.append(oldf[cik]); continue
            period, cur = read_13f(sec, reps[0][1])
            pperiod, prev = None, {}
            for filed, href in reps[1:]:
                pperiod, prev = read_13f(sec, href)
                if pperiod != period: break
            cmp, tot = compare(cur, prev)
            funds.append({"cik": cik, "n": {"zh": zh, "tw": tw, "en": en}, "style": style, "filed": reps[0][0], "period": period,
                          "prev": pperiod, "total": round(tot), "positions": len(cur), **cmp,
                          "url": reps[0][1]})
            changed = True
            print(f"13F {en}: {period} vs {pperiod}, {len(cur)} positions, new {cmp['n_new']}, exit {cmp['n_exit']}")
        except Exception as ex:
            print(f"13F {en}: FAILED {ex}", file=sys.stderr)
            if cik in oldf: funds.append(oldf[cik])
    need = {r["cusip"] for f in funds for k in ("top", "new", "exit", "add", "trim") for r in f[k]}
    before = len(cache)
    try: figi(sorted(need), cache)
    except Exception as ex: print(f"openfigi: {ex}", file=sys.stderr)
    names = {r["cusip"]: r["name"] for f in funds for k in ("top", "new", "exit", "add", "trim") for r in f[k] if not cache.get(r["cusip"])}
    try: by_name(sec, names, cache)
    except Exception as ex: print(f"name match: {ex}", file=sys.stderr)
    if len(cache) != before or names:
        with open(CUSIPS, "w", encoding="utf-8") as f: json.dump(dict(sorted(cache.items())), f, separators=(",", ":")); f.write("\n")
    for f in funds:
        for k in ("top", "new", "exit", "add", "trim"):
            for r in f[k]: r["t"] = cache.get(r["cusip"])
    # what several funds did with the same stock this quarter
    latest = max((f["period"] for f in funds), default=None)
    agg = {}
    for f in funds:
        if f["period"] != latest: continue
        for k, sign in (("new", 1), ("add", 1), ("exit", -1), ("trim", -1)):
            for r in f[k]:
                if not r.get("t"): continue
                a = agg.setdefault(r["t"], {"t": r["t"], "name": r["name"], "buy": [], "sell": []})
                (a["buy"] if sign > 0 else a["sell"]).append(f["cik"])
    cons = sorted(agg.values(), key=lambda a: (-(len(a["buy"]) - len(a["sell"])), -len(a["buy"])))
    out = {"updated": dt.date.today().isoformat(), "period": latest, "funds": funds,
           "buying": [a for a in cons if len(a["buy"]) >= 2 and len(a["buy"]) > len(a["sell"])][:15],
           "selling": [a for a in sorted(agg.values(), key=lambda a: (-(len(a["sell"]) - len(a["buy"])), -len(a["sell"]))) if len(a["sell"]) >= 2 and len(a["sell"]) > len(a["buy"])][:15]}
    changed = changed or out["funds"] != old.get("funds")
    if changed:
        with open(FUNDS, "w", encoding="utf-8") as f: json.dump(out, f, ensure_ascii=False, separators=(",", ":")); f.write("\n")
    return changed

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ua", default=os.environ.get("SEC_UA", ""))
    ap.add_argument("--days", type=int, default=10, help="13D/13G: look back this many calendar days for missing days")
    ap.add_argument("--skip-13f", action="store_true"); ap.add_argument("--skip-13d", action="store_true")
    a = ap.parse_args()
    if not a.ua: sys.exit("--ua is required (a contact, as for SEC)")
    sec = SEC(a.ua)
    ch = False
    if not a.skip_13d: ch |= run_13d(sec, a.days)
    if not a.skip_13f: ch |= run_13f(sec)
    if ch:
        os.makedirs(WORK, exist_ok=True); open(os.path.join(WORK, "inst_changed"), "w").write("1")
    print(f"changed={ch}")

if __name__ == "__main__":
    main()
