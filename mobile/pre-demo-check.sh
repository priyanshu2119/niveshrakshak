#!/usr/bin/env bash
# FINAL PRE-DEMO VERIFICATION
# The single most important check: does the URL baked into the INSTALLED APK
# still resolve to a live backend? A Cloudflare quick-tunnel hostname is
# regenerated on every tunnel restart, so three days of uptime is not guaranteed.
set -uo pipefail
export PATH="$HOME/Android/Sdk/platform-tools:$PATH"
cd /home/any/Desktop/try/niveshrakshak

APK=mobile/android/app/build/outputs/apk/release/app-arm64-v8a-release.apk
PKG=app.niveshrakshak
fail=0
ok()   { printf "  ✅ %s\n" "$1"; }
bad()  { printf "  🔴 %s\n" "$1"; fail=1; }
warn() { printf "  ⚠️  %s\n" "$1"; }

echo "═══════════════════════════════════════════════════════════════"
echo " 1. THE URL BAKED INTO THE APK  (this is what the phone will call)"
echo "═══════════════════════════════════════════════════════════════"
APK_URL=$(unzip -p "$APK" assets/public/api-config.js 2>/dev/null | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | head -1)
SRC_URL=$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' web/api-config.js | head -1)
echo "  in APK    : ${APK_URL:-<none found>}"
echo "  in source : ${SRC_URL:-<none found>}"
[ -n "$APK_URL" ] && ok "APK carries a tunnel URL" || bad "no URL in the APK"
[ "$APK_URL" = "$SRC_URL" ] && ok "APK matches source" || bad "APK is STALE vs source"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo " 2. IS THAT URL STILL ALIVE?"
echo "═══════════════════════════════════════════════════════════════"
if [ -n "$APK_URL" ]; then
  CODE=$(curl -sS -m 25 -o /tmp/nrhealth.json -w '%{http_code}' "$APK_URL/api/health" 2>/dev/null || echo "000")
  echo "  GET /api/health → HTTP $CODE"
  if [ "$CODE" = "200" ]; then
    ok "backend reachable at the URL the APK uses"
    python3 -c "
import json
d=json.load(open('/tmp/nrhealth.json'))
s=d['sebi_check']; r=d['registry']
print(f\"     sebi_check : {s['state']} (fails={s['fails']})\")
print(f\"     registry   : {r['mirror_rows']:,} rows · as_of {r['as_of']} · stale={r['stale']}\")
print(f\"     checks_run : {d['checks_run']}\")
"
  else
    bad "URL is DEAD (HTTP $CODE) — the tunnel hostname changed. Rebuild + reinstall required."
  fi
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo " 3. VPS: tunnel + timers + container"
echo "═══════════════════════════════════════════════════════════════"
ssh -o BatchMode=yes -o ConnectTimeout=15 hermes 'bash -s' <<'EOS' || bad "cannot reach the VPS"
printf "  container   : "; sudo -n docker ps --filter name=niveshrakshak --format "{{.Status}}" | head -1
printf "  tunnel svc  : "; systemctl is-active nr-tunnel
CUR=$(grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" /var/log/nr-tunnel.log 2>/dev/null | tail -1)
printf "  tunnel URL  : %s\n" "${CUR:-<none in log>}"
printf "  anti-idle   : "; systemctl is-active nr-anti-idle.timer
printf "  backup      : "; systemctl is-active nr-backup.timer
printf "  last anti-idle run : "; grep -c '^===' /var/log/nr-anti-idle.log 2>/dev/null
printf "  uptime      : "; uptime -p
printf "  disk free   : "; df -h / | awk 'NR==2{print $4}'
printf "  mem avail   : "; free -h | awk '/Mem:/{print $7}'
EOS

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo " 4. PHONE"
echo "═══════════════════════════════════════════════════════════════"
if [ "$(adb get-state 2>/dev/null)" = "device" ]; then
  ok "device authorized"
  printf "  model       : %s Android %s (SDK %s)\n" \
    "$(adb shell getprop ro.product.model | tr -d '\r')" \
    "$(adb shell getprop ro.build.version.release | tr -d '\r')" \
    "$(adb shell getprop ro.build.version.sdk | tr -d '\r')"
  if adb shell pm list packages 2>/dev/null | grep -q "$PKG"; then
    ok "app installed"
    printf "  versionName : %s\n" "$(adb shell dumpsys package $PKG 2>/dev/null | grep -m1 versionName | tr -d '\r ')"
    printf "  versionCode : %s\n" "$(adb shell dumpsys package $PKG 2>/dev/null | grep -m1 versionCode | tr -d '\r ' | cut -d' ' -f1)"
    printf "  network     : wifi=$(adb shell settings get global wifi_on | tr -d '\r')  mobile=$(adb shell settings get global mobile_data | tr -d '\r')\n"
  else
    bad "app NOT installed"
  fi
else
  bad "no authorized device — plug in the phone and accept the USB debugging prompt"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
[ "$fail" -eq 0 ] && echo " ✅ READY FOR DEMO" || echo " 🔴 FIX THE ABOVE BEFORE THE DEMO"
echo "═══════════════════════════════════════════════════════════════"
exit $fail
