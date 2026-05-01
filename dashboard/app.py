#!/usr/bin/env python3
"""Flask dashboard for Claude Observability."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import db
import tracker
import analyzer
from config import DASHBOARD_PORT

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
db.init_db()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/summary")
def api_summary():
    stats = db.get_summary_stats()
    return jsonify(stats)


@app.route("/api/daily")
def api_daily():
    days = int(request.args.get("days", 30))
    rows = db.get_daily_stats(days)
    # Sort ascending for chart display
    rows.sort(key=lambda r: r["date"])
    return jsonify(rows)


@app.route("/api/interactions")
def api_interactions():
    limit = int(request.args.get("limit", 20))
    rows = db.get_recent_interactions(limit)
    # Truncate prompt/response for UI
    for row in rows:
        row["prompt_preview"] = row.get("prompt", "")[:120]
        row.pop("prompt", None)
        row.pop("response", None)
    return jsonify(rows)


@app.route("/api/expensive")
def api_expensive():
    limit = int(request.args.get("limit", 10))
    rows = db.get_top_expensive(limit)
    for row in rows:
        row["prompt_preview"] = row.get("prompt", "")[:120]
        row.pop("prompt", None)
        row.pop("response", None)
    return jsonify(rows)


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """Analyze a prompt and return suggestions (used by the dashboard prompt tester)."""
    data = request.get_json(force=True)
    prompt = data.get("prompt", "")
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400
    analysis = analyzer.analyze(prompt)
    return jsonify(analysis.to_dict())


@app.route("/api/estimate", methods=["POST"])
def api_estimate():
    data = request.get_json(force=True)
    text = data.get("text", "")
    count = tracker.estimate_tokens(text)
    return jsonify({"tokens": count, "chars": len(text)})


if __name__ == "__main__":
    print(f"Dashboard running at http://localhost:{DASHBOARD_PORT}")
    app.run(port=DASHBOARD_PORT, debug=False)
