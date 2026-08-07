#!/usr/bin/env bash
# Pulls the latest code, applies migrations, and restarts the service.
# Run on the VPS as the app owner (needs sudo for the restart).
#
# Relies on APP_DIR/.env being a symlink to the real secrets file (set up
# once in deploy/README.md step 3) — without it, `alembic upgrade head`
# below would silently fall back to dev defaults instead of the real DB.
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
