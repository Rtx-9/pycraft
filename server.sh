#!/usr/bin/env bash
# Start a headless PyCraft dedicated server on Linux.
#   ./server.sh                         new world in ~/.pycraft/server_world.sav, port 25565
#   ./server.sh --password hunter2 --max-players 12 --port 25570
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
fi
exec .venv/bin/python pycraft.py --server "$@"
