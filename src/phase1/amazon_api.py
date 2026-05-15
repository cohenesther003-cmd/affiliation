"""
Amazon product validator — scrapes product pages directly with Playwright.
No PA-API credentials required. Affiliate links are built using your Partner Tag.

Skips any product where rating, review count, or price cannot be extracted.
Keeps going until the DB has 50 complete records (no nulls).
"""

import asyncio
import os
import re

from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page

from src.db import get_by_status, upsert_product, update_status

load_dotenv()

_DELAY_BETWEEN_PAGES = 2500
_ISRAEL_COUNTRY_CODE = "IL"
_NO_SHIP_PHRASES = [
    "does not ship to",
    "not available for",
    "cannot be shipped to",
    "item can't be shipped",
    "unavailable for your delivery location",
    "this item is not available",
]


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
    match = re.search(r"\$(\d[\d,]*\.?\d*)", text.replace(",", ""))
    if match:
        try:
            val = float(match.group(1))
            return val if val > 0 else None
        except ValueError:
            return None
    return None


async def _extract_rating(page: Page) -> float | None:
    # Try title attribute on the star widget first (most reliable)
    for selector in ["#acrPopover", "span[data-hook='rating-out-of-text']"]:
        el = await page.query_selector(selector)
        if el:
            title = await el.get_attribute("title")
            if title:
                r = _parse_rating(title)
                if r:
                    return r
            text = await el.inner_text()
            r = _parse_rating(text)
            if r:
                return r

    # Fallback: first .a-icon-alt span (contains "X.X out of 5 stars")
    els = await page.query_selector_all(".a-icon-alt")
    for el in els:
        text = await el.inner_text()
        r = _parse_rating(text)
        if r:
            return r

    return None


async def _extract_review_count(page: Page) -> int | None:
    for selector in [
        "#acrCustomerReviewText",
        "[data-hook='total-review-count']",
        "#acrCustomerReviewLink",
    ]:
        el = await page.query_selector(selector)
        if el:
            text = (await el.inner_text()).strip()
            count = _parse_review_count(text)
            if count:
                return count
    return None


async def _extract_price(page: Page) -> float | None:
    # Try the most common current Amazon price containers first
    priority_selectors = [
        "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
        "#apex_offerDisplay_desktop .a-price .a-offscreen",
        "#corePrice_feature_div .a-price .a-offscreen",
        "#price_inside_buybox",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        "#sns-base-price",
        ".a-price .a-offscreen",
    ]
    for selector in priority_selectors:
        els = await page.query_selector_all(selector)
        for el in els:
            text = (await el.inner_text()).strip()
            price = _parse_price(text)
            if price:
                return price

    # Fallback: reconstruct from whole + fraction parts
    whole_el = await page.query_selector(".a-price-whole")
    frac_el  = await page.query_selector(".a-price-fraction")
    if whole_el:
        whole = re.sub(r"[^\d]", "", await whole_el.inner_text())
        frac  = re.sub(r"[^\d]", "", await frac_el.inner_text()) if frac_el else "00"
        try:
            price = float(f"{whole}.{frac or '00'}")
            if price > 0:
                return price
        except ValueError:
            pass

    return None


async def _check_ships_to_israel(page: Page) -> bool:
    for selector in [
        "#mir-layout-DELIVERY_BLOCK",
        "#deliveryBlockMessage",
        "#ddmDeliveryMessage",
        "#delivery-message",
        "#availability",
        "#exports_desktop_qualifiedPrograms_feature_div",
    ]:
        el = await page.query_selector(selector)
        if el:
            text = (await el.inner_text()).lower()
            if any(phrase in text for phrase in _NO_SHIP_PHRASES):
                return False

    body_text = (await page.inner_text("body")).lower()
    if any(phrase in body_text for phrase in _NO_SHIP_PHRASES):
        return False

    add_to_cart = await page.query_selector("#add-to-cart-button")
    return bool(add_to_cart)


async def _set_delivery_to_israel(page: Page) -> bool:
    try:
        await page.goto("https://www.amazon.com", wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(2000)
        loc_btn = await page.query_selector("#nav-global-location-popover-link")
        if not loc_btn:
            return False
        await loc_btn.click()
        await page.wait_for_timeout(1500)

        intl_link = await page.query_selector(
            ".a-popover-content a[href*='international'], .GLUXPopoverFooter a, #GLUXCountryListDropdown"
        )
        if intl_link:
            await intl_link.click()
            await page.wait_for_timeout(1000)

        country_select = await page.query_selector(
            "#GLUXCountryList, select[name='GLUXCountryValue'], #GLUXCountryListDropdown select"
        )
        if not country_select:
            return False

        await country_select.select_option(_ISRAEL_COUNTRY_CODE)
        await page.wait_for_timeout(800)

        done_btn = await page.query_selector(
            "input[data-action='GLUXCountryConfirm'], #GLUXConfirmClose, "
            ".a-popover-footer input[type='submit'], span[data-action='GLUXCountryConfirm'] input"
        )
        if done_btn:
            await done_btn.click()
            await page.wait_for_timeout(2000)
            print("  [Israel] Delivery location set to Israel.")
            return True
    except Exception as e:
        print(f"  [Israel] Could not set location: {e}")
    return False


async def _scrape_product(page: Page, asin: str, partner_tag: str) -> dict | None:
    url = f"https://www.amazon.com/dp/{asin}/"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        # Wait for the title to appear before reading anything
        try:
            await page.wait_for_selector("#productTitle", timeout=5000)
        except Exception:
            pass
        await page.wait_for_timeout(_DELAY_BETWEEN_PAGES)
    except Exception as e:
        print(f"    {asin}: load failed — {e}")
        return None

    try:
        body_text = await page.inner_text("body")
    except Exception:
        body_text = ""
    if "robot" in body_text.lower() or "captcha" in body_text.lower():
        print(f"    {asin}: captcha hit — skipping")
        return None

    # Extract all fields
    rating       = await _extract_rating(page)
    review_count = await _extract_review_count(page)
    price        = await _extract_price(page)
    ships        = await _check_ships_to_israel(page)

    # Require all three core fields — skip if any is missing
    if not rating or not review_count or not price:
        missing = [f for f, v in [("rating", rating), ("reviews", review_count), ("price", price)] if not v]
        print(f"    {asin}: incomplete data ({', '.join(missing)} missing) — skipping")
        return None

    # Refine product title
    name = None
    title_el = await page.query_selector("#productTitle")
    if title_el:
        name = (await title_el.inner_text()).strip()[:200] or None

    # Product image URL
    image_url = None
    for img_sel in ["#landingImage", "#imgTagWrapperId img", "#main-image"]:
        img_el = await page.query_selector(img_sel)
        if img_el:
            image_url = (await img_el.get_attribute("data-old-hires")) or \
                        (await img_el.get_attribute("src"))
            if image_url:
                break

    # English description bullets (used by enrich_products.py for translation)
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

    return {
        "affiliate_link":  _affiliate_link(asin, partner_tag),
        "name":            name,
        "rating":          rating,
        "review_count":    review_count,
        "price_usd":       price,
        "ships_to_israel": 1 if ships else 0,
        "image_url":       image_url,
        "description_en":  description_en,
    }


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

        await _set_delivery_to_israel(page)

        for product in products:
            asin = product["asin"]
            print(f"  {asin} — {product.get('name', '')[:50]}")

            data = await _scrape_product(page, asin, partner_tag)

            if data is None:
                update_status(asin, "filtered_out")
                continue

            print(f"    ✓ {data['rating']}★  ${data['price_usd']}  "
                  f"{'🇮🇱' if data['ships_to_israel'] else '✗'}")
            data["status"] = "validated"
            data.pop("description_en", None)  # not a DB column
            upsert_product(asin, data)
            validated += 1

        await browser.close()

    return validated


def run() -> int:
    partner_tag = os.getenv("AMAZON_PARTNER_TAG")
    if not partner_tag:
        raise EnvironmentError(
            "AMAZON_PARTNER_TAG is not set. Copy .env.example → .env and fill it in."
        )

    pending = get_by_status("discovered")
    if not pending:
        print("  No discovered products to validate.")
        return 0

    print(f"  Validating {len(pending)} products (skipping any with missing data)...")
    validated = asyncio.run(_validate_all(pending, partner_tag))
    print(f"  Done — {validated} complete records saved.")
    return validated
