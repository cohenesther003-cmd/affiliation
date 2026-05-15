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

from dotenv import load_dotenv
from openai import OpenAI
from playwright.async_api import async_playwright

from src.db import get_all, upsert_product, init_db

load_dotenv()

PARTNER_TAG = os.getenv("AMAZON_PARTNER_TAG", "eskl20-20")


def translate_to_hebrew(client: OpenAI, description_en: str) -> str:
    resp = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": (
                    "אתה עוזר שמתרגם תיאורי מוצרים לעברית שיווקית. "
                    "כתוב 2-3 משפטים קצרים ומשכנעים בעברית, בשפה פשוטה. "
                    "אל תציין מחיר. אל תכתוב כותרות. רק טקסט רץ."
                ),
            },
            {
                "role": "user",
                "content": f"תרגם את תיאור המוצר הבא לעברית:\n\n{description_en}",
            },
        ],
        max_tokens=300,
    )
    return resp.choices[0].message.content.strip()


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


async def enrich(products: list[dict], openai_client: OpenAI) -> None:
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

            image_url, description_en = await scrape_image_and_description(page, asin)

            updates: dict = {}

            if image_url and not product.get("image_url"):
                updates["image_url"] = image_url
                print(f"  ✓ image captured")
            elif product.get("image_url"):
                print(f"  → image already set, skipping")

            if description_en and not product.get("description_he"):
                try:
                    description_he = translate_to_hebrew(openai_client, description_en)
                    updates["description_he"] = description_he
                    print(f"  ✓ Hebrew description: {description_he[:60]}...")
                except Exception as e:
                    print(f"  ✗ GPT-4o error: {e}")
            elif product.get("description_he"):
                print(f"  → Hebrew description already set, skipping")
            elif not description_en:
                print(f"  ✗ no description found on Amazon page")

            if updates:
                upsert_product(asin, updates)

        await browser.close()


def main():
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print("⚠️  OPENAI_API_KEY not set — will scrape images only, no Hebrew translation")

    init_db()
    all_products = get_all()
    to_enrich = [
        p for p in all_products
        if p["status"] == "ready_for_video"
        and (not p.get("image_url") or not p.get("description_he"))
    ]

    if not to_enrich:
        print("✓ All ready_for_video products already have images and descriptions.")
        return

    print(f"Enriching {len(to_enrich)} products...")
    client = OpenAI(api_key=openai_key) if openai_key else None

    asyncio.run(enrich(to_enrich, client))
    print("Done.")


if __name__ == "__main__":
    main()
