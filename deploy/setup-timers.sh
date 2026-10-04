#!/usr/bin/env bash
# Install the maintenance jobs as SYSTEMD TIMERS. Run ON THE VPS:
#
#   sudo bash deploy/setup-timers.sh
#
# 🔴 Why not cron: the Oracle Ubuntu 24.04 ARM image ships WITHOUT the cron
# package (`apt-cache policy cron` → "Installed: (none)"). A file dropped in
# /etc/cron.d is therefore silently ignored — which is exactly what happened:
# the anti-idle job never ran for two days, leaving the instance exposed to
# Oracle's idle reclamation, and no backups were ever created.
# systemd timers are the native mechanism on this image (5 are already active)
# and Persistent=true replays missed runs on boot.
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST=/opt/niveshrakshak
RUN_USER="${SUDO_USER:-ubuntu}"
RUN_HOME="$(getent passwd "$RUN_USER" | cut -d: -f6)"

echo "→ installing scripts to $DEST"
mkdir -p "$DEST" "$RUN_HOME/backups/niveshrakshak" /var/log
install -m 0755 "$SRC/anti-idle.sh" "$DEST/anti-idle.sh"
install -m 0755 "$SRC/backup-db.sh" "$DEST/backup-db.sh"
install -m 0644 "$SRC/README.md"    "$DEST/README.md" 2>/dev/null || true
touch /var/log/nr-anti-idle.log && chmod 0644 /var/log/nr-anti-idle.log
chown -R "$RUN_USER":"$RUN_USER" "$RUN_HOME/backups"

echo "→ removing the dead cron.d entry (cron is not installed on this image)"
rm -f /etc/cron.d/niveshrakshak

echo "→ installing systemd units"
install -m 0644 "$SRC/systemd/nr-anti-idle.service" /etc/systemd/system/
install -m 0644 "$SRC/systemd/nr-anti-idle.timer"   /etc/systemd/system/
install -m 0644 "$SRC/systemd/nr-backup.service"    /etc/systemd/system/
install -m 0644 "$SRC/systemd/nr-backup.timer"      /etc/systemd/system/
systemctl daemon-reload

echo "→ enabling + starting timers"
systemctl enable --now nr-anti-idle.timer nr-backup.timer

echo ""
echo "→ running BOTH jobs once now (closes the gap from the dead cron)"
systemctl start nr-anti-idle.service || echo "  ⚠️ anti-idle reported a failure — see /var/log/nr-anti-idle.log"
systemctl start nr-backup.service    || echo "  ⚠️ backup reported a failure"

echo ""
echo "════════ verification ════════"
systemctl list-timers 'nr-*' --no-pager
echo ""
echo "── anti-idle log (tail) ──"
tail -12 /var/log/nr-anti-idle.log 2>/dev/null || echo "  (empty)"
echo ""
echo "── backups ──"
ls -lh "$RUN_HOME/backups/niveshrakshak/" 2>/dev/null | tail -4 || echo "  (none)"
echo ""
echo "── registry freshness ──"
curl -sS -m 20 http://127.0.0.1:8300/api/health 2>/dev/null \
  | python3 -c "import json,sys; d=json.load(sys.stdin); r=d['registry']; print(f\"  rows={r['mirror_rows']} as_of={r['as_of']} stale={r['stale']}\")" \
  || echo "  (api unreachable)"
echo ""
echo "✅ timers installed. Verify later with:  systemctl list-timers 'nr-*'"
