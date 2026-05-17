# Technical Flow — Affiliation Pipeline

## What it does
Finds Amazon products, validates them, translates them to Hebrew, and publishes them to a public product store at GitHub Pages.

---

## Data sources

| Source | Category in DB | How it's scraped |
|--------|---------------|-----------------|
| Amazon Best Sellers | `Best Sellers …` | Playwright visits Amazon category pages |
| byotools.me/byotlinks | `byotools` | Playwright scrapes the affiliate link page, resolves short links to ASINs |
| Telegram @haregakaniti | `telegram` | Polls `t.me/s/haregakaniti` (public web preview) every 6h, extracts Amazon links |
| Hand-picked top picks | `top` | Manually ingested; 20 products with highest @byotools TikTok view counts |

---

## Product lifecycle

```
discovered → validated → ready_for_video → (shown on site)
                       ↘ filtered_out    → (hidden)
                       ↘ unavailable     → (hidden, auto-restores when back in stock)
```

1. **discovered** — ASIN added to DB, no details yet
2. **validated** — Amazon product page scraped: name, price, rating, image, ships-to-Israel confirmed
3. **filter step** — product checked against rules in `config.yaml`:
   - `byotools` → **skip quality rules** (pre-vetted), but still checked for Israel shipping
   - `top` / `telegram` → **skip category rule only**; still checked for rating, reviews, price, shipping
   - All others → **all rules apply**
4. **ready_for_video** — passed filters, shown on public site
5. **filtered_out** — failed a rule (bad rating, no Israel shipping, wrong category, etc.)
6. **unavailable** — out of stock; auto-restored to `ready_for_video` when back in stock

---

## Pipeline steps (in order)

### Step 1 — Scrape
`python main.py --url "..." --phase scrape`

Playwright opens the Amazon Best Sellers page (or byotools.me), collects ASINs, and inserts new ones as `status='discovered'`. Already-known ASINs are skipped (delta scrape).

### Step 2 — Validate
`python main.py --phase validate`

Playwright opens each `discovered` product's Amazon page and scrapes: name, price (USD), rating, review count, image URL, whether it ships to Israel. Sets status → `validated`.

### Step 3 — Filter
`python main.py --phase filter`

Reads all `validated` products, applies rules from `config.yaml`. Sets status → `ready_for_video` or `filtered_out`.

### Step 4 — Translate names
`python translate_names.py`

Sends product names in batches of 15 to the Claude CLI. Returns natural Hebrew names (no niqqud, metric units). Skips already-translated products. `--retranslate` flag clears and re-runs all.

### Step 5 — Enrich descriptions
`python enrich_products.py`

Sends product details to Claude CLI → generates a 4–5 sentence Hebrew marketing description per product. Resets any description shorter than 200 chars so it gets regenerated.

### Step 6 — Export site
`python export_page.py`

Reads all `ready_for_video` products from the DB and writes the full `docs/` folder:
- `docs/index.html` — product grid with sidebar filters
- `docs/products/{asin}.html` — one detail page per product

Then: `git add docs/ && git commit -m "..." && git push` → GitHub Pages publishes automatically.

---

## Automated schedules (Mac launchd)

| Job | Schedule | Script | What it does |
|-----|----------|--------|-------------|
| Telegram ingest | Every 6h (2 AM / 8:15 AM / 2 PM / 8 PM) | `run_telegram_pipeline.sh` | Scrape → validate → filter → translate → enrich → export → push → queue email |
| Daily refresh | 8:00 AM (local) | `refresh_products.py` | Re-scrape prices/availability → export → push → queue email |
| Mail sender | Every 30 min | `send_pending_reports.py` | Send queued emails from `data/pending_reports/`, delete after send |

**Email architecture (separated agents):**
- Pipelines **never send email directly**. At the end of each run, they write a JSON file to `data/pending_reports/` with `subject`, `body`, and `created_at`.
- `send_pending_reports.py` (mail-sender agent) runs independently every 30 minutes, picks up any pending files, sends via Gmail SMTP (`GMAIL_USER` + `GMAIL_APP_PASSWORD`), and deletes each file after sending.
- Pending report files: `data/pending_reports/telegram_YYYYMMDD_HHMMSS.json`, `data/pending_reports/refresh_YYYYMMDD_HHMMSS.json`

---

## Useful one-off scripts

| Script | When to run |
|--------|-------------|
| `update_ratings.py` | Products with rating = 0 (scrape bot was blocked) |
| `verify_israel_shipping.py` | Re-check Israel shipping for all live products |
| `fix_missing_names.py` | Products whose name is still the raw ASIN code |
| `refresh_products.py` | Re-scrape prices/availability for all live products |

---

## Config

All filter thresholds live in `config.yaml` — never hardcoded in Python:
- `min_rating`, `min_reviews`, `min_price_usd`, `max_price_usd`
- `ships_to_israel: true/false`
- `allowed_categories` list (applied to Best Sellers; skipped for top/telegram/byotools)

---

## Hebrew content generation

Both `translate_names.py` and `enrich_products.py` use the **Claude CLI** via subprocess:
```
claude --print -p "..."
```
No API key needed — uses the same Claude Code login session. Never use the `anthropic` Python SDK (would need a separate API key).

---

## Public site

URL: `https://cohenesther003-cmd.github.io/affiliation/`

- Static HTML/CSS (Bootstrap 5 RTL + Heebo font)
- Right-to-left Hebrew layout
- Sidebar filters: price, rating, shipping, category, search
- Mobile: slide-in filter drawer
- Filters + scroll position saved in `sessionStorage` — survives back-navigation
