"""Build the Articles section (/articles/) of April's Stock Atlas.

Sources live in articles/src/<slug>.<lang>.md (lang = zh, tw, en), each with a small front matter block
(slug, date, title, subtitle, summary). articles/src/sources.md is a shared reference list appended to
every article. A paragraph that is exactly [[diagram]] is replaced by the article's inline SVG
(DIAGRAMS below), drawn in the page's own colours so it follows light and dark mode.

Each article becomes ONE page holding all three languages; the reader's language (sif-lang, the same
key the rest of the site uses) decides which one shows. Without JavaScript the Simplified Chinese
version shows. Standard library only, because the daily workflow runs plain python3 -I.

    build(out)  -> list of site paths written, e.g. ["articles/", "articles/ai-chokepoints/"]
"""
import os, re, html, glob, json

SITE = "https://april-insider-flow.com"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "articles", "src")
LANGS = ("zh", "tw", "en")
LOC = {"zh": "zh-CN", "tw": "zh-TW", "en": "en"}

UI = {
    "zh": {"section": "文章", "intro": "围绕AI产业链的长篇研究笔记。每篇都附资料来源，仅供研究，不构成投资建议。",
           "back": "← 全部文章", "sources": "资料来源", "read": "阅读全文 →", "updated": "数据截至"},
    "tw": {"section": "文章", "intro": "圍繞AI產業鏈的長篇研究筆記。每篇都附資料來源，僅供研究，不構成投資建議。",
           "back": "← 全部文章", "sources": "資料來源", "read": "閱讀全文 →", "updated": "資料截至"},
    "en": {"section": "Articles", "intro": "Long-form research notes on the AI supply chain. Every piece lists its sources; for research only, not investment advice.",
           "back": "← All articles", "sources": "Sources", "read": "Read →", "updated": "Data as of"},
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
 L.forEach(function(x){var b=document.getElementById("lang-"+x);if(b)b.setAttribute("aria-pressed",String(x===k))})}
set(lang);
L.forEach(function(k){var b=document.getElementById("lang-"+k);if(b)b.addEventListener("click",function(){try{localStorage.setItem("sif-lang",k)}catch(e){}set(k)})});
})();
</script>"""

FONTS = "".join(
    f"@font-face{{font-family:'{fam}';font-style:normal;font-weight:{w};font-display:swap;src:url(/fonts/{f}) format('woff2');"
    "unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+2000-206F,U+2074,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}"
    for fam, w, f in (("Figtree", 400, "f1.woff2"), ("Figtree", 600, "f2.woff2"), ("Figtree", 700, "f3.woff2"), ("Bricolage Grotesque", 700, "f4.woff2")))

def page(path, titles, desc, body):
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
{JS % json.dumps(titles, ensure_ascii=False)}
</body>
</html>
"""

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
    return sorted(out, key=lambda a: a["date"], reverse=True)

def build(out):
    arts = articles()
    src_path = os.path.join(ROOT, "sources.md")
    sources = open(src_path, encoding="utf-8").read() if os.path.exists(src_path) else ""
    written = []
    for a in arts:
        s = a["slug"]; draw = DIAGRAMS.get(s)
        blocks = []
        for l in LANGS:
            meta, body = a["l"][l]; u = UI[l]
            src = f'<h2>{u["sources"]}</h2><div class="src">{md(sources)}</div>' if sources else ""
            blocks.append(f'<article data-l="{l}" lang="{LOC[l]}"><p class="crumb"><a href="/articles/">{u["back"]}</a></p>'
                          f'<p class="meta">{html.escape(meta.get("date", ""))}</p><h1>{inline(meta.get("title", ""))}</h1>'
                          f'<p class="sub">{inline(meta.get("subtitle", ""))}</p>{md(body, draw(l) if draw else "")}{src}</article>')
        body = '<main class="paper"><div class="col">' + "".join(blocks) + "</div></main>"
        body = body.replace('<div class="tbl"><table><thead><tr><th>环节', '<div class="tbl wide"><table><thead><tr><th>环节') \
                   .replace('<div class="tbl"><table><thead><tr><th>環節', '<div class="tbl wide"><table><thead><tr><th>環節') \
                   .replace('<div class="tbl"><table><thead><tr><th>Link', '<div class="tbl wide"><table><thead><tr><th>Link')
        titles = {l: f'{a["l"][l][0].get("title", "")} · April\'s Stock Atlas' for l in LANGS}
        os.makedirs(f"{out}/articles/{s}", exist_ok=True)
        open(f"{out}/articles/{s}/index.html", "w", encoding="utf-8").write(page(f"articles/{s}/", titles, a["l"]["zh"][0].get("summary", ""), body))
        written.append(f"articles/{s}/")
    cards = []
    for l in LANGS:
        u = UI[l]
        items = "".join(f'<a class="card" href="/articles/{a["slug"]}/"><p class="meta">{html.escape(a["date"])}</p><h2>{inline(a["l"][l][0].get("title", ""))}</h2>'
                        f'<p>{inline(a["l"][l][0].get("summary", ""))}</p><span class="go">{u["read"]}</span></a>' for a in arts)
        cards.append(f'<section data-l="{l}" lang="{LOC[l]}"><div class="hero"><h1>{u["section"]}</h1><p>{u["intro"]}</p></div><div class="cards">{items}</div></section>')
    titles = {l: f'{UI[l]["section"]} · April\'s Stock Atlas' for l in LANGS}
    os.makedirs(f"{out}/articles", exist_ok=True)
    open(f"{out}/articles/index.html", "w", encoding="utf-8").write(page("articles/", titles, UI["zh"]["intro"], "<main>" + "".join(cards) + "</main>"))
    written.insert(0, "articles/")
    return written

if __name__ == "__main__":
    import sys
    print(build(sys.argv[1] if len(sys.argv) > 1 else "public"))
