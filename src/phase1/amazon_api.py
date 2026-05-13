"""
Amazon product validator — scrapes product pages directly with Playwright.
No PA-API credentials required. Affiliate links are built using your Partner Tag.

Flow:
  1. Set Amazon delivery location to Israel (once per session)
  2. For each 'discovered' product, visit amazon.com/dp/{ASIN}
  3. Extract rating, review count, price
  4. Check Israel shipping: look for "does not ship to" message on the page
  5. Build affiliate link: amazon.com/dp/{ASIN}/?tag={PARTNER_TAG}
  6. Update status to 'validated'
"""

import asyncio
import os
import re

from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page

from src.db import get_by_status, upsert_product, update_status

load_dotenv()

_DELAY_BETWEEN_PAGES = 2500  # ms — be polite to Amazon's servers
_ISRAEL_COUNTRY_CODE = "IL"
_ISRAEL_ZIP = "6100000"  # Tel Aviv postal code


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


async def _set_delivery_to_israel(page: Page) -> bool:
    """
    Change Amazon delivery location to Israel for this browser session.
    Returns True if successful, False if the flow failed.
    """
    try:
        await page.goto("https://www.amazon.com", wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(2000)

        # Click the "Deliver to" location widget in the nav
        loc_btn = await page.query_selector("#nav-global-location-popover-link")
        if not loc_btn:
            print("  [Israel check] Could not find location selector — skipping.")
            return False
        await loc_btn.click()
        await page.wait_for_timeout(1500)

        # The modal shows a US zip input. Look for "international address" link.
        intl_link = await page.query_selector(
            ".a-popover-content a[href*='international'], "
            ".GLUXPopoverFooter a, "
            "#GLUXCountryListDropdown"
        )
        if intl_link:
            await intl_link.click()
            await page.wait_for_timeout(1000)

        # Find the country dropdown and select Israel
        country_select = await page.query_selector(
            "#GLUXCountryList, select[name='GLUXCountryValue'], #GLUXCountryListDropdown select"
        )
        if not country_select:
            print("  [Israel check] Country dropdown not found — skipping.")
            return False

        await country_select.select_option(_ISRAEL_COUNTRY_CODE)
        await page.wait_for_timeout(800)

        # Click Done / Apply / Confirm
        done_btn = await page.query_selector(
            "input[data-action='GLUXCountryConfirm'], "
            "#GLUXConfirmClose, "
            ".a-popover-footer input[type='submit'], "
            "span[data-action='GLUXCountryConfirm'] input"
        )
        if done_btn:
            await done_btn.click()
            await page.wait_for_timeout(2000)
            print("  [Israel check] Delivery location set to Israel.")
            return True

        print("  [Israel check] Done button not found — skipping.")
        return False

    except Exception as e:
        print(f"  [Israel check] Error setting Israel location: {e}")
        return False


async def _check_ships_to_israel(page: Page) -> bool:
    """
    Check current product page for Israel shipping availability.
    Must be called AFTER _set_delivery_to_israel().
    """
    # Phrases Amazon shows when a product doesn't ship to the selected country
    _NO_SHIP_PHRASES = [
        "does not ship to",
        "not available for",
        "cannot be shipped to",
        "item can't be shipped",
        "unavailable for your delivery location",
        "this item is not available",
    ]

    # Check delivery/shipping block text
    for selector in [
        "#mir-layout-DELIVERY_BLOCK",
        "#deliveryBlockMessage",
        "#ddmDeliveryMessage",
        "#delivery-message",
        "#availability",
        "#exports_desktop_qualifiedPrograms_feature_div",
        "#exports_desktop_unifiedProgramEligibility_feature_div",
    ]:
        el = await page.query_selector(selector)
        if el:
            text = (await el.inner_text()).lower()
            if any(phrase in text for phrase in _NO_SHIP_PHRASES):
                return False

    # Also check full page body for hard blocks
    body_text = (await page.inner_text("body")).lower()
    if any(phrase in body_text for phrase in _NO_SHIP_PHRASES):
        return False

    # If "Add to Cart" exists and no blocking message found → ships
    add_to_cart = await page.query_selector("#add-to-cart-button")
    return bool(add_to_cart)


async def _scrape_product(page: Page, asin: str, partner_tag: str) -> dict | None:
    url = f"https://www.amazon.com/dp/{asin}/"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(_DELAY_BETWEEN_PAGES)
    except Exception as e:
        print(f"    Could not load {asin}: {e}")
        return None

    # Captcha / bot detection check
    page_text = await page.inner_text("body")
    if "robot" in page_text.lower() or "captcha" in page_text.lower():
        print(f"    {asin}: hit captcha — skipping")
        return None

    data: dict = {"affiliate_link": _affiliate_link(asin, partner_tag)}

    # Product title
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

    # Real Israel shipping check
    ships = await _check_ships_to_israel(page)
    data["ships_to_israel"] = 1 if ships else 0

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

        # Set delivery location to Israel once for the whole session
        israel_set = await _set_delivery_to_israel(page)
        if not israel_set:
            print("  [Warning] Could not set Israel delivery location.")
            print("  Israel shipping check will use page text fallback only.")

        for product in products:
            asin = product["asin"]
            print(f"  Validating {asin} — {product.get('name', '')[:50]}")

            data = await _scrape_product(page, asin, partner_tag)

            if data is None:
                update_status(asin, "filtered_out")
                continue

            ships_label = "ships to IL" if data.get("ships_to_israel") else "NO Israel shipping"
            print(f"    → rating={data.get('rating', 'N/A')}  price=${data.get('price_usd', 'N/A')}  {ships_label}")

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

    print(f"  Validating {len(pending)} products (with real Israel shipping check)...")
    validated = asyncio.run(_validate_all(pending, partner_tag))
    print(f"  Done — {validated} products validated.")
    return validated
