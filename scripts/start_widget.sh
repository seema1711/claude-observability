#!/usr/bin/env bash
OBS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$OBS_DIR/.venv/bin/python3" "$OBS_DIR/menubar_widget.py"
