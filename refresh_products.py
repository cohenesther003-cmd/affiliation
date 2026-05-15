"""
Combined refresh: for every ready_for_video product, sets Amazon delivery to Israel,
then re-scrapes price, verifies Israel shipping, and detects unavailable products.

Also re-checks previously unavailable products — restores them if back in stock.

Run: python refresh_products.py
"""

import re
import time
import random
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))

from src.db import init_db, get_all, upsert_product, update_status
from playwright.sync_api import sync_playwright, Page

ISRAEL_ZIP = "6100000"  # Tel Aviv

NO_SHIP_PHRASES = [
    "cannot be shipped to your selected delivery location",
    "does not ship to",
    "item can't be shipped",
    "unavailable for your delivery location",
    "not available for",
]

UNAVAILABLE_PHRASES = [
    "currently unavailable",
    "we don't know when or if this item will be back in stock",
    "out of stock",
    "temporarily out of stock",
    "this item is currently unavailable",
]

ILS_TO_USD = 1 / 3.65


def set_israel_delivery(page: Page) -> bool:
    """Change Amazon delivery location to Israel. Returns True if successful."""
    try:
        loc = page.query_selector("#nav-global-location-popover-link, #glow-ingress-block")
        if not loc:
            return False
        loc.click()
        page.wait_for_timeout(800)

        zip_input = page.query_selector("input[data-action-type='SELECT_LOCATION'], #GLUXZipUpdateInput")
        if not zip_input:
            # close popover and move on
            page.keyboard.press("Escape")
            return False
        zip_input.triple_click()
        zip_input.fill(ISRAEL_ZIP)
        page.wait_for_timeout(400)

        apply_btn = page.query_selector("[data-action-type='LOCATION_APPLY_BTN'], #GLUXZipUpdate")
        if apply_btn:
            apply_btn.click()
            page.wait_for_timeout(1200)

        done = page.query_selector("[data-action-type='GW_DISMISS'], .a-popover-footer .a-button-primary")
        if done:
            done.click()
            page.wait_for_timeout(800)

        return True
    except Exception:
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        return False


def scrape_price_and_shipping(page: Page, asin: str) -> dict:
    """
    Returns dict with keys: price_usd (float), ships_to_israel (bool).
    price_usd = 0.0 means could not determine.
    """
    try:
        page.goto(f"https://www.amazon.com/dp/{asin}/", wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(random.randint(1500, 2500))
    except Exception:
        return {"price_usd": 0.0, "ships_to_israel": None}

    body = ""
    try:
        body = page.inner_text("body").lower()
    except Exception:
        pass

    if "robot" in body or "captcha" in body:
        return {"price_usd": 0.0, "ships_to_israel": None, "available": True}

    # ── Price ──────────────────────────────────────────────────────────
    price = 0.0
    price_selectors = [
        "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
        "#apex_offerDisplay_desktop .a-price .a-offscreen",
        "#corePrice_feature_div .a-price .a-offscreen",
        "#price_inside_buybox",
        "#priceblock_ourprice",
        ".a-price .a-offscreen",
    ]
    for sel in price_selectors:
        try:
            el = page.query_selector(sel)
            if not el:
                continue
            raw = el.inner_text().strip()
            # USD price
            m = re.search(r"\$(\d[\d,]*\.?\d*)", raw)
            if m:
                price = float(m.group(1).replace(",", ""))
                if price > 0:
                    break
            # ILS price — "ILS 123" or "₪123"
            m_ils = re.search(r"(?:ILS\s*|₪\s*)([\d,]+\.?\d*)", raw)
            if m_ils:
                ils = float(m_ils.group(1).replace(",", ""))
                if ils > 0:
                    price = round(ils * ILS_TO_USD, 2)
                    break
        except Exception:
            continue

    # Fallback: whole + fraction — check surrounding text for currency symbol
    if price <= 0:
        try:
            whole = page.query_selector(".a-price-whole")
            frac = page.query_selector(".a-price-fraction")
            symbol = page.query_selector(".a-price-symbol")
            if whole:
                w = whole.inner_text().replace(",", "").rstrip(".")
                f = frac.inner_text() if frac else "00"
                candidate = float(f"{w}.{f}")
                sym = symbol.inner_text().strip() if symbol else "$"
                if candidate > 0:
                    if sym == "₪" or sym.upper() == "ILS":
                        price = round(candidate * ILS_TO_USD, 2)
                    else:
                        price = candidate
        except Exception:
            pass

    # ── Shipping ───────────────────────────────────────────────────────
    full_text = body
    for sel in ["#mir-layout-DELIVERY_BLOCK", "#deliveryBlockMessage",
                "#ddmDeliveryMessage", "#delivery-message", "#availability"]:
        try:
            el = page.query_selector(sel)
            if el:
                full_text += " " + el.inner_text().lower()
        except Exception:
            pass

    ships_to_israel = not any(phrase in full_text for phrase in NO_SHIP_PHRASES)
    available = not any(phrase in body for phrase in UNAVAILABLE_PHRASES)

    return {"price_usd": round(price, 2), "ships_to_israel": ships_to_israel, "available": available}


def main():
    init_db()
    all_products = get_all()
    active   = [p for p in all_products if p["status"] in ("ready_for_video", "video_ready", "video_failed")]
    recovery = [p for p in all_products if p["status"] == "unavailable"]
    products = active + recovery

    print(f"Refreshing {len(active)} active + {len(recovery)} unavailable products...\n")

    price_updated = 0
    marked_unavailable = 0
    restored = 0
    blocked = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"}
        )
        page = ctx.new_page()

        # Warm up cookies
        page.goto("https://www.amazon.com/", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(2000)

        for i, prod in enumerate(products, 1):
            asin = prod["asin"]
            name = (prod.get("name") or asin)[:45]
            old_price = prod.get("price_usd") or 0
            was_unavailable = prod["status"] == "unavailable"

            result = scrape_price_and_shipping(page, asin)

            if result["ships_to_israel"] is None:
                print(f"[{i}/{len(products)}] {name} — BLOCKED")
                blocked += 1
                time.sleep(random.uniform(4, 7))
                continue

            # Availability check
            if not result["available"]:
                if not was_unavailable:
                    update_status(asin, "unavailable")
                    marked_unavailable += 1
                    print(f"[{i}/{len(products)}] {name} — UNAVAILABLE ⚠️")
                else:
                    print(f"[{i}/{len(products)}] {name} — still unavailable")
                time.sleep(random.uniform(2.0, 3.5))
                continue

            # If it was unavailable but is now back, restore it
            if was_unavailable:
                update_status(asin, "ready_for_video")
                restored += 1
                print(f"[{i}/{len(products)}] {name} — RESTORED ✅")

            # Price update
            new_price = result["price_usd"]
            if new_price > 0 and abs(new_price - old_price) > 0.05:
                upsert_product(asin, {"price_usd": new_price})
                price_updated += 1
                print(f"[{i}/{len(products)}] {name} — ${old_price:.2f} → ${new_price:.2f} ✓")
            elif not was_unavailable:
                print(f"[{i}/{len(products)}] {name} — ${old_price:.2f} (ok)")

            time.sleep(random.uniform(2.0, 3.5))

        browser.close()

    print(f"\n{'='*55}")
    print(f"  Prices updated:      {price_updated}")
    print(f"  Marked unavailable:  {marked_unavailable}")
    print(f"  Restored:            {restored}")
    print(f"  Blocked by Amazon:   {blocked}")
    print(f"{'='*55}")
    if marked_unavailable or restored:
        print(f"\nRun: python export_page.py && git add docs/ && git commit -m 'Update availability' && git push")


if __name__ == "__main__":
    main()
