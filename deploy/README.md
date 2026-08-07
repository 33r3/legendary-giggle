# Deploying to the VPS

Assumes Ubuntu, nginx already installed, and that you're comfortable
running these as root/sudo over SSH. Everything here is a template —
adjust paths if you want something different.

## Layout

- App code: `/opt/exercise-rpg` (this repo, checked out)
- Persistent data (SQLite DB): `/var/lib/exercise-rpg`
- Secrets: `/etc/exercise-rpg/exercise-rpg.env`
- Runs as a dedicated system user (`exercise-rpg`), not root, not you
- nginx terminates TLS and reverse-proxies to the app on `127.0.0.1:8000`
  — the app itself is never exposed directly

## 1. System user and directories

```
sudo useradd --system --create-home --home-dir /opt/exercise-rpg --shell /usr/sbin/nologin exercise-rpg
sudo mkdir -p /var/lib/exercise-rpg /etc/exercise-rpg
sudo chown exercise-rpg:exercise-rpg /var/lib/exercise-rpg /etc/exercise-rpg
sudo chmod 700 /etc/exercise-rpg
```

## 2. Get the code and install

```
sudo -u exercise-rpg git clone <this repo's URL> /opt/exercise-rpg
cd /opt/exercise-rpg
sudo -u exercise-rpg python3 -m venv .venv
sudo -u exercise-rpg .venv/bin/pip install -e ".[dev]"
```

## 3. Secrets

There are exactly two things that need to be secret, plus one path that's
environment-specific. Generate them and write `/etc/exercise-rpg/exercise-rpg.env`:

```
sudo tee /etc/exercise-rpg/exercise-rpg.env > /dev/null <<EOF
DATABASE_URL=sqlite:////var/lib/exercise-rpg/raw.db
INGEST_WEBHOOK_TOKEN=$(openssl rand -hex 32)
GAME_SEED=$(openssl rand -hex 16)
EOF
sudo chown exercise-rpg:exercise-rpg /etc/exercise-rpg/exercise-rpg.env
sudo chmod 600 /etc/exercise-rpg/exercise-rpg.env
sudo -u exercise-rpg ln -s /etc/exercise-rpg/exercise-rpg.env /opt/exercise-rpg/.env
```

That symlink matters: the app loads config from a `.env` file in its working
directory (`/opt/exercise-rpg`), and this makes every invocation — the
systemd service, `deploy.sh`, and any one-off script you run by hand —
pick up the real secrets automatically. Without it, only the systemd
service (which also gets them via `EnvironmentFile=` in the unit file)
would see them; a manual `alembic upgrade head` or `python scripts/...`
run straight in a shell would silently fall back to the built-in dev
defaults instead — including a relative, never-created SQLite path,
which is exactly what produces `unable to open database file`.

- **`INGEST_WEBHOOK_TOKEN`** — the shared secret your HealthKit export app
  sends as `Authorization: Bearer <token>`. Read it back out with
  `sudo cat /etc/exercise-rpg/exercise-rpg.env` when you configure that app.
- **`GAME_SEED`** — drives every generated (not committed) balance number:
  the passive-tier curve, session roll cap, and region unlock costs. This
  is the one value where losing it or changing it later actually matters
  — changing it after the fact regenerates different numbers next time you
  materialize, which is fine for a deliberate retune but not something to
  do by accident. Keep a copy somewhere durable outside this file (a
  password manager is fine); it's not committed anywhere.
- **`DATABASE_URL`** — not secret, just environment-specific (points at
  the real DB path instead of the local dev default).

This file is never in git — it's the one artifact from this whole setup
that has to be created by hand on the box, and it's the only thing you'd
need to restore by hand if you ever rebuild the VPS from scratch (the DB
itself you'd restore from backup — see step 7).

## 4. Migrate and load content

First deploy only for the `materialize_*` scripts — they're not meant to
be rerun casually (see the note below).

Sanity check before running anything — this should print the real
`/var/lib/exercise-rpg/raw.db` path, not the local dev default:

```
cd /opt/exercise-rpg
sudo -u exercise-rpg .venv/bin/python -c "from app.config import get_settings; print(get_settings().database_url)"
```

```
sudo -u exercise-rpg .venv/bin/alembic upgrade head
sudo -u exercise-rpg .venv/bin/python scripts/materialize_economy.py
sudo -u exercise-rpg .venv/bin/python scripts/load_regions.py
sudo -u exercise-rpg .venv/bin/python scripts/load_drop_tables.py
sudo -u exercise-rpg .venv/bin/python scripts/materialize_unlock_costs.py
```

`materialize_economy.py` inserts a *new version* of the reward curve
every time it runs — that's deliberate (see `PassiveTierConfig` /
`SessionTierConfig` in the design), but it means you shouldn't run it
again except when an actual retune is intended. `load_regions.py`,
`load_drop_tables.py`, and `materialize_unlock_costs.py` are all safe to
rerun any time (upsert/idempotent).

## 5. systemd service

```
sudo cp deploy/systemd/exercise-rpg.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now exercise-rpg
sudo systemctl status exercise-rpg
```

Confirm it's alive locally before touching nginx:

```
curl http://127.0.0.1:8000/healthz
```

## 6. nginx + TLS

```
sudo cp deploy/nginx/exercise-rpg.conf /etc/nginx/sites-available/exercise-rpg
sudo sed -i 's/__DOMAIN__/your.actual.domain/' /etc/nginx/sites-available/exercise-rpg
sudo ln -s /etc/nginx/sites-available/exercise-rpg /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d your.actual.domain
```

Certbot rewrites the config in place to add the TLS server block and an
HTTP→HTTPS redirect. Point DNS at the box before running certbot.

## 7. Firewall

If using `ufw`, only 80/443/22 need to be open — the app port (8000)
should stay unreachable from outside:

```
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable   # if not already
```

## 8. Point the export app at it

Configure your HealthKit export app to POST to:

```
https://your.actual.domain/ingest/healthkit
```

with header `Authorization: Bearer <INGEST_WEBHOOK_TOKEN from step 3>`.

## 9. Backups

Raw health data is append-only and irreplaceable — back it up.

```
sudo cp deploy/backup_db.sh /opt/exercise-rpg/deploy/backup_db.sh
sudo chmod +x /opt/exercise-rpg/deploy/backup_db.sh
sudo crontab -e   # add: 0 3 * * * /opt/exercise-rpg/deploy/backup_db.sh
```

That keeps 14 days of backups on the same box, which protects against a
bad deploy or accidental deletion but not against losing the box itself.
Worth copying `/var/backups/exercise-rpg` somewhere off-box periodically
(another machine, object storage) if you want real disaster recovery —
not set up here since it depends on what you've got available.

## Redeploying

After the first setup, routine code updates are:

```
/opt/exercise-rpg/deploy/deploy.sh
```

Run as yourself, not as `exercise-rpg` and not prefixed with
`sudo -u exercise-rpg` — the script sudos to that user internally only
where it needs to (see the comment at the top of the script for why).

This pulls, migrates, and restarts. It does **not** rerun the
`materialize_*` scripts or reload content — run `load_regions.py` /
`load_drop_tables.py` by hand (safe to rerun) whenever content actually
changes.

## Processing sessions

`scripts/process_sessions.py` isn't wired to run automatically yet — for
now, run it by hand (or add it to `deploy.sh` / a cron job) after new
workouts come in:

```
sudo -u exercise-rpg /opt/exercise-rpg/.venv/bin/python /opt/exercise-rpg/scripts/process_sessions.py
```

A timer that runs it every few minutes would be the natural next step
once you're ready to stop doing that by hand.
