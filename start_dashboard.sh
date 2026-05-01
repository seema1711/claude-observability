#!/usr/bin/env bash
# Start the observability dashboard
OBS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$OBS_DIR"
echo "Starting Claude Observability Dashboard at http://localhost:7891"
python dashboard/app.py
