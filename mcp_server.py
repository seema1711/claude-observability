#!/usr/bin/env python3
"""
Claude Observability MCP Server

Connect this to Claude Desktop and Claude Code to get:
- Prompt analysis & real-time optimization suggestions
- Token usage tracking
- Cost estimation
- Usage statistics

Claude Desktop config (~/.config/claude/claude_desktop_config.json):
{
  "mcpServers": {
    "observability": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"]
    }
  }
}
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

# Ensure local modules are importable
sys.path.insert(0, str(Path(__file__).parent))

import db
import analyzer
import tracker
from config import MODEL_PRICING

db.init_db()

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "claude-observability",
    instructions=(
        "You are connected to the Claude Observability MCP server. "
        "IMPORTANT: At the START of every conversation, call `analyze_prompt` "
        "with the user's first message and show the analysis summary before answering. "
        "This helps the user see optimization opportunities. "
        "Also call `log_interaction` after generating each response so usage is tracked."
    ),
)


# ── Tools ──────────────────────────────────────────────────────────────────

@mcp.tool()
def analyze_prompt(prompt: str, show_rewrite: bool = False) -> str:
    """
    Analyze a prompt and return token count, category, optimization score,
    and actionable suggestions to reduce token usage.

    Call this at the start of every conversation with the user's message.
    If show_rewrite=True, also return a more concise rewritten version.
    """
    analysis = analyzer.analyze(prompt)
    result = analysis.to_dict()

    lines = [
        "## Prompt Analysis",
        f"- **Tokens**: ~{result['token_count']}",
        f"- **Category**: {result['category']}",
        f"- **Optimization Score**: {result['optimization_score']}/100",
    ]

    if result["suggestions"]:
        lines.append(f"- **Potential savings**: ~{result['total_potential_savings']} tokens\n")
        lines.append("### Suggestions")
        for s in sorted(result["suggestions"], key=lambda x: x["token_savings"], reverse=True):
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(s["priority"], "•")
            saving_str = f" *(saves ~{s['token_savings']} tokens)*" if s["token_savings"] else ""
            lines.append(f"{icon} [{s['type'].upper()}] {s['message']}{saving_str}")
    else:
        lines.append("\n✅ Prompt is already well-optimized!")

    if show_rewrite and result["suggestions"]:
        lines.append("\n### Quick Wins")
        rewrite_tips = []
        for s in result["suggestions"]:
            if s["type"] == "verbosity":
                rewrite_tips.append(f"- {s['message']}")
        if rewrite_tips:
            lines.extend(rewrite_tips)
        else:
            lines.append("No quick verbosity rewrites available.")

    return "\n".join(lines)


@mcp.tool()
def log_interaction(
    prompt: str,
    response: str,
    model: str = "claude-sonnet-4-6",
    session_id: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> str:
    """
    Log a completed prompt/response interaction for tracking.
    Call this after generating each response.

    If input_tokens/output_tokens are 0, they are estimated automatically.
    Returns a confirmation with cost and running totals.
    """
    if not session_id:
        session_id = "desktop-" + str(uuid.uuid4())[:8]

    db.insert_session(session_id, model, source="claude-desktop")

    if input_tokens == 0:
        input_tokens = tracker.estimate_tokens(prompt)
    if output_tokens == 0:
        output_tokens = tracker.estimate_tokens(response)

    cost = tracker.calculate_cost(input_tokens, output_tokens, model)
    analysis = analyzer.analyze(prompt)

    row_id = db.insert_interaction(
        session_id=session_id,
        prompt=prompt,
        response=response,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=model,
        cost=cost,
        category=analysis.category,
        optimization_score=analysis.optimization_score,
        suggestions=[s.message for s in analysis.suggestions],
    )

    stats = db.get_summary_stats()
    return (
        f"Logged interaction #{row_id}\n"
        f"- This turn: {tracker.format_tokens(input_tokens + output_tokens)} tokens "
        f"({tracker.format_tokens(input_tokens)} in / {tracker.format_tokens(output_tokens)} out) "
        f"— {tracker.format_cost(cost)}\n"
        f"- All time: {tracker.format_tokens(stats['total_input_tokens'] + stats['total_output_tokens'])} tokens "
        f"— {tracker.format_cost(stats['total_cost'])}"
    )


@mcp.tool()
def get_stats(days: int = 7) -> str:
    """
    Get usage statistics: token consumption, costs, and category breakdown
    for the last N days (default 7).
    """
    summary = db.get_summary_stats()
    daily = db.get_daily_stats(days)

    lines = [
        f"## Usage Statistics (last {days} days)",
        f"- **Total interactions**: {summary['total_interactions']}",
        f"- **Total input tokens**: {tracker.format_tokens(summary['total_input_tokens'])}",
        f"- **Total output tokens**: {tracker.format_tokens(summary['total_output_tokens'])}",
        f"- **Total cost**: {tracker.format_cost(summary['total_cost'])}",
        f"- **Avg optimization score**: {summary['avg_optimization_score']}/100",
    ]

    if summary["categories"]:
        lines.append("\n### By Category")
        for cat in summary["categories"][:5]:
            lines.append(f"- {cat['category']}: {cat['cnt']} interactions")

    if daily:
        lines.append("\n### Daily Breakdown")
        for d in daily[:days]:
            total_tok = d["input_tokens"] + d["output_tokens"]
            lines.append(
                f"- {d['date']}: {tracker.format_tokens(total_tok)} tokens "
                f"({d['interaction_count']} interactions) — {tracker.format_cost(d['cost'])}"
            )

    return "\n".join(lines)


@mcp.tool()
def get_optimization_report() -> str:
    """
    Return a full optimization report showing the most expensive prompts
    and top recommendations to reduce token usage.
    """
    top = db.get_top_expensive(10)
    summary = db.get_summary_stats()

    lines = ["## Optimization Report\n"]

    if not top:
        return "No interactions logged yet. Start using Claude and the data will appear here."

    avg_score = summary["avg_optimization_score"]
    grade = "A" if avg_score >= 90 else "B" if avg_score >= 75 else "C" if avg_score >= 60 else "D"
    lines.append(f"**Overall Grade**: {grade} ({avg_score}/100)\n")

    # Aggregate suggestion types across all interactions
    tip_counts: dict[str, int] = {}
    for row in db.get_recent_interactions(50):
        for tip in row.get("suggestions", []):
            tip_counts[tip] = tip_counts.get(tip, 0) + 1

    if tip_counts:
        lines.append("### Most Common Issues")
        for tip, count in sorted(tip_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            lines.append(f"- ({count}×) {tip}")

    lines.append("\n### Top 5 Most Expensive Prompts")
    for i, row in enumerate(top[:5], 1):
        preview = row["prompt"][:80].replace("\n", " ")
        lines.append(
            f"{i}. [{row['category']}] {preview}… "
            f"— {tracker.format_tokens(row['input_tokens'])} tokens, {tracker.format_cost(row['cost'])}"
        )

    lines.append("\n### Quick Wins")
    lines.extend([
        "1. **Prompt Caching**: Add `cache_control` to system prompts >1024 tokens (90% cost reduction)",
        "2. **System Prompts**: Move persona/formatting instructions out of every user message",
        "3. **Verbosity**: Remove filler phrases ('Please', 'Could you', 'I would like you to')",
        "4. **Structure**: Use XML tags for multi-part prompts; split >3 questions into separate calls",
        "5. **Model Selection**: Use Haiku for classification/simple tasks (20× cheaper than Opus)",
    ])

    return "\n".join(lines)


@mcp.tool()
def estimate_tokens(text: str) -> str:
    """
    Estimate the token count for any text string.
    Useful for checking how large a prompt/context will be before sending.
    """
    count = tracker.estimate_tokens(text)
    chars = len(text)
    lines_count = text.count("\n") + 1

    pricing_rows = []
    for model_name in ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-7"]:
        p = MODEL_PRICING[model_name]
        cost = (count / 1_000_000) * p["input"]
        pricing_rows.append(f"  - {model_name}: {tracker.format_cost(cost)}")

    return (
        f"**Token estimate**: ~{count} tokens\n"
        f"- Characters: {chars}\n"
        f"- Lines: {lines_count}\n"
        f"- Ratio: {chars / max(count, 1):.1f} chars/token\n\n"
        f"**Input cost** (this text as a prompt):\n" + "\n".join(pricing_rows)
    )


@mcp.tool()
def get_prompt_history(limit: int = 10) -> str:
    """
    Return the most recent N logged interactions with token counts and scores.
    """
    rows = db.get_recent_interactions(limit)
    if not rows:
        return "No interactions logged yet."

    lines = [f"## Recent {len(rows)} Interactions\n"]
    for i, row in enumerate(rows, 1):
        preview = row["prompt"][:70].replace("\n", " ")
        score_str = f"score={row['optimization_score']}/100"
        tok_str = tracker.format_tokens(row["input_tokens"] + row["output_tokens"])
        lines.append(
            f"{i}. [{row['category']}] {preview}…\n"
            f"   {row['timestamp'][:19]} | {tok_str} tokens | "
            f"{tracker.format_cost(row['cost'])} | {score_str}"
        )
    return "\n".join(lines)


@mcp.tool()
def start_session(model: str = "claude-sonnet-4-6", source: str = "claude-desktop") -> str:
    """
    Start a new tracked session. Returns a session_id to pass to log_interaction.
    Call this at the beginning of a new conversation.
    """
    session_id = f"{source}-{str(uuid.uuid4())[:12]}"
    db.insert_session(session_id, model, source)
    return f"Session started: `{session_id}`\nModel: {model}\nPass this id to `log_interaction`."


if __name__ == "__main__":
    mcp.run(transport="stdio")
