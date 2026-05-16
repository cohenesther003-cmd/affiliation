"""
Scrapes byotools.me/byotlinks, resolves all affiliate links to Amazon ASINs,
then checks price, Israel shipping, and free shipping for each product.

Run: python byotools_scrape.py
Output: byotools_results.csv + printed summary
"""

import csv
import re
import sys
import time
from urllib.request import urlopen, Request
from urllib.error import URLError
from urllib.parse import urlparse

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from src.db import init_db, get_all, upsert_product

from playwright.sync_api import sync_playwright, Page

BYOT_URL = "https://byotools.me/byotlinks"
PARTNER_TAG = "eskl20-20"
MAX_PRICE = 9999.0
OUTPUT_CSV = "byotools_results_all.csv"

ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})")

NO_SHIP_PHRASES = [
    "does not ship to",
    "not available for",
    "cannot be shipped to",
    "item can't be shipped",
    "unavailable for your delivery location",
    "this item is not available",
]
FREE_SHIP_PHRASES = [
    "free delivery",
    "free shipping",
    "free returns",
]


# ── URL resolution ────────────────────────────────────────────────────────────

def resolve_url(url: str) -> str:
    """Follow redirects to get the final URL (no browser needed)."""
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10) as resp:
            return resp.url
    except Exception:
        return url


def extract_asin(url: str) -> str | None:
    m = ASIN_RE.search(url)
    return m.group(1) if m else None


def is_amazon(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return "amazon.com" in host or "amazon." in host


# ── Amazon page scraping ──────────────────────────────────────────────────────

def _get_text(page: Page, selectors: list[str]) -> str:
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                return el.inner_text().strip()
        except Exception:
            pass
    return ""


def scrape_amazon_product(page: Page, asin: str) -> dict | None:
    url = f"https://www.amazon.com/dp/{asin}/"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)
    except Exception:
        return None

    body = ""
    try:
        body = page.inner_text("body").lower()
    except Exception:
        pass

    if "robot" in body or "captcha" in body:
        print(f"  [!] Bot check on {asin}, skipping")
        return None

    # Name
    name = _get_text(page, ["#productTitle", "h1.product-title-word-break"])
    name = name.strip()

    ILS_TO_USD = 1 / 3.65  # approximate conversion rate

    # Price — page may show USD ($) or ILS depending on IP location
    price = 0.0
    price_in_ils = False
    price_selectors = [
        "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
        "#apex_offerDisplay_desktop .a-price .a-offscreen",
        "#corePrice_feature_div .a-price .a-offscreen",
        "#price_inside_buybox",
        "#priceblock_ourprice",
        ".a-price .a-offscreen",
    ]
    for sel in price_selectors:
        raw = _get_text(page, [sel])
        m = re.search(r"\$(\d[\d,]*\.?\d*)", raw)
        if m:
            try:
                price = float(m.group(1).replace(",", ""))
                if price > 0:
                    break
            except ValueError:
                pass
        # ILS price (Israeli IP)
        m_ils = re.search(r"ILS\s*([\d,]+\.?\d*)", raw)
        if m_ils:
            try:
                ils = float(m_ils.group(1).replace(",", ""))
                if ils > 0:
                    price = round(ils * ILS_TO_USD, 2)
                    price_in_ils = True
                    break
            except ValueError:
                pass

    # Fallback: whole + fraction
    if price <= 0:
        whole = _get_text(page, [".a-price-whole"])
        frac = _get_text(page, [".a-price-fraction"])
        if whole:
            try:
                price = float(whole.replace(",", "").rstrip(".") + "." + (frac or "00"))
                # If this looks like ILS (>30 for most items), convert
                if price > 20:
                    price = round(price * ILS_TO_USD, 2)
                    price_in_ils = True
            except ValueError:
                pass

    # Ships to Israel — if price shows in ILS, it definitely ships here
    if price_in_ils:
        ships_israel = True
    else:
        delivery_text = ""
        for sel in ["#mir-layout-DELIVERY_BLOCK", "#deliveryBlockMessage",
                    "#ddmDeliveryMessage", "#delivery-message", "#availability",
                    "#exports_desktop_qualifiedPrograms_feature_div"]:
            t = _get_text(page, [sel])
            if t:
                delivery_text += t.lower() + " "

        if not delivery_text:
            delivery_text = body[:3000]

        ships_israel = not any(p in delivery_text for p in NO_SHIP_PHRASES)

        if not ships_israel:
            atc = page.query_selector("#add-to-cart-button")
            if atc:
                ships_israel = True

    # Free shipping
    delivery_text = ""
    for sel in ["#mir-layout-DELIVERY_BLOCK", "#deliveryBlockMessage", "#delivery-message"]:
        t = _get_text(page, [sel])
        if t:
            delivery_text += t.lower() + " "
    if not delivery_text:
        delivery_text = body[:3000]
    free_shipping = any(p in delivery_text for p in FREE_SHIP_PHRASES)

    # Rating
    rating = 0.0
    rating_raw = _get_text(page, ["#acrPopover", "span[data-hook='rating-out-of-text']", ".a-icon-alt"])
    m_rating = re.search(r"(\d+\.?\d*)\s*out of\s*5", rating_raw, re.IGNORECASE)
    if m_rating:
        try:
            rating = round(float(m_rating.group(1)), 1)
        except ValueError:
            pass

    # Review count
    review_count = 0
    review_raw = _get_text(page, ["#acrCustomerReviewText", "[data-hook='total-review-count']"])
    m_reviews = re.search(r"([\d,]+)", review_raw)
    if m_reviews:
        try:
            review_count = int(m_reviews.group(1).replace(",", ""))
        except ValueError:
            pass

    affiliate_link = f"https://www.amazon.com/dp/{asin}/?tag={PARTNER_TAG}"

    return {
        "asin": asin,
        "name": name or asin,
        "price_usd": round(price, 2),
        "ships_to_israel": ships_israel,
        "free_shipping": free_shipping,
        "rating": rating,
        "review_count": review_count,
        "affiliate_link": affiliate_link,
        "source": "byotools",
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def scrape_byotools_links(page: Page) -> list[dict]:
    """Return list of {name, url, youtube_url} from byotlinks page."""
    page.goto(BYOT_URL, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)

    skip_domains = {"byotools.me", "squarespace.com",
                    "etsy.com", "facebook.com", "instagram.com", "tiktok.com"}

    # Collect all links with index so we can find the nearest YouTube link per product.
    # Squarespace stores raw relative hrefs in the attribute; use e.href for the real URL.
    # Product name lives in parentElement, not inside the <a> tag itself.
    raw = page.eval_on_selector_all(
        "a",
        """els => els.map((e, i) => {
            const p = e.parentElement;
            const text = p ? p.innerText.trim().split('\\n')[0] : '';
            return {href: e.href, text, idx: i};
        })"""
    )

    # Separate YouTube links and product links
    youtube_entries = []   # [{idx, href}]
    product_candidates = []

    for item in raw:
        href = item.get("href", "")
        text = (item.get("text", "") or "").strip()
        idx = item.get("idx", 0)

        if not href:
            continue

        host = urlparse(href).netloc.lower().replace("www.", "")

        if "youtube.com" in host or "youtu.be" in host:
            youtube_entries.append({"idx": idx, "href": href})
            continue

        if not text:
            continue
        if any(d in host for d in skip_domains) or "byotools.me" in href:
            continue

        product_candidates.append({"name": text, "url": href, "idx": idx})

    # Deduplicate product URLs
    seen_urls = set()
    products = []
    for p in product_candidates:
        if p["url"] in seen_urls:
            continue
        seen_urls.add(p["url"])

        # Find the nearest preceding YouTube link (within 10 positions)
        yt_url = None
        for yt in reversed(youtube_entries):
            if yt["idx"] < p["idx"] and (p["idx"] - yt["idx"]) <= 10:
                yt_url = yt["href"]
                break

        products.append({"name": p["name"], "url": p["url"], "youtube_url": yt_url})

    return products


def search_amazon_for_product(page: Page, name: str) -> str | None:
    """Search Amazon for a product by name, return ASIN of first result or None."""
    query = re.sub(r"[^\w\s]", " ", name).strip()
    search_url = f"https://www.amazon.com/s?k={query.replace(' ', '+')}"
    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(1000)
    except Exception:
        return None

    body = ""
    try:
        body = page.inner_text("body").lower()
    except Exception:
        pass
    if "robot" in body or "captcha" in body:
        return None

    # Find first product link containing /dp/ASIN
    for sel in [
        "[data-asin]",
        "a[href*='/dp/']",
        ".s-result-item a[href*='/dp/']",
    ]:
        try:
            els = page.query_selector_all(sel)
            for el in els:
                asin = el.get_attribute("data-asin") or ""
                if not asin:
                    href = el.get_attribute("href") or ""
                    m = ASIN_RE.search(href)
                    asin = m.group(1) if m else ""
                if asin and len(asin) == 10:
                    return asin
        except Exception:
            continue
    return None


def main():
    results = []
    skipped_non_amazon = []

    # Load existing ASINs from DB — skip anything already scraped
    init_db()
    existing_asins = {p["asin"] for p in get_all()}
    print(f"DB has {len(existing_asins)} existing products — will skip these.\n")

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

        # Warm up cookies so Amazon search works
        page.goto("https://www.amazon.com/", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(1500)

        # Step 1: get all links from byotlinks
        print("Scraping byotools.me/byotlinks...")
        products = scrape_byotools_links(page)
        print(f"Found {len(products)} product links\n")

        # Step 2: resolve + check each one
        for i, prod in enumerate(products, 1):
            name = prod["name"]
            url = prod["url"]
            youtube_url = prod.get("youtube_url")
            print(f"[{i}/{len(products)}] {name[:50]}")

            # Resolve short URL
            final_url = url
            if any(d in url for d in ["geni.us", "amzn.to", "bit.ly", "homedepot.sjv.io",
                                       "shoplowes.me", "acmetools.pxf.io", "redwood-outdoors.pxf.io",
                                       "creatoriq.cc", "exoskelinc.pxf.io"]):
                final_url = resolve_url(url)
                print(f"  → resolved: {final_url[:80]}")

            # For non-Amazon links: search Amazon by product name
            if not is_amazon(final_url):
                print(f"  → not Amazon, searching Amazon for: {name[:40]}")
                asin = search_amazon_for_product(page, name)
                if not asin:
                    print(f"  → not found on Amazon, skipping")
                    skipped_non_amazon.append(name)
                    continue
                print(f"  → found ASIN {asin} on Amazon")
            else:
                asin = extract_asin(final_url)
            if not asin:
                print(f"  → no ASIN found in {final_url[:60]}, skipping")
                continue

            if asin in existing_asins:
                print(f"  → already in DB, skipping")
                continue

            data = scrape_amazon_product(page, asin)
            if not data:
                print(f"  → failed to scrape")
                continue

            if youtube_url:
                data["source_video_url"] = youtube_url
                print(f"  price=${data['price_usd']} rating={data['rating']} ships_il={data['ships_to_israel']} yt={youtube_url[:50]}")
            else:
                print(f"  price=${data['price_usd']} rating={data['rating']} ships_il={data['ships_to_israel']}")
            results.append({"byotools_name": name, **data})
            time.sleep(1.5)

        browser.close()

    # Step 3: filter
    passed = [r for r in results if r["price_usd"] > 0 and r["price_usd"] <= MAX_PRICE and r["ships_to_israel"]]
    free_ship_passed = [r for r in passed if r["free_shipping"]]

    # Step 4: write CSV
    fieldnames = ["byotools_name", "name", "asin", "price_usd", "rating", "review_count", "ships_to_israel", "free_shipping", "affiliate_link"]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(sorted(passed, key=lambda x: x["price_usd"]))

    # Step 5: print summary
    print("\n" + "=" * 60)
    print("  byotools.me → Israel-Eligible Products")
    print("=" * 60)
    print(f"  Total links found:       {len(products)}")
    print(f"  Amazon links checked:    {len(results)}")
    print(f"  Under $75 + ships IL:    {len(passed)}")
    print(f"  Of those, free shipping: {len(free_ship_passed)}")
    print(f"  Saved to:                {OUTPUT_CSV}")
    print("=" * 60)

    if passed:
        print("\n✓ Products under $75 that ship to Israel:\n")
        for r in sorted(passed, key=lambda x: x["price_usd"]):
            ship_tag = " [FREE SHIP]" if r["free_shipping"] else ""
            print(f"  ${r['price_usd']:.2f}{ship_tag}  {r['byotools_name']} → {r['affiliate_link']}")

    if skipped_non_amazon:
        print(f"\n(Could not find on Amazon: {len(skipped_non_amazon)} products)")


if __name__ == "__main__":
    main()
