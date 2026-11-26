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
- `scripts/build_calendar.py` — builds `/calendar/` from `data/macro.json` (also published as `/calendar/macro.json`). Times show US Eastern first, then Beijing, converted in the browser so daylight saving needs no upkeep.
- `scripts/weekly.py`, `scripts/whatsnew.py`, `scripts/bd_post.py` — weekly digest email (Buttondown).

## Automation (`.github/workflows/`)

- **daily.yml** — weekdays 03:45 UTC (evening Pacific): fetch every missing weekday of the last 10 days → SEC verification → consistency check → anomaly scan → build → deploy to Cloudflare Pages project `april-insider-flow` → commit the new data. Withheld days, urgent anomalies or a failed run open a GitHub issue (GitHub emails you). Run it by hand from the Actions tab; inputs let you refetch specific dates or force a redeploy.
- The same run also updates the macro calendar (`fetch_macro.py`, with the `SEC_UA` contact, which BLS also asks for); a changed calendar alone is enough to rebuild, deploy and commit `data/macro.json`.
- **weekly-email.yml** — Saturdays 15:35 UTC (08:35 Pacific): builds the weekly digest (Chinese first, then English) and **sends it to subscribers** through Buttondown, but only if the data consistency check passes, the latest weekday is present and the week has no urgent anomalies. Otherwise it saves a draft and opens an issue. Manual runs only save a draft unless "send" is ticked. GitHub sometimes drops scheduled runs, so catch-up runs follow (Sat 19:41 and 23:17, Sun 04:53 UTC); each run first checks Buttondown and stops if this week's email already exists, so nothing is sent twice.
- **Top of the weekly email, "本周上线 / New this week"**: earnings reports new since the last sent email (live `april-insider-flow.com/earnings/data/index.json` compared with `data/earnings_seen.json`, which is updated after each send) and new features from `data/whatsnew.json` dated this week. To announce a feature, add `{"date": "YYYY-MM-DD", "zh": "...", "en": "..."}` to that file.

Secrets: `CLOUDFLARE_API_TOKEN` (Account → Cloudflare Pages → Edit), `CLOUDFLARE_ACCOUNT_ID`, `BUTTONDOWN_API_KEY`.

## Local use

```
python3 scripts/daily_update.py --ua "Name email@example.com" --dates 2026-10-27
python3 scripts/check_data.py
python3 scripts/build_site.py data/days site/index.html public
```
