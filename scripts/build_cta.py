"""Market watch chart study: CTA (trend-following) position vs the S&P 500, at /market/cta/.

Data: charts/cta.json, exported from the options research project (april-options, scripts/cta_chart_page.py
--site) and committed here; the daily workflow only rebuilds the page from it. Keys:
  rows    [[date, SPY close, position, trend, size, s_1m, s_3m, s_12m], ...]  weekly, then daily for ~2 years
  bottoms [{date, dd, pos_at, pmin_date, pmin, lag}]   SPY bottoms after 10%+ falls and the CTA low in each
  scen    [[SPX close, position, change, s_1m, s_3m, s_12m, size], ...]   "if the next close is X"
  now     {date, close, pos, trend, size, rv, flow20, pctl, s[3], flip[3]}  SPX, last official close
Standard library only (the daily workflow runs plain python3 -I).

    build(out, page) -> "market/cta/" or None when there is no data file
"""
import os, json, html

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "charts", "cta.json")
LANGS = ("zh", "tw", "en")
LOC = {"zh": "zh-CN", "tw": "zh-TW", "en": "en"}

TXT = {
    "zh": {
        "title": "CTA 仓位与标普 500",
        "card": "趋势跟踪基金（CTA）的股票仓位是怎么算出来的，它和标普 500 的底部有没有关系。附 2001 年以来的图和历史检验。",
        "back": "← 市场观察", "asof": "数据截至",
        "sub": "大跌时常听到“CTA 被动卖出”。这里按公开规则复刻 CTA 的股票仓位，和 SPY 放在同一条时间轴上，看它在历史上能说明什么、不能说明什么。",
        "chartNote": "仓位 1.0 = 正常波动下的满仓多头；波动越大，同样的趋势对应的仓位越小。紫色虚线是 SPY 跌 10% 以上那几段的价格底部，紫点是同一段里 CTA 仓位最低的那天。2 年以前按周显示，最近 2 年按日显示。",
        "nowH": "现在的模型读数",
        "scenH": "下一交易日收在不同价位，仓位会怎样",
        "scenP": "“变化”为负表示模型还要再卖，为正表示买回。",
        "botH": "价格底部和 CTA 仓位最低点",
        "botP": "“相差”是从仓位最低那天到价格底部隔了多少个交易日；负数表示仓位最低出现在价格底部之后。",
        "howH": "怎么算",
        "how": ["CTA 是按规则做趋势跟踪的基金。银行（例如高盛）会估算它们的仓位，但模型不公开，所以这里用的是业内和学术研究中通用的做法，数字会和银行报告不同。",
                "<b>趋势：</b>分别看 1 个月、3 个月、12 个月的涨跌幅，除以这段时间的正常波动，结果截断在 −1 到 +1 之间，三个取平均。",
                "<b>规模：</b>按波动目标调整，规模 = 15% ÷ 实际波动，最多 1.5 倍。波动越大，仓位越小，这就是大跌时它们被迫卖出的原因。",
                "<b>仓位</b> = 趋势 × 规模。<b>翻转价</b>：价格跌破（或涨回）某个周期起点的价格时，这个周期的信号就会换方向。"],
        "testH": "历史检验（SPY，2001 年至今）",
        "test": ["<b>大幅减仓之后：</b>20 天内减仓幅度在历史最大的 3%（29 次），之后一周中位数 +1.1%，平常是 +0.3%。但和“20 天跌幅相同”的日子比，只有这一种算法多出约 1 个百分点，一个月后就消失了，换一种信号算法也没有。",
                 "<b>由空转为回补：</b>31 次。2001–2012 年之后的表现比平常差，2013–2026 年比平常好，两段方向相反。",
                 "<b>仓位最低和价格底部：</b>10 次 10% 以上的回撤里，仓位最低点比价格底部早 284 天到晚 41 天都有，只有 2018 年 12 月是同一天。",
                 "<b>结论：</b>这个仓位能解释为什么某几天跌得特别急（规则驱动的卖盘），但不能用来判断底部。"],
        "fine": "公开数据的研究汇总，不构成投资建议。价格来自每日收盘数据。",
        "ui": {"ranges": ["全部", "10 年", "5 年", "2 年", "6 个月"], "price": "SPY（对数）", "posAx": "CTA 仓位",
               "long": "偏多", "short": "偏空", "mark": "价格底部 / 仓位最低", "pos": "仓位", "bottom": "价格底部，回撤",
               "s": ["短", "中", "长"], "size": "规模", "names": ["短期 1 个月", "中期 3 个月", "长期 12 个月"],
               "statPos": "仓位", "pctl": "历史第 {p} 百分位", "statFlow": "20 天内变化", "statRv": "实际波动",
               "rvN": "规模 = 15% ÷ 波动", "flip": "翻转价", "trendN": "趋势 {t} × 规模 {s}",
               "scenCols": ["SPX 收盘", "仓位", "变化", "短", "中", "长", "规模"],
               "botCols": ["价格底部", "回撤", "当时仓位", "仓位最低日", "最低", "相差"],
               "scenSum": "再跌到 {lo}，仓位只再变 {d}：趋势更空，但波动上升让规模变小，两者大致抵消。{up}",
               "scenUp": "要涨到 {p} 左右，仓位才回到 0。", "scenUpNo": "表中价位内仓位都还在 0 以下。",
               "spx": "SPX {d} 收盘 {c}"}},
    "tw": {
        "title": "CTA 部位與標普 500",
        "card": "趨勢跟蹤基金（CTA）的股票部位是怎麼算出來的，它和標普 500 的底部有沒有關係。附 2001 年以來的圖和歷史檢驗。",
        "back": "← 市場觀察", "asof": "資料截至",
        "sub": "大跌時常聽到「CTA 被動賣出」。這裡按公開規則複製 CTA 的股票部位，和 SPY 放在同一條時間軸上，看它在歷史上能說明什麼、不能說明什麼。",
        "chartNote": "部位 1.0 = 正常波動下的滿倉多頭；波動越大，同樣的趨勢對應的部位越小。紫色虛線是 SPY 跌 10% 以上那幾段的價格底部，紫點是同一段裡 CTA 部位最低的那天。2 年以前按週顯示，最近 2 年按日顯示。",
        "nowH": "現在的模型讀數",
        "scenH": "下一交易日收在不同價位，部位會怎樣",
        "scenP": "「變化」為負表示模型還要再賣，為正表示買回。",
        "botH": "價格底部和 CTA 部位最低點",
        "botP": "「相差」是從部位最低那天到價格底部隔了多少個交易日；負數表示部位最低出現在價格底部之後。",
        "howH": "怎麼算",
        "how": ["CTA 是按規則做趨勢跟蹤的基金。銀行（例如高盛）會估算它們的部位，但模型不公開，所以這裡用的是業內和學術研究中通用的做法，數字會和銀行報告不同。",
                "<b>趨勢：</b>分別看 1 個月、3 個月、12 個月的漲跌幅，除以這段時間的正常波動，結果截斷在 −1 到 +1 之間，三個取平均。",
                "<b>規模：</b>按波動目標調整，規模 = 15% ÷ 實際波動，最多 1.5 倍。波動越大，部位越小，這就是大跌時它們被迫賣出的原因。",
                "<b>部位</b> = 趨勢 × 規模。<b>翻轉價</b>：價格跌破（或漲回）某個週期起點的價格時，這個週期的訊號就會換方向。"],
        "testH": "歷史檢驗（SPY，2001 年至今）",
        "test": ["<b>大幅減倉之後：</b>20 天內減倉幅度在歷史最大的 3%（29 次），之後一週中位數 +1.1%，平常是 +0.3%。但和「20 天跌幅相同」的日子比，只有這一種算法多出約 1 個百分點，一個月後就消失了，換一種訊號算法也沒有。",
                 "<b>由空轉為回補：</b>31 次。2001–2012 年之後的表現比平常差，2013–2026 年比平常好，兩段方向相反。",
                 "<b>部位最低和價格底部：</b>10 次 10% 以上的回撤裡，部位最低點比價格底部早 284 天到晚 41 天都有，只有 2018 年 12 月是同一天。",
                 "<b>結論：</b>這個部位能解釋為什麼某幾天跌得特別急（規則驅動的賣盤），但不能用來判斷底部。"],
        "fine": "公開資料的研究彙總，不構成投資建議。價格來自每日收盤資料。",
        "ui": {"ranges": ["全部", "10 年", "5 年", "2 年", "6 個月"], "price": "SPY（對數）", "posAx": "CTA 部位",
               "long": "偏多", "short": "偏空", "mark": "價格底部 / 部位最低", "pos": "部位", "bottom": "價格底部，回撤",
               "s": ["短", "中", "長"], "size": "規模", "names": ["短期 1 個月", "中期 3 個月", "長期 12 個月"],
               "statPos": "部位", "pctl": "歷史第 {p} 百分位", "statFlow": "20 天內變化", "statRv": "實際波動",
               "rvN": "規模 = 15% ÷ 波動", "flip": "翻轉價", "trendN": "趨勢 {t} × 規模 {s}",
               "scenCols": ["SPX 收盤", "部位", "變化", "短", "中", "長", "規模"],
               "botCols": ["價格底部", "回撤", "當時部位", "部位最低日", "最低", "相差"],
               "scenSum": "再跌到 {lo}，部位只再變 {d}：趨勢更空，但波動上升讓規模變小，兩者大致抵消。{up}",
               "scenUp": "要漲到 {p} 左右，部位才回到 0。", "scenUpNo": "表中價位內部位都還在 0 以下。",
               "spx": "SPX {d} 收盤 {c}"}},
    "en": {
        "title": "CTA positioning and the S&P 500",
        "card": "How trend-following funds' (CTAs') stock exposure is estimated, and whether it lines up with S&P 500 bottoms. Chart since 2001 and a history test.",
        "back": "← Market watch", "asof": "Data as of",
        "sub": "In sharp sell-offs you often hear about \"forced CTA selling\". This page rebuilds CTA equity exposure from public rules and puts it on the same timeline as SPY, to show what it has and has not told us in the past.",
        "chartNote": "A position of 1.0 = fully long at normal volatility; the higher volatility is, the smaller the position for the same trend. Purple dashed lines are SPY bottoms after falls of 10% or more; purple dots are the day CTA exposure was lowest in that fall. Weekly before the last 2 years, daily after.",
        "nowH": "Current model reading",
        "scenH": "If the next session closes at…",
        "scenP": "A negative change means the model still sells; positive means it buys back.",
        "botH": "Price bottoms and CTA lows",
        "botP": "\"Gap\" is the number of trading days from the CTA low to the price bottom; negative means the CTA low came after the price bottom.",
        "howH": "How it is calculated",
        "how": ["CTAs are funds that follow trends by fixed rules. Banks such as Goldman Sachs estimate their positioning, but their models are not public, so this uses the standard approach from industry and academic work. Its numbers will differ from bank reports.",
                "<b>Trend:</b> the 1-, 3- and 12-month returns, each divided by normal volatility over that span and capped at −1 to +1, then averaged.",
                "<b>Size:</b> volatility targeting, size = 15% ÷ realized volatility, at most 1.5. Higher volatility means a smaller position, which is why these funds are forced to sell in sharp falls.",
                "<b>Position</b> = trend × size. <b>Flip level:</b> when the price falls below (or climbs back above) the price at the start of a lookback, that signal changes sign."],
        "testH": "History test (SPY, 2001 to now)",
        "test": ["<b>After heavy de-leveraging:</b> the largest 3% of 20-day cuts (29 cases) were followed by a median +1.1% over a week, against +0.3% normally. Compared with days that had the same 20-day price fall, only this version of the model was about 1 point better, the edge was gone after a month, and it did not hold with a different signal rule.",
                 "<b>Turning from short to buying back:</b> 31 cases. Worse than usual afterwards in 2001–2012, better than usual in 2013–2026: opposite results in the two halves.",
                 "<b>CTA lows vs price bottoms:</b> in the 10 falls of 10% or more, the CTA low came anywhere from 284 trading days before the price bottom to 41 days after. Only December 2018 was the same day.",
                 "<b>Conclusion:</b> the position helps explain why some days fall so fast (rule-driven selling), but it does not mark bottoms."],
        "fine": "A research summary of public data, not investment advice. Prices are daily closes.",
        "ui": {"ranges": ["All", "10y", "5y", "2y", "6m"], "price": "SPY (log)", "posAx": "CTA position",
               "long": "Long", "short": "Short", "mark": "Price bottom / CTA low", "pos": "Position", "bottom": "Price bottom, fall",
               "s": ["1m", "3m", "12m"], "size": "size", "names": ["Short term, 1 month", "Medium term, 3 months", "Long term, 12 months"],
               "statPos": "Position", "pctl": "{p}th percentile of history", "statFlow": "Change over 20 days", "statRv": "Realized volatility",
               "rvN": "size = 15% ÷ volatility", "flip": "Flip level", "trendN": "trend {t} × size {s}",
               "scenCols": ["SPX close", "Position", "Change", "1m", "3m", "12m", "Size"],
               "botCols": ["Price bottom", "Fall", "Position then", "CTA low on", "Low", "Gap"],
               "scenSum": "A further fall to {lo} changes the position by only {d}: the trend gets more negative, but rising volatility shrinks the size, and the two roughly cancel. {up}",
               "scenUp": "The position only gets back to 0 around {p}.", "scenUpNo": "Within this table the position stays below 0.",
               "spx": "SPX close on {d}: {c}"}},
}

CSS = """
.cta-chart{background:var(--surface);border:1px solid var(--line);border-radius:18px;box-shadow:var(--shadow);padding:16px;margin:0 0 10px;min-width:0}
.cta-bar{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between;margin-bottom:8px}
.cta-btns{display:flex;gap:6px;flex-wrap:wrap}
.cta-btns button{font-size:13.5px;padding:3px 12px;border-radius:999px;border:1px solid var(--line);background:transparent;color:var(--muted);cursor:pointer}
.cta-btns button[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.cta-leg{display:flex;flex-wrap:wrap;gap:14px;font-size:13px;color:var(--muted)}
.cta-leg i{display:inline-block;width:12px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
#cta-plot{position:relative}#cta-plot svg{display:block;width:100%}
#cta-plot svg text{font-size:11px;fill:var(--faint);font-variant-numeric:tabular-nums}
#cta-tip{position:absolute;pointer-events:none;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:8px 10px;font-size:13px;line-height:1.5;box-shadow:var(--shadow);min-width:170px}
.cta-note{font-size:13.5px;color:var(--faint);margin:0 0 34px;max-width:80ch}
.cta-sec{margin:0 0 34px}.cta-sec>h2{border:0;padding:0;margin:0 0 6px}.cta-sec>p.lead{color:var(--muted);margin:0 0 14px;font-size:15px;max-width:72ch}
.cta-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
@media (max-width:760px){.cta-stats{grid-template-columns:repeat(2,minmax(0,1fr))}}
.cta-stat{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:12px 14px;min-width:0}
.cta-stat .k{font-size:13px;color:var(--muted);font-weight:600}.cta-stat .v{font:700 24px/1.2 var(--display);font-variant-numeric:tabular-nums}
.cta-stat .n{font-size:12.5px;color:var(--faint)}
.cta-two{display:grid;grid-template-columns:1fr 1fr;gap:24px}@media (max-width:860px){.cta-two{grid-template-columns:1fr}}
.cta-two>div{min-width:0}
.cta-tbl td,.cta-tbl th{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums;padding:6px 10px}
.cta-tbl td:first-child,.cta-tbl th:first-child{text-align:left}
.cta-tbl td{font-weight:400}.cta-tbl td:first-child{font-weight:600}
.cta-sum{font-size:14px;color:var(--muted);margin:0 0 12px}
.cta-text{max-width:76ch}.cta-text p,.cta-text li{color:var(--ink)}
.c-long{color:var(--accent)}.c-short{color:var(--t2)}
:root{--mark:#7c4dcc}@media (prefers-color-scheme:dark){:root{--mark:#b39af0}}
"""

JS = r"""<script>
(function(){
var J=__DATA__,T=__UI__;
var D=J.rows.map(function(r){return{d:r[0],t:Date.parse(r[0]),c:r[1],p:r[2],tr:r[3],sz:r[4],s:[r[5],r[6],r[7]]}});
var YRS=[0,10,5,2,0.5],range=0,NS="http://www.w3.org/2000/svg";
function css(n){return getComputedStyle(document.documentElement).getPropertyValue(n).trim()}
function f(v,d){d=d==null?2:d;return(v>0?"+":v<0?"−":"")+Math.abs(v).toFixed(d)}
function el(tag,a,p){var e=document.createElementNS(NS,tag);for(var k in a)e.setAttribute(k,a[k]);if(p)p.appendChild(e);return e}
function L(){return T[window.PAGE_LANG||"zh"]}
function sub(s,o){return s.replace(/\{(\w+)\}/g,function(_,k){return o[k]})}
function btns(){var u=L(),b=document.getElementById("cta-btns");b.innerHTML="";
 u.ranges.forEach(function(lab,i){var x=document.createElement("button");x.type="button";x.textContent=lab;x.setAttribute("aria-pressed",String(YRS[i]===range));
  x.onclick=function(){range=YRS[i];btns();draw()};b.appendChild(x)});
 document.getElementById("cta-leg").innerHTML='<span><i style="background:var(--ink)"></i>'+u.price+'</span><span><i style="background:var(--accent)"></i>'+u.long+'</span><span><i style="background:var(--t2)"></i>'+u.short+'</span><span><i style="background:var(--mark)"></i>'+u.mark+'</span>'}
function draw(){var u=L(),svg=document.getElementById("cta-svg");svg.innerHTML="";
 var W=document.getElementById("cta-plot").clientWidth;if(W<120){requestAnimationFrame(draw);return}var nar=W<560,Lm=40,R=8,Tm=22,H1=nar?190:270,G=18,H2=nar?120:160,B=22,H=Tm+H1+G+H2+B;
 svg.setAttribute("viewBox","0 0 "+W+" "+H);svg.setAttribute("height",H);
 var end=D[D.length-1].t,start=range?end-range*365.25*864e5:D[0].t,v=D.filter(function(a){return a.t>=start});
 function x(t){return Lm+(t-start)/(end-start)*(W-Lm-R)}
 var lo=Math.min.apply(null,v.map(function(a){return a.c})),hi=Math.max.apply(null,v.map(function(a){return a.c}));
 var ly=Math.log(lo*.97),hy=Math.log(hi*1.03);function y1(c){return Tm+(hy-Math.log(c))/(hy-ly)*H1}
 var y0=Tm+H1+G,PM=1.5;function y2(p){return y0+(PM-p)/(2*PM)*H2}
 var line=css("--line"),faint=css("--faint"),mark=css("--mark");
 var st=range&&range<=2?[1,1.5,2,3,4,5,6,7,8]:[1,2,5],ticks=[];for(var p=10;p<=1e4;p*=10)st.forEach(function(s){var c=s*p;if(c>=lo*.97&&c<=hi*1.03)ticks.push(c)});
 while(ticks.length>6)ticks=ticks.filter(function(_,i){return i%2===0});
 if(ticks.length<3){ticks=[];for(var i=0;i<4;i++)ticks.push(Math.round(lo+(hi-lo)*(i+.5)/4))}
 ticks.forEach(function(c){el("line",{x1:Lm,x2:W-R,y1:y1(c),y2:y1(c),stroke:line},svg);el("text",{x:Lm-6,y:y1(c)+4,"text-anchor":"end"},svg).textContent=c});
 [-1,-.5,0,.5,1].forEach(function(p){el("line",{x1:Lm,x2:W-R,y1:y2(p),y2:y2(p),stroke:p===0?faint:line},svg);el("text",{x:Lm-6,y:y2(p)+4,"text-anchor":"end"},svg).textContent=(p>0?"+":"")+p});
 el("text",{x:Lm,y:Tm-8},svg).textContent="SPY";el("text",{x:Lm,y:y0-4},svg).textContent=u.posAx;
 if(range&&range<1){var m=new Date(start);m.setDate(1);for(;m.getTime()<=end;m.setMonth(m.getMonth()+1)){var t=m.getTime();if(t<start)continue;el("text",{x:x(t),y:H-6,"text-anchor":"middle"},svg).textContent=(m.getFullYear()%100)+"/"+(m.getMonth()+1)}}
 else{var a0=new Date(start).getFullYear()+1,a1=new Date(end).getFullYear(),ev=a1-a0>16?4:a1-a0>8?2:1;
  for(var yr=a0;yr<=a1;yr++)if((yr-a0)%ev===0){var t2=Date.UTC(yr,0,1);el("line",{x1:x(t2),x2:x(t2),y1:Tm+H1,y2:Tm+H1+4,stroke:faint},svg);el("text",{x:x(t2),y:H-6,"text-anchor":"middle"},svg).textContent=yr}}
 var last=-99;J.bottoms.forEach(function(b){var t=Date.parse(b.date);if(t<start)return;
  el("line",{x1:x(t),x2:x(t),y1:Tm,y2:y0+H2,stroke:mark,"stroke-dasharray":"3 3","stroke-opacity":.7},svg);
  if(x(t)-last>34){el("text",{x:x(t),y:Tm-8,"text-anchor":"middle",style:"fill:"+mark},svg).textContent=b.date.slice(0,4);last=x(t)}});
 function area(sg){var d="M"+x(v[0].t)+","+y2(0);v.forEach(function(a){d+="L"+x(a.t).toFixed(1)+","+y2(sg>0?Math.max(a.p,0):Math.min(a.p,0)).toFixed(1)});return d+"L"+x(v[v.length-1].t)+","+y2(0)+"Z"}
 el("path",{d:area(1),fill:css("--accent"),"fill-opacity":.5},svg);el("path",{d:area(-1),fill:css("--t2"),"fill-opacity":.65},svg);
 el("path",{d:v.map(function(a,i){return(i?"L":"M")+x(a.t).toFixed(1)+","+y1(a.c).toFixed(1)}).join(""),fill:"none",stroke:css("--ink"),"stroke-width":1.5,"stroke-linejoin":"round"},svg);
 J.bottoms.forEach(function(b){var t=Date.parse(b.pmin_date);if(t<start)return;el("circle",{cx:x(t),cy:y2(b.pmin),r:4,fill:mark,stroke:css("--surface"),"stroke-width":2},svg)});
 var g=el("g",{style:"display:none"},svg),vl=el("line",{y1:Tm,y2:y0+H2,stroke:faint},g),c1=el("circle",{r:4,fill:css("--ink"),stroke:css("--surface"),"stroke-width":2},g),c2=el("circle",{r:4,stroke:css("--surface"),"stroke-width":2},g);
 var hit=el("rect",{x:Lm,y:Tm,width:W-Lm-R,height:y0+H2-Tm,fill:"transparent"},svg),tip=document.getElementById("cta-tip");
 function mv(e){var r=svg.getBoundingClientRect(),mx=(e.touches?e.touches[0].clientX:e.clientX)-r.left,t=start+(mx-Lm)/(W-Lm-R)*(end-start),i=0,j=v.length-1;
  while(j-i>1){var k=(i+j)>>1;if(v[k].t<t)i=k;else j=k}var a=Math.abs(v[i].t-t)<Math.abs(v[j].t-t)?v[i]:v[j];
  g.style.display="";vl.setAttribute("x1",x(a.t));vl.setAttribute("x2",x(a.t));c1.setAttribute("cx",x(a.t));c1.setAttribute("cy",y1(a.c));
  c2.setAttribute("cx",x(a.t));c2.setAttribute("cy",y2(a.p));c2.setAttribute("fill",a.p>=0?css("--accent"):css("--t2"));
  var bt=J.bottoms.filter(function(b){return Math.abs(Date.parse(b.date)-a.t)<4*864e5})[0];
  tip.innerHTML="<div>"+a.d+"</div><div>SPY <b>"+a.c.toFixed(2)+"</b></div><div>"+u.pos+' <b class="'+(a.p<0?"c-short":"c-long")+'">'+f(a.p)+"</b></div>"+
   '<div style="color:var(--faint);font-size:12px">'+u.s[0]+" "+f(a.s[0])+" · "+u.s[1]+" "+f(a.s[1])+" · "+u.s[2]+" "+f(a.s[2])+" · "+u.size+" "+a.sz.toFixed(2)+"</div>"+
   (bt?'<div style="color:var(--mark)">'+u.bottom+" "+bt.dd+"%</div>":"");
  tip.hidden=false;var tw=tip.offsetWidth,lf=x(a.t)+12;if(lf+tw>W)lf=x(a.t)-tw-12;tip.style.left=Math.max(0,lf)+"px";tip.style.top=(Tm+6)+"px"}
 hit.addEventListener("mousemove",mv);hit.addEventListener("touchmove",mv,{passive:true});hit.addEventListener("mouseleave",function(){g.style.display="none";tip.hidden=true})}
function tables(){var u=L(),N=J.now;
 document.getElementById("cta-spx").textContent=sub(u.spx,{d:N.date,c:N.close});
 var st='<div class="cta-stat"><div class="k">'+u.statPos+'</div><div class="v '+(N.pos<0?"c-short":"c-long")+'">'+f(N.pos)+'</div><div class="n">'+sub(u.pctl,{p:N.pctl})+'</div></div>'+
  '<div class="cta-stat"><div class="k">'+u.statFlow+'</div><div class="v">'+f(N.flow20)+'</div><div class="n">'+sub(u.trendN,{t:f(N.trend),s:N.size.toFixed(2)})+'</div></div>'+
  '<div class="cta-stat"><div class="k">'+u.statRv+'</div><div class="v">'+N.rv.toFixed(1)+'%</div><div class="n">'+u.rvN+'</div></div>'+
  u.names.map(function(n,i){return'<div class="cta-stat"><div class="k">'+n+'</div><div class="v '+(N.s[i]<0?"c-short":"c-long")+'">'+f(N.s[i])+'</div><div class="n">'+u.flip+" "+N.flip[i]+"</div></div>"}).join("");
 document.getElementById("cta-stats").innerHTML=st;
 var S=J.scen,lo=S[0],up=S.filter(function(r){return r[1]>=0})[0];
 document.getElementById("cta-sum").textContent=sub(u.scenSum,{lo:lo[0],d:f(lo[2]),up:up?sub(u.scenUp,{p:up[0]}):u.scenUpNo});
 document.getElementById("cta-scen").innerHTML="<thead><tr>"+u.scenCols.map(function(c){return"<th>"+c+"</th>"}).join("")+"</tr></thead><tbody>"+
  S.map(function(r){return"<tr><td>"+r[0]+"</td><td>"+f(r[1])+'</td><td class="'+(r[2]<0?"c-short":r[2]>0?"c-long":"")+'">'+f(r[2])+"</td><td>"+f(r[3])+"</td><td>"+f(r[4])+"</td><td>"+f(r[5])+"</td><td>"+r[6].toFixed(2)+"</td></tr>"}).join("")+"</tbody>";
 document.getElementById("cta-bot").innerHTML="<thead><tr>"+u.botCols.map(function(c){return"<th>"+c+"</th>"}).join("")+"</tr></thead><tbody>"+
  J.bottoms.map(function(b){return"<tr><td>"+b.date+"</td><td>"+b.dd+"%</td><td>"+f(b.pos_at)+"</td><td>"+b.pmin_date+"</td><td>"+f(b.pmin)+"</td><td>"+b.lag+"</td></tr>"}).join("")+"</tbody>"}
function all(){btns();draw();tables()}
window.onPageLang=function(){all()};all();
var rt;window.addEventListener("resize",function(){clearTimeout(rt);rt=setTimeout(draw,120)});
})();
</script>"""


def card(l):
    """(title, summary) for the Market watch page, or None without data."""
    return (TXT[l]["title"], TXT[l]["card"]) if os.path.exists(DATA) else None


def build(out, page):
    if not os.path.exists(DATA):
        return None
    data = json.load(open(DATA, encoding="utf-8"))
    asof = data["now"]["date"]
    blocks = []
    for l in LANGS:
        t = TXT[l]
        lis = lambda xs: "<ul>" + "".join(f"<li>{x}</li>" for x in xs) + "</ul>"
        blocks.append((
            f'<div data-l="{l}" lang="{LOC[l]}"><p class="crumb"><a href="/market/">{t["back"]}</a></p>'
            f'<p class="meta">{t["asof"]} {html.escape(asof)}</p><h1>{t["title"]}</h1><p class="sub">{t["sub"]}</p></div>',
            f'<p data-l="{l}" lang="{LOC[l]}" class="cta-note">{t["chartNote"]}</p>',
            f'<div data-l="{l}" lang="{LOC[l]}"><h2>{t["nowH"]}</h2></div>',
            f'<div data-l="{l}" lang="{LOC[l]}"><h2>{t["scenH"]}</h2><p class="lead">{t["scenP"]}</p></div>',
            f'<div data-l="{l}" lang="{LOC[l]}"><h2>{t["botH"]}</h2><p class="lead">{t["botP"]}</p></div>',
            f'<div data-l="{l}" lang="{LOC[l]}" class="cta-text"><h2>{t["howH"]}</h2>' + "".join(f"<p>{p}</p>" for p in t["how"]) +
            f'<h2>{t["testH"]}</h2>{lis(t["test"])}<p class="fine">{t["fine"]}</p></div>'))
    pick = lambda i: "".join(b[i] for b in blocks)
    body = (f'<main>{pick(0)}'
            f'<div class="cta-chart"><div class="cta-bar"><div class="cta-btns" id="cta-btns"></div><div class="cta-leg" id="cta-leg"></div></div>'
            f'<div id="cta-plot"><svg id="cta-svg" role="img" aria-label="SPY / CTA"></svg><div id="cta-tip" hidden></div></div></div>{pick(1)}'
            f'<section class="cta-sec">{pick(2)}<p class="cta-sum" id="cta-spx"></p><div class="cta-stats" id="cta-stats"></div></section>'
            f'<div class="cta-two"><section class="cta-sec">{pick(3)}<p class="cta-sum" id="cta-sum"></p><div class="tbl"><table class="cta-tbl" id="cta-scen"></table></div></section>'
            f'<section class="cta-sec">{pick(4)}<div class="tbl"><table class="cta-tbl" id="cta-bot"></table></div></section></div>'
            f'<section class="cta-sec">{pick(5)}</section></main><style>{CSS}</style>')
    js = JS.replace("__DATA__", json.dumps(data, separators=(",", ":"))).replace(
        "__UI__", json.dumps({l: TXT[l]["ui"] for l in LANGS}, ensure_ascii=False))
    titles = {l: f'{TXT[l]["title"]} · April\'s Stock Atlas' for l in LANGS}
    os.makedirs(f"{out}/market/cta", exist_ok=True)
    open(f"{out}/market/cta/index.html", "w", encoding="utf-8").write(page("market/cta/", titles, TXT["zh"]["card"], body, js))
    return "market/cta/"
