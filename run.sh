#!/usr/bin/env bash
# Start the app on 127.0.0.1:$PORT and a cloudflared quick tunnel (HTTPS, needed for the mic).
# PIDs go to run/*.pid so stop.sh kills only these two processes.
set -euo pipefail
cd "$(dirname "$0")"
PORT=$(grep -E '^PORT=' .env | cut -d= -f2 || true); PORT=${PORT:-5040}
mkdir -p run logs
if [ -f run/app.pid ] && kill -0 "$(cat run/app.pid)" 2>/dev/null; then
  echo "app already running (pid $(cat run/app.pid))"
else
  nohup .venv/bin/uvicorn api.index:app --host 127.0.0.1 --port "$PORT" >> logs/app.log 2>&1 &
  echo $! > run/app.pid
  echo "app started on 127.0.0.1:$PORT (pid $!)"
fi
if [ "${1:-}" = "--no-tunnel" ]; then exit 0; fi
if [ -f run/tunnel.pid ] && kill -0 "$(cat run/tunnel.pid)" 2>/dev/null; then
  echo "tunnel already running (pid $(cat run/tunnel.pid))"
else
  : > logs/tunnel.log
  nohup cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$PORT" >> logs/tunnel.log 2>&1 &
  echo $! > run/tunnel.pid
  echo "tunnel started (pid $!)"
fi
for _ in $(seq 1 30); do
  URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' logs/tunnel.log | head -1 || true)
  [ -n "$URL" ] && { echo "public URL: $URL"; exit 0; }
  sleep 1
done
echo "tunnel URL not found yet; see logs/tunnel.log"
