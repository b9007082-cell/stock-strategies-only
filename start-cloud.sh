#!/bin/sh
set -eu
.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000 &
cd web
exec npm run start -- --hostname 0.0.0.0 --port "${PORT:-10000}"
