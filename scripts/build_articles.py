"""Build the Articles section (/articles/) of April's Stock Atlas.

Sources live in articles/src/<slug>.<lang>.md (lang = zh, tw, en), each with a small front matter block
(slug, date, title, subtitle, summary). articles/src/<slug>.sources.md is the article's reference list,
appended at its end. A paragraph that is exactly [[diagram]] is replaced by the article's inline SVG
(DIAGRAMS below), drawn in the page's own colours so it follows light and dark mode.

Each article becomes ONE page holding all three languages; the reader's language (sif-lang, the same
key the rest of the site uses) decides which one shows. Without JavaScript the Simplified Chinese
version shows. Standard library only, because the daily workflow runs plain python3 -I.

The articles are listed on the Market watch page (/market/, built here too): a macro dashboard and a
sector-rotation table drawn in the browser from /earnings/data/market.json (daily closes fetched by the
earnings repo's prices workflow), next to the site's own effective insider buying and selling per sector
over the last 30 days (computed here from data/days and embedded in the page). /articles/ redirects there.

    build(out)  -> list of site paths written, e.g. ["market/", "articles/ai-chokepoints/"]
"""
import os, re, html, glob, json

SITE = "https://april-insider-flow.com"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "articles", "src")
LANGS = ("zh", "tw", "en")
LOC = {"zh": "zh-CN", "tw": "zh-TW", "en": "en"}

UI = {
    "zh": {"section": "文章", "intro": "围绕AI产业链的长篇研究笔记。每篇都附资料来源，仅供研究，不构成投资建议。",
           "back": "← 市场观察", "sources": "资料来源", "read": "阅读全文 →", "updated": "数据截至"},
    "tw": {"section": "文章", "intro": "圍繞AI產業鏈的長篇研究筆記。每篇都附資料來源，僅供研究，不構成投資建議。",
           "back": "← 市場觀察", "sources": "資料來源", "read": "閱讀全文 →", "updated": "資料截至"},
    "en": {"section": "Articles", "intro": "Long-form research notes on the AI supply chain. Every piece lists its sources; for research only, not investment advice.",
           "back": "← Market watch", "sources": "Sources", "read": "Read →", "updated": "Data as of"},
}

# ------------------------------------------------------------------ markdown (the subset the sources use)
def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", lambda m: f'<a href="{html.escape(m.group(2))}" rel="noopener" target="_blank">{m.group(1)}</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<em>\1</em>", s)
    return s

def md(text, diagram=""):
    out, lines, i = [], text.split("\n"), 0
    while i < len(lines):
        ln = lines[i]
        if not ln.strip(): i += 1; continue
        if ln.strip() == "[[diagram]]":
            out.append(f'<figure class="dia">{diagram}</figure>'); i += 1; continue
        m = re.match(r"^(#{2,3})\s+(.*)$", ln)
        if m:
            n = len(m.group(1)); out.append(f"<h{n}>{inline(m.group(2))}</h{n}>"); i += 1; continue
        if ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")]); i += 1
            head, body = rows[0], [r for r in rows[1:] if not all(re.fullmatch(r":?-{3,}:?", c) for c in r)]
            t = "<thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
            t += "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body) + "</tbody>"
            out.append(f'<div class="tbl"><table>{t}</table></div>'); continue
        if re.match(r"^(- |\d+\. )", ln):
            tag = "ol" if re.match(r"^\d+\. ", ln) else "ul"; items = []
            while i < len(lines) and re.match(r"^(- |\d+\. )", lines[i]):
                items.append(re.sub(r"^(- |\d+\. )", "", lines[i])); i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>"); continue
        para = []
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{2,3}\s|\||- |\d+\. |\[\[diagram\]\])", lines[i]):
            para.append(lines[i].strip()); i += 1
        out.append(f"<p>{inline(' '.join(para) if all(ord(c) < 0x3000 for c in ''.join(para)) else ''.join(para))}</p>")
    return "\n".join(out)

def read(path):
    raw = open(path, encoding="utf-8").read()
    meta, body = {}, raw
    m = re.match(r"^---\n(.*?)\n---\n", raw, re.S)
    if m:
        for ln in m.group(1).split("\n"):
            if ":" in ln:
                k, v = ln.split(":", 1); meta[k.strip()] = v.strip()
        body = raw[m.end():]
    return meta, body

# ------------------------------------------------------------------ diagrams
# ai-chokepoints: the bottleneck map. Boxes are (stage column, row, tier, name, who) per language.
CHOKE = {
    "title": {"zh": "四个环节没有替代品：EDA、EUV、先进制程与CoWoS、ABF绝缘膜",
              "tw": "四個環節沒有替代品：EDA、EUV、先進製程與CoWoS、ABF絕緣膜",
              "en": "Four links have no substitute: EDA, EUV, leading-edge foundry and CoWoS, ABF film"},
    "sub": {"zh": "按一颗AI芯片从设计到通电的顺序排列，颜色代表绕不开的程度",
            "tw": "按一顆AI晶片從設計到通電的順序排列，顏色代表繞不開的程度",
            "en": "In the order an AI chip goes from design to power-on; colour shows how hard each link is to route around"},
    "stages": {"zh": ["① 设计", "② 制造", "③ 封装", "④ 上线与通电"],
               "tw": ["① 設計", "② 製造", "③ 封裝", "④ 上線與通電"],
               "en": ["1 Design", "2 Manufacturing", "3 Packaging", "4 Deploy and power"]},
    "keys": {"zh": ["第一档：几乎不可替代", "第二档：寡头且正在缺货", "第三档：强势但有替代者"],
             "tw": ["第一檔：幾乎不可替代", "第二檔：寡頭且正在缺貨", "第三檔：強勢但有替代者"],
             "en": ["Tier 1: nearly irreplaceable", "Tier 2: oligopoly in shortage", "Tier 3: strong, substitutes exist"]},
    "boxes": [
        (0, 0, 1, {"zh": "EDA设计软件", "tw": "EDA設計軟體", "en": "EDA software"}, "Synopsys · Cadence"),
        (0, 1, 3, {"zh": "AI加速器", "tw": "AI加速器", "en": "AI accelerators"}, {"zh": "英伟达 · 博通 · Marvell", "tw": "輝達 · 博通 · Marvell", "en": "Nvidia · Broadcom · Marvell"}),
        (1, 0, 1, {"zh": "EUV光刻机", "tw": "EUV曝光機", "en": "EUV lithography"}, {"zh": "ASML（唯一）", "tw": "ASML（唯一）", "en": "ASML (sole)"}),
        (1, 1, 1, {"zh": "3nm以下制程", "tw": "3nm以下製程", "en": "3nm and below"}, {"zh": "台积电", "tw": "台積電", "en": "TSMC"}),
        (1, 2, 2, {"zh": "制程检测", "tw": "製程檢測", "en": "Process control"}, "KLA"),
        (1, 3, 2, {"zh": "HBM内存", "tw": "HBM記憶體", "en": "HBM memory"}, {"zh": "SK海力士 · 三星 · 美光", "tw": "SK海力士 · 三星 · 美光", "en": "SK hynix · Samsung · Micron"}),
        (1, 4, 3, {"zh": "刻蚀与沉积", "tw": "蝕刻與沉積", "en": "Etch and deposition"}, {"zh": "Lam · 应用材料 · 东电", "tw": "Lam · 應用材料 · 東京威力", "en": "Lam · AMAT · TEL"}),
        (2, 0, 1, {"zh": "CoWoS封装", "tw": "CoWoS封裝", "en": "CoWoS packaging"}, {"zh": "台积电", "tw": "台積電", "en": "TSMC"}),
        (2, 1, 1, {"zh": "ABF绝缘膜", "tw": "ABF絕緣膜", "en": "ABF film"}, {"zh": "味之素（约95%）", "tw": "味之素（約95%）", "en": "Ajinomoto (~95%)"}),
        (2, 2, 2, {"zh": "ABF载板", "tw": "ABF載板", "en": "ABF substrates"}, {"zh": "Ibiden · 欣兴 等", "tw": "Ibiden · 欣興 等", "en": "Ibiden · Unimicron etc."}),
        (3, 0, 2, {"zh": "磷化铟激光器", "tw": "磷化銦雷射", "en": "InP lasers"}, "Lumentum · Coherent"),
        (3, 1, 2, {"zh": "燃气轮机", "tw": "燃氣渦輪機", "en": "Gas turbines"}, {"zh": "GE Vernova 等三家", "tw": "GE Vernova 等三家", "en": "GE Vernova + 2 others"}),
        (3, 2, 3, {"zh": "液冷与供电", "tw": "液冷與供電", "en": "Cooling and power"}, {"zh": "Vertiv 等多家", "tw": "Vertiv 等多家", "en": "Vertiv and many others"}),
    ],
}

def choke_svg(l):
    E = lambda s: html.escape(s if isinstance(s, str) else s[l])
    W, H, xs = 166, 48, (24, 206, 388, 570)
    y = lambda r: 108 + 60 * r
    p = [f'<svg viewBox="0 0 760 468" role="img" aria-label="{E(CHOKE["title"])}" class="choke" font-size="13">',
         f'<defs><marker id="ca-{l}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="ax-f"/></marker></defs>',
         f'<text x="24" y="26" font-size="15" font-weight="700" class="ink">{E(CHOKE["title"])}</text>',
         f'<text x="24" y="46" font-size="11.5" class="mut">{E(CHOKE["sub"])}</text>']
    for k, x in enumerate(xs):
        p.append(f'<rect x="{x}" y="56" width="{W}" height="32" rx="8" class="hd"/><text x="{x + W / 2}" y="76" text-anchor="middle" font-weight="700" class="ink">{E(CHOKE["stages"][l][k])}</text>')
        if k < 3: p.append(f'<path d="M{x + W + 2} 72H{xs[k + 1] - 2}" class="ax" marker-end="url(#ca-{l})"/>')
    for c, r, t, name, who in CHOKE["boxes"]:
        x = xs[c]
        p.append(f'<rect x="{x}" y="{y(r)}" width="{W}" height="{H}" rx="8" class="t{t}"/>'
                 f'<text x="{x + 12}" y="{y(r) + 20}" font-weight="700" class="ink">{E(name)}</text>'
                 f'<text x="{x + 12}" y="{y(r) + 38}" font-size="11.5" class="mut">{E(who)}</text>')
    for k, (x, t) in enumerate(((24, 1), (264, 2), (504, 3))):
        p.append(f'<rect x="{x}" y="428" width="14" height="14" rx="3" class="t{t}"/><text x="{x + 22}" y="439" font-size="11.5" class="ink">{E(CHOKE["keys"][l][k])}</text>')
    p.append("</svg>")
    return "".join(p)

DIAGRAMS = {"ai-chokepoints": choke_svg}

# ------------------------------------------------------------------ page shell
CSS = """
:root{--bg:#eef1f5;--surface:#fff;--surface-2:#f5f7fa;--ink:#0e1726;--muted:#5d6879;--faint:#7d8798;--line:#e1e6ed;--accent:#2c49c9;--t2:#d9772b;--hero:#0f1b2d;
--shadow:0 1px 2px rgba(14,23,38,.05),0 6px 20px rgba(14,23,38,.06);
--display:"Bricolage Grotesque","Figtree","PingFang SC","Microsoft YaHei",system-ui,sans-serif;
--body:"Figtree","PingFang SC","Hiragino Sans GB","Microsoft YaHei","Noto Sans SC",system-ui,-apple-system,sans-serif;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--bg:#0b111b;--surface:#131c2a;--surface-2:#1a2535;--ink:#e8edf4;--muted:#9aa6b8;--faint:#7a869a;--line:#243146;--accent:#8ea6ff;--t2:#f0a35e;--hero:#16243a;
--shadow:0 1px 2px rgba(0,0,0,.3),0 8px 24px rgba(0,0,0,.25);color-scheme:dark}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.75 var(--body);-webkit-font-smoothing:antialiased}
button{font:inherit;color:inherit}a{color:var(--accent)}
.wrap{max-width:1040px;margin:0 auto;padding:0 16px}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.top{display:flex;align-items:center;gap:12px;padding-block:14px}
.brand{display:flex;align-items:center;gap:10px;min-width:0;flex:1;color:var(--ink);text-decoration:none}
.logo{width:30px;height:30px;border-radius:9px;background:var(--hero);display:grid;place-items:center;flex:none}
.brand b{font-family:var(--display);font-weight:700;font-size:18px;letter-spacing:-.01em;white-space:nowrap}
.brand b i{font-style:normal;color:var(--accent)}
.lang{display:inline-flex;background:var(--surface);border:1px solid var(--line);border-radius:999px;padding:3px;flex:none}
.lang button{border:0;background:none;padding:5px 10px;border-radius:999px;font-size:13px;color:var(--muted);cursor:pointer}
.lang button[aria-pressed="true"]{background:var(--ink);color:var(--bg)}
@media (max-width:640px){.lang .l2{display:none}}
[data-l]{display:none}
html.l-zh [data-l=zh],html.l-tw [data-l=tw],html.l-en [data-l=en]{display:block}
.paper{background:var(--surface);border:1px solid var(--line);border-radius:20px;box-shadow:var(--shadow);padding:clamp(20px,5vw,56px);margin:8px 0 48px}
.col{max-width:760px;margin:0 auto}
.crumb{font-size:14px;margin:0 0 18px}.crumb a{text-decoration:none}
.meta{color:var(--faint);font-size:13.5px;margin:0 0 6px}
h1{font:700 clamp(28px,4.4vw,42px)/1.15 var(--display);letter-spacing:-.015em;margin:0 0 14px;text-wrap:balance}
html.l-zh h1,html.l-tw h1{word-break:keep-all}
.sub{color:var(--muted);font-size:clamp(16px,1.9vw,18px);margin:0 0 28px;line-height:1.6}
h2{font:700 clamp(22px,2.8vw,27px)/1.25 var(--display);margin:44px 0 14px;padding-top:20px;border-top:1px solid var(--line)}
h3{font-size:19px;line-height:1.35;margin:30px 0 10px}
p{margin:0 0 16px}ul,ol{margin:0 0 18px;padding-left:1.4em}li{margin:0 0 8px}
strong{font-weight:700}
.tbl{overflow-x:auto;margin:0 0 20px;border:1px solid var(--line);border-radius:12px;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;width:100%;font-size:14px;line-height:1.55}
th,td{text-align:left;vertical-align:top;padding:9px 12px;border-bottom:1px solid var(--line)}
th{background:var(--surface-2);font-weight:700;white-space:nowrap}
tr:last-child td{border-bottom:0}
td:first-child{font-weight:600}
.tbl.wide table{min-width:860px}
.dia{margin:6px 0 18px;padding:12px;background:var(--surface-2);border-radius:14px;overflow-x:auto}
.dia svg{display:block;width:100%;min-width:600px;height:auto}
.choke .ink{fill:var(--ink)}.choke .mut{fill:var(--muted)}
.choke .hd{fill:var(--surface);stroke:var(--line)}.choke .ax{stroke:var(--faint);fill:none;stroke-width:1.25}.choke .ax-f{fill:var(--faint)}
.choke .t1{fill:color-mix(in srgb,var(--accent) 14%,transparent);stroke:var(--accent);stroke-width:2}
.choke .t2{fill:color-mix(in srgb,var(--t2) 12%,transparent);stroke:var(--t2);stroke-width:1.5}
.choke .t3{fill:var(--surface);stroke:var(--faint);stroke-width:1}
.src{font-size:13.5px;color:var(--muted)}.src li{margin:0 0 4px;word-break:break-word}
.fine{color:var(--faint);font-size:13.5px}
.cards{display:grid;gap:14px;margin:0 0 48px}
.card{display:block;text-decoration:none;color:var(--ink);background:var(--surface);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow);padding:22px 24px;transition:transform .15s}
.card:hover{transform:translateY(-2px)}
.card h2{border:0;padding:0;margin:4px 0 8px}.card p{color:var(--muted);margin:0 0 10px}.card .go{color:var(--accent);font-weight:700;font-size:14.5px}
.hero{margin:16px 0 28px}.hero h1{margin-bottom:8px}.hero p{color:var(--muted);max-width:62ch}
footer{color:var(--faint);font-size:13px;padding:0 0 40px}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""

LOGO = ('<span class="logo" aria-hidden="true"><svg width="18" height="18" viewBox="0 0 18 18"><rect x="2" y="9" width="3" height="7" rx="1.5" fill="#ff7b72"/>'
        '<rect x="7.5" y="5" width="3" height="11" rx="1.5" fill="#3ddc9b"/><rect x="13" y="2" width="3" height="14" rx="1.5" fill="#3ddc9b"/></svg></span>')

JS = """<script>
(function(){var L=["en","zh","tw"],C={en:"en",zh:"zh-CN",tw:"zh-TW"},T=%s;
function det(){var ls=(navigator.languages&&navigator.languages.length?navigator.languages:[navigator.language||"en"]);
 for(var i=0;i<ls.length;i++){var x=String(ls[i]).toLowerCase();if(x.indexOf("zh")===0)return /hant|-tw|-hk|-mo/.test(x)?"tw":"zh";if(x.indexOf("en")===0)return "en"}return "en"}
var lang=det();try{var v=localStorage.getItem("sif-lang");if(L.indexOf(v)>=0)lang=v}catch(e){}
try{var q=new URLSearchParams(location.search).get("lang");if(L.indexOf(q)>=0)lang=q}catch(e){}
function set(k){lang=k;var h=document.documentElement;h.className="l-"+k;h.lang=C[k];if(T[k])document.title=T[k];
 L.forEach(function(x){var b=document.getElementById("lang-"+x);if(b)b.setAttribute("aria-pressed",String(x===k))});
 window.PAGE_LANG=k;if(window.onPageLang)window.onPageLang(k)}
set(lang);
L.forEach(function(k){var b=document.getElementById("lang-"+k);if(b)b.addEventListener("click",function(){try{localStorage.setItem("sif-lang",k)}catch(e){}set(k)})});
})();
</script>"""

FONTS = "".join(
    f"@font-face{{font-family:'{fam}';font-style:normal;font-weight:{w};font-display:swap;src:url(/fonts/{f}) format('woff2');"
    "unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}"
    for fam, w, f in (("Figtree", 400, "f1.woff2"), ("Figtree", 600, "f2.woff2"), ("Figtree", 700, "f3.woff2"), ("Bricolage Grotesque", 700, "f4.woff2")))

def page(path, titles, desc, body, extra=""):
    url = f"{SITE}/{path}"
    return f"""<!doctype html>
<html lang="zh-CN" class="l-zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{html.escape(titles['zh'])}</title>
<meta name="description" content="{html.escape(desc)}">
<meta property="og:type" content="article"><meta property="og:site_name" content="April's Stock Atlas"><meta property="og:title" content="{html.escape(titles['zh'])}">
<meta property="og:description" content="{html.escape(desc)}"><meta property="og:url" content="{url}"><meta property="og:image" content="{SITE}/og.png">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:image" content="{SITE}/og.png">
<link rel="canonical" href="{url}">
<link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="apple-touch-icon" href="/apple-touch-icon.png">
<meta name="theme-color" content="#eef1f5" media="(prefers-color-scheme: light)"><meta name="theme-color" content="#0b111b" media="(prefers-color-scheme: dark)">
<style>{FONTS}{CSS}</style>
</head>
<body>
<script src="/earnings/switcher.js"></script>
<div class="wrap">
<header class="top">
<a class="brand" href="/" aria-label="April's Stock Atlas">{LOGO}<b><i>April's</i> Stock Atlas</b></a>
<div class="lang" role="group" aria-label="Language / 语言">
<button type="button" id="lang-en" aria-pressed="false">EN</button>
<button type="button" id="lang-zh" aria-pressed="true" lang="zh-CN">简<span class="l2">体</span></button>
<button type="button" id="lang-tw" aria-pressed="false" lang="zh-TW">繁<span class="l2">體</span></button>
</div>
</header>
{body}
<footer>April's Stock Atlas · april-insider-flow.com</footer>
</div>
{extra}
{JS % json.dumps(titles, ensure_ascii=False)}
</body>
</html>
"""

# ------------------------------------------------------------------ market watch page
DAYS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "days")
SECTOR_ETF = {"Technology": "XLK", "Communication Services": "XLC", "Consumer Cyclical": "XLY", "Consumer Defensive": "XLP",
              "Energy": "XLE", "Financial Services": "XLF", "Healthcare": "XLV", "Industrials": "XLI",
              "Basic Materials": "XLB", "Real Estate": "XLRE", "Utilities": "XLU"}
SEC_NAME = {
    "zh": {"Technology": "科技", "Communication Services": "通信服务", "Consumer Cyclical": "周期性消费", "Consumer Defensive": "防御性消费",
           "Energy": "能源", "Financial Services": "金融服务", "Healthcare": "医疗保健", "Industrials": "工业",
           "Basic Materials": "基础材料", "Real Estate": "房地产", "Utilities": "公用事业"},
    "tw": {"Technology": "科技", "Communication Services": "通訊服務", "Consumer Cyclical": "週期性消費", "Consumer Defensive": "防禦性消費",
           "Energy": "能源", "Financial Services": "金融服務", "Healthcare": "醫療保健", "Industrials": "工業",
           "Basic Materials": "基礎材料", "Real Estate": "房地產", "Utilities": "公用事業"},
    "en": {k: k for k in SECTOR_ETF},
}
WINDOW_DAYS = 30

def insider_sectors(days_dir=DAYS):
    """Effective insider buying/selling per sector over the last 30 days (filing dates), same definition as the site."""
    import datetime as dt
    days = []
    for f in sorted(glob.glob(os.path.join(days_dir, "*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        if isinstance(d, dict) and "data" in d and "sectors" not in d: d = d["data"]
        if isinstance(d, dict) and d.get("date") and d.get("companies") is not None: days.append(d)
    if not days: return None
    asof = max(d["date"] for d in days)
    start = (dt.date.fromisoformat(asof) - dt.timedelta(days=WINDOW_DAYS - 1)).isoformat()
    agg = {s: {"buy": 0, "sell": 0, "b": set(), "s": set()} for s in SECTOR_ETF}
    for d in days:
        if d["date"] < start: continue
        for c in d["companies"]:
            a = agg.get(c.get("sector"))
            if a is None: continue
            key = c.get("cik") or c.get("ticker")
            if c.get("eff_buy_usd"): a["buy"] += c["eff_buy_usd"]; a["b"].add(key)
            if c.get("eff_sell_usd"): a["sell"] += c["eff_sell_usd"]; a["s"].add(key)
    return {"from": start, "to": asof,
            "s": {k: {"buy": round(v["buy"]), "sell": round(v["sell"]), "nb": len(v["b"]), "ns": len(v["s"])} for k, v in agg.items()}}

MK = {
    "zh": {"title": "市场观察", "intro": "美股整体的宏观与板块面貌：利率、油价、资金在板块之间的流动，以及本站内部人数据的板块视角。每个交易日更新，只做公开数据的汇总，不是买卖建议。",
           "dashH": "宏观仪表盘", "dashP": "六个最影响整体估值的指标。不需要每天看，每周看一次变化方向就够了。",
           "secH": "板块轮动", "secP": "11个板块的表现，对照近30天内部人的有效买卖（已排除10b5-1计划、期权行权、税务代扣等，与内部人动向页口径一致）。点表头可以排序。",
           "artH": "文章", "artP": "对单一主题的长篇研究笔记，每篇附资料来源。",
           "loading": "价格数据加载中…", "err": "价格数据暂时无法加载，请稍后再试。",
           "wk": "近一周", "m1": "近1个月", "ytd": "今年以来", "hi": "距52周高点", "sector": "板块", "etf": "ETF",
           "ib": "内部人有效买入", "is": "有效卖出", "nb": "买入公司数", "flag": "股价跌、内部人净买入",
           "eqw": "等权", "cap": "市值加权", "small": "小盘", "large": "大盘", "ahead": "跑赢", "behind": "跑输",
           "note": "价格截至 {p}，每个交易日收盘后更新。内部人数据为 {f} 至 {t} 的 SEC Form 4 申报。这是公开数据的汇总，不是买卖建议。",
           "insLink": "查看内部人动向明细 →",
           "cards": {"TNX": ["10年期美债收益率", "所有资产定价的锚；高于5%会压低股票估值"],
                     "WTI": ["WTI原油", "通胀预期的主要来源，影响美联储是否继续加息"],
                     "DXY": ["美元指数", "美元走强会压低海外收入和大宗商品价格"],
                     "VIX": ["VIX恐慌指数", "市场恐慌程度；急升后回落常伴随阶段性低点"],
                     "BRD": ["等权 vs 市值加权", "等权跑赢，说明上涨在向更多股票扩散"],
                     "SML": ["小盘 vs 大盘", "小盘领涨，说明市场开始相信利率见顶"]}},
    "tw": {"title": "市場觀察", "intro": "美股整體的總體經濟與板塊面貌：利率、油價、資金在板塊之間的流動，以及本站內部人資料的板塊視角。每個交易日更新，只做公開資料的彙總，不是買賣建議。",
           "dashH": "總經儀表板", "dashP": "六個最影響整體估值的指標。不需要每天看，每週看一次變化方向就夠了。",
           "secH": "板塊輪動", "secP": "11個板塊的表現，對照近30天內部人的有效買賣（已排除10b5-1計畫、選擇權行權、稅務代扣等，與內部人動向頁口徑一致）。點表頭可以排序。",
           "artH": "文章", "artP": "對單一主題的長篇研究筆記，每篇附資料來源。",
           "loading": "價格資料載入中…", "err": "價格資料暫時無法載入，請稍後再試。",
           "wk": "近一週", "m1": "近1個月", "ytd": "今年以來", "hi": "距52週高點", "sector": "板塊", "etf": "ETF",
           "ib": "內部人有效買入", "is": "有效賣出", "nb": "買入公司數", "flag": "股價跌、內部人淨買入",
           "eqw": "等權", "cap": "市值加權", "small": "小型股", "large": "大型股", "ahead": "跑贏", "behind": "跑輸",
           "note": "價格截至 {p}，每個交易日收盤後更新。內部人資料為 {f} 至 {t} 的 SEC Form 4 申報。這是公開資料的彙總，不是買賣建議。",
           "insLink": "查看內部人動向明細 →",
           "cards": {"TNX": ["10年期美債殖利率", "所有資產定價的錨；高於5%會壓低股票估值"],
                     "WTI": ["WTI原油", "通膨預期的主要來源，影響聯準會是否繼續升息"],
                     "DXY": ["美元指數", "美元走強會壓低海外收入和大宗商品價格"],
                     "VIX": ["VIX恐慌指數", "市場恐慌程度；急升後回落常伴隨階段性低點"],
                     "BRD": ["等權 vs 市值加權", "等權跑贏，說明上漲在向更多股票擴散"],
                     "SML": ["小型股 vs 大型股", "小型股領漲，說明市場開始相信利率見頂"]}},
    "en": {"title": "Market watch", "intro": "The macro and sector picture of the whole US stock market: rates, oil, how money moves between sectors, and this site's insider data seen by sector. Updated every trading day; a summary of public data, not trading advice.",
           "dashH": "Macro dashboard", "dashP": "Six indicators that move valuations across the market. No need to check daily; the weekly direction is enough.",
           "secH": "Sector rotation", "secP": "How the 11 sectors are doing, next to effective insider buying and selling over the last 30 days (10b5-1 plans, option exercises, tax withholding and similar excluded, as on the insider page). Click a column header to sort.",
           "artH": "Articles", "artP": "Long-form research notes on a single theme, each with its sources.",
           "loading": "Loading price data…", "err": "Price data could not be loaded. Please try again later.",
           "wk": "1 week", "m1": "1 month", "ytd": "Year to date", "hi": "From 52-week high", "sector": "Sector", "etf": "ETF",
           "ib": "Insider effective buying", "is": "Effective selling", "nb": "Companies buying", "flag": "Price down, insiders net buying",
           "eqw": "Equal weight", "cap": "Cap weight", "small": "Small caps", "large": "Large caps", "ahead": "ahead", "behind": "behind",
           "note": "Prices as of {p}, updated after every close. Insider data covers SEC Form 4 filings from {f} to {t}. A summary of public data, not trading advice.",
           "insLink": "See insider trade details →",
           "cards": {"TNX": ["US 10-year Treasury yield", "The anchor for pricing every asset; above 5% it weighs on stock valuations"],
                     "WTI": ["WTI crude oil", "The main driver of inflation expectations and of whether the Fed keeps hiking"],
                     "DXY": ["US dollar index", "A stronger dollar weighs on overseas revenue and commodity prices"],
                     "VIX": ["VIX", "How fearful the market is; a spike that fades often comes with a short-term low"],
                     "BRD": ["Equal vs cap weight", "Equal weight leading means gains are spreading to more stocks"],
                     "SML": ["Small vs large caps", "Small caps leading suggests the market believes rates have peaked"]}},
}

MARKET_CSS = """
.mk-hero{margin:16px 0 22px}.mk-hero h1{margin-bottom:8px}.mk-hero p{color:var(--muted);max-width:68ch;margin:0}
.mk-sec{margin:0 0 40px}.mk-sec>h2{border:0;padding:0;margin:0 0 6px}.mk-sec>p.lead{color:var(--muted);margin:0 0 16px;max-width:72ch;font-size:15px}
.dash{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
@media (max-width:860px){.dash{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:520px){.dash{grid-template-columns:1fr}}
.kpi{min-width:0;overflow:hidden;background:var(--surface);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow);padding:16px 18px;display:grid;gap:4px}
.kpi .lab{font-size:13.5px;color:var(--muted);font-weight:600}
.kpi .row{display:flex;align-items:flex-end;justify-content:space-between;gap:10px}
.kpi .val{font:700 28px/1.1 var(--display);letter-spacing:-.01em}
.kpi .row>div{min-width:0}
.kpi .chg{font-size:13.5px;color:var(--muted);line-height:1.45}
.kpi .chg b{color:var(--ink);font-weight:700}
.kpi .why{font-size:13px;color:var(--faint);line-height:1.5}
.kpi svg{width:104px;height:34px;flex:0 1 104px;min-width:64px;color:var(--accent)}
.sect{background:var(--surface);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow);overflow-x:auto;-webkit-overflow-scrolling:touch}
.sect table{min-width:820px;font-size:14px}
.sect th{cursor:pointer;user-select:none;background:var(--surface-2)}
.sect th[aria-sort]::after{content:" ↓";color:var(--accent)}.sect th[aria-sort=ascending]::after{content:" ↑"}
.sect td,.sect th{white-space:nowrap}
.sect td.n,.sect th.n{text-align:right;font-variant-numeric:tabular-nums}
.sect tr.flag td{background:color-mix(in srgb,var(--t2) 9%,transparent)}
.sect .tag{display:inline-block;margin-left:8px;font-size:11.5px;font-weight:700;color:var(--t2);border:1px solid var(--t2);border-radius:999px;padding:0 7px;vertical-align:1px}
.sect td:first-child,.sect th:first-child{position:sticky;left:0;background:inherit;z-index:1}
.sect tbody td:first-child{background:var(--surface)}.sect tr.flag td:first-child{background:color-mix(in srgb,var(--t2) 9%,var(--surface))}
.up{color:#0f9d6e}.dn{color:#e0483f}
@media (prefers-color-scheme:dark){.up{color:#34d399}.dn{color:#ff7b72}}
.mk-note{font-size:13px;color:var(--faint);margin:10px 0 0}.mk-note a{font-weight:600}
.mk-msg{color:var(--muted);padding:18px;background:var(--surface);border:1px dashed var(--line);border-radius:14px}
"""

MARKET_JS = r"""<script>
(function(){
var MK=__MK__,INS=__INS__,SEC=__SEC__,ETF=__ETF__,DATA=null,FAIL=false,sortKey="ytd",sortDir=-1;
function $(id){return document.getElementById(id)}
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function ser(k){return DATA&&DATA.t[k]||null}
function at(r,n){return r.length>n?r[r.length-1-n][1]:null}
function pct(a,b){return a==null||b==null||!b?null:(a/b-1)*100}
function sgn(x,d,u){if(x==null||isNaN(x))return "–";var v=Math.abs(x).toFixed(d);return(x>0?"+":x<0?"−":"")+v+(u||"")}
function cls(x){return x==null?"":x>0?"up":x<0?"dn":""}
function ytdBase(r){var y=r[r.length-1][0].slice(0,4),b=null;for(var i=0;i<r.length;i++){if(r[i][0]<y+"-01-01")b=r[i][1]}return b==null?r[0][1]:b}
function hi52(r){var m=-Infinity;for(var i=Math.max(0,r.length-252);i<r.length;i++)m=Math.max(m,r[i][1]);return m}
function spark(vals){if(!vals||vals.length<2)return "";var mn=Math.min.apply(null,vals),mx=Math.max.apply(null,vals),W=112,H=34,p=3;
 var pts=vals.map(function(v,i){return(i/(vals.length-1)*W).toFixed(1)+","+(H-p-(mx===mn?0.5:(v-mn)/(mx-mn))*(H-2*p)).toFixed(1)}).join(" ");
 return '<svg viewBox="0 0 '+W+' '+H+'" aria-hidden="true"><polyline points="'+pts+'" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/></svg>'}
function tail(r,n){return r.slice(-n).map(function(x){return x[1]})}
function ratio(a,b,n){var m={};b.forEach(function(x){m[x[0]]=x[1]});var o=[];a.forEach(function(x){if(m[x[0]])o.push(x[1]/m[x[0]])});return o.slice(-n)}
function money(v){if(!v)return "–";var a=Math.abs(v);return "$"+(a>=1e9?(a/1e9).toFixed(1)+"B":a>=1e6?(a/1e6).toFixed(1)+"M":a>=1e3?Math.round(a/1e3)+"K":Math.round(a))}
function card(l,k,val,chg,sp){var c=MK[l].cards[k];
 return '<div class="kpi"><div class="lab">'+esc(c[0])+'</div><div class="row"><div><div class="val">'+val+'</div><div class="chg">'+chg+'</div></div>'+sp+'</div><div class="why">'+esc(c[1])+'</div></div>'}
function dash(l){var u=MK[l],h=[],r;
 if((r=ser("TNX"))){var v=at(r,0),w=at(r,5);h.push(card(l,"TNX",v.toFixed(2)+"%",u.wk+' <b class="'+cls(v-w)+'">'+sgn((v-w)*100,0,"bp")+'</b>',spark(tail(r,126))))}
 if((r=ser("WTI"))){var v2=at(r,0);h.push(card(l,"WTI","$"+v2.toFixed(2),u.wk+' <b class="'+cls(pct(v2,at(r,5)))+'">'+sgn(pct(v2,at(r,5)),1,"%")+'</b>',spark(tail(r,126))))}
 if((r=ser("DXY"))){var v3=at(r,0);h.push(card(l,"DXY",v3.toFixed(2),u.wk+' <b class="'+cls(pct(v3,at(r,5)))+'">'+sgn(pct(v3,at(r,5)),1,"%")+'</b>',spark(tail(r,126))))}
 if((r=ser("VIX"))){var v4=at(r,0),w4=at(r,5);h.push(card(l,"VIX",v4.toFixed(1),u.wk+' <b>'+sgn(v4-w4,1)+'</b>',spark(tail(r,126))))}
 [["BRD","RSP","SPY",u.eqw,u.cap],["SML","IWM","SPY",u.small,u.large]].forEach(function(x){var a=ser(x[1]),b=ser(x[2]);if(!a||!b)return;
  var ra=pct(at(a,0),at(a,21)),rb=pct(at(b,0),at(b,21)),d=ra-rb;
  h.push(card(l,x[0],'<span class="'+cls(d)+'">'+sgn(d,1,"pp")+'</span>',u.m1+": "+esc(x[3])+" "+sgn(ra,1,"%")+" · "+esc(x[4])+" "+sgn(rb,1,"%"),spark(ratio(a,b,126))))});
 return h.length?'<div class="dash">'+h.join("")+'</div>':'<p class="mk-msg">'+esc(u.err)+'</p>'}
function rows(){return Object.keys(ETF).map(function(s){var r=ser(ETF[s]),i=(INS&&INS.s[s])||{buy:0,sell:0,nb:0,ns:0};
 var o={s:s,etf:ETF[s],ytd:null,m1:null,hi:null,buy:i.buy,sell:i.sell,nb:i.nb};
 if(r){var v=at(r,0);o.ytd=pct(v,ytdBase(r));o.m1=pct(v,at(r,21));o.hi=pct(v,hi52(r))}
 o.flag=o.m1!=null&&o.m1<0&&i.buy>i.sell;return o})}
function table(l){var u=MK[l],R=rows();
 R.sort(function(a,b){var x=a[sortKey],y=b[sortKey];if(sortKey==="s"){x=SEC[l][a.s];y=SEC[l][b.s];return sortDir*(x<y?-1:x>y?1:0)}
  if(x==null)return 1;if(y==null)return -1;return sortDir*(x-y)});
 var cols=[["s",u.sector,""],["etf",u.etf,""],["ytd",u.ytd,"n"],["m1",u.m1,"n"],["hi",u.hi,"n"],["buy",u.ib,"n"],["sell",u.is,"n"],["nb",u.nb,"n"]];
 var th=cols.map(function(c){return '<th class="'+c[2]+'" data-k="'+c[0]+'"'+(c[0]===sortKey?' aria-sort="'+(sortDir<0?"descending":"ascending")+'"':"")+'>'+esc(c[1])+'</th>'}).join("");
 var tb=R.map(function(o){return '<tr'+(o.flag?' class="flag"':'')+'><td>'+esc(SEC[l][o.s])+(o.flag?'<span class="tag">'+esc(u.flag)+'</span>':'')+'</td><td>'+o.etf+'</td>'+
  '<td class="n '+cls(o.ytd)+'">'+sgn(o.ytd,1,"%")+'</td><td class="n '+cls(o.m1)+'">'+sgn(o.m1,1,"%")+'</td><td class="n">'+sgn(o.hi,1,"%")+'</td>'+
  '<td class="n">'+money(o.buy)+'</td><td class="n">'+money(o.sell)+'</td><td class="n">'+(o.nb||"–")+'</td></tr>'}).join("");
 return '<div class="sect"><table><thead><tr>'+th+'</tr></thead><tbody>'+tb+'</tbody></table></div>'}
function render(l){var u=MK[l];
 var d=$("mk-dash"),t=$("mk-sect"),n=$("mk-note");if(!d)return;
 if(!DATA){d.innerHTML='<p class="mk-msg">'+esc(FAIL?u.err:u.loading)+'</p>';t.innerHTML="";n.innerHTML="";return}
 d.innerHTML=dash(l);t.innerHTML=table(l);
 n.innerHTML=esc(u.note.replace("{p}",DATA.last||"").replace("{f}",INS?INS.from:"").replace("{t}",INS?INS.to:""))+' <a href="/insider/">'+esc(u.insLink)+'</a>';
 t.querySelectorAll("th").forEach(function(h){h.addEventListener("click",function(){var k=h.getAttribute("data-k");if(k===sortKey)sortDir=-sortDir;else{sortKey=k;sortDir=k==="s"||k==="etf"?1:-1}render(window.PAGE_LANG||"zh")})})}
window.onPageLang=function(l){render(l)};
fetch("/earnings/data/market.json",{cache:"no-cache"}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(j){DATA=j;render(window.PAGE_LANG||"zh")}).catch(function(){FAIL=true;render(window.PAGE_LANG||"zh")});
})();
</script>"""

def market_page(arts, out):
    ins = insider_sectors()
    sec = {}
    for l in LANGS:
        u, m = UI[l], MK[l]
        cards = "".join(f'<a class="card" href="/articles/{a["slug"]}/"><p class="meta">{html.escape(a["date"])}</p><h2>{inline(a["l"][l][0].get("title", ""))}</h2>'
                        f'<p>{inline(a["l"][l][0].get("summary", ""))}</p><span class="go">{u["read"]}</span></a>' for a in arts)
        sec[l] = (f'<div data-l="{l}" lang="{LOC[l]}" class="mk-hero"><h1>{m["title"]}</h1><p>{m["intro"]}</p></div>',
                  f'<div data-l="{l}" lang="{LOC[l]}"><h2>{m["dashH"]}</h2><p class="lead">{m["dashP"]}</p></div>',
                  f'<div data-l="{l}" lang="{LOC[l]}"><h2>{m["secH"]}</h2><p class="lead">{m["secP"]}</p></div>',
                  f'<div data-l="{l}" lang="{LOC[l]}"><h2>{m["artH"]}</h2><p class="lead">{m["artP"]}</p><div class="cards">{cards}</div></div>')
    pick = lambda i: "".join(sec[l][i] for l in LANGS)
    body = (f'<main>{pick(0)}<section class="mk-sec">{pick(1)}<div id="mk-dash"></div></section>'
            f'<section class="mk-sec">{pick(2)}<div id="mk-sect"></div><p class="mk-note" id="mk-note"></p></section>'
            f'<section class="mk-sec" id="articles">{pick(3)}</section></main>'
            f'<style>{MARKET_CSS}</style>')
    js = (MARKET_JS.replace("__MK__", json.dumps(MK, ensure_ascii=False)).replace("__INS__", json.dumps(ins))
          .replace("__SEC__", json.dumps(SEC_NAME, ensure_ascii=False)).replace("__ETF__", json.dumps(SECTOR_ETF)))
    titles = {l: f'{MK[l]["title"]} · April\'s Stock Atlas' for l in LANGS}
    os.makedirs(f"{out}/market", exist_ok=True)
    open(f"{out}/market/index.html", "w", encoding="utf-8").write(page("market/", titles, MK["zh"]["intro"], body, js))
    # old /articles/ list now lives on the market page
    os.makedirs(f"{out}/articles", exist_ok=True)
    open(f"{out}/articles/index.html", "w", encoding="utf-8").write(
        '<!doctype html><meta charset="utf-8"><title>Market watch</title><link rel="canonical" href="https://april-insider-flow.com/market/">'
        '<meta http-equiv="refresh" content="0;url=/market/#articles"><a href="/market/#articles">/market/</a>')

# ------------------------------------------------------------------ build
def articles():
    slugs = sorted({os.path.basename(p).split(".")[0] for p in glob.glob(os.path.join(ROOT, "*.zh.md"))})
    out = []
    for s in slugs:
        a = {"slug": s, "l": {}}
        for l in LANGS:
            p = os.path.join(ROOT, f"{s}.{l}.md")
            if not os.path.exists(p): p = os.path.join(ROOT, f"{s}.zh.md")
            a["l"][l] = read(p)
        a["date"] = a["l"]["zh"][0].get("date", "")
        out.append(a)
    return sorted(out, key=lambda a: (a["date"], a["slug"]), reverse=True)

WIDE = ("环节", "環節", "Link")

def build(out):
    arts = articles()
    written = []
    for a in arts:
        s = a["slug"]; draw = DIAGRAMS.get(s)
        sp = os.path.join(ROOT, f"{s}.sources.md")
        sources = open(sp, encoding="utf-8").read() if os.path.exists(sp) else ""
        blocks = []
        for l in LANGS:
            meta, body = a["l"][l]; u = UI[l]
            src = f'<h2>{u["sources"]}</h2><div class="src">{md(sources)}</div>' if sources else ""
            blocks.append(f'<article data-l="{l}" lang="{LOC[l]}"><p class="crumb"><a href="/market/">{u["back"]}</a></p>'
                          f'<p class="meta">{html.escape(meta.get("date", ""))}</p><h1>{inline(meta.get("title", ""))}</h1>'
                          f'<p class="sub">{inline(meta.get("subtitle", ""))}</p>{md(body, draw(l) if draw else "")}{src}</article>')
        body = '<main class="paper"><div class="col">' + "".join(blocks) + "</div></main>"
        for w in WIDE:
            body = body.replace(f'<div class="tbl"><table><thead><tr><th>{w}', f'<div class="tbl wide"><table><thead><tr><th>{w}')
        titles = {l: f'{a["l"][l][0].get("title", "")} · April\'s Stock Atlas' for l in LANGS}
        os.makedirs(f"{out}/articles/{s}", exist_ok=True)
        open(f"{out}/articles/{s}/index.html", "w", encoding="utf-8").write(page(f"articles/{s}/", titles, a["l"]["zh"][0].get("summary", ""), body))
        written.append(f"articles/{s}/")
    market_page(arts, out)
    written.insert(0, "market/")
    return written

if __name__ == "__main__":
    import sys
    print(build(sys.argv[1] if len(sys.argv) > 1 else "public"))
