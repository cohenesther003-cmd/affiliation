"""
Amazon product validator — scrapes product pages directly with Playwright.
No PA-API credentials required. Affiliate links are built using your Partner Tag.

For each 'discovered' product:
  - Visits amazon.com/dp/{ASIN}
  - Extracts rating, review count, price, availability
  - Builds affiliate link: amazon.com/dp/{ASIN}/?tag={PARTNER_TAG}
  - Updates status to 'validated'
"""

import asyncio
import os
import re

from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page

from src.db import get_by_status, upsert_product, update_status

load_dotenv()

_DELAY_BETWEEN_PAGES = 2000  # ms — be polite to Amazon's servers


def _affiliate_link(asin: str, partner_tag: str) -> str:
    return f"https://www.amazon.com/dp/{asin}/?tag={partner_tag}"


def _parse_rating(text: str) -> float | None:
    match = re.search(r"(\d+\.?\d*)\s+out of\s+5", text)
    return float(match.group(1)) if match else None


def _parse_review_count(text: str) -> int | None:
    text = text.replace(",", "").replace(".", "")
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else None


def _parse_price(text: str) -> float | None:
    match = re.search(r"\$(\d+\.?\d*)", text)
    return float(match.group(1)) if match else None


async def _scrape_product(page: Page, asin: str, partner_tag: str) -> dict | None:
    url = f"https://www.amazon.com/dp/{asin}/"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(_DELAY_BETWEEN_PAGES)
    except Exception as e:
        print(f"    Could not load {asin}: {e}")
        return None

    # Check if page is a captcha or unavailable
    page_text = await page.inner_text("body")
    if "robot" in page_text.lower() or "captcha" in page_text.lower():
        print(f"    {asin}: hit captcha — skipping")
        return None

    data: dict = {"affiliate_link": _affiliate_link(asin, partner_tag)}

    # Product title (refine scraped name)
    title_el = await page.query_selector("#productTitle")
    if title_el:
        title = (await title_el.inner_text()).strip()
        if title:
            data["name"] = title[:200]

    # Rating
    rating_el = await page.query_selector(
        "#acrPopover, [data-hook='rating-out-of-text'], .a-icon-alt"
    )
    if rating_el:
        rating_text = await rating_el.get_attribute("title") or await rating_el.inner_text()
        rating = _parse_rating(rating_text or "")
        if rating:
            data["rating"] = rating

    # Review count
    review_el = await page.query_selector(
        "#acrCustomerReviewText, [data-hook='total-review-count']"
    )
    if review_el:
        review_text = (await review_el.inner_text()).strip()
        count = _parse_review_count(review_text)
        if count:
            data["review_count"] = count

    # Price
    for price_selector in [
        ".a-price .a-offscreen",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        ".a-price-whole",
    ]:
        price_el = await page.query_selector(price_selector)
        if price_el:
            price_text = (await price_el.inner_text()).strip()
            price = _parse_price(price_text)
            if price:
                data["price_usd"] = price
                break

    # Availability — proxy for "ships to Israel"
    # If the product has an Add to Cart button, it's available internationally
    add_to_cart = await page.query_selector("#add-to-cart-button, #buy-now-button")
    unavailable_el = await page.query_selector("#availability .a-color-price")
    unavailable_text = ""
    if unavailable_el:
        unavailable_text = (await unavailable_el.inner_text()).lower()

    ships = 1 if add_to_cart and "unavailable" not in unavailable_text else 0
    data["ships_to_israel"] = ships

    return data


async def _validate_all(products: list[dict], partner_tag: str) -> int:
    validated = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )

        for product in products:
            asin = product["asin"]
            print(f"  Validating {asin} — {product.get('name', '')[:50]}")

            data = await _scrape_product(page, asin, partner_tag)

            if data is None:
                update_status(asin, "filtered_out")
                continue

            data["status"] = "validated"
            upsert_product(asin, data)
            validated += 1

        await browser.close()

    return validated


def run() -> int:
    partner_tag = os.getenv("AMAZON_PARTNER_TAG")
    if not partner_tag:
        raise EnvironmentError(
            "AMAZON_PARTNER_TAG is not set.\n"
            "Copy .env.example → .env and set: AMAZON_PARTNER_TAG=eskl20-20"
        )

    pending = get_by_status("discovered")
    if not pending:
        print("  No discovered products to validate.")
        return 0

    print(f"  Validating {len(pending)} products by scraping Amazon product pages...")
    validated = asyncio.run(_validate_all(pending, partner_tag))
    print(f"  Done — {validated} products validated.")
    return validated
