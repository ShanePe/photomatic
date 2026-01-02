#!/bin/bash
source .venv/Scripts/activate
python3 app/app.py --photos /mnt/Pennicloud/Home/Photos --port 5050
deactivate

#!/bin/bash
set -e

# Default values
PHOTOS_DIR="/app/photo-storage"
PORT=5050

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --photos)
            PHOTOS_DIR="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo "Starting Photomatic with photos dir: $PHOTOS_DIR on port: $PORT"

# Run Flask app directly (no venv needed in Docker)
exec python3 -m app.app --photos "$PHOTOS_DIR" --port "$PORT"