# April's Insider Flow

Source, data and daily pipeline for https://april-insider-flow.com — SEC Form 4 open-market insider buys and sells, by sector.

## Layout

- `data/days/YYYY-MM-DD.json` — one summary per EDGAR filing date (schema 2), from 2026-07-01.
- `site/index.html` — the interactive page template.
- `scripts/form4_sector.py` — fetches one filing date from EDGAR (Form 4 + Form 144 cross-check, exclusion categories, foreign-currency prices converted to USD).
- `scripts/verify.py` — re-checks a fetched day against SEC's rendered filing pages (top-10 effective buyers/sellers, every effective purchase, every foreign-currency filing, 30 random filings, holdings before/after, totals). A day is published only with `0 problem(s)`.
- `scripts/check_data.py` — offline consistency check of every stored day (sector totals = company sums = filing sums).
- `scripts/anomaly.py` — flags likely data errors (`!!` urgent, `~` review) in newly added days.
- `scripts/build_site.py` — builds `public/`: language pages, per-company pages `s/<TICKER>.html`, RSS feeds, sitemap, share images.
- `scripts/daily_update.py` — orchestrates fetch → verify → keep passing days.
- `scripts/weekly.py`, `scripts/bd_post.py` — weekly digest email (Buttondown draft).

## Automation (`.github/workflows/`)

- **daily.yml** — weekdays 03:45 UTC (evening Pacific): fetch every missing weekday of the last 10 days → SEC verification → consistency check → anomaly scan → build → deploy to Cloudflare Pages project `april-insider-flow` → commit the new data. Withheld days, urgent anomalies or a failed run open a GitHub issue (GitHub emails you). Run it by hand from the Actions tab; inputs let you refetch specific dates or force a redeploy.
- **weekly-email.yml** — Saturdays 15:35 UTC: builds the weekly digest (Chinese first, then English) and saves it as a Buttondown **draft**.

Secrets: `CLOUDFLARE_API_TOKEN` (Account → Cloudflare Pages → Edit), `CLOUDFLARE_ACCOUNT_ID`, `BUTTONDOWN_API_KEY`.

## Local use

```
python3 scripts/daily_update.py --ua "Name email@example.com" --dates 2026-10-27
python3 scripts/check_data.py
python3 scripts/build_site.py data/days site/index.html public
```
