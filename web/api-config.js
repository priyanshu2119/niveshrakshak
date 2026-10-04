/* API base URL resolution — one place to change, no logic edits needed.
 *
 * Three contexts, one file:
 *   1. Android app (Capacitor, androidScheme:"https") → origin is https://localhost
 *      → must call the REMOTE backend.
 *   2. Hosted web version (served by FastAPI itself)   → same-origin → "".
 *   3. Local dev (./run.sh → http://127.0.0.1:8300)    → same-origin → "".
 *
 * The Capacitor WebView serves the bundled assets from a local origin, so case 1
 * is a genuine cross-origin call and the backend needs CORS for it (already
 * configured via NR_CORS_ORIGINS in docker-compose.yml).
 */
(function () {
  "use strict";

  // 🔴 CURRENT VALUE = a Cloudflare QUICK TUNNEL. It is free, needs no domain and
  // no inbound firewall ports (Oracle's VCN only allows 22 and 20128), but the
  // hostname is REGENERATED EVERY TIME the tunnel restarts. If the app suddenly
  // cannot reach the backend, run on the VPS:
  //     grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" /var/log/nr-tunnel.log | tail -1
  // paste it here, then:  npm run sync && npm run build
  //
  // For a PERMANENT URL, put any domain on Cloudflare's free plan and convert
  // nr-tunnel.service to a named tunnel — see deploy/README.md.
  var REMOTE_API = "https://columns-meets-desired-hub.trycloudflare.com";

  var h = location.hostname;
  var isNativeApp =
    location.protocol === "capacitor:" ||       // iOS
    (h === "localhost" && location.protocol === "https:");  // Android WebView

  window.NR_API_BASE = isNativeApp ? REMOTE_API : "";
  window.NR_IS_NATIVE = isNativeApp;

  /* Link stamped onto every shared verdict, so a forward recruits the next user
     instead of only sending them to SEBI. Point this at the public web app once
     a permanent domain exists (see deploy/README.md); until then the repository
     is the only stable public URL the project has. */
  window.NR_SHARE_URL = "https://github.com/priyanshu2119/niveshrakshak";

  /* Shown in the footer next to the registry-data timestamp so the two are
     never confused again. Keep in step with versionName in
     ../niveshrakshak-app/android/app/build.gradle. */
  window.NR_APP_VERSION = "1.0.0";
})();
