"""
Generic TikTok profile scraper: processes a locally-saved Apify dataset JSON,
extracts Amazon product links from video descriptions/titles, scrapes each
product page, and stores results in the products DB + a CSV file.

Usage:
  python amitkapit_scrape.py --dataset-id <FILE.json> [--username <handle>] [--category <name>] [--output <file.csv>]

Examples:
  python amitkapit_scrape.py --dataset-id amitkapit_dataset.json --username amitkapit.offical --category amitkapit
  python amitkapit_scrape.py --dataset-id bk_owner_dataset.json  --username bk_owner          --category bk_owner --output bk_owner_products.csv

Workflow:
  1. Load Apify dataset JSON (saved locally via MCP)
  2. Extract Amazon links from video descriptions -> resolve -> ASIN
  3. For videos without a link: extract core product name from title and search Amazon
  4. Scrape Amazon product pages (price, rating, shipping, image)
  5. Upsert to DB with the specified category (only ships_to_israel=1)
  6. Write CSV (all videos, sorted by play count)
"""

import argparse
import csv
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from src.db import init_db, get_all, upsert_product
from byotools_scrape import (
    resolve_url, extract_asin, is_amazon,
    scrape_amazon_product, search_amazon_for_product,
    ASIN_RE,
)
from playwright.sync_api import sync_playwright

PARTNER_TAG = "eskl20-20"

AMAZON_URL_RE = re.compile(
    r"https?://(?:[\w.-]+\.)?(?:amazon\.com|amzn\.to|amzn\.eu|a\.co)/[^\s)\]]+"
)

# Strip these noise patterns from video titles before using as Amazon search query
_TITLE_NOISE = re.compile(
    r"(?:amazon\s+)?(?:new\s+)?(?:best\s+)?(?:top\s+\d+\s+)?"   # prefixes
    r"|products?\s+linked?\s+in\s+bio.*"                           # "products linked in bio..."
    r"|shop\s+my\s+amazon.*"                                       # "shop my amazon storefront..."
    r"|just\s+search\s+under.*"                                    # "just search under..."
    r"|this\s+video\s+is\s+being\s+shared.*"                       # disclaimer
    r"|#\S+"                                                       # hashtags
    r"|✨|❤️|🏆|🥄|🇸🇪|🎉|⭐",
    re.IGNORECASE,
)

_GENERIC_TERMS = re.compile(
    r"^(kitchen|home|cleaning|laundry|bathroom|closet|office|beauty|"
    r"car|travel|kids|toddler|summer|self.?care|furniture|decor|gadget|"
    r"organization|organizer|must.?have|finds?|hacks?|new|best|top)\s*$",
    re.IGNORECASE,
)


def extract_product_name(title: str) -> str | None:
    """Extract a searchable product name from a TikTok video title."""
    # Strip everything after the first ✨ (usually the template boilerplate)
    clean = title.split("✨")[0].strip()
    # Remove leading "Amazon "
    clean = re.sub(r"^Amazon\s+", "", clean, flags=re.IGNORECASE).strip()
    # Remove trailing "Finds", "MustHave Finds", etc.
    clean = re.sub(r"\s+(must.?have\s+)?finds?\s*$", "", clean, flags=re.IGNORECASE).strip()
    # Remove trailing "MustHave"
    clean = re.sub(r"\s+must.?have\s*$", "", clean, flags=re.IGNORECASE).strip()
    # Remove hashtags and remaining noise
    clean = re.sub(r"#\S+", "", clean).strip()

    if not clean or len(clean) < 5:
        return None
    # Skip if it's just a generic category word
    if _GENERIC_TERMS.match(clean):
        return None
    return clean


def fetch_apify_dataset(dataset_id: str) -> list[dict]:
    """Load Apify dataset from a local JSON file."""
    path = Path(dataset_id) if Path(dataset_id).exists() else Path(f"{dataset_id}.json")
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("items", data) if isinstance(data, dict) else data
    raise FileNotFoundError(f"Dataset file not found: {path}")


def extract_amazon_links(text: str) -> list[str]:
    return AMAZON_URL_RE.findall(text or "")


def parse_videos(items: list[dict], username: str) -> list[dict]:
    """Normalise Apify output into a clean list of video dicts."""
    videos = []
    for item in items:
        eng      = item.get("engagement") or {}
        plays    = eng.get("play_count") or item.get("playCount") or 0
        likes    = eng.get("digg_count") or item.get("diggCount") or 0
        comments = eng.get("comment_count") or item.get("commentCount") or 0
        shares   = eng.get("share_count") or item.get("shareCount") or 0
        saves    = eng.get("collect_count") or item.get("collectCount") or 0

        video_id  = item.get("video_id") or item.get("id") or ""
        desc      = item.get("title") or item.get("video_description") or item.get("desc") or ""
        posted_ts = item.get("create_time") or item.get("created_time") or item.get("createTime") or ""
        cover     = item.get("cover_url") or item.get("origin_cover_url") or (item.get("covers") or {}).get("default") or ""
        video_url = (
            f"https://www.tiktok.com/@{username}/video/{video_id}"
            if video_id else item.get("video_url") or ""
        )

        posted_date = ""
        if posted_ts:
            try:
                posted_date = datetime.fromtimestamp(int(posted_ts), tz=timezone.utc).strftime("%Y-%m-%d")
            except Exception:
                posted_date = str(posted_ts)

        videos.append({
            "plays": int(plays), "likes": int(likes), "comments": int(comments),
            "shares": int(shares), "saves": int(saves),
            "video_url": video_url, "posted_date": posted_date,
            "description": desc, "cover": cover,
        })

    return sorted(videos, key=lambda v: v["plays"], reverse=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-id", required=True, help="Local Apify dataset JSON file path")
    parser.add_argument("--username",   default="amitkapit.offical", help="TikTok username (for URL construction)")
    parser.add_argument("--category",   default="amitkapit",         help="DB category name")
    parser.add_argument("--output",     default=None,                 help="Output CSV filename (default: <category>_products.csv)")
    args = parser.parse_args()

    output_csv = args.output or f"{args.category}_products.csv"

    init_db()
    existing_asins = {p["asin"] for p in get_all()}
    print(f"DB has {len(existing_asins)} existing products.\n")

    print(f"Loading dataset {args.dataset_id}...")
    items = fetch_apify_dataset(args.dataset_id)
    print(f"Got {len(items)} videos.\n")

    videos = parse_videos(items, args.username)
    print(f"Parsed {len(videos)} videos. Top plays: {[v['plays'] for v in videos[:5]]}\n")

    now_iso = datetime.now(timezone.utc).isoformat()
    video_asin_map: dict[str, str] = {}
    asin_data: dict[str, dict] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US", timezone_id="America/New_York",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = ctx.new_page()
        page.goto("https://www.amazon.com/", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(1500)

        for i, vid in enumerate(videos, 1):
            desc = vid["description"]
            vurl = vid["video_url"]
            print(f"[{i}/{len(videos)}] {desc[:70]!r}  ({vid['plays']:,} plays)")

            # Step 1: Amazon link in description
            asin = None
            for link in extract_amazon_links(desc):
                resolved = resolve_url(link) if not is_amazon(link) else link
                asin = extract_asin(resolved)
                if asin:
                    print(f"  -> ASIN from link: {asin}")
                    break

            # Step 2: extract product name and search Amazon
            if not asin:
                product_name = extract_product_name(desc)
                if product_name:
                    print(f"  -> searching: {product_name!r}")
                    asin = search_amazon_for_product(page, product_name)
                    if asin:
                        print(f"  -> found: {asin}")
                    else:
                        print(f"  -> not found on Amazon")
                else:
                    print(f"  -> generic title, skipping")

            if not asin:
                time.sleep(0.3)
                continue

            video_asin_map[vurl] = asin

            if asin in asin_data:
                print(f"  -> already scraped {asin}, reusing")
                continue

            if asin in existing_asins:
                print(f"  -> {asin} already in DB")
                asin_data[asin] = {"asin": asin, "already_in_db": True}
                continue

            data = scrape_amazon_product(page, asin)
            if not data:
                print(f"  -> scrape failed for {asin}")
                time.sleep(1)
                continue

            asin_data[asin] = data
            ships = data.get("ships_to_israel", False)
            print(f"  -> ${data.get('price_usd',0):.2f}  rating={data.get('rating',0)}  ships_IL={ships}")

            if ships:
                upsert_product(asin, {
                    "name":               data.get("name") or asin,
                    "category":           args.category,
                    "rating":             data.get("rating", 0),
                    "review_count":       data.get("review_count", 0),
                    "price_usd":          data.get("price_usd", 0),
                    "ships_to_israel":    1,
                    "free_shipping_type": "free" if data.get("free_shipping") else "paid",
                    "affiliate_link":     data.get("affiliate_link", f"https://www.amazon.com/dp/{asin}/?tag={PARTNER_TAG}"),
                    "source_video_url":   vurl,
                    "image_url":          data.get("image_url") or vid["cover"],
                    "status":             "discovered",
                })
                existing_asins.add(asin)
                print(f"  -> saved to DB")
            else:
                print(f"  -> does not ship to Israel, not saved")

            time.sleep(1.5)

        browser.close()

    # Write CSV
    db_products = {p["asin"]: p for p in get_all()}
    csv_rows = []
    for rank, vid in enumerate(videos, 1):
        vurl = vid["video_url"]
        asin = video_asin_map.get(vurl, "")
        db   = db_products.get(asin, {}) if asin else {}
        csv_rows.append({
            "rank":               rank,
            "tiktok_play_count":  vid["plays"],
            "tiktok_likes":       vid["likes"],
            "tiktok_comments":    vid["comments"],
            "tiktok_shares":      vid["shares"],
            "tiktok_saves":       vid["saves"],
            "tiktok_url":         vurl,
            "tiktok_posted_date": vid["posted_date"],
            "asin":               asin,
            "name":               db.get("name", ""),
            "name_he":            db.get("name_he", ""),
            "category":           args.category,
            "rating":             db.get("rating", ""),
            "review_count":       db.get("review_count", ""),
            "price_usd":          db.get("price_usd", ""),
            "ships_to_israel":    db.get("ships_to_israel", ""),
            "free_shipping_type": db.get("free_shipping_type", ""),
            "affiliate_link":     db.get("affiliate_link", f"https://www.amazon.com/dp/{asin}/?tag={PARTNER_TAG}" if asin else ""),
            "source_video_url":   db.get("source_video_url", vurl),
            "image_url":          db.get("image_url", vid["cover"]),
            "description_he":     db.get("description_he", ""),
            "status":             db.get("status", "discovered"),
            "discovered_at":      db.get("discovered_at", now_iso),
            "updated_at":         db.get("updated_at", now_iso),
        })

    fieldnames = [
        "rank", "tiktok_play_count", "tiktok_likes", "tiktok_comments",
        "tiktok_shares", "tiktok_saves", "tiktok_url", "tiktok_posted_date",
        "asin", "name", "name_he", "category", "rating", "review_count",
        "price_usd", "ships_to_israel", "free_shipping_type", "affiliate_link",
        "source_video_url", "image_url", "description_he", "status",
        "discovered_at", "updated_at",
    ]
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(csv_rows)

    ships_count = sum(1 for r in csv_rows if r["ships_to_israel"] == 1)
    print(f"\n{'='*55}")
    print(f"  Total videos:     {len(videos)}")
    print(f"  ASINs found:      {len(video_asin_map)}")
    print(f"  Ship to Israel:   {ships_count}")
    print(f"  CSV:              {output_csv}")
    print(f"{'='*55}")
    print(f"\nNext: python main.py --phase filter && python translate_names.py && python enrich_products.py")


if __name__ == "__main__":
    main()
