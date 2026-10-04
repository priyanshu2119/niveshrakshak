#!/usr/bin/env bash
# Deploy the NiveshRakshak backend to the Oracle VPS.
#
#   ./deploy/deploy.sh            # rsync + build + restart
#   ./deploy/deploy.sh --seed     # also push the local registry mirror into the volume
#
# Requires the `hermes` ssh alias (see deploy/README.md) and passwordless sudo
# on the VPS for docker.
set -euo pipefail

cd "$(dirname "$0")/.."
REPO="$(pwd)"
HOST="${NR_VPS_HOST:-hermes}"
REMOTE="${NR_REMOTE_DIR:-~/niveshrakshak}"
SEED="${1:-}"

echo "→ repo:    $REPO"
echo "→ target:  $HOST:$REMOTE"

# --- 1. sync source -----------------------------------------------------------
echo "→ rsync source…"
rsync -az --delete \
  --exclude '.git' --exclude '.venv' --exclude '__pycache__' \
  --exclude '*.pyc' --exclude '.pytest_cache' \
  --exclude 'data/' --exclude 'android/' --exclude 'node_modules/' \
  ./ "$HOST:$REMOTE/"

# --- 2. optionally seed the registry mirror -----------------------------------
if [ "$SEED" = "--seed" ]; then
  echo "→ checkpointing local WAL so the seed DB is self-contained…"
  python3 - <<'PY'
import sqlite3, os
p = "data/nr.sqlite"
if os.path.exists(p):
    c = sqlite3.connect(p)
    c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    c.close()
    print("   ok:", p, os.path.getsize(p), "bytes")
else:
    print("   (no local data/nr.sqlite — skipping seed)")
PY
  if [ -f data/nr.sqlite ]; then
    echo "→ pushing seed DB…"
    rsync -az --progress data/nr.sqlite "$HOST:$REMOTE/seed-nr.sqlite"
    # 🔴 chown -R the DIRECTORY, not just the file. SQLite runs in WAL mode and
    # must CREATE nr.sqlite-wal / nr.sqlite-shm alongside it — that needs write
    # permission on the directory. A root-owned dir with a 10001-owned file
    # fails at startup with "attempt to write a readonly database".
    ssh "$HOST" "sudo -n docker volume create niveshrakshak_nr-data >/dev/null 2>&1 || true; \
      sudo -n docker run --rm -v niveshrakshak_nr-data:/data -v \$HOME/niveshrakshak:/src alpine \
      sh -c 'cp /src/seed-nr.sqlite /data/nr.sqlite && chown -R 10001:10001 /data && ls -lan /data'"
  fi
fi

# --- 3. build + start ---------------------------------------------------------
echo "→ building and starting container (this pulls python:3.11-slim + apt on first run)…"
ssh "$HOST" "cd $REMOTE && sudo -n docker compose up -d --build"

# --- 4. wait for health -------------------------------------------------------
echo "→ waiting for /api/health…"
for i in $(seq 1 40); do
  if ssh "$HOST" "curl -fsS -m 5 http://127.0.0.1:8300/api/health" >/tmp/nr-health.json 2>/dev/null; then
    echo "✅ healthy after ${i}0s-ish:"
    python3 -m json.tool /tmp/nr-health.json 2>/dev/null || cat /tmp/nr-health.json
    exit 0
  fi
  sleep 5
done

echo "🔴 not healthy after ~200s. Last 40 log lines:"
ssh "$HOST" "cd $REMOTE && sudo -n docker compose logs --tail=40"
exit 1
