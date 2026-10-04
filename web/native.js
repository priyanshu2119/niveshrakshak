/* NiveshRakshak — native integration layer (Capacitor).
 *
 * Loaded AFTER vendor/capacitor-core.js and BEFORE app.js. Everything here
 * degrades to a no-op in a plain browser, so the hosted web version and local
 * ./run.sh keep working untouched.
 *
 * Why this file exists instead of importing the plugins as ES modules:
 * the project deliberately has no bundler (docs/DECISIONS.md §1). Capacitor
 * core ships a standalone IIFE build (vendor/capacitor-core.js) exposing
 * window.capacitorExports.registerPlugin, which resolves plugins through the
 * PluginHeaders that native-bridge.js injects — so no import map and no build
 * step are needed.
 *
 * Three responsibilities:
 *   1. share IN   — receive text/images shared from WhatsApp, Telegram, Chrome,
 *                   Gallery (the manifest intent-filters are already declared)
 *   2. share OUT  — hand the verdict-card PNG to the Android share sheet
 *   3. clipboard  — the fallback for Telegram TEXT messages, which Telegram
 *                   cannot share out (Forward is internal-only)
 */
(function () {
  "use strict";

  var ex = window.capacitorExports;
  var cap = (ex && ex.Capacitor) || window.Capacitor || null;

  var isNative = false;
  try { isNative = !!(cap && cap.isNativePlatform && cap.isNativePlatform()); }
  catch (e) { isNative = false; }

  /* Resolve a native plugin proxy. Returns null on web or if absent, so every
     caller can feature-detect with a simple truthiness check. */
  function plugin(name) {
    if (!isNative) return null;
    try {
      if (ex && ex.registerPlugin) return ex.registerPlugin(name);
    } catch (e) { /* fall through */ }
    try {
      if (window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins[name]) {
        return window.Capacitor.Plugins[name];
      }
    } catch (e) { /* ignore */ }
    return null;
  }

  var ShareTarget = plugin("CapacitorShareTarget");
  var Share       = plugin("Share");
  var Filesystem  = plugin("Filesystem");
  var Clipboard   = plugin("Clipboard");

  /* SystemBars is bundled INSIDE @capacitor/core in Capacitor 8 — there is no
     separate @capacitor/system-bars package — so it comes straight off the
     standalone build's exports rather than through registerPlugin. */
  var SystemBars  = (ex && ex.SystemBars) || plugin("SystemBars");

  /* Status bar fix. Two independent causes were in play:
       (a) capacitor.config.json had splashFullScreen + splashImmersive, and the
           plugin's tearDown() removes the splash view and restores
           setDecorFitsSystemWindows but never calls show(systemBars()) — so
           restoration depended entirely on the splash window going away.
           Both flags are now removed from the config.
       (b) targetSdk 36 means Android 15+ edge-to-edge: the bars are TRANSPARENT
           with content drawn behind them. Default light icons on this app's
           #F7F3EC paper background are close to invisible, which reads as
           "no status bar". Forcing dark icons fixes the contrast.
     🔴 The enum is counter-intuitive and easy to get backwards:
        SystemBarsStyle.Dark  = "DARK"  → LIGHT icons, for a DARK background
        SystemBarsStyle.Light = "LIGHT" → DARK  icons, for a LIGHT background
     This UI has zero prefers-color-scheme CSS (always the light paper theme),
     so "LIGHT" is correct — "DARK" would paint white icons on cream and
     reproduce the exact bug being fixed. The JS setStyle() path does NOT
     uppercase its argument (SystemBars.java:153), so the value must be exact.
     Belt and braces: explicitly show + set style on every launch. */
  function fixSystemBars() {
    if (!isNative || !SystemBars) return;
    try {
      if (SystemBars.show) SystemBars.show().catch(function () {});
      if (SystemBars.setStyle) SystemBars.setStyle({ style: "LIGHT" }).catch(function () {});
    } catch (e) { /* older core without SystemBars — the config change alone suffices */ }
  }
  fixSystemBars();

  /* Directory.Cache === 0 in @capacitor/filesystem's enum. Hardcoded because we
     cannot import the enum without a bundler. 🔴 Cache is the ONLY directory
     Capacitor's template file_paths.xml declares for FileProvider sharing, so
     writing the verdict PNG anywhere else makes getUriForFile throw. */
  var DIR_CACHE = "CACHE";

  // ---------------------------------------------------------------- utilities

  function b64ToBlob(b64, mime) {
    var bin = atob(b64);
    var len = bin.length;
    var bytes = new Uint8Array(len);
    for (var i = 0; i < len; i++) bytes[i] = bin.charCodeAt(i);
    return new Blob([bytes], { type: mime || "application/octet-stream" });
  }

  function blobToB64(blob) {
    return new Promise(function (resolve, reject) {
      var r = new FileReader();
      r.onloadend = function () {
        var s = String(r.result || "");
        var comma = s.indexOf(",");
        // 🔴 Filesystem.writeFile with no `encoding` expects PURE base64 —
        // a data-URI prefix makes the native decoder throw.
        resolve(comma >= 0 ? s.slice(comma + 1) : s);
      };
      r.onerror = reject;
      r.readAsDataURL(blob);
    });
  }

  /* The share-target plugin copies incoming content:// bytes into
     <cacheDir>/shared_files/<name> and hands back that local path (verified in
     CapacitorShareTargetPlugin.java: copyFileToCache + fileData.put("uri", …)).
     That copy is what makes the temporary URI grant safe — the grant does not
     survive process death, the cached file does.

     Filesystem.readFile wants a path RELATIVE to a Directory enum value, so
     strip everything up to and including "/cache/". */
  function toCacheRelative(p) {
    var s = String(p || "");
    var i = s.indexOf("/cache/");
    if (i >= 0) return s.slice(i + "/cache/".length);
    return s.replace(/^file:\/\/+/, "");
  }

  async function readSharedFile(uri, mime, name) {
    var rel = toCacheRelative(uri);
    var b64 = null;

    // 1) preferred: Filesystem, relative to the cache dir
    if (Filesystem) {
      try {
        var r = await Filesystem.readFile({ path: rel, directory: DIR_CACHE });
        b64 = r && r.data;
      } catch (e) { /* try next */ }
      // 1b) some builds want the absolute path
      if (!b64) {
        try {
          var r2 = await Filesystem.readFile({ path: uri });
          b64 = r2 && r2.data;
        } catch (e) { /* try next */ }
      }
    }
    // 2) data: URI handed back directly
    if (!b64 && /^data:/i.test(uri)) {
      var m = uri.match(/^data:([^;,]+)?(;base64)?,(.*)$/i);
      if (m) { b64 = m[3]; mime = m[1] || mime; }
    }
    // 3) last resort: fetch (works for http(s) and, on some WebView configs, file://)
    if (!b64) {
      try {
        var resp = await fetch(uri);
        var blob = await resp.blob();
        return new File([blob], name || "shared-image", { type: blob.type || mime || "image/jpeg" });
      } catch (e) { /* give up */ }
    }
    if (!b64) return null;
    var out = b64ToBlob(b64, mime || "image/jpeg");
    return new File([out], name || "shared-image", { type: mime || out.type || "image/jpeg" });
  }

  // ------------------------------------------------------------ 1. share IN

  var handlers = { onText: null, onImage: null };
  var listenerStarted = false;

  async function startShareListener() {
    if (!ShareTarget || listenerStarted) return;
    listenerStarted = true;
    try {
      await ShareTarget.addListener("shareReceived", async function (ev) {
        // Text and image are handled INDEPENDENTLY: WhatsApp drops EXTRA_TEXT
        // when an image is present, so neither branch may assume the other ran.
        var texts = (ev && ev.texts) || [];
        var joined = texts.join("\n").trim();
        if (ev && ev.title && ev.title.trim() && joined.indexOf(ev.title.trim()) < 0) {
          joined = (ev.title + "\n" + joined).trim();
        }
        if (joined && handlers.onText) handlers.onText(joined);

        var files = (ev && ev.files) || [];
        for (var i = 0; i < files.length; i++) {
          var f = files[i];
          var mt = f.mimeType || "";
          if (mt.indexOf("image/") !== 0) continue;   // only images are useful here
          var file = await readSharedFile(f.uri, mt, f.name);
          if (file && handlers.onImage) { handlers.onImage(file); break; }
        }
      });
    } catch (e) {
      listenerStarted = false;
    }
  }

  // ---------------------------------------------------------- 2. share OUT

  /* The verified recipe (SharePlugin.java):
       canvas blob → PURE base64 → Filesystem.writeFile into Cache with a .png
       name → Share.share({ files: [file:// uri] }).
     🔴 The .png extension is not cosmetic: the plugin derives the MIME type from
     the extension via MimeTypeMap, and with no extension it falls back to the
     wildcard MIME type, which makes WhatsApp treat the card as a document or
     reject it outright.
     The plugin then handles FileProvider content:// conversion,
     FLAG_GRANT_READ_URI_PERMISSION, ClipData (Q+) and createChooser itself.
     Returns true if the native path handled it. */
  async function shareImageBlob(blob, text) {
    if (!isNative || !Share || !Filesystem || !blob) return false;
    try {
      var b64 = await blobToB64(blob);
      var written = await Filesystem.writeFile({
        path: "niveshrakshak-verdict.png",
        data: b64,
        directory: DIR_CACHE,
        recursive: true,
      });
      var uri = written && written.uri;
      if (!uri) return false;
      await Share.share({
        title: "NiveshRakshak",
        // Captions are best-effort: WhatsApp silently dropped EXTRA_TEXT on
        // image shares from Nov 2025 until ~Jan 2026. The card renders its own
        // text, so nothing load-bearing is lost if the caption disappears.
        text: text || "",
        files: [uri],
        dialogTitle: "Share verdict card",
      });
      return true;
    } catch (e) {
      return false;   // caller falls back to Web Share / download
    }
  }

  /* Text-only share (no image). Native sheet is more reliable than
     navigator.share inside a WebView. */
  async function shareTextOnly(text) {
    if (!isNative || !Share || !text) return false;
    try { await Share.share({ title: "NiveshRakshak", text: text }); return true; }
    catch (e) { return false; }
  }

  // --------------------------------------------------------- 3. clipboard

  /* Telegram cannot share a TEXT message out to other apps (its Forward is
     internal-only; long-standing open feature request). Copy-then-paste is the
     only route, which is why this exists — and why RakshaLink ships a
     "Paste & Check". Offered on app resume, never read silently. */
  async function readClipboard() {
    // Native: the Capacitor Clipboard plugin (no permission prompt on Android).
    if (isNative && Clipboard) {
      try {
        var r = await Clipboard.read();
        var s = (r && r.value) ? String(r.value).trim() : "";
        return s || null;
      } catch (e) { /* fall through to the web API */ }
    }
    // Web: async Clipboard API. Needs a user gesture + permission, and is
    // unavailable on insecure origins — hence the try/catch and the null return.
    try {
      if (navigator.clipboard && navigator.clipboard.readText) {
        var t = await navigator.clipboard.readText();
        t = String(t || "").trim();
        return t || null;
      }
    } catch (e) { /* denied or unsupported */ }
    return null;
  }

  // ------------------------------------------------------------------ public

  window.NRNative = {
    isNative: isNative,
    platform: (cap && cap.getPlatform) ? cap.getPlatform() : "web",
    available: {
      shareTarget: !!ShareTarget,
      share: !!Share,
      filesystem: !!Filesystem,
      clipboard: !!Clipboard,
      systemBars: !!SystemBars,
    },
    init: function (h) {
      handlers.onText = (h && h.onText) || null;
      handlers.onImage = (h && h.onImage) || null;
      return startShareListener();
    },
    shareImageBlob: shareImageBlob,
    shareTextOnly: shareTextOnly,
    readClipboard: readClipboard,
  };
})();
