"""
Re-verifies Israel shipping for all ready_for_video products.
Sets Amazon delivery location to Israel (Tel Aviv) before checking each product.
Updates ships_to_israel in DB and moves non-shipping products to filtered_out.

Run: python verify_israel_shipping.py
"""

import time
import random
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))

from src.db import init_db, get_all, upsert_product, update_status
from playwright.sync_api import sync_playwright, Page

NO_SHIP_PHRASES = [
    "cannot be shipped to your selected delivery location",
    "does not ship to",
    "not available for",
    "cannot be shipped to",
    "item can't be shipped",
    "unavailable for your delivery location",
    "this item is not available",
    "no featured offers available",
]

ISRAEL_ZIP = "6100000"  # Tel Aviv


def set_israel_delivery(page: Page) -> bool:
    """Set Amazon delivery location to Israel. Returns True if successful."""
    try:
        page.goto("https://www.amazon.com/", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(1500)

        # Click "Deliver to" location widget
        loc = page.query_selector("#nav-global-location-popover-link")
        if not loc:
            loc = page.query_selector("#glow-ingress-block")
        if not loc:
            return False
        loc.click()
        page.wait_for_timeout(1000)

        # Enter zip/postal code
        zip_input = page.query_selector("input[data-action-type='SELECT_LOCATION']")
        if not zip_input:
            zip_input = page.query_selector("#GLUXZipUpdateInput")
        if not zip_input:
            return False

        zip_input.fill(ISRAEL_ZIP)
        page.wait_for_timeout(500)

        apply_btn = page.query_selector("[data-action-type='LOCATION_APPLY_BTN']")
        if not apply_btn:
            apply_btn = page.query_selector("#GLUXZipUpdate")
        if apply_btn:
            apply_btn.click()
            page.wait_for_timeout(1500)

        # Confirm via "Done" if it appears
        done = page.query_selector("[data-action-type='GW_DISMISS']")
        if not done:
            done = page.query_selector(".a-popover-footer .a-button-primary")
        if done:
            done.click()
            page.wait_for_timeout(1000)

        return True
    except Exception as e:
        print(f"  [location] could not set Israel delivery: {e}")
        return False


def check_ships_to_israel(page: Page, asin: str) -> bool:
    """Visit product page and return True if it ships to Israel."""
    try:
        page.goto(f"https://www.amazon.com/dp/{asin}/", wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(random.randint(1500, 2500))
    except Exception:
        return False

    body = ""
    try:
        body = page.inner_text("body").lower()
    except Exception:
        pass

    if "robot" in body or "captcha" in body:
        return None  # can't determine

    # Check delivery sections
    delivery_text = ""
    for sel in ["#mir-layout-DELIVERY_BLOCK", "#deliveryBlockMessage",
                "#ddmDeliveryMessage", "#delivery-message", "#availability",
                "#exports_desktop_qualifiedPrograms_feature_div"]:
        try:
            el = page.query_selector(sel)
            if el:
                delivery_text += el.inner_text().lower() + " "
        except Exception:
            pass

    # Always also check full body — the warning can appear anywhere on the page
    full_text = delivery_text + " " + body

    # If any no-ship phrase is found → doesn't ship
    if any(phrase in full_text for phrase in NO_SHIP_PHRASES):
        return False

    return True


def main():
    init_db()
    products = [p for p in get_all() if p["status"] in ("ready_for_video", "video_failed", "video_ready")]
    print(f"Verifying Israel shipping for {len(products)} products...\n")

    ships = 0
    no_ship = 0
    unknown = 0

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

        print("Setting delivery location to Israel (Tel Aviv)...")
        ok = set_israel_delivery(page)
        print(f"  Location set: {'✓' if ok else '✗ (will check anyway)'}\n")

        for i, prod in enumerate(products, 1):
            asin = prod["asin"]
            name = (prod.get("name") or asin)[:45]

            result = check_ships_to_israel(page, asin)

            if result is None:
                print(f"[{i}/{len(products)}] {name} — BLOCKED (skipping)")
                unknown += 1
            elif result:
                print(f"[{i}/{len(products)}] {name} — ✓ ships to Israel")
                upsert_product(asin, {"ships_to_israel": 1})
                ships += 1
            else:
                print(f"[{i}/{len(products)}] {name} — ✗ does NOT ship to Israel")
                upsert_product(asin, {"ships_to_israel": 0})
                update_status(asin, "filtered_out")
                no_ship += 1

            # Re-set location every 5 products — Amazon resets between navigations
            if i % 5 == 0:
                set_israel_delivery(page)

            time.sleep(random.uniform(2.0, 3.5))

        browser.close()

    print(f"\n{'='*50}")
    print(f"  Ships to Israel:     {ships}")
    print(f"  Does NOT ship:       {no_ship}  → moved to filtered_out")
    print(f"  Unknown (blocked):   {unknown}")
    print(f"{'='*50}")
    print(f"\nRun: python export_page.py && git add docs/index.html && git commit -m 'Fix shipping data' && git push")


if __name__ == "__main__":
    main()
