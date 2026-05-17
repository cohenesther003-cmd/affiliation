#!/bin/zsh
# Telegram → Amazon → site pipeline.
# Run by launchd every 6 hours, or manually with: ./run_telegram_pipeline.sh
set -e
cd /Users/esthercohen/affiliation

echo "─── Telegram pipeline run: $(date) ───"

# 1) Discover new ASINs from Telegram channel
OUTPUT=$(.venv/bin/python telegram_scrape.py 2>&1)
echo "$OUTPUT"
NEW=$(echo "$OUTPUT" | grep -oE 'Discovered [0-9]+' | grep -oE '[0-9]+' | head -1)
NEW=${NEW:-0}

# Also check for pending 'discovered' or 'validated' products from previous runs that
# may not have made it all the way through (e.g. previous run failed mid-pipeline).
PENDING_DISC=$(.venv/bin/python -c "from src.db import init_db, get_by_status; init_db(); print(len(get_by_status('discovered')))")
PENDING_VAL=$(.venv/bin/python -c "from src.db import init_db, get_by_status; init_db(); print(len(get_by_status('validated')))")

if [ "$NEW" = "0" ] && [ "$PENDING_DISC" = "0" ] && [ "$PENDING_VAL" = "0" ]; then
    echo "No new or pending products — done."
    exit 0
fi
echo "Processing: $NEW new + $PENDING_DISC pending discovered + $PENDING_VAL pending validated"

echo ""
echo "─── Validating $NEW new products ───"
.venv/bin/python main.py --phase validate

sleep 2

echo ""
echo "─── Filtering against config.yaml rules ───"
.venv/bin/python main.py --phase filter

echo ""
echo "─── Translating new Hebrew names ───"
.venv/bin/python translate_names.py || echo "(translate failed, continuing)"

echo ""
echo "─── Enriching new product descriptions ───"
.venv/bin/python enrich_products.py || echo "(enrich failed, continuing)"

echo ""
echo "─── Regenerating site ───"
.venv/bin/python export_page.py

echo ""
echo "─── Committing changes (if any) ───"
if [ -n "$(git status --porcelain docs/)" ]; then
    git add docs/
    git commit -m "Telegram ingest: +$NEW products"
    git push
    echo "✓ Pushed $NEW new products to site"
else
    echo "No docs/ changes to push"
fi

echo ""
echo "─── Sending email report ───"
.venv/bin/python telegram_report.py || echo "(email report failed, continuing)"

echo "─── Done: $(date) ───"
