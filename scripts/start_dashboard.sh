#!/usr/bin/env bash
OBS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Starting Claude Observability Dashboard at http://localhost:7891"
exec "$OBS_DIR/.venv/bin/python3" "$OBS_DIR/dashboard/app.py"
