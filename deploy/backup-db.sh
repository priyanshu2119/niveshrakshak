#!/usr/bin/env bash
# Nightly backup of the SQLite volume (registry mirror + audit log + SEBI cache).
#
# Why this exists: Oracle's idle reclamation is PERMANENT and unrecoverable, and
# the box also has no snapshot schedule on the Always Free tier. The registry
# half is regenerable (it re-downloads from sebi.gov.in), but the `checks` audit
# log is not.
#
# Keeps 14 daily copies on-box. Pull them to another machine with
# deploy/pull-backup.sh — an on-box backup does not survive instance reclamation.
#
# 🔴 Two bugs this version fixes:
#   1. It mounted `-v nr-data:/from`, but docker compose prefixes volumes with
#      the project name, so the real one is `niveshrakshak_nr-data`. The wrong
#      name silently auto-created an EMPTY volume and the copy died with
#      "can't stat '/from/nr.sqlite'".
#   2. It preferred the `sqlite3` CLI for a WAL-safe `.backup`, but the
#      python:3.11-slim image ships no sqlite3 binary — so that branch never ran
#      and it always fell back to a plain `cp` of a LIVE WAL database, which can
#      capture a torn state.
#   Both are gone: the snapshot now uses Python's sqlite3 backup API *inside* the
#   container — WAL-safe, no volume name needed, no extra packages.
set -euo pipefail

DEST="${NR_BACKUP_DIR:-$HOME/backups/niveshrakshak}"
KEEP=14
STAMP="$(date -u +%Y%m%d-%H%M%S)"
CONTAINER=niveshrakshak
TMP_IN_CONTAINER="/tmp/nr-backup-$STAMP.sqlite"

# `id -un`, not $USER: systemd does not set $USER for User= units. Prefer
# SUDO_USER when present so a manual `sudo bash backup-db.sh` does not leave
# root-owned files inside the invoking user's home directory.
OWNER="${SUDO_USER:-$(id -un)}"

mkdir -p "$DEST"
echo "[$(date -Is)] snapshotting $CONTAINER:/app/data/nr.sqlite"

# 1. Consistent online snapshot — safe while the app is writing (WAL mode).
# 🔴 `docker exec -i` — the -i is LOAD-BEARING. Without it docker does not
# forward stdin, so `python -` receives an empty program, does nothing and exits
# 0. `set -e` cannot catch that, and the failure only surfaces later as
# "Could not find the file … in container".
sudo -n docker exec -i "$CONTAINER" python - "$TMP_IN_CONTAINER" <<'PY'
import sqlite3, sys
dst_path = sys.argv[1]
src = sqlite3.connect("file:/app/data/nr.sqlite?mode=ro", uri=True)
dst = sqlite3.connect(dst_path)
with dst:
    src.backup(dst)
n = dst.execute("SELECT COUNT(*) FROM registry").fetchone()[0]
c = dst.execute("SELECT COUNT(*) FROM checks").fetchone()[0]
dst.close(); src.close()
if n == 0:
    sys.exit("refusing to back up an empty registry table")
print(f"  snapshot ok: registry={n} rows, checks={c} rows")
PY

# 2. Confirm the snapshot really exists before copying it out — a silent no-op
#    above must fail HERE, loudly, not produce a zero-byte "backup".
if ! sudo -n docker exec "$CONTAINER" test -s "$TMP_IN_CONTAINER"; then
  echo "🔴 snapshot was not created inside the container" >&2
  exit 1
fi

# 3. Copy out + compress.
sudo -n docker cp "$CONTAINER:$TMP_IN_CONTAINER" "$DEST/nr-$STAMP.sqlite"
sudo -n docker exec "$CONTAINER" rm -f "$TMP_IN_CONTAINER"
gzip -f "$DEST/nr-$STAMP.sqlite"
chown "$OWNER":"$OWNER" "$DEST/nr-$STAMP.sqlite.gz" 2>/dev/null || true
chmod 0600 "$DEST/nr-$STAMP.sqlite.gz"

# 4. Verify. A corrupt backup is worse than none — it is only discovered at the
#    moment it is needed.
if ! gzip -t "$DEST/nr-$STAMP.sqlite.gz" 2>/dev/null; then
  echo "🔴 gzip integrity check FAILED — removing" >&2
  rm -f "$DEST/nr-$STAMP.sqlite.gz"; exit 1
fi
# 🔴 The `|| true` inside the braces is load-bearing. `head -c 15` closes the
# pipe early, zcat dies of SIGPIPE and exits non-zero, and with `set -o pipefail`
# that kills the whole script AFTER a perfectly good backup was already written
# (observed in production: "gzip: stdout: Broken pipe"). Swallowing zcat's status
# here keeps the pipeline at 0 while still giving us the header bytes.
MAGIC="$( { zcat "$DEST/nr-$STAMP.sqlite.gz" 2>/dev/null || true; } | head -c 15 )"
if [ "$MAGIC" != "SQLite format 3" ]; then
  echo "🔴 not a SQLite file (got: $MAGIC) — removing" >&2
  rm -f "$DEST/nr-$STAMP.sqlite.gz"; exit 1
fi

# 5. Prune old copies.
ls -1t "$DEST"/nr-*.sqlite.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f

SIZE="$(du -h "$DEST/nr-$STAMP.sqlite.gz" | cut -f1)"
COUNT="$(ls -1 "$DEST"/nr-*.sqlite.gz 2>/dev/null | wc -l)"
echo "[$(date -Is)] ✅ verified backup nr-$STAMP.sqlite.gz ($SIZE) · keeping $COUNT/$KEEP"
