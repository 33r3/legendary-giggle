#!/usr/bin/env bash
# Consistent SQLite backup via the .backup command (safe on a live DB,
# unlike cp). Raw health data is irreplaceable — this should run daily.
set -euo pipefail

DB_PATH="/var/lib/exercise-rpg/raw.db"
BACKUP_DIR="/var/backups/exercise-rpg"
KEEP_DAYS=14

mkdir -p "$BACKUP_DIR"
sqlite3 "$DB_PATH" ".backup '$BACKUP_DIR/raw-$(date +%Y%m%d-%H%M%S).db'"
find "$BACKUP_DIR" -name 'raw-*.db' -mtime "+$KEEP_DAYS" -delete
