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


@app.route("/widget")
def widget():
    return render_template("widget.html")


@app.route("/api/widget")
def api_widget():
    recent = db.get_recent_interactions(limit=1)
    today = db.get_daily_stats(days=1)
    summary = db.get_summary_stats()
    last = recent[0] if recent else {}
    today_row = today[0] if today else {}
    return jsonify({
        "last_input": last.get("input_tokens", 0),
        "last_output": last.get("output_tokens", 0),
        "last_cost": last.get("cost", 0.0),
        "last_score": last.get("optimization_score", 100),
        "last_id": last.get("id"),
        "today_tokens": today_row.get("input_tokens", 0) + today_row.get("output_tokens", 0),
        "today_cost": today_row.get("cost", 0.0),
        "total_tokens": summary["total_input_tokens"] + summary["total_output_tokens"],
        "total_cost": summary["total_cost"],
    })


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
