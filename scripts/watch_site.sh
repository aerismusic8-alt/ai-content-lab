#!/usr/bin/env bash
# Keep the listening page served on port 12000.
#
# This sandbox is a pod that is recycled after ~20 min idle, so this watchdog
# dies with it; restart the script after a recycle. While the pod lives, it
# recovers the server from idle cleanup or a crash.
#
# A 502 on every path means the process is gone (not that the page is broken),
# so check `ps aux | grep http.server` before sharing a link.

PORT=12000
DIR="$(cd "$(dirname "$0")/.." && pwd)/site"

port_busy() {
  # `ss`/`netstat`/`lsof` are NOT installed in this image, and a missing tool
  # makes a pipe check report "free" even when the port is taken.
  python3 - "$PORT" <<'PY'
import socket, sys
s = socket.socket()
sys.exit(0 if s.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 1)
PY
}

start_server() {
  setsid nohup python3 -m http.server "$PORT" --directory "$DIR" \
    > /tmp/content_lab_http.log 2>&1 &
  sleep 2
}

if port_busy; then
  echo "$(date '+%F %T')  port $PORT already serving"
else
  start_server
  if port_busy; then
    echo "$(date '+%F %T')  started server on $PORT -> $DIR"
  else
    echo "$(date '+%F %T')  FAILED to bind $PORT (see /tmp/content_lab_http.log)"
  fi
fi
