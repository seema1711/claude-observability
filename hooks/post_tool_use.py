#!/usr/bin/env python3
"""
Claude Code hook: PostToolUse (optional — for deeper tracking)

Captures tool call events and logs them so the dashboard can
show which tools consume the most tokens.

Install via .claude/settings.json alongside UserPromptSubmit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

OBS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(OBS_DIR))

import db
import tracker
db.init_db()


def main() -> None:
    try:
        raw = sys.stdin.read()
        event = json.loads(raw)
    except Exception:
        sys.exit(0)

    tool_name: str = event.get("tool_name", "")
    tool_input: dict = event.get("tool_input", {})
    tool_response = event.get("tool_response", {})

    # Estimate tokens used by large tool calls (e.g. Read, Bash with long output)
    input_text = json.dumps(tool_input)
    output_text = json.dumps(tool_response) if isinstance(tool_response, (dict, list)) else str(tool_response)

    in_tok = tracker.estimate_tokens(input_text)
    out_tok = tracker.estimate_tokens(output_text)

    # Only log tool calls with significant token usage
    if in_tok + out_tok < 50:
        sys.exit(0)

    session_id = event.get("session_id", "cc-unknown")
    db.insert_session(session_id, model="unknown", source="claude-code")

    try:
        db.insert_interaction(
            session_id=session_id,
            prompt=f"[tool:{tool_name}] {input_text[:500]}",
            response=output_text[:500],
            input_tokens=in_tok,
            output_tokens=out_tok,
            model="unknown",
            cost=0.0,
            category="code",
            optimization_score=100,
            suggestions=[],
        )
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
