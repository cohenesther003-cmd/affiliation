"""
Batch-translates product names to Hebrew using the Claude CLI.
Sends 15 names per call for speed. Safe to re-run — skips already-translated products.

Run: python translate_names.py
"""

import json
import sqlite3
import sys
import subprocess
from src.db import init_db, get_all, upsert_product, DB_PATH

BATCH_SIZE = 15


def translate_batch(names: list[str]) -> list[str]:
    numbered = "\n".join(f"{i+1}. {n}" for i, n in enumerate(names))
    prompt = (
        "תרגם את שמות המוצרים הבאים לעברית שיווקית טבעית.\n"
        "חשוב: השתמש בטרמינולוגיה מקצועית עברית — לא תרגום מילולי.\n"
        "לדוגמה: \"Door Stop\" → \"מעצור דלת\" (לא \"עצור דלת\"), \"Drill Bit\" → \"מקדח\" (לא \"ביט קידוח\").\n"
        "הנחיות: שמות קצרים, זורמים, כפי שישראלי היה אומר אותם. אם חלק מהשם הוא מיותר, השמט אותו. ללא ניקוד.\n"
        f"החזר JSON בלבד: [\"שם1\", \"שם2\", ...]. ללא טקסט נוסף.\n\n{numbered}"
    )
    result = subprocess.run(
        ["claude", "--print", "-p", prompt],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())

    output = result.stdout.strip()
    # Extract JSON array from output
    start = output.find("[")
    end = output.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON array found in: {output[:200]}")

    translations = json.loads(output[start:end])
    if len(translations) != len(names):
        raise ValueError(f"Got {len(translations)} translations for {len(names)} names")
    return translations


def main():
    init_db()

    if "--retranslate" in sys.argv:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE products SET name_he = NULL WHERE name_he IS NOT NULL")
        conn.commit()
        conn.close()
        print("Cleared all name_he for re-translation")

    products = [
        p for p in get_all()
        if p["status"] in ("ready_for_video", "video_ready", "video_failed") and not p.get("name_he")
    ]

    if not products:
        print("✓ All product names already translated.")
        return

    print(f"Translating {len(products)} product names in batches of {BATCH_SIZE}...")
    done = 0
    errors = 0

    for i in range(0, len(products), BATCH_SIZE):
        batch = products[i:i + BATCH_SIZE]
        names = [p.get("name") or p["asin"] for p in batch]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(products) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"  Batch {batch_num}/{total_batches}...", end=" ", flush=True)

        try:
            translations = translate_batch(names)
            for p, name_he in zip(batch, translations):
                upsert_product(p["asin"], {"name_he": name_he})
            done += len(batch)
            print(f"✓ {len(batch)} done")
        except Exception as e:
            errors += len(batch)
            print(f"✗ error: {e}")

    print(f"\nDone — {done} translated, {errors} failed.")


if __name__ == "__main__":
    main()
