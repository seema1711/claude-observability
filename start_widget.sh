#!/usr/bin/env bash
OBS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$OBS_DIR"
exec .venv/bin/python3 menubar_widget.py
