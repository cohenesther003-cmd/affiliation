"""
Send an email summary of the Telegram pipeline run.

Reads /tmp/telegram_new_asins.txt (written by telegram_scrape.py),
looks up final product status from the DB, and emails a Hebrew report
to GMAIL_USER.

Run: python telegram_report.py
"""

import os
import smtplib
import sqlite3
import sys
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from src.db import DB_PATH, init_db

load_dotenv()

ASINS_FILE = "/tmp/telegram_new_asins.txt"
CHANNEL = "haregakaniti"


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

    gmail_user = os.getenv("GMAIL_USER", "")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "")
    if not gmail_user or not gmail_pass or "xxxx" in gmail_pass:
        print("\n[telegram_report] No Gmail credentials — skipping email.")
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"Telegram pipeline: {len(approved)} מוצרים חדשים ({now})"
    msg["From"] = gmail_user
    msg["To"] = gmail_user

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(gmail_user, gmail_pass)
            server.sendmail(gmail_user, gmail_user, msg.as_string())
        print(f"\n[telegram_report] Report sent to {gmail_user} ✓")
    except Exception as e:
        print(f"\n[telegram_report] Failed to send email: {e}")


if __name__ == "__main__":
    main()
