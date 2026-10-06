"""Second-pass reproduction: realistic text sizes and real phone-camera resolutions.

The first pass proved QR decoding is NOT the problem (all six QR variants decoded,
including centre-logo, 200px-small, JPEG and 4000x3000). It also showed a
text-only UPI screenshot failing -- but that used PIL's ~11px default bitmap font,
which is not what a real screenshot looks like.

This pass answers three questions:
  1. Does OCR find a UPI handle at REALISTIC screenshot text sizes?
  2. What happens at 50MP, the actual sensor size of the test phone
     (Realme 12 Pro+ / RMX3870)? Audit check #23 took 20.8s, which nothing
     below 4000x3000 reproduced.
  3. Does Devanagari text survive?
"""
import glob
import resource
import sys
import time
import pathlib

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from server import ocr, extract  # noqa: E402

OUT = pathlib.Path("/tmp/nrimg")
OUT.mkdir(exist_ok=True)


def find_font(patterns):
    for pat in patterns:
        hits = sorted(glob.glob(pat, recursive=True))
        if hits:
            return hits[0]
    return None


SANS = find_font([
    "/usr/share/fonts/**/NotoSans-Regular.ttf",
    "/usr/share/fonts/**/NotoSansDisplay-Regular.ttf",
    "/usr/share/fonts/**/DejaVuSans.ttf",
    "/usr/share/fonts/**/LiberationSans-Regular.ttf",
])
DEVA = find_font([
    "/usr/share/fonts/**/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/**/NotoSansDevanagariUI-Regular.ttf",
    "/usr/share/fonts/**/Lohit-Devanagari.ttf",
])
print("sans font : %s" % SANS)
print("deva font : %s" % DEVA)
print()


def font(size, path=None):
    p = path or SANS
    try:
        return ImageFont.truetype(p, size) if p else ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()


def whatsapp_screenshot(lines, size_px, w=1080, deva=False):
    """A WhatsApp-style bubble screenshot with text at a given pixel height."""
    h = max(400, 140 + 90 * len(lines))
    im = Image.new("RGB", (w, h), (230, 221, 211))
    d = ImageDraw.Draw(im)
    f = font(size_px, DEVA if deva else None)
    d.rectangle([50, 60, w - 50, h - 60], fill=(255, 255, 255))
    y = 90
    for ln in lines:
        d.text((80, y), ln, fill=(18, 18, 18), font=f)
        y += int(size_px * 1.7)
    return im


def peak_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


UPI = "jaiswalrahul2427-1@oksbi"
cases = []

# ── 1. realistic text sizes ─────────────────────────────────────────────────
for px in (28, 36, 44, 56):
    im = whatsapp_screenshot(
        ["Invest 50000 today,", "guaranteed 30% monthly return.",
         "Pay to UPI ID:", UPI, "Act fast, offer closes today!"], px)
    p = OUT / ("h-text-%dpx.jpg" % px)
    im.save(p, "JPEG", quality=88)
    cases.append(("text UPI, %dpx glyphs" % px, p))

# ── 2. Devanagari ───────────────────────────────────────────────────────────
# Per-script font fallback, the way WhatsApp/Telegram/payment apps actually
# render: Devanagari face for the Indic lines, Latin face for the handle. Drawing
# the Latin handle in the Devanagari face is pathological -- no tesseract
# language or --psm combination recovers it (see tools/repro_devanagari.py).
if DEVA:
    im = whatsapp_screenshot(
        ["निवेश की शानदार योजना!", "गारंटीड 30% मासिक रिटर्न",
         "इस UPI पर पैसे भेजें:"], 44, deva=True)
    _d = ImageDraw.Draw(im)
    _d.text((80, 90 + int(44 * 1.7) * 3), UPI, fill=(18, 18, 18), font=font(44))
    p = OUT / "i-devanagari.jpg"
    im.save(p, "JPEG", quality=88)
    cases.append(("Devanagari + Latin UPI, 44px", p))

# ── 3. real phone-camera resolutions ────────────────────────────────────────
qr = Image.open("docs/demo-assets/taurus-official-qr.png").convert("RGB").crop((0, 0, 800, 800))
for (w, h, qs, label) in [
    (4000, 3000, 1200, "12MP 4000x3000"),
    (8160, 6120, 2400, "50MP 8160x6120 (RMX3870 sensor)"),
]:
    im = Image.new("RGB", (w, h), (222, 219, 213))
    d = ImageDraw.Draw(im)
    d.text((int(w * 0.04), int(h * 0.05)), "Scan to pay  ·  PhonePe Ltd", fill=(30, 30, 30))
    big = qr.resize((qs, qs), Image.LANCZOS)
    im.paste(big, ((w - qs) // 2, (h - qs) // 2))
    p = OUT / ("j-%dx%d.jpg" % (w, h))
    im.save(p, "JPEG", quality=90)
    cases.append((label, p))

# ── run ─────────────────────────────────────────────────────────────────────
print("=" * 92)
print("%-38s %7s %9s %9s  %-20s %s" % (
    "CASE", "SEC", "BYTES", "PEAK MB", "QR", "UPI EXTRACTED"))
print("=" * 92)
for label, path in cases:
    data = path.read_bytes()
    m0 = peak_mb()
    t0 = time.time()
    r = ocr.process_image(data)
    dt = time.time() - t0
    qr_hits = r.get("qr") or []
    merged = "\n".join(([r.get("text") or ""] + qr_hits))
    upis = extract.extract_all(merged)["upis"]
    ok = bool(upis)
    print("%s %-36s %7.1f %9d %9.0f  %-20s %s" % (
        "✅" if ok else "🔴", label, dt, len(data), peak_mb() - m0,
        (qr_hits[0][:18] + "…") if qr_hits else "—",
        upis[0] if upis else "— NONE —"))
print("=" * 92)

print()
print("─── what tesseract actually returned for the failures ───")
for label, path in cases:
    r = ocr.process_image(path.read_bytes())
    merged = "\n".join(([r.get("text") or ""] + (r.get("qr") or [])))
    if not extract.extract_all(merged)["upis"]:
        print("\n[%s]" % label)
        print("  raw text: %r" % ((r.get("text") or "").strip()[:300],))
