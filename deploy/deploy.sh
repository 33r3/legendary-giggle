#!/usr/bin/env bash
# Pulls the latest code, applies migrations, and restarts the service.
# Run on the VPS as the app owner (needs sudo for the restart).
set -euo pipefail

APP_DIR="/opt/exercise-rpg"
SERVICE="exercise-rpg"

cd "$APP_DIR"
git pull
source .venv/bin/activate
pip install -e ".[dev]" -q
alembic upgrade head
deactivate

sudo systemctl restart "$SERVICE"
sudo systemctl status "$SERVICE" --no-pager
