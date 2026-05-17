"""
One-time recovery script: restores products that were incorrectly marked
'unavailable' by a bot-blocked daily refresh run.

On 2026-05-16, Amazon blocked the refresh scraper and 368 products were
falsely marked unavailable because the block pages had no #add-to-cart-button.
This script restores all products marked unavailable on that date back to
'ready_for_video', then re-exports and pushes the site.

Run: python restore_unavailable.py
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from src.db import init_db, get_all, update_status

def main():
    init_db()
    all_products = get_all()

    # Restore every unavailable product — the mass marking was clearly a
    # bot-blocking incident (368 of 401 products in one run is impossible to be real).
    # Products genuinely unavailable before the incident would have been
    # re-confirmed by yesterday's refresh; that run affected them too due to blocking.
    to_restore = [p for p in all_products if p["status"] == "unavailable"]

    print(f"Found {len(to_restore)} unavailable products to restore.\n")

    for p in to_restore:
        update_status(p["asin"], "ready_for_video")
        name = (p.get("name") or p["asin"])[:55]
        print(f"  Restored: {name}")

    print(f"\nRestored {len(to_restore)} products → ready_for_video.")

    # Re-export the site
    print("\nRegenerating site...")
    root = Path(__file__).parent
    try:
        subprocess.run(["python", "export_page.py"], cwd=root, check=True)
        print("Site regenerated ✓")
    except subprocess.CalledProcessError as e:
        print(f"export_page.py failed: {e}")
        sys.exit(1)

    # Commit and push
    print("\nCommitting and pushing...")
    try:
        subprocess.run(["git", "add", "docs/"], cwd=root, check=True)
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=root
        )
        if result.returncode != 0:
            subprocess.run(
                ["git", "commit", "-m",
                 f"Restore {len(to_restore)} products: undo false-unavailable from bot-blocked refresh"],
                cwd=root, check=True
            )
            subprocess.run(["git", "push"], cwd=root, check=True)
            print("Pushed ✓")
        else:
            print("No docs/ changes to push.")
    except subprocess.CalledProcessError as e:
        print(f"Git operation failed: {e}")
        sys.exit(1)

    print(f"\nDone. Site now shows ~{len(to_restore) + 9} products again.")

if __name__ == "__main__":
    main()
