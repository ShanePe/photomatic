#!/bin/bash
set -e

# Display startup information
echo "Starting Photomatic..."
echo "Port: $PORT"

if [ -n "$CONFIG_FILE" ]; then
  echo "Config file: $CONFIG_FILE"
fi

# Build the initial indexes before starting the web server. Scheduled rebuilds
# run in a separate process so image requests never trigger a directory scan.
python -m app.cache_service --build-once
python -m app.cache_service --schedule &
CACHE_SERVICE_PID=$!

# Production WSGI server settings (override via env vars if needed)
PORT="${PORT:-80}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-2}"
GUNICORN_THREADS="${GUNICORN_THREADS:-4}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-120}"
GUNICORN_LOG_LEVEL="${GUNICORN_LOG_LEVEL:-info}"
GUNICORN_MAX_REQUESTS="${GUNICORN_MAX_REQUESTS:-1000}"
GUNICORN_MAX_REQUESTS_JITTER="${GUNICORN_MAX_REQUESTS_JITTER:-100}"

echo "Starting Gunicorn with workers=$GUNICORN_WORKERS threads=$GUNICORN_THREADS timeout=${GUNICORN_TIMEOUT}s max_requests=$GUNICORN_MAX_REQUESTS max_requests_jitter=$GUNICORN_MAX_REQUESTS_JITTER log_level=$GUNICORN_LOG_LEVEL"

gunicorn \
  --workers "$GUNICORN_WORKERS" \
  --threads "$GUNICORN_THREADS" \
  --timeout "$GUNICORN_TIMEOUT" \
  --max-requests "$GUNICORN_MAX_REQUESTS" \
  --max-requests-jitter "$GUNICORN_MAX_REQUESTS_JITTER" \
  --log-level "$GUNICORN_LOG_LEVEL" \
  --bind "0.0.0.0:$PORT" \
  app.wsgi:application \
  "$@" &
GUNICORN_PID=$!

shutdown() {
  kill -TERM "$GUNICORN_PID" "$CACHE_SERVICE_PID" 2>/dev/null || true
  wait "$GUNICORN_PID" 2>/dev/null || true
  wait "$CACHE_SERVICE_PID" 2>/dev/null || true
}
trap shutdown TERM INT

if wait "$GUNICORN_PID"; then
  GUNICORN_STATUS=0
else
  GUNICORN_STATUS=$?
fi
shutdown
exit "$GUNICORN_STATUS"
