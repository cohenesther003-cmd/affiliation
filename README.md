# Affiliation Pipeline

Automated affiliate marketing pipeline: discover Amazon products → validate → transform into Hebrew TikTok videos → distribute → track performance.

## Project Phases

| Phase | Description | Status |
|-------|-------------|--------|
| **1 — Data & Validation** | Scrape Amazon, validate via PA-API, store in SQLite | ✅ Built |
| **2 — Video Transformation** | yt-dlp + GPT-4o script + ElevenLabs voiceover + MoviePy editing | 🔜 Next |
| **3 — Distribution** | TikTok posting + Spark Ads + Link-in-Bio page | 🔜 Planned |
| **4 — Analytics** | Amazon sales + TikTok ad spend → KPI dashboard | 🔜 Planned |

---

## Phase 1 — Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Set up your API keys

```bash
cp .env.example .env
```

Open `.env` and fill in your Amazon PA-API credentials (see setup guide below).

### 3. Configure your filters

Open `config.yaml` — edit any threshold without touching code:

```yaml
filters:
  min_rating: 4.0
  min_reviews: 50
  min_price_usd: 15.0
  max_price_usd: 150.0
  ships_to_israel: true
  allowed_categories:
    - Tools
    - Garden
```

### 4. Run the pipeline

```bash
# Full run: scrape → validate → filter
python main.py --url "https://www.amazon.com/Best-Sellers-Tools-Home-Improvement/zgbs/hi/"

# Run individual steps
python main.py --url "..." --phase scrape      # scrape only
python main.py --phase validate                # validate only (no URL needed)
python main.py --phase filter                  # apply filters only
python main.py --phase status                  # print DB summary
```

### 5. Inspect results

Open `data/products.db` with [DB Browser for SQLite](https://sqlitebrowser.org/) (free) to browse all products and their statuses.

---

## API Key Setup Guide

### Amazon PA-API (required for Phase 1)

1. **Join Amazon Associates**: go to [affiliate-program.amazon.com](https://affiliate-program.amazon.com) and sign up
2. **Request PA-API access**: after your account is approved, go to **Tools → Product Advertising API**
3. **Create credentials**: you'll receive an Access Key, Secret Key, and Partner Tag
4. Add them to your `.env` file

> Note: Amazon requires you to make at least 3 qualifying sales within 180 days to keep PA-API access active.

---

### OpenAI — GPT-4o (Phase 2)

1. Go to [platform.openai.com](https://platform.openai.com)
2. Sign up or log in → click **API Keys** in the left menu
3. Click **Create new secret key** → copy it to `.env` as `OPENAI_API_KEY`

---

### ElevenLabs — Hebrew Voiceover (Phase 2)

1. Go to [elevenlabs.io](https://elevenlabs.io) and sign up
2. Click your profile icon → **Profile + API key**
3. Copy the API key to `.env` as `ELEVENLABS_API_KEY`
4. Choose a Hebrew voice from the Voice Library (search "Hebrew")

---

### TikTok APIs (Phase 3)

1. Go to [developers.tiktok.com](https://developers.tiktok.com) and sign up as a developer
2. Create an app → request access to:
   - **Content Posting API** (for uploading videos)
   - **Marketing API** (for Spark Ads / ad management)
3. Copy `Client Key` and `Client Secret` to `.env`

---

## Project Structure

```
affiliation/
├── data/products.db          # SQLite database (not tracked in git)
├── src/
│   ├── db.py                 # database helpers
│   └── phase1/
│       ├── scraper.py        # Playwright scraper
│       ├── amazon_api.py     # PA-API validator
│       └── filter.py         # dynamic config-driven filter
├── main.py                   # CLI entry point
├── config.yaml               # all filter thresholds (edit freely)
├── config.py                 # loads config.yaml (don't edit)
├── .env.example              # API key template
└── requirements.txt
```
