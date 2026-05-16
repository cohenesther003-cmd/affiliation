"""
Fixes products where name == asin (name was never scraped).
Visits each Amazon page and updates the name in the DB.
"""
import time, random, sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from src.db import init_db, get_all, upsert_product
from playwright.sync_api import sync_playwright

def main():
    init_db()
    products = [p for p in get_all() if p.get("name") == p["asin"] or not p.get("name")]
    print(f"Fixing names for {len(products)} products...\n")

    fixed = 0
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="en-US", timezone_id="America/New_York",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"}
        )
        page = ctx.new_page()
        page.goto("https://www.amazon.com/", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(1500)

        for i, prod in enumerate(products, 1):
            asin = prod["asin"]
            try:
                page.goto(f"https://www.amazon.com/dp/{asin}/", wait_until="domcontentloaded", timeout=25000)
                page.wait_for_timeout(random.randint(1200, 2000))
                el = page.query_selector("#productTitle")
                name = el.inner_text().strip() if el else ""
                if name and name != asin:
                    upsert_product(asin, {"name": name})
                    print(f"[{i}/{len(products)}] {asin} → {name[:60]}")
                    fixed += 1
                else:
                    print(f"[{i}/{len(products)}] {asin} → could not find name")
            except Exception as e:
                print(f"[{i}/{len(products)}] {asin} → error: {e}")
            time.sleep(random.uniform(1.5, 3.0))

        browser.close()

    print(f"\nDone — {fixed}/{len(products)} names fixed.")

if __name__ == "__main__":
    main()
