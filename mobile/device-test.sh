#!/usr/bin/env bash
# One-command resume: installs the current RELEASE build on a plugged-in phone and
# runs every check that does not need a human.
#
#   ./device-test.sh              # install release + automated checks
#   ./device-test.sh --debug      # install the debug build instead (enables CDP)
#
# Safe to re-run: it always uninstalls first, so a half-applied previous install
# can never leave the phone in an unknown state.
set -uo pipefail

export ANDROID_HOME="${ANDROID_HOME:-$HOME/Android/Sdk}"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-21-openjdk}"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"

cd "$(dirname "$0")"
PKG=app.niveshrakshak
VARIANT="${1:-release}"

echo "════════════════════════════════════════════════════════════"
echo " NiveshRakshak device test — variant: $VARIANT"
echo "════════════════════════════════════════════════════════════"

# --- 1. wait for an authorized device ---------------------------------------
echo "→ waiting for the phone (accept the 'Allow USB debugging' prompt)…"
for i in $(seq 1 36); do
  ST=$(adb get-state 2>/dev/null || true)
  [ "$ST" = "device" ] && break
  printf "."; sleep 5
done
if [ "$(adb get-state 2>/dev/null)" != "device" ]; then
  echo ""; echo "🔴 no authorized device. Check: cable, USB debugging, and the"
  echo "   authorization dialog on the phone. Then re-run."; exit 1
fi
echo ""

# --- 2. device profile -------------------------------------------------------
MODEL=$(adb shell getprop ro.product.model | tr -d '\r')
REL=$(adb shell getprop ro.build.version.release | tr -d '\r')
SDK=$(adb shell getprop ro.build.version.sdk | tr -d '\r')
ABI=$(adb shell getprop ro.product.cpu.abi | tr -d '\r')
echo "→ device: $MODEL · Android $REL (SDK $SDK) · $ABI"

# --- 3. pick + verify the APK BEFORE installing ------------------------------
# 🔴 Lesson learned the hard way: a stale APK once masqueraded as a fresh build
# and "reintroduced" two already-fixed bugs. Always assert the contents.
case "$VARIANT" in
  debug)   DIR=debug;   SUFFIX=debug ;;
  release) DIR=release; SUFFIX=release ;;
  *) echo "🔴 unknown variant '$VARIANT' (use --debug or nothing)"; exit 1 ;;
esac
case "$ABI" in
  arm64-v8a)   APK="android/app/build/outputs/apk/$DIR/app-arm64-v8a-$SUFFIX.apk" ;;
  armeabi-v7a) APK="android/app/build/outputs/apk/$DIR/app-armeabi-v7a-$SUFFIX.apk" ;;
  *)           APK="android/app/build/outputs/apk/$DIR/app-universal-$SUFFIX.apk" ;;
esac
if [ ! -f "$APK" ]; then
  echo "🔴 $APK not found — build it first:  npm run sync && npm run build"
  exit 1
fi
echo "→ apk: $APK ($(du -h "$APK" | cut -f1), built $(date -r "$APK" +%H:%M:%S))"

echo "→ verifying the APK actually contains every fix…"
FAIL=0
assert_in() {  # assert_in <file-in-apk> <needle> <label>
  local n; n=$(unzip -p "$APK" "$1" 2>/dev/null | grep -cF "$2")
  if [ "$n" -ge 1 ]; then printf "   ✅ %s\n" "$3"; else printf "   🔴 %s MISSING\n" "$3"; FAIL=1; fi
}
assert_absent() {
  local n; n=$(unzip -p "$APK" "$1" 2>/dev/null | grep -cF "$2")
  if [ "$n" -eq 0 ]; then printf "   ✅ %s\n" "$3"; else printf "   🔴 %s STILL PRESENT\n" "$3"; FAIL=1; fi
}
assert_in     assets/public/styles.css        '[hidden] { display: none'      "broken-image fix ([hidden] override)"
assert_in     assets/public/app.js            'removeAttribute("src")'        "broken-image fix (removeAttribute)"
assert_in     assets/public/native.js         'style: "LIGHT"'                "status-bar fix (dark icons on cream)"
assert_absent assets/capacitor.config.json    'splashImmersive'               "status-bar fix (immersive flag removed)"
assert_in     assets/public/app.js            'renderLocalFailure'            "stale-verdict fix (offline honesty)"
assert_in     assets/public/app.js            'renderBuildInfo'               "footer-translation fix"
assert_in     assets/public/app.js            'async function shareCard'      "new share UX (card-first)"
assert_absent assets/public/app.js            'async function shareWeb'       "new share UX (old text-first removed)"
assert_in     assets/public/i18n.js           'share_text_btn'                "new share button labels"
assert_in     assets/public/vendor/html2canvas-pro.min.js 'html2canvas-pro'   "html2canvas-pro (dead 1.4.1 replaced)"
assert_in     assets/public/api-config.js     'NR_APP_VERSION'                "version stamp in footer"
[ "$FAIL" -eq 0 ] || { echo "🔴 APK is stale/incomplete — rebuild before installing."; exit 1; }

# --- 4. clean install --------------------------------------------------------
echo "→ uninstalling any previous build (avoids signature mismatch)…"
adb uninstall "$PKG" >/dev/null 2>&1 || true
echo "→ installing…"
adb install -r "$APK" 2>&1 | tail -1

# --- 5. launch + automated checks -------------------------------------------
adb logcat -c
adb shell am start -n "$PKG/.MainActivity" >/dev/null 2>&1
echo "→ launched, waiting for the WebView…"
sleep 12

echo ""
echo "── status bar (LIGHT_STATUS_BARS = DARK icons, which is what we want) ──"
adb shell dumpsys window 2>/dev/null | grep -m1 'mLastAppearance' | sed 's/^/   /'

echo "── edge-to-edge state ──"
adb shell dumpsys window windows 2>/dev/null \
  | grep -A14 "$PKG/$PKG.MainActivity" \
  | grep -oE 'EDGE_TO_EDGE_ENFORCED|FORCE_DRAW_STATUS_BAR_BACKGROUND' | sort -u | sed 's/^/   /'

echo "── crashes? ──"
CRASH=$(adb logcat -d 2>/dev/null | grep -iE 'FATAL EXCEPTION|AndroidRuntime.*Exception' | grep -ci "$PKG" || true)
echo "   fatal lines mentioning the app: ${CRASH:-0}"

echo "── memory ──"
adb shell "dumpsys meminfo $PKG 2>/dev/null | grep -E 'Native Heap|Dalvik Heap' | head -2" | sed 's/^/   /'

echo "── share-target intent filters registered with the OS? ──"
adb shell "dumpsys package $PKG 2>/dev/null" | grep -A2 -iE 'android.intent.action.SEND|PROCESS_TEXT' \
  | grep -oE 'android.intent.action.[A-Z_]+|text/plain|image/\*' | sort -u | sed 's/^/   /'

echo "── screenshot ──"
SHOT="/tmp/nrshots/resume-$(date +%H%M%S).png"
mkdir -p /tmp/nrshots
adb exec-out screencap -p > "$SHOT" 2>/dev/null && echo "   saved: $SHOT ($(du -h "$SHOT" | cut -f1))"

echo ""
echo "════════════════════════════════════════════════════════════"
echo " Automated checks done. These THREE still need a human:"
echo "   1. Share an IMAGE from real WhatsApp/Gallery into the app"
echo "      (adb cannot grant a content:// URI the way a real app does)"
echo "   2. Tap 'Share the card' → WhatsApp AND Telegram:"
echo "      confirm it arrives as an IMAGE with the caption"
echo "   3. Try sharing a Telegram TEXT message → it should NOT offer"
echo "      NiveshRakshak; the 'Paste from clipboard' button covers it"
echo "════════════════════════════════════════════════════════════"
if [ "$VARIANT" = "debug" ]; then
  echo ""
  echo " Debug build installed → CDP available:"
  echo "   adb forward tcp:9222 localabstract:webview_devtools_remote_\$(adb shell pidof $PKG)"
  echo "   node /tmp/nrtest/cdp-verify.js"
fi
