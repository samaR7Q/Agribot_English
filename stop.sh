#!/usr/bin/env bash
# Stop only the app and tunnel started by run.sh (by their saved PIDs).
cd "$(dirname "$0")"
for name in tunnel app; do
  f="run/$name.pid"
  if [ -f "$f" ] && kill -0 "$(cat "$f")" 2>/dev/null; then
    kill "$(cat "$f")" && echo "stopped $name (pid $(cat "$f"))"
  fi
  rm -f "$f"
done
