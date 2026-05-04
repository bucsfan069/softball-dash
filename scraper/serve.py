"""
Local development server for the softball dashboard.

- Serves site/ as static files at http://localhost:8000
- POST /api/refresh runs build_data.py for the requested year and returns
  {"ok": true, "duration_ms": N} on success or {"ok": false, "error": "..."}.

Run:
    cd scraper && python3 serve.py
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

SCRAPER_DIR = Path(__file__).resolve().parent
SITE_DIR = SCRAPER_DIR.parent / "site"

app = Flask(__name__)


@app.route("/")
def index():
    return send_from_directory(SITE_DIR, "index.html")


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    body = request.get_json(force=True, silent=True) or {}
    year = body.get("year")

    cmd = [sys.executable, str(SCRAPER_DIR / "build_data.py")]
    if year is not None:
        cmd += ["--year", str(int(year))]

    t0 = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            cwd=str(SCRAPER_DIR),
            capture_output=True,
            text=True,
            timeout=300,
        )
        duration_ms = int((time.monotonic() - t0) * 1000)
        if result.returncode == 0:
            return jsonify({"ok": True, "duration_ms": duration_ms})
        error = result.stderr.strip() or result.stdout.strip() or "Unknown error"
        return jsonify({"ok": False, "error": error, "duration_ms": duration_ms}), 500
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "error": "Scraper timed out after 5 minutes"}), 504
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(SITE_DIR, filename)


if __name__ == "__main__":
    print(f"Serving {SITE_DIR} at http://localhost:8000")
    print("POST /api/refresh to re-run the scraper for a season")
    app.run(host="127.0.0.1", port=8000, debug=False)
