"""
Finds the source YouTube URL for a product.
- BYOT products: URL already stored in source_video_url column (set by byotools_scrape.py)
- Amazon Best Sellers: searches YouTube by product name using yt-dlp
"""

import subprocess
import re


def find_video_url(product: dict) -> str | None:
    """Return a YouTube URL for the product, or None if not found."""
    # Already have a URL from the scraper
    existing = product.get("source_video_url")
    if existing:
        return existing

    name = product.get("name") or product.get("asin")
    if not name or name == product.get("asin"):
        return None

    return _search_youtube(name)


def _search_youtube(product_name: str) -> str | None:
    """Use yt-dlp to search YouTube and return the first result URL."""
    query = f"ytsearch1:{product_name} review"
    try:
        result = subprocess.run(
            ["yt-dlp", "--get-id", "--no-warnings", "--quiet", query],
            capture_output=True, text=True, timeout=30
        )
        video_id = result.stdout.strip()
        if video_id and re.match(r"^[A-Za-z0-9_-]{11}$", video_id):
            return f"https://www.youtube.com/watch?v={video_id}"
    except Exception:
        pass
    return None
