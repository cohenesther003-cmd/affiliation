"""
Backfill image_url and description_he for existing ready_for_video products.

Run: python enrich_products.py

- Scrapes Amazon product pages for image URL + English description bullets
- Translates to Hebrew with GPT-4o
- Saves both fields to the DB
- Safe to re-run: skips products that already have both fields
- Requires OPENAI_API_KEY in .env
"""

import asyncio
import os
import random
import subprocess

from dotenv import load_dotenv
from playwright.async_api import async_playwright

from src.db import get_all, upsert_product, init_db

load_dotenv()

PARTNER_TAG = os.getenv("AMAZON_PARTNER_TAG", "eskl20-20")


def generate_hebrew_description(product: dict) -> str:
    name     = (product.get("name") or product["asin"])[:120]
    category = product.get("category") or ""
    rating   = product.get("rating") or 0
    reviews  = product.get("review_count") or 0
    price    = product.get("price_usd") or 0
    prompt = (
        f"כתוב תיאור מוצר שיווקי בעברית (4-5 משפטים) עבור המוצר: {name}. "
        f"קטגוריה: {category}. דירוג: {rating}/5 ({reviews} ביקורות). מחיר: ${price:.2f}. "
        "הכלל: מה המוצר עושה, מי ירוויח ממנו, 2-3 יתרונות מרכזיים, ולמה כדאי לרכוש אותו. "
        "סגנון שיווקי ידידותי, עברית טבעית ושוטפת. ללא כותרות, ללא מחיר, ללא מספור, ללא ניקוד."
    )
    result = subprocess.run(
        ["claude", "--print", "-p", prompt],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())
    return result.stdout.strip()


async def scrape_image_and_description(page, asin: str) -> tuple[str | None, str | None]:
    url = f"https://www.amazon.com/dp/{asin}/"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
        await page.wait_for_timeout(random.randint(2000, 3500))
    except Exception as e:
        print(f"  {asin}: load failed — {e}")
        return None, None

    body_text = await page.inner_text("body")
    if "robot" in body_text.lower() or "captcha" in body_text.lower():
        print(f"  {asin}: captcha — skipping")
        return None, None

    # Image
    image_url = None
    for sel in ["#landingImage", "#imgTagWrapperId img", "#main-image"]:
        el = await page.query_selector(sel)
        if el:
            image_url = (await el.get_attribute("data-old-hires")) or \
                        (await el.get_attribute("src"))
            if image_url:
                break

    # Description bullets
    description_en = None
    bullet_els = await page.query_selector_all("#feature-bullets ul li span.a-list-item")
    if bullet_els:
        bullets = []
        for el in bullet_els[:6]:
            text = (await el.inner_text()).strip()
            if text:
                bullets.append(text)
        if bullets:
            description_en = "\n".join(bullets)

    return image_url, description_en


async def enrich(products: list[dict]) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )

        for i, product in enumerate(products):
            asin = product["asin"]
            name = (product.get("name") or asin)[:50]
            print(f"[{i+1}/{len(products)}] {asin} — {name}")

            image_url, _ = await scrape_image_and_description(page, asin)

            updates: dict = {}

            if image_url and not product.get("image_url"):
                updates["image_url"] = image_url
                print(f"  ✓ image captured")
            elif product.get("image_url"):
                print(f"  → image already set, skipping")

            if not product.get("description_he"):
                try:
                    description_he = generate_hebrew_description(product)
                    updates["description_he"] = description_he
                    print(f"  ✓ Hebrew: {description_he[:70]}...")
                except Exception as e:
                    print(f"  ✗ Claude error: {e}")
            else:
                print(f"  → Hebrew description already set, skipping")

            if updates:
                upsert_product(asin, updates)

        await browser.close()


def main():
    init_db()
    import sqlite3
    from src.db import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE products SET description_he = NULL "
        "WHERE status IN ('ready_for_video','video_ready','video_failed') "
        "AND description_he IS NOT NULL AND length(description_he) < 200"
    )
    conn.commit()
    conn.close()

    all_products = get_all()
    to_enrich = [
        p for p in all_products
        if p["status"] in ("ready_for_video", "video_ready", "video_failed")
        and (not p.get("image_url") or not p.get("description_he"))
    ]

    if not to_enrich:
        print("✓ All ready_for_video products already have images and descriptions.")
        return

    print(f"Enriching {len(to_enrich)} products...")
    asyncio.run(enrich(to_enrich))
    print("Done.")


if __name__ == "__main__":
    main()
