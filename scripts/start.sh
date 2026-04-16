#!/bin/bash
echo "PORT from env: ${PORT:-not set}"
exec /opt/venv/bin/uvicorn gyros_os.server.main:app --host 0.0.0.0 --port "${PORT:-8080}"
