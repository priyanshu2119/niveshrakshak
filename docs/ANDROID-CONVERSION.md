# NiveshRakshak → Android App: Conversion Blueprint

Researched & written 2026-10-01. Every external fact below was verified via live web
research (sources inline). Items marked ⚠️ are unverified/judgment calls.

---

## 0. TL;DR — Recommended route

**Route A: Capacitor 8 app (bundled frontend) + FastAPI backend hosted on Fly.io Mumbai ($5/mo).**

- Your `web/` folder ships *inside* the APK (no blank-screen-if-server-down problem),
  native plugins give you Camera + Share sheet + Splash, and the Python backend keeps
  doing what only it can do: the SEBI Check session dance (WAF, captcha pass-through,
  circuit breaker, shared 6h cache) and the registry mirror.
- **Working APK on a phone: 1–2 days. Play Store production: ~3–4 weeks** (mostly the
  mandatory 14-day closed test).
- Total cost: **$5/mo hosting + $25 one-time Play account** (fly.dev subdomain = free HTTPS).
- Biggest risk: **whether siportal.sebi.gov.in's WAF tolerates datacenter IPs** —
  unverified; test with one curl on deploy day. Fallbacks in §6.

Why not the alternatives (full comparison in §2):
- **TWA/Bubblewrap** (Route B): lightest effort, but needs PWA-ification first
  (manifest + service worker + assetlinks.json — none exist today) and the app is
  100% remote → weaker Play "Minimum Functionality" position.
- **Fully on-device Chaquopy** (Route C): zero server cost, strongest privacy story,
  and your 5.6 MB SQLite mirror bundles easily — but 4 dependency blockers
  (pydantic-core, rapidfuzz, tesseract, zbarimg) make it a 1–2 week job, and
  per-device SEBI sessions kill the shared-cache politeness that protects you from
  SEBI rate gates. Keep it as the v2 evolution.
- **Native Kotlin / Flutter / RN rewrite**: 3–6 weeks, re-implements tested logic,
  no user-visible gain over Route A. Overkill.

---

## 1. Codebase index (what has to move where)

Full read of all 4,741 lines on 2026-10-01. Component → Android disposition:

| Component | What it does | Android disposition (Route A) |
|---|---|---|
| `server/app.py` | FastAPI orchestration, rate limit, CSP, static mount | **Stays on server.** Add CORS + proxy-headers (§3.2) |
| `server/sebicheck.py` | SEBI Check session (CA_SESSIONID, WAF-505 retry, captcha pass-through, circuit breaker, 6h cache) | **Must stay server-side.** Stateful shared session + cache is a feature: one SEBI hit per viral handle, captcha state can't live on 1000 devices |
| `server/registry.py` | Live AJAX + SQLite mirror + rapidfuzz near-miss | **Stays on server** (Route A). 5.6 MB DB → bundleable on-device in Route C |
| `server/extract.py` | Regex extraction (UPI incl. `(at)` obfuscation + zero-width strip, IFSC, accounts, phones, regnos, org names, categories) | **Stays on server** (pure Python, trivially portable to Kotlin later if ever needed) |
| `server/redflags.py` | 10 EN/HI scam-language patterns, no score | **Stays on server** |
| `server/verdict.py` | Strict precedence assembly (failed primary never overridden; unavailable poisons headline) | **Stays on server** — this is the product's spine; do NOT re-implement client-side |
| `server/policy.py` | @valid transition policy (env-configurable) | **Stays on server** |
| `server/db.py` | SQLite: registry mirror, masked audit log (90d), cache, meta | **Stays on server** + persistent volume |
| `server/ocr.py` | tesseract (eng+hin) + zbarimg CLI subprocesses | **Stays on server** (Docker apt packages). Route C replaces with Tesseract4Android/pyzbar or ML Kit |
| `tools/refresh_registry.py` | Daily .xls download, 25 categories | **Stays on server** (background thread already wired) |
| `web/index.html`, `styles.css`, `fonts.css`, `i18n.js`, `fonts/` (776 KB), `icon.svg` | UI shell, paper-and-stamp design, EN/HI dictionary, self-hosted fonts | **Bundles into the APK unchanged** |
| `web/app.js` | fetch `/api/check` `/api/captcha` `/api/health`, verdict render, html2canvas PNG, Web Share | **Bundles with 3 small edits** (§3.3): API_BASE, native share bridge, (optional) camera |
| `web/vendor/html2canvas.min.js` | Verdict-card PNG export | Bundles; ⚠️ test in Android WebView (generally works) |
| `tests/` | 6 offline test files + live-marked tests | Run in CI against the server; add a deployed-endpoint smoke test |

Key facts that shape the plan:
- Frontend is **vanilla JS, no build step** → Capacitor can bundle it as-is; no
  bundler/framework migration needed.
- Frontend talks to exactly **3 endpoints** (`/api/check` POST multipart, `/api/captcha`
  GET, `/api/health` GET) → API-base-URL change is a 3-line edit.
- **No `manifest.json`, no service worker** → the app is *not* a PWA today; Route B
  requires creating both first.
- `data/nr.sqlite` = **5.6 MB** (23.5k registry rows) — small enough to bundle in an
  APK or download on first launch (matters for Route C).
- `server/tessdata/` = 5 MB (eng+hin traineddata, already in repo; `ocr.py` points
  `TESSDATA_PREFIX` at it, so the Docker image doesn't even need `tesseract-ocr-hin`).
- CSP `connect-src 'self'` is a **server response header** — it does not apply to the
  bundled APK copy (assets served from the device), so cross-origin fetch to the API
  works without CSP changes. (If you ever add a `<meta>` CSP, allow the API origin.)

---

## 2. Architecture options compared (research-backed)

### Route A — Capacitor 8 shell + hosted Python backend ✅ RECOMMENDED

Capacitor (Ionic) compiles your web assets into a real Android Studio project with a
WebView + native plugin bridge.

Verified facts (Oct 2026):
- **Capacitor 8** is current; ships **targetSdk 36** (Capacitor 7 → 35, 6 → 34; a new
  major every year to stay Play-compliant). Requires **Node 22+**, **Android Studio
  2025.2.1+**, JDK 21 (bundled with Android Studio), min **Android 7 / API 24**.
  (capacitorjs.com/docs/android/setting-target-sdk, /docs/getting-started/environment-setup)
- Official plugins you need: `@capacitor/camera`, `@capacitor/share` (native share
  sheet **with image files**), `@capacitor/filesystem`, `@capacitor/splash-screen`,
  `@capacitor/status-bar` (v8 also adds a newer System Bars plugin). Install with the
  `@latest-8` npm tag. (capacitorjs.com/docs/apis)
- **Bundled assets vs `server.url` remote loading**: remote works and people ship it,
  but it's a grayer Play-policy area, has no offline story, and a blank screen if your
  server dies. Bundled + native plugins = strongest compliance position.
  (github.com/ionic-team/capacitor/discussions/4080, capawesome.io blog)
- Play's **"Spam and Minimum Functionality"** policy rejects apps that merely load a
  website URL; wrapping **your own** content with real native functionality (camera,
  share, offline shell) is explicitly acceptable. Verbatim: *"We don't allow apps whose
  primary purpose is to … provide a webview of a website without permission from the
  website owner"* — your own site, your permission, plus native features = fine.
  (support.google.com/googleplay/android-developer/answer/18258653,
  play.google.com/about/spam-min-functionality/)
- **Target API deadlines**: new apps submitted after **Aug 31, 2026 must target API 36**
  (Android 16) — that deadline has passed as of today, so Capacitor 8 (targetSdk 36) or
  Bubblewrap ≥1.25.0 is mandatory, not optional. Extension to Nov 1, 2026 requestable
  in Play Console. (developer.android.com/google/play/requirements/target-sdk)

### Route B — TWA via Bubblewrap (host everything, wrap with Chrome)

- **Bubblewrap v1.25.0** (Jul 31, 2026), maintained by Google ChromeLabs, generates
  **targetSdk 36** apps; built-in `bubblewrap play` commands for Play Console uploads.
  (github.com/GoogleChromeLabs/bubblewrap/releases)
- Requirements: **PWA manifest** (name, icons, `start_url`, `display: standalone`),
  **HTTPS**, **`assetlinks.json`** Digital Asset Links at `/.well-known/` (without it
  the browser URL bar shows). Service worker needed for offline/installability quality.
  (developer.chrome.com/docs/android/trusted-web-activity/quick-start)
- Google **explicitly sanctions** TWAs for Play (official codelab "Adding Your PWA to
  Google Play") — but Minimum Functionality review still applies, and a TWA is by
  definition remote-content.
- For NiveshRakshak: you'd deploy the *whole* app (FastAPI already serves `web/`) to
  one HTTPS origin, add manifest + SW + assetlinks, run `bubblewrap init --manifest
  https://yourdomain/manifest.webmanifest && bubblewrap build`. **Near-zero frontend
  code changes.** Web Share API + html2canvas keep working because the engine is
  literal Chrome.
- Verdict: viable and lightest-touch, but server-down = dead app, and the Play
  reviewer story is weaker than Route A's bundled+plugins profile.

### Route C — Fully on-device: Chaquopy (Python inside the APK, no server)

Verified facts (Oct 2026):
- **Chaquopy 17.0.0** (Dec 2025): **MIT license — free even for closed-source
  commercial use** (free since v12.0.1 via Anaconda sponsorship). Python **3.10–3.14**
  (your 3.11 ✅). Min API 24, AGP 7.3–9.2. **16 KB page size: fully supported**
  (core libs 16 KB-ready since Chaquopy 16; tracking issue #1171 closed against 17.0 —
  ahead of the Nov 1, 2025 Play deadline). Caveat: native wheels for Python ≤3.12 were
  initially not 16 KB-aligned; **Python 3.13+ wheels are fine**.
  (chaquo.com/chaquopy/news/, github.com/chaquo/chaquopy/issues/1171)
- **The FastAPI + uvicorn in-process + WebView-on-`127.0.0.1` pattern is proven in
  production**: OpenSquilla-mobile (Apache-2.0, updated Aug 2026 — "FastAPI gateway
  boots inside the app via Chaquopy, serves the web UI in a local WebView on
  127.0.0.1:18790"), Kolibri Installer Android (Learning Equality, production education
  app), snowdrift. (github.com/lzhhhhc/OpenSquilla-mobile,
  github.com/learningequality/kolibri-installer-android)
- Known pitfalls (all documented): Android 9+ **cleartext policy** needs
  `usesCleartextTraffic` or a `networkSecurityConfig` loopback exception; run uvicorn
  **in-process in a Python thread** (no subprocess/fork on Android); bind `127.0.0.1`
  only (no permission needed for unprivileged loopback ports); aggressive OEM ROMs
  (MIUI/EMUI) freeze background processes — fine if the server lives only while the
  activity is open.
- **Dependency audit for your `requirements.txt`** against Chaquopy's wheel repo
  (chaquo.com/pypi-13.1/, 133 native packages + pure-Python PyPI fallback):

  | Package | Status | Fix |
  |---|---|---|
  | fastapi / uvicorn / starlette | pure-Python ✅ | — |
  | **pydantic-core** (FastAPI dep, Rust) | ❌ not in repo | supply a pre-built Android wheel (OpenSquilla precedent bundles one) ⚠️ project-specific |
  | requests, xlrd, python-multipart | pure-Python ✅ | — |
  | pillow | ✅ in repo | — |
  | **rapidfuzz** (C++) | ❌ not in repo, no p4a recipe | replace with stdlib `difflib` or `editdistance` (in repo), or build your own wheel via Chaquopy's server/pypi toolchain |
  | sqlite3 | ✅ stdlib bundled (16 KB-fixed) | — |
  | uvloop | ❌ | uvicorn falls back to stdlib asyncio — fine on-device |
  | **tesseract CLI** | ❌ can't exec system binaries | **Tesseract4Android 4.9.0** (Apache-2.0, active — Jun 2025 release, commits into Feb 2026, wraps Tesseract 5.5.1; ship your existing 5 MB eng+hin traineddata from assets) **or ML Kit** via Kotlin bridge |
  | **zbarimg CLI** | ❌ | **pyzbar** ✅ *is* in Chaquopy's repo (wraps chaquopy-zbar) — near drop-in for `decode_qr` |
- On-device OCR alternative: **ML Kit Text Recognition v2** — confirmed **Devanagari
  support**, free, fully on-device; bundled model ~4 MB/script vs ~260 KB unbundled
  (Play-services-delivered); API `TextRecognition.getClient(DevanagariTextRecognizerOptions…)`.
  ⚠️ Docs say non-Latin scripts are slower; ⚠️ mixed Eng+Hindi screenshots may need
  two passes (Latin + Devanagari clients) and merging — unverified, test it. For QR:
  **ML Kit Barcode Scanning API** on a Bitmap (the permissionless "Google code scanner"
  is live-camera-UI only — wrong tool for QRs *inside screenshots*).
  (developers.google.com/ml-kit/vision/text-recognition/v2/android,
  developers.google.com/ml-kit/vision/barcode-scanning)
- **Why Route C is v2, not v1**: (1) four dependency blockers = days of yak-shaving;
  (2) **per-device SEBI sessions** mean per-device captchas and *no shared cache* — a
  viral scam handle checked by 100 users hits SEBI 100× (your server-side 6h cache
  exists precisely to prevent this; SEBI's rate gates would punish the distributed
  model); (3) registry refresh becomes a per-device 25-file download. The centralized
  backend is not legacy baggage — it's your SEBI-politeness and captcha-state anchor.
  Route C's wins (₹0 server, messages never leave the device) are real; revisit when
  server cost or the privacy narrative demands it.

### Route D — Native Kotlin / Flutter / React Native rewrite

3–6 weeks re-implementing tested, adversarially-reviewed logic (`verdict.py` precedence
rules are money paths with dedicated tests). Flutter/RN WebView wrappers are strictly
worse than Capacitor for your case: extra toolchain, same wrapper, fewer free native
plugins. Only makes sense if you later want a fully native UI. **Not now.**

---

## 3. Route A step-by-step

### 3.1 Backend: Dockerize + deploy (Day 1, ~2–3 h)

**Dockerfile** (repo root):

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr zbar-tools \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server/ server/
COPY tools/ tools/
COPY web/ web/
COPY data/nr.sqlite data/nr.sqlite   # seed mirror; volume overrides in prod
ENV HOST=0.0.0.0 PORT=8300
EXPOSE 8300
CMD ["sh", "-c", "exec uvicorn server.app:app --host 0.0.0.0 --port ${PORT:-8300} --proxy-headers --forwarded-allow-ips='*'"]
```

Notes:
- `tesseract-ocr-hin` apt package NOT needed — `ocr.py` sets `TESSDATA_PREFIX` to the
  repo's own `server/tessdata/` (eng+hin already bundled, 5 MB).
- `--proxy-headers --forwarded-allow-ips='*'` is **load-bearing**: without it,
  `request.client.host` is the platform proxy's IP and your per-IP token bucket
  (30 checks/10 min) becomes a *global* bucket — the app breaks under ~30 users.

**Deploy target: Fly.io Hobby ($5/mo)** — the only sub-$10 PaaS with a **Mumbai (BOM)
region** (~10–30 ms for Indian users), custom Docker, **persistent volumes** for
`data/nr.sqlite`, and always-on machines (no forced spin-down). A shared-cpu-1x 512 MB
machine (~$3/mo) + 1 GB volume (~$0.15/GB/mo) fits inside the included $5 credit.
Free `*.fly.dev` subdomain with automatic TLS → no domain purchase needed for v1.
(docs.fly.io/about/pricing)

Runner-up: **DigitalOcean Bangalore $6/mo (1 GB droplet)** — plain VPS, India-local IP
(⚠️ may fare better with SEBI's WAF than US/EU ranges — unverified), Caddy for auto-TLS.

Avoid: **Render free** (15-min idle spin-down, 30–60 s cold starts, persistent disks
paid-only, no India region), **AWS new free tier** (post-Jul-2025 model: $100 credits,
6-month expiry, account auto-closes), **Zeabur free** (sleeps). **Oracle Always Free
A1 Mumbai** (4 OCPU/24 GB, $0) is the best-specs gamble but has chronic ARM
"Out of Capacity" in Mumbai/Hyderabad, idle-instance reclamation, and a ⚠️ June-2026
policy change — only with a one-command migration path to Fly/DO.

**🔴 GO/NO-GO TEST — run immediately after first deploy:**

```bash
fly ssh console -a <app> -C "curl -sS -o /dev/null -w '%{http_code}\n' \
  -A 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36' \
  https://siportal.sebi.gov.in/intermediary/sebi-check"
# expect 200. Also POST a known-invalid UPI through your own /api/check and
# confirm you get a real SEBI verdict (TXN-… id), not circuit_open/unavailable.
```

Live-probe evidence from research (Oct 1, 2026, residential Indian IP): `HEAD` to
siportal returns **505 BLOCKED** (WAF blocks by method regardless of UA — use GET/POST
only, which your client already does); `GET` returns 200 even with bare curl UA;
www.sebi.gov.in is plain Apache, no visible WAF. **Datacenter-IP blocking is UNVERIFIED
in both directions** — no public reports either way, no official SEBI API/app program
exists, and no public GitHub projects call the sebi-check endpoints. You are in thinly
charted territory; the day-one curl is the only real answer. Fallback chain in §6.

### 3.2 Backend code changes (small, ~1 h)

1. **CORS** for the app's WebView origin (Capacitor Android default origin is
   `https://localhost`; iOS is `capacitor://localhost`):

   ```python
   from fastapi.middleware.cors import CORSMiddleware
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["https://localhost", "http://localhost", "capacitor://localhost"],
       allow_methods=["*"], allow_headers=["*"])
   ```

   Keep the existing security-headers middleware; CORS and it coexist. (Alternative:
   Capacitor's `CapacitorHttp` plugin routes fetch through the native layer and skips
   CORS entirely — but its multipart/file-upload support is weaker; plain CORS is safer
   for your `FormData` + image upload.)
2. **Admin endpoint**: `/api/admin/refresh-registry` checks `ip in ("127.0.0.1","::1")` —
   with proxy-headers enabled, real client IPs are never loopback, so it stays locked.
   Optionally add a shared-secret header for yourself.
3. **Scale note (post-launch)**: one shared SEBI session behind a global lock
   serializes all users (already flagged in LIMITATIONS.md §4). Fine for closed test +
   early production; before any viral moment, move to a small per-user session pool.
4. **Contract canary** (LIMITATIONS.md §2): a cron/scheduled job that POSTs a known
   handle and asserts the response shape — alerts you when SEBI changes the endpoint.

### 3.3 Frontend changes (3 edits in `web/app.js`, ~1–2 h)

1. **API base URL** (top of file):

   ```js
   const API_BASE = (location.hostname === "localhost" || location.protocol === "capacitor:")
     ? "https://<your-app>.fly.dev"   // bundled APK → remote API
     : "";                              // served by the same FastAPI → relative
   ```

   Then the 3 call sites: `fetch(API_BASE + "/api/check", …)`,
   `fetch(API_BASE + "/api/captcha")`, `fetch(API_BASE + "/api/health")`.
   The web deployment keeps working unchanged (same-origin, `API_BASE === ""`).

2. **Native share bridge for the verdict PNG** — Web Share file-sharing is flaky in
   WebViews; Capacitor injects `window.Capacitor` + `Capacitor.Plugins` into the
   WebView automatically (no npm/build step needed — perfect for your vanilla setup):

   ```js
   async function sharePngNative(blob) {
     const { Filesystem, Directory, Share } = Capacitor.Plugins;
     const b64 = await new Promise(res => { const r = new FileReader();
       r.onloadend = () => res(r.result.split(",")[1]); r.readAsDataURL(blob); });
     const f = await Filesystem.writeFile({ path: "niveshrakshak-verdict.png",
       data: b64, directory: Directory.Cache });
     await Share.share({ title: "NiveshRakshak verdict",
       text: shareText(), files: [f.uri] });
   }
   // in sharePng(): if (window.Capacitor?.isNativePlatform?.()) return sharePngNative(blob);
   ```

   Text-only share (`shareWeb`) can keep `navigator.share` — it works in the WebView —
   with the same Capacitor fallback if needed.

3. **Camera**: your existing `<input type="file" accept="image/png,image/jpeg,image/webp">`
   already opens the Android system photo picker **inside the Capacitor WebView** — zero
   changes required for v1. For a direct camera-capture button later, add
   `@capacitor/camera` and call `Capacitor.Plugins.Camera.getPhoto({source: 'camera'})`,
   converting the result to a `File` for the existing `setImage()` path.

Everything else (i18n, styles, fonts, html2canvas, captcha panel, progress theatre)
ships unchanged. ⚠️ Test html2canvas rendering inside the Android WebView early —
it generally works, but the verdict-card PNG is the product's viral artifact.

### 3.4 Capacitor project setup (Day 1–2, ~2 h)

Prereqs: **Node 22+**, **Android Studio 2025.2.1+** (bundles JDK 21 + SDK 36).

```bash
mkdir nr-app && cd nr-app && npm init -y
npm i @capacitor/core@latest-8 @capacitor/cli@latest-8 \
      @capacitor/android@latest-8 @capacitor/share@latest-8 \
      @capacitor/filesystem@latest-8 @capacitor/splash-screen@latest-8 \
      @capacitor/status-bar@latest-8 @capacitor/camera@latest-8
npx cap init "NiveshRakshak" "app.niveshrakshak" --web-dir=www
# copy your frontend in (script it so it's repeatable):
rsync -a --delete web/ www/
npx cap add android
npx @capacitor/assets generate          # icon.svg → adaptive icons + splash
npx cap sync && npx cap open android    # build & run on a device/emulator
```

`capacitor.config.ts` essentials:

```ts
{
  appId: "app.niveshrakshak",
  appName: "NiveshRakshak",
  webDir: "www",
  server: { androidScheme: "https" },        // origin = https://localhost (CORS above)
  android: { allowMixedContent: false },
  plugins: { SplashScreen: { launchShowDuration: 800, backgroundColor: "#F7F3EC" } }
}
```

Device smoke-test checklist:
- [ ] text-only check → verdict card renders (EN + HI toggle)
- [ ] screenshot upload via file input → OCR path works server-side
- [ ] QR photo → decoded, `upi://pay?pa=…` extracted
- [ ] captcha flow: trigger SEBI's gate (several rapid checks) → image renders → solve → verdict
- [ ] verdict PNG → native share sheet → forward into a real WhatsApp chat
- [ ] airplane mode → app shell renders, honest "couldn't verify" error (not a blank screen)
- [ ] rate-limit 429 → toast shows

### 3.5 Build the release artifact

```bash
cd android && ./gradlew bundleRelease   # → app/build/outputs/bundle/release/*.aab
```

Sign with a Play App Signing upload key (Android Studio → Build → Generate Signed
Bundle). AAB (not APK) is mandatory for Play.

---

## 4. Play Store publishing checklist (Route A)

Verified requirements (Oct 2026):

1. **Developer account**: $25 one-time + government-ID identity verification
   (mandatory for all new accounts). (support.google.com/googleplay/android-developer/answer/13629642)
2. **Closed testing gate**: personal accounts created after **Nov 13, 2023** need a
   closed test with **≥12 testers opted-in continuously for ≥14 days** (per app)
   before applying for production access; internal testing does NOT count. Launched
   at 20 testers, reduced to 12 since Dec 2024 (⚠️ date from secondary source).
   → *Start recruiting 12 testers the day you upload; the 14-day clock is your
   critical path.* (support.google.com/googleplay/android-developer/answer/14151465)
3. **Financial features declaration**: EVERY app on EVERY track must file it — even
   with no financial features (you certify "My app doesn't provide any financial
   features"). The policy's scope is *"management or investment of money and
   cryptocurrencies, including personalized advice"*; India-specific RBI verification
   applies **only to personal-loan apps**. A scam-checker that moves no money fits
   none of the buckets. ⚠️ Judgment call: keyword-heavy "investment/UPI/SEBI" metadata
   + choosing the **Finance** category can trigger manual financial review → pick
   **Tools** category, keep the description factual.
   (support.google.com/googleplay/android-developer/answer/9876821, /answer/13849271, /answer/16604194)
4. **Privacy policy URL: mandatory for ALL apps** ("Apps that do not access any
   personal and sensitive user data must still submit a privacy policy") — live on the
   store listing AND inside the app. Free options: a `/privacy` route on your FastAPI
   app or a GitHub Pages file. (support.google.com/googleplay/android-developer/answer/10144311)
5. **Data safety form**: Google counts data as "collected" when it **leaves the
   device** — even if never persisted. Declare: user-pasted messages + uploaded
   screenshots (personal info / app interactions), transmitted over HTTPS to your
   backend, **not retained** (raw text/images processed in memory — true per your
   privacy posture), plus the masked 90-day audit log (masked identifiers only).
   The "ephemeral processing" exemption is easy to get wrong — declaring
   collected-but-not-retained is the safer path. ⚠️ Form details not re-scraped.
   (support.google.com/googleplay/android-developer/answer/10787469)
6. **Naming & trademark**: keep "SEBI" out of the leading name position (e.g.
   **"NiveshRakshak — Investment Scam Checker"**, not "SEBI Checker"); never use
   SEBI's emblem or the NPCI/BHIM UPI logos. Descriptive/nominative use ("checks
   whether a payment destination is SEBI-verified") + your existing footer disclaimer
   ("Not affiliated with, endorsed by, or part of SEBI / NPCI") is standard accepted
   practice. NPCI's UPI trademark rules formally bind **network participants**
   (banks/PSPs/TPAPs), not third-party utilities — no rule found banning the word
   "UPI" in app names; Google's Impersonation policy is the real enforcement vector.
   ⚠️ Your app icon's green triangle deliberately echoes NPCI's validated-handle mark —
   it's your own shield+triangle drawing (fine), but do NOT add the white-thumbs-up
   inside it on the store icon. (UPI Procedural Guidelines; NPCI UPI Consolidated
   Circular v1.0 Sep 18, 2026 §13; bhimupi.org.in brand guidelines)
7. **Target audience**: declare **18+** — not legally forced, but it exempts you from
   the Families policy entirely. (support.google.com/googleplay/android-developer/answer/9867183)
8. **Technical**: AAB format, Play App Signing, **targetSdk 36** (Capacitor 8 default),
   16 KB page-size compliance (Capacitor 8 ✅; Chaquopy 17 ✅ if Route C), content
   rating questionnaire, no-ads declaration (you have none — simplifies review).
9. **Precedent scan**: Sanchar Saathi/Chakshu (Govt. of India, 4.4★, ~190K ratings)
   covers fraud-call/SMS reporting; **no official SEBI consumer checker app exists**
   (SEBI's outreach is the "SEBI Sahi Hai" campaign + the web portal), and no prominent
   independent SEBI-verification app surfaced → **your niche is genuinely open**, with
   the flip side that there's no review precedent for "SEBI-checker" metadata. ⚠️

---

## 5. Route B (TWA) — if you want minimum code changes

Only if you'd rather not touch `app.js` at all:

1. Deploy the whole app (FastAPI already serves `web/`) to Fly.io with a **custom
   domain** (assetlinks + TWA need a stable domain you control; `*.fly.dev` works
   technically but a real domain is safer for review).
2. Add `web/manifest.webmanifest`: `name`/`short_name`, 192px + 512px PNG icons (you
   have `icon.svg` — rasterize), `start_url: "/"`, `display: "standalone"`,
   `theme_color: "#F7F3EC"`, `background_color: "#F7F3EC"`; link it from `index.html`.
3. Add a minimal service worker caching the app shell + `fonts/` + `vendor/` (your
   assets are already self-hosted — SW caching makes it installable-grade).
4. Host `/.well-known/assetlinks.json` with your signing-cert SHA-256 fingerprint
   (`bubblewrap fingerprint generate` helps; FastAPI StaticFiles or a dedicated route).
5. `npm i -g @bubblewrap/cli && bubblewrap init --manifest https://yourdomain/manifest.webmanifest
   && bubblewrap build` → signed AAB → Play Console (same §4 checklist).

Tradeoffs vs Route A: engine is full Chrome (Web Share + html2canvas guaranteed),
zero JS changes; but no bundled offline shell (server down = blank screen), no native
plugin story (weaker Minimum-Functionality position), and PWA plumbing you must
maintain. **If you do Route B, still consider adding the manifest+SW even for Route A**
— it makes the hosted web version installable on iOS/Android browsers for free.

---

## 6. Risk register

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | **siportal WAF blocks datacenter IPs** (unverified both directions; HEAD→505 observed even residential, GET→200) | 🔴 blocks the product | Day-one curl test (§3.1). Fallback chain: (a) DigitalOcean **Bangalore** / Oracle **Mumbai** — India-residential-adjacent IPs; (b) **Cloudflare Tunnel** (free) from a home server → SEBI sees your residential IP exactly as today, at the cost of home uptime; (c) Route C (on-device = user's own mobile IP, most residential-like of all). Registry mirror (`www.sebi.gov.in`, plain Apache) is low-risk either way |
| 2 | Per-IP rate limiter collapses behind a reverse proxy (all users share one bucket) | 🔴 breaks at ~30 users | `--proxy-headers --forwarded-allow-ips='*'` in the uvicorn CMD (§3.1) — verify `request.client.host` shows real IPs |
| 3 | Shared SEBI session serializes concurrent users; captcha state is session-scoped (LIMITATIONS.md §4) | 🟠 degrades at scale | Closed test (12 users) is fine; before public launch, per-user session pool keyed by device id; captcha pass-through UI already built ✅ |
| 4 | Play "Minimum Functionality" rejection of a webview app | 🟠 delays launch | Route A profile: bundled assets + Camera/Share/Splash plugins + offline shell render. Never ship a bare `server.url` shell |
| 5 | html2canvas / Web Share files flaky in WebView | 🟡 breaks the viral loop | Capacitor Filesystem+Share bridge (§3.3.2); test PNG export on a real low-end Android early |
| 6 | SEBI changes the undocumented endpoint (LIMITATIONS.md §2) | 🟡 silent breakage | Contract canary cron + existing honest-UNAVAILABLE states mean it fails loudly, never falsely |
| 7 | 12-tester × 14-day closed test forgotten in timeline | 🟡 delays production by weeks | Recruit testers on upload day (WhatsApp group of friends/family works — they must *opt-in via the Play link* and keep the app installed 14 days) |
| 8 | Data-safety/financial-declaration misfiling | 🟡 review friction | §4.3/§4.5: "no financial features", Tools category, declare message/screenshot transmission with not-retained |
| 9 | Route C only: pydantic-core/rapidfuzz/tesseract/zbarimg blockers | 🟡 (v2) | Pre-built pydantic-core wheel (OpenSquilla precedent); difflib/editdistance or custom rapidfuzz wheel; Tesseract4Android + your existing traineddata; pyzbar (in Chaquopy repo) |
| 10 | Icon/branding reads as NPCI endorsement | 🟢 | Own shield mark, no thumbs-up-in-triangle on the store icon, permanent footer disclaimer (already in `index.html`) |

---

## 7. Cost & timeline summary

| Item | Cost |
|---|---|
| Fly.io Hobby (Mumbai, 512 MB + 1 GB volume) | $5/mo (within included credit) |
| Play Console developer account | $25 one-time |
| Domain (optional — `*.fly.dev` suffices for v1) | ~$10/yr |
| **Year-one total** | **≈ $85–90 (₹7,500)** |

| Phase | Time |
|---|---|
| Day 1 | Dockerfile + Fly deploy + **SEBI go/no-go curl** + backend edits (CORS, proxy-headers) |
| Day 1–2 | Capacitor project, 3 frontend edits, assets/splash, first APK on a real phone |
| Day 3–7 | Smoke-test checklist (§3.4), captcha flow, PNG-share bridge, AAB build |
| Week 2 | Play Console: $25, ID verification, listings, privacy policy, data safety, financial declaration, upload → **closed test with ≥12 testers starts** |
| Weeks 2–4 | 14-day closed-test clock → production application → **live on Play** |
| Later (v2) | Per-user SEBI session pool; contract canary; Route C on-device build if server cost/privacy narrative demands; mr/gu/ta/te/bn i18n packs (single dictionary file each) |

---

## 8. Sources (all fetched/verified 2026-10-01)

- Capacitor: capacitorjs.com/docs/android/setting-target-sdk · /docs/getting-started/environment-setup · /docs/apis · github.com/ionic-team/capacitor/discussions/4080 · github.com/ionic-team/capacitor/issues/7839
- Play policy: support.google.com/googleplay/android-developer/answer/18258653 (Spam & Minimum Functionality) · play.google.com/about/spam-min-functionality/ · answer/9888379 (Device & Network Abuse) · developer.android.com/google/play/requirements/target-sdk (API 35/36 deadlines)
- TWA: github.com/GoogleChromeLabs/bubblewrap/releases (v1.25.0, Jul 31 2026) · developer.chrome.com/docs/android/trusted-web-activity/quick-start · developers.google.com/codelabs/pwa-in-play
- Chaquopy: chaquo.com/chaquopy/news/ (17.0.0) · chaquo.com/chaquopy/doc/current/versions.html · github.com/chaquo/chaquopy/issues/1171 (16 KB) · chaquo.com/pypi-13.1/ (wheel repo) · chaquo.com/chaquopy/doc/current/android.html
- On-device FastAPI precedents: github.com/lzhhhhc/OpenSquilla-mobile · github.com/learningequality/kolibri-installer-android · github.com/snowball1452-lgtm/snowdrift
- BeeWare/Kivy: beeware.org/news/buzz/2026/december-2025-status-update/ · github.com/kivy/python-for-android/issues/3019
- OCR/QR: developers.google.com/ml-kit/vision/text-recognition/v2/android (Devanagari, sizes) · developers.google.com/ml-kit/vision/barcode-scanning · github.com/adaptech-cz/Tesseract4Android (4.9.0) · github.com/zxing-cpp/zxing-cpp · arxiv.org/html/2205.02543v1 (Indic OCR benchmark) · stackoverflow.com/questions/79567195
- Play publishing: answer/13629642 (signup) · answer/14151465 (12 testers × 14 days) · answer/9876821 (Financial Services) · answer/13849271 (financial features declaration) · answer/16604194 (India loan apps) · answer/10144311 (User Data/privacy policy) · answer/9867183 (target audience) · play.google.com/store/apps/details?id=com.dot.app.sancharsaathi
- NPCI/UPI marks: UPI Procedural Guidelines (slbcmadhyapradesh.in mirror) · NPCI UPI Consolidated Circular v1.0 (Sep 18, 2026) §13 · bhimupi.org.in/files/bhim/BHIM-UPI-Guidelines.pdf
- Hosting: docs.fly.io/about/pricing · docs.railway.com/pricing/plans · render.com/docs/free + render.com/articles/platforms-with-a-real-free-tier-for-developers-in-2026 · koyeb.com/pricing · zeabur.com/docs/en-US/pricing/free-plan · northflank.com/pricing · oracle.com/cloud/free · aws.amazon.com/free (Jul-2025 model) · digitalocean.com/pricing/droplets
- SEBI WAF probe: live HEAD/GET against siportal.sebi.gov.in from a residential Indian connection, 2026-10-01 (HEAD→505 BLOCKED, GET→200; www.sebi.gov.in plain Apache)
