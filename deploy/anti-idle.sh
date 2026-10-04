#!/usr/bin/env bash
# ANTI-IDLE — keeps this Oracle Always Free instance above the reclamation
# thresholds. Oracle permanently and unrecoverably deletes an Always Free
# instance whose 95th-percentile CPU, network AND memory all stay below 10%
# over a 7-day window. A 30-40-tester app can easily trip that in a quiet week,
# and it would take the neighbouring project down with it.
#
# Installed as a cron job (every 4 hours) by deploy/setup-cron.sh.
# Cheap on purpose: a few seconds of CPU + a couple of small HTTPS requests.
set -uo pipefail

LOG=/var/log/nr-anti-idle.log
exec >>"$LOG" 2>&1 || true
echo "=== $(date -Is) anti-idle run ==="

# 1) CPU: run tesseract on a generated image. This is the heaviest signal and
#    it doubles as a liveness test of the OCR path.
TMP="$(mktemp -d)"
if command -v python3 >/dev/null 2>&1; then
  python3 - "$TMP/warm.png" <<'PY' 2>/dev/null || true
import sys
try:
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (900, 300), "white")
    d = ImageDraw.Draw(im)
    for i in range(14):
        d.text((20, 12 + i * 20), f"NiveshRakshak warmup line {i} 1234567890 @valid", fill="black")
    im.save(sys.argv[1])
except Exception:
    pass
PY
fi
if [ -s "$TMP/warm.png" ] && command -v tesseract >/dev/null 2>&1; then
  tesseract "$TMP/warm.png" stdout --psm 6 >/dev/null 2>&1 || true
fi
rm -rf "$TMP"

# 2) Network: hit both upstreams the product depends on. GET only — siportal's
#    WAF answers HEAD with a non-standard "505 BLOCKED".
curl -sS -o /dev/null -m 25 -w 'siportal %{http_code} %{time_total}s\n' \
  -A 'Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36' \
  'https://siportal.sebi.gov.in/intermediary/sebi-check' || echo "siportal unreachable"

curl -sS -o /dev/null -m 25 -w 'sebiweb %{http_code} %{time_total}s\n' \
  -A 'Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36' \
  'https://www.sebi.gov.in/' || echo "sebiweb unreachable"

# 3) Local health, so the log doubles as a monitor.
curl -sS -o /dev/null -m 10 -w 'local-api %{http_code}\n' \
  'http://127.0.0.1:8300/api/health' || echo "local API down"

# 4) Daily registry refresh. refresh() self-skips when the mirror is <24h old,
#    so calling it every 4h is safe and gives us a same-day-fresh mirror.
if [ -f /app/tools/refresh_registry.py ] || true; then
  sudo -n docker exec niveshrakshak python -m tools.refresh_registry 2>&1 | tail -3 || true
fi

echo "=== done ==="
