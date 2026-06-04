#!/bin/bash
set -e

# Display startup information
echo "Starting Photomatic..."
echo "Port: $PORT"

if [ -n "$CONFIG_FILE" ]; then
  echo "Config file: $CONFIG_FILE"
fi

# Production WSGI server settings (override via env vars if needed)
PORT="${PORT:-80}"
GUNICORN_WORKERS="${GUNICORN_WORKERS:-2}"
GUNICORN_THREADS="${GUNICORN_THREADS:-4}"
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-120}"
GUNICORN_LOG_LEVEL="${GUNICORN_LOG_LEVEL:-info}"

echo "Starting Gunicorn with workers=$GUNICORN_WORKERS threads=$GUNICORN_THREADS timeout=${GUNICORN_TIMEOUT}s log_level=$GUNICORN_LOG_LEVEL"

exec gunicorn \
  --workers "$GUNICORN_WORKERS" \
  --threads "$GUNICORN_THREADS" \
  --timeout "$GUNICORN_TIMEOUT" \
  --log-level "$GUNICORN_LOG_LEVEL" \
  --bind "0.0.0.0:$PORT" \
  app.wsgi:application \
  "$@"
