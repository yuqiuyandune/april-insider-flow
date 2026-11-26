"""Fetch the official US macro release schedules into data/macro.json (the /calendar/ page reads it).

Sources (all official, read as published; nothing is typed in by hand):
  fomc  federalreserve.gov  FOMC meetings (decision 14:00 ET on the second day; * = with projections/dot plot)
  cpi   bls.gov             Consumer Price Index
  jobs  bls.gov             Employment Situation (nonfarm payrolls)
  ppi   bls.gov             Producer Price Index
  bea   bea.gov             Personal Income and Outlays (PCE price index) and GDP estimates
  nyse  nyse.com            market holidays and 13:00 ET early closes

Each source is replaced only when it parses cleanly; a source that fails keeps its previous events and
is listed in work/macro_problems.md (the daily workflow opens an issue for it). BLS refuses requests
without a contact, so pass the same --ua as for SEC ("Name email@example.com").

    python3 -I scripts/fetch_macro.py --ua "$SEC_UA" [--force] [--offline DIR]

--offline DIR reads <source>.html files from DIR instead of the network (for testing the parsers).
Without --force a source fetched successfully in the last 3 days is skipped.
Standard library only (the workflow runs plain python3 -I).
"""
import argparse, datetime as dt, html, json, os, re, sys, urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "data", "macro.json")
WORK = os.path.join(ROOT, "work")
KEEP_PAST_DAYS = 120
MAX_AGE_DAYS = 3
REPORT_EVERY_DAYS = 7

URLS = {
    "fomc": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
    "cpi": "https://www.bls.gov/schedule/news_release/cpi.htm",
    "jobs": "https://www.bls.gov/schedule/news_release/empsit.htm",
    "ppi": "https://www.bls.gov/schedule/news_release/ppi.htm",
    "bea": "https://www.bea.gov/news/schedule/full",
    "nyse": "https://www.nyse.com/markets/hours-calendars",
}
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                       "september", "october", "november", "december"], 1)}

def month_no(s):
    s = s.strip().lower().rstrip(".")
    for name, n in MONTHS.items():
        if name.startswith(s[:3]) and (len(s) <= 4 or name.startswith(s)):  # "Sept", "Sep", "Dec", "December"
            return n
    raise ValueError(f"month? {s!r}")

def text(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()

def hm(s):
    """'8:30 AM' / '08:30 AM' / '10:00 a.m.' -> '08:30' (24h)"""
    m = re.search(r"(\d{1,2}):(\d{2})\s*([ap])\.?m", s, re.I)
    if not m: raise ValueError(f"time? {s!r}")
    h = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "p" else 0)
    return f"{h:02d}:{m.group(2)}"

def iso(y, m, d): return dt.date(y, m, d).isoformat()

# ------------------------------------------------------------------ parsers (each returns a list of events)
def parse_fomc(page):
    ev = []
    heads = list(re.finditer(r"(\d{4}) FOMC Meetings", page))
    for i, h in enumerate(heads):
        year = int(h.group(1))
        if year < dt.date.today().year - 1: continue
        block = page[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(page)]
        for row in re.findall(r'class="[^"]*fomc-meeting__month[^"]*"[^>]*>(.*?)</div>\s*<div class="[^"]*fomc-meeting__date[^"]*"[^>]*>(.*?)</div>', block, re.S):
            mon, day = text(row[0]), text(row[1])
            m = re.fullmatch(r"(\d{1,2})-(\d{1,2})(\*?)", day.replace(" ", ""))
            if not m: continue  # notation votes, unscheduled meetings
            ms = mon.split("/")
            m1 = month_no(ms[0]); m2 = month_no(ms[-1])
            d1, d2 = int(m.group(1)), int(m.group(2))
            ev.append({"date": iso(year, m2, d2), "time": "14:00", "kind": "fomc", "start": iso(year, m1, d1), "sep": bool(m.group(3))})
    if len(ev) < 8: raise ValueError(f"only {len(ev)} FOMC meetings found")
    return ev

def parse_bls(page, kind):
    ev = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = [text(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)]
        if len(cells) < 3: continue
        rm = re.fullmatch(r"([A-Za-z]+)\.? (\d{4})", cells[0])
        dm = re.search(r"([A-Za-z]+)\.? (\d{1,2}), (\d{4})", cells[1])
        if not (rm and dm): continue
        ev.append({"date": iso(int(dm.group(3)), month_no(dm.group(1)), int(dm.group(2))), "time": hm(cells[2]), "kind": kind,
                   "ref": f"{int(rm.group(2))}-{month_no(rm.group(1)):02d}"})
    if len(ev) < 6: raise ValueError(f"only {len(ev)} {kind} releases found")
    return ev

def parse_bea(page):
    ym = re.search(r'href="/news/(\d{4})/', page)
    year = int(ym.group(1)) if ym else dt.date.today().year
    ev, last = [], 0
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        dm = re.search(r'class="release-date"[^>]*>\s*([A-Za-z]+) (\d{1,2})\s*<', row)
        tm = re.search(r'<small[^>]*>([^<]*[AP]M)', row)
        tl = re.search(r'class="release-title[^"]*"[^>]*>(.*?)</td>', row, re.S)
        if not (dm and tm and tl): continue
        mon = month_no(dm.group(1))
        if mon < last: year += 1
        last = mon
        title = text(tl.group(1))
        base = {"date": iso(year, mon, int(dm.group(2))), "time": hm(tm.group(1))}
        p = re.fullmatch(r"Personal Income and Outlays, (.+)", title)
        if p:
            mm = re.findall(r"([A-Z][a-z]+)(?: and [A-Z][a-z]+)? (\d{4})", p.group(1))
            ref = ""
            if mm:
                months = re.findall(r"[A-Z][a-z]+", p.group(1))
                ref = f"{mm[-1][1]}-{month_no(months[-1]):02d}"
            ev.append({**base, "kind": "pce", "ref": ref}); continue
        g = re.match(r"(?:GDP|Gross Domestic Product)\b(?! by (?:State|County|Industry))", title)
        if g and "by State" not in title[:40] and "by County" not in title[:40]:
            q = re.search(r"(\d)(?:st|nd|rd|th) Quarter(?: and Year)? (\d{4})", title)
            est = "adv" if "Advance" in title else "2nd" if "Second" in title else "3rd" if "Third" in title else "upd"
            ev.append({**base, "kind": "gdp", "ref": f"{q.group(2)}Q{q.group(1)}" if q else "", "est": est})
    if not any(e["kind"] == "pce" for e in ev): raise ValueError("no Personal Income and Outlays release found")
    return ev

def parse_nyse(page):
    ev = []
    i = page.find("New Year")
    start, end = page.rfind("<table", 0, i), page.find("</table>", i)
    if i < 0 or start < 0 or end < 0: raise ValueError("holiday table not found")
    tbl = page[start:end]
    years = [int(y) for y in re.findall(r"<th[^>]*>\s*(\d{4})\s*</th>", tbl)]
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", tbl, re.S):
        th = re.search(r"<th[^>]*>(.*?)</th>", row, re.S)
        tds = [text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if not th or not tds or len(tds) != len(years): continue
        name = text(th.group(1))
        for y, c in zip(years, tds):
            m = re.search(r"[A-Za-z]+day, ([A-Za-z]+) (\d{1,2})", c)
            if m: ev.append({"date": iso(y, month_no(m.group(1)), int(m.group(2))), "time": None, "kind": "closed", "name": name})
    # footnotes: "Each market will close early at 1:00 p.m. (1:15 p.m. for eligible options) on Friday, November 27, 2026, ..."
    for m in re.finditer(r"close early at (\d{1,2}):(\d{2}) ?([ap])\.m\.(.{0,400}?)(?=\*|NYSE American|All times|$)", text(page)):
        t = f"{int(m.group(1)) % 12 + (12 if m.group(3) == 'p' else 0):02d}:{m.group(2)}"
        for mon, d, y in re.findall(r"[A-Za-z]+day, ([A-Za-z]+) (\d{1,2}), (\d{4})", m.group(4)):
            ev.append({"date": iso(int(y), month_no(mon), int(d)), "time": t, "kind": "early"})
    ev = list({(e["date"], e["kind"]): e for e in ev}.values())
    if sum(e["kind"] == "closed" for e in ev) < 9: raise ValueError("too few holidays found")
    return ev

PARSERS = {"fomc": parse_fomc, "cpi": lambda p: parse_bls(p, "cpi"), "jobs": lambda p: parse_bls(p, "jobs"),
           "ppi": lambda p: parse_bls(p, "ppi"), "bea": parse_bea, "nyse": parse_nyse}

# ------------------------------------------------------------------ main
def get(url, ua):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "text/html", "Accept-Language": "en-US,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ua", default=os.environ.get("SEC_UA", ""))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--offline")
    a = ap.parse_args()
    if not a.offline and not a.ua: sys.exit("--ua is required (a contact, as for SEC)")
    today = dt.date.today()
    old = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {"sources": {}, "events": []}
    events = {s: [e for e in old["events"] if e.get("src") == s] for s in URLS}
    sources, problems, changed = json.loads(json.dumps(old.get("sources", {}))), [], False  # deep copy: compared with old below
    cut = (today - dt.timedelta(days=KEEP_PAST_DAYS)).isoformat()
    for s, url in URLS.items():
        last = sources.get(s, {}).get("ok")
        if not a.force and not a.offline and last and (today - dt.date.fromisoformat(last)).days < MAX_AGE_DAYS:
            print(f"{s}: fresh ({last}), skipped"); continue
        try:
            page = open(os.path.join(a.offline, f"{s}.html"), encoding="utf-8").read() if a.offline else get(url, a.ua)
            ev = sorted(({**e, "src": s} for e in PARSERS[s](page) if e["date"] >= cut), key=lambda e: (e["date"], e["time"] or "", e["kind"]))
        except Exception as ex:
            src = sources.setdefault(s, {})
            src["failed"] = today.isoformat()
            rep = src.get("reported")
            if not rep or (today - dt.date.fromisoformat(rep)).days >= REPORT_EVERY_DAYS:  # one issue a week per source, not one per run
                problems.append(f"- **{s}** ({url}): {type(ex).__name__}: {ex}" + (f" (last good read {src['ok']})" if src.get("ok") else " (never read yet)"))
                src["reported"] = today.isoformat()
            print(f"{s}: FAILED {ex}"); continue
        if ev != events[s]: changed = True
        events[s] = ev
        sources[s] = {"ok": today.isoformat(), "url": url, "n": len(ev)}
        print(f"{s}: {len(ev)} events, {ev[0]['date']} .. {ev[-1]['date']}")
    allev = sorted((e for v in events.values() for e in v if e["date"] >= cut), key=lambda e: (e["date"], e["time"] or "", e["kind"]))
    out = {"updated": today.isoformat(), "sources": sources, "events": allev}
    changed = changed or sources != old.get("sources")  # also commit read dates, so the 3-day skip survives between runs
    if changed:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=0); f.write("\n")
    os.makedirs(WORK, exist_ok=True)
    if changed: open(os.path.join(WORK, "macro_changed"), "w").write("1")
    if problems:
        with open(os.path.join(WORK, "macro_problems.md"), "w", encoding="utf-8") as f:
            f.write("These official schedules could not be read; the calendar keeps their previous dates:\n\n" + "\n".join(problems) + "\n")
    print(f"{len(allev)} events kept; changed={changed}; problems={len(problems)}")

if __name__ == "__main__":
    main()
