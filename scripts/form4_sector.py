#!/usr/bin/env python3
"""Daily insider buy/sell by sector from SEC EDGAR Form 4 filings.

Stdlib only. For each EDGAR filing date, reads the daily form index, fetches every
original Form 4 (amendments excluded), keeps open-market purchases (code P) and
sales (code S) from the non-derivative table, maps the issuer's SIC code to one of
11 sectors, and writes one JSON summary per filing date.

Usage:
  python3 form4_sector.py --ua "Name email@example.com" --out DIR [--dates 2026-10-19 ...] [--days 7]
With no --dates, processes every filing date in the last --days calendar days
(up to today) whose JSON is not already in DIR.
"""
import argparse, datetime as dt, json, os, re, sys, threading, time, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

SECTORS = ["Basic Materials", "Communication Services", "Consumer Cyclical", "Consumer Defensive",
           "Energy", "Financial Services", "Healthcare", "Industrials", "Real Estate", "Technology",
           "Utilities", "Unclassified"]

# A single transaction above this, or a per-share price above this, is treated as a
# likely filer data error: kept in "flagged", excluded from totals.
MAX_TX_USD = 1_000_000_000
MAX_PRICE = 10_000
# Filings whose price is clearly a filer typo but cannot be caught by a rule. Key: accession number.
# Trades in them are left out of totals and listed under "flagged" with the reason (shown on the site).
MANUAL_EXCLUDE = {
    "0001214659-26-012438": "UUU: price $5,134/share on an 18,000-share buy is ~1,000x the stock's usual ~$5 price "
                            "(likely $5.134); treated as a filing error",
}
# "prices ranging from $a to $b" in a price footnote: a reported price far outside it is a typo
RANGE_RX = re.compile(r"rang\w*\s+from\s+(?:US)?\$?\s?([\d,]*\.?\d+)\s*(?:to|-|through)\s+(?:US)?\$?\s?([\d,]*\.?\d+)", re.I)
RANGE_X = 5.0


def sic_to_sector(sic):
    """Approximate SIC -> Morningstar-style sector (the same 11 sectors secform4 uses)."""
    if sic is None:
        return "Unclassified"
    s = int(sic)
    def r(a, b): return a <= s <= b
    if s == 0 or s >= 9900: return "Unclassified"
    if r(100, 299): return "Consumer Defensive"
    if r(700, 999): return "Basic Materials"
    if r(1000, 1099) or r(1400, 1499): return "Basic Materials"
    if r(1200, 1399): return "Energy"
    if s == 1531: return "Consumer Cyclical"
    if r(1500, 1799): return "Industrials"
    if r(2000, 2199): return "Consumer Defensive"
    if r(2200, 2399): return "Consumer Cyclical"
    if r(2400, 2499) or r(2600, 2699): return "Basic Materials"
    if r(2500, 2599): return "Consumer Cyclical"
    if r(2700, 2799): return "Communication Services"
    if r(2833, 2836): return "Healthcare"
    if r(2840, 2844): return "Consumer Defensive"
    if r(2800, 2899): return "Basic Materials"
    if r(2900, 2999): return "Energy"
    if r(3000, 3099) or r(3200, 3399): return "Basic Materials"
    if r(3100, 3199): return "Consumer Cyclical"
    if r(3400, 3499): return "Industrials"
    if r(3570, 3579): return "Technology"
    if r(3500, 3599): return "Industrials"
    if r(3630, 3639) or r(3650, 3652): return "Consumer Cyclical"
    if r(3600, 3699): return "Technology"
    if s in (3711, 3713, 3714, 3716, 3751) or r(3790, 3799): return "Consumer Cyclical"
    if r(3700, 3799): return "Industrials"
    if s == 3812: return "Industrials"
    if r(3840, 3851): return "Healthcare"
    if r(3800, 3899): return "Technology"
    if r(3900, 3999): return "Consumer Cyclical"
    if r(4000, 4799): return "Industrials"
    if r(4800, 4899): return "Communication Services"
    if s in (4922, 4923): return "Energy"
    if r(4950, 4959): return "Industrials"
    if r(4900, 4999): return "Utilities"
    if s == 5045: return "Technology"
    if s == 5122: return "Healthcare"
    if r(5140, 5149) or r(5180, 5182): return "Consumer Defensive"
    if r(5171, 5172): return "Energy"
    if r(5000, 5199): return "Industrials"
    if r(5400, 5499) or s in (5331, 5399, 5912): return "Consumer Defensive"
    if r(5200, 5999): return "Consumer Cyclical"
    if r(6500, 6599) or s == 6798: return "Real Estate"
    if r(6000, 6799): return "Financial Services"
    if r(7000, 7099) or r(7200, 7299) or r(7500, 7599) or r(7900, 7999): return "Consumer Cyclical"
    if r(7310, 7319) or r(7800, 7899): return "Communication Services"
    if r(7370, 7379): return "Technology"
    if r(7300, 7399): return "Industrials"
    if r(8000, 8099) or s == 8731: return "Healthcare"
    if r(8200, 8299): return "Consumer Defensive"
    return "Industrials"


class Fetcher:
    def __init__(self, ua, rate=8.0):
        self.ua, self.gap, self.lock, self.next_t = ua, 1.0 / rate, threading.Lock(), 0.0

    def get(self, url, tries=4, on404=None):
        for i in range(tries):
            with self.lock:
                now = time.monotonic()
                wait = self.next_t - now
                self.next_t = max(now, self.next_t) + self.gap
            if wait > 0:
                time.sleep(wait)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": self.ua, "Accept-Encoding": "identity"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return resp.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return on404
                time.sleep(2 * (i + 1))
            except Exception:
                time.sleep(2 * (i + 1))
        return None


def daily_index(f, d):
    q = (d.month - 1) // 3 + 1
    url = f"https://www.sec.gov/Archives/edgar/daily-index/{d.year}/QTR{q}/form.{d:%Y%m%d}.idx"
    txt = f.get(url)
    if not txt:
        return None
    paths = []
    for line in txt.splitlines():
        if line.startswith("4 "):
            m = re.search(r"(edgar/data/\S+\.txt)", line)
            if m:
                paths.append(m.group(1))
    # each filing is listed once per filer (issuer + owners): dedupe by accession
    seen, out = set(), []
    for p in paths:
        acc = p.rsplit("/", 1)[1]
        if acc not in seen:
            seen.add(acc); out.append(p)
    return out


# ---- foreign-currency prices ----
# Some issuers (mostly foreign: ASE/TWD, Canadian cross-listings ...) report the per-share price in
# local currency and say so only in a footnote ("New Taiwan Dollars."). Detect that and convert to USD
# with the trade-date rate. Rates: npm package @fawazahmed0/currency-api (one dated version per day,
# units of currency per 1 USD), fetched from registry.npmjs.org and cached on disk.
CCY_RX = [
    ("TWD", r"New Taiwan Dollars?|\bNT\s?\$|\bNTD\b|\bTWD\b"),
    ("HKD", r"Hong Kong Dollars?|\bHK\s?\$|\bHKD\b"),
    ("SGD", r"Singapore Dollars?|\bS\$|\bSGD\b"),
    ("CAD", r"Canadian Dollars?|\bCDN\s?\$|\bC\$|\bCAD\b|\bCDN\b"),
    ("AUD", r"Australian Dollars?|\bA\$|\bAUD\b"),
    ("NZD", r"New Zealand Dollars?|\bNZ\$|\bNZD\b"),
    ("GBX", r"\bpence\b|\bGBX\b|\bGBp\b"),
    ("GBP", r"Pounds? Sterling|British Pounds?|£|\bGBP\b"),
    ("EUR", r"\bEuros?\b|€|\bEUR\b"),
    ("JPY", r"Japanese Yen|\bYen\b|¥|\bJPY\b"),
    ("CHF", r"Swiss Francs?|\bCHF\b"),
    ("ILS", r"Shekels?|\bNIS\b|\bILS\b"),
    ("KRW", r"Korean Won|\bKRW\b"),
    ("SEK", r"Swedish Kron(a|or)|\bSEK\b"),
    ("NOK", r"Norwegian Kron(e|er)|\bNOK\b"),
    ("DKK", r"Danish Kron(e|er)|\bDKK\b"),
    ("INR", r"Indian Rupees?|\bINR\b"),
    ("BRL", r"Brazilian Rea(l|is)|\bR\$|\bBRL\b"),
    ("MXN", r"Mexican Pesos?|\bMXN\b"),
    ("CNY", r"Renminbi|\bRMB\b|Chinese Yuan|\bCNY\b"),
    ("ZAR", r"South African Rand|\bZAR\b"),
]
CCY_RX = [(c, re.compile(p, re.I)) for c, p in CCY_RX]
USD_RX = re.compile(r"U\.?\s?S\.?\s?(dollars?|\$)|US\s?\$|\bUSD\b|United States (dollars?|currency)", re.I)
# e.g. "translated into U.S. dollars", "converted from ZAR", "$1.3880 U.S. dollars is the equivalent",
# "exchange rate ... 3.072 ILS to $1.00", "DKK 229.00 per share (approximately $36.35 per share)"
USD_STATED = re.compile(r"(translat|conver)\w*\s+(in)?to\s+(the\s+)?(U\.?\s?S|US|United States)|(translat|conver)\w*\s+from"
                        r"|equivalent|exchange rate|conversion rate|approximately\s+(US\s?)?\$|\bto\s+(US\s?)?\$\s?1(\.0+)?\b"
                        r"|per\s+(US\s?)?\$\s?1(\.0+)?\b|U\.?\s?S\.?\s?dollar amount", re.I)
NUM_RX = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")


def detect_ccy(text, px):
    """Currency the XML price `px` is stated in, judged from the footnotes attached to the price.
    None = USD. Seen in practice:
      'New Taiwan Dollars.' / 'Australian dollars'               -> local currency (convert)
      'translated from NT$2,462 ... at NT$32.143 to US$1'          -> already USD
      'represents a per ordinary share price of MXN$59.75' (px 3.42) -> already USD (local price differs)
    """
    if not text or not text.strip():
        return None
    found = [c for c, rx in CCY_RX if rx.search(text)]
    if "GBX" in found and "GBP" in found:
        found.remove("GBP")            # "pence (GBP 0.01)" -> pence
    if not found:
        return None
    if USD_STATED.search(text):
        return None                    # footnote says the reported price is the USD translation
    nums = []
    for m in NUM_RX.finditer(text):
        try:
            nums.append((float(m.group(0).replace(",", "")), m.start()))
        except ValueError:
            pass
    usd = bool(USD_RX.search(text))
    hit = [pos for v, pos in nums if px and abs(v - px) <= max(0.005 * px, 1e-6)]
    if hit:
        # the footnote restates the reported price: which currency labels it?
        pre = text[max(0, hit[0] - 25):hit[0]]
        if USD_RX.search(pre):
            return None
        lab = [c for c, rx in CCY_RX if rx.search(pre)]
        if lab:
            return lab[-1] if lab[-1] != "GBP" or "GBX" not in found else "GBX"
        return None if usd else (found[0] if len(found) == 1 else "MIXED")
    if usd or nums:
        return None                    # converted to USD, or the footnote quotes a different local price
    return found[0] if len(found) == 1 else "MIXED"


class FX:
    """Trade-date FX: USD per 1 unit of currency."""
    def __init__(self, cache_dir=None):
        self.dir = cache_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), "fx_cache")
        self.mem, self.lock = {}, threading.Lock()

    def _day(self, d):
        if d in self.mem:
            return self.mem[d]
        os.makedirs(self.dir, exist_ok=True)
        p = os.path.join(self.dir, f"usd-{d.isoformat()}.json")
        rates = None
        if os.path.exists(p):
            rates = json.load(open(p))
        else:
            import io, tarfile
            url = (f"https://registry.npmjs.org/@fawazahmed0/currency-api/-/"
                   f"currency-api-{d.year}.{d.month}.{d.day}.tgz")
            for i in range(3):
                try:
                    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "fx"}), timeout=60) as r:
                        tz = tarfile.open(fileobj=io.BytesIO(r.read()), mode="r:gz")
                    j = json.load(tz.extractfile("package/v1/currencies/usd.min.json"))
                    rates = {k.upper(): v for k, v in j["usd"].items()}
                    json.dump(rates, open(p, "w"))
                    break
                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        break
                    time.sleep(3 * (i + 1))
                except Exception:
                    time.sleep(3 * (i + 1))
        self.mem[d] = rates
        return rates

    def usd_per(self, ccy, date_str):
        """USD per 1 unit of ccy on date (falls back up to 7 days earlier). None if unknown."""
        if ccy is None:
            return 1.0
        base, div = ("GBP", 100.0) if ccy == "GBX" else (ccy, 1.0)
        try:
            d = dt.date.fromisoformat(date_str[:10])
        except (TypeError, ValueError):
            return None
        d = min(d, dt.date.today())
        with self.lock:
            for k in range(8):
                r = self._day(d - dt.timedelta(days=k))
                if r and r.get(base):
                    return 1.0 / (r[base] * div)
        return None


FXRATES = FX()


def _t(el, path):
    x = el.find(path)
    return x.text.strip() if x is not None and x.text else None


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---- transaction classification (footnote / filing based) ----
RX = {
    "plan": re.compile(r"10b5-1", re.I),
    "offering": re.compile(r"initial public offering|\bIPO\b|underwritten|public offering|private placement|"
                           r"registered direct|subscription agreement|concurrent (private )?placement|offering price|"
                           r"purchase agreement|per unit|units? (each )?consist|unit purchase", re.I),
    "drip": re.compile(r"dividend reinvestment|\bDRIP\b|employee stock purchase|\bESPP\b|401\(k\)|"
                       r"deferred compensation|automatic(ally)? (re)?invest", re.I),
    # only checked on footnotes attached to the trade itself (not the holdings column, where
    # "includes shares acquired through reinvested dividends" describes the total, not this buy)
    "drip_tx": re.compile(r"reinvest\w*\s+(of\s+)?(the\s+)?(cash\s+)?dividends?|dividends?\s+(were\s+|are\s+)?reinvested", re.I),
    "tax": re.compile(r"cover (the )?(applicable )?tax|tax withholding|withholding (tax )?obligation|sell[- ]to[- ]cover|"
                      r"satisfy (the )?(applicable )?(tax|withholding)|tax liabilit", re.I),
    "exercise": re.compile(r"exercise of (vested )?(stock )?options?|options? exercise|same[- ]day (exercise|sale)|"
                           r"cashless exercise", re.I),
    "ipo_any": re.compile(r"initial public offering|\bIPO\b", re.I),
}
# Securities that are not common equity (preferred stock or units, notes, warrants...): a trade in them
# says little about how an insider values the common stock, so it stays out of "effective" totals.
NONEQUITY_RX = re.compile(r"preferred|\bpref\b|debenture|\bnotes?\b|\bbonds?\b|warrants?|\brights?\b|"
                          r"subordinated|senior secured", re.I)
# Indirect holdings through a company (a sponsor, holding company or fund vehicle) rather than a
# person, trust or retirement account: shown as a label, still counted.
ENTITY_RX = re.compile(r"\b(AS|ASA|AB|LLC|L\.L\.C\.?|LP|L\.P\.?|LLP|Inc\.?|Incorporated|Corp\.?|Corporation|Ltd\.?|"
                       r"Limited|Holdings?|GmbH|AG|S\.A\.?|B\.V\.?|N\.V\.?|plc|Pte|Partners|Capital|Ventures)\b", re.I)
PERSONAL_RX = re.compile(r"trust|\bIRA\b|spouse|wife|husband|child|son\b|daughter|famil|401\(k\)|custodian|UTMA|UGMA|"
                         r"retirement|pension|estate", re.I)


def security_kind(tx, ticker=""):
    title = (_t(tx, "securityTitle/value") or "").strip()
    if not NONEQUITY_RX.search(title) or re.search(r"common|ordinary", title, re.I):
        return None
    # the listed class itself can be preferred (Brazilian PN shares such as "Preferred shares (ITUB4)")
    if ticker and re.search(r"\b" + re.escape(ticker) + r"\d*\b", title, re.I):
        return None
    return "nonequity"


def via_entity(tx):
    if (_t(tx, "ownershipNature/directOrIndirectOwnership/value") or "") != "I":
        return False
    nat = (_t(tx, "ownershipNature/natureOfOwnership/value") or "").strip()
    return bool(nat) and bool(ENTITY_RX.search(nat)) and not PERSONAL_RX.search(nat)


# Flags that keep a trade out of "effective" purchases / sales
EFF_BUY_EXCL = {"plan", "offering", "spac", "drip", "fund", "nontraded", "nonequity"}
EFF_SELL_EXCL = {"plan", "exercise", "tax", "spac", "drip", "fund", "nontraded", "nonequity"}
FLAG_ORDER = ["plan", "exercise", "tax", "offering", "spac", "drip", "fund", "nontraded", "nonequity", "affiliate",
              "late", "fx", "fx_unknown", "ccy_note", "price_error"]


def holdings(root):
    """Holdings before/after the filing's open-market purchases, for the security classes bought.

    Each ownership line (security title + direct/indirect + nature of ownership) is followed through
    its transactions in order: pre = holding before the line's first transaction, post = holding after
    its last one. Lines reported only in the holdings table (no transaction) count as unchanged.
    Returns {"pre": shares, "post": shares, "bought": P shares} or None (no P, or data inconsistent).
    """
    def key(el):
        return ((_t(el, "securityTitle/value") or "").strip().lower(),
                _t(el, "ownershipNature/directOrIndirectOwnership/value") or "",
                (_t(el, "ownershipNature/natureOfOwnership/value") or "").strip().lower())
    lines, bought, titles = {}, 0.0, set()
    for tx in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        k = key(tx)
        sh = _f(_t(tx, "transactionAmounts/transactionShares/value")) or 0.0
        ad = _t(tx, "transactionAmounts/transactionAcquiredDisposedCode/value")
        post = _f(_t(tx, "postTransactionAmounts/sharesOwnedFollowingTransaction/value"))
        if _t(tx, "transactionCoding/transactionCode") == "P" and sh:
            bought += sh; titles.add(k[0])
        if post is None:
            return None
        if k not in lines:
            lines[k] = [post - (sh if ad == "A" else -sh), post]
        else:
            lines[k][1] = post
    if not bought:
        return None
    for h in root.findall("nonDerivativeTable/nonDerivativeHolding"):
        k = key(h)
        post = _f(_t(h, "postTransactionAmounts/sharesOwnedFollowingTransaction/value"))
        if post is not None and k not in lines:
            lines[k] = [post, post]
    rel = [v for k, v in lines.items() if k[0] in titles]
    pre, post = sum(v[0] for v in rel), sum(v[1] for v in rel)
    if pre < -0.5 or post <= 0:
        return None
    return {"pre": max(0.0, pre), "post": post, "bought": bought}


def parse_filing(txt, filed=None):
    m = re.search(r"ISSUER:.*?STANDARD INDUSTRIAL CLASSIFICATION:[^\[]*\[(\d+)\]", txt, re.S)
    sic = m.group(1) if m else None
    m = re.search(r"<XML>\s*(.*?)\s*</XML>", txt, re.S)
    if not m:
        return None
    try:
        root = ET.fromstring(m.group(1).strip())
    except ET.ParseError:
        return None
    if _t(root, "documentType") != "4":
        return None
    plan = _t(root, "aff10b5One") in ("1", "true")
    roles = set()
    names = []
    for ro in root.findall("reportingOwner"):
        names.append(_t(ro, "reportingOwnerId/rptOwnerName") or "")
        rel = ro.find("reportingOwnerRelationship")
        if rel is None:
            continue
        if _t(rel, "isOfficer") in ("1", "true"):
            roles.add(_t(rel, "officerTitle") or "Officer")
        if _t(rel, "isDirector") in ("1", "true"):
            roles.add("Director")
        if _t(rel, "isTenPercentOwner") in ("1", "true"):
            roles.add("10% Owner")
        if _t(rel, "isOther") in ("1", "true"):
            roles.add("Other")
    notes = {n.get("id"): " ".join(n.itertext()) for n in root.iter("footnote")}
    remarks = _t(root, "remarks") or ""
    all_text = " ".join(notes.values()) + " " + remarks
    # dates with option exercises (M/X) and conversions (C) anywhere in the filing
    ex_dates, conv_dates, deriv_buy_dates = set(), set(), set()
    for t in root.findall(".//nonDerivativeTransaction") + root.findall(".//derivativeTransaction"):
        c = _t(t, "transactionCoding/transactionCode")
        dte = (_t(t, "transactionDate/value") or "")[:10]
        if c in ("M", "X"):
            ex_dates.add(dte)
        if c == "C":
            conv_dates.add(dte)
    # derivative securities bought together with the shares (units: free warrants, or the same
    # package price) mark the share purchase as an offering / private placement, not open market
    for t in root.findall(".//derivativeTransaction"):
        if _t(t, "transactionCoding/transactionCode") == "P":
            dpx = _f(_t(t, "transactionAmounts/transactionPricePerShare/value"))
            deriv_buy_dates.add(((_t(t, "transactionDate/value") or "")[:10], None if not dpx else round(dpx, 4)))
    ticker = (_t(root, "issuer/issuerTradingSymbol") or "").upper()
    if ticker in ("NONE", "N/A", "NA", "-", "N.A."):
        ticker = ""
    base = set()
    if sic == "6770":
        base.add("spac")
    if sic is None:
        base.add("fund")          # no SIC code: funds, trusts, interval/BDC vehicles
    if not ticker:
        base.add("nontraded")
    txs = []
    for tx in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code = _t(tx, "transactionCoding/transactionCode")
        if code not in ("P", "S"):
            continue
        sh = _f(_t(tx, "transactionAmounts/transactionShares/value"))
        px = _f(_t(tx, "transactionAmounts/transactionPricePerShare/value"))
        if not sh or px is None:
            continue
        dte = (_t(tx, "transactionDate/value") or "")[:10]
        ft = " ".join(notes.get(e.get("id"), "") for e in tx.iter("footnoteId")) + " " + remarks
        fl = set(base)
        price_note = None
        pe = tx.find("transactionAmounts/transactionPricePerShare")
        ptxt = " ".join(notes.get(e.get("id"), "") for e in pe.iter("footnoteId")) if pe is not None else ""
        ccy = detect_ccy(ptxt, px)
        if not ccy and ptxt.strip() and any(rx.search(ptxt) for _, rx in CCY_RX) \
                and not USD_RX.search(ptxt) and not USD_STATED.search(ptxt):
            fl.add("ccy_note")          # foreign currency named, judged USD anyway: anomaly.py asks a human
        rg = RANGE_RX.search(ptxt) if ptxt else None
        if rg and not any(rx.search(ptxt) for _, rx in CCY_RX):
            try:
                lo, hi = sorted(float(g.replace(",", "")) for g in rg.groups())
                if lo > 0 and (px > hi * RANGE_X or px < lo / RANGE_X):
                    fl.add("price_error")
                    price_note = f"reported price ${px:,.4g} is outside the footnote's range ${lo:,.4g}-${hi:,.4g}"
            except ValueError:
                pass
        px_local, fxr = px, 1.0
        if ccy:
            fl.add("fx")
            fxr = None if ccy == "MIXED" else FXRATES.usd_per(ccy, dte or filed)
            if fxr is None:
                fl.add("fx_unknown")       # currency named but no rate: kept out of totals (see summarize)
                fxr = 0.0
            px = px_local * fxr
        if plan or RX["plan"].search(ft):
            fl.add("plan")
        if security_kind(tx, ticker):
            fl.add("nonequity")
        if via_entity(tx):
            fl.add("affiliate")
        if code == "P":
            if (RX["offering"].search(ft) or (dte in conv_dates and RX["ipo_any"].search(all_text))
                    or (dte, None) in deriv_buy_dates or (dte, round(px, 4)) in deriv_buy_dates):
                fl.add("offering")
            if RX["drip"].search(ft):
                fl.add("drip")
            else:
                ids = {e.get("id") for part in ("securityTitle", "transactionDate", "transactionCoding", "transactionAmounts")
                       for el in tx.findall(part) for e in el.iter("footnoteId")}
                if RX["drip_tx"].search(" ".join(notes.get(i, "") for i in ids)):
                    fl.add("drip")
        else:
            if dte in ex_dates or RX["exercise"].search(ft):
                fl.add("exercise")
            if RX["tax"].search(ft):
                fl.add("tax")
        if filed and dte:
            try:
                if (dt.date.fromisoformat(filed) - dt.date.fromisoformat(dte)).days > 30:
                    fl.add("late")
            except ValueError:
                pass
        t = {"code": code, "shares": sh, "price": px, "usd": sh * px, "date": dte,
             "flags": sorted(fl, key=FLAG_ORDER.index)}
        if "price_error" in fl:
            t["error"] = price_note
        if ccy:
            t.update({"ccy": ccy, "price_local": px_local, "usd_per_unit": fxr})
        txs.append(t)
    # same filing, same typo on a line without the footnote (e.g. APCX: 2,895 footnoted, 2,900 not)
    bad_px = [t["price"] for t in txs if "price_error" in t["flags"]]
    for t in txs:
        if "price_error" not in t["flags"] and any(abs(t["price"] / b - 1) < 0.10 for b in bad_px if b):
            t["flags"] = sorted(set(t["flags"]) | {"price_error"}, key=FLAG_ORDER.index)
            t["error"] = next(x["error"] for x in txs if "price_error" in x["flags"] and x.get("error"))
    return {
        "cik": _t(root, "issuer/issuerCik"),
        "ticker": ticker,
        "name": _t(root, "issuer/issuerName") or "",
        "sic": sic, "sector": sic_to_sector(sic),
        "owners": names, "roles": sorted(r for r in roles if r), "plan": plan, "txs": txs,
        "hold": holdings(root),
    }


def summarize(d, filings, n_total):
    sec = {s: {"buy_usd": 0.0, "sell_usd": 0.0, "sell_plan_usd": 0.0, "buy_plan_usd": 0.0, "buy_filings": 0,
               "sell_filings": 0, "buy_cos": set(), "sell_cos": set(),
               "buy_od_usd": 0.0, "sell_od_usd": 0.0, "buy_od_filings": 0, "sell_od_filings": 0,
               "buy_eff_usd": 0.0, "buy_eff_filings": 0,
               "sell_eff_usd": 0.0, "sell_eff_filings": 0} for s in SECTORS}
    cos, flagged = {}, []
    excluded = {}            # flag -> usd removed from "effective" (od trades only)
    dups = {"count": 0, "usd": 0.0, "examples": []}
    # cross-filing de-duplication: the same transaction reported by several related filers
    # (fund + GP + director ...). Officer/director filings win so attribution is kept.
    order = sorted(range(len(filings)), key=lambda i: (
        0 if filings[i][1] and any(r not in ("10% Owner", "Other") for r in filings[i][1]["roles"]) else 1, filings[i][0]))
    seen = {}
    dup_mark = set()
    for i in order:
        url, fl = filings[i]
        if not fl:
            continue
        for j, t in enumerate(fl["txs"]):
            key = (fl["cik"], t["code"], t["date"], round(t["shares"], 4), round(t["price"], 4))
            if key in seen and seen[key] != url:
                dup_mark.add((url, j))
            else:
                seen.setdefault(key, url)
    for url, fl in filings:
        if not fl or not fl["txs"]:
            continue
        od = any(r not in ("10% Owner", "Other") for r in fl["roles"])
        b = s_ = bsh = ssh = eb = es = bplan = splan = 0.0
        rm = {"P": 0.0, "S": 0.0}     # usd removed from this filing (duplicates / outliers)
        tdates, fflags, fxl = [], set(), []
        for j, t in enumerate(fl["txs"]):
            if (url, j) in dup_mark:
                dups["count"] += 1; dups["usd"] += t["usd"]; rm[t["code"]] += t["usd"]
                if len(dups["examples"]) < 20:
                    dups["examples"].append({"ticker": fl["ticker"], "code": t["code"], "usd": round(t["usd"]),
                                             "url": "https://www.sec.gov/Archives/" + url})
                continue
            if t.get("ccy"):
                fxl.append({"code": t["code"], "date": t["date"], "ccy": t["ccy"], "shares": t["shares"],
                            "price_local": t["price_local"], "usd_per_unit": t["usd_per_unit"]})
            if "fx_unknown" in t["flags"]:
                flagged.append({"ticker": fl["ticker"], "name": fl["name"], "code": t["code"],
                                "shares": t["shares"], "price": t["price_local"], "ccy": t["ccy"],
                                "usd": None, "reason": "price in foreign currency, no FX rate",
                                "url": "https://www.sec.gov/Archives/" + url})
                continue
            why = MANUAL_EXCLUDE.get(url.rsplit("/", 1)[-1].replace(".txt", "")) or t.get("error")
            if why or t["usd"] > MAX_TX_USD or t["price"] > MAX_PRICE:
                flagged.append({"ticker": fl["ticker"], "name": fl["name"], "code": t["code"],
                                "shares": t["shares"], "price": t["price"], "usd": round(t["usd"]),
                                **({"reason": why} if why else {}),
                                "url": "https://www.sec.gov/Archives/" + url})
                rm[t["code"]] += t["usd"]
                continue
            tf = set(t["flags"]); fflags |= tf
            if t["code"] == "P":
                b += t["usd"]; bsh += t["shares"]
                if "plan" in tf: bplan += t["usd"]
                if od:
                    bad = tf & EFF_BUY_EXCL
                    if bad:
                        for k in bad: excluded[("P", k)] = excluded.get(("P", k), 0) + t["usd"]
                    else:
                        eb += t["usd"]
            else:
                s_ += t["usd"]; ssh += t["shares"]
                if "plan" in tf: splan += t["usd"]
                if od:
                    bad = tf & EFF_SELL_EXCL
                    if bad:
                        for k in bad: excluded[("S", k)] = excluded.get(("S", k), 0) + t["usd"]
                    else:
                        es += t["usd"]
            if t["date"]: tdates.append(t["date"])
        if b == 0 and s_ == 0:
            continue
        S = sec[fl["sector"]]
        if od and b: S["buy_od_usd"] += b; S["buy_od_filings"] += 1
        if od and s_: S["sell_od_usd"] += s_; S["sell_od_filings"] += 1
        if eb: S["buy_eff_usd"] += eb; S["buy_eff_filings"] += 1
        if es: S["sell_eff_usd"] += es; S["sell_eff_filings"] += 1
        S["sell_plan_usd"] += splan; S["buy_plan_usd"] += bplan
        key = fl["cik"] or fl["ticker"]
        c = cos.setdefault(key, {"cik": fl["cik"], "ticker": fl["ticker"], "name": fl["name"], "sector": fl["sector"],
                                 "buy_usd": 0.0, "sell_usd": 0.0, "buy_filings": 0, "sell_filings": 0,
                                 "eff_buy_usd": 0.0, "eff_sell_usd": 0.0, "eff_buy_filings": 0, "eff_sell_filings": 0,
                                 "buyers": set(), "sellers": set(), "od_buy": False, "filings": []})
        who = [nm + (f" ({', '.join(fl['roles'])})" if fl["roles"] else "") for nm in fl["owners"]]
        c["filings"].append({"path": url, "who": "; ".join(who)[:160],
                             "tx_date": min(tdates) if tdates else None,
                             "buy": round(b), "buy_sh": round(bsh), "sell": round(s_), "sell_sh": round(ssh),
                             "eff_buy": round(eb), "eff_sell": round(es),
                             "od": od, "plan": bool(fl["plan"]) or bool(bplan or splan),
                             "flags": sorted(fflags, key=FLAG_ORDER.index),
                             **({"fx": fxl} if fxl else {}),
                             **({"hold_pre": round(fl["hold"]["pre"]), "hold_post": round(fl["hold"]["post"])}
                                if b and fl.get("hold") else {}),
                             **({"removed_buy": round(rm["P"])} if rm["P"] else {}),
                             **({"removed_sell": round(rm["S"])} if rm["S"] else {})})
        if b:
            S["buy_usd"] += b; S["buy_filings"] += 1; S["buy_cos"].add(key)
            c["buy_usd"] += b; c["buy_filings"] += 1
            c["od_buy"] = c["od_buy"] or od
        if s_:
            S["sell_usd"] += s_; S["sell_filings"] += 1; S["sell_cos"].add(key)
            c["sell_usd"] += s_; c["sell_filings"] += 1
        if eb: c["eff_buy_usd"] += eb; c["eff_buy_filings"] += 1; c["buyers"].update(who)
        if es: c["eff_sell_usd"] += es; c["eff_sell_filings"] += 1; c["sellers"].update(who)
    sectors = []
    for name, S in sec.items():
        row = {"sector": name}
        for k, v in S.items():
            row[k.replace("_cos", "_companies")] = len(v) if isinstance(v, set) else (round(v) if isinstance(v, float) else v)
        sectors.append(row)
    keep = []
    for c in cos.values():
        for k in ("buy_usd", "sell_usd", "eff_buy_usd", "eff_sell_usd"):
            c[k] = round(c[k])
        c["buyers"] = sorted(c["buyers"])[:4]
        c["sellers"] = sorted(c["sellers"])[:4]
        if c["buy_usd"] or c["sell_usd"]:
            keep.append(c)
    return {"date": d.isoformat(), "form4_filings": n_total, "schema": 2,
            "ps_filings": sum(1 for _, fl in filings if fl and fl["txs"]),
            "sectors": sectors, "companies": keep, "flagged": flagged,
            "duplicates": {"count": dups["count"], "usd": round(dups["usd"]), "examples": dups["examples"]},
            "excluded_eff": {f"{k[0]}:{k[1]}": round(v) for k, v in sorted(excluded.items())},
            "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


# ---- Form 144: notices of proposed sales (a heads-up before the Form 4) ----
_TICKERS = {}
def ticker_map(f):
    """CIK -> ticker from SEC's company_tickers.json (Form 144 has no ticker)."""
    if not _TICKERS:
        txt = f.get("https://www.sec.gov/files/company_tickers.json")
        if txt:
            for v in json.loads(txt).values():
                _TICKERS.setdefault(int(v["cik_str"]), v["ticker"])
    return _TICKERS

def index_paths(f, d, form):
    q = (d.month - 1) // 3 + 1
    txt = f.get(f"https://www.sec.gov/Archives/edgar/daily-index/{d.year}/QTR{q}/form.{d:%Y%m%d}.idx")
    if not txt:
        return None
    seen, out = set(), []
    for line in txt.splitlines():
        if line.startswith(form + " "):
            m = re.search(r"(edgar/data/\S+\.txt)", line)
            if m and m.group(1).rsplit("/", 1)[1] not in seen:
                seen.add(m.group(1).rsplit("/", 1)[1]); out.append(m.group(1))
    return out

def parse_144(txt, tmap):
    m = re.search(r"<XML>\s*(.*?)\s*</XML>", txt, re.S)
    if not m:
        return None
    try:
        root = ET.fromstring(m.group(1).strip())
    except ET.ParseError:
        return None
    for el in root.iter():                       # drop namespaces
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    if (_t(root, "headerData/submissionType") or "") != "144":
        return None
    fd = root.find("formData")
    if fd is None:
        return None
    sic = re.search(r"SUBJECT COMPANY:.*?STANDARD INDUSTRIAL CLASSIFICATION:[^\[]*\[(\d+)\]", txt, re.S)
    sic = sic.group(1) if sic else None
    own = re.search(r"REPORTING-OWNER:.*?COMPANY CONFORMED NAME:[ \t]*([^\r\n]+)", txt, re.S)
    cik = _t(fd, "issuerInfo/issuerCik")
    rel = [x.text.strip() for x in fd.iter("relationshipToIssuer") if x.text]
    sh = usd = 0.0; date = None; titles = set()
    for si in fd.findall("securitiesInformation"):
        sh += _f(_t(si, "noOfUnitsSold")) or 0
        usd += _f(_t(si, "aggregateMarketValue")) or 0
        date = date or _t(si, "approxSaleDate")
        if _t(si, "securitiesClassTitle"): titles.add(_t(si, "securitiesClassTitle"))
    if not sh:
        return None
    nat = [x.text.strip() for x in fd.iter("natureOfAcquisitionTransaction") if x.text]
    plan = [x.text.strip() for x in fd.iter("planAdoptionDate") if x.text]
    def iso(s):
        try:
            mo, dd, yy = s.split("/"); return f"{yy}-{int(mo):02d}-{int(dd):02d}"
        except Exception:
            return None
    try:
        tk = tmap.get(int(cik)) if cik else None
    except ValueError:
        tk = None
    return {"cik": cik, "ticker": tk or "", "name": _t(fd, "issuerInfo/issuerName") or "", "sic": sic,
            "sector": sic_to_sector(sic),
            "person": (own.group(1).strip() if own else _t(fd, "issuerInfo/nameOfPersonForWhoseAccountTheSecuritiesAreToBeSold") or ""),
            "rel": rel, "class": sorted(titles)[0] if titles else "", "shares": round(sh), "usd": round(usd),
            "sale_date": iso(date) if date else None, "nature": nat[0] if nat else "",
            "plan": iso(plan[0]) if plan else None}

def run_144(f, d, workers=8):
    paths = index_paths(f, d, "144")
    if paths is None:
        return None, 0
    tmap = ticker_map(f)
    def one(p):
        txt = f.get("https://www.sec.gov/Archives/" + p, tries=6, on404="")
        if txt is None:
            return p, "fetch"
        if not txt:
            return p, None  # removed from EDGAR (404)
        r = parse_144(txt, tmap)
        return p, r
    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(one, paths))
    out, missing = [], 0
    for p, r in res:
        if r == "fetch":
            missing += 1
        elif r:
            r["path"] = p; out.append(r)
    out.sort(key=lambda x: -x["usd"])
    return out, missing


def run_day(f, d, workers=8):
    paths = daily_index(f, d)
    if paths is None:
        return None
    def one(p):
        txt = f.get("https://www.sec.gov/Archives/" + p)
        return p, (parse_filing(txt, d.isoformat()) if txt else None)
    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(one, paths))
    # retry filings that could not be fetched (SEC throttling / transient errors)
    for attempt in range(3):
        bad = [i for i, (p, x) in enumerate(res) if x is None]
        if not bad:
            break
        time.sleep(10 * (attempt + 1))
        for i in bad:
            p = res[i][0]
            txt = f.get("https://www.sec.gov/Archives/" + p, tries=6)
            if txt:
                fl = parse_filing(txt, d.isoformat())
                # a fetched document that is not an original Form 4 is legitimately skipped
                res[i] = (p, fl if fl is not None else {"txs": [], "roles": [], "skip": True})
    missing = sum(1 for _, x in res if x is None)
    res = [(p, (None if (x and x.get("skip")) else x)) for p, x in res]
    out = summarize(d, res, len(paths))
    out["unparsed_filings"] = missing
    f144, miss144 = run_144(f, d, workers)
    if f144 is not None:
        out["f144"] = f144; out["f144_unfetched"] = miss144
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ua", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dates", nargs="*")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    f = Fetcher(a.ua)
    if a.dates:
        dates = [dt.date.fromisoformat(x) for x in a.dates]
    else:
        today = dt.date.today()
        dates = [today - dt.timedelta(days=i) for i in range(a.days - 1, -1, -1)]
    for d in dates:
        if d.weekday() >= 5:
            continue
        path = os.path.join(a.out, f"{d.isoformat()}.json")
        if os.path.exists(path) and not a.force:
            print(d, "exists, skip"); continue
        t0 = time.time()
        res = run_day(f, d)
        if res is None:
            print(d, "no index (holiday or not yet published)"); continue
        with open(path, "w") as fh:
            json.dump(res, fh)
        print(d, f"{res['form4_filings']} Form 4s, {res['ps_filings']} with P/S, "
                 f"{res['unparsed_filings']} unparsed, {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
