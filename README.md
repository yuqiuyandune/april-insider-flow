# April's Stock Atlas

Source, data and daily pipeline for https://april-insider-flow.com — SEC Form 4 open-market insider buys and sells, by sector.

## Layout

- `data/days/YYYY-MM-DD.json` — one summary per EDGAR filing date (schema 2), from 2026-07-01.
- `site/index.html` — the interactive page template.
- `scripts/form4_sector.py` — fetches one filing date from EDGAR (Form 4 + Form 144 cross-check, exclusion categories, foreign-currency prices converted to USD).
- `scripts/verify.py` — re-checks a fetched day against SEC's rendered filing pages (top-10 effective buyers/sellers, every effective purchase, every foreign-currency filing, 30 random filings, holdings before/after, totals). A day is published only with `0 problem(s)`.
- `scripts/check_data.py` — offline consistency check of every stored day (sector totals = company sums = filing sums).
- `scripts/anomaly.py` — flags likely data errors (`!!` urgent, `~` review) in newly added days.
- `scripts/build_site.py` — builds `public/`: language pages, per-company pages `s/<TICKER>.html`, RSS feeds, sitemap, share images.
- `articles/src/<slug>.{zh,tw,en}.md` + `<slug>.sources.md` — long-form articles (Simplified, Traditional, English) and their source lists.
- `scripts/build_articles.py` — builds `/market/` (Market watch: macro dashboard and sector table drawn in the browser from `/earnings/data/market.json`, which the earnings repo's daily prices workflow fetches; per-sector effective insider buying/selling over 30 days computed here and embedded) and each article at `/articles/<slug>/`. `/articles/` redirects to `/market/`.
- `scripts/daily_update.py` — orchestrates fetch → verify → keep passing days.
- `scripts/fetch_macro.py` — reads the official schedules (Fed FOMC calendar; BLS CPI, Employment Situation, PPI; BEA Personal Income and Outlays/PCE and GDP; NYSE holidays and early closes) into `data/macro.json`. Each source is re-read at most every 3 days; one that fails keeps its previous dates and is reported in an issue at most once a week.
- `scripts/build_home.py` — builds the homepage `/`: one header bar for the whole site (sections, ticker search, language, subscribe), today's market tiles, today's signals (cluster buys and the largest buy of the last 5 filing days), the next macro events, the latest earnings reviews, the largest insider buys and sells, and a grid of every section. Old `/#NVDA` and `/#layer-3` links are forwarded to the AI chain.
- Supply chains live under `/themes/`: `/themes/ai/` and `/themes/energy/` (from `stack/index.html`, data.json next to each). `/stack/`, `/energy/` and `/ai/` redirect there.
- `scripts/fetch_volume.py` — daily price and volume read of 32 key ETFs and stocks (index, 11 sector ETFs, SMH/TLT/GLD/USO/IBIT, the largest tech and AI names) from Nasdaq's public quote API into `data/volume.json`: change, relative volume, close in range, 20/50/200-day averages, distance from the one-year high, rule-based flags.
- `scripts/build_volume.py` — builds `/market/volume/` (量价分析) and the short summary on the homepage; the homepage market tiles come from the same file.
- `scripts/fetch_options.py` — daily options read from Nasdaq's public option chains for index/asset ETFs, key stocks and the companies on the homepage's insider signals: call and put volume, put/call ratio, premium, volume/open interest, unusual new positions (volume 5x+ open interest, real size, 7 days to a year out, out of the money or at most 10% in) and rule-based flags, into `data/options.json`; daily totals accumulate in `data/options_hist.json` for a 20-day comparison.
- `scripts/build_options.py` — builds `/options/` (期权异动) and the homepage's options box; the homepage signals light up Options for a company whose options also moved.
- `scripts/fetch_institutions.py` — 13D/13G: every new Schedule 13D, 13D/A and 13G in SEC's daily index (company, filer, % of class, purpose) into `data/stakes.json` (60 days); 13F: the latest two reports of 20 fundamental managers compared (new, exited, added, trimmed, top holdings) into `data/funds.json`, re-read only when a fund files. CUSIPs become tickers through OpenFIGI, then SEC's company list by name; cached in `data/cusip_tickers.json`.
- `scripts/build_institutions.py` — builds `/institutions/` (机构持仓): what several funds bought or sold together, recent 5%+ stakes (market makers and index-fund families left out), each fund's quarter; the homepage's Institutions box and signal tag.
- `scripts/recap.py`, `scripts/recap_text.py` — the daily market recap on `/market/volume/` (one page per session under `/market/volume/<date>/`): `fetch_volume.py` also reads the Nasdaq Composite, the AI chain's listed stocks, CBOE's VIX history and the Treasury yield curve, and `recap.py` turns one session into numbers and the reading rules that fire (intraday shape, two-day net, best day since, drawdown and year-to-date, streaks, sector reversal, volume against the down day, ETF volume regime, where the money went, yields, the chain's breadth, concentration and close-in-range trail). Results are kept in `data/recaps/<date>.json`. Sentences are written in `recap_text.py` (Simplified and English); the Traditional ones are generated into `recap_tw.py` by `scripts/make_recap_tw.py` (OpenCC) after a Simplified template changes.
- **April's notes on a session**: add `data/notes/<YYYY-MM-DD>.md` (Simplified Chinese; optional `.tw.md` and `.en.md`) and it appears on that day's recap under Catalysts. Markdown as in the articles; a file can be added or edited later, the next build picks it up.
- `scripts/build_calendar.py` — builds `/calendar/` from `data/macro.json` (also published as `/calendar/macro.json`). Times show US Eastern first, then Beijing, converted in the browser so daylight saving needs no upkeep.
- `scripts/weekly.py`, `scripts/whatsnew.py`, `scripts/bd_post.py` — weekly digest email (Buttondown).

## Automation (`.github/workflows/`)

- **daily.yml** — weekdays 03:45 UTC (evening Pacific): fetch every missing weekday of the last 10 days → SEC verification → consistency check → anomaly scan → build → deploy to Cloudflare Pages project `april-insider-flow` → commit the new data. Withheld days, urgent anomalies or a failed run open a GitHub issue (GitHub emails you). Run it by hand from the Actions tab; inputs let you refetch specific dates or force a redeploy.
- The same run also updates the macro calendar (`fetch_macro.py`, with the `SEC_UA` contact, which BLS also asks for); a changed calendar alone is enough to rebuild, deploy and commit `data/macro.json`.
- **daily-email.yml** — weekdays 11:40 UTC (19:40 Beijing), catch-up 13:17: `scripts/daily_email.py` builds the daily brief (the latest recap's key points, the homepage signals with their options and institutions tags, the next calendar events in ET and Beijing time, options and institutions lines; Chinese first, then English) and `scripts/bd_daily.py` sends it through Buttondown **only to subscribers tagged `daily`** (the site's subscribe forms have a "daily brief" checkbox; the tag is subscriber-editable in Buttondown's portal). It creates a draft with the tag filter, checks Buttondown kept the filter, then sends; a session is never sent twice (after a holiday the repeat is skipped); if the data is not for the latest US session it saves a draft and opens an issue. Manual runs save a draft unless "send" is ticked.
- **weekly-email.yml** — Saturdays 15:35 UTC (08:35 Pacific): builds the weekly digest (Chinese first, then English) and **sends it to subscribers** through Buttondown, but only if the data consistency check passes, the latest weekday is present and the week has no urgent anomalies. Otherwise it saves a draft and opens an issue. Manual runs only save a draft unless "send" is ticked. GitHub sometimes drops scheduled runs, so catch-up runs follow (Sat 19:41 and 23:17, Sun 04:53 UTC); each run first checks Buttondown and stops if this week's email already exists, so nothing is sent twice.
- **Top of the weekly email, "本周上线 / New this week"**: earnings reports new since the last sent email (live `april-insider-flow.com/earnings/data/index.json` compared with `data/earnings_seen.json`, which is updated after each send) and new features from `data/whatsnew.json` dated this week. To announce a feature, add `{"date": "YYYY-MM-DD", "zh": "...", "en": "..."}` to that file.

Secrets: `CLOUDFLARE_API_TOKEN` (Account → Cloudflare Pages → Edit), `CLOUDFLARE_ACCOUNT_ID`, `BUTTONDOWN_API_KEY`.

## Local use

```
python3 scripts/daily_update.py --ua "Name email@example.com" --dates 2026-10-27
python3 scripts/check_data.py
python3 scripts/build_site.py data/days site/index.html public
```
