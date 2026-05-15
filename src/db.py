import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "products.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                asin             TEXT UNIQUE NOT NULL,
                name             TEXT,
                category         TEXT,
                rating           REAL,
                review_count     INTEGER,
                price_usd        REAL,
                ships_to_israel  INTEGER DEFAULT 0,
                affiliate_link   TEXT,
                source_video_url TEXT,
                image_url        TEXT,
                description_he   TEXT,
                status           TEXT DEFAULT 'discovered',
                discovered_at    TEXT,
                updated_at       TEXT
            )
        """)
        # Migrate existing DBs that don't have the new columns yet
        for col, typedef in [("image_url", "TEXT"), ("description_he", "TEXT")]:
            try:
                conn.execute(f"ALTER TABLE products ADD COLUMN {col} {typedef}")
            except Exception:
                pass


def upsert_product(asin: str, data: dict) -> None:
    now = datetime.now(timezone.utc).isoformat()
    data = {**data, "asin": asin, "updated_at": now}

    with _connect() as conn:
        existing = conn.execute(
            "SELECT id FROM products WHERE asin = ?", (asin,)
        ).fetchone()

        if existing:
            fields = ", ".join(f"{k} = :{k}" for k in data if k != "asin")
            conn.execute(f"UPDATE products SET {fields} WHERE asin = :asin", data)
        else:
            data.setdefault("discovered_at", now)
            data.setdefault("status", "discovered")
            cols = ", ".join(data.keys())
            placeholders = ", ".join(f":{k}" for k in data)
            conn.execute(
                f"INSERT INTO products ({cols}) VALUES ({placeholders})", data
            )


def get_by_status(status: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM products WHERE status = ?", (status,)
        ).fetchall()
    return [dict(row) for row in rows]


def update_status(asin: str, status: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "UPDATE products SET status = ?, updated_at = ? WHERE asin = ?",
            (status, now, asin),
        )


def reset_to_validated() -> int:
    """Move ready_for_video and filtered_out products back to validated so filters can be re-applied."""
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE products SET status='validated', updated_at=? "
            "WHERE status IN ('ready_for_video', 'filtered_out')",
            (now,),
        )
        return cur.rowcount


def get_all() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM products ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]
