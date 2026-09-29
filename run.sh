#!/bin/bash
cd "$(dirname "$0")"
PORT="${PORT:-8000}"
if [ ! -x .venv/bin/uvicorn ]; then
  echo "No virtual environment found — creating .venv and installing dependencies..."
  python3 -m venv .venv
fi
.venv/bin/pip install -q -r requirements.txt
( sleep 1.5; open "http://127.0.0.1:${PORT}" ) &
exec .venv/bin/uvicorn app.main:app --port "${PORT}"
