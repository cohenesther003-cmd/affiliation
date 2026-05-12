"""
Affiliation Pipeline — CLI Orchestrator
Usage:
    python main.py --url "https://www.amazon.com/Best-Sellers-Tools/zgbs/hi/"
    python main.py --url "..." --phase scrape      # only scrape
    python main.py --url "..." --phase validate    # only PA-API validate
    python main.py --phase filter                  # only apply filters
    python main.py --phase status                  # print DB summary
"""

import argparse
from src.db import init_db, get_all


def print_summary() -> None:
    products = get_all()
    if not products:
        print("Database is empty — run with --url to start scraping.")
        return

    from collections import Counter
    counts = Counter(p["status"] for p in products)

    print("\n─── Product Database Summary ──────────────────")
    for status, count in sorted(counts.items()):
        print(f"  {status:<20} {count:>4} products")
    print(f"  {'TOTAL':<20} {len(products):>4} products")

    ready = [p for p in products if p["status"] == "ready_for_video"]
    if ready:
        print("\n─── Ready for Video ────────────────────────────")
        print(f"  {'ASIN':<12} {'Rating':>6}  {'Price':>8}  {'Name'}")
        print("  " + "─" * 60)
        for p in ready:
            rating = f"{p['rating']:.1f}" if p.get("rating") else "N/A"
            price = f"${p['price_usd']:.2f}" if p.get("price_usd") else "N/A"
            name = (p.get("name") or "")[:45]
            print(f"  {p['asin']:<12} {rating:>6}  {price:>8}  {name}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Affiliation Pipeline — Phase 1")
    parser.add_argument("--url", help="Amazon Best Sellers page URL to scrape")
    parser.add_argument(
        "--phase",
        choices=["scrape", "validate", "filter", "status", "all"],
        default="all",
        help="Which phase to run (default: all)",
    )
    args = parser.parse_args()

    init_db()

    if args.phase == "status":
        print_summary()
        return

    run_scrape = args.phase in ("scrape", "all")
    run_validate = args.phase in ("validate", "all")
    run_filter = args.phase in ("filter", "all")

    if run_scrape:
        if not args.url:
            parser.error("--url is required for scraping (--phase scrape or all)")
        print("\n[Phase 1 / Step 1] Scraping Amazon Best Sellers...")
        from src.phase1.scraper import run as scrape
        scrape(args.url)

    if run_validate:
        print("\n[Phase 1 / Step 2] Validating products via Amazon PA-API...")
        from src.phase1.amazon_api import run as validate
        validate()

    if run_filter:
        print("\n[Phase 1 / Step 3] Applying filters from config.yaml...")
        from src.phase1.filter import run as apply_filter
        apply_filter()

    print_summary()


if __name__ == "__main__":
    main()
