"""
Amazon PA-API 5.0 validator.
For each 'discovered' product, fetches official rating, review count,
price, Israel shipping availability, and generates an affiliate link.
"""

import os
from dotenv import load_dotenv
from amazon.paapi import AmazonAPI

from src.db import get_by_status, upsert_product, update_status

load_dotenv()

_BATCH_SIZE = 10  # PA-API allows up to 10 ASINs per GetItems call


def _build_client() -> AmazonAPI:
    access_key = os.getenv("AMAZON_ACCESS_KEY")
    secret_key = os.getenv("AMAZON_SECRET_KEY")
    partner_tag = os.getenv("AMAZON_PARTNER_TAG")

    if not all([access_key, secret_key, partner_tag]):
        raise EnvironmentError(
            "Missing Amazon PA-API credentials. "
            "Copy .env.example → .env and fill in your keys."
        )

    return AmazonAPI(
        access_key=access_key,
        secret_key=secret_key,
        partner_tag=partner_tag,
        country="US",
    )


def _ships_to_israel(item) -> bool:
    """
    PA-API doesn't expose per-country shipping directly.
    We check if the item has an active listing (IsEligibleForPrime or
    a buyable offer) as a proxy — actual Israel eligibility is confirmed
    at checkout. Mark True if the product has an active offer.
    """
    try:
        offers = item.offers.listings
        return bool(offers)
    except AttributeError:
        return False


def _extract_data(item) -> dict:
    data: dict = {}

    # Rating and review count
    try:
        data["rating"] = float(item.browse_node_info.browse_nodes[0].sales_rank or 0)
    except (AttributeError, TypeError, IndexError):
        pass

    try:
        data["rating"] = float(
            item.customer_reviews.star_rating.value
        )
        data["review_count"] = int(
            item.customer_reviews.count
        )
    except (AttributeError, TypeError):
        pass

    # Price
    try:
        data["price_usd"] = float(
            item.offers.listings[0].price.amount
        )
    except (AttributeError, TypeError, IndexError):
        pass

    # Affiliate link (DetailPageURL includes the partner tag automatically)
    try:
        data["affiliate_link"] = item.detail_page_url
    except AttributeError:
        pass

    # Ships to Israel proxy
    data["ships_to_israel"] = 1 if _ships_to_israel(item) else 0

    # Product name (may refine the scraped name)
    try:
        data["name"] = item.item_info.title.display_value
    except AttributeError:
        pass

    return data


def run() -> int:
    pending = get_by_status("discovered")
    if not pending:
        print("  No discovered products to validate.")
        return 0

    client = _build_client()
    validated = 0

    for i in range(0, len(pending), _BATCH_SIZE):
        batch = pending[i : i + _BATCH_SIZE]
        asins = [p["asin"] for p in batch]

        try:
            response = client.get_items(asins)
            items_map = {item.asin: item for item in (response.items_result.items or [])}
        except Exception as e:
            print(f"  PA-API error for batch {asins}: {e}")
            continue

        for product in batch:
            asin = product["asin"]
            item = items_map.get(asin)

            if not item:
                update_status(asin, "filtered_out")
                continue

            data = _extract_data(item)
            data["status"] = "validated"
            upsert_product(asin, data)
            validated += 1

    print(f"  Validated {validated} products via PA-API.")
    return validated
