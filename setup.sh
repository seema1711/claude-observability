#!/usr/bin/env bash
# Claude Observability — One-time setup
set -euo pipefail

OBS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_SCRIPT="$OBS_DIR/hooks/user_prompt_submit.py"
POST_HOOK="$OBS_DIR/hooks/post_tool_use.py"
CLAUDE_SETTINGS="$HOME/.claude/settings.json"

echo "=== Claude Observability Setup ==="
echo "Installation directory: $OBS_DIR"
echo ""

# ── 1. Python dependencies ──────────────────────────────────────────────────
echo "[1/5] Installing Python dependencies..."
pip install -q -r "$OBS_DIR/requirements.txt"
echo "    Done."

# ── 2. Init database ────────────────────────────────────────────────────────
echo "[2/5] Initialising database..."
cd "$OBS_DIR" && python -c "import db; db.init_db(); print('    DB initialised:', db.DB_PATH)"

# ── 3. Make hook scripts executable ─────────────────────────────────────────
echo "[3/5] Making hook scripts executable..."
chmod +x "$HOOK_SCRIPT" "$POST_HOOK"
echo "    Done."

# ── 4. Patch Claude Code settings.json ──────────────────────────────────────
echo "[4/5] Configuring Claude Code hooks..."

PYTHON_BIN="$(which python3 || which python)"

HOOK_CMD="$PYTHON_BIN $HOOK_SCRIPT"
POST_CMD="$PYTHON_BIN $POST_HOOK"

mkdir -p "$HOME/.claude"

if [ ! -f "$CLAUDE_SETTINGS" ]; then
  echo "{}" > "$CLAUDE_SETTINGS"
fi

# Use Python to safely merge the hook config
python3 - <<PYEOF
import json, sys, os

settings_path = os.path.expanduser("~/.claude/settings.json")
hook_cmd      = "$HOOK_CMD"
post_cmd      = "$POST_CMD"

with open(settings_path) as f:
    settings = json.load(f)

hooks = settings.setdefault("hooks", {})

# UserPromptSubmit hook
ups_hooks = hooks.setdefault("UserPromptSubmit", [])
ups_entry = {
    "matcher": "",
    "hooks": [{"type": "command", "command": hook_cmd}]
}
# Avoid duplicates
existing_cmds = [h["command"] for e in ups_hooks for h in e.get("hooks", [])]
if hook_cmd not in existing_cmds:
    ups_hooks.append(ups_entry)
    print("    Added UserPromptSubmit hook.")
else:
    print("    UserPromptSubmit hook already present.")

# PostToolUse hook
ptu_hooks = hooks.setdefault("PostToolUse", [])
ptu_entry = {
    "matcher": "",
    "hooks": [{"type": "command", "command": post_cmd}]
}
existing_cmds_ptu = [h["command"] for e in ptu_hooks for h in e.get("hooks", [])]
if post_cmd not in existing_cmds_ptu:
    ptu_hooks.append(ptu_entry)
    print("    Added PostToolUse hook.")
else:
    print("    PostToolUse hook already present.")

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)

print("    Settings saved to", settings_path)
PYEOF

# ── 5. Claude Desktop MCP config hint ───────────────────────────────────────
echo ""
echo "[5/5] Claude Desktop MCP configuration"
echo ""
echo "    To connect Claude Desktop to the observability MCP server,"
echo "    add the following to your Claude Desktop config:"
echo ""

DESKTOP_CONFIG_MAC="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
DESKTOP_CONFIG_LIN="$HOME/.config/claude/claude_desktop_config.json"

if [ "$(uname)" = "Darwin" ]; then
  DESKTOP_CONFIG="$DESKTOP_CONFIG_MAC"
else
  DESKTOP_CONFIG="$DESKTOP_CONFIG_LIN"
fi

echo "    Config file: $DESKTOP_CONFIG"
echo ""
echo '    "mcpServers": {'
echo '      "observability": {'
echo "        \"command\": \"$(which python3 || which python)\","
echo "        \"args\": [\"$OBS_DIR/mcp_server.py\"]"
echo '      }'
echo '    }'
echo ""

# Optionally auto-patch Claude Desktop config
if [ -f "$DESKTOP_CONFIG" ]; then
  python3 - <<PYEOF2
import json, os

cfg_path = "$DESKTOP_CONFIG"
obs_dir  = "$OBS_DIR"
import subprocess
py_bin = subprocess.check_output(["which", "python3"], text=True).strip()

with open(cfg_path) as f:
    cfg = json.load(f)

servers = cfg.setdefault("mcpServers", {})
if "observability" not in servers:
    servers["observability"] = {
        "command": py_bin,
        "args": [os.path.join(obs_dir, "mcp_server.py")]
    }
    with open(cfg_path, "w") as f:
        json.dump(cfg, f, indent=2)
    print("    Automatically added MCP server to Claude Desktop config!")
    print("    Restart Claude Desktop to activate.")
else:
    print("    MCP server already in Claude Desktop config.")
PYEOF2
fi

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Start the dashboard:  python $OBS_DIR/dashboard/app.py"
echo "  2. Open dashboard:       http://localhost:7891"
echo "  3. Start MCP server:     python $OBS_DIR/mcp_server.py"
echo "  4. Restart Claude Desktop (if you edited its config)"
echo "  5. Use Claude Code as usual — you'll see analysis before every response!"
echo ""
