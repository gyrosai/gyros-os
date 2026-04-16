#!/bin/bash
PORT="${PORT:-8080}"
exec /opt/venv/bin/uvicorn gyros_os.server.main:app --host 0.0.0.0 --port "$PORT"
