#!/bin/sh
set -eu
.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000 &
cd web
npm run start -- --hostname 127.0.0.1 --port 3000 &
exec nginx -g 'daemon off;'
