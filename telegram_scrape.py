"""
Telegram channel → Amazon product ingestion.

Polls a public Telegram channel's preview page (t.me/s/{channel}), extracts
all Amazon URLs from recent messages, resolves short links, dedupes against
the DB, and inserts new ASINs as status='discovered' with category='telegram'.

The orchestrator (run_telegram_pipeline.sh) then runs the standard validate +
filter + enrich pipeline on the new products.

Run: python telegram_scrape.py
Schedule: every 6 hours via ~/Library/LaunchAgents/me.affiliation.telegram-ingest.plist
"""

import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).parent))
from src.db import init_db, upsert_product, get_all
from byotools_scrape import extract_asin, resolve_url, is_amazon

# ── Configuration ────────────────────────────────────────────────────────────
# TODO: replace with the actual channel handle (without the @)
# Examples: "amazonisrael", "deals_il", etc.
CHANNEL = "haregakaniti"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

AMAZON_URL_RE = re.compile(
    r"https?://(?:[\w.-]+\.)?(?:amazon\.com|amzn\.to|amzn\.eu|a\.co)/[^\s)\]]+"
)


def fetch_messages(channel: str) -> list[str]:
    """Return text+links blob for each recent message in the channel."""
    url = f"https://t.me/s/{channel}"
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    blobs = []
    for m in soup.select(".tgme_widget_message"):
        text = m.get_text(" ", strip=True)
        links = " ".join(a.get("href", "") for a in m.find_all("a"))
        blobs.append(f"{text} {links}")
    return blobs


def main() -> int:
    if CHANNEL == "PLACEHOLDER_CHANNEL_HANDLE":
        print("ERROR: Set CHANNEL constant in telegram_scrape.py to the real handle.")
        return -1

    init_db()
    existing_asins = {p["asin"] for p in get_all()}
    print(f"DB has {len(existing_asins)} known ASINs")

    try:
        messages = fetch_messages(CHANNEL)
    except Exception as e:
        print(f"ERROR fetching @{CHANNEL}: {e}")
        return -1
    print(f"Fetched {len(messages)} messages from @{CHANNEL}")

    seen_urls = set()
    new_asins = set()
    for msg in messages:
        for url in AMAZON_URL_RE.findall(msg):
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # Resolve short links; direct /dp/ URLs don't need a redirect lookup
            if "/dp/" in url and is_amazon(url):
                resolved = url
            else:
                resolved = resolve_url(url)

            asin = extract_asin(resolved)
            if not asin:
                continue
            if asin in existing_asins or asin in new_asins:
                continue

            new_asins.add(asin)
            upsert_product(asin, {"status": "discovered", "category": "telegram"})
            print(f"  + {asin}  (from {url[:60]})")
            time.sleep(0.3)

    print(f"Discovered {len(new_asins)} new products from Telegram")
    return len(new_asins)


if __name__ == "__main__":
    n = main()
    sys.exit(0 if n >= 0 else 1)
