#!/bin/bash
set -e

source .venv/Scripts/activate
python3 -m app.app
deactivate