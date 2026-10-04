# Flutter rewrite vs Capacitor wrap — evidence-based decision (Oct 2026)

**Question:** Should we throw away the working vanilla-JS frontend (~420 lines app logic, ~316 lines
bilingual EN/HI i18n, ~388 lines custom "paper-and-stamp" CSS, inline SVG icons, self-hosted variable
fonts Anek Devanagari + IBM Plex, html2canvas export card) and rebuild in Flutter, on the theory that
"Flutter gives web + Android + iOS from the same code"?

**Context constraints:** Python/FastAPI backend must stay on a server (stateful SEBI session, shared
6h cache, 5.6MB SQLite). Target = sideloaded Android APK for 30–40 testers. iOS explicitly out of
scope. Web version already exists and works. NOT going on Google Play.

**Verdict: NO. Wrap with Capacitor. The Flutter reasoning is cargo-cult for this specific situation.**

---

## 1. The core logic error in "Flutter gives web + Android + iOS from one code"

The claim only pays off if you need all three platforms AND don't already have one of them. Here:

- **Web: already exists and works.** Flutter Web would be a *downgrade* of it (see §3). You would
  delete a fast, SEO-able, accessible DOM app and replace it with a 3–5MB+ canvas app.
- **iOS: explicitly out of scope.** The single biggest cross-platform dividend is unused.
- **Android: the only platform Flutter would actually add** — and Capacitor adds it in ~a day by
  reusing 100% of the existing, polished, tested frontend.
- **"One codebase" never materializes anyway.** The backend stays Python/FastAPI regardless
  (stateful government-portal session cannot move to a client). So the real choice is:
  - Capacitor: **one** frontend codebase (existing JS) + Python backend.
  - Flutter: **two** frontend codebases (new Dart app + the vanilla-JS web app you still need for
    the web presence) + Python backend — or one frontend codebase that is worse on web.

The frontend is also the *smallest* part of this system (~1,100 lines total). Rewriting the smallest,
already-finished part in a new language is negative-value work.

## 2. Effort comparison (realistic)

| Work item | Capacitor wrap | Flutter rebuild |
|---|---|---|
| Shell + working APK | Hours–1 day (`docs/ANDROID-CONVERSION.md` already plans Capacitor 8) | Days just for project setup + learning Dart/Flutter if new |
| App logic (~420 lines JS) | Reused as-is | Full rewrite in Dart |
| Bilingual i18n (~316 lines) | Reused as-is | Rewrite into ARB/intl or custom; re-test all Hindi strings |
| "Paper-and-stamp" CSS design (388 lines) | Reused as-is | Reimplement from scratch in widgets/CustomPainter to pixel parity |
| Variable fonts (Anek Devanagari, IBM Plex) | Reused as-is (WebView = Chrome text stack) | **Risk:** Flutter `fontVariations` support has been historically uneven; Devanagari shaping goes through Flutter's own text engine, not the browser's. Exact visual parity unverified — flag as project risk |
| html2canvas share card | Reused as-is | Reimplement via RepaintBoundary (Flutter is arguably *cleaner* here — one genuine Flutter win) |
| Camera/QR | Official Barcode Scanner plugin (ZXING **or MLKIT**) or capawesome ML Kit plugin | mobile_scanner (ML Kit) — parity |
| On-device OCR (Devanagari) | capawesome ML Kit Text Recognition (ML Kit v2 Devanagari already verified in `ONDEVICE-ARCHITECTURE.md`) | google_mlkit_text_recognition — parity |
| Ongoing maintenance | One frontend | Two frontends (web + app) forever, or a worse web |
| **Total to testers** | **~1–3 days** | **~2–6 weeks** to parity (solo dev, part-time, unfamiliar stack), then dual maintenance |

Corroboration: code2native (biased — sells conversions, but the technical claim is standard):
"Converting an existing React/Vue/Angular app to mobile is straightforward. You can reuse 80–90% of
your existing code." https://code2native.com/blog/capacitor-vs-native-app-2026

## 3. Flutter Web reality 2025–2026 (why replacing the existing web app is a downgrade)

**Official guidance first.** Flutter's own docs (updated 2026-07-23) say web support is most valuable
for (a) SPAs and (b) *browser delivery of existing Flutter mobile apps* — and explicitly concede:
"Not every HTML scenario is ideally suited for Flutter at this time. For example, text-rich,
flow-based, static content … benefit from the document-centric model that the web is built around."
They even point DOM-style sites to Jaspr (Dart, not Flutter). https://docs.flutter.dev/platform-integration/web
Translation: Flutter Web is an *appendage to a Flutter mobile app*, not a way to ship a web product
that already exists in HTML.

Concrete criticisms (Suica blog — written by a self-described Flutter *enthusiast* for mobile;
https://suica.dev/en/blogs/flutter-web-is-a-bad-idea):

- **Download size:** skwasm runtime ~1.1MB, CanvasKit ~1.5MB *before your app code*; a simple app
  lands at 3–5MB compressed (corroborated: https://medium.com/@flutter-app/flutter-web-performance-the-brutal-truth-nobodys-talking-about-ecb4bffc9a64).
  React gzips to <50KB; the current vanilla-JS app + fonts is a fraction of a Flutter build.
  Colored emoji require a **24MB** font bundle (flutter/engine#40990).
- **SEO:** canvas rendering = "essentially invisible to search engines"; no SSR/SSG possible because
  there is no HTML. Same conclusion: https://leancode.co/glossary/flutter-and-seo ("The root issue is
  the rendering model, not metadata configuration"). For a public-interest scam-checking tool that
  wants organic discovery, this is disqualifying.
- **Renderer status:** the old HTML renderer is gone; the path is CanvasKit/skwasm (WASM). Official
  docs now lead with WebAssembly. WASM support is still described as having gaps (hot reload bugs,
  `package:html` not WASM-ready, lazy loading/code splitting unsupported in WASM). *(Version-level
  detail — HTML renderer removed in 3.29, WASM default — is from release-note knowledge, not
  re-verified this session; the WASM-centric official docs and Suica's account are consistent with it.)*
- **Text/accessibility/devtools:** browser DevTools "has nothing to do" (no DOM); no render flame
  chart on web; font-weight rendering bugs unfixed on web; text selection and a11y depend on the
  semantics tree over a canvas. Community rule of thumb: "You can immediately recognize a web app
  developed with Flutter just by scrolling. DO NOT DEVELOP websites in Flutter"
  (https://itnext.io/flutter-web-the-good-the-bad-and-the-ugly-7fdaf6f66f00 — excerpt only, not fetched).
- **Rendering perf:** benchmarked *slower than React* in-browser, gap widens with complex styling;
  everything runs on one isolate vs the browser's multi-threaded compositing ("CSS is god").

**Conclusion for Q2:** Flutter Web is not a good way to ship a web app that already exists in
vanilla JS. It is a good way to ship a *Flutter mobile app* to browsers as a secondary target.

## 4. Does "one codebase" hold up in practice? (Q3)

- Kitrum (Nov 2025, https://kitrum.com/blog/why-flutter-isnt-ideal-for-cross-platform-development/):
  "'One Codebase' isn't always that simple… you'll often still need platform-specific tweaks";
  "bloated app size across all platforms"; "web and desktop versions still feel like a work in
  progress"; canvas approach "can lead to issues with SEO, accessibility, and performance."
- Suica (a Flutter mobile advocate): every mobile advantage he lists *fails to translate to web* —
  widgets are mobile-first, responsive design is fought with MediaQuery instead of CSS, ecosystem is
  mobile-focused (550K pub.dev packages vs 3.1M npm; data-grid/form/chart components weak).
- The honest pattern across sources: Flutter's promise holds **for mobile↔mobile** (Android+iOS from
  one Dart codebase — genuinely true, genuinely strong). It does **not** hold for "mobile + a real
  web presence," which is exactly this project's shape.

## 5. Capacitor status 2025–2026 (Q4)

- Official positioning, current site: "**Drop Capacitor into any existing web app**" —
  `npm install @capacitor/cli @capacitor/core` + `npx cap init` (https://capacitorjs.com/). The npm
  step builds the *native shell*; your web assets are copied from a `webDir` folder. **No bundler or
  framework required** — vanilla JS with no build step is a first-class supported case:
  - Ionic's own VanillaJS + Capacitor camera tutorial: https://ionic.io/blog/create-powerful-native-mobile-apps-with-capacitor-vanillajs
  - Developer account of shipping a vanilla-JS Capacitor app to **both** Play Store and App Store:
    https://medium.com/@stepan.rumyantsev/can-i-use-ionic-and-capacitor-with-vanilla-javascript-without-a-framework-like-react-or-angular-8f4e3f146278
    (⚠️ 2021 — dated, but corroborated by the current Ionic blog and docs above)
  - Ionic forum confirmations: https://forum.ionicframework.com/t/build-app-without-framework-possible/195255
- **What you gain:** official/maintained plugins for Camera, Share sheet, Filesystem, Preferences,
  Push, Haptics; **official Barcode Scanner plugin with a choice of ZXING or MLKIT engines**
  (https://capacitorjs.com/docs/apis/barcode-scanner); capawesome's ML Kit plugin family incl.
  barcode scanning + text recognition (https://github.com/capawesome-team/capacitor-mlkit); optional
  OTA live-update services (Capgo/Capawesome Cloud) — useful for pushing fixes to 30–40 sideloaded
  testers without re-sending APKs.
- **What you lose vs Flutter:** UI runs in a WebView (system Chrome on Android) — no custom render
  engine, so heavy 60fps custom animation/complex gesture work is harder; no single Dart codebase if
  iOS ever comes back into scope (though Capacitor does iOS too, via WKWebView); plugin quality
  varies between official and community. **None of these losses bite this app**: it is a
  form → scan → verdict → share-card flow with typography-driven design, which is exactly what
  WebViews do well.

## 6. Sideloaded distribution: does the choice matter for compliance? (Q5)

**No. Zero.** Store-review risk is the only place where "wrapper apps" face policy pressure, and it
doesn't exist here:

- Google Play rejections of WebView apps (Device & Network Abuse / "broken functionality" / minimum
  functionality) apply **only to Play submission** (https://nativeappai.com/webview-app-rejected-by-google-play,
  https://code2native.com/blog/webview-app-google-play-approval-2026 — both biased vendors, but the
  policy mechanics are accurate and match Play's published policies).
- Apple Guideline 4.2 (minimum functionality) kills WebView wrappers — **iOS is out of scope**
  (https://www.mobiloud.com/blog/app-store-review-guidelines-webview-wrapper).
- A sideloaded APK faces **no review at all**: users enable "Install unknown apps," that's it. There
  is no policy surface where Flutter beats a WebView wrapper. Any Flutter advantage framed as
  "safer for store review" is worth exactly nothing to this rollout.
- Bonus: even the *future* Play door isn't closed — the same sources document WebView apps passing
  Play when they add native value (camera scanning, share target, offline mode), which this app has.

## 7. Where Flutter is genuinely right — and wrong — for THIS app (Q6)

**Genuinely right (be fair):**

- **Image export:** Flutter's RepaintBoundary → PNG is more reliable than html2canvas (which has
  known font/SVG rendering quirks). Small real win; not worth a rewrite.
- **If iOS returns to scope:** one Dart codebase for Android+iOS is Flutter's true strength and beats
  maintaining a Capacitor iOS shell separately — *if* the app becomes animation/gesture-heavy.
- **If the product pivots app-first** (kills the web version, adds heavy on-device ML pipelines,
  complex offline sync): Flutter's mobile ecosystem (mobile_scanner, google_mlkit_*, drift/isar) is
  more mature than WebView plugins.
- **Greenfield with no existing code:** starting fresh, Flutter for mobile-only is a defensible pick.

**Wrong here — the assumption fails because:**

1. There is nothing greenfield: the frontend is *finished, polished, and bilingual*. Flutter's value
   proposition is building UIs cheaply; you already paid that cost.
2. The web app must stay a *real* web app (SEO, shareability, zero-install virality for a
   scam-checking tool). Flutter Web actively destroys all three.
3. iOS is out of scope → the cross-platform dividend is ~0.
4. Backend stays Python → "one codebase" is unreachable in every scenario.
5. Camera/QR/OCR/share — the native features that actually matter — have **first-class Capacitor
   plugins using the same ML Kit underneath** that Flutter would use. Feature parity is real here
   (verified: official barcode plugin with MLKIT option; capawesome ML Kit text recognition;
   Devanagari ML Kit support already confirmed in `ONDEVICE-ARCHITECTURE.md`).
6. Sideloaded distribution → no store-review risk to hedge against.
7. 30–40 testers want the app *now*. Days (Capacitor) vs weeks (Flutter parity + Dart learning
   curve) is the whole ballgame.

## 8. Recommendation

**Wrap the existing frontend with Capacitor (the route already documented in
`docs/ANDROID-CONVERSION.md`).** Ship the APK to testers this week. Add the official Barcode
Scanner plugin (MLKIT engine) and Share plugin as the only native integrations needed. Keep the
FastAPI server exactly as-is. Revisit Flutter **only if** (a) iOS enters scope AND (b) the app
evolves into an animation-heavy, app-first product — and even then, keep the vanilla-JS web app
for the web presence rather than adopting Flutter Web.

## 9. Sources

Primary / official:
- Flutter web support (official, updated 2026-07-23): https://docs.flutter.dev/platform-integration/web
- Capacitor (official): https://capacitorjs.com/
- Capacitor Barcode Scanner plugin (official, ZXING/MLKIT): https://capacitorjs.com/docs/apis/barcode-scanner
- capawesome ML Kit plugins for Capacitor: https://github.com/capawesome-team/capacitor-mlkit
- Ionic VanillaJS + Capacitor tutorial (official blog): https://ionic.io/blog/create-powerful-native-mobile-apps-with-capacitor-vanillajs

Developer accounts / analysis:
- "Flutter Web Is a Bad Idea" (Flutter mobile enthusiast; benchmarks, sizes, SEO, WASM): https://suica.dev/en/blogs/flutter-web-is-a-bad-idea
- "Why Flutter Isn't Ideal for Cross-Platform Development" (Kitrum, Nov 2025): https://kitrum.com/blog/why-flutter-isnt-ideal-for-cross-platform-development/
- Vanilla-JS Capacitor app shipped to both stores (2021, dated): https://medium.com/@stepan.rumyantsev/can-i-use-ionic-and-capacitor-with-vanilla-javascript-without-a-framework-like-react-or-angular-8f4e3f146278
- Flutter Web perf/"brutal truth" (excerpt only): https://medium.com/@flutter-app/flutter-web-performance-the-brutal-truth-nobodys-talking-about-ecb4bffc9a64
- Flutter & SEO (LeanCode): https://leancode.co/glossary/flutter-and-seo
- "Flutter Web: good, bad, ugly" (excerpt only): https://itnext.io/flutter-web-the-good-the-bad-and-the-ugly-7fdaf6f66f00

Store-policy context (moot for sideloading; vendors biased):
- https://nativeappai.com/webview-app-rejected-by-google-play
- https://code2native.com/blog/webview-app-google-play-approval-2026
- https://www.mobiloud.com/blog/app-store-review-guidelines-webview-wrapper
- https://code2native.com/blog/capacitor-vs-native-app-2026
- https://nextnative.dev/comparisons/capacitor-vs-flutter

**Unverified / flagged:**
- Reddit r/FlutterDev thread "I built a web app with Flutter and this is how I feel about it"
  (https://www.reddit.com/r/FlutterDev/comments/1gfhyfn/) — bot-walled, could not fetch; cited only
  as an existence signal, not evidence.
- Exact Flutter version that removed the HTML renderer / made WASM default — from release-note
  knowledge; direction confirmed by official WASM-centric docs.
- Flutter variable-font (Anek Devanagari axes) + Devanagari shaping parity with browser rendering —
  flagged as risk from known `fontVariations` limitations; not verified against the issue tracker
  this session.
- capawesome Text Recognition plugin's exposed script list (Devanagari) — underlying ML Kit v2
  Devanagari support is verified (repo research); plugin-level exposure to be confirmed at
  implementation time.
