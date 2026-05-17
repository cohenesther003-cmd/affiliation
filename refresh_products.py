"""
Combined refresh: for every ready_for_video product, sets Amazon delivery to Israel,
then re-scrapes price, verifies Israel shipping, and detects unavailable products.

Also re-checks previously unavailable products — restores them if back in stock.

Run: python refresh_products.py
"""

import re
import time
import random
import smtplib
import subprocess
import sys
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.db import init_db, get_all, upsert_product, update_status
from playwright.sync_api import sync_playwright, Page

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass
import os

ISRAEL_ZIP = "6100000"  # Tel Aviv

NO_SHIP_PHRASES = [
    "cannot be shipped to your selected delivery location",
    "does not ship to",
    "item can't be shipped",
    "unavailable for your delivery location",
    "not available for",
]

def detect_shipping_type(text: str) -> str | None:
    """Determine free shipping mode for Israel from page text.

    Important: matches PRECISELY around 'to israel' so we don't false-positive
    on Amazon nav links like 'Free Shipping Zone' or 'FREE International Returns'.
    """
    t = text.lower()

    # Definitive PAID signal: a dollar amount immediately before "shipping to israel"
    # (e.g. "$20.08 Shipping to Israel")
    if re.search(r'\$\s*\d+(?:\.\d+)?\s*shipping to israel', t):
        return "paid"

    # Threshold-based ($49 minimum for free shipping)
    threshold_phrases = [
        "spend over $49", "spend $49 or more", "spend $49.00 or more",
        "$49 or more on eligible", "$49.00 or more on eligible",
        "free shipping when you spend",
        "מעל $49", "מעל 49",
    ]
    if any(p in t for p in threshold_phrases):
        return "free_over_49"

    # Direct free shipping — must say "FREE Shipping/Delivery to Israel" explicitly.
    # If the page shows a Prime price AND a regular price, both may say
    # "free shipping to Israel" — in that case the regular price also has free
    # shipping so we classify as "free", not "free_with_prime".
    # Only use "free_with_prime" when free shipping is exclusively for Prime members
    # (i.e. "with prime" appears but the regular price section has no free shipping).
    free_to_israel = "free shipping to israel" in t or "free delivery to israel" in t
    prime_mentioned = "with prime" in t or "for prime members" in t or "prime members get" in t
    # "exclusively for" signals Prime-only pricing; if the regular price row
    # also says free shipping the "exclusively" phrase will be present for the
    # Prime PRICE but not for the shipping line of the regular option.
    prime_exclusive = "exclusively for" in t or "this price is exclusively" in t
    if free_to_israel and not prime_mentioned:
        return "free"
    if free_to_israel and prime_mentioned and not prime_exclusive:
        # Both Prime and regular price have free shipping
        return "free"
    if free_to_israel and prime_mentioned and prime_exclusive:
        return "free_with_prime"

    return "paid"


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
        return {"price_usd": 0.0, "ships_to_israel": None, "available": True, "shipping_type": None}

    body = ""
    try:
        body = page.inner_text("body").lower()
    except Exception:
        pass

    if "robot" in body or "captcha" in body:
        return {"price_usd": 0.0, "ships_to_israel": None, "available": True, "shipping_type": None}

    # ── Price ──────────────────────────────────────────────────────────
    # .priceToPay is the actual selling price. .basisPrice is the struck-out list price.
    # Read inner_text() of .priceToPay directly — .a-offscreen child may not exist.
    price = 0.0

    def _parse_raw(raw: str) -> float:
        # Collapse whitespace so split renders like "ILS116\n.\n63" become "ILS116.63"
        raw = re.sub(r"\s+", "", raw).replace(",", "")
        m = re.search(r"\$([\d]+\.?\d*)", raw)
        if m:
            v = float(m.group(1))
            return v if v > 0 else 0.0
        m = re.search(r"(?:ILS|₪)([\d]+\.?\d*)", raw)
        if m:
            ils = float(m.group(1))
            return round(ils * ILS_TO_USD, 2) if ils > 0 else 0.0
        return 0.0

    # Strategy 1: prefer the regular (non-Prime) price.
    # When Amazon shows both a Prime price and a regular price, both appear as
    # .priceToPay elements inside the buy-box — Prime first, regular last.
    # Taking the LAST .priceToPay in the container gives the regular price.
    # For products with only one price there is only one element, so last = correct.
    for container in [
        "#corePriceDisplay_desktop_feature_div",
        "#apex_offerDisplay_desktop",
        "#corePrice_feature_div",
    ]:
        try:
            els = page.query_selector_all(f"{container} .priceToPay")
            if els:
                # Last element = regular (non-Prime) price
                v = _parse_raw(els[-1].inner_text().strip())
                if v > 0:
                    price = v
                    break
        except Exception:
            continue

    # Fall back: any .priceToPay on page (last one to prefer regular over Prime)
    if price <= 0:
        try:
            els = page.query_selector_all(".priceToPay")
            if els:
                price = _parse_raw(els[-1].inner_text().strip())
        except Exception:
            pass

    # Strategy 2: legacy buy-box selectors (older page layouts)
    if price <= 0:
        for sel in ["#price_inside_buybox", "#priceblock_ourprice", "#priceblock_dealprice"]:
            try:
                el = page.query_selector(sel)
                if el:
                    price = _parse_raw(el.inner_text().strip())
                    if price > 0:
                        break
            except Exception:
                continue

    # Strategy 3: whole + fraction scoped inside buy-box — avoids variant/seller prices
    if price <= 0:
        try:
            scope = page.query_selector("#corePriceDisplay_desktop_feature_div, #corePrice_feature_div, #apex_offerDisplay_desktop")
            if scope:
                whole = scope.query_selector(".a-price-whole")
                frac = scope.query_selector(".a-price-fraction")
                symbol = scope.query_selector(".a-price-symbol")
                if whole:
                    w = whole.inner_text().replace(",", "").rstrip(".")
                    f = frac.inner_text() if frac else "00"
                    candidate = float(f"{w}.{f}")
                    sym = symbol.inner_text().strip() if symbol else "$"
                    if candidate > 0:
                        price = round(candidate * ILS_TO_USD, 2) if sym in ("₪", "ILS") else candidate
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

    # Availability: phrase check first, then confirm with Add to Cart button.
    # A product without an Add to Cart button has no active buy box → unavailable.
    phrase_unavailable = any(phrase in body for phrase in UNAVAILABLE_PHRASES)
    try:
        add_to_cart = page.query_selector("#add-to-cart-button, #buy-now-button")
        no_buy_box = add_to_cart is None
    except Exception:
        no_buy_box = False
    available = not phrase_unavailable and not no_buy_box

    shipping_type = detect_shipping_type(full_text) if ships_to_israel else None

    return {"price_usd": round(price, 2), "ships_to_israel": ships_to_israel, "available": available, "shipping_type": shipping_type}


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
    no_ship_count = 0
    newly_unavailable_list = []
    restored_list = []
    no_ship_list = []

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
                    newly_unavailable_list.append((prod.get("name") or asin, asin))
                    print(f"[{i}/{len(products)}] {name} — UNAVAILABLE ⚠️")
                else:
                    print(f"[{i}/{len(products)}] {name} — still unavailable")
                time.sleep(random.uniform(2.0, 3.5))
                continue

            # Shipping check — remove products that don't ship to Israel
            if not result["ships_to_israel"]:
                if not was_unavailable:
                    update_status(asin, "filtered_out")
                    no_ship_count += 1
                    no_ship_list.append((prod.get("name") or asin, asin))
                    print(f"[{i}/{len(products)}] {name} — NO ISRAEL SHIPPING ❌")
                time.sleep(random.uniform(2.0, 3.5))
                continue

            # If it was unavailable but is now back, restore it
            if was_unavailable:
                update_status(asin, "ready_for_video")
                restored += 1
                restored_list.append((prod.get("name") or asin, asin))
                print(f"[{i}/{len(products)}] {name} — RESTORED ✅")

            # Save shipping type
            if result.get("shipping_type") and result["shipping_type"] != prod.get("free_shipping_type"):
                upsert_product(asin, {"free_shipping_type": result["shipping_type"]})

            # Price update
            new_price = result["price_usd"]
            if new_price > 0 and abs(new_price - old_price) > 0.05:
                upsert_product(asin, {"price_usd": new_price})
                price_updated += 1
                print(f"[{i}/{len(products)}] {name} — ${old_price:.2f} → ${new_price:.2f} ✓")
            elif not was_unavailable:
                print(f"[{i}/{len(products)}] {name} — ${old_price:.2f} (ok) [{result.get('shipping_type') or '?'}]")

            time.sleep(random.uniform(2.0, 3.5))

        browser.close()

    # Run filter to catch any validated products with bad shipping (e.g. byotools that slipped through)
    from src.phase1.filter import run as run_filter
    filter_passed, filter_removed = run_filter()
    if filter_removed:
        print(f"\n  Filter cleaned up {filter_removed} validated products that failed shipping/quality rules.")

    print(f"\n{'='*55}")
    print(f"  Prices updated:      {price_updated}")
    print(f"  Marked unavailable:  {marked_unavailable}")
    print(f"  No Israel shipping:  {no_ship_count}")
    print(f"  Restored:            {restored}")
    print(f"  Blocked by Amazon:   {blocked}")
    print(f"  Filter removed:      {filter_removed}")
    print(f"{'='*55}")

    # Auto-export and push the site whenever anything changed
    has_site_changes = marked_unavailable or restored or no_ship_count or filter_removed
    if has_site_changes:
        print("\nAuto-updating site...")
        root = Path(__file__).parent
        try:
            subprocess.run([sys.executable, "export_page.py"], cwd=root, check=True)
            subprocess.run(["git", "add", "docs/"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-m", "Daily refresh: update availability and shipping"], cwd=root, check=True)
            subprocess.run(["git", "push"], cwd=root, check=True)
            print("Site updated and pushed ✓")
        except subprocess.CalledProcessError as e:
            print(f"Site update failed: {e}")

    send_email_report(
        price_updated=price_updated,
        newly_unavailable=newly_unavailable_list,
        restored_list=restored_list,
        no_ship_list=no_ship_list,
        blocked=blocked,
        total_active=len(active),
    )


def send_email_report(price_updated, newly_unavailable, restored_list, no_ship_list, blocked, total_active):
    gmail_user = os.getenv("GMAIL_USER", "")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "")
    if not gmail_user or not gmail_pass or "xxxx" in gmail_pass:
        print("\n[Email] No Gmail credentials configured — skipping email report.")
        return

    today = datetime.now().strftime("%d/%m/%Y")
    has_changes = bool(newly_unavailable or restored_list or no_ship_list or price_updated)

    if has_changes:
        subject = f"🔄 דו\"ח יומי {today} — {len(newly_unavailable)} לא זמינים, {len(restored_list)} חזרו למלאי"
    else:
        subject = f"✅ דו\"ח יומי {today} — הכל תקין, אין שינויים"

    lines = [
        f"דו\"ח יומי אוטומטי — {today}",
        f"סה\"כ מוצרים פעילים באתר: {total_active}",
        "",
    ]

    if newly_unavailable:
        lines.append(f"⚠️ מוצרים שהפכו ללא זמינים ({len(newly_unavailable)}):")
        for name, asin in newly_unavailable:
            lines.append(f"  • {name[:60]} ({asin})")
        lines.append("")

    if no_ship_list:
        lines.append(f"🚫 מוצרים שהוסרו — לא נשלחים לישראל ({len(no_ship_list)}):")
        for name, asin in no_ship_list:
            lines.append(f"  • {name[:60]} ({asin})")
        lines.append("")

    if restored_list:
        lines.append(f"✅ מוצרים שחזרו למלאי ({len(restored_list)}):")
        for name, asin in restored_list:
            lines.append(f"  • {name[:60]} ({asin})")
        lines.append("")

    if price_updated:
        lines.append(f"💰 מחירים עודכנו: {price_updated} מוצרים")
        lines.append("")

    if blocked:
        lines.append(f"🚫 חסומים ע\"י אמזון: {blocked} מוצרים")
        lines.append("")

    if not has_changes:
        lines.append("כל המוצרים זמינים ואין שינויים במחירים.")
        lines.append("")

    lines.append("—")
    lines.append("המוצרים שלי — דו\"ח אוטומטי יומי")

    body = "\n".join(lines)
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = gmail_user

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, gmail_user, msg.as_string())
        print(f"\n[Email] Report sent to {gmail_user} ✓")
    except Exception as e:
        print(f"\n[Email] Failed to send: {e}")


if __name__ == "__main__":
    main()
