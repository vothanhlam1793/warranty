#!/bin/bash
# Start Warranty Management System

cd "$(dirname "$0")"
ROOT="$(pwd)"

echo "=== Warranty Management System ==="
echo ""

# Load environment variables
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

BACKEND_PORT=${BACKEND_PORT:-8001}
FRONTEND_PORT=${FRONTEND_PORT:-3000}

echo "=== Warranty Management System ==="
echo "Backend Port: $BACKEND_PORT"
echo "Frontend Port: $FRONTEND_PORT"
echo ""

# Kill any existing server on ports
lsof -ti:$BACKEND_PORT | xargs kill -9 2>/dev/null || true
lsof -ti:$FRONTEND_PORT | xargs kill -9 2>/dev/null || true
sleep 1

echo "Starting backend API on http://localhost:$BACKEND_PORT ..."
cd "$ROOT/apps/server" && PYTHONPATH="$ROOT/apps" \
  "$ROOT/apps/server/.venv/bin/uvicorn" server.main:app \
  --host 0.0.0.0 --port $BACKEND_PORT --reload \
  > /tmp/warranty-server.log 2>&1 &
cd "$ROOT"

SERVER_PID=$!
echo "Server PID: $SERVER_PID"
sleep 4

# Verify
if curl -s http://localhost:$BACKEND_PORT/api/health > /dev/null; then
  echo "✓ API is running"
else
  echo "✗ API failed to start. Check /tmp/warranty-server.log"
  exit 1
fi

# Serve frontend
echo ""
echo "Starting web frontend on http://localhost:$FRONTEND_PORT ..."
cd "$ROOT/apps/web"
python3 -m http.server $FRONTEND_PORT > /tmp/warranty-web.log 2>&1 &
WEB_PID=$!
echo "Web PID: $WEB_PID"
sleep 1

echo ""
echo "==================================="
echo "  Backend  → http://localhost:$BACKEND_PORT"
echo "  Frontend  → http://localhost:$FRONTEND_PORT"
echo "  API docs  → http://localhost:$BACKEND_PORT/docs"
echo "==================================="
echo ""
echo "Press Ctrl+C to stop both servers"

trap "kill $SERVER_PID $WEB_PID 2>/dev/null; echo 'Stopped.'" EXIT INT TERM
wait
