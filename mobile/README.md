# NiveshRakshak — Android app

Capacitor 8 shell around the **existing** vanilla-JS frontend. Separate folder on
purpose: the original repo stays a clean Python/web project, and nothing Android
touches it except reading `web/`.

```
niveshrakshak/mobile/       ← you are here (Android shell only)
├── capacitor.config.json   webDir → ../web
├── package.json
├── keystore/               🔴 GITIGNORED — the app's identity, back it up
└── android/                generated native project
    └── app/src/main/assets/public/   ← copied from ../web at sync time

../                          ← repo root: backend + the ONE copy of the frontend
├── server/  web/  tools/  tests/  docs/
├── Dockerfile  docker-compose.yml
└── deploy/
```

## Why `webDir` points outside this folder

**Single source of truth.** `cap sync` copies `../web` into
`android/app/src/main/assets/public` at build time, so there is exactly one
frontend. Any improvement you make to the web app lands in the Android app on the
next `npm run sync` — automatically. A copied `web/` folder would drift, and you
would eventually ship a fix to one and forget the other.

## Prerequisites (all already present on this machine)

| | |
|---|---|
| Node ≥ 22 | v26.10.0 ✅ |
| **JDK 21** | `/usr/lib/jvm/java-21-openjdk` ✅ — pinned in `android/gradle.properties` |
| Android SDK | `~/Android/Sdk` ✅ platforms android-36 + android-36.1, build-tools 36.x |
| Physical Android phone | USB debugging on — **no emulator**, saves ~12 GB |

🔴 **Do not build with the system `java`.** It is OpenJDK **27**, and Gradle 8.14
supports running on Java **24 at most** ([compatibility matrix](https://docs.gradle.org/current/userguide/compatibility.html)).
`android/gradle.properties` pins `org.gradle.java.home` to JDK 21, but also export
`JAVA_HOME` so `gradlew`'s own bootstrap JVM is 21:

```bash
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk
export ANDROID_HOME=~/Android/Sdk
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"
```

## Build

```bash
npm install                 # once
npm run sync                # copy ../web → android assets
npm run build               # → signed release APKs (per-ABI splits)
```

Output in `android/app/build/outputs/apk/release/`:

| APK | Size | Ship to |
|---|---|---|
| `app-arm64-v8a-release.apk` | **29 MB** | virtually every phone from the last ~7 years |
| `app-armeabi-v7a-release.apk` | 23 MB | older / budget 32-bit devices |
| `app-universal-release.apk` | 72 MB | fallback when the device ABI is unknown |

ABI splits exist because the ML Kit OCR + barcode plugins ship native `.so` per
ABI; a universal APK carries all four copies. x86/x86_64 are excluded on purpose
(we test on a real phone).

Install on a plugged-in phone:
```bash
adb devices -l
adb install -r android/app/build/outputs/apk/release/app-arm64-v8a-release.apk
```

## 🔴 The keystore

`keystore/niveshrakshak-release.jks` + `keystore/keystore.properties` are
**gitignored**. The password was generated locally and never printed.

- **Back both files up off this machine now.**
- Android installs an update over an existing app **only if it is signed with the
  same key.** Lose the key → your testers must uninstall and reinstall (losing
  local data), and you can never update the app they already have.
- Validity: 2026-10-02 → **2056-09-24** (30 years), RSA 4096, alias `niveshrakshak`.
- SHA-256 fingerprint (public, safe to share): `c0a786a8372b65a8e2e38b3d2421034e85221beeb0d5b54aa761d8bf0fd4e422`

## Backend URL

Lives in **one place**: `../web/api-config.js`.

It resolves automatically:
- Capacitor WebView (origin `https://localhost`) → the remote API
- hosted web version / local `./run.sh` → `""` (same-origin)

⚠️ **The current value is a Cloudflare QUICK TUNNEL** — free, no domain, no
inbound ports, but **the hostname changes every time the tunnel restarts.**
If the app suddenly cannot reach the backend:

```bash
ssh hermes 'grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" /var/log/nr-tunnel.log | tail -1'
```
Paste it into `api-config.js`, then `npm run sync && npm run build`.

For a permanent URL see `../deploy/README.md`.

## Plugins (all versions npm-verified 2026-10-02, all free)

| Plugin | Version | License | Purpose | Status |
|---|---|---|---|---|
| `@capacitor/core` `cli` `android` | 8.5.2 | MIT | shell | ✅ building |
| `@capacitor/share` | 8.0.2 | MIT | share the verdict card **out** | ✅ installed |
| `@capacitor/filesystem` | 8.1.3 | MIT | write the PNG to Cache | ✅ installed |
| `@capacitor/camera` | 8.2.4 | MIT | camera capture | ✅ installed |
| `@capacitor-mlkit/text-recognition` | 8.2.1 | Apache-2.0 | on-device OCR incl. **Devanagari** | ✅ installed, **not yet wired** |
| `@capacitor-mlkit/barcode-scanning` | 8.2.1 | Apache-2.0 | QR from a static image + live camera | ✅ installed, **not yet wired** |
| `@capgo/capacitor-share-target` | 8.0.54 | MPL-2.0 | receive shares **in** | ✅ installed, **needs JS wiring** |

🔴 Deliberately avoided: `@capacitor-community/barcode-scanner` (**archived** Oct 2024),
`send-intent` (stale, no v8 release), `@capawesome-team/capacitor-share-target` (paid).

## What is wired vs still to do

**Working right now:** the full existing web app inside a native shell — paste a
message, upload a screenshot (server-side tesseract OCR), QR photo, SEBI Check
live verification, registry near-miss, EN/HI toggle, verdict card, captcha
pass-through, share out.

**Remaining (see `../docs/IMPLEMENTATION-PLAN.md` Phases 3–5):**
1. **Share IN** — the manifest intent-filters are already added (SEND text/plain,
   SEND image/*, SEND_MULTIPLE, PROCESS_TEXT, `exported="true"`, `singleTask`).
   What's left is the JS side: subscribe to `@capgo/capacitor-share-target`'s
   `shareReceived`, and **copy `content://` bytes into cache immediately** (the
   temporary grant does not survive process death, and
   `takePersistableUriPermission` will not work because WhatsApp/Telegram never
   set the persistable flag).
2. **Clipboard fallback** — 🔴 Telegram offers **no** external share for text
   messages (Forward is internal-only; long-standing open feature request). A
   prominent "Paste from clipboard" on app resume is the only way to cover it.
   This is exactly why RakshaLink uses Paste&Check.
3. **Share OUT recipe** — replace the `html2canvas` download path with:
   canvas → base64 (**strip the `data:image/png;base64,` prefix**) →
   `Filesystem.writeFile({path:'verdict.png', directory:Directory.Cache})` →
   `Share.share({files:[uri]})`. The filename **must** end `.png` and the
   directory **must** be `Cache`, or WhatsApp rejects it / `getUriForFile` throws.
4. **On-device OCR + QR** — swap the server round-trip for ML Kit so screenshots
   never leave the phone.

## Notes

- `web/vendor/html2canvas.min.js` (1.4.1, dead since 2022, 1054 open issues,
  crashes on `oklch()`/`color()`) was replaced with **`html2canvas-pro` 2.5.0**.
  Its UMD build self-flattens (`window.html2canvas = window.html2canvas.default`),
  so the existing `html2canvas(card, {...})` call needed no change.
- `capacitor.config.json` is JSON, not TS — Capacitor requires TypeScript to be
  installed for a `.ts` config, and this project deliberately has no build step.
- No Google Play services dependency: the ML Kit plugins use **bundled** model
  artifacts, so the app runs on devices without GMS.
