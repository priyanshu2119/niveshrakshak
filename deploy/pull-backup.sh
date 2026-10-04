#!/usr/bin/env bash
# Pull the latest VPS-side DB backup to THIS machine.
#
# Run this (or cron it) so a copy exists off-box. Oracle's idle reclamation
# deletes the instance permanently — an on-box backup dies with it.
#
#   ./deploy/pull-backup.sh
set -euo pipefail

HOST="${NR_VPS_HOST:-hermes}"          # ssh alias from ~/.ssh/config
# 🔴 Use ~, not ${HOME}. rsync hands the remote path to the remote shell, which
# expands ~ but leaves a single-quoted ${HOME} as a LITERAL directory name —
# that produced "/home/ubuntu/${HOME}/backups/…" and a change_dir failure.
REMOTE_DIR='~/backups/niveshrakshak'
LOCAL_DIR="${NR_LOCAL_BACKUP:-$HOME/backups/niveshrakshak-vps}"
mkdir -p "$LOCAL_DIR"

echo "→ pulling from $HOST:$REMOTE_DIR"
rsync -az --progress "$HOST:$REMOTE_DIR/" "$LOCAL_DIR/"

echo "→ local copies:"
ls -1ht "$LOCAL_DIR" | head -5
echo "✅ off-box backup up to date: $LOCAL_DIR"
