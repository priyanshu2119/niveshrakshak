# On-Device Architecture + Naming — Research Findings

Researched 2026-10-01 via 4 parallel research agents. All external facts source-cited.
⚠️ = unverified / needs empirical test before committing.

Answers two questions:
1. Can the SEBI check be cached at install time? (partially — see §1)
2. Can processing happen on-device so data never leaves the phone? (mostly — see §2)

App name stays **NiveshRakshak** (decided 2026-10-01).

---

## 1. The caching question — you're conflating two different data sources

This is the single most important correction. The pipeline has **two** SEBI sources and
they behave completely differently:

| | SECONDARY: registry mirror | PRIMARY: SEBI Check |
|---|---|---|
| What it is | 23,452 registered entities (name, reg-no, type, validity) | "Does THIS specific UPI handle / account belong to a verified entity?" |
| Source | Daily `.xls` exports, 25 categories, bulk-downloadable | Live POST to `siportal.sebi.gov.in/.../validate.html` |
| Local size | **5.6 MB SQLite** | n/a — it's a query, not a dataset |
| **Can it be bundled offline?** | ✅ **YES — trivially** | ❌ **NO — verified impossible** |
| Refresh cadence | Daily (SEBI republishes) | Real-time per query |

### Why the PRIMARY check can never be pre-cached (verified against primary sources)

- [SEBI PR 31/2025](https://www.sebi.gov.in/media-and-notifications/press-releases/jun-2025/sebi-to-introduce-validated-upi-handles-and-sebi-check-for-secured-payments-by-investors-to-enhance-investor-protection-and-combat-fraud_94539.html):
  `@valid` handles are "**exclusively allocated by NPCI**". SEBI Check is described only as
  verify-by-QR-scan or manual-UPI-ID-entry. No list, no download, no API.
- [Circular SEBI/HO/DEPA-II/.../CIR/2025/86](https://www.sebi.gov.in/legal/circulars/jun-2025/adoption-of-standardised-validated-and-exclusive-upi-ids-for-payment-collection-by-sebi-registered-intermediaries-in-investors_94535.html)
  (full 15-page text read): handles issued by NPCI via **52 Self-Certified Syndicate Banks**
  (Annexure C); usernames generated only through a **utility on SI Portal** (Annexure D).
  Records are created "in **SEBI's system**" on intermediary request, finalized on bank
  confirmation. **No publication or bulk-export provision exists anywhere in the circular.**
- The only API access mentioned (§6.2.1) is for **SCSBs (banks)**, credentials via
  `paymenthandles@sebi.gov.in` — issuance-side validation, not public consumption.
- The distribution model is the *inverse* of bulk download: each intermediary must
  **self-publicize its own handle** (website/SMS/social, Annexure E templates). So the
  handle→entity mapping is scattered across ~1,000+ intermediary websites. No central file.
- Searches across sebi.gov.in, siportal, NPCI, and news: **zero** downloadable handle→entity
  datasets. No official SEBI Check API, no developer program. SEBI Innovation Sandbox
  ([innovation-sandbox.in](https://www.innovation-sandbox.in/)) exists but surfaces no
  handle-verification API ⚠️ (catalog not exhaustively verified).
- NPCI's **Nfinite** sandbox is on the government [API Setu directory](https://directory.apisetu.gov.in/api-collection/npci)
  — no validated-handle verification API found there either.
- Adoption is still expanding (Aug 2026 SEBI communication via NSE Circ 73/2026: all
  investor-facing bank accounts → `@valid`, T+30/T+60 waves), so the mapping changes daily.
  A static bundle would rot even if it existed.

**Consequence:** offline caching of *results* is fine (your existing 6h TTL cache). Offline
caching of the *mapping* is not possible legitimately. The live query is unavoidable.

### But the registry CAN and SHOULD be bundled

Play size limits ([official](https://support.google.com/googleplay/android-developer/answer/9859372),
all = compressed download size):

| Component | Limit |
|---|---|
| Base module (AAB) | **500 MB** |
| Individual feature module | 500 MB |
| Individual asset pack | 1.5 GB |
| All modules + install-time asset packs | 4 GB |
| On-demand + fast-follow asset packs | 30 GB |
| Grand total | 34 GB |

>200 MB only triggers a non-blocking mobile-data warning dialog. (The old "200 MB base
limit" is obsolete; note developer.android.com/guide/playcore/asset-delivery still carries
stale text — cite the support page.)

**Your 5.6 MB DB = ~1% of the base-module budget. No asset packs needed.**

Shipping method ([Room prepopulate](https://developer.android.com/training/data-storage/room/prepopulate)):
`RoomDatabase.Builder.createFromAsset("database/registry.db")` copies from `assets/` on
first open; `createFromFile()` is the hook for downloaded updates.

🔴 **Gotcha that will bite you:** never ship `-wal`/`-shm` files in assets. Your
`data/` currently has `nr.sqlite-wal` at **5.0 MB of uncommitted data** — checkpoint
(`PRAGMA wal_checkpoint(TRUNCATE)`) and delete before packaging, or the bundled DB will
be missing ~half its rows.

⚠️ **16 KB page size** (mandatory since Nov 1, 2025 for apps targeting Android 15+):
framework SQLite/Room is fine; a SQLite *file's* page size (default 4096) is independent
of the OS page size, so your 4 KB-page DB opens fine. The only risk is **bundled native
`.so`s** (SQLCipher, NDK-built sqlite3, capacitor-community/sqlite) — must be built with
16 KB ELF alignment (NDK r28+ / AGP 8.5.1+ handle this).

### Refresh pattern: WorkManager daily full-file swap

For 23.5k rows the full file is 5.6 MB (~2 MB gzipped) — **full-file replacement beats
delta complexity**. Pattern:
[`PeriodicWorkRequest`](https://developer.android.com/develop/background-work/background-tasks/persistent/getting-started)
(min interval 15 min; daily typical) with network constraint → download to temp → verify
(checksum + `PRAGMA integrity_check`) → atomic rename → reopen via `createFromFile`.

Alternatives considered and rejected: delta downloads (marginal at 6 MB), versioned PAD
asset packs (positioned for games, adds Play Core dep, same-day update not guaranteed),
app-update-as-refresh (Play review latency too slow for daily data — fine as a baseline floor).

⚠️ No documented example found of an Indian government app bundling a daily-refreshed
local DB. SEBI's own SAARTHI app added its SEBI Check tab (May 2026) as a **live
server-backed** feature, not bundled data; mAadhaar/DigiLocker/UMANG do live API calls.
Offline-first bundled-data + periodic sync is established in field-data tools (ODK Collect
lineage), not gov consumer apps.

---

## 2. On-device processing — what can move, and the one thing that can't

### ✅ Can move on-device (all verified)

| Pipeline stage | Current | On-device replacement | Notes |
|---|---|---|---|
| OCR (eng+hin) | `tesseract` CLI | **ML Kit Text Recognition v2** | Devanagari **confirmed**. `InputImage.fromBitmap(bitmap, rotation)` — **in-memory, no disk write**. Bundled `com.google.mlkit:text-recognition-devanagari:16.0.1` (~4 MB/script/ABI); unbundled `com.google.android.gms:play-services-mlkit-text-recognition-devanagari:16.0.1` (~260 KB). Min API 21. |
| QR decode | `zbarimg` CLI | **ML Kit Barcode Scanning** | Works on a **static Bitmap**, not just live camera. Bundled `com.google.mlkit:barcode-scanning:17.3.0` (~2.4 MB) = **fully offline**. Restrict to `Barcode.FORMAT_QR_CODE`. |
| Identifier extraction | `extract.py` regex | Kotlin `java.util.regex` | Portable, but see the 3 gotchas below |
| Scam-language patterns | `redflags.py` regex | Kotlin `java.util.regex` | Same gotchas |
| Registry lookup + near-miss | `registry.py` + rapidfuzz | Bundled SQLite + Commons Text / fuzzywuzzy | See §3 |
| Verdict assembly | `verdict.py` | Kotlin | Pure logic, trivially portable |

Source: [ML Kit text recognition v2](https://developers.google.com/ml-kit/vision/text-recognition/v2/android)
(updated 2026-09-28), [ML Kit barcode scanning](https://developers.google.com/ml-kit/vision/barcode-scanning/android)
(updated 2026-09-24).

⚠️ **ML Kit script coverage is Latin, Chinese, Devanagari, Japanese, Korean ONLY** — no
Tamil/Telugu/Kannada/Bengali/Marathi-specific models (Marathi uses Devanagari so it's
covered). Your LIMITATIONS.md §8 already says EN+HI honestly; this doesn't change that.

⚠️ **No Devanagari accuracy benchmark exists** for chat screenshots. Official docs say
non-Latin scripts are "slower" (performance, not accuracy). Known ML Kit issue
[googlesamples/mlkit#561](https://github.com/googlesamples/mlkit/issues/561): OCR engine
unstable in corner cases — few-pixel image shifts change results. **Must test empirically
against your Tesseract baseline on real WhatsApp/Telegram screenshots before committing.**
Community sentiment (r/androiddev): Devanagari "works well".

### 🔴 Three Kotlin/Devanagari regex gotchas that WILL break your port

From the official [Pattern reference](https://developer.android.com/reference/java/util/regex/Pattern):

1. **`\p{IsDevanagari}` (script form, `Is` prefix) is supported only since Android 10
   (API 29).** For older devices use the block form **`\p{InDevanagari}`** (U+0900–U+097F)
   or an explicit `[\u0900-\u097F]` range. ⚠️ `\p{sc=Devanagari}` pre-API-29 behavior unverified.
2. **`CANON_EQ` is explicitly "not supported on Android"** — no canonical-equivalence
   matching in regex. You must normalize manually: `java.text.Normalizer.normalize(text, Form.NFC)`
   on **both** the OCR/pasted input and your pattern literals. Why it matters: nukta
   characters (क़ ख़ ग़ ज़ ड़ ढ़ फ़ य़, U+0958–U+095F) have precomposed NFC forms that
   decompose to base + U+093C in NFD — a literal in one form won't match the other. OCR
   engines and WhatsApp copy-paste can emit either form. (Regular matras ा ि ी ु have no
   precomposed forms and are NFC/NFD-stable.)
3. **`\d` is ASCII-only by default** — Devanagari digits ०–९ (U+0966–U+096F) won't match
   unless you set `UNICODE_CHARACTER_CLASS` or use explicit ranges. Your `_AMOUNT` and
   `_DIGITS` patterns would silently miss Hindi-numeral amounts. `\X` (extended grapheme
   cluster) is supported and useful for conjuncts.

### ❌ The one thing that cannot move on-device

The **live SEBI Check query**. Either:
- **(a) direct from the phone** → 100 phones = 100 independent sessions = 100 captcha
  challenges, no cross-user cache, and SEBI's rate gates punish the distributed model; or
- **(b) proxied through your server** → shared session, shared 6h cache, one SEBI hit per
  viral handle globally.

**(b) is correct.** Your server-side cache isn't legacy baggage — it's the SEBI-politeness
anchor. This is exactly the concern you raised, and the hybrid architecture solves it.

### ✅ The privacy story this unlocks (and Play officially recognizes it)

Official Data Safety guidance ([answer/10787469](https://support.google.com/googleplay/android-developer/answer/10787469)):
> *"User data accessed by your app that is only processed locally on the user's device and
> not sent off device **does not need to be disclosed**"*

So the hybrid gives you a genuinely strong, *true* claim:

> **Your message and screenshot never leave your phone. Only the payment destination you're
> checking is sent — the same UPI ID or account+IFSC string you'd type into SEBI's own website.**

That is a materially better privacy posture than the current "upload your screenshot to our
server", and it's verifiable rather than marketing.

Data that IS sent off-device but processed in-memory per request = **ephemeral processing**:
declared in the Play form, **not shown publicly**. Your FastAPI SEBI check qualifies *only
if* you don't log/store query content — your current design already satisfies this
(raw messages/images never persisted; audit log keeps masked identifiers only).
Privacy-policy URL and User-Data-policy consent remain mandatory regardless.

### APK size impact — comfortable

| Component | Download size |
|---|---|
| ML Kit text-recognition Latin (bundled) | ~4 MB per ABI |
| ML Kit text-recognition Devanagari (bundled) | ~4 MB per ABI |
| ML Kit barcode-scanning (bundled) | ~2.4 MB |
| Registry SQLite asset | 5.6 MB (≤6 MB; exact compressed delta ⚠️ unverified) |
| **Total** | **~16–17 MB per device** |

App Bundle / split APKs deliver **one** ABI per device, so the "per architecture" figures
don't multiply. ~17 MB ≈ 8% of the 200 MB warning threshold — **comfortably under**, and
small enough to be a selling point on low-end Android + slow data.

**Bundled (not unbundled) is the right call** for the "works offline, never leaves the
phone" guarantee. Unbundled would shrink libraries to ~1 MB but requires Play services +
a first-use model download.

---

## 3. Fuzzy matching on-device (replacing rapidfuzz)

**No official rapidfuzz Java/Kotlin port exists.** rapidfuzz is Python/C++; `rapidfuzz-cpp`
could be NDK-compiled but that's DIY with no ready artifact ⚠️.

Realistic architecture: **FTS5-trigram candidate generation → metric re-rank.**

| Option | Verdict |
|---|---|
| **Apache Commons Text** (`org.apache.commons.text.similarity`) | ✅ Best fit. Pure Java, works on Android. `LevenshteinDistance` (with threshold for early-exit), `JaroWinklerSimilarity`, `CosineSimilarity`, `FuzzyScore`, `JaccardSimilarity`, `LongestCommonSubsequence`. Release line 1.14.x/1.15.x. |
| **`me.xdrop:fuzzywuzzy`** | ✅ Java port of FuzzyWuzzy (`ratio`/`partialRatio`/`tokenSortRatio`), Levenshtein-based, pure Java. **Closest semantic match to your `fuzz.token_set_ratio` usage.** |
| **SQLite FTS5 trigram** | ✅ Excellent for candidate shortlisting, **but requires SQLite ≥ 3.34.0** (trigram added 2020-12-01). See version trap below. Caveats: queries need ≥3 chars; `remove_diacritics` is Latin-oriented (won't fold Devanagari matras — normalize to NFC before indexing). |
| RapidFuzz port | ❌ none |
| Tantivy / MeiliSearch | ❌ Tantivy = Rust, no turnkey Android artifact; MeiliSearch = server, not embeddable |
| On-device embeddings/vector (LiteRT, MediaPipe Text Embedder, sqlite-vec) | ⚠️ Possible but overkill for 23.5k short names; adds ~20–100+ MB ⚠️ and complexity |

**Performance:** 23.5k rows is tiny. Brute-force full scan with Commons Text Levenshtein is
likely tens-of-ms on mid-range hardware, but ⚠️ **no published Android benchmark exists** —
the trigram→re-rank pattern guarantees sub-100ms with margin.

### 🔴 SQLite FTS5 version trap

Framework SQLite versions ([official table](https://developer.android.com/reference/android/database/sqlite/package-summary)):

| API | SQLite | | API | SQLite |
|---|---|---|---|---|
| 37 / 36.1 | 3.50 | | 31–33 | **3.32** |
| 35 | 3.44 | | 30 | 3.28 |
| 34 | 3.39→3.42 | | 24–28 | 3.9–3.22 |
| | | | 21 | 3.8 |

- **Plain FTS5:** needs ≥3.9 → framework support from **API 24 (Android 7.0)**. ⚠️ FTS5
  compile-enablement in the framework build is secondary-sourced (SO, Medium) — the official
  page doesn't list compile flags. API 21–23 = FTS4 only.
- **Trigram tokenizer:** needs ≥3.34.0 → **framework SQLite only on API 34+ (Android 14)**.
  Android 13 and below ship 3.32 — **trigram will fail there.**
- **Fix — bundle your own SQLite:**
  - **`com.github.requery:sqlite-android:3.50.4`** — verified its `jni/sqlite/Android.mk`
    builds with `-DSQLITE_ENABLE_FTS5`, `FTS4`, `JSON1`, `RTREE`.
  - **`androidx.sqlite` `BundledSQLiteDriver`** — androidx.sqlite 2.5.0 bundles **SQLite
    3.46.0** (trigram-capable on all devices); works with Room 2.7+ / SQLDelight.
  - SQLCipher: encryption-focused, FTS5 availability ⚠️ unverified per version.

**Simpler alternative:** skip FTS5 entirely. 23.5k normalized names in memory + Commons
Text `LevenshteinDistance` with a threshold is likely fine and removes the whole
native-SQLite dependency. Benchmark first; add trigram only if needed.

---

## 4. Resulting architecture

```
┌─────────────────────── ON DEVICE (never leaves phone) ───────────────────────┐
│                                                                              │
│  Input: share target / text-selection action / paste / gallery image         │
│     │                                                                        │
│     ├─ ML Kit Text Recognition (Latin + Devanagari, in-memory Bitmap)        │
│     ├─ ML Kit Barcode Scanning (QR → upi://pay?pa=…)                         │
│     ├─ Kotlin regex extraction (NFC-normalized; \p{InDevanagari};            │
│     │   UNICODE_CHARACTER_CLASS for Devanagari digits)                       │
│     ├─ Kotlin redflag patterns (EN/HI)                                       │
│     ├─ Bundled registry.db (5.6 MB) + daily WorkManager refresh              │
│     │     exact match + Commons Text/fuzzywuzzy near-miss                    │
│     └─ Kotlin verdict assembly (same strict precedence as verdict.py)        │
│                                                                              │
└──────────────────────────────────┬───────────────────────────────────────────┘
                                   │  ONLY the extracted identifier:
                                   │  "abc.brk@validhdfc"  or  (acc, IFSC)
                                   │  — never the message, never the image
                                   ▼
┌──────────────────────── SERVER (shared, cached) ─────────────────────────────┐
│  POST /api/verify-handle                                                     │
│    → shared SEBI Check session (CA_SESSIONID, WAF-505 retry, circuit breaker)│
│    → captcha pass-through                                                    │
│    → 6h result cache  ← 100 phones checking one viral handle = 1 SEBI hit    │
│    → returns {state, entity{name,regNo,role}, txn, checked_at}               │
└──────────────────────────────────────────────────────────────────────────────┘
```

**What this buys you:**
- Registry lookups, near-miss, OCR, QR, extraction, redflags: **instant + offline + free**
- Server load drops from "full message + image upload" to "one short identifier string"
- Cross-user SEBI cache preserved (the politeness anchor)
- Privacy claim becomes true and Play-recognizable: content never leaves the device
- Server cost drops sharply → cheaper hosting tier viable

**What it costs you:**
- The Python `extract.py` / `redflags.py` / `verdict.py` logic must be **re-implemented in
  Kotlin** (regex ports + the 3 Devanagari gotchas). This is the real work — not the
  Capacitor wrapper. Budget for it and port the existing pytest cases as Kotlin tests so
  behavior stays identical.
- Two implementations of the same rules = drift risk. Mitigation: keep the server path
  working as the reference implementation and add a parity test suite.

**Migration path (lowest risk):**
1. **Phase 1** — Capacitor wrapper, everything server-side (as in `ANDROID-CONVERSION.md`).
   Ship it. 1–2 days.
2. **Phase 2** — bundle `registry.db` on-device, move registry lookup + near-miss local.
   Server now only does SEBI Check. Big win, small change.
3. **Phase 3** — ML Kit OCR/QR on-device, port extraction + redflags to Kotlin.
   Now only the identifier leaves the phone. Privacy claim becomes true.
4. **Phase 4** — port verdict assembly to Kotlin; server reduced to a thin SEBI proxy.

Each phase ships independently and the app keeps working throughout.

---

## 5. Sources

- Play size limits: support.google.com/googleplay/android-developer/answer/9859372 · developer.android.com/guide/playcore/asset-delivery · developer.android.com/guide/app-bundle
- Room prepopulate: developer.android.com/training/data-storage/room/prepopulate
- 16 KB page size: developer.android.com/guide/practices/page-sizes
- WorkManager: developer.android.com/develop/background-work/background-tasks/persistent/getting-started
- SEBI: PR 31/2025 (jun-2025) · Circular CIR/2025/86 (full text via APMI mirror) · NSE Circ 73/2026 · innovation-sandbox.in · directory.apisetu.gov.in/api-collection/npci
- ML Kit: developers.google.com/ml-kit/vision/text-recognition/v2/android (2026-09-28) · developers.google.com/ml-kit/vision/barcode-scanning/android (2026-09-24) · github.com/googlesamples/mlkit/issues/561
- Kotlin regex: developer.android.com/reference/java/util/regex/Pattern
- Fuzzy: commons.apache.org/proper/commons-text/apidocs/org/apache/commons/text/similarity/package-summary.html · github.com/xdrop/fuzzywuzzy
- SQLite: sqlite.org/fts5.html#the_trigram_tokenizer · developer.android.com/reference/android/database/sqlite/package-summary · github.com/requery/sqlite-android · wsoh.released.at/blog/bundledsqlitedriver
- Data safety: support.google.com/googleplay/android-developer/answer/10787469 · answer/10144311
