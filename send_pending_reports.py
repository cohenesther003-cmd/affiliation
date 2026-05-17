"""
Mail-sender agent — scans data/pending_reports/ for queued email reports,
sends each one via Gmail, then deletes the file.

Run: python send_pending_reports.py
Scheduled: every 30 minutes via launchd (me.affiliation.mail-sender)
"""

import json
import os
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

PENDING_DIR = Path(__file__).parent / "data" / "pending_reports"


def main():
    PENDING_DIR.mkdir(parents=True, exist_ok=True)

    pending = sorted(PENDING_DIR.glob("*.json"))
    if not pending:
        print("[mail-sender] No pending reports.")
        return

    gmail_user = os.getenv("GMAIL_USER", "")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD", "")
    if not gmail_user or not gmail_pass or "xxxx" in gmail_pass:
        print(f"[mail-sender] No Gmail credentials — skipping {len(pending)} pending report(s).")
        return

    sent = 0
    for path in pending:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            subject = data["subject"]
            body = data["body"]

            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = gmail_user
            msg["To"] = gmail_user

            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.ehlo()
                server.starttls()
                server.login(gmail_user, gmail_pass)
                server.sendmail(gmail_user, gmail_user, msg.as_string())

            print(f"[mail-sender] Sent: {subject}")
            path.unlink()
            sent += 1
        except Exception as e:
            print(f"[mail-sender] Failed to send {path.name}: {e}")

    print(f"[mail-sender] Done — {sent}/{len(pending)} report(s) sent.")


if __name__ == "__main__":
    main()
