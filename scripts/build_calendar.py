"""Build the Calendar page (/calendar/) of April's Stock Atlas from data/macro.json.

data/macro.json is written by scripts/fetch_macro.py from the official schedules (Fed, BLS, BEA, NYSE).
The page embeds the events and also publishes them as /calendar/macro.json for other pages.
Times are shown US Eastern first, then Beijing; both are computed in the browser with the time-zone
database, so daylight-saving changes need nothing here. "Today" and the week grouping follow US Eastern.

    build(out, page)  -> "calendar/"   (page = build_articles.page, the shared site template)
"""
import os, json

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "data", "macro.json")
LANGS = ("zh", "tw", "en")
LOC = {"zh": "zh-CN", "tw": "zh-TW", "en": "en"}

T = {
    "zh": {"title": "日历", "intro": "美股宏观数据、美联储议息、休市和半日市。时间先写美东（ET），括号里是北京时间。日期每天自动从官方网站更新。",
           "week": "本周", "nothing": "本周没有重要的宏观事件。", "upcoming": "接下来", "past": "显示已经过去的事件", "hidePast": "隐藏已经过去的事件",
           "key": "只看最重要的", "all": "显示全部", "today": "今天", "bj": "北京", "next": "次日", "prev": "前一日", "allday": "全天",
           "srcH": "数据来源", "srcP": "全部来自官方发布的日程，每天自动检查一次。官方改期时，这里会跟着更新。",
           "upd": "最近一次更新", "wait": "等待首次自动更新", "back": "← 市场观察",
           "wd": "周日,周一,周二,周三,周四,周五,周六", "md": "{m}月{d}日", "range": "{a} – {b}",
           "k": {"fomc": "美联储议息会议（FOMC）", "cpi": "CPI 消费者物价指数", "jobs": "非农就业报告", "ppi": "PPI 生产者物价指数",
                 "pce": "PCE 物价指数", "gdp": "GDP 经济增长", "closed": "美股休市", "early": "美股半日市"},
           "ref": "（{m}月数据）", "q": "（{y} 年第 {q} 季度，{e}）", "est": {"adv": "首次估计", "2nd": "第二次估计", "3rd": "第三次估计", "upd": "更新估计"},
           "sep": "含经济预测和点阵图", "meet": "{a}–{b}日开会", "earlyT": "提前收盘",
           "w": {"fomc": "决定利率方向，影响所有股票的估值。", "fomcSep": "决定利率方向，影响所有股票的估值；点阵图显示官员们对未来利率的预期。",
                 "cpi": "最受关注的通胀数据。高于预期时降息可能推迟，高估值的成长股通常跌得最多。",
                 "jobs": "看就业市场的冷热。太强可能推迟降息，太弱则让人担心经济衰退。",
                 "ppi": "企业端的成本变化，常被用来提前推测 CPI。", "pce": "美联储最看重的通胀指标，它的目标是 2%。",
                 "gdp": "经济增长的速度。", "gdpAdv": "经济增长速度的第一次估计，对市场影响最大。", "closed": "全天不交易。", "early": "股市提前收盘，成交通常比较清淡。"},
           "hol": {"New Year’s Day": "元旦", "Martin Luther King, Jr. Day": "马丁·路德·金纪念日", "Washington's Birthday": "总统日",
                   "Good Friday": "耶稣受难日", "Memorial Day": "阵亡将士纪念日", "Juneteenth National Independence Day": "六月节",
                   "Independence Day": "独立日", "Labor Day": "劳动节", "Thanksgiving Day": "感恩节", "Christmas Day": "圣诞节"}},
    "tw": {"title": "日曆", "intro": "美股總經數據、聯準會利率決議、休市和半日市。時間先寫美東（ET），括號裡是北京時間。日期每天自動從官方網站更新。",
           "week": "本週", "nothing": "本週沒有重要的總經事件。", "upcoming": "接下來", "past": "顯示已經過去的事件", "hidePast": "隱藏已經過去的事件",
           "key": "只看最重要的", "all": "顯示全部", "today": "今天", "bj": "北京", "next": "次日", "prev": "前一日", "allday": "全天",
           "srcH": "資料來源", "srcP": "全部來自官方發布的日程，每天自動檢查一次。官方改期時，這裡會跟著更新。",
           "upd": "最近一次更新", "wait": "等待首次自動更新", "back": "← 市場觀察",
           "wd": "週日,週一,週二,週三,週四,週五,週六", "md": "{m}月{d}日", "range": "{a} – {b}",
           "k": {"fomc": "聯準會利率決議（FOMC）", "cpi": "CPI 消費者物價指數", "jobs": "非農就業報告", "ppi": "PPI 生產者物價指數",
                 "pce": "PCE 物價指數", "gdp": "GDP 經濟成長", "closed": "美股休市", "early": "美股半日市"},
           "ref": "（{m}月數據）", "q": "（{y} 年第 {q} 季，{e}）", "est": {"adv": "首次估計", "2nd": "第二次估計", "3rd": "第三次估計", "upd": "更新估計"},
           "sep": "含經濟預測與點陣圖", "meet": "{a}–{b}日開會", "earlyT": "提前收盤",
           "w": {"fomc": "決定利率方向，影響所有股票的估值。", "fomcSep": "決定利率方向，影響所有股票的估值；點陣圖顯示官員們對未來利率的預期。",
                 "cpi": "最受關注的通膨數據。高於預期時降息可能延後，高估值的成長股通常跌得最多。",
                 "jobs": "看就業市場的冷熱。太強可能延後降息，太弱則讓人擔心經濟衰退。",
                 "ppi": "企業端的成本變化，常被用來提前推測 CPI。", "pce": "聯準會最看重的通膨指標，它的目標是 2%。",
                 "gdp": "經濟成長的速度。", "gdpAdv": "經濟成長速度的第一次估計，對市場影響最大。", "closed": "全天不交易。", "early": "股市提前收盤，成交通常比較清淡。"},
           "hol": {"New Year’s Day": "元旦", "Martin Luther King, Jr. Day": "馬丁·路德·金恩紀念日", "Washington's Birthday": "總統日",
                   "Good Friday": "耶穌受難日", "Memorial Day": "陣亡將士紀念日", "Juneteenth National Independence Day": "六月節",
                   "Independence Day": "獨立紀念日", "Labor Day": "勞動節", "Thanksgiving Day": "感恩節", "Christmas Day": "聖誕節"}},
    "en": {"title": "Calendar", "intro": "US macro data, Fed rate decisions, market holidays and early closes. Times are US Eastern (ET), with Beijing time in brackets. Dates update automatically from the official sites every day.",
           "week": "This week", "nothing": "No major macro events this week.", "upcoming": "Coming up", "past": "Show past events", "hidePast": "Hide past events",
           "key": "Most important only", "all": "Show all", "today": "Today", "bj": "Beijing", "next": "next day", "prev": "previous day", "allday": "All day",
           "srcH": "Sources", "srcP": "All dates come from the official published schedules and are checked automatically every day. When an agency moves a date, this page follows.",
           "upd": "Last updated", "wait": "waiting for the first automatic update", "back": "← Market watch",
           "wd": "Sun,Mon,Tue,Wed,Thu,Fri,Sat", "md": "{M} {d}", "range": "{a} – {b}",
           "k": {"fomc": "Fed rate decision (FOMC)", "cpi": "CPI inflation", "jobs": "Jobs report (nonfarm payrolls)", "ppi": "PPI producer prices",
                 "pce": "PCE inflation", "gdp": "GDP growth", "closed": "US market closed", "early": "US market early close"},
           "ref": " ({M} data)", "q": " (Q{q} {y}, {e})", "est": {"adv": "advance estimate", "2nd": "second estimate", "3rd": "third estimate", "upd": "updated estimate"},
           "sep": "with projections and dot plot", "meet": "meets {a}–{b}", "earlyT": "Early close",
           "w": {"fomc": "Sets the direction of rates, which moves the valuation of every stock.", "fomcSep": "Sets the direction of rates, which moves every stock's valuation; the dot plot shows where officials expect rates to go.",
                 "cpi": "The most watched inflation number. A hot reading can delay rate cuts, and richly valued growth stocks usually fall the most.",
                 "jobs": "How hot or cold the job market is. Too strong can delay cuts; too weak raises recession worries.",
                 "ppi": "Costs at the business level, often used to anticipate CPI.", "pce": "The Fed's preferred inflation gauge; its target is 2%.",
                 "gdp": "How fast the economy is growing.", "gdpAdv": "The first estimate of economic growth, the one that moves markets most.", "closed": "No trading all day.", "early": "Stocks close early; trading is usually thin."},
           "hol": {}},
}
SRC = {"fomc": ("Federal Reserve", "美联储", "聯準會"), "cpi": ("BLS · CPI", "劳工统计局 · CPI", "勞工統計局 · CPI"),
       "jobs": ("BLS · Employment Situation", "劳工统计局 · 非农", "勞工統計局 · 非農"), "ppi": ("BLS · PPI", "劳工统计局 · PPI", "勞工統計局 · PPI"),
       "bea": ("BEA · PCE, GDP", "经济分析局 · PCE、GDP", "經濟分析局 · PCE、GDP"), "nyse": ("NYSE · holidays", "纽交所 · 休市", "紐交所 · 休市")}

CSS = """
.cal-hero{margin:16px 0 22px}.cal-hero p{color:var(--muted);max-width:66ch;margin:0}
.cal-bar{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 18px}
.cal-bar button{border:1px solid var(--line);background:var(--surface);border-radius:999px;padding:6px 14px;font-size:14px;cursor:pointer;color:var(--ink)}
.cal-bar button[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.cal-wk{background:var(--surface);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow);padding:6px 20px;margin:0 0 18px}
.cal-wk.now{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent),var(--shadow)}
.cal-wk h2{margin:14px 0 4px;padding:0;border:0;font-size:18px;display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}
.cal-wk h2 small{font:500 13.5px var(--body);color:var(--muted)}
.cal-ev{display:grid;grid-template-columns:7.5em 1fr;gap:4px 16px;padding:12px 0;border-top:1px solid var(--line)}
.cal-wk h2+.cal-ev{border-top:0}
.cal-d{font-weight:700;font-variant-numeric:tabular-nums;line-height:1.4}.cal-d small{display:block;font-weight:500;color:var(--muted);font-size:13px}
.cal-ev.past{opacity:.55}.cal-ev.today .cal-d{color:var(--accent)}
.cal-n{font-weight:700;line-height:1.4}.cal-n .dots{color:var(--accent);letter-spacing:1px;margin-left:6px;font-size:12px}
.cal-t{font-variant-numeric:tabular-nums;font-size:14.5px;margin:2px 0}.cal-t b{font-weight:700}.cal-t span{color:var(--muted)}
.cal-w{color:var(--muted);font-size:14px;margin:2px 0 0;line-height:1.55}
.cal-tag{display:inline-block;font-size:12px;font-weight:700;border-radius:6px;padding:1px 7px;margin-right:6px;vertical-align:1px;background:var(--surface-2);color:var(--muted)}
.cal-ev.k-closed .cal-tag,.cal-ev.k-early .cal-tag{background:color-mix(in srgb,var(--t2,#e5a00d) 18%,transparent);color:var(--ink)}
.cal-empty{color:var(--muted);padding:12px 0;border-top:1px solid var(--line)}
.cal-src{font-size:13.5px;color:var(--muted);margin:30px 0 40px}.cal-src ul{padding-left:1.2em}.cal-src li{margin:0 0 3px}
@media (max-width:560px){.cal-ev{grid-template-columns:1fr}.cal-wk{padding:4px 14px}}
"""

JS = r"""<script>
(function(){
var T=__T__, D=__D__, SRC=__SRC__, KEYK={fomc:3,cpi:3,jobs:3,pce:3,gdp:2,ppi:2};
var MON=["January","February","March","April","May","June","July","August","September","October","November","December"];
var showPast=false, keyOnly=false;
try{keyOnly=localStorage.getItem("cal-key")==="1"}catch(e){}
function parts(ms,tz){var o={};new Intl.DateTimeFormat("en-US",{timeZone:tz,hourCycle:"h23",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"}).formatToParts(new Date(ms)).forEach(function(p){o[p.type]=p.value});
 return {d:o.year+"-"+o.month+"-"+o.day,t:(o.hour==="24"?"00":o.hour)+":"+o.minute}}
function etMs(d,t){var a=d.split("-").map(Number),b=t.split(":").map(Number),w=Date.UTC(a[0],a[1]-1,a[2],b[0],b[1]),u=w;
 for(var i=0;i<3;i++){var p=parts(u,"America/New_York"),x=p.d.split("-").map(Number),y=p.t.split(":").map(Number);u+=w-Date.UTC(x[0],x[1]-1,x[2],y[0],y[1])}return u}
function addDays(d,n){var a=d.split("-").map(Number),x=new Date(Date.UTC(a[0],a[1]-1,a[2]+n));return x.toISOString().slice(0,10)}
function dow(d){var a=d.split("-").map(Number);return new Date(Date.UTC(a[0],a[1]-1,a[2])).getUTCDay()}
function f(s,o){return s.replace(/\{(\w+)\}/g,function(_,k){return o[k]})}
function md(L,d){var a=d.split("-").map(Number);return f(T[L].md,{m:a[1],d:a[2],M:MON[a[1]-1].slice(0,3)})}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]})}
var TODAY=parts(Date.now(),"America/New_York").d;
function name(L,e){var t=T[L],n=t.k[e.kind],a;
 if((e.kind==="cpi"||e.kind==="jobs"||e.kind==="ppi"||e.kind==="pce")&&e.ref){a=e.ref.split("-").map(Number);n+=f(t.ref,{m:a[1],M:MON[a[1]-1]})}
 else if(e.kind==="gdp"&&e.ref){n+=f(t.q,{y:e.ref.slice(0,4),q:e.ref.slice(5),e:t.est[e.est]||""})}
 else if(e.kind==="closed"&&e.name){n+=(L==="en"?": ":"：")+(t.hol[e.name]||e.name)}
 return n}
function why(L,e){var w=T[L].w;if(e.kind==="fomc")return (e.sep?w.fomcSep:w.fomc);if(e.kind==="gdp"&&e.est==="adv")return w.gdpAdv;return w[e.kind]||""}
function when(L,e){var t=T[L];
 if(!e.time)return "<b>"+t.allday+"</b>";
 var ms=etMs(e.date,e.time),bj=parts(ms,"Asia/Shanghai"),rel=bj.d>e.date?t.next+" ":bj.d<e.date?t.prev+" ":"";
 var lead=e.kind==="early"?t.earlyT+" ":"";
 var o=L==="en"?"(":"（",c=L==="en"?")":"）";
 return "<b>"+lead+e.time+" ET</b> <span>"+o+t.bj+" "+rel+bj.t+c+"</span>"}
function row(L,e){var t=T[L],cls="cal-ev k-"+e.kind+(e.date<TODAY?" past":"")+(e.date===TODAY?" today":""),k=KEYK[e.kind]||0;
 var sub=[];if(e.kind==="fomc"){var s=e.start.split("-").map(Number),x=e.date.split("-").map(Number);sub.push(f(t.meet,{a:s[2],b:x[2]}));if(e.sep)sub.push(t.sep)}
 var wd=T[L].wd.split(",")[dow(e.date)];
 return '<div class="'+cls+'"><div class="cal-d">'+md(L,e.date)+'<small>'+(e.date===TODAY?t.today+" · ":"")+wd+'</small></div><div>'
  +'<div class="cal-n">'+((e.kind==="closed"||e.kind==="early")?'<span class="cal-tag">'+(e.kind==="closed"?"✕":"½")+'</span>':"")+esc(name(L,e))+(k?'<span class="dots" aria-label="'+k+'/3">'+"●●●".slice(0,k)+'</span>':"")+'</div>'
  +'<div class="cal-t">'+when(L,e)+(sub.length?' <span>· '+esc(sub.join(" · "))+'</span>':"")+'</div>'
  +'<p class="cal-w">'+esc(why(L,e))+'</p></div></div>'}
function monday(d){return addDays(d,-((dow(d)+6)%7))}
function render(L){L=L||"zh";var t=T[L],box=document.getElementById("cal-list");if(!box)return;
 document.getElementById("cal-past").textContent=showPast?t.hidePast:t.past;
 document.getElementById("cal-past").setAttribute("aria-pressed",String(showPast));
 document.getElementById("cal-key").textContent=t.key;document.getElementById("cal-key").setAttribute("aria-pressed",String(keyOnly));
 var thisWk=monday(TODAY),from=showPast?"0000":thisWk,ev=D.events.filter(function(e){return e.date>=from&&(!keyOnly||KEYK[e.kind]===3||e.kind==="closed"||e.kind==="early")});
 var weeks={},order=[];ev.forEach(function(e){var w=monday(e.date);if(!weeks[w]){weeks[w]=[];order.push(w)}weeks[w].push(e)});
 if(order.indexOf(thisWk)<0){order.push(thisWk);order.sort();weeks[thisWk]=[]}
 box.innerHTML=order.map(function(w){var now=w===thisWk,h=f(t.range,{a:md(L,w),b:md(L,addDays(w,6))});
  return '<section class="cal-wk'+(now?" now":"")+'"><h2>'+(now?t.week+" <small>"+h+"</small>":h)+'</h2>'
   +(weeks[w].length?weeks[w].map(function(e){return row(L,e)}).join(""):'<p class="cal-empty">'+t.nothing+'</p>')+'</section>'}).join("");
 var s=D.sources||{};document.getElementById("cal-src").innerHTML='<h2>'+t.srcH+'</h2><p>'+t.srcP+'</p><ul>'+Object.keys(SRC).map(function(k){var x=s[k]||{},nm=SRC[k][L==="en"?0:L==="zh"?1:2];
  return '<li>'+(x.url?'<a href="'+esc(x.url)+'" rel="noopener" target="_blank">'+esc(nm)+'</a>':esc(nm))+' — '+(x.ok?t.upd+" "+x.ok:t.wait)+'</li>'}).join("")+'</ul>';
}
document.getElementById("cal-past").addEventListener("click",function(){showPast=!showPast;render(window.PAGE_LANG)});
document.getElementById("cal-key").addEventListener("click",function(){keyOnly=!keyOnly;try{localStorage.setItem("cal-key",keyOnly?"1":"0")}catch(e){}render(window.PAGE_LANG)});
window.onPageLang=render;render(window.PAGE_LANG||"zh");
})();
</script>"""

def build(out, page):
    if not os.path.exists(DATA): return None
    data = json.load(open(DATA, encoding="utf-8"))
    os.makedirs(f"{out}/calendar", exist_ok=True)
    with open(f"{out}/calendar/macro.json", "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    hero = "".join(f'<div data-l="{l}" lang="{LOC[l]}"><p class="crumb"><a href="/market/">{T[l]["back"]}</a></p><h1>{T[l]["title"]}</h1><p>{T[l]["intro"]}</p></div>' for l in LANGS)
    body = (f'<main><div class="cal-hero">{hero}</div>'
            '<div class="cal-bar"><button type="button" id="cal-key" aria-pressed="false"></button><button type="button" id="cal-past" aria-pressed="false"></button></div>'
            '<div id="cal-list"></div><div class="cal-src" id="cal-src"></div></main>'
            f'<style>{CSS}</style>')
    js = (JS.replace("__T__", json.dumps(T, ensure_ascii=False)).replace("__D__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
          .replace("__SRC__", json.dumps(SRC, ensure_ascii=False)))
    titles = {l: f'{T[l]["title"]} · April\'s Stock Atlas' for l in LANGS}
    open(f"{out}/calendar/index.html", "w", encoding="utf-8").write(page("calendar/", titles, T["zh"]["intro"], body, js))
    return "calendar/"
