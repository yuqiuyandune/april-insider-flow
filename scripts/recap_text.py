"""Sentences and sections for the daily market recap (data/recaps/<date>.json, from scripts/recap.py).

Each rule key has one template per language. ZH and EN are written here; TW is generated from ZH with OpenCC (s2twp)
by scripts/make_recap_tw.py into recap_tw.py, so after changing a ZH template run that script once.

    sentences(r, l)  -> [(fact key, section, html sentence)] in weight order
    key_points(r, l) -> the "worth remembering" sentences
    sections(r, l)   -> HTML of the whole recap
"""
import datetime as dt, html, importlib.util, os

E = lambda s: html.escape(str(s))
MON = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

NAMES = {
    "zh": {"COMP": "纳斯达克", "SPY": "标普 500", "DIA": "道指", "IWM": "罗素 2000", "QQQ": "纳指 100", "SMH": "半导体", "SOXX": "费城半导体",
           "XLK": "科技", "XLC": "通讯", "XLY": "可选消费", "XLP": "必需消费", "XLE": "能源", "XLF": "金融", "XLV": "医疗", "XLI": "工业",
           "XLB": "材料", "XLRE": "地产", "XLU": "公用", "GLD": "黄金", "TLT": "长债", "IBIT": "比特币"},
    "en": {"COMP": "Nasdaq", "SPY": "S&P 500", "DIA": "Dow", "IWM": "Russell 2000", "QQQ": "Nasdaq 100", "SMH": "semis", "SOXX": "PHLX semis",
           "XLK": "tech", "XLC": "communications", "XLY": "discretionary", "XLP": "staples", "XLE": "energy", "XLF": "financials", "XLV": "health care",
           "XLI": "industrials", "XLB": "materials", "XLRE": "real estate", "XLU": "utilities", "GLD": "gold", "TLT": "long bonds", "IBIT": "bitcoin"},
}
WD = {"zh": "周一 周二 周三 周四 周五 周六 周日".split(), "en": "Mon Tue Wed Thu Fri Sat Sun".split()}

UI = {
    "zh": {"title": "每日盘后复盘", "key": "今天值得记住的", "index": "大盘", "sector": "板块", "volume": "成交量", "flows": "资金去向", "bonds": "债市",
           "chain": "AI 产业链", "notes": "导火索 · April 的笔记", "archive": "往日复盘", "table": "全部数据",
           "cols": ["", "收盘", "涨跌", "点数", "盘中最低", "收盘距最低", "离一年高点", "年内"], "vix": "VIX", "vixHigh": "盘中最高",
           "yields": "美债收益率", "bp": "个基点", "up": "涨得最多", "down": "跌得最多", "segs": "各环节平均", "trail": "最近四天的收盘位置和振幅",
           "pos": "收盘位置", "rng": "平均振幅", "x": "倍", "five": "最近五个交易日对比", "liq": "流动性视角", "liqP": "看谁的流动性在枯竭、谁在吸收成交、谁取得了控制权：放量却推不动价格，是有人在吸收；缩量却走得快，是对手盘稀薄、容易加速；跌破（或突破）20 日低点（高点）又收回，是流动性扫荡。这些只是反转的前提，要等收盘突破前 10 日的高点（或低点）才算控制权转移。只用日线数据，看不到逐笔成交和订单簿。", "liqCols": ["", "今天", "量比", "价格效率", "今天的信号", "近 5 日信号", "控制权"], "effNote": "价格效率 = 涨跌幅 ÷ 量比，和自己过去 60 天比的分位：越低越推不动，越高越容易走。", "tag": {"absorb": "放量推不动", "thin": "缩量走得快", "sweep_lo": "扫低点后收回", "sweep_hi": "扫高点后回落", "fade_down": "下跌越来越弱", "fade_up": "上涨越来越弱"}, "short": {"absorb": "吸收", "thin": "薄", "sweep_lo": "扫低", "sweep_hi": "扫高"}, "state": {"buyers": "买方确认", "sellers": "卖方确认", "watch_bottom": "底部信号 · 待确认", "watch_top": "顶部信号 · 待确认", "accel_down": "缩量加速下跌", "accel_up": "缩量加速上涨", "mixed": "信号混杂"}, "quiet": "其余没有流动性信号：{x}。", "fiveP": "每格上面是涨跌，下面是量比（当天成交量 ÷ 前 20 日平均）。右边是今天在这些 ETF 里的涨幅排名，箭头是和上个交易日比排名升降。", "rank": "排名", "note": "大盘行情：纳斯达克综合指数；标普 500、道指和罗素 2000 用 SPY、DIA、IWM 的涨跌代替。量比 = 当天成交量 ÷ 前 20 个交易日平均。"},
    "en": {"title": "Daily market recap", "key": "Worth remembering", "index": "The index", "sector": "Sectors", "volume": "Volume", "flows": "Where the money went",
           "bonds": "Bonds", "chain": "The AI supply chain", "notes": "Catalysts · April's notes", "archive": "Earlier recaps", "table": "All the numbers",
           "cols": ["", "Close", "Change", "Points", "Intraday low", "Close vs low", "From 1-yr high", "YTD"], "vix": "VIX", "vixHigh": "intraday high",
           "yields": "Treasury yields", "bp": "bp", "up": "Biggest gainers", "down": "Biggest losers", "segs": "Average by segment", "trail": "Close in range and range, last four sessions",
           "pos": "close in range", "rng": "average range", "x": "x", "five": "The last five sessions side by side", "liq": "Liquidity view", "liqP": "Whose liquidity is running out, who is absorbing trades, who holds control: heavy volume that barely moves price means someone is absorbing; light volume with a fast move means the other side is thin and price can speed up; breaking the 20-day low (or high) and closing back inside is a liquidity sweep. These are only preconditions for a reversal; control changes hands when a close clears the previous 10 sessions' high (or low). Daily data only: individual trades and the order book are not visible.", "liqCols": ["", "Today", "Rel. vol.", "Efficiency", "Today's signals", "Last 5 sessions", "Control"], "effNote": "Efficiency = the move ÷ relative volume, as a percentile of its own last 60 sessions: low means hard to move, high means it moves easily.", "tag": {"absorb": "heavy, no progress", "thin": "light, fast", "sweep_lo": "swept the low", "sweep_hi": "swept the high", "fade_down": "weaker pushes down", "fade_up": "weaker pushes up"}, "short": {"absorb": "abs", "thin": "thin", "sweep_lo": "sw↓", "sweep_hi": "sw↑"}, "state": {"buyers": "buyers confirmed", "sellers": "sellers confirmed", "watch_bottom": "bottom signal, unconfirmed", "watch_top": "top signal, unconfirmed", "accel_down": "fast on light volume, down", "accel_up": "fast on light volume, up", "mixed": "mixed signals"}, "quiet": "No liquidity signals for the rest: {x}.", "fiveP": "Each cell: the change on top, relative volume below (the day's volume ÷ the previous 20-day average). On the right, today's rank by change among these ETFs, with the move since the previous session.", "rank": "Rank", "note": "Index: the Nasdaq Composite; the S&P 500, the Dow and the Russell 2000 use the moves of SPY, DIA and IWM. Relative volume = the day's volume ÷ the average of the previous 20 sessions."},
}

ZH = {
    "never_back": "{name}全天最高 {high}，比昨天收盘的 {prev} 还低：从开盘到收盘，一刻都没有回到昨天的位置。",
    "never_below": "{name}全天最低 {low}，仍然高于昨天收盘的 {prev}：开盘就在昨收之上，全天没有一刻跌回去。",
    "open_high_close_low": "{name}开盘就是全天最高，一路往下，收在全天最低附近：不是冲高回落，也不是震荡下跌。",
    "flush_rebound": "真正的故事在盘中：{rows}。只看收盘价，几乎看不出今天发生了什么。",
    "flush_row": "{name}盘中最低跌 {low}，收盘 {chg}，从最低拉回 {off}",
    "flush_row_green": "{name}盘中最低跌 {low}，收盘翻红（{chg}），从最低拉回 {off}",
    "spike_fade": "{name}盘中一度涨 {high}，收盘却是 {chg}：冲高回落。",
    "two_day": "两天放在一起看：{yday}{name}{ymove}，今天{tmove}，一来一回{net}。",
    "move_up": "涨 {n} 点", "move_down": "跌 {n} 点", "net_up": "净涨 {n} 点", "net_down": "净跌 {n} 点",
    "best_day_up": "{name}今天涨 {chg}，是{since}以来最好的一天。", "best_day_down": "{name}今天跌 {chg}，是{since}以来最差的一天。",
    "since_month": " {y} 年 {m} 月", "since_long": "至少一年",
    "correction": "{name}收盘离一年高点 {dd}，进入技术性回调（跌超 10%）。", "bear": "{name}收盘离一年高点 {dd}，进入熊市（跌超 20%）。",
    "ytd_zero_down": "{name}今年以来的涨幅全部吐回，年内现在是 {ytd}。", "ytd_zero_up": "{name}年内重新转正（{ytd}）。",
    "streak_down": "标普 500（SPY）连续 {n} 个交易日下跌。", "streak_up": "标普 500（SPY）连续 {n} 个交易日上涨。",
    "vix": "VIX 收 {close}，{chg}。", "vix_spike": "VIX 收 {close}，{chg}；盘中最高 {high}，比昨天收盘高 {highChg}{tail}。", "vix_fade": "，一度进入恐慌区，收盘又回落",
    "reversal": "板块的排序和昨天几乎反过来：昨天领涨的是{yUp}，垫底的是{yDown}；今天领涨的是{tUp}，垫底的是{tDown}。昨天那套解释，今天不一定成立。",
    "few_green": "全场只有{green}是涨的。", "few_red": "全场只有{red}是跌的。",
    "semis_big": "半导体 ETF {t} 单日 {chg}{other}{sym}。", "semis_other": "（{t} {chg}）", "semis_sym": "，和{day}那根 {chg} 正好对称",
    "broad_down": "SPY 成交是平时的 {spy} 倍，主要 ETF 的中位数 {med} 倍：不是几只票被砸，是有人在成建制地减整个指数的仓位。",
    "broad_up": "SPY 成交是平时的 {spy} 倍，主要 ETF 的中位数 {med} 倍：资金在整体加仓指数，不只是几只票在涨。",
    "regime_up_down": "ETF 的量从前两天的 {before} 倍跳到今天的 {now} 倍：前几天是个股被精细地砸，今天是整个指数被无差别地卖。前者是选股，后者是降杠杆。",
    "regime_up_up": "ETF 的量从前两天的 {before} 倍跳到今天的 {now} 倍：前几天是个股行情，今天是资金在整体买指数。",
    "regime_down": "ETF 的量从前两天的 {before} 倍回落到今天的 {now} 倍，整体性的买卖告一段落。",
    "up_vs_down": "今天{bigger}，但 SPY 的量只有{dday}那天的 {ratio}（{up} 倍对 {down} 倍）。涨的量比跌的量小，说明主要是空头回补，而不是新的长线资金进场{fading}。",
    "bigger_yes": "涨得比{dday}跌得还多", "bigger_no": "涨了 {chg}", "fading": "，而且之后的反弹一次比一次轻",
    "heavy_on_down": "这几天 SPY 的量：{trail}。最大的量出现在下跌那天，之后的几天一次比一次轻。",
    "trail_item": "{day} {chg} {rvol} 倍",
    "amp_mismatch": "SPY 盘中振幅 {rng}，成交量却只有平时的 {rvol} 倍：这个量级配不上这个振幅。",
    "thin": "成交清淡，SPY 只有平时的 {rvol} 倍，这种日子任何方向的波动都不要过度解读。",
    "sell_everything": "黄金 {gld}、比特币 {ibit} 也在跌，只有{green}是涨的：典型的什么都卖，只留现金和国债。",
    "haven": "股票跌的时候，{havens}在涨：钱往避险资产跑。",
    "liquidity_back": "黄金也跟着涨了 {gld}：今天不是卖掉避险资产去追风险资产的轮动，而是整体流动性回来了。",
    "rotation_to_risk": "黄金 {gld}、长债 {tlt}：钱从避险资产流向股票。",
    "haven_top_volume_both": "全场成交量最大的是{top}：最恐慌的时候，钱是往黄金和长债跑的，不是往股票里跑的。",
    "haven_top_volume_one": "全场成交量最大的是{top}：有一部分钱在往避险资产跑。",
    "gold_wild": "黄金盘中摆了 {gld}，比标普的 {spy} 还大，成交是平时的 {rvol} 倍。",
    "still_up": "股票涨 {spy}，10 年期收益率却几乎不动（{d10} 个基点，{y10}%）：今天的上涨完全来自风险偏好，没有来自折现率的帮助。",
    "still_down": "股票跌 {spy}，10 年期收益率却几乎不动（{d10} 个基点，{y10}%）：今天的下跌和利率无关，是风险偏好在退。",
    "flight": "5 年期 {d5}、10 年期 {d10}、30 年期 {d30} 个基点，长债 TLT {tlt}，成交是平时的 {rvol} 倍：股票跌的时候，钱跑进了国债。",
    "big_move": "10 年期收益率变动 {d10} 个基点，到 {y10}%。",
    "summary": "AI 产业链 {n} 只：{up} 涨 {down} 跌，中位数 {median}。",
    "concentration_up": "涨幅集中在{lead}，{lag}只有 {lagavg}：这是围绕少数环节的重新定价，不是整条链一起被重估。",
    "concentration_down": "跌幅集中在{lead}，{lag}只有 {lagavg}：被砸的是少数环节，不是整条链。",
    "decoupled": "和全链方向相反的：{names}。",
    "all_one_way_up": "{k}/{n} 只全部上涨。", "all_one_way_down": "{k}/{n} 只全部下跌。",
    "seg_all_bear": "全链 {n} 只里有 {bear} 只已经进入熊市（离一年高点跌超 20%），{segs}{more}一只不剩。", "more": "等 {k} 个环节", "more3": "这几个环节",
    "sellers_done": "全链平均收在当日区间的 {pos}，平均振幅 {rng}，是平时的 {ampx} 倍，SPY 成交却只有 {spyRvol} 倍。收在高位、振幅极大、成交只有一倍出头，三件事放在一起，指向的是卖盘先走完了，不是买盘涌进来了。",
    "sold_into_close": "全链平均收在当日区间的 {pos}，平均振幅 {rng}：卖压一直持续到收盘。",
    "all_upper_half": "全链 {n} 只全部收在当日区间的上半区，平均收在 {pos}。",
    "new_high_low": "全链 {n} 只里，{hi} 只创一年新高，{lo} 只创一年新低。",
    "big_mover": "单日大幅波动：{names}。",
    "streak": "{t} 连续 {n} 个交易日下跌。",
    "absorb_down": "{names}放量下跌却跌不动：成交量很大，价格几乎没有往下走，主动卖盘可能正在被吸收。这是形成底部的前提之一，还不是反转信号。",
    "absorb_up": "{names}放量上涨却涨不动：大量买入没能有效推高价格，买盘可能正在被吸收。这是形成顶部的前提之一。",
    "thin_fast": "{names}缩量却走得很快：对手盘稀薄，价格容易沿原方向加速。",
    "sweep_lo": "{names}盘中跌破 20 日低点又收了回来：止损卖盘被触发后被承接，是典型的流动性扫荡。要等之后收盘站上近期高点，才算买方取得控制权。",
    "sweep_hi": "{names}盘中突破 20 日高点又跌了回去：假突破，追涨的买盘被吸收。",
    "confirmed_up": "{names}在出现底部信号之后，收盘站上了前 10 个交易日的最高点：买方取得控制权，底部得到确认。",
    "confirmed_down": "{names}在出现顶部信号之后，收盘跌破了前 10 个交易日的最低点：卖方取得控制权，顶部得到确认。",
    "chain_liq": "AI 产业链 {n} 只里，{sw} 只盘中跌破 20 日低点后收回{swl}，{ab} 只放量但价格推不动{abl}。{conf}",
    "chain_liq_eg": "（如 {x}）", "chain_conf_up": "买方已确认的：{x}。", "chain_conf_dn": "卖方已确认的：{x}。",
}
EN = {
    "never_back": "The {name}'s high of the day, {high}, was below yesterday's close of {prev}: it never got back to yesterday's level, not for a moment.",
    "never_below": "The {name}'s low of the day, {low}, was still above yesterday's close of {prev}: it opened above and never traded back below.",
    "open_high_close_low": "The {name} opened at its high and slid all day to close near its low: not a spike and fade, not a choppy decline.",
    "flush_rebound": "The real story was intraday: {rows}. The closing prices alone say almost nothing about today.",
    "flush_row": "the {name} fell as much as {low} and closed {chg}, {off} off the low",
    "flush_row_green": "the {name} fell as much as {low} and still closed higher ({chg}), {off} off the low",
    "spike_fade": "The {name} was up as much as {high} but closed {chg}: a spike and fade.",
    "two_day": "Put the two days together: {yday} the {name} {ymove}, today it {tmove}, a round trip that ends {net}.",
    "move_up": "gained {n} points", "move_down": "lost {n} points", "net_up": "{n} points higher", "net_down": "{n} points lower",
    "best_day_up": "The {name} rose {chg} today, its best day since {since}.", "best_day_down": "The {name} fell {chg} today, its worst day since {since}.",
    "since_month": "{M} {y}", "since_long": "at least a year",
    "correction": "The {name} closed {dd} from its one-year high: a technical correction (down more than 10%).",
    "bear": "The {name} closed {dd} from its one-year high: a bear market (down more than 20%).",
    "ytd_zero_down": "The {name} has given back all of this year's gain; year to date it is now {ytd}.", "ytd_zero_up": "The {name} is back above where it started the year ({ytd}).",
    "streak_down": "The S&P 500 (SPY) has fallen {n} sessions in a row.", "streak_up": "The S&P 500 (SPY) has risen {n} sessions in a row.",
    "vix": "The VIX closed at {close}, {chg}.", "vix_spike": "The VIX closed at {close}, {chg}; its intraday high was {high}, {highChg} above yesterday's close{tail}.", "vix_fade": ", in panic territory before easing into the close",
    "reversal": "Sector order nearly flipped from yesterday: yesterday {yUp} led and {yDown} lagged; today {tUp} led and {tDown} lagged. Yesterday's story may not hold today.",
    "few_green": "Only {green} rose.", "few_red": "Only {red} fell.",
    "semis_big": "The semiconductor ETF {t} moved {chg} in one day{other}{sym}.", "semis_other": " ({t} {chg})", "semis_sym": ", mirroring {day}'s {chg}",
    "broad_down": "SPY traded {spy}x its usual volume and the main ETFs a median {med}x: not a few stocks being hit, but whole-index positions being cut.",
    "broad_up": "SPY traded {spy}x its usual volume and the main ETFs a median {med}x: money buying the whole index, not just a few names.",
    "regime_up_down": "ETF volume jumped from {before}x in the previous two days to {now}x today: earlier it was single stocks being sold with care, today the whole index was sold indiscriminately. The first is stock picking, the second is deleveraging.",
    "regime_up_up": "ETF volume jumped from {before}x in the previous two days to {now}x today: from a stock pickers' market to money buying the whole index.",
    "regime_down": "ETF volume fell back from {before}x in the previous two days to {now}x: the index-wide buying and selling has paused.",
    "up_vs_down": "Today {bigger}, but SPY traded only {ratio} of {dday}'s volume ({up}x against {down}x). Lighter volume on the way up than on the way down points to short covering more than new long-term money{fading}.",
    "bigger_yes": "the market rose more than it fell on {dday}", "bigger_no": "the market rose {chg}", "fading": ", and each bounce has been lighter than the last",
    "heavy_on_down": "SPY volume these days: {trail}. The heaviest day was the down day, and every day since has been lighter.",
    "trail_item": "{day} {chg} {rvol}x",
    "amp_mismatch": "SPY's intraday range was {rng}, on only {rvol}x its usual volume: that volume does not match that range.",
    "thin": "Thin trading: SPY at {rvol}x its usual volume. Don't read too much into moves either way on days like this.",
    "sell_everything": "Gold {gld} and bitcoin {ibit} fell too; only {green} rose: the classic sell-everything day, keep only cash and Treasuries.",
    "haven": "As stocks fell, {havens} rose: money moved to safety.",
    "liquidity_back": "Gold rose too, {gld}: not a rotation out of safe havens into risk, but liquidity coming back across the board.",
    "rotation_to_risk": "Gold {gld}, long bonds {tlt}: money moved out of safe havens into stocks.",
    "haven_top_volume_both": "The heaviest volume of the day was in {top}: at the most fearful moment money ran to gold and long bonds, not into stocks.",
    "haven_top_volume_one": "The heaviest volume of the day was in {top}: some money was moving to safety.",
    "gold_wild": "Gold swung {gld} intraday, more than the S&P's {spy}, on {rvol}x its usual volume.",
    "still_up": "Stocks rose {spy} while the 10-year yield barely moved ({d10} bp, {y10}%): today's gain came from risk appetite, with no help from the discount rate.",
    "still_down": "Stocks fell {spy} while the 10-year yield barely moved ({d10} bp, {y10}%): the drop had nothing to do with rates; risk appetite pulled back.",
    "flight": "The 5-year moved {d5}, the 10-year {d10} and the 30-year {d30} bp; TLT {tlt} on {rvol}x its usual volume: as stocks fell, money went into Treasuries.",
    "big_move": "The 10-year yield moved {d10} bp to {y10}%.",
    "summary": "AI supply chain, {n} stocks: {up} up, {down} down, median {median}.",
    "concentration_up": "The gains were concentrated in {lead}; {lag} rose only {lagavg}: a repricing around a few links, not a re-rating of the whole chain.",
    "concentration_down": "The losses were concentrated in {lead}; {lag} moved only {lagavg}: a few links were hit, not the whole chain.",
    "decoupled": "Going against the chain: {names}.",
    "all_one_way_up": "{k} of {n} rose.", "all_one_way_down": "{k} of {n} fell.",
    "seg_all_bear": "{bear} of the chain's {n} stocks are in a bear market (more than 20% below their one-year high); in {segs}{more}, every single one is.", "more": " and {k} segments in all", "more3": "",
    "sellers_done": "The chain closed on average at {pos} of the day's range, with an average range of {rng}, {ampx}x normal, while SPY traded only {spyRvol}x its volume. A high close, a huge range and barely normal volume together point to sellers running out, not buyers rushing in.",
    "sold_into_close": "The chain closed on average at {pos} of the day's range, with an average range of {rng}: selling lasted into the close.",
    "all_upper_half": "All {n} stocks in the chain closed in the upper half of the day's range, at {pos} on average.",
    "new_high_low": "Of the chain's {n} stocks, {hi} made a one-year high and {lo} a one-year low.",
    "big_mover": "Big single-day moves: {names}.",
    "streak": "{t} has fallen {n} sessions in a row.",
    "absorb_down": "{names} fell on heavy volume but barely moved: a lot traded and price hardly went lower, so selling may be getting absorbed. A precondition for a bottom, not a reversal signal yet.",
    "absorb_up": "{names} rose on heavy volume but barely moved: heavy buying failed to lift price much, so buying may be getting absorbed. A precondition for a top.",
    "thin_fast": "{names} moved fast on light volume: the other side is thin, and price can speed up in the same direction.",
    "sweep_lo": "{names} broke the 20-day low intraday and closed back above it: stop-loss selling was triggered and absorbed, a classic liquidity sweep. Buyers take control only once a close clears the recent high.",
    "sweep_hi": "{names} broke the 20-day high intraday and fell back below it: a false breakout, with the chasing buyers absorbed.",
    "confirmed_up": "{names}, after a bottom signal, closed above the previous 10 sessions' high: buyers have taken control and the bottom is confirmed.",
    "confirmed_down": "{names}, after a top signal, closed below the previous 10 sessions' low: sellers have taken control and the top is confirmed.",
    "chain_liq": "Of the AI chain's {n} stocks, {sw} broke the 20-day low intraday and closed back above it{swl}, and {ab} traded heavily without moving much{abl}. {conf}",
    "chain_liq_eg": " (e.g. {x})", "chain_conf_up": "Buyers confirmed: {x}.", "chain_conf_dn": "Sellers confirmed: {x}.",
}

def _tw():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recap_tw.py")
    if not os.path.exists(p): return None
    spec = importlib.util.spec_from_file_location("recap_tw", p); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m
_TWM = _tw()
TPL = {"zh": ZH, "en": EN, "tw": (_TWM.TPL if _TWM else ZH)}
if _TWM:
    NAMES["tw"] = _TWM.NAMES; UI["tw"] = _TWM.UI; WD["tw"] = _TWM.WD
else:
    NAMES["tw"] = NAMES["zh"]; UI["tw"] = UI["zh"]; WD["tw"] = WD["zh"]

# ------------------------------------------------------------------ formatting
def pct(x, sign=True): return "–" if x is None else (f"{x:+.2f}%" if sign else f"{abs(x):.2f}%")
def pct1(x): return "–" if x is None else f"{x:.1f}%"
def num(x, d=2): return "–" if x is None else f"{x:,.{d}f}"
def bp(x): return "–" if x is None else f"{x:+.0f}"
def lst(xs, l): return ("、" if l != "en" else ", ").join(xs)
def nm(t, l): return NAMES[l].get(t, t)
def tnm(t, l):
    n = NAMES[l].get(t)
    return f"{n}（{t}）" if n and l != "en" else (f"{n} ({t})" if n else t)
def day_lbl(d, l):
    y, m, dd = map(int, d.split("-")); wd = WD[l][dt.date(y, m, dd).weekday()]
    return f"{wd}（{m}月{dd}日）" if l != "en" else f"{wd} {MON[m-1]} {dd}"
def short_day(d, l):
    y, m, dd = map(int, d.split("-")); return WD[l][dt.date(y, m, dd).weekday()]

def sentence(f, l, r):
    T = TPL[l]; p = f["p"]; k = f["k"]
    idxname = lambda t: nm(t, l) if t == "COMP" else tnm(t, l)
    if k == "never_back": return T[k].format(name=idxname(p["t"]), high=num(p["high"]), prev=num(p["prev"]))
    if k == "never_below": return T[k].format(name=idxname(p["t"]), low=num(p["low"]), prev=num(p["prev"]))
    if k == "open_high_close_low": return T[k].format(name=idxname(p["t"]))
    if k == "flush_rebound":
        rows = ("；" if l != "en" else "; ").join(T["flush_row_green" if x["chg"] > 0 else "flush_row"].format(
            name=idxname(x["t"]), low=pct(x["lowPct"], False), chg=pct(x["chg"]), off=pct(x["offLow"], False)) for x in p["rows"][:3])
        return T[k].format(rows=rows)
    if k == "spike_fade": return T[k].format(name=idxname(p["t"]), high=pct(p["highPct"]), chg=pct(p["chg"]))
    if k == "two_day":
        mv = lambda x: (T["move_up"] if x > 0 else T["move_down"]).format(n=f"{abs(x):,.0f}")
        net = (T["net_up"] if p["net"] > 0 else T["net_down"]).format(n=f"{abs(p['net']):,.0f}")
        return T[k].format(yday=short_day(p["yDay"], l), name=idxname(p["t"]), ymove=mv(p["yPts"]), tmove=mv(p["tPts"]), net=net)
    if k == "best_day":
        if p["since"]:
            y, m, _ = map(int, p["since"].split("-")); since = T["since_month"].format(y=y, m=m, M=MON[m - 1])
        else: since = T["since_long"]
        main = next(x for x in r["index"] if x["t"] == p["t"])
        return T["best_day_up" if p["up"] else "best_day_down"].format(name=idxname(p["t"]), chg=pct(main["chg"], False), since=since)
    if k in ("correction", "bear"): return T[k].format(name=idxname(p["t"]), dd=pct1(p["dd"]))
    if k == "ytd_zero": return T["ytd_zero_down" if p["down"] else "ytd_zero_up"].format(name=idxname(p["t"]), ytd=f"{p['ytd']:+.1f}%")
    if k == "streak" and f["sec"] == "index": return T["streak_down" if p["n"] < 0 else "streak_up"].format(n=abs(p["n"]))
    if k == "vix":
        tail = T["vix_fade"] if p["high"] >= 30 and p["close"] < p["high"] * 0.9 else ""
        spike = (p.get("highChg") or 0) >= 10
        return T["vix_spike" if spike else "vix"].format(close=num(p["close"]), chg=pct(p["chg"]), high=num(p["high"]), highChg=pct(p["highChg"], False), tail=tail)
    if k == "reversal":
        j = lambda xs: lst([tnm(x, l) for x in xs], l)
        return T[k].format(yUp=j(p["yUp"]), yDown=j(p["yDown"]), tUp=j(p["tUp"]), tDown=j(p["tDown"]))
    if k == "few_green": return T[k].format(green=lst([tnm(x, l) for x in p["green"]], l) or "–")
    if k == "few_red": return T[k].format(red=lst([tnm(x, l) for x in p["red"]], l) or "–")
    if k == "semis_big":
        oth = "SMH" if p["t"] == "SOXX" else "SOXX"
        other = T["semis_other"].format(t=oth, chg=pct(p["other"])) if p.get("other") is not None else ""
        sym = T["semis_sym"].format(day=short_day(p["sym"]["day"], l), chg=pct(p["sym"]["chg"])) if p.get("sym") else ""
        return T[k].format(t=p["t"], chg=pct(p["chg"]), other=other, sym=sym)
    if k == "broad": return T["broad_down" if p["down"] else "broad_up"].format(spy=num(p["spy"]), med=num(p["med"]))
    if k == "regime_up": return T["regime_up_down" if p["down"] else "regime_up_up"].format(before=num(p["before"]), now=num(p["now"]))
    if k == "regime_down": return T[k].format(before=num(p["before"]), now=num(p["now"]))
    if k == "up_vs_down":
        dd_ = short_day(p["downDay"], l)
        bigger = (T["bigger_yes"] if p["bigger"] else T["bigger_no"]).format(dday=dd_, chg=pct(p["upChg"], False))
        ratio = f"{p['ratio']*100:.0f}%" if l == "en" else (f"{p['ratio']:.0%}".replace("%", "%"))
        return T[k].format(bigger=bigger, dday=dd_, ratio=ratio, up=num(p["upRvol"]), down=num(p["downRvol"]), fading=T["fading"] if p["fading"] else "")
    if k == "heavy_on_down":
        tr = lst([T["trail_item"].format(day=short_day(x["d"], l), chg=pct(x["chg"]), rvol=num(x["rvol"])) for x in p["trail"]], l)
        return T[k].format(trail=tr)
    if k == "amp_mismatch": return T[k].format(rng=pct(p["rng"], False), rvol=num(p["rvol"]))
    if k == "thin": return T[k].format(rvol=num(p["rvol"]))
    if k == "sell_everything": return T[k].format(gld=pct(p["gld"]), ibit=pct(p["ibit"]), green=lst([tnm(x, l) for x in p["green"]], l) or "–")
    if k == "haven":
        hv = [tnm(t, l) for t, v in (("GLD", p.get("gld")), ("TLT", p.get("tlt"))) if v and v > 0]
        return T[k].format(havens=lst(hv, l))
    if k == "liquidity_back": return T[k].format(gld=pct(p["gld"], False))
    if k == "rotation_to_risk": return T[k].format(gld=pct(p["gld"]), tlt=pct(p["tlt"]))
    if k == "haven_top_volume":
        both = {x["t"] for x in p["top"]} >= {"GLD", "TLT"}
        top = lst([f'{tnm(x["t"], l)} {num(x["rvol"])}' + (f' {UI[l]["x"]}' if l != "en" else "x") for x in p["top"]], l)
        return T["haven_top_volume_both" if both else "haven_top_volume_one"].format(top=top)
    if k == "gold_wild": return T[k].format(gld=pct(p["gld"], False), spy=pct(p["spy"], False), rvol=num(p["rvol"]))
    if k == "still": return T["still_up" if p["spy"] > 0 else "still_down"].format(spy=pct(p["spy"], False), d10=bp(p["d10"]), y10=num(p["y10"]))
    if k == "flight": return T[k].format(d5=bp(p["d5"]), d10=bp(p["d10"]), d30=bp(p["d30"]), tlt=pct(p["tlt"]), rvol=num(p["tltRvol"]))
    if k == "big_move": return T[k].format(d10=bp(p["d10"]), y10=num(p["y10"]))
    segn = lambda sid: (r.get("segNames", {}).get(str(sid), {}) or {}).get(l, str(sid))
    if k == "summary": return T[k].format(n=p["n"], up=p["up"], down=p["down"], median=pct(p["median"]))
    if k == "concentration":
        lead = lst([f'{segn(x["seg"])}（{pct(x["avg"])}）' if l != "en" else f'{segn(x["seg"])} ({pct(x["avg"])})' for x in p["lead"]], l)
        return T["concentration_up" if p["up"] else "concentration_down"].format(lead=lead, lag=segn(p["lag"]["seg"]), lagavg=pct(p["lag"]["avg"]))
    if k == "decoupled": return T[k].format(names=lst([f'{x["t"]} {pct(x["chg"])}' for x in p["names"]], l))
    if k == "all_one_way": return T["all_one_way_up" if p["up"] else "all_one_way_down"].format(k=p["k"], n=p["n"])
    if k == "seg_all_bear":
        more = T["more"].format(k=len(p["segs"])) if len(p["segs"]) > 3 else T["more3"]
        return T[k].format(segs=lst([segn(s) for s in p["segs"][:3]], l), more=more, bear=p["bear"], n=p["n"])
    if k == "sellers_done": return T[k].format(pos=pct1(p["pos"]), rng=pct1(p["rng"]), ampx=num(p["ampx"], 1), spyRvol=num(p["spyRvol"]))
    if k == "sold_into_close": return T[k].format(pos=pct1(p["pos"]), rng=pct1(p["rng"]))
    if k == "all_upper_half": return T[k].format(n=p["n"], pos=pct1(p["pos"]))
    if k == "new_high_low": return T[k].format(n=p["n"], hi=p["hi"], lo=p["lo"])
    if k == "big_mover": return T[k].format(names=lst([f'{x["t"]} {pct(x["chg"])}' for x in p["names"]], l))
    if k == "streak": return T[k].format(t=p["t"], n=abs(p["n"]))
    if k in ("absorb_down", "absorb_up", "sweep_lo", "sweep_hi", "confirmed_up", "confirmed_down"):
        return T[k].format(names=lst([tnm(t, l) for t in p["names"]], l))
    if k == "thin_fast":
        return T[k].format(names=lst([f'{tnm(x["t"], l)}（{pct(x["chg"])}，{num(x["rvol"])} {UI[l]["x"]}）' if l != "en" else f'{tnm(x["t"], l)} ({pct(x["chg"])}, {num(x["rvol"])}x)' for x in p["names"]], l))
    if k == "chain_liq":
        eg = lambda xs: T["chain_liq_eg"].format(x=lst(xs[:4], l)) if xs else ""
        conf = (T["chain_conf_up"].format(x=lst(p["buyers"][:6], l)) if p["buyers"] else "") + (T["chain_conf_dn"].format(x=lst(p["sellers"][:6], l)) if p["sellers"] else "")
        return T[k].format(n=p["n"], sw=len(p["sweep_lo"]), swl=eg(p["sweep_lo"]), ab=len(p["absorb"]), abl=eg(p["absorb"]), conf=conf)
    return None

def sentences(r, l):
    out = []
    for f in r["facts"]:
        s = sentence(f, l, r)
        if s: out.append((f["k"], f["sec"], s))
    return out

def key_points(r, l):
    by = {}
    for f in r["facts"]:
        by.setdefault(f["k"], f)
    return [sentence(by[k], l, r) for k in r.get("key", []) if k in by]

# ------------------------------------------------------------------ liquidity table (also used on /market/)
def liq_table(r, l, symbols=None, active_only=False):
    """active_only: only rows with a signal today, in the last five sessions or a control state; the rest are named below"""
    u = UI[l]; liq = r.get("liq") or {}
    by = {b["t"]: b for b in r.get("board", [])}
    syms = [t for t in (symbols or list(liq)) if t in liq]
    quiet = []
    if active_only:
        quiet = [t for t in syms if not (liq[t]["tags"] or liq[t]["recent"] or liq[t]["state"])]
        syms = [t for t in syms if t not in quiet]
    if not syms: return f'<p class="rc-small">{u["quiet"].format(x=lst(quiet, l))}</p>' if quiet else ""
    def tags(xs): return " ".join(f'<span class="lq lq-{x}">{u["tag"].get(x, x)}</span>' for x in xs) or '<span class="lq-none">–</span>'
    def recent(x):
        seen = []
        for e in x["recent"]:
            lab = f'{short_day(e["d"], l)} {u["tag"].get(e["t"], e["t"])}'
            if lab not in seen: seen.append(lab)
        return "<br>".join(E(s_) for s_ in seen[-3:]) or "–"
    def state(x):
        st_ = x.get("state")
        if not st_: return '<span class="lq-none">–</span>'
        cls = "up" if st_ in ("buyers", "watch_bottom", "accel_up") else "" if st_ == "mixed" else "dn"
        return f'<span class="ls ls-{st_} {cls}">{u["state"][st_]}</span>'
    rows = ""
    for t in syms:
        x = liq[t]; b = by.get(t, {})
        ep = x.get("effPct")
        rows += (f'<tr><th><b>{t}</b><small>{E(nm(t, l))}</small></th><td class="num {"up" if (b.get("chg") or 0) >= 0 else "dn"}">{pct(b.get("chg"))}</td>'
                 f'<td class="num">{num(b.get("rvol"))}x</td><td class="num">{"–" if ep is None else f"{ep:.0%}"}</td><td>{tags(x["tags"])}</td>'
                 f'<td class="rc-rec">{recent(x)}</td><td>{state(x)}</td></tr>')
    return (f'<div class="rc-t rc-liq"><table><thead><tr>{"".join(f"<th>{c}</th>" for c in u["liqCols"])}</tr></thead><tbody>{rows}</tbody></table></div>'
            + (f'<p class="rc-small">{u["quiet"].format(x=lst(quiet, l))}</p>' if quiet else "") + f'<p class="rc-small">{u["effNote"]}</p>')

RC_CSS_MIN = """
.rc-t{overflow-x:auto;background:var(--surface);border:1px solid var(--line);border-radius:14px;margin:0 0 6px}
.rc-small{color:var(--muted);font-size:13.5px;margin:6px 0 8px}
.num{font-variant-numeric:tabular-nums;white-space:nowrap}
"""

LIQ_CSS = """
.rc-liq table{min-width:820px;font-size:13.5px}.rc-liq tbody th{text-align:left;font-weight:400;white-space:nowrap}.rc-liq tbody th b{display:block}
.rc-liq tbody th small{color:var(--muted);font-size:12px}.rc-liq td{vertical-align:middle;padding:7px 10px}.rc-rec{font-size:12.5px;color:var(--muted);line-height:1.5}
.lq{display:inline-block;font-size:12px;font-weight:600;border-radius:999px;padding:1px 8px;margin:1px 2px;white-space:nowrap;background:var(--surface-2);color:var(--muted)}
.lq-absorb{background:color-mix(in srgb,var(--t2) 18%,transparent);color:var(--ink)}.lq-thin{background:color-mix(in srgb,var(--accent) 14%,transparent);color:var(--ink)}
.lq-sweep_lo,.lq-sweep_hi{background:color-mix(in srgb,#7a5cff 16%,transparent);color:var(--ink)}
.lq-none{color:var(--faint)}.ls{font-weight:700;font-size:13px;white-space:nowrap}
.rc-five td em{display:block;font-style:normal;font-size:11px;font-weight:700;color:var(--t2)}
"""

# ------------------------------------------------------------------ sections
def _sec(title, body): return f'<section class="rc-s"><h2>{title}</h2>{body}</section>'

def sections(r, l, notes_html=""):
    u = UI[l]; S = sentences(r, l)
    para = lambda sec: "".join(f"<p>{E(s)}</p>" for k, sc, s in S if sc == sec and k != "summary")
    # index table
    rows = "".join(
        f'<tr><td><b>{E(nm(x["t"], l))}</b>{"" if x["t"] == "COMP" else f"<small>{x["t"]}</small>"}</td><td class="num">{num(x["close"])}</td>'
        f'<td class="num {"up" if x["chg"] >= 0 else "dn"}">{pct(x["chg"])}</td><td class="num">{"" if x["t"] != "COMP" else f"{x["pts"]:+,.0f}"}</td>'
        f'<td class="num">{pct(x["lowPct"])}</td><td class="num">{pct(x["offLow"])}</td><td class="num">{pct1(x["dd"])}</td><td class="num">{"–" if x["ytd"] is None else f"{x["ytd"]:+.1f}%"}</td></tr>'
        for x in r["index"])
    vx = r.get("vix")
    if vx:
        rows += (f'<tr><td><b>{u["vix"]}</b></td><td class="num">{num(vx["close"])}</td><td class="num {"dn" if (vx["chg"] or 0) >= 0 else "up"}">{pct(vx["chg"])}</td>'
                 f'<td></td><td class="num" colspan="2">{u["vixHigh"]} {num(vx["high"])} ({pct(vx["highChg"])})</td><td></td><td></td></tr>')
    idx_tbl = f'<div class="rc-t"><table><thead><tr>{"".join(f"<th>{c}</th>" for c in u["cols"])}</tr></thead><tbody>{rows}</tbody></table></div>'
    # sector board, two columns like a newspaper table
    b = sorted((x for x in r["board"] if x["chg"] is not None and x["t"] not in ("DIA",)), key=lambda x: -x["chg"])
    board = "".join(f'<span class="bd"><b>{x["t"]}</b> {E(nm(x["t"], l))} <i class="num {"up" if x["chg"] >= 0 else "dn"}">{pct(x["chg"])}</i></span>' for x in b)
    vols = "".join(f'<span class="vb"><b>{x["t"]}</b> <i class="num{" hot" if x["rvol"] >= 1.5 else " cold" if x["rvol"] < 0.8 else ""}">{num(x["rvol"])}x</i></span>' for x in r["volumes"])
    five = ""
    if r.get("grid"):
        head = "".join(f"<th>{short_day(d, l)}<small>{int(d[5:7])}/{int(d[8:10])}</small></th>" for d in r["days5"])
        def cell(c):
            if not c or c["chg"] is None: return "<td>–</td>"
            hot = " hot" if (c["rvol"] or 0) >= 1.5 else " cold" if (c["rvol"] or 1) < 0.8 else ""
            mk = " ".join(u["short"][x] for x in (c.get("liq") or []) if x in u["short"])
            return f'<td><b class="num {"up" if c["chg"] >= 0 else "dn"}">{pct(c["chg"])}</b><i class="num{hot}">{num(c["rvol"])}x</i>{f"<em>{mk}</em>" if mk else ""}</td>'
        def rk(g):
            if not g.get("rank"): return "<td></td>"
            mv = (g["rankPrev"] or g["rank"]) - g["rank"]
            arrow = f'<i class="up">▲{mv}</i>' if mv > 0 else f'<i class="dn">▼{-mv}</i>' if mv < 0 else "<i>–</i>"
            return f'<td class="rk"><b class="num">{g["rank"]}</b>{arrow}</td>'
        rows = "".join(f'<tr><th><b>{g["t"]}</b><small>{E(nm(g["t"], l))}</small></th>{"".join(cell(c) for c in g["cells"])}{rk(g)}</tr>'
                       for g in sorted(r["grid"], key=lambda g: g.get("rank") or 99))
        five = f'<h3>{u["five"]}</h3><p class="rc-small">{u["fiveP"]}</p><div class="rc-t rc-five"><table><thead><tr><th></th>{head}<th>{u["rank"]}</th></tr></thead><tbody>{rows}</tbody></table></div>'
    trail = "".join(f'<span class="vb">{short_day(x["d"], l)} <i class="num {"up" if (x["chg"] or 0) >= 0 else "dn"}">{pct(x["chg"])}</i> <b class="num">{num(x["rvol"])}x</b></span>' for x in r["spyTrail"])
    bonds = ""
    if r.get("bonds"):
        bo = r["bonds"]
        bonds = ('<div class="rc-chips">' + "".join(f'<span class="vb">{k}Y <b class="num">{num(bo.get(k))}%</b> <i class="num">{bp(bo.get("d" + k))} {u["bp"]}</i></span>' for k in ("5", "10", "30"))
                 + f'<span class="vb">TLT <i class="num {"up" if (bo.get("tlt") or 0) >= 0 else "dn"}">{pct(bo.get("tlt"))}</i> <b class="num">{num(bo.get("tltRvol"))}x</b></span></div>')
    chain = ""
    c = r.get("chain")
    if c:
        summ = next((s for k, sc, s in S if k == "summary"), "")
        top = "".join(f'<span class="vb"><a href="/s/{x["t"]}.html"><b>{x["t"]}</b></a> <i class="num up">{pct(x["chg"])}</i></span>' for x in c["top"])
        bot = "".join(f'<span class="vb"><a href="/s/{x["t"]}.html"><b>{x["t"]}</b></a> <i class="num dn">{pct(x["chg"])}</i></span>' for x in c["bottom"])
        segn = lambda sid: (r.get("segNames", {}).get(str(sid), {}) or {}).get(l, str(sid))
        segs = "".join(f'<span class="vb">{E(segn(x["seg"]))} <i class="num {"up" if x["avg"] >= 0 else "dn"}">{pct(x["avg"])}</i></span>' for x in c["segs"])
        tr = "".join(f'<span class="vb">{short_day(x["d"], l)} <b class="num">{pct1(x["pos"])}</b> <i class="num">{pct1(x["rng"])}</i></span>' for x in c["trail"])
        chain = (f'<p><b>{E(summ)}</b></p>{para("chain")}<div class="rc-two"><div><h3 class="up">{u["up"]}</h3><div class="rc-chips">{top}</div></div>'
                 f'<div><h3 class="dn">{u["down"]}</h3><div class="rc-chips">{bot}</div></div></div><h3>{u["segs"]}</h3><div class="rc-chips">{segs}</div>'
                 f'<h3>{u["trail"]}</h3><div class="rc-chips">{tr}</div>')
    key = "".join(f"<li>{E(s)}</li>" for s in key_points(r, l))
    out = (f'<div class="rc-key"><h2>{u["key"]}</h2><ol>{key}</ol></div>'
           + _sec(u["index"], idx_tbl + para("index"))
           + _sec(u["sector"], f'<div class="rc-board">{board}</div>' + para("sector"))
           + _sec(u["volume"], f'<div class="rc-chips">{vols}</div><h3>SPY</h3><div class="rc-chips">{trail}</div>' + para("volume") + five)
           + _sec(u["liq"], f'<p class="rc-small">{u["liqP"]}</p>' + para("liquidity") + liq_table(r, l, active_only=True))
           + (_sec(u["flows"], para("flows")) if para("flows") else "")
           + _sec(u["bonds"], bonds + para("bonds"))
           + (_sec(u["chain"], chain) if chain else "")
           + (_sec(u["notes"], f'<div class="rc-notes">{notes_html}</div>') if notes_html else "")
           + f'<p class="rc-note">{u["note"]}</p>')
    return out
