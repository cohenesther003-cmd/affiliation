"""
Affiliation Pipeline — CLI Orchestrator
Usage:
    python main.py --url "https://www.amazon.com/Best-Sellers-Tools/zgbs/hi/"
    python main.py --url "..." --phase scrape      # only scrape
    python main.py --url "..." --phase validate    # only validate
    python main.py --phase filter                  # only apply filters
    python main.py --phase status                  # print DB summary
    python main.py --phase report                  # show ready products + affiliate links
    python main.py --phase video                   # Phase 2: download videos + generate Hebrew scripts
"""

import argparse
from src.db import init_db, get_all


def print_report() -> None:
    """Show all ready-for-video products with their affiliate links."""
    products = get_all()
    ready = [p for p in products if p["status"] == "ready_for_video"]

    if not ready:
        print("\nNo products are ready for video yet.")
        print("Run the full pipeline first: python main.py --url <amazon_url>")
        return

    print(f"\n{'═' * 80}")
    print(f"  READY FOR VIDEO — {len(ready)} products")
    print(f"{'═' * 80}\n")

    for i, p in enumerate(ready, 1):
        rating  = f"{p['rating']:.1f} ★" if p.get("rating") else "N/A"
        price   = f"${p['price_usd']:.2f}" if p.get("price_usd") else "N/A"
        reviews = f"{p['review_count']:,} reviews" if p.get("review_count") else "N/A"
        ships   = "✓ Ships to Israel" if p.get("ships_to_israel") else "✗ No Israel shipping"
        link    = p.get("affiliate_link") or f"https://www.amazon.com/dp/{p['asin']}/"

        print(f"  [{i}] {p.get('name', p['asin'])}")
        print(f"       Rating : {rating}  |  Price : {price}  |  {reviews}")
        print(f"       Shipping: {ships}")
        print(f"       Link   : {link}")
        print()

    print(f"{'═' * 80}")
    print(f"  {len(ready)} products ready  |  run 'python main.py --phase filter' to refresh")
    print(f"{'═' * 80}\n")


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
        print(f"\n  Tip: run 'python main.py --phase report' to see products + links")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Affiliation Pipeline — Phase 1")
    parser.add_argument("--url", help="Amazon Best Sellers page URL to scrape")
    parser.add_argument("--limit", type=int, help="Max number of products to process (Phase 2)")
    parser.add_argument("--max-price", type=float, dest="max_price", help="Max price filter (Phase 2)")
    parser.add_argument("--ships-to-israel", action="store_true", dest="ships_to_israel", help="Only products shipping to Israel (Phase 2)")
    parser.add_argument(
        "--phase",
        choices=["scrape", "validate", "filter", "status", "report", "all", "video"],
        default="all",
        help="Which phase to run (default: all)",
    )
    args = parser.parse_args()

    init_db()

    if args.phase == "status":
        print_summary()
        return

    if args.phase == "report":
        print_report()
        return

    if args.phase == "video":
        print("\n[Phase 2] Downloading videos + generating Hebrew scripts...")
        from src.phase2.pipeline import run as run_video
        run_video(
            limit=args.limit,
            max_price=args.max_price,
            ships_to_israel=args.ships_to_israel,
        )
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
        from src.db import reset_to_validated
        from src.phase1.filter import run as apply_filter
        reset_to_validated()
        apply_filter()

    print_summary()


if __name__ == "__main__":
    main()
