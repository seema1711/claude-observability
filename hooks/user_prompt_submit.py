#!/usr/bin/env python3
"""
Claude Code hook: UserPromptSubmit

Fires every time you press Enter in Claude Code.
Prints a compact prompt analysis so you see token count and
optimization suggestions before Claude responds.

Install via .claude/settings.json:
{
  "hooks": {
    "UserPromptSubmit": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python /path/to/hooks/user_prompt_submit.py"
      }]
    }]
  }
}
"""
from __future__ import annotations

import json
import sys
import os
from pathlib import Path

# Resolve the observability package regardless of CWD
OBS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(OBS_DIR))

from core import db, analyzer, tracker
from core.config import DASHBOARD_PORT

db.init_db()

MIN_TOKENS_TO_WARN = 30   # skip analysis for very short prompts


def main() -> None:
    try:
        raw = sys.stdin.read()
        event = json.loads(raw)
    except Exception:
        sys.exit(0)

    prompt: str = event.get("prompt", "")
    if not prompt or not prompt.strip():
        sys.exit(0)

    token_count = tracker.estimate_tokens(prompt)
    if token_count < MIN_TOKENS_TO_WARN:
        # Still log but skip verbose output for short prompts
        _log_prompt(event, prompt, token_count)
        sys.exit(0)

    analysis = analyzer.analyze(prompt)
    _log_prompt(event, prompt, analysis.token_count)

    # Print analysis to stdout — Claude Code shows this as feedback
    output = _format_for_claude_code(analysis)
    print(output, flush=True)

    sys.exit(0)


def _log_prompt(event: dict, prompt: str, token_count: int) -> None:
    """Write the prompt to the observability DB for later dashboard viewing."""
    try:
        session_id = event.get("session_id", "cc-unknown")
        db.insert_session(session_id, model="unknown", source="claude-code")
        # We log with empty response — the PostToolUse hook or manual log_interaction
        # fills in the response side. For now we track the input.
        db.insert_interaction(
            session_id=session_id,
            prompt=prompt,
            response="",
            input_tokens=token_count,
            output_tokens=0,
            model="unknown",
            cost=0.0,
            category=analyzer.analyze(prompt).category if token_count >= MIN_TOKENS_TO_WARN else "other",
            optimization_score=100,
            suggestions=[],
        )
    except Exception:
        pass  # never fail the hook


def _format_for_claude_code(analysis: analyzer.PromptAnalysis) -> str:
    score = analysis.optimization_score
    score_icon = "✅" if score >= 85 else "⚠️" if score >= 65 else "🔴"
    dash = "─" * 56

    lines = [
        "",
        dash,
        f"  PROMPT OBSERVABILITY",
        f"  Tokens: ~{analysis.token_count}  │  Category: {analysis.category}  │  Score: {score_icon} {score}/100",
    ]

    if analysis.suggestions:
        savings = analysis.total_potential_savings
        lines.append(f"  Potential savings: ~{savings} tokens  │  Dashboard: http://localhost:{DASHBOARD_PORT}")
        lines.append("")

        # Show top 3 suggestions only (keep output compact)
        top = sorted(analysis.suggestions, key=lambda s: s.token_savings, reverse=True)[:3]
        for s in top:
            icon = {"high": "!", "medium": "~", "low": "·"}.get(s.priority, "·")
            saving_str = f"  (-{s.token_savings} tok)" if s.token_savings else ""
            tag = f"[{s.type}]"
            lines.append(f"  {icon} {tag:<16} {s.message}{saving_str}")

        if len(analysis.suggestions) > 3:
            more = len(analysis.suggestions) - 3
            lines.append(f"    + {more} more suggestion(s) at http://localhost:{DASHBOARD_PORT}")
    else:
        lines.append(f"  ✅ Prompt looks great! Dashboard: http://localhost:{DASHBOARD_PORT}")

    lines.append(dash)
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
