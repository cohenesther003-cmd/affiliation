"""
Re-scrapes Amazon ratings for products that currently have rating=0.
Uses slower speed + better selectors to avoid bot detection.

Run: python update_ratings.py
"""

import re
import time
import random
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))

from src.db import init_db, get_all, upsert_product
from playwright.sync_api import sync_playwright

RATING_SELECTORS = [
    "#acrPopover .a-icon-alt",
    "span[data-hook='rating-out-of-text']",
    "#averageCustomerReviews .a-icon-alt",
    ".a-icon-alt",
]
REVIEW_SELECTORS = [
    "#acrCustomerReviewText",
    "[data-hook='total-review-count']",
]

def get_text(page, selectors):
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                t = el.inner_text().strip()
                if t:
                    return t
        except Exception:
            pass
    return ""


def scrape_rating(page, asin):
    url = f"https://www.amazon.com/dp/{asin}/"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(random.randint(1800, 3000))
    except Exception:
        return None, None

    body = ""
    try:
        body = page.inner_text("body").lower()
    except Exception:
        pass

    if "robot" in body or "captcha" in body or "enter the characters" in body:
        return None, None

    rating = 0.0
    rating_raw = get_text(page, RATING_SELECTORS)
    m = re.search(r"(\d+\.?\d*)\s*out of\s*5", rating_raw, re.IGNORECASE)
    if m:
        try:
            rating = round(float(m.group(1)), 1)
        except ValueError:
            pass

    review_count = 0
    review_raw = get_text(page, REVIEW_SELECTORS)
    m2 = re.search(r"([\d,]+)", review_raw)
    if m2:
        try:
            review_count = int(m2.group(1).replace(",", ""))
        except ValueError:
            pass

    return rating, review_count


def main():
    init_db()
    products = [p for p in get_all() if (p.get("rating") or 0) == 0 and p["status"] == "ready_for_video"]
    print(f"Updating ratings for {len(products)} products...\n")

    updated = 0
    bot_blocked = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            }
        )
        page = ctx.new_page()

        # Warm up cookies
        page.goto("https://www.amazon.com/", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(2000)

        for i, prod in enumerate(products, 1):
            asin = prod["asin"]
            name = (prod.get("name") or asin)[:45]

            # Re-warm cookies every 30 products
            if i > 1 and i % 30 == 1:
                page.goto("https://www.amazon.com/", wait_until="domcontentloaded", timeout=20000)
                page.wait_for_timeout(2500)

            rating, review_count = scrape_rating(page, asin)

            if rating is None:
                print(f"[{i}/{len(products)}] {name} — BLOCKED")
                bot_blocked += 1
                time.sleep(random.uniform(4, 7))
                continue

            if rating > 0:
                upsert_product(asin, {"rating": rating, "review_count": review_count})
                updated += 1
                print(f"[{i}/{len(products)}] {name} — ★{rating} ({review_count} reviews) ✓")
            else:
                print(f"[{i}/{len(products)}] {name} — no rating on Amazon page")

            # Slower: 2.5–4.5s between requests
            time.sleep(random.uniform(2.5, 4.5))

        browser.close()

    print(f"\nDone — {updated} updated, {bot_blocked} blocked by Amazon.")


if __name__ == "__main__":
    main()
