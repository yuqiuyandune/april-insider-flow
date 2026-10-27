# April's Insider Flow

Source and data for https://april-insider-flow.com — SEC Form 4 open-market insider buys and sells, by sector.

- `data/days/YYYY-MM-DD.json` — one summary per EDGAR filing date (schema 2). History starts 2026-07-01.
- `scripts/verify.py` — consistency checks run before every deploy: sector totals equal company sums, company totals equal their filings, no unparsed filings, no missing weekdays.

To do (in progress):
- daily fetch script (schema 2, with Form 144 cross-check, exclusion categories and FX conversion)
- site page and build step
- GitHub Actions workflow: fetch → verify → build → deploy to Cloudflare Pages
