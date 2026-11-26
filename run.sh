#!/usr/bin/env bash
# Start the PyCraft game on Linux/macOS (creates a local virtualenv on first run).
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
fi
exec .venv/bin/python pycraft.py "$@"
