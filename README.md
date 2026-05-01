# Claude Observability

Real-time prompt analysis, token tracking, and cost monitoring for Claude — via Claude Code hooks and an MCP server.

## What it does

- **Prompt analysis** — scores every prompt 0–100 and surfaces actionable suggestions (verbosity, structure, caching opportunities, redundancy)
- **Token tracking** — estimates input/output tokens for every interaction and stores them in a local SQLite database
- **Cost estimation** — calculates USD cost per interaction based on current Claude model pricing
- **Claude Code hooks** — automatically fires before each prompt (`UserPromptSubmit`) and after each tool call (`PostToolUse`) so you see analysis inline without any manual steps
- **MCP server** — connect to Claude Desktop for the same analysis inside any Claude conversation
- **Web dashboard** — Flask app at `http://localhost:7891` with charts, a live prompt tester, and a table of your most expensive prompts

## Project structure

```
.
├── mcp_server.py              # MCP server (FastMCP) — 7 tools
├── analyzer.py                # Rule-based prompt analyzer
├── tracker.py                 # Token counting & cost calculation
├── db.py                      # SQLite database layer
├── config.py                  # Model pricing & config
├── requirements.txt
├── setup.sh                   # One-time setup script
├── start_dashboard.sh
├── start_mcp.sh
├── CLAUDE.md                  # System instructions for Claude
├── dashboard/
│   ├── app.py                 # Flask API
│   └── templates/
│       └── index.html         # Dashboard UI
└── hooks/
    ├── user_prompt_submit.py  # Claude Code UserPromptSubmit hook
    └── post_tool_use.py       # Claude Code PostToolUse hook
```

## Quick start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run setup (installs hooks + configures Claude Desktop)

```bash
bash setup.sh
```

This will:
- Install Python dependencies
- Initialise the SQLite database
- Register the `UserPromptSubmit` and `PostToolUse` hooks in `~/.claude/settings.json`
- Auto-patch Claude Desktop's MCP config if it exists

### 3. Start the dashboard

```bash
bash start_dashboard.sh
# or
python dashboard/app.py
```

Open `http://localhost:7891` in your browser.

### 4. Start the MCP server (Claude Desktop)

```bash
bash start_mcp.sh
```

Or add it to your Claude Desktop config manually:

```json
{
  "mcpServers": {
    "observability": {
      "command": "python",
      "args": ["/path/to/mcp_server.py"]
    }
  }
}
```

## MCP tools

| Tool | Description |
|------|-------------|
| `analyze_prompt` | Token count, category, score, and suggestions for a prompt |
| `log_interaction` | Log a prompt/response pair with token counts and cost |
| `get_stats` | Usage statistics for the last N days |
| `get_optimization_report` | Full report with most expensive prompts and top recommendations |
| `estimate_tokens` | Token count and per-model cost estimate for any text |
| `get_prompt_history` | Most recent N logged interactions |
| `start_session` | Start a new tracked session and get a `session_id` |

## Optimization score

Each prompt is scored 0–100 (higher = better). Points are deducted for:

| Issue | Severity |
|-------|----------|
| Filler phrases ("Please", "Could you", "I would like you to") | low – medium |
| Long wall-of-text paragraphs | medium |
| 3+ questions in one prompt | medium |
| Persona/role definition not in system prompt | high |
| Prompt >1024 tokens without caching | high |
| Near-duplicate sentences | medium |

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | Enables exact token counts via the API (optional; falls back to estimation) |
| `OBSERVABILITY_DASHBOARD_PORT` | `7891` | Port for the Flask dashboard |

## Requirements

- Python 3.10+
- `anthropic>=0.40.0`
- `mcp>=1.9.0`
- `flask>=3.0.0`
- `tiktoken>=0.7.0`
- `rich>=13.7.0`
- `click>=8.1.7`
