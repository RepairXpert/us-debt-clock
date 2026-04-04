#!/bin/bash

# Run US Debt Clock in development mode

set -a
source .env 2>/dev/null || true
set +a

# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start API in background
echo "Starting API server on port 8500..."
python api.py &
API_PID=$!

# Wait for API to start
sleep 3

# Start monitor
echo "Starting health monitor..."
python self_heal.py &
MONITOR_PID=$!

echo "Servers running:"
echo "  API: http://localhost:8500"
echo "  PIDs: API=$API_PID, Monitor=$MONITOR_PID"
echo
echo "Press Ctrl+C to stop all services"

# Trap to kill both on exit
trap "kill $API_PID $MONITOR_PID 2>/dev/null" EXIT

wait
