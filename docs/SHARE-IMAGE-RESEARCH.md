# Sharing a Generated PNG out of a Capacitor 8 Android App — Research Report

Researched 2026-10-02 via live web (firecrawl/tinyfish) + GitHub API + npm registry + plugin source code.
Complements `docs/CAPACITOR-PLUGIN-RESEARCH.md` section (b). All plugin versions verified against npm `latest` on 2026-10-02.

## TL;DR — The Reliable Recipe (verified against plugin source)

1. Canvas → blob → **base64 string with the `data:image/png;base64,` prefix STRIPPED**.
2. `Filesystem.writeFile({ path: 'result-card.png', data: b64, directory: Directory.Cache, recursive: true })` → returns `{ uri }` (a `file://` URI).
3. `Share.share({ files: [uri], text: 'caption…', dialogTitle: 'Share' })`.
4. The plugin (verified in `SharePlugin.java` source) then:
   - derives MIME from the **file extension** via `MimeTypeMap` (so the filename MUST end in `.png`),
   - converts to a FileProvider `content://` URI (authority `<appId>.fileprovider`),
   - sets `EXTRA_STREAM` + `FLAG_GRANT_READ_URI_PERMISSION` + `ClipData` (Android 10+),
   - wraps in `Intent.createChooser`.

Hard requirements:
- **Filename must have the `.png` extension.** No extension → MIME falls back to `*/*` → WhatsApp treats it as a document or rejects it. (Source-verified: `getMimeType()` in SharePlugin.java.)
- **`Directory.Cache` is the only directory shareable out-of-the-box.** Share docs: "By default, Capacitor apps only allow to share files from caches folder." The Capacitor android-template `file_paths.xml` declares only `<cache-path path="."/>` and `<external-path path="."/>`. Anything else (Data/files dir, External files dir) needs editing `android/app/src/main/res/xml/file_paths.xml` first, or `FileProvider.getUriForFile` throws `IllegalArgumentException`.
- **Pass the `file://` URI** returned by `writeFile` — the plugin rejects anything else ("only file urls are supported"). Do not pass `content://` URIs or bare paths.
- Single file → `ACTION_SEND`; multiple → `ACTION_SEND_MULTIPLE` with type forced to `*/*` (avoid multi-file for WhatsApp).

## Q1 — Android native mechanics (2026)

- **Why `file://` is banned:** since Android 7.0 (API 24), exposing a `file://` URI outside your app throws `FileUriExposedException` (StrictMode VmPolicy). Canonical citation: https://developer.android.com/about/versions/nougat/android-7.0-changes (not re-scraped this session; long-standing documented behavior).
- **FileProvider** is the sanctioned replacement: "FileProvider is a special subclass of `ContentProvider` that facilitates secure sharing of files associated with an app by creating a `content://` Uri for a file instead of a `file:///` Uri. A content URI allows you to grant read and write access using temporary access permissions." — https://developer.android.com/reference/androidx/core/content/FileProvider (scraped, verbatim).
- **Setup** (same page): `<provider android:name="androidx.core.content.FileProvider" android:authorities="com.mydomain.fileprovider" android:exported="false" android:grantUriPermissions="true">` + `meta-data android.support.FILE_PROVIDER_PATHS` → `res/xml/file_paths.xml` with `<files-path>`, `<cache-path>`, `<external-path>`, `<external-files-path>`, `<external-cache-path>`, `<external-media-path>` entries. Capacitor's `android-template/app/src/main/AndroidManifest.xml` already declares exactly this with authority `${applicationId}.fileprovider` (verified in repo).
- **Granting access:** put the content URI in `EXTRA_STREAM`, call `intent.setFlags(FLAG_GRANT_READ_URI_PERMISSION)`, and (per FileProvider docs, for API 16–22 compat, and modern best practice) also `setClipData()`. Then `startActivity(Intent.createChooser(sendIntent, title))`.
- **Intent shape:** `ACTION_SEND` + `EXTRA_STREAM` (content URI) + `setType("image/png")` — https://developer.android.com/develop/ui/compose/sharing/send and https://developer.android.com/training/sharing/send.
- **`OpenableColumns`:** FileProvider's `query()` automatically reports `DISPLAY_NAME` (= filename) and `SIZE` (verbatim from reference docs). Receiving apps (WhatsApp included) use DISPLAY_NAME for type detection → another reason the filename must carry `.png`. No extra work needed.

## Q2 — Which directory for the shared image

**Answer: app cache dir (`Directory.Cache`).**
- Works with zero config: `<cache-path path="."/>` is in the Capacitor template's `file_paths.xml`; Share plugin docs confirm caches is the default shareable location.
- No storage permissions needed (app-private).
- OS can evict cache under storage pressure — irrelevant here since the file only needs to survive the share flow; write it fresh each time.
- Internal files dir (`Directory.Data`) and external files dir (`Directory.External`) work equally well *for the receiving app* (WhatsApp/Telegram read through the `content://` URI + granted permission; they never touch your filesystem directly) — **but** Capacitor's default `file_paths.xml` does NOT declare `<files-path>`/`<external-files-path>`, so `getUriForFile` will throw unless you add those entries.
- Historical WhatsApp/Telegram read failures were about **URI scheme** (`file://`, `android.resource://`), never about which private directory backs the FileProvider.
- `<external-path path="."/>` (external storage root) is in the template for legacy reasons; writing there is blocked by scoped storage on Android 10+ anyway.

## Q3 — WhatsApp "unsupported / not detected" failures: root causes & 2024–2026 status

Verified root causes (each with source):

| # | Root cause | Symptom | Fix | Source |
|---|-----------|---------|-----|--------|
| 1 | `file://` URI in `EXTRA_STREAM` | `FileUriExposedException` crash (targetSdk ≥ 24) or WhatsApp silently fails | FileProvider `content://` + `FLAG_GRANT_READ_URI_PERMISSION` | developer.android.com FileProvider ref |
| 2 | **Null/wrong intent MIME type** | WhatsApp: "Can't send empty message"; email works fine | Always `setType("image/png")` — this was exactly Capacitor issue #196 (Jan 2021), **fixed by PR #816 "Fixing null intent type"** | github.com/ionic-team/capacitor-plugins/issues/196 |
| 3 | **No file extension** → MIME `*/*` | WhatsApp shows document picker / "unsupported format" | Name the file `*.png` (plugin derives MIME from extension via MimeTypeMap) | SharePlugin.java source (verified) |
| 4 | Exotic URIs (`android.resource://`, asset URIs) | "The file format is not supported" | Copy to a real file, share via FileProvider or MediaStore content URI | stackoverflow.com/questions/37833459 (canonical, 18k views) |
| 5 | Missing URI grant / ClipData | Receiver gets SecurityException or blank preview | `FLAG_GRANT_READ_URI_PERMISSION` (+ ClipData on modern Android) | FileProvider ref docs; SharePlugin.java sets both |
| 6 | Missing DISPLAY_NAME | Receiver can't infer type/name | Automatic with FileProvider (reports `OpenableColumns.DISPLAY_NAME` = filename) — just keep the `.png` extension | FileProvider ref docs (verbatim) |

**2024 status:** issue #2034 (Feb 2024, @capacitor/share 5.0.0, "Issue while sharing an image via Whatsapp") — OutSystems maintainer comment 2024-04-22: *"This is a limitation of WhatsApp. You can share both text and images but not simultaneously."* Locked as stale May 2024. Image-only sharing itself was NOT broken — the complaint was the dropped caption.

**Nov 2025 regression → Jan 2026 fix (important, recent):** A WhatsApp Android update (~Nov 2025) started **dropping `EXTRA_TEXT` entirely** on `image/*` shares — caption never appeared. Community findings (r/androiddev thread, 2025-11-23): the text WAS delivered (visible if the user tapped "edit" on the preview); shares via Direct Share/"recent contacts" kept the caption; only the full contact-picker flow dropped it; Telegram unaffected. **Fixed by WhatsApp + WhatsApp Business updates ~Jan 2026** (multiple confirmations in-thread: "WhatsApp and WhatsApp Business latest version have fixed this issue"). As of Oct 2026 image+caption sharing works again — but treat captions as best-effort and render critical text INTO the image.

**Bottom line:** with current `@capacitor/share` 8.0.2 + a `.png` file in `Directory.Cache`, there is no known open bug preventing WhatsApp/Telegram from receiving the image. All plugin-side causes were fixed years ago (#196/PR #816); the 2024–2026 issues were WhatsApp-side caption handling.

## Q4 — Capacitor plugins (versions verified on npm 2026-10-02)

**`@capacitor/share` 8.0.2** (repo: ionic-team/capacitor-plugins):
- `files: string[]` — "Array of file:// URLs of the files to be shared. Only supported on iOS and Android." Since 4.1.0. Single file also OK via `url: 'file://…'`.
- Yes, the file **must be written to disk first** (plugin only accepts `file:` URLs; it does the FileProvider conversion internally — you never handle `content://` yourself).
- Best `Directory`: **Cache** (only default-shareable one; see Q2).
- Wants the **full `file://` URI** (what `writeFile` returns as `uri`), not a bare path, not a content URI.
- `text` + `files` together: plugin puts `EXTRA_TEXT` and `EXTRA_STREAM` on the same intent and overrides the type to the image MIME (source-verified) — i.e., the standard caption pattern.
- Docs: https://capacitorjs.com/docs/apis/share (v8). Android note quoted above re: caches folder + `file_paths.xml`.

**`@capacitor/filesystem` 8.1.3** (moved to its own repo: ionic-team/capacitor-filesystem; Android native side now delegates to the `@capacitor/synapse` library `io.ionic.libs.ionfilesystemlib`):
- `writeFile({ path, data, directory, encoding?, recursive? })`; `data: string | Blob` — **Blob only on Web**; native wants a base64 string.
- Docs (updated 2026-01-27 via PR #65 "docs: Better document writing binary data", merged): *"If not provided [encoding], binary data will be written. For this, you must provide data as base64 encoded… If you do not provide encoding and use non-base64 data, an error will be thrown."*
- **Data-URI prefix:** the Web implementation strips it for you (source-verified in `src/web.ts`: `data = data.indexOf(',') >= 0 ? data.split(',')[1] : data;` then base64-validates). The Android synapse decoder is a compiled lib — prefix tolerance **UNVERIFIED**. → **Strip the prefix yourself** (`dataUrl.split(',')[1]`); that is the documented contract and is safe on every platform/version.
- `writeFile` resolves `{ uri }` — the `file://` URI to hand to Share.
- Docs: https://capacitorjs.com/docs/apis/filesystem (v8).

**Known-issue trail (image → WhatsApp):** #196 (2021, fixed PR #816) · #530 (PDF→WhatsApp passes text only) · #1353 (2022) · #2034 (2024, caption limitation, locked) · Ionic forum t/212601 ("known issue, some apps don't detect the images the way Capacitor share plugin shares them") · SO 68411694. All pre-date Capacitor 5; none reflects a current image-delivery bug. Do one real-device WhatsApp+Telegram test early regardless.

## Q5 — Text + image in one intent

- **Yes, it's the standard pattern:** `ACTION_SEND`, `type="image/png"`, `EXTRA_STREAM` (image) + `EXTRA_TEXT` (caption). `@capacitor/share` does exactly this when you pass `text` + `files`.
- **Telegram:** honors both (image + caption) — consistently, including through the Nov 2025 WhatsApp regression.
- **WhatsApp:** honors both as of the ~Jan 2026 fix (see Q3 timeline). Historically flaky: 2024 maintainer-acknowledged limitation, Nov 2025 regression, now fixed. Design assumption: caption may vanish on some WhatsApp versions → put essential info in the image, caption as bonus.
- **Instagram:** accepts `image/*` via `ACTION_SEND` but **ignores `EXTRA_TEXT`** (long-standing community knowledge, e.g. SO 63901007 — partially verified via search excerpts only).
- Email/Gmail: `EXTRA_TEXT` becomes the body, `EXTRA_STREAM` the attachment, `EXTRA_SUBJECT` (plugin maps `title` to it) the subject.

## Q6 — Text vs image reliability; size/format limits

- **Plain text (`text/plain`) is the most universally reliable** share payload — every share target handles it. But for a visual result card, image share + text caption + (optionally) a text-only fallback button is the right UX.
- **No practical size limit at the share-sheet level:** the intent carries only the URI; the receiving app streams the file. Multi-MB PNGs are fine.
- **WhatsApp limits (official FAQ, fetched 2026-10-02):** documents up to **2 GB**; up to **100 photos/videos per send**. https://faq.whatsapp.com/453914586839706
- **WhatsApp recompression:** images shared as *photos* are recompressed (standard quality by default; HD is a user opt-in per-send). A PNG sent as a photo is converted/recompressed (lossy, transparency flattened). Pixel-perfect delivery requires the recipient to choose "Document" in WhatsApp's own picker — you cannot force that from `ACTION_SEND` with `image/png`. (Recompression behavior: WhatsApp FAQ HD-quality docs + 2026 community guides, e.g. chatarmin.com WhatsApp Image Size Guide 2026 — the 2 GB/100-item numbers are FAQ-verified; the PNG→recompress detail is community-sourced, flag as high-confidence-but-not-officially-documented.)
- For a typical result card (< 1–2 MB PNG), WhatsApp recompression is visually acceptable; rejection risk ≈ none.
- Telegram: sends images compressed by default too, but offers "send as file" in its own UI; 2 GB per-file limit for documents (4 GB for Premium). [Community knowledge — not re-verified this session.]

## Source URLs

- https://developer.android.com/reference/androidx/core/content/FileProvider (scraped; quotes verbatim)
- https://developer.android.com/develop/ui/compose/sharing/send (search excerpt; ACTION_SEND/EXTRA_STREAM/createChooser)
- https://developer.android.com/training/sharing/send
- https://developer.android.com/about/versions/nougat/android-7.0-changes (file:// ban / FileUriExposedException — cited, not scraped)
- https://capacitorjs.com/docs/apis/share (v8, scraped)
- https://capacitorjs.com/docs/apis/filesystem (v8, scraped)
- https://github.com/ionic-team/capacitor-plugins/blob/main/share/android/src/main/java/com/capacitorjs/plugins/share/SharePlugin.java (scraped raw — MIME-from-extension, FileProvider authority, flags, ClipData all verified here)
- https://github.com/ionic-team/capacitor-plugins/issues/196 (scraped; fixed by PR #816)
- https://github.com/ionic-team/capacitor-plugins/issues/2034 (comments via API; 2024 WhatsApp caption limitation)
- https://github.com/ionic-team/capacitor-filesystem (repo of record for Filesystem 8.x; PR #65 docs update merged 2026-01-27; src/web.ts prefix-stripping verified)
- https://stackoverflow.com/questions/37833459/android-share-image-intent-whatsapp-the-file-format-is-not-supported (scraped; android.resource:// root cause + MediaStore/FileProvider fix, working on Android 11)
- https://www.reddit.com/r/androiddev/comments/1p490o4/share_image_text_on_whatsapp_it_shares_only_the/ (fetched via tinyfish; Nov 2025 regression + Jan 2026 fix timeline)
- https://faq.whatsapp.com/453914586839706 (fetched via tinyfish; 2 GB documents, 100 media per send)
- https://forum.ionicframework.com/t/ionic-capacitor-share-plugin-not-sharing-image-with-whatsapp/212601
- https://stackoverflow.com/questions/68411694 (workaround thread referencing #196)
- npm registry: @capacitor/share 8.0.2, @capacitor/filesystem 8.1.3 (deps: @capacitor/synapse ^1.0.4) — verified 2026-10-02

## Unverified / flagged items

1. Android synapse decoder tolerance for un-stripped `data:` prefix (web impl strips; native is a compiled lib) → strip it yourself.
2. Instagram ignoring `EXTRA_TEXT` — community consensus, not officially documented.
3. PNG→JPEG recompression by WhatsApp on photo shares — community/FAQ-adjacent, not a single official statement.
4. The Nougat `FileUriExposedException` page was cited from established knowledge, not scraped this session.
5. Real-device WhatsApp/Telegram test on Capacitor 8.0.2 still recommended before shipping (all evidence says it works; no substitute for a device test).
