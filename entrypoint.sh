#!/bin/bash
set -e

# Display startup information
echo "Starting Photomatic..."
echo "Port: $PORT"

if [ -n "$CONFIG_FILE" ]; then
  echo "Config file: $CONFIG_FILE"
fi

# Run the application
exec python3 -m app.app "$@"
