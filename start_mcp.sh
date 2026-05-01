#!/usr/bin/env bash
# Start the MCP server (stdio transport — Claude Desktop launches this directly)
OBS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$OBS_DIR"
exec python mcp_server.py
