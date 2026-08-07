#!/usr/bin/env bash
# Pulls the latest code, applies migrations, and restarts the service.
#
# Run this as YOURSELF (a sudo-capable user) — not as exercise-rpg, and
# not prefixed with `sudo -u exercise-rpg`. It sudos to exercise-rpg
# internally only for the file/app operations that need that user's
# ownership context; the service restart needs real sudo, which the
# exercise-rpg account deliberately doesn't have.
#
# Relies on APP_DIR/.env being a symlink to the real secrets file (set up
# once in deploy/README.md step 3) — without it, `alembic upgrade head`
# below would silently fall back to dev defaults instead of the real DB.
set -euo pipefail

APP_DIR="/opt/exercise-rpg"
SERVICE="exercise-rpg"
AS_APP_USER="sudo -u exercise-rpg"

cd "$APP_DIR"
$AS_APP_USER git pull
$AS_APP_USER .venv/bin/pip install -e ".[dev]" -q
$AS_APP_USER .venv/bin/alembic upgrade head

sudo systemctl restart "$SERVICE"
sudo systemctl status "$SERVICE" --no-pager
