# NiveshRakshak Android — Master Implementation Plan

**Date:** 2026-10-02 · **Status:** 🟢 **GO — SEBI reachable from Oracle VPS**
**Target:** Fully functional sideloaded Android APK for 30–40 testers. No Play Store.
**Stack:** Capacitor 8.5.2 wrapping the existing vanilla-JS `web/` + existing Python FastAPI backend on the Oracle VPS.

---

## ✅ PROGRESS (updated 2026-10-02)

| Phase | Status | Evidence |
|---|---|---|
| **0** Verify + prep | ✅ **DONE** | 54 GB freed (89 GB free) · cmdline-tools + `platforms;android-36` installed · release keystore created (valid → 2056) |
| **1** Backend on VPS | ✅ **DONE + LIVE** | container `Up (healthy)` · `sebi_check: ok, fails 0` · **23,513 registry rows** · anti-idle + backup crons installed · Cloudflare tunnel active |
| **2** Capacitor shell + APK | ✅ **DONE** | `BUILD SUCCESSFUL` · **7 plugins** · signed APKs 29M / 23M / 72M |
| **3** Share IN | ✅ **CODE DONE** | manifest filters verified in the built APK via `aapt2 dump xmltree`; `native.js` wired; clipboard fallback added. ⏳ **needs a device to test** |
| **4** On-device ML Kit OCR/QR | ⏸️ **DEFERRED** | plugins installed + bundled, JS not wired. Server-side tesseract already works and is verified — see the deferral note in §6 |
| **5** Share OUT | ✅ **CODE DONE** | verified recipe implemented in `native.js`. ⏳ **needs a device to test** |
| **6** Distribution | ⏳ **BLOCKED** | needs the APK on a phone first |

**End-to-end proof (production, through the public tunnel):**
```
POST /api/check  "SEBI registered advisor Rakesh Capital Securities (INZ000031633)
                  Guaranteed 30% monthly return! Pay 50000 to scam123@ybl, act fast"
→ headline : red_flag ['personal_handle']
→ registry : exact (3 matches, 23513 rows)
→ redflags : guaranteed_returns, urgency, tips_group, sebi_claim
```
This is the `DEMO.md` IIFL-pattern case passing in production: a **real** company name and
a **real** registration number, with a fraudulent payment destination → RED FLAG. The
registry said "exact match" and the failed primary still dominated. Verdict precedence works.

**🔴 Two things only the user can do:**
1. **Plug in an Android phone** with USB debugging — `adb devices` is currently empty, so
   nothing in Phases 3/5 has been device-tested.
2. **Back up `../niveshrakshak-app/keystore/` off this machine.** Lose it and the 40 testers
   can never be updated in place.

---

Everything below is verified against the local system, the npm registry, or primary web
sources (cited). ⚠️ = unverified, needs a device test.

---

## 0. The decisive risk is now RESOLVED 🟢

The single biggest project risk was: *does siportal.sebi.gov.in's WAF block datacenter IPs?*
There was zero public evidence either way.

**Answer from your own Oracle VPS (2026-10-01): NO. It returned HTTP 200 + the genuine
SEBI Check landing page** (verified by the page content: "CHECK VERIFIED UPI ID",
"USING PHOTO" / "TYPE" / "FOR SAFER NEFT/RTGS TRANSFERS", 12-language modal).

Your curl command was mangled by the paste (the `\ ` line-continuations collapsed and
`# expect: 200` glued onto the URL), which is why you saw `Malformed input to a URL
function` twice — but curl's `-o /dev/null` only applies to the *first* URL, so the real
URL's body printed to stdout. **The `200` after the HTML is the real result.**

⚠️ **But this is necessary, not sufficient.** The landing page is a plain GET. The actual
product depends on a **POST to `validate.html` with a `CA_SESSIONID` cookie**. Run §1
before anything else.

---

## 1. STEP ZERO — the real SEBI verification (run on the Oracle VPS, ~2 min)

Paste these **one at a time** (don't multi-line paste — that's what broke last time).

**Test 1 — landing page + does it set the session cookie?**
```bash
curl -sS -c /tmp/sebi.jar -o /tmp/sebi.html -w 'HTTP %{http_code}\n' -A 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36' 'https://siportal.sebi.gov.in/intermediary/sebi-check'
```
```bash
grep -c CA_SESSIONID /tmp/sebi.jar
```
✅ Want: `HTTP 200` and a count of `1` or more.

**Test 2 — 🔴 THE ACTUAL API (this is the real go/no-go).** Uses a deliberately invalid
handle, so a *correct* answer is SEBI saying "not valid" **with a transaction ID**:
```bash
curl -sS -b /tmp/sebi.jar -w '\nHTTP %{http_code}\n' -A 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36' -H 'X-Requested-Via: SI Portal' -H 'X-Requested-With: XMLHttpRequest' -H 'Referer: https://siportal.sebi.gov.in/intermediary/sebi-check' -H 'Origin: https://siportal.sebi.gov.in' -F 'ctype=upi-check' -F 'upi=test123@ybl' -F 'captcha=' 'https://siportal.sebi.gov.in/intermediary/sebi-check/validate.html'
```
✅ **FULL GO** if you get JSON like:
`{"status":"error","message":"UPI Id is not valid!",...,"transactionId":"TXN-XXXXXXXX-XXXX"}`
→ a real `TXN-` id means the WAF accepted the POST and SEBI actually processed it.

🔴 **STOP if you get:** `505` (WAF block) · `429` (rate limited) · `432` (captcha missing
— acceptable, means it works but is gated) · HTML instead of JSON · connection refused.

**Test 3 — the registry endpoint (www.sebi.gov.in, plain Apache, lower risk):**
```bash
curl -sS -o /dev/null -w 'HTTP %{http_code}\n' -X POST -H 'Content-type: application/x-www-form-urlencoded' -H 'Referer: https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognised=yes' --data 'intmId=&search=zerodha&regNo=' 'https://www.sebi.gov.in/sebiweb/ajax/other/getrecognisedintm.jsp'
```
✅ Want `HTTP 200`.

**Test 4 — the .xls export (registry refresh depends on it):**
```bash
curl -sS -o /tmp/t.xls -w 'HTTP %{http_code} size=%{size_download}\n' -X POST -A 'Mozilla/5.0 (X11; Linux x86_64) Chrome/126.0' -H 'Referer: https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRecognised=yes' 'https://www.sebi.gov.in/sebiweb/other/IntmExportAction.do?intmId=30'
```
✅ Want `HTTP 200` and a size around 1.9 MB.

**If Test 2 fails but 1/3/4 pass** → fallback chain: (a) Cloudflare Tunnel (free) from a
home machine so SEBI sees a residential IP, (b) move to DigitalOcean Bangalore / Vultr
Mumbai (Indian DC IP), (c) on-device Route C from `ONDEVICE-ARCHITECTURE.md` (user's own
mobile IP — most residential-like of all).

---

## 2. System audit — you already have almost everything ✅

**Machine:** EndeavourOS (Arch-based, so **`pacman` not `apt`**) · x86_64 · **23 GB RAM** ·
**16 cores** · **35 GB free of 217 GB (84% used)**

| Component | Status | Notes |
|---|---|---|
| Node v26.10.0 | ✅ | Capacitor 8 needs ≥22 |
| npm 12.2.0 | ✅ | |
| **JDK 21** (`/usr/lib/jvm/java-21-openjdk`, 21.0.12.1) | ✅ **ALREADY INSTALLED** | 🎉 **This kills the Gradle blocker** — see §3 |
| JDK 17 | ✅ | also present |
| JDK 27 (system default) | ⚠️ | **too new for Gradle 8.14** — must NOT be used for the build |
| Android SDK (1.7 GB) | ✅ | `~/Android/Sdk` |
| platform-tools / **adb 1.0.41** | ✅ | |
| platforms/**android-36.1** | ⚠️ | API **36.1**, not `android-36` — may need the base 36 platform (§3) |
| build-tools 36.0.0 / 36.1.0 / 37.0.0 | ✅ | includes `zipalign` + `apksigner` |
| emulator binary | ✅ | but **no system-images** — keep it that way (§3) |
| SDK licenses | ✅ | already accepted |
| **cmdline-tools / `sdkmanager`** | 🔴 **MISSING** | needed to install anything else into the SDK |
| Android Studio | ❌ not installed | ✅ **and you don't need it** — saves ~10 GB |
| Flutter | ❌ | ✅ correct, per `FLUTTER-VS-CAPACITOR.md` |
| git | ✅ | clean at `c0a9c4d` |
| Docker (local) | ❌ | not needed locally — Docker runs on the VPS |

### 🔴 The Gradle/Java blocker is already solved

Official [Gradle compatibility matrix](https://docs.gradle.org/current/userguide/compatibility.html):
**Java 24 is the maximum for running Gradle 8.14** (Capacitor 8 = AGP 8.13 + Gradle 8.14).
Your default `java` is **27** → `./gradlew` from the CLI **would fail**.

But you have **JDK 21 installed**. Fix = one line in `android/gradle.properties`:
```
org.gradle.java.home=/usr/lib/jvm/java-21-openjdk
```
No Android Studio needed. No new JDK needed. **Zero extra disk.**

---

## 3. Storage: free ~52 GB BEFORE installing anything

You have 35 GB free and were worried about exhausting it. Good news — your caches are
holding **~58 GB of pure garbage**:

| Path | Size | Safe to delete? |
|---|---|---|
| `~/.cache/yay` | **44 GB** | ✅ **YES** — AUR build caches/source tarballs. Rebuilds on demand. |
| `~/.cache/pip` | **8.2 GB** | ✅ **YES** — `pip cache purge` |
| `~/.npm` | **5.0 GB** | ✅ **YES** — `npm cache clean --force` |
| `~/.cache/paru` | 737 MB | ✅ YES (second AUR helper) |
| `~/.cache/pypoetry` | 487 MB | ✅ YES |
| `~/.gradle` | 2.1 GB | ⚠️ **KEEP** — needed for Android builds (will grow to ~3–4 GB) |
| `~/.cache/huggingface` | 4.0 GB | ⚠️ your call — only if you don't need those models |

**Commands (frees ~52 GB, taking you from 35 GB → ~87 GB free):**
```bash
rm -rf ~/.cache/yay/* ~/.cache/paru/*
pip cache purge
npm cache clean --force
```

### What the Android build will actually cost you

| Item | Size |
|---|---|
| `cmdline-tools` (for `sdkmanager`) | ~150 MB |
| `platforms;android-36` (only if AGP rejects 36.1) | ~60 MB |
| Project `node_modules` (Capacitor + 6 plugins) | ~150 MB |
| Gradle build outputs + wrapper | ~500 MB – 1 GB |
| Release APK | ~20 MB |
| **Total new** | **~1.5 GB max** |

### 🔴 What NOT to install (this is where people lose 25 GB)

| Skip | Saves | Why |
|---|---|---|
| **Android Studio** | ~10 GB | CLI build with JDK 21 works. You already have the SDK. |
| **Emulator system-images** | ~10–15 GB | **Use a physical Android phone over USB.** Faster, real-world accurate (WebView version, real WhatsApp/Telegram share sheets — an emulator can't test those anyway). |
| Extra build-tools / platforms | ~2 GB each | You already have 36.0.0 / 36.1.0 / 37.0.0 and android-36.1. |
| Flutter | ~5 GB | Rejected — see `FLUTTER-VS-CAPACITOR.md` |

**Net: you free 52 GB and spend ~1.5 GB.** Storage is a non-issue after cleanup.

---

## 4. Install list (EndeavourOS/Arch — minimal, ~1.5 GB total)

### 4.1 System packages
```bash
# Only if `unzip`/`wget` are missing (needed for cmdline-tools):
sudo pacman -S --needed unzip wget
```
That's likely the **only** pacman install. Everything else is already present.

### 4.2 Android SDK cmdline-tools (gives you `sdkmanager`) — ~150 MB
```bash
cd ~/Android/Sdk
wget -q https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip -O /tmp/cmdtools.zip
unzip -q /tmp/cmdtools.zip -d /tmp/cmdtools
mkdir -p cmdline-tools && mv /tmp/cmdtools/cmdline-tools cmdline-tools/latest
rm /tmp/cmdtools.zip
export ANDROID_HOME=~/Android/Sdk
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"
sdkmanager --list_installed   # verify it works
```
⚠️ The URL above carries a specific build number — if it 404s, get the current one from
https://developer.android.com/studio#command-line-tools-only (bottom of page).

Add to `~/.bashrc` (or `~/.zshrc`) permanently:
```bash
export ANDROID_HOME="$HOME/Android/Sdk"
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"
```

### 4.3 Only if the build complains about `compileSdk 36` — ~60 MB
```bash
sdkmanager "platforms;android-36"
```
You have `android-36.1` (API 36.1 / Android 16 QPR, `IsBaseSdk=true`). AGP *may* accept it
for `compileSdk 36`; ⚠️ **unverified**. Install the base 36 platform only if Gradle errors
with `Failed to find target with hash string 'android-36'`.

### 4.4 Project npm packages (all versions verified against the npm registry 2026-10-02)

| Package | Version | License | Purpose |
|---|---|---|---|
| `@capacitor/cli` | **8.5.2** | MIT | build tooling |
| `@capacitor/core` | **8.5.2** | MIT | runtime bridge |
| `@capacitor/android` | **8.5.2** | MIT | native project |
| `@capacitor/share` | **8.0.2** | MIT | share card **OUT** (image files ✅) |
| `@capacitor/filesystem` | **8.1.3** | MIT | write the PNG to Cache dir |
| `@capacitor/camera` | **8.2.4** | MIT | camera capture |
| `@capgo/capacitor-share-target` | **8.0.54** | **MPL-2.0 (free)** | share **IN** — peerDep `@capacitor/core >=8.0.0` ✅, last published **2026-09-22** (actively maintained) |
| `@capacitor-mlkit/text-recognition` | **8.2.1** | **Apache-2.0 (free)** | on-device OCR incl. **Devanagari**, offline |
| `@capacitor-mlkit/barcode-scanning` | **8.2.1** | Apache-2.0 | QR from **static image** + live camera |
| `html2canvas-pro` | **2.5.0** | MIT | replaces the **dead** `html2canvas` 1.4.1 |

🔴 **Do NOT use** `@capacitor-community/barcode-scanner` — **ARCHIVED Oct 2024**.
🔴 **Do NOT use** `send-intent` — stale (7.0.0, Feb 2025), no v8 release.
💰 `@capawesome-team/capacitor-share-target` is the **paid** alternative — not needed.

---

## 5. Final architecture

```
┌──────────────── ANDROID (Capacitor 8 WebView + existing web/ assets) ────────────────┐
│                                                                                      │
│  INGEST (3 paths — all three are needed)                                             │
│   1. Share target: WhatsApp text+image · Telegram IMAGE · Chrome URL · Gallery       │
│   2. 🔴 Clipboard "Paste" button  ← the ONLY way for Telegram TEXT messages          │
│   3. Manual textarea (already built)                                                 │
│   + ACTION_PROCESS_TEXT (Chrome/SMS only — NOT inside WhatsApp/Telegram)             │
│                                                                                      │
│  ON-DEVICE (nothing leaves the phone)                                                │
│   · ML Kit OCR (Latin + Devanagari, in-memory Bitmap)                                │
│   · ML Kit barcode → QR payload (upi://pay?pa=…)                                     │
│                                                                                      │
│  OUT: canvas → PNG → Filesystem(Cache, ".png") → Share.share({files:[uri]})          │
│       → WhatsApp / Telegram / Instagram / Drive / email                              │
└───────────────────────────────────────┬──────────────────────────────────────────────┘
                                        │ HTTPS (only the extracted identifiers +
                                        │ image bytes in Phase 1; identifier-only
                                        │ once Phase 3 lands)
                                        ▼
┌──────────────── ORACLE VPS (existing, co-located with Hermes) ───────────────────────┐
│  Docker container: FastAPI + tesseract + zbar + 5.6 MB registry SQLite               │
│   · shared SEBI Check session (CA_SESSIONID, WAF-505 retry, circuit breaker)         │
│   · 6h result cache → 100 testers checking one viral handle = 1 SEBI hit             │
│   · captcha pass-through · registry mirror + rapidfuzz near-miss                     │
│   · nightly refresh cron (doubles as ANTI-IDLE)  · nightly off-box SQLite backup     │
│   · Caddy/nginx for TLS  ·  CPU+MEM limits so OCR bursts can't starve Hermes         │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Phase plan

### PHASE 0 — Verify + prep (Day 1, ~1 h)
- [ ] Run §1 Tests 1–4 on the VPS. **Record the results.** Test 2 must return a `TXN-` id.
- [ ] Free 52 GB (§3 cleanup commands).
- [ ] Install cmdline-tools (§4.2), add `ANDROID_HOME`/`PATH` to shell rc.
- [ ] Plug in a physical Android phone, enable USB debugging, confirm `adb devices` lists it.
- [ ] **Create the release keystore NOW and back it up off-machine.** 🔴 Android only
      updates an app signed with the *same* key — lose it and your 40 testers must
      uninstall + reinstall (losing local data). `keytool` ships with the JDK.
- [ ] Snapshot/backup the VPS before touching Hermes' neighbourhood.

### PHASE 1 — Backend on the VPS (Day 1, ~3 h)
- [ ] `Dockerfile` (python:3.11-slim + `tesseract-ocr` + `zbar-tools`; tessdata already in repo).
- [ ] `docker-compose.yml` with **CPU + memory limits** so OCR bursts can't starve Hermes.
      Mount a named volume for `data/nr.sqlite`.
- [ ] 🔴 uvicorn must run with **`--proxy-headers --forwarded-allow-ips='*'`** — otherwise
      `request.client.host` is the proxy IP and your per-IP rate limiter (30/10 min)
      becomes a **global** bucket that locks out all 40 testers.
- [ ] Add **CORS** for origin `https://localhost` (Capacitor's default Android WebView origin).
- [ ] TLS: Caddy (auto-HTTPS) or nginx + Let's Encrypt. Point a subdomain at the VPS.
- [ ] 🔴 **Anti-idle cron** — Oracle permanently deletes Always Free instances idle for
      7 days (95th-pctile CPU <10% AND network <10% AND memory <10%). Nightly
      `tools/refresh_registry.py` + a small tesseract self-test keeps you above it.
- [ ] 🔴 **Nightly off-box backup** of the 6 MB SQLite (reclamation is unrecoverable).
- [ ] 🔴 **Never terminate or resize the instance.** Oracle halved Always Free ARM to
      2 OCPU/12 GB on **2026-06-15**; a terminated instance *"may not be possible to
      recreate above the updated limit."*
- [ ] Smoke-test `/api/health` and a real `/api/check` from your laptop over HTTPS.

### PHASE 2 — Capacitor shell + first APK (Day 2, ~3 h)
- [ ] `npm i` the §4.4 packages; `npx cap init NiveshRakshak app.niveshrakshak --web-dir=web`
- [ ] `capacitor.config.ts`: `androidScheme: "https"`, SplashScreen `#F7F3EC`.
- [ ] `npx cap add android` → set `org.gradle.java.home=/usr/lib/jvm/java-21-openjdk`
      in `android/gradle.properties`.
- [ ] 🔴 **Swap `web/vendor/html2canvas.min.js` (dead 1.4.1, 1054 open issues, crashes on
      `oklch()`/`color()`) → `html2canvas-pro` 2.5.0** (published 2026-09-30).
- [ ] Add `API_BASE` to `web/app.js` (3 call sites: `/api/check`, `/api/captcha`, `/api/health`).
- [ ] **No-build-step plugin access** — pick one:
      (a) change `<script src="app.js">` → `<script type="module" src="app.js">` and use
      native ESM imports, vendoring plugin `dist/esm` into `web/vendor/`; **or**
      (b) simplest — call `Capacitor.Plugins.Share.share(...)` directly. Capacitor
      auto-injects `window.Capacitor` and registers native plugins, no import needed.
- [ ] `npx @capacitor/assets generate` (icon.svg → adaptive icons + splash).
- [ ] `cd android && ./gradlew assembleRelease` → signed APK → `adb install -r`.
- [ ] Verify on the phone: text check, EN/HI toggle, screenshot upload, captcha flow,
      verdict card renders, **airplane mode shows an honest error not a blank screen**.

### PHASE 3 — Share IN (Day 3–4, ~1 day) ← the riskiest phase
- [ ] Install `@capgo/capacitor-share-target` 8.0.54; wire `shareReceived` listener.
- [ ] AndroidManifest on `MainActivity`: **three** intent-filters (`SEND`+`text/plain`,
      `SEND`+`image/*`, `SEND_MULTIPLE`+`image/*`) each with `category.DEFAULT`, plus
      `PROCESS_TEXT`+`text/plain`.
      🔴 **`android:exported="true"` is MANDATORY** (API 31+). The official intents-filters
      guide shows `exported="false"` — **that example is misleading**; the system share
      sheet launches your activity cross-UID.
      `android:launchMode="singleTask"`. Activity-level `android:label` = **"Check with
      NiveshRakshak"** (that's what shows in the sheet). Note: since API 29 the sheet uses
      only the `<application>` icon — activity/intent-filter icons are ignored.
- [ ] 🔴 **Cold start:** the native intent lands **before the WebView/JS bridge is ready**.
      The capgo plugin queues and replays it — **this is exactly why you use the plugin
      instead of hand-rolling Kotlin.**
- [ ] 🔴 **App already running:** intent arrives in `onNewIntent()`; you **must call
      `setIntent(intent)`** or later `getIntent()` returns **stale** data.
- [ ] 🔴 **`content://` URIs:** `takePersistableUriPermission()` **will not work** — it
      requires the *sender* to set `FLAG_GRANT_PERSISTABLE_URI_PERMISSION`, which
      WhatsApp/Telegram/Photos essentially never do. **Correct pattern:
      `ContentResolver.openInputStream(uri)` → copy bytes into your own cache
      IMMEDIATELY.** The grant is task-scoped and does not survive process death.
      No storage permission needed (sender grants temporary read).
- [ ] 🔴 **WhatsApp drops `EXTRA_TEXT` when an image is present** → handle `EXTRA_STREAM`
      and `EXTRA_TEXT` **independently**.
- [ ] Do binary reads **off the main thread**.
- [ ] 🔴 **Clipboard fallback for Telegram text** — Telegram offers **no** external share
      for text messages (Forward is internal-only; open feature requests on
      bugs.telegram.org since years). Add a prominent **"Paste from clipboard"** button
      that checks the clipboard on app resume. *This is exactly why RakshaLink uses
      Paste&Check.* Telegram **images** DO share normally.
- [ ] **Device-test matrix** (see §7).

### PHASE 4 — On-device OCR + QR (Day 5, ~1 day)
- [ ] `@capacitor-mlkit/text-recognition` — `processImage({path, script})`, Devanagari
      bundled → **fully offline, no Play services**.
      ⚠️ Unverified whether one Devanagari pass also picks up embedded English —
      **test**; worst case run two passes (Latin + Devanagari) and merge.
- [ ] `@capacitor-mlkit/barcode-scanning` — `readBarcodesFromImage({path})` for QRs
      **inside screenshots** (the docs literally cite that use case) + `startScan()` for
      live camera. One plugin covers both.
- [ ] Compare ML Kit Devanagari output against your existing Tesseract baseline on real
      WhatsApp/Telegram screenshots. ⚠️ **No public Devanagari benchmark exists** — this
      is the one genuine unknown. Keep server-side Tesseract as a fallback if ML Kit
      underperforms.

### PHASE 5 — Share OUT (Day 5–6, ~half day)
🔴 **The exact recipe (source-verified in `SharePlugin.java`):**
1. canvas → blob → base64, **strip the `data:image/png;base64,` prefix**
   (`@capacitor/filesystem` 8.1.3: with no `encoding` param the data must be **pure
   base64**; non-base64 **throws**).
2. `Filesystem.writeFile({ path: 'niveshrakshak-verdict.png', data: b64, directory: Directory.Cache, recursive: true })` → returns `{ uri }` (a `file://` URI).
3. `Share.share({ files: [uri], text: shareText(), dialogTitle: 'Share' })`

**Three non-negotiables:**
| Rule | Why |
|---|---|
| 🔴 Filename **must end `.png`** | Plugin derives MIME from the extension via `MimeTypeMap`. No extension → `*/*` → **WhatsApp treats it as a document or rejects it.** |
| 🔴 **`Directory.Cache` is the only shareable-by-default dir** | Capacitor's template `file_paths.xml` declares only `<cache-path>` + `<external-path>`. Any other dir → **`getUriForFile` THROWS** unless you edit `android/app/src/main/res/xml/file_paths.xml`. |
| 🔴 Pass the **`file://` URI** | Plugin rejects anything else ("only file urls are supported"). It handles FileProvider `content://` conversion, `FLAG_GRANT_READ_URI_PERMISSION`, `ClipData` (Q+) and `createChooser` internally. |

**All historical WhatsApp failure modes are already fixed:** null MIME (issue #196 →
PR #816, 2021) · `android.resource://` (copy to a real file) · missing grant/ClipData
(plugin does it) · **Nov 2025 WhatsApp regression that silently dropped captions on image
shares → fixed by WhatsApp ~Jan 2026**. **No known open bug blocks image delivery on
`@capacitor/share` 8.0.2 in 2026.**

**Text + image together:** Telegram honours both, always has. WhatsApp fixed Jan 2026 but
**treat captions as best-effort → render critical text INTO the image** (your verdict card
already does this — that design decision just got validated). Instagram ignores `EXTRA_TEXT`.

**Limits:** no share-sheet size limit (the intent carries a URI, not bytes). WhatsApp:
2 GB documents / 100 media items per send. Images get **recompressed** (PNG → lossy,
transparency flattened); pixel-perfect needs the recipient to choose "Document" — you
can't force that from the intent. A <2 MB card is cosmetically fine.

### PHASE 6 — Distribution to 30–40 testers (Day 6–7)
🟢 **India is NOT in Google's Sept-30-2026 sideloading wave** (wave 1 = Brazil, Indonesia,
Singapore, Thailand only; global = "2027 and beyond", **no confirmed India date**). So plain
APK sideloading works today with **no developer certificate, no ID, no waiting period**.
ADB installs are permanently unaffected.

**Recommended: Firebase App Distribution** (free, email invites + **update notifications**).
Testers enable "install unknown apps" once.
Alternatives: Diawi / InstallOnAir (free tiers, ⚠️ links expire) · direct APK on your own
server · Telegram/Drive (⚠️ **test one `.apk` via WhatsApp first** — its handling changes
over time; Telegram/Drive are safer for file integrity).

🔴 **Ship a signed APK, not an AAB** — an `.aab` **cannot be installed directly on a
device**; it's a publishing format that Play splits. Use `gradlew assembleRelease`.

**Optional upgrade (not required):** Play **Internal Testing** — $25 one-time + ID
verification, up to **100 testers**, **NO Google review** (builds live in minutes),
**EXEMPT from the 12-tester/14-day rule** (that's production-only), never publicly listed,
no financial declaration / data-safety form needed. Testers install via the normal Play
Store → **no unknown-sources, auto-updates**. Smoothest for non-technical/senior testers.
App code is identical — you can switch later without rebuilding.

### PHASE 7 — Later (post-tester-feedback)
- [ ] Bundle `registry.db` on-device → registry lookup + near-miss go local (Phase 2 of
      `ONDEVICE-ARCHITECTURE.md`). Server then only does SEBI Check.
- [ ] Port `extract.py` / `redflags.py` / `verdict.py` to Kotlin → only the identifier
      leaves the phone. 🔴 Watch the 3 Devanagari regex gotchas in
      `ONDEVICE-ARCHITECTURE.md` §2 (`\p{InDevanagari}` not `\p{IsDevanagari}`;
      `CANON_EQ` unsupported → manual NFC normalize; `\d` is ASCII-only).
- [ ] Notification-listener as an **opt-in** Telegram-text workaround (`BIND_NOTIFICATION_LISTENER_SERVICE`
      is **not** in Play's declaration list → no form/approval; needs prominent disclosure
      + affirmative consent). 🔴 **Never use AccessibilityService** — likely rejection, and
      the "must use more narrowly scoped APIs" clause kills it.
- [ ] Per-user SEBI session pool before any viral moment (LIMITATIONS.md §4).
- [ ] Contract canary cron asserting the SEBI response shape (LIMITATIONS.md §2).

---

## 7. Device-test matrix (run every one on a real phone)

| # | Test | Expect |
|---|---|---|
| 1 | Paste a scam message manually | Red verdict card |
| 2 | WhatsApp → long-press message → Forward → share icon → NiveshRakshak | Text arrives, verdict renders |
| 3 | WhatsApp → share a **screenshot image** | Image arrives, OCR runs |
| 4 | **Telegram → share a PHOTO** | ✅ works |
| 5 | **Telegram → try to share a TEXT message** | 🔴 **won't appear** — confirm the clipboard button covers it |
| 6 | Chrome → share a URL | Text arrives |
| 7 | Gallery → share an image with a QR | QR decoded → `upi://pay?pa=…` extracted |
| 8 | **Cold start**: app NOT running, share into it | 🔴 payload must survive the bridge-not-ready race |
| 9 | **Warm start**: app already open, share into it | 🔴 must not show the *previous* share's data (`setIntent`) |
| 10 | Share an image, background the app mid-flow, return | Bytes were copied to cache → still works |
| 11 | Verdict card → Share → **WhatsApp** (individual + group) | Image arrives as an **image**, not a document |
| 12 | Verdict card → Share → **Telegram** | Image **+ caption** both arrive |
| 13 | Verdict card → Share → Drive / Gmail | Works |
| 14 | SEBI captcha triggers (do ~6 rapid checks) | Captcha image renders → solve → verdict |
| 15 | **Airplane mode** | Honest "couldn't verify", **not a blank screen** |
| 16 | EN ↔ हिं toggle mid-result | Card re-renders in the other language |
| 17 | Rate limit (31 checks in 10 min) | 429 toast, not a crash |
| 18 | Low-end / old Android device | OCR + fonts + card export all work |

---

## 8. Risk register (updated)

| # | Risk | Sev | Status / mitigation |
|---|---|---|---|
| 1 | SEBI blocks datacenter IPs | ~~🔴~~ | 🟢 **RESOLVED** — VPS returned 200 + genuine page. Confirm with §1 Test 2 (POST + `TXN-` id) |
| 2 | Per-IP rate limiter collapses behind a proxy | 🔴 | `--proxy-headers --forwarded-allow-ips='*'` (Phase 1) |
| 3 | **Oracle idle reclamation = permanent deletion** | 🔴 | Anti-idle cron + nightly off-box backup + **never terminate/resize** |
| 4 | **Java 27 breaks Gradle 8.14** | ~~🔴~~ | 🟢 **RESOLVED** — JDK 21 already installed; set `org.gradle.java.home` |
| 5 | **Telegram text can't be shared out** | 🟠 | Platform limitation, not fixable. **Clipboard-paste fallback** (Phase 3) |
| 6 | Share-target cold-start race in Capacitor | 🟠 | Use `@capgo/capacitor-share-target` (queues + replays); don't hand-roll |
| 7 | WhatsApp image share fails | ~~🟠~~ | 🟢 All known causes fixed; recipe in Phase 5. Still run tests 11–12 |
| 8 | `html2canvas` 1.4.1 dead / crashes on modern CSS | 🟠 | Swap to `html2canvas-pro` 2.5.0 (Phase 2) |
| 9 | ML Kit Devanagari accuracy unknown | 🟠 | ⚠️ No public benchmark. Test vs Tesseract baseline; keep server OCR as fallback |
| 10 | Lost release keystore | 🔴 | Create in Phase 0, **back up off-machine immediately** |
| 11 | `android-36.1` vs `compileSdk 36` mismatch | 🟡 | Install `platforms;android-36` only if Gradle errors |
| 12 | Shared SEBI session serializes users | 🟡 | Fine for 40 testers; per-user pool before scale |
| 13 | Storage exhaustion | ~~🟡~~ | 🟢 **RESOLVED** — 52 GB reclaimable; build needs ~1.5 GB |
| 14 | 2027 global sideloading verification reaches India | 🟡 | ⚠️ No India date. Re-check before relying on sideloading long-term; Play Internal Testing is the escape hatch |

---

## 9. Cost

| Item | Cost |
|---|---|
| Oracle Always Free VPS (already running) | **$0** |
| Domain + TLS (optional — a free DuckDNS/no-IP + Caddy works) | $0–10/yr |
| Firebase App Distribution | **$0** |
| All npm plugins | **$0** (MIT / MPL-2.0 / Apache-2.0) |
| Android Studio, emulator images | **$0 — not installing** |
| Play Internal Testing (optional upgrade) | $25 one-time |
| **Total** | **$0–25** |

---

## 10. Timeline

| Day | Deliverable |
|---|---|
| **1** | §1 SEBI tests pass · 52 GB freed · cmdline-tools · keystore · VPS deploy + TLS + anti-idle cron |
| **2** | Capacitor project · `html2canvas-pro` swap · JDK-21 gradle config · **first APK on a real phone** |
| **3–4** | Share IN (WhatsApp text+image, Telegram image, Chrome, Gallery) + clipboard fallback · tests 2–10 |
| **5** | ML Kit OCR (Devanagari) + QR from screenshot · compare vs Tesseract |
| **5–6** | Share OUT recipe · tests 11–13 (real WhatsApp + Telegram groups) |
| **6–7** | Firebase App Distribution · 30–40 testers invited · **ship** |

**~7 days to a fully functional app in 40 people's hands, for $0.**

---

## Sources
- Gradle Java compatibility: docs.gradle.org/current/userguide/compatibility.html (Java 24 max for 8.14)
- AGP JDK: developer.android.com/build/releases/agp-9-4-0-release-notes (JDK 17 min/default)
- Share target: developer.android.com/develop/ui/compose/sharing/receive (updated 2026-09-22) · developer.android.com/reference/android/content/Intent#ACTION_PROCESS_TEXT · developer.android.com/about/versions/12/behavior-changes-12#exported
- Telegram limits: bugs.telegram.org/c/999/11 · /c/999/13 · /c/4842 · /c/62277
- WhatsApp share-out: faq.whatsapp.com/887468535575482 (in-app forward only; external share is community-documented) · stackoverflow.com/questions/46578918
- Capacitor Share/Filesystem: npm registry (verified 2026-10-02) · forum.ionicframework.com/t/212601 · github.com/ionic-team/capacitor/issues/196 + PR #816 · developer.android.com/about/versions/nougat/android-7.0-changes
- html2canvas dead: github.com/niklasvh/html2canvas/issues/2700
- ML Kit: developers.google.com/ml-kit/vision/text-recognition/v2/android (2026-09-28) · /barcode-scanning/android (2026-09-24)
- Oracle free tier: docs.oracle.com/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm · infoq.com/news/2026/07/oracle-cloud-free-tier-limits · terminalbytes.com/oracle-cloud-free-tier-changes-2026
- SEBI WAF: nanobot.srik.me/blog/sebi-security-analysis (2026-06-05, disclosed to CERT-In/NCIIPC)
- Sideload verification: developer.android.com/developer-verification/guides · android-developers.googleblog.com/2026/03/android-developer-verification-rolling-out-to-all-developers.html
- Play internal testing: support.google.com/googleplay/android-developer/answer/9845334 · /answer/14151465
- App Center retired: learn.microsoft.com/en-us/appcenter/retirement (2025-03-31)
- Vanilla-JS Capacitor: ionic.io/blog/create-powerful-native-mobile-apps-with-capacitor-vanillajs · stackoverflow.com/questions/70932707
