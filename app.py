"""
Affiliation Pipeline — Web Dashboard
Run: python app.py
Open: http://localhost:5000
"""

import sys
import threading
import subprocess
from pathlib import Path

import yaml
from flask import Flask, render_template, jsonify, request

from src.db import init_db, get_all, reset_to_validated
from src.phase1.filter import run as apply_filter

app = Flask(__name__)

CONFIG_PATH = Path(__file__).parent / "config.yaml"

# Global scrape state — shared between the background thread and Flask routes
_scrape_state: dict = {"running": False, "log": [], "done": True, "error": None}
_scrape_lock = threading.Lock()


# ── Config helpers ────────────────────────────────────────────────────────────

def _load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_stats() -> dict:
    products = get_all()
    stats = {"total": len(products), "ready": 0, "filtered_out": 0, "discovered": 0, "validated": 0}
    for p in products:
        s = p.get("status", "")
        if s == "ready_for_video":
            stats["ready"] += 1
        elif s == "filtered_out":
            stats["filtered_out"] += 1
        elif s == "discovered":
            stats["discovered"] += 1
        elif s == "validated":
            stats["validated"] += 1
    return stats


def _ready_products() -> list[dict]:
    return [p for p in get_all() if p["status"] == "ready_for_video"]


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    init_db()
    config = _load_config()
    products = _ready_products()
    stats = _get_stats()
    return render_template(
        "index.html",
        products=products,
        stats=stats,
        filters=config.get("filters", {}),
        categories=config.get("categories", {}),
    )


@app.route("/products")
def products_api():
    """JSON endpoint — called by frontend after scrape completes to refresh table."""
    return jsonify(_ready_products())


@app.route("/stats")
def stats_api():
    return jsonify(_get_stats())


@app.route("/scrape", methods=["POST"])
def scrape():
    """Start a background scrape for the selected category."""
    with _scrape_lock:
        if _scrape_state["running"]:
            return jsonify({"error": "A scrape is already running. Please wait."}), 400

        url = (request.json or {}).get("url", "").strip()
        if not url:
            return jsonify({"error": "No category URL provided."}), 400

        _scrape_state["running"] = True
        _scrape_state["log"] = ["Starting scrape..."]
        _scrape_state["done"] = False
        _scrape_state["error"] = None

    def _run():
        try:
            proc = subprocess.Popen(
                [sys.executable, "main.py", "--url", url],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=str(Path(__file__).parent),
            )
            for line in proc.stdout:
                _scrape_state["log"].append(line.rstrip())
            proc.wait()
            if proc.returncode != 0:
                _scrape_state["error"] = "Scrape process exited with an error."
            else:
                _scrape_state["log"].append("✓ Done!")
        except Exception as e:
            _scrape_state["error"] = str(e)
        finally:
            _scrape_state["running"] = False
            _scrape_state["done"] = True

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/scrape/status")
def scrape_status():
    """Polled by the frontend every 2s during a scrape."""
    return jsonify({
        "running": _scrape_state["running"],
        "log":     _scrape_state["log"],
        "done":    _scrape_state["done"],
        "error":   _scrape_state["error"],
    })


@app.route("/filters", methods=["POST"])
def update_filters():
    """Save new filter values and immediately re-run the filter step."""
    data = request.json or {}
    config = _load_config()
    f = config.setdefault("filters", {})

    f["min_rating"]    = float(data.get("min_rating",    f.get("min_rating",    4.0)))
    f["min_reviews"]   = int(data.get("min_reviews",     f.get("min_reviews",   50)))
    f["min_price_usd"] = float(data.get("min_price_usd", f.get("min_price_usd", 15.0)))
    f["max_price_usd"] = float(data.get("max_price_usd", f.get("max_price_usd", 75.0)))
    f["ships_to_israel"] = bool(data.get("ships_to_israel", f.get("ships_to_israel", True)))

    _save_config(config)
    reset_to_validated()
    passed, filtered_out = apply_filter()

    return jsonify({
        "passed": passed,
        "filtered_out": filtered_out,
        "products": _ready_products(),
        "stats": _get_stats(),
    })


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("Dashboard running at http://localhost:5001")
    app.run(debug=False, port=5001)
