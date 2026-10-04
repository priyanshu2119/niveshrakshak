# Capacitor Plugin Research — Android Requirements (a)–(h)

Researched 2026-10-01 via live web (firecrawl) + npm registry + GitHub API. All versions are `latest` on npm as of this date.

## TL;DR

| # | Requirement | Verdict | Plugin @ version |
|---|-------------|---------|------------------|
| a | RECEIVE shared content (share target) | **MODERATE** | `@capgo/capacitor-share-target` 8.0.54 (free) or `@capawesome-team/capacitor-share-target` 8.x (PAID Insiders) |
| b | SEND image file to WhatsApp | **EASY** (1 known quirk) | `@capacitor/share` 8.0.2 (official) |
| c | OCR English + Hindi/Devanagari, offline | **EASY** | `@capacitor-mlkit/text-recognition` 8.2.1 (free, OSS) |
| d | QR decode (camera + static image) | **EASY** | `@capacitor-mlkit/barcode-scanning` 8.2.1 (static image ✓) + official `@capacitor/barcode-scanner` 3.1.2 (camera UI) |
| e | Camera / photo picking | **EASY** | `@capacitor/camera` 8.2.4 (official) |
| f | Save generated PNG | **EASY** (gallery-save nuance) | `@capacitor/filesystem` 8.1.3 (official) |
| g | HTML→PNG in WebView | **EASY–MODERATE** | `html2canvas-pro` 2.5.0 (NOT `html2canvas` 1.4.1) |
| h | HTTPS JSON + multipart upload | **EASY** | plain `fetch`/`FormData` + server CORS; `CapacitorHttp` (built into core) only for 3rd-party APIs |

---

## (a) Share TARGET — receive from WhatsApp/Telegram/Gallery — MODERATE (riskiest, but solvable)

**Official `@capacitor/share` is SEND-only.** No official receive plugin exists. Receiving requires BOTH:
1. `AndroidManifest.xml` intent-filters on `MainActivity` (`android:exported="true"`, recommended `android:launchMode="singleTask"`): `ACTION_SEND` + `text/plain`, `ACTION_SEND` + `image/*`, `ACTION_SEND_MULTIPLE` + `image/*`.
2. A plugin (or ~50 lines of custom Kotlin) to read the intent and bridge `EXTRA_TEXT` / `EXTRA_STREAM` (content:// URI) to JS.

Options, best first:

| Plugin | Version | Cost | Status | Notes |
|---|---|---|---|---|
| `@capgo/capacitor-share-target` | 8.0.54 | Free (OSS) | Active — repo pushed 2026-09-24, v8 marked "maintained ✅" | `addListener('shareReceived', e => {e.title, e.texts, e.files[{name,mimeType,uri}]})`. Small community (20★, 6 open issues). https://github.com/Cap-go/capacitor-share-target |
| `@capawesome-team/capacitor-share-target` | 8.x (private registry) | **PAID — Capawesome Insiders only** (license key via Polar, private npm registry) | Active support, plugin 8.x ↔ Capacitor ≥8 | Most complete: text/URL/image/video/files, large-file caching, Web Share Target API, demo repo https://github.com/capawesome-team/capacitor-share-target-demo. Docs: https://capawesome.io/docs/sdks/capacitor/share-target/ |
| `send-intent` | 7.0.0 (published 2025-02-27) | Free | **Aging** — peerDep `@capacitor/core >=7`, no v8 release | https://github.com/carsten-klaffke/send-intent. Tutorial: https://capacitor-tutorial.com/blog/send-intent/ |
| Custom Kotlin bridge | — | Free | Always works | Override intent handling in MainActivity, emit to WebView via Capacitor bridge. Full control, no dependency risk. |

- `@capawesome/capacitor-app-shortcuts` (8.0.2) is **NOT** a share target — it's home-screen long-press shortcuts. Irrelevant here.
- WhatsApp shares a single message as `text/plain`; screenshots from Gallery arrive as `image/*` `ACTION_SEND` — both covered by the filters above. (Consistent with prior research in `docs/ANDROID-PRESENCE-POLICY.md` / repo memory: ACTION_SEND target = zero Play declaration burden.)
- Bonus: `ACTION_PROCESS_TEXT` (text-selection toolbar "Check with…" in ANY app) is NOT covered by any of these plugins — needs a manifest entry + custom Kotlin or a generic intent plugin.
- **UNVERIFIED:** cold-start (app not running) intent delivery in `@capgo/capacitor-share-target` — not tested here; check its issues before committing. Fallback = custom Kotlin (well-documented pattern, e.g. https://stackoverflow.com/questions/62238132).

## (b) SEND image file OUT to WhatsApp — EASY

- `@capacitor/share` **8.0.2** (official, ships with Capacitor 8). Supports file sharing: `Share.share({ files: [path] })` (multiple files) or `url: photo.path` (single local file), plus `text`/`title`. Android uses FileProvider `content://` URIs. Docs: https://capacitorjs.com/docs/apis/share
- **Known quirk:** community reports that some apps (WhatsApp among them, in some configurations) don't detect images shared by the plugin — "known issue, some apps don't detect the images the way Capacitor share plugin shares them, so will need some code changes": https://forum.ionicframework.com/t/ionic-capacitor-share-plugin-not-sharing-image-with-whatsapp/212601. **UNVERIFIED** whether this affects 8.0.2 — do a real-device WhatsApp test early. Text sharing is unaffected.

## (c) On-device OCR English + Hindi — EASY

- `@capacitor-mlkit/text-recognition` **8.2.1** (published 2026-09-10). New npm scope `@capacitor-mlkit/*` (repo: https://github.com/capawesome-team/capacitor-mlkit, 216★, pushed 2026-09-18, not archived). Plugin 8.x = "Active support" for Capacitor ≥8.
- **Free & open source** — confirmed by vendor FAQ: "All ML Kit plugins listed here are open source and free to use" (https://capawesome.io/docs/sdks/capacitor/mlkit/). No license key, "No configuration required".
- **Scripts: Latin, Chinese, Devanagari, Japanese, Korean** — Devanagari confirmed. API: `TextRecognition.processImage({ path, script: Script.Devanagari })` → `{text, blocks}`.
- **Offline/bundled:** Android deps are the *bundled* ML Kit artifacts (`com.google.mlkit:text-recognition-devanagari:16.0.1` etc., overridable via `variables.gradle`) → works with **no network and no Google Play services**. Size cost: "several MB" per script model.
- Docs: https://capawesome.io/docs/sdks/capacitor/mlkit/text-recognition/ · Demo: https://github.com/robingenz/capacitor-mlkit-plugin-demo
- iOS note (if ever needed): CocoaPods only, no SPM, deployment target ≥15.5.
- **UNVERIFIED:** whether one `Script.Devanagari` pass also captures embedded English/Latin text (Google's v2 script models are documented to recognize English alongside their script — likely yes, but test; worst case run Latin + Devanagari and merge).

## (d) QR decoding — EASY

- **Static image file (your screenshot case):** `@capacitor-mlkit/barcode-scanning` **8.2.1** (free/OSS, same repo as (c), published 2026-09-10). Has `readBarcodesFromImage({ path })` (Android/iOS; `blob` on Web since 7.4.0) — docs explicitly list the use case "Importing barcodes from images: Read barcodes from existing photos, for example a screenshot of a QR code". Also `startScan()` for live camera. Rich result types (URL, WiFi, contact, driver license…). https://capawesome.io/docs/sdks/capacitor/mlkit/barcode-scanning/
- **Official `@capacitor/barcode-scanner` 3.1.2** (OutSystems-donated libs): live-camera scanner UI only (`scanBarcode(options)` — no image-file parameter in the API). Android engine selectable: `ZXING` (all formats) or `MLKIT` (all except MAXICODE/RSS_14/RSS_EXPANDED/UPC_EAN_EXTENSION). Requires **minSdk 26** (vs Capacitor default 24). Web via html5-qrcode. https://capacitorjs.com/docs/apis/barcode-scanner
- **`@capacitor-community/barcode-scanner` is ARCHIVED** (repo archived, last push 2024-10-10) — do not use. https://github.com/capacitor-community/barcode-scanner
- Capawesome also sells a paid Insiders "Barcode Scanner" plugin (AVFoundation/Vision on iOS) — not needed for Android.
- Recommendation: `@capacitor-mlkit/barcode-scanning` alone covers both live camera and static images, free.

## (e) Camera — EASY

- `@capacitor/camera` **8.2.4** (official, maintained in lockstep with core). `getPhoto()` (camera capture) + `pickImages()` (gallery multi-pick). https://capacitorjs.com/docs/apis/camera

## (f) Save PNG to device — EASY (one nuance)

- `@capacitor/filesystem` **8.1.3** (official; now depends on `@capacitor/synapse`). `writeFile()` with base64 data to `Directory.Cache`/`Data` (app-private, no permissions) or public dirs. https://capacitorjs.com/docs/apis/filesystem
- Nuance: making the PNG appear in the **system Gallery** on Android 10+ (scoped storage) needs MediaStore insertion — either a community media plugin or simply handing the file to the share sheet ("Save to images"/WhatsApp). App-private save + share = trivially easy; direct gallery insert = the only moderate path. **UNVERIFIED:** exact behavior of Filesystem 8.x public-directory writes on API 36 — test on device.

## (g) html2canvas in Android WebView — EASY–MODERATE

- **Do not use `html2canvas` 1.4.1** (last release 2022; repo effectively dormant — last push 2024-07-18, **1,054 open issues**). It fails hard on modern CSS color functions: `oklch()`, `color()`, `lab()` → "Attempting to parse an unsupported color function" (https://github.com/niklasvh/html2canvas/issues/2700; the Tailwind-4 breakage: https://www.reddit.com/r/tailwindcss/comments/1ib2iv0/). This is a parser limitation of the library, **not** of the WebView — Chromium WebView renders oklch fine (Chrome 111+), html2canvas re-implements CSS parsing and chokes.
- **Use `html2canvas-pro` 2.5.0** — published **2026-09-30** (one day before this research), actively maintained fork with oklch/color()/lab/lch support. https://www.npmjs.com/package/html2canvas-pro · https://github.com/yorickshan/html2canvas-pro. Drop-in API. You already vendor `web/vendor/html2canvas.min.js` — swap the vendored file.
- Remaining known caveats (both libs): external images taint canvas unless CORS-served (your images are local/blob → fine); webfonts must be fully loaded before capture (your fonts are locally vendored → fine); SVG support partial; some exotic CSS (blend modes, filters) unsupported. Your controlled DOM (no Tailwind 4, local assets) = low risk.
- Alternative if it ever misbehaves: native WebView screenshot via a community screenshot plugin, or render server-side.

## (h) Remote HTTPS JSON + multipart upload — EASY

- **Plain `fetch` + `FormData` works** in the Capacitor WebView. With default `androidScheme: "https"` the origin is `https://localhost`, so normal CORS rules apply — **your own FastAPI backend just needs `CORSMiddleware` allowing `https://localhost`** (trivial; you control the server). This is the most reliable path for multipart file upload.
- `CapacitorHttp` (built into `@capacitor/core`, enabled via `plugins.CapacitorHttp.enabled` in capacitor.config — it monkey-patches `window.fetch`/XHR to run natively, bypassing CORS entirely): intended for **third-party** APIs that can't set CORS headers. It does support FormData (`dataType: 'formData'` in HttpOptions; `BodyInit` includes `FormData` — https://capacitorjs.com/docs/apis/http), but has a bug history: FormData/image-upload gaps (https://github.com/ionic-team/capacitor/issues/7498), empty-file reports (https://stackoverflow.com/questions/76488467/), and it sends an **empty `Origin` header on Android** (https://forum.ionicframework.com/t/capacitorhttp-on-android-is-sending-empty-origin/247643) which can break strict server-side origin checks.
- Recommendation: own API → plain fetch + server CORS. siportal/SEBI stays server-side per existing architecture, so no third-party CORS problem exists in this app.

---

## 9. Capacitor 8 — current major, requirements, no-build-step

- **Current: Capacitor 8** (`@capacitor/core` **8.5.2** on npm, 2026-10-01; docs versioned "v8"). Announcement: https://ionic.io/blog/announcing-capacitor-8 (exact release date **UNVERIFIED** — not fetched).
- **Android:** `targetSdk 36` (Android 16) — **mandatory, custom target SDK unsupported** (https://capacitorjs.com/docs/android/setting-target-sdk); `minSdk 24` (Android 7.0); AGP 8.13 / Gradle 8.14 (https://capgo.app/blog/upgrade-capacitor-app-to-capacitor-8/). Official barcode plugin raises minSdk to 26 if used.
- **Tooling:** Node **≥22**; Android Studio **≥2025.2.1**; JDK bundled with Android Studio (https://capacitorjs.com/docs/getting-started/environment-setup). iOS (FYI): Xcode 26, iOS 15 min, SPM default.
- **No build step: YES.** `webDir` in capacitor.config points at any static folder — your existing `web/` (plain HTML/JS/CSS) is copied as-is into the Android project; no framework, no bundler required. One nuance: the Capacitor plugin JS packages are npm ESM modules — with zero build step you load them by **vendoring their `dist/esm` bundles into `web/vendor/`** (same pattern as your existing `html2canvas.min.js`) or via an import map; alternatively one tiny esbuild command bundles just the plugin glue. Your app code itself stays build-free.

## 10. Without Google Play Store — YES

- A Capacitor Android app is a **standard Gradle project**: `./gradlew assembleRelease` (or `npx cap build android`) produces a signed standalone APK — sideloadable/distributable anywhere. Nothing in Capacitor core requires Play Store distribution or Play licensing.
- **Play-services dependencies:** Capacitor core = none (it uses the system Android WebView, preinstalled on all GMS and most non-GMS devices). The ML Kit plugins here use the **bundled** artifacts (`com.google.mlkit:text-recognition-*` / barcode, v16.0.1/17.x) which ship models inside the APK and run **fully on-device without Google Play services** — consistent with prior on-device research (`docs/ONDEVICE-ARCHITECTURE.md`). ZXing = pure Java, no GMS. So a de-Googled/Huawei-style device runs everything except WebView updates (vendor-supplied there).
- Only if you later add push notifications (FCM) would GMS become a hard dependency — not in scope.

---

## Unverified / flag list

1. Capacitor 8 exact release date (blog not fetched).
2. `@capacitor/share` 8.0.2 + WhatsApp image detection quirk — forum-reported, version-specific status unknown → **device-test in week 1**.
3. Single-pass Devanagari+English OCR via `Script.Devanagari` — Google-documented behavior, not re-verified here.
4. `@capgo/capacitor-share-target` cold-start delivery + real-world robustness (20★ project) — inspect issues/demo before committing; paid Capawesome plugin or custom Kotlin are the fallbacks.
5. Filesystem 8.x public-directory (Gallery) writes on API 36 scoped storage.
6. Capawesome Insiders pricing for the share-target plugin (not fetched).
