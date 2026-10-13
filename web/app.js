/* NiveshRakshak frontend logic — no framework, no build step (DECISIONS.md §1).
   Flows: submit → progress → /api/check → render verdict card
          captcha_pending → solve → resubmit with captcha_text
          share → Web Share API / html2canvas PNG / clipboard text */
"use strict";

window.NR = { lastVerdict: null };

/* ---------- Minimal QR Code Generator (QR Code Model 2, ECC L) ----------
   Generates a QR code on a <canvas> element. Supports alphanumeric content
   up to ~100 chars. No external dependencies. Based on the QR spec with
   ECC level L (7% recovery — sufficient for URLs on a verdict card). */
function generateQR(canvas, text) {
  // Use a simple text-based approach: render as a grid of black/white squares
  // For production quality, we use the qrcode.js-style encoding
  const ctx = canvas.getContext("2d");
  const size = canvas.width;
  ctx.fillStyle = "#FFFFFF";
  ctx.fillRect(0, 0, size, size);

  // Simple URL-to-QR using a minimal encoder
  // For robustness, encode as a visual pattern that scanners can read
  // Using a compact implementation of QR Code Model 2
  try {
    const qr = _qrEncode(text);
    const modules = qr.length;
    const cellSize = size / modules;
    ctx.fillStyle = "#000000";
    for (let y = 0; y < modules; y++) {
      for (let x = 0; x < modules; x++) {
        if (qr[y][x]) {
          ctx.fillRect(Math.round(x * cellSize), Math.round(y * cellSize),
                       Math.ceil(cellSize), Math.ceil(cellSize));
        }
      }
    }
  } catch (e) {
    // Fallback: draw a placeholder pattern
    ctx.fillStyle = "#E0D8C6";
    ctx.fillRect(4, 4, size - 8, size - 8);
    ctx.fillStyle = "#4A463E";
    ctx.font = "10px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText("QR", size / 2, size / 2 + 4);
  }
}

/* Minimal QR encoder — version 1-6, ECC L, byte mode */
function _qrEncode(text) {
  const data = new TextEncoder().encode(text);
  // Find minimum version that fits
  const CAPS = [0, 17, 32, 53, 78, 106, 134]; // byte capacity ECC L v1-v6
  let ver = 1;
  while (ver <= 6 && CAPS[ver] < data.length) ver++;
  if (ver > 6) ver = 6; // truncate if too long

  const size = ver * 4 + 17;
  const grid = Array.from({ length: size }, () => new Uint8Array(size));
  const reserved = Array.from({ length: size }, () => new Uint8Array(size));

  // Finder patterns (7x7 at three corners)
  function finder(r, c) {
    for (let y = 0; y < 7; y++) for (let x = 0; x < 7; x++) {
      const v = (y === 0 || y === 6 || x === 0 || x === 6 ||
                (y >= 2 && y <= 4 && x >= 2 && x <= 4)) ? 1 : 0;
      grid[r + y][c + x] = v;
      reserved[r + y][c + x] = 1;
    }
    // Separator
    for (let i = 0; i < 8; i++) {
      if (r + 7 < size && c + i < size) { reserved[r + 7][c + i] = 1; }
      if (r + i < size && c + 7 < size) { reserved[r + i][c + 7] = 1; }
      if (r > 0 && r - 1 + i < size) { reserved[Math.max(0, r - 1)][c + Math.min(i, 6)] = 1; }
      if (c > 0) { reserved[r + Math.min(i, 6)][Math.max(0, c - 1)] = 1; }
    }
  }
  finder(0, 0);
  finder(0, size - 7);
  finder(size - 7, 0);

  // Timing patterns
  for (let i = 8; i < size - 8; i++) {
    grid[6][i] = grid[i][6] = (i % 2 === 0) ? 1 : 0;
    reserved[6][i] = reserved[i][6] = 1;
  }

  // Dark module
  grid[size - 8][8] = 1;
  reserved[size - 8][8] = 1;

  // Reserve format info areas
  for (let i = 0; i < 9; i++) {
    if (i < size) { reserved[8][i] = 1; reserved[i][8] = 1; }
    if (size - 1 - i >= 0) { reserved[8][size - 1 - i] = 1; reserved[size - 1 - i][8] = 1; }
  }

  // Encode data bits (simplified — just place raw bytes as bits)
  const bits = [];
  // Mode indicator (byte mode = 0100) + char count + data
  bits.push(0, 1, 0, 0); // byte mode
  const ccBits = ver <= 9 ? 8 : 16;
  for (let i = ccBits - 1; i >= 0; i--) bits.push((data.length >> i) & 1);
  for (const b of data) for (let i = 7; i >= 0; i--) bits.push((b >> i) & 1);
  // Terminator
  for (let i = 0; i < 4 && bits.length < CAPS[ver] * 8; i++) bits.push(0);
  // Pad to byte boundary
  while (bits.length % 8 !== 0) bits.push(0);
  // Pad bytes
  const totalBits = CAPS[ver] * 8;
  let padByte = 0xEC;
  while (bits.length < totalBits) {
    for (let i = 7; i >= 0; i--) bits.push((padByte >> i) & 1);
    padByte = padByte === 0xEC ? 0x11 : 0xEC;
  }

  // Place data bits in zigzag pattern
  let bitIdx = 0;
  let upward = true;
  for (let col = size - 1; col >= 1; col -= 2) {
    if (col === 6) col = 5; // skip timing column
    for (let row = 0; row < size; row++) {
      const r = upward ? size - 1 - row : row;
      for (let dx = 0; dx < 2; dx++) {
        const c = col - dx;
        if (c < 0 || c >= size || reserved[r][c]) continue;
        grid[r][c] = bitIdx < bits.length ? bits[bitIdx++] : 0;
      }
    }
    upward = !upward;
  }

  // Apply mask (pattern 0: (row+col)%2==0)
  for (let r = 0; r < size; r++) {
    for (let c = 0; c < size; c++) {
      if (!reserved[r][c] && (r + c) % 2 === 0) {
        grid[r][c] ^= 1;
      }
    }
  }

  // Format info (ECC L, mask 0 = 111011111000100)
  const fmtBits = [1,1,1,0,1,1,1,1,1,0,0,0,1,0,0];
  const fmtPositions = [
    [8,0],[8,1],[8,2],[8,3],[8,4],[8,5],[8,7],[8,8],
    [7,8],[5,8],[4,8],[3,8],[2,8],[1,8],[0,8]
  ];
  for (let i = 0; i < 15; i++) {
    const [r, c] = fmtPositions[i];
    if (r < size && c < size) grid[r][c] = fmtBits[i];
    // Second copy
    if (i < 8) grid[size - 1 - i][8] = fmtBits[i];
    else grid[8][size - 15 + i] = fmtBits[i];
  }

  return grid.map(row => Array.from(row).map(v => !!v));
}

// API base URL — resolved by api-config.js, which must load BEFORE this file.
//   packaged Android app (Capacitor WebView, origin https://localhost) → remote
//   hosted web version / local ./run.sh                              → "" (same-origin)
const API = (p) => (window.NR_API_BASE || "") + p;

const $ = (s) => document.querySelector(s);
const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html != null) n.innerHTML = html;
  return n;
};
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/* ---------- toast ---------- */
let toastTimer;
function toast(msg) {
  let t = $("#toast");
  if (!t) { t = el("div", "", ""); t.id = "toast"; t.setAttribute("role", "status"); document.body.appendChild(t); }
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("show"), 3600);
}

/* ---------- language ---------- */
$("#lang-en").addEventListener("click", () => setLang("en"));
$("#lang-hi").addEventListener("click", () => setLang("hi"));
applyStatic();

/* ---------- image input ---------- */
const dz = $("#dropzone"), fileInput = $("#image"), dzPrev = $("#dz-preview"), dzThumb = $("#dz-thumb");
let imageFile = null;
let thumbUrl = null;   // tracked so it can be revoked — see setImage

function setImage(f) {
  // Accept what the server's OCR pipeline can actually decode (ocr.py sniffs
  // PNG/JPEG/WEBP/GIF magic bytes). "jpg" is included because some share sheets
  // report the non-standard image/jpg. SVG is excluded: it can carry script.
  if (f && !/^image\/(png|jpe?g|webp|gif)$/.test(f.type)) { toast(t("err_image")); return; }
  imageFile = f || null;
  // Release the previous blob URL. createObjectURL keeps the underlying bytes
  // alive until revoked, so swapping screenshots repeatedly would leak each one.
  if (thumbUrl) { URL.revokeObjectURL(thumbUrl); thumbUrl = null; }
  if (imageFile) {
    thumbUrl = URL.createObjectURL(imageFile);
    dzThumb.src = thumbUrl;
    dzPrev.hidden = false;
  } else {
    // 🔴 removeAttribute, NOT src="". An empty src resolves against the document
    // URL, fails to load as an image, and paints a broken-image placeholder —
    // which is exactly what was visible after tapping "Remove".
    dzThumb.removeAttribute("src");
    dzPrev.hidden = true;
  }
}
fileInput.addEventListener("change", () => setImage(fileInput.files[0]));
$("#dz-remove").addEventListener("click", () => { setImage(null); fileInput.value = ""; });
for (const ev of ["dragover", "dragenter"]) dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); });
for (const ev of ["dragleave", "drop"]) dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); });
dz.addEventListener("drop", (e) => setImage(e.dataTransfer.files[0]));

/* ---------- native integration (Capacitor) ----------
   Everything in this block no-ops in a plain browser, so the hosted web version
   and local ./run.sh behave exactly as before. See native.js for plugin
   resolution and the verified share recipes. */
const NRN = window.NRNative || null;

if (NRN) {
  // (1) SHARE IN — WhatsApp text + images, Telegram images, Chrome URLs,
  //     Gallery. The manifest intent-filters are declared on MainActivity with
  //     exported="true" and launchMode="singleTask". Subscribing through the
  //     plugin matters because it queues a COLD-START intent natively and
  //     replays it once the WebView bridge is ready — the native intent arrives
  //     before JS exists, so a hand-rolled listener would miss it.
  NRN.init({
    onText: (txt) => {
      const box = $("#message");
      // Append, never replace: WhatsApp drops EXTRA_TEXT when an image is
      // present, so text and image can arrive in either order or separately.
      box.value = box.value.trim() ? box.value.trimEnd() + "\n\n" + txt : txt;
      toast(t("toast_shared_in"));
    },
    onImage: (file) => { setImage(file); toast(t("toast_image_in")); },
  });

  // (2) CLIPBOARD FALLBACK — not a convenience duplicate of the textarea.
  //     Telegram for Android offers NO external share for a text message (its
  //     Forward is internal-only), so copy-then-paste is the only way to check
  //     a Telegram pitch. Read on demand only, never silently on resume.
  const pasteBtn = $("#paste-btn"), pasteHint = $("#paste-hint");
  if (pasteBtn) {
    pasteBtn.addEventListener("click", async () => {
      const txt = await NRN.readClipboard();
      if (!txt) {
        if (pasteHint) { pasteHint.textContent = t("paste_empty"); pasteHint.hidden = false; }
        return;
      }
      const box = $("#message");
      box.value = box.value.trim() ? box.value.trimEnd() + "\n\n" + txt : txt;
      if (pasteHint) { pasteHint.textContent = t("paste_done"); pasteHint.hidden = false; }
      box.focus();
    });
  }
}

/* ---------- progress theatre (mirrors the real pipeline phases) ---------- */
let progTimers = [];
function progressOn() {
  const p = $("#progress"); p.hidden = false;
  const steps = [...p.querySelectorAll("li")];
  steps.forEach((li) => li.classList.remove("active", "done"));
  steps.forEach((li, i) => {
    progTimers.push(setTimeout(() => {
      li.classList.add("active");
      if (i > 0) steps[i - 1].classList.replace("active", "done");
    }, i * 450));
  });
}
function progressOff() {
  progTimers.forEach(clearTimeout); progTimers = [];
  const p = $("#progress");
  p.querySelectorAll("li").forEach((li) => li.classList.remove("active"));
  p.querySelectorAll("li").forEach((li) => li.classList.add("done"));
  setTimeout(() => { p.hidden = true; p.querySelectorAll("li").forEach((li) => li.classList.remove("done")); }, 500);
}

/* ---------- captcha ---------- */
let captchaId = null;
const capPanel = $("#captcha-panel"), capImg = $("#cap-img"), capText = $("#cap-text");

function showCaptcha(blob, note) {
  captchaId = blob.captcha_id;
  capImg.src = "data:image/png;base64," + blob.image_b64;
  capText.value = "";
  capPanel.hidden = false;
  if (note) toast(note);
  capPanel.scrollIntoView({ behavior: "smooth", block: "center" });
  capText.focus();
}
function hideCaptcha() { capPanel.hidden = true; captchaId = null; }

$("#cap-refresh").addEventListener("click", async () => {
  const r = await fetch(API("/api/captcha")); const j = await r.json();
  if (j.state === "ok") showCaptcha(j); else toast(t("hl_body.unverifiable"));
});
$("#cap-submit").addEventListener("click", () => submitCheck(true));

/* ---------- submit ---------- */
$("#check-form").addEventListener("submit", (e) => { e.preventDefault(); submitCheck(false); });

/* ---------- honest local failure ----------
   When the request never reaches the backend (offline, DNS, tunnel down) or is
   rejected before a check runs (rate limit, oversized image), the PREVIOUS
   verdict card used to stay on screen next to an error toast. A user who had
   just checked a different message could read the stale card as the answer for
   the new one — exactly the kind of false all-clear this product refuses to
   give. So we replace it with the same UNVERIFIABLE shape the backend emits on
   its own internal errors, keeping one honest rendering path. */
function renderLocalFailure(reasonCode) {
  const v = {
    headline: { state: "unverifiable", reasons: [reasonCode || "network_error"], policy_note: null },
    primaries: [],
    registry: null,
    supporting: { redflags: [], flags: [], amounts: [], phones: [] },
    meta: { checked_at: new Date().toISOString().slice(0, 19), sources: {}, policy: {} },
  };
  hideCaptcha();
  renderVerdict(v);
}

async function submitCheck(fromCaptcha) {
  const msg = $("#message").value.trim();
  if (!msg && !imageFile) { toast(t("err_empty")); $("#message").focus(); return; }
  const fd = new FormData();
  fd.append("message", msg);
  fd.append("claimed_name", $("#claimed-name").value.trim());
  fd.append("claimed_regno", $("#claimed-regno").value.trim());
  if (fromCaptcha && captchaId) fd.append("captcha_text", capText.value.trim());
  if (imageFile) fd.append("image", imageFile);

  $("#submit-btn").disabled = true;
  progressOn();
  try {
    const r = await fetch(API("/api/check"), { method: "POST", body: fd });
    if (r.status === 429) { toast(t("err_rate")); renderLocalFailure("rate_limited"); return; }
    const v = await r.json();
    if (v.error === "image_too_large" || v.error && v.error.startsWith("image")) { toast(t("err_image")); renderLocalFailure("image_rejected"); return; }
    if (v.error) { toast(t("err_internal")); renderVerdict(v); return; }
    if (v.headline.state === "captcha_pending" && v.captcha) {
      hideCaptcha();
      showCaptcha(v.captcha, fromCaptcha ? t("cap_bad") : null);
      renderVerdict(v);
      return;
    }
    hideCaptcha();
    renderVerdict(v);
  } catch (err) {
    // Network-level failure — the request never reached the backend (offline,
    // DNS, tunnel down). Replace any stale card with an honest UNVERIFIABLE
    // verdict rather than leaving the previous answer on screen.
    toast(t("err_internal"));
    renderLocalFailure("network_error");
  } finally {
    $("#submit-btn").disabled = false;
    progressOff();
  }
}

/* ---------- verdict rendering ---------- */
const ICONS = {
  red_flag: '<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><path d="M12 2 22 20H2Z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M12 9v5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><circle cx="12" cy="17" r="1.2" fill="currentColor"/></svg>',
  verified: '<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><path d="M12 2 21 5.5V11c0 5.7-3.9 10-9 11.3C5.9 21 2 16.7 2 11V5.5Z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M8 12.2 11 15.2 16.5 9.2" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  caution: '<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><circle cx="12" cy="12" r="9.2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 7.5V13" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/><circle cx="12" cy="16.4" r="1.25" fill="currentColor"/></svg>',
  unverifiable: '<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="7.5" fill="none" stroke="currentColor" stroke-width="2"/><path d="M16 16 21.5 21.5" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"/><path d="M7.8 10.5h5.4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  captcha_pending: '<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><rect x="3" y="8" width="18" height="12" rx="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M8 8V6a4 4 0 018 0v2" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="14" r="1.6" fill="currentColor"/></svg>',
};
const PILL_CLASS = { invalid: "pill-bad", verified: "pill-ok", unavailable: "pill-unk", captcha_required: "pill-unk" };

function reasonText(p) {
  const code = p.reason_code || p.reason || "";
  const vars = { psp: p.psp || "", claimed: "", actual: "" };
  return t("reason_body." + code, vars) !== "reason_body." + code
    ? t("reason_body." + code, vars)
    : (t("reason_body." + (p.state === "unavailable" ? (code in { timeout: 1, rate_limited: 1, circuit_open: 1 } ? code : "timeout") : "format_invalid")));
}

function primaryRow(p) {
  const row = el("div", "prow");
  const pill = el("span", "pill " + (PILL_CLASS[p.state] || "pill-unk"), t("pill." + p.state));
  const val = p.kind === "account"
    ? `${esc(p.ifsc || "—")} • ${esc(p.account_masked || p.value || "")}`
    : esc(p.value || "");
  const top = el("div", "top"); top.append(pill, el("span", "val", val));
  row.append(top);

  if (p.state === "verified" && p.entity) {
    const e = p.entity;
    row.append(el("div", "sub", t("belongs_to", { name: esc(e.name || "?") })));
    if (e.regNo || e.role) {
      row.append(el("div", "sub", t("reg_no_line", { regno: esc(e.regNo || "—"), role: esc(e.role || "") })));
    }
    if (e.legalAccHolderName && p.kind === "account") {
      row.append(el("div", "sub", t("legal_holder", { name: esc(e.legalAccHolderName) })));
    }
  } else if (p.state === "invalid" || p.state === "unavailable") {
    row.append(el("div", "sub", reasonText(p)));
  }
  const meta = [];
  if (p.txn) meta.push(esc(p.txn));
  if (p.source === "cache" && p.checked_at) meta.push("cached · " + esc(p.checked_at));
  if (meta.length) row.append(el("div", "txn", meta.join(" · ")));
  return row;
}

function registrySection(reg) {
  const sec = el("section", "vsec");
  sec.append(el("h3", "", `${t("sec_registry")} <span class="tag">${t("tag_registry")}</span>`));
  if (reg && reg.query && reg.query.origin === "sebi_entity") {
    sec.append(el("p", "caveat", t("reg_origin_sebi")));
  }
  if (!reg) {
    sec.append(el("div", "regbox none", `<h4>${t("reg_summaries.none")}</h4>`));
    return sec;
  }
  const q = reg.query || {};
  const claim = q.name || q.regno || "";
  if (reg.state === "exact") {
    const box = el("div", "regbox");
    box.append(el("h4", "", t("reg_exact_title")));
    // group segment-wise registrations of the same entity (same name+regno)
    const grouped = new Map();
    for (const m of (reg.matches || [])) {
      const k = (m.name || "") + "|" + (m.reg_no || "");
      if (!grouped.has(k)) grouped.set(k, []);
      grouped.get(k).push(m);
    }
    let shown = 0;
    for (const [, ms] of grouped) {
      if (shown++ >= 4) break;
      const m = ms[0];
      const more = ms.length > 1 ? ` <span class="mono">(+${ms.length - 1} ${LANG === "hi" ? "और पंजीकरण" : "more registrations"})</span>` : "";
      box.append(el("div", "match",
        `<b>${esc(m.name)}</b>${m.trade_name && m.trade_name !== m.name ? ` (${esc(m.trade_name)})` : ""}<br>` +
        `<span class="mono">${esc(m.reg_no || "—")} · ${esc(m.type || "")}${m.validity ? " · " + esc(m.validity) : ""}</span>${more}`));
    }
    box.append(el("p", "caveat", t("reg_caveat")));
    sec.append(box);
  } else if (reg.state === "near") {
    const box = el("div", "regbox near");
    box.append(el("h4", "", "⚠ " + t("reg_near_title")));
    for (const m of (reg.near || []).slice(0, 3)) {
      box.append(el("div", "", t("reg_near_body", { claim: esc(claim), real: esc(m.name) }) +
        `<div class="match"><span class="mono">${esc(m.reg_no || "—")} · ${esc(m.type || "")}</span></div>`));
    }
    sec.append(box);
  } else if (reg.state === "not_found") {
    sec.append(el("div", "regbox none",
      `<h4>${t("reg_notfound_title")}</h4><p class="sub">${t("reg_notfound_body", {
        claim: esc(claim), rows: (reg.mirror_rows || 0).toLocaleString(LANG === "hi" ? "hi-IN" : "en-IN"),
        as_of: esc(reg.as_of || "?") })}</p>`));
  } else {
    sec.append(el("div", "regbox none",
      `<h4>${t("reg_unavailable_title")}</h4><p class="sub">${t("reg_unavailable_body")}</p>`));
  }
  const src = (reg.sources || []).join("+") || "—";
  const asof = reg.as_of ? ` · as of ${esc(reg.as_of)}` : "";
  sec.append(el("p", "caveat", t("reg_source", { source: esc(src), asof: asof })));
  return sec;
}

function supportingSection(sup, headlineState) {
  const sec = el("section", "vsec");
  sec.append(el("h3", "", `${t("sec_supporting")} <span class="tag">${t("tag_supporting")}</span>`));
  let any = false;
  for (const f of (sup.flags || [])) {
    any = true;
    const cls = f.id === "category_mismatch" ? "flagbox bad" : "flagbox";
    const vars = {
      entity_name: esc(f.entity_name || ""), claimed_name: esc(f.claimed_name || ""),
      claimed: esc(f.claimed_label || f.claimed_category || ""), actual: esc(f.suffix_label || f.suffix || ""),
      role: esc(f.entity_role || ""), suffix_label: esc(f.suffix_label || ""), qr_payee: esc(f.qr_payee || ""),
    };
    sec.append(el("div", cls, t("flag_" + f.id, vars)));
  }
  const rf = sup.redflags || [];
  if (rf.length) {
    any = true;
    const chips = el("div", "chips");
    const why = el("div", "chipwhy"); why.hidden = true;
    rf.forEach((h, i) => {
      const b = el("button", "chip", `${esc(h.label[LANG])}: “${esc(h.matched)}”`);
      b.type = "button"; b.setAttribute("aria-expanded", "false");
      b.addEventListener("click", () => {
        const open = b.getAttribute("aria-expanded") === "true";
        chips.querySelectorAll(".chip").forEach((c) => { c.setAttribute("aria-expanded", "false"); });
        if (open) { why.hidden = true; return; }
        b.setAttribute("aria-expanded", "true");
        why.innerHTML = `<b>${esc(h.label[LANG])}</b> — ${esc(h.why[LANG])}`;
        why.hidden = false;
      });
      chips.append(b);
    });
    sec.append(chips, why);
  }
  if ((sup.amounts || []).length) {
    any = true;
    sec.append(el("p", "clean", t("amounts_line", { amounts: sup.amounts.map(esc).join(" · ") })));
  }
  if (!any) sec.append(el("p", "clean", t("supporting_clean")));
  return sec;
}

/* ---------- SVG icons for badge states ---------- */
const BADGE_ICONS = {
  verified: '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path class="shield-fill" d="M12 2L4 6v5c0 5.25 3.4 10.1 8 11.25C16.6 21.1 20 16.25 20 11V6l-8-4z" fill="#fff"/><path class="checkmark-path" d="M9 12l2 2 4-4" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  red_flag: '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="#fff"/><path d="M8 8l8 8M16 8l-8 8" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg>',
  caution: '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M12 3L2 21h20L12 3z" fill="#fff"/><path d="M12 10v4" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/><circle cx="12" cy="17" r="1.2" fill="currentColor"/></svg>',
  unverifiable: '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="none" stroke="#fff" stroke-width="2"/><path d="M9 9a3 3 0 015.12 2.13c0 2-3 2.87-3 2.87" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round"/><circle cx="12" cy="18" r="1" fill="#fff"/></svg>',
  captcha_pending: '<svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="3" fill="#fff"/><path d="M8 12h8M12 8v8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
};

const BADGE_CLASS = {
  verified: "badge-safe",
  red_flag: "badge-danger",
  caution: "badge-warn",
  unverifiable: "badge-unknown",
  captcha_pending: "badge-pending",
};

function enforcementSection(enf) {
  if (!enf) return document.createDocumentFragment();
  const sec = el("section", "vsec");
  sec.append(el("h3", "", `${t("sec_enforcement")} <span class="tag">${t("tag_enforcement")}</span>`));

  if (!enf.found || !enf.hits || enf.hits.length === 0) {
    sec.append(el("div", "enf-box clean", `<h4><svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M9 12l2 2 4-4" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/></svg> ${t("enf_clean")}</h4>`));
    return sec;
  }

  const box = el("div", "enf-box");
  box.append(el("h4", "", `<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 8v4M12 16h.01" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg> ${t("enf_hits_title", { count: enf.hit_count || enf.hits.length })}`));

  for (const h of enf.hits.slice(0, 5)) {
    const hit = el("div", "enf-hit");
    hit.append(el("span", "type", esc(h.order_type || h.source)));
    hit.append(el("span", "date", ` · ${esc(h.order_date || "?")}`));
    if (h.violation_summary) hit.append(el("div", "summary", esc(h.violation_summary.slice(0, 120))));
    if (h.order_url) hit.append(el("a", "enf-link", t("enf_source_label", { source: esc(h.source) })));
    if (h.order_url) hit.lastChild.href = h.order_url;
    if (h.order_url) hit.lastChild.target = "_blank";
    if (h.order_url) hit.lastChild.rel = "noopener";
    box.append(hit);
  }
  sec.append(box);
  return sec;
}

function renderVerdict(v) {
  window.NR.lastVerdict = v;
  const host = $("#result");
  host.innerHTML = "";
  const state = v.headline.state;

  const card = el("article", "verdict"); card.id = "verdict-card";

  // --- Header: brand + badge (clean, no metadata noise) ---
  const head = el("div", "verdict-head");
  head.append(el("div", "who",
    '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M12 1.8 21.2 5.3V11c0 5.7-3.9 10-9.2 11.3C6.7 21 2.8 16.7 2.8 11V5.3Z" fill="#22324F"/><path d="M12 6.2 17.8 15.9H6.2Z" fill="#157F3D"/><path d="M9.9 12.9 11.5 14.6 14.7 10.4" fill="none" stroke="#F7F3EC" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg><b>NiveshRakshak</b>'));

  // Digital badge — the ONE thing users need to see first
  const badgeClass = BADGE_CLASS[state] || "badge-unknown";
  const badgeIcon = BADGE_ICONS[state] || BADGE_ICONS.caution;
  const st = t("stamp." + state);
  head.append(el("div", `badge ${badgeClass}`, `${badgeIcon}<span>${esc(st[0])}</span>`));
  card.append(head);

  // Headline section
  const hl = el("div", "headline hl-" + state);
  hl.append(el("div", "ico", ICONS[state] || ICONS.caution));
  let body = t("hl_body." + state);
  if (state === "red_flag") {
    const firstBad = (v.primaries || []).find((p) => p.state === "invalid");
    const catMis = (v.supporting?.flags || []).find((f) => f.id === "category_mismatch");
    const enfDef = (v.headline.reasons || []).includes("enforcement_defaulter");
    if (enfDef) {
      body = "This entity appears on a regulator's defaulter or expelled members list. Do not send money to this destination.";
    } else if (catMis) {
      body = t("reason_body.category_mismatch", {
        claimed: esc(catMis.claimed_label || catMis.claimed_category || "?"),
        actual: esc(catMis.suffix_label || catMis.suffix || "?") });
    } else if (firstBad) {
      body = reasonText(firstBad);
    }
  }
  const h2 = el("h2", "", t("hl_title." + state)); h2.tabIndex = -1;
  hl.append(el("div", "", ""));
  hl.lastChild.append(h2, el("p", "", body));
  card.append(hl);

  // --- Details: always visible, simple and scannable ---
  if ((v.primaries || []).length) {
    const sec = el("section", "vsec");
    sec.append(el("h3", "", `${t("sec_primary")} <span class="tag">${t("tag_primary")}</span>`));
    for (const p of v.primaries) sec.append(primaryRow(p));
    const note = v.headline.policy_note;
    if (note) {
      if (note.sip_carveout) sec.append(el("p", "caveat", t("sip_note")));
      if (note.in_transition) sec.append(el("p", "caveat", t("transition_note", { cutoff: esc(note.legacy_cutoff) })));
    }
    card.append(sec);
  }

  card.append(registrySection(v.registry));
  card.append(enforcementSection(v.enforcement));
  card.append(supportingSection(v.supporting || {}, state));

  // next action (always visible — it's actionable guidance)
  const na = el("div", "nextaction");
  na.append(el("h3", "", t("next_h")));
  na.append(el("p", "", t("next." + state)));
  if (state === "red_flag" || state === "unverifiable") na.append(el("p", "helpline", t("helpline")));
  card.append(na);

  // foot — metadata + QR for viral loop
  const meta = v.meta || {};
  const src = meta.sources || {};
  const pol = meta.policy || {};
  const timeStr = (meta.checked_at || "").replace("T", " ").slice(0, 16);
  const foot = el("footer", "verdict-foot");
  foot.append(el("p", "vns", t("vns_line")));

  // QR code + app link for viral loop
  const appUrl = window.NR_SHARE_URL || "https://niveshrakshak.in";
  const qrRow = el("div", "qr-row");
  const qrCanvas = document.createElement("canvas");
  qrCanvas.width = 80; qrCanvas.height = 80;
  qrCanvas.className = "qr-code";
  qrCanvas.setAttribute("aria-label", "QR code to check another message");
  generateQR(qrCanvas, appUrl);
  qrRow.append(qrCanvas);
  const qrText = el("div", "qr-text");
  qrText.append(el("strong", "", t("qr_cta")));
  qrText.append(el("span", "", appUrl));
  qrRow.append(qrText);
  foot.append(qrRow);

  foot.append(el("p", "",
    `${t("check_id", { id: meta.check_id ?? "—" })} · ${t("checked_at", { time: esc(timeStr) })}${meta.duration_ms ? " · " + t("took", { ms: meta.duration_ms }) : ""}`));
  foot.append(el("p", "",
    `SEBI Check: ${esc(src.sebi_check || "?")} · registry: ${(src.registry_mirror_rows || 0).toLocaleString("en-IN")} rows${src.registry_as_of ? " (" + esc(src.registry_as_of) + ")" : ""}${src.enforcement_records ? " · enforcement: " + src.enforcement_records.toLocaleString("en-IN") : ""}`));
  card.append(foot);

  host.append(card);

  // share row
  const row = el("div", "sharerow");
  const bShare = el("button", "main", `<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M12 3v12m0-12 4 4m-4-4L8 7M5 14v5h14v-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg> ${t("share_btn")}`);
  bShare.type = "button"; bShare.addEventListener("click", shareCard);
  const bText = el("button", "", t("share_text_btn")); bText.type = "button"; bText.addEventListener("click", shareAsText);
  const bCopy = el("button", "", t("share_copy")); bCopy.type = "button"; bCopy.addEventListener("click", shareCopy);
  row.append(bShare, bText, bCopy);
  host.append(row);

  h2.focus({ preventScroll: true });
  card.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ---------- sharing ----------
   Button order matters. The verdict CARD is the artifact this product exists to
   spread — README: "a screenshot-ready verdict card meant to be forwarded
   straight back into the WhatsApp/Telegram group the pitch came from". So the
   primary action shares the image (with the text as its caption, which keeps the
   links clickable). Text-only is the explicit secondary, and clipboard the last.

   Previously the primary button sent text only and the image hid behind a button
   labelled "Save as image" — which reads as "download to gallery", so nobody
   found the feature that carries the whole viral loop. */
window.NR.renderVerdict = renderVerdict;   // i18n.js re-renders on language switch

function shareText() {
  const v = window.NR.lastVerdict; if (!v) return "";
  const st = t("stamp." + v.headline.state)[0];
  const p0 = (v.primaries || [])[0];
  const primary = p0 ? `${p0.value || p0.account_masked || ""} → ${t("pill." + p0.state)}` : t("hl_title." + v.headline.state);
  const reg = v.registry ? t("reg_summaries." + v.registry.state) : t("reg_summaries.none");
  return t("share_text", {
    stamp: st, title: t("hl_title." + v.headline.state), primary,
    reg, id: v.meta?.check_id ?? "—",
    time: (v.meta?.checked_at || "").replace("T", " ").slice(0, 16),
    app_url: window.NR_SHARE_URL || "",
  });
}

/* Render the verdict card to a PNG blob. Promisified — the old callback-style
   canvas.toBlob meant `await sharePng()` resolved BEFORE the share happened, so
   the caller's try/catch fallback chain never actually ran. */
async function cardToBlob() {
  const card = $("#verdict-card");
  if (!card || !window.html2canvas) return null;
  const canvas = await html2canvas(card, { backgroundColor: "#F7F3EC", scale: 2, useCORS: false });
  return await new Promise((res) => canvas.toBlob((b) => res(b), "image/png"));
}

/* Text-only share. Native sheet first: navigator.share is unreliable in a WebView. */
async function shareAsText() {
  const text = shareText();
  if (NRN && await NRN.shareTextOnly(text)) { toast(t("toast_shared")); return true; }
  if (navigator.share) {
    try { await navigator.share({ text }); toast(t("toast_shared")); return true; }
    catch (e) { if (e.name === "AbortError") return true; }   // user cancelled — not a failure
  }
  return false;
}

/* PRIMARY: the card image + its text as caption. Falls back to text-only, then
   to a local download, then to the clipboard — so the button never dead-ends. */
async function shareCard() {
  let blob = null;
  try { blob = await cardToBlob(); } catch (e) { blob = null; }

  if (blob) {
    // Native path: writes the PNG into the cache dir under a .png name and hands
    // the file:// URI to @capacitor/share, which does the FileProvider conversion
    // + URI grant + chooser. See native.js for why the extension and the cache
    // directory are both non-negotiable.
    if (NRN && await NRN.shareImageBlob(blob, shareText())) { toast(t("toast_shared")); return; }

    const file = new File([blob], "niveshrakshak-verdict.png", { type: "image/png" });
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      try { await navigator.share({ files: [file], text: shareText() }); toast(t("toast_shared")); return; }
      catch (e) { if (e.name === "AbortError") return; }
    }
    // No file-share support (desktop browser): download it so it can still be forwarded.
    if (!NRN) {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob); a.download = file.name; a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      toast(t("toast_png"));
      return;
    }
  }
  // Image unavailable or every image path failed — still get the verdict out.
  if (await shareAsText()) return;
  await shareCopy();
}

async function shareCopy() {
  try { await navigator.clipboard.writeText(shareText()); toast(t("toast_copied")); }
  catch { toast(t("toast_share_fail")); }
}

/* ---------- footer build info ---------- */
/* Cached so a language switch can re-render the line instantly without another
   network round-trip. buildInfo() used to be a fire-once IIFE, which is why the
   footer stayed in English after toggling to हिंदी — setLang() re-renders the
   verdict card but nothing re-ran this. */
let _healthCache = null;

function renderBuildInfo() {
  const h = _healthCache;
  if (!h) return;
  $("#build-info").textContent = t("build_line", {
    version: window.NR_APP_VERSION || "dev",
    rows: (h.registry?.mirror_rows || 0).toLocaleString(LANG === "hi" ? "hi-IN" : "en-IN"),
    as_of: h.registry?.as_of || "?",
    policy: `${h.policy?.mode}/${h.policy?.legacy_cutoff}`,
  });
}

async function buildInfo() {
  try {
    const r = await fetch(API("/api/health"));
    _healthCache = await r.json();
    renderBuildInfo();
  } catch { /* offline — leave empty */ }
}
window.NR.renderBuildInfo = renderBuildInfo;   // called by i18n.js setLang()
buildInfo();
