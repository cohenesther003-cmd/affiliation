"""
Playwright scraper — extracts products from Amazon Best Sellers pages.
Saves each discovered product to the SQLite DB with status='discovered'.
"""

import asyncio
import re
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from config import CONFIG
from src.db import init_db, upsert_product, get_all


def _asin_from_url(url: str) -> str | None:
    match = re.search(r"/dp/([A-Z0-9]{10})", url)
    return match.group(1) if match else None


def _category_from_url(url: str) -> str:
    parts = urlparse(url).path.strip("/").split("/")
    # Best Sellers URLs typically contain a readable category segment
    for part in parts:
        if part not in ("Best-Sellers", "zgbs", "dp", "gp", "b"):
            cleaned = part.replace("-", " ").title()
            if len(cleaned) > 2:
                return cleaned
    return "General"


async def _scrape(url: str) -> list[dict]:
    cfg = CONFIG["scraper"]
    max_products = cfg.get("max_products_per_run", 50)
    scroll_pages = cfg.get("scroll_pages", 3)

    existing_asins = {p["asin"] for p in get_all()}
    discovered: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )

        current_url = url
        for page_num in range(scroll_pages):
            print(f"  Scraping page {page_num + 1}: {current_url}")
            await page.goto(current_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            # Scroll to load lazy content
            for _ in range(5):
                await page.keyboard.press("End")
                await page.wait_for_timeout(800)

            product_links = await page.query_selector_all(
                "a[href*='/dp/']"
            )

            for link in product_links:
                if len(discovered) >= max_products:
                    break

                href = await link.get_attribute("href") or ""
                asin = _asin_from_url(href)
                if not asin or asin in existing_asins:
                    continue

                # Grab the closest text as product name
                name = (await link.inner_text()).strip()
                if not name or len(name) < 5:
                    # Try parent element for the title
                    parent = await link.query_selector("..")
                    if parent:
                        name = (await parent.inner_text()).strip().split("\n")[0]

                if not name or len(name) < 5:
                    continue

                category = _category_from_url(url)
                existing_asins.add(asin)
                discovered.append(
                    {
                        "asin": asin,
                        "name": name[:200],
                        "category": category,
                        "status": "discovered",
                    }
                )

            if len(discovered) >= max_products:
                break

            # Try to navigate to next page
            next_btn = await page.query_selector("li.a-last a, .a-pagination .a-last a")
            if next_btn:
                next_href = await next_btn.get_attribute("href")
                if next_href:
                    current_url = (
                        next_href
                        if next_href.startswith("http")
                        else f"https://www.amazon.com{next_href}"
                    )
                else:
                    break
            else:
                break

        await browser.close()

    return discovered


def run(url: str) -> int:
    init_db()
    products = asyncio.run(_scrape(url))
    for product in products:
        upsert_product(product["asin"], product)
    print(f"  Discovered {len(products)} new products.")
    return len(products)
