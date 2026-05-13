"""
Dynamic filter — reads all thresholds from config.yaml.
Products in 'validated' status are checked against every rule.
Pass → 'ready_for_video', Fail → 'filtered_out'.
"""

from config import CONFIG
from src.db import get_by_status, update_status


def _passes(product: dict, rules: dict) -> tuple[bool, list[str]]:
    """Returns (passed, list_of_failed_reasons)."""
    failures: list[str] = []

    rating = product.get("rating") or 0.0
    if rating < rules.get("min_rating", 0):
        failures.append(f"rating {rating} < {rules['min_rating']}")

    review_count = product.get("review_count") or 0
    if review_count < rules.get("min_reviews", 0):
        failures.append(f"reviews {review_count} < {rules['min_reviews']}")

    price = product.get("price_usd") or 0.0
    min_price = rules.get("min_price_usd", 0)
    max_price = rules.get("max_price_usd", float("inf"))
    if price < min_price:
        failures.append(f"price ${price:.2f} < ${min_price:.2f}")
    if price > max_price:
        failures.append(f"price ${price:.2f} > ${max_price:.2f}")

    if rules.get("ships_to_israel") and not product.get("ships_to_israel"):
        failures.append("does not ship to Israel")

    allowed_categories = rules.get("allowed_categories") or []
    if allowed_categories:
        category = product.get("category", "")
        if not any(
            cat.lower() in category.lower() for cat in allowed_categories
        ):
            failures.append(f"category '{category}' not in allowed list")

    return (len(failures) == 0, failures)


def run() -> tuple[int, int]:
    """Returns (passed_count, filtered_out_count)."""
    rules = CONFIG.get("filters", {})
    candidates = get_by_status("validated")

    if not candidates:
        print("  No validated products to filter.")
        return 0, 0

    passed = 0
    filtered_out = 0

    for product in candidates:
        # External sources (e.g. byotools) are pre-filtered at scrape time — skip Amazon rules
        if product.get("category") == "byotools":
            update_status(product["asin"], "ready_for_video")
            passed += 1
            continue

        ok, reasons = _passes(product, rules)
        if ok:
            update_status(product["asin"], "ready_for_video")
            passed += 1
        else:
            update_status(product["asin"], "filtered_out")
            filtered_out += 1
            print(f"  Filtered out {product['asin']} ({product.get('name', '')[:40]}): {'; '.join(reasons)}")

    print(f"  Filter results: {passed} ready for video, {filtered_out} filtered out.")
    return passed, filtered_out
