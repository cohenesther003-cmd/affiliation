"""
Scrape @byotools TikTok, match videos to DB products, store tiktok_url.

Run: python tiktok_match.py
"""

import json
import re
import subprocess
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from src.db import init_db, upsert_product, DB_PATH

# Words that don't help with matching
STOPWORDS = {
    "a", "an", "the", "and", "or", "for", "in", "on", "with", "of", "to",
    "pack", "pcs", "piece", "pieces", "set", "inch", "inches", "ft", "feet",
    "lb", "lbs", "oz", "ml", "l", "count", "pk", "ct", "x", "new", "plus",
    "pro", "heavy", "duty", "high", "quality", "best", "premium", "easy",
    "use", "diy", "home", "tool", "tools", "product", "item",
}

TIKTOK_PROFILE = "https://www.tiktok.com/@byotools"
LIMIT = 10  # max products to match


def fetch_tiktok_videos() -> list[dict]:
    print("Fetching videos from @byotools TikTok...")
    result = subprocess.run(
        ["yt-dlp", "--flat-playlist", "--dump-json", "--no-warnings", TIKTOK_PROFILE],
        capture_output=True, text=True, timeout=120
    )
    videos = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        try:
            v = json.loads(line)
            video_id = v.get("id") or v.get("display_id") or ""
            title = v.get("title") or ""
            description = v.get("description") or title
            if video_id:
                videos.append({
                    "id": video_id,
                    "title": title,
                    "description": description,
                    "url": f"https://www.tiktok.com/@byotools/video/{video_id}",
                })
        except Exception:
            continue
    print(f"  Found {len(videos)} TikTok videos")
    return videos


def extract_keywords(text: str) -> set[str]:
    words = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in STOPWORDS}


def score_match(product_keywords: set, video_text: str) -> int:
    video_words = extract_keywords(video_text)
    return len(product_keywords & video_words)


def load_byotools_products() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT asin, name, name_he, tiktok_url FROM products "
        "WHERE category = 'byotools' AND status = 'ready_for_video'"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def main():
    init_db()

    videos = fetch_tiktok_videos()
    if not videos:
        print("No videos found — exiting.")
        return

    products = load_byotools_products()
    already_matched = sum(1 for p in products if p.get("tiktok_url"))
    unmatched = [p for p in products if not p.get("tiktok_url")]
    print(f"  {len(products)} byotools ready_for_video products ({already_matched} already have a TikTok URL, {len(unmatched)} remaining)")

    # Build keyword sets for each product
    for p in unmatched:
        p["_keywords"] = extract_keywords(p["name"] or "")

    # Score every video against every product, pick best match per video
    matches = []  # list of (score, video, product)
    used_products = set()
    used_videos = set()

    # Build full score matrix and greedily assign best pairs
    scores = []
    for video in videos:
        video_text = video["title"] + " " + video["description"]
        for product in unmatched:
            s = score_match(product["_keywords"], video_text)
            if s >= 2:
                scores.append((s, video, product))

    # Sort by score descending, assign greedily
    scores.sort(key=lambda x: -x[0])
    for score, video, product in scores:
        if video["id"] in used_videos or product["asin"] in used_products:
            continue
        matches.append((score, video, product))
        used_videos.add(video["id"])
        used_products.add(product["asin"])
        if len(matches) >= LIMIT:
            break

    if not matches:
        print("\nNo matches found with score >= 2. Try lowering the threshold.")
        return

    print(f"\n{'='*60}")
    print(f"  MATCHES FOUND: {len(matches)}")
    print(f"{'='*60}")
    for score, video, product in matches:
        print(f"\n  MATCH [score={score}]")
        print(f"  TikTok : {video['title'][:70]}")
        print(f"  Product: {product['name'][:70]}")
        print(f"  ASIN   : {product['asin']}")
        print(f"  URL    : {video['url']}")

    # Save to DB
    print(f"\nSaving {len(matches)} matches to DB...")
    for _, video, product in matches:
        upsert_product(product["asin"], {"tiktok_url": video["url"]})
    print("Done.")


if __name__ == "__main__":
    main()
