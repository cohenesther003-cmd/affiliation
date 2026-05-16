"""
Phase 2 pipeline — for each ready_for_video product:
  1. Find YouTube source video URL
  2. Download the video
  3. Generate Hebrew script with GPT-4o
  4. Update DB status to video_ready or video_failed
"""

from pathlib import Path

from config import CONFIG
from src.db import get_by_status, upsert_product, update_status
from src.phase2.video_source import find_video_url
from src.phase2.downloader import download_video
from src.phase2.script_generator import generate_script


def run(limit: int = None, max_price: float = None, ships_to_israel: bool = None):
    cfg = CONFIG.get("phase2", {})
    output_dir = Path(cfg.get("output_dir", "videos"))
    max_duration = cfg.get("max_video_duration_seconds", 180)

    products = get_by_status("ready_for_video")
    if not products:
        print("  No ready_for_video products to process.")
        return

    if max_price is not None:
        products = [p for p in products if (p.get("price_usd") or 0) <= max_price]
    if ships_to_israel:
        products = [p for p in products if p.get("ships_to_israel")]
    if limit:
        products = products[:limit]

    print(f"Processing {len(products)} products...\n")
    counts = {"video_ready": 0, "video_failed": 0, "skipped": 0}

    for i, product in enumerate(products, 1):
        asin = product["asin"]
        name = (product.get("name") or asin)[:50]
        print(f"[{i}/{len(products)}] {name}")

        # Step 1: find video URL
        video_url = find_video_url(product)
        if not video_url:
            print(f"  [video_source] no video found — skipping")
            counts["skipped"] += 1
            continue

        print(f"  [video_source] {video_url}")

        # Step 2: download video
        downloaded = download_video(asin, video_url, output_dir, max_duration)

        # Step 3: generate Hebrew script (even if download failed — script still useful)
        scripted = generate_script(product, output_dir, cfg)

        # Step 4: update DB
        upsert_product(asin, {"source_video_url": video_url})
        if downloaded and scripted:
            update_status(asin, "video_ready")
            counts["video_ready"] += 1
        else:
            update_status(asin, "video_failed")
            counts["video_failed"] += 1

        print()

    print("=" * 50)
    print(f"  video_ready:  {counts['video_ready']}")
    print(f"  video_failed: {counts['video_failed']}")
    print(f"  skipped:      {counts['skipped']}")
    print("=" * 50)
