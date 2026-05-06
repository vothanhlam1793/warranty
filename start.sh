#!/bin/bash
# Start Warranty Management System

cd "$(dirname "$0")"
ROOT="$(pwd)"

echo "=== Warranty Management System ==="
echo ""

# Kill any existing server on port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null || true
sleep 1

echo "Starting backend API on http://localhost:8000 ..."
cd "$ROOT/apps/server" && PYTHONPATH="$ROOT/apps" \
  "$ROOT/apps/server/.venv/bin/uvicorn" server.main:app \
  --host 0.0.0.0 --port 8000 --reload \
  > /tmp/warranty-server.log 2>&1 &
cd "$ROOT"

SERVER_PID=$!
echo "Server PID: $SERVER_PID"
sleep 4

# Verify
if curl -s http://localhost:8000/api/health > /dev/null; then
  echo "✓ API is running"
else
  echo "✗ API failed to start. Check /tmp/warranty-server.log"
  exit 1
fi

# Serve frontend
echo ""
echo "Starting web frontend on http://localhost:3000 ..."
cd "$ROOT/apps/web"
python3 -m http.server 3000 > /tmp/warranty-web.log 2>&1 &
WEB_PID=$!
echo "Web PID: $WEB_PID"
sleep 1

echo ""
echo "==================================="
echo "  Backend  → http://localhost:8000"
echo "  Frontend  → http://localhost:3000"
echo "  API docs  → http://localhost:8000/docs"
echo "==================================="
echo ""
echo "Press Ctrl+C to stop both servers"

trap "kill $SERVER_PID $WEB_PID 2>/dev/null; echo 'Stopped.'" EXIT INT TERM
wait
