"""
Build a Hebrew summary of the Telegram pipeline run and queue it for sending.

Reads /tmp/telegram_new_asins.txt (written by telegram_scrape.py),
looks up final product status from the DB, and writes a report JSON to
data/pending_reports/. The mail-sender agent (send_pending_reports.py)
picks it up within 30 minutes and sends it via Gmail.

Run: python telegram_report.py
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from src.db import DB_PATH, init_db

ASINS_FILE = "/tmp/telegram_new_asins.txt"
CHANNEL = "haregakaniti"
PENDING_DIR = Path(__file__).parent / "data" / "pending_reports"


def _write_pending_report(prefix: str, subject: str, body: str) -> None:
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = PENDING_DIR / f"{prefix}_{ts}.json"
    path.write_text(json.dumps({"subject": subject, "body": body, "created_at": datetime.now().isoformat()}, ensure_ascii=False), encoding="utf-8")


def main():
    init_db()

    if not Path(ASINS_FILE).exists():
        print("[telegram_report] No ASINs file found — nothing to report.")
        return

    raw = Path(ASINS_FILE).read_text().strip()
    new_asins = [a for a in raw.splitlines() if a.strip()]

    if not new_asins:
        print("[telegram_report] ASINs file is empty — nothing to report.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        f"SELECT asin, name, name_he, price_usd, rating, review_count, status, ships_to_israel "
        f"FROM products WHERE asin IN ({','.join('?'*len(new_asins))})",
        new_asins
    ).fetchall()
    conn.close()

    found = {r["asin"]: dict(r) for r in rows}

    approved = [p for p in found.values() if p["status"] == "ready_for_video"]
    filtered = [p for p in found.values() if p["status"] == "filtered_out"]
    other    = [p for p in found.values() if p["status"] not in ("ready_for_video", "filtered_out")]
    missing  = [a for a in new_asins if a not in found]

    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    lines = [
        f"סיכום ריצת Telegram – @{CHANNEL}",
        f"תאריך: {now}",
        f"",
        f"סה\"כ מוצרים חדשים שנמצאו: {len(new_asins)}",
        f"  ✅ עברו פילטרים (ready_for_video): {len(approved)}",
        f"  ❌ סוננו החוצה (filtered_out):     {len(filtered)}",
    ]
    if other:
        lines.append(f"  ⏳ אחר:                              {len(other)}")
    if missing:
        lines.append(f"  ⚠️  לא נמצאו ב-DB:                  {len(missing)}")

    if approved:
        lines += ["", "─── מוצרים שאושרו לאתר ───"]
        for p in sorted(approved, key=lambda x: x.get("rating") or 0, reverse=True):
            name = p.get("name_he") or p.get("name") or p["asin"]
            price = f"${p['price_usd']:.2f}" if p.get("price_usd") else "מחיר לא ידוע"
            rating = f"⭐ {p['rating']}" if p.get("rating") else ""
            lines.append(f"  • {name[:60]}  {price}  {rating}".rstrip())

    if filtered:
        lines += ["", "─── מוצרים שסוננו ───"]
        for p in filtered:
            name = p.get("name") or p["asin"]
            lines.append(f"  • {name[:70]}")

    if missing:
        lines += ["", "─── לא נמצאו ב-DB (אולי נכשל ה-validate) ───"]
        for a in missing:
            lines.append(f"  • {a}")

    body = "\n".join(lines)
    print(body)

    subject = f"Telegram pipeline: {len(approved)} מוצרים חדשים ({now})"
    _write_pending_report("telegram", subject, body)
    print("\n[telegram_report] Report queued for mail sender ✓")


if __name__ == "__main__":
    main()
