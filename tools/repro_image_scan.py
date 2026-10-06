"""Reproduce the friend's image-scan failure against the real ocr.py pipeline.

Builds realistic variants of a genuine UPI QR (the repo's own Taurus asset) and
runs each through server.ocr.process_image, reporting what zbar and tesseract
each returned plus the wall-clock cost.
"""
import io
import sys
import time
import pathlib

from PIL import Image, ImageDraw, ImageOps

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from server import ocr, extract  # noqa: E402

SRC = pathlib.Path("docs/demo-assets/taurus-official-qr.png")
OUT = pathlib.Path("/tmp/nrimg")
OUT.mkdir(exist_ok=True)

qr_full = Image.open(SRC).convert("RGB")
# The Taurus asset is 800x900 with the QR inside it; crop to the square QR body.
qr = qr_full.crop((0, 0, 800, 800)).resize((560, 560), Image.LANCZOS)


def phone_screen(w=1080, h=2400):
    """A plain app-background canvas the size of a real phone screenshot."""
    im = Image.new("RGB", (w, h), (248, 249, 250))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w, 150], fill=(95, 66, 189))          # app header
    d.text((40, 60), "Scan any QR to pay", fill=(255, 255, 255))
    d.text((40, h - 120), "PhonePe Ltd  ·  UPI payments", fill=(60, 60, 60))
    return im


def add_logo(im, size=150):
    """Overlay an opaque brand logo in the centre, the way PhonePe/GPay/Paytm QRs do."""
    d = ImageDraw.Draw(im)
    w, h = im.size
    box = [(w - size) // 2, (h - size) // 2, (w + size) // 2, (h + size) // 2]
    d.rectangle(box, fill=(255, 255, 255), outline=(95, 66, 189), width=6)
    d.text((box[0] + 28, box[1] + 62), "LOGO", fill=(95, 66, 189))
    return im


def save_jpeg(im, path, quality=85):
    """WhatsApp/Telegram re-encode every shared photo as JPEG; mimic that."""
    im.save(path, "JPEG", quality=quality)
    return path


cases = []

# ── A. Pristine QR, PNG ──────────────────────────────────────────────────────
p = OUT / "a-pristine.png"
qr.save(p)
cases.append(("A pristine QR (png, 560px)", p))

# ── B. QR inside a full phone screenshot ─────────────────────────────────────
scr = phone_screen()
scr.paste(qr, ((1080 - 560) // 2, 700))
p = OUT / "b-screenshot.png"
scr.save(p)
cases.append(("B QR in 1080x2400 screenshot", p))

# ── C. Same screenshot but JPEG-compressed (what WhatsApp actually sends) ────
p = OUT / "c-screenshot.jpg"
save_jpeg(scr, p, 82)
cases.append(("C same, JPEG q82 (WhatsApp)", p))

# ── D. Screenshot with a brand logo over the QR centre ───────────────────────
scr2 = phone_screen()
qr_logo = add_logo(qr.copy())
scr2.paste(qr_logo, ((1080 - 560) // 2, 700))
p = OUT / "d-logo.jpg"
save_jpeg(scr2, p, 82)
cases.append(("D QR with centre logo, JPEG", p))

# ── E. Small QR in a big screenshot (QR only ~18% of width) ──────────────────
scr3 = phone_screen()
small = qr.resize((200, 200), Image.LANCZOS)
scr3.paste(small, ((1080 - 200) // 2, 900))
p = OUT / "e-smallqr.jpg"
save_jpeg(scr3, p, 82)
cases.append(("E small QR (200px) in screenshot", p))

# ── F. Large camera photo 4000x3000 ─────────────────────────────────────────
photo = Image.new("RGB", (4000, 3000), (225, 222, 216))
dp = ImageDraw.Draw(photo)
dp.text((120, 120), "Payment QR  ·  PhonePe Ltd", fill=(40, 40, 40))
big = qr.resize((1500, 1500), Image.LANCZOS)
photo.paste(big, (1250, 700))
p = OUT / "f-bigphoto.jpg"
save_jpeg(photo, p, 88)
cases.append(("F 4000x3000 camera photo", p))

# ── G. Text-only WhatsApp-style screenshot with a UPI ID (no QR) ─────────────
# Rendered with a real TTF face at a realistic glyph height. PIL's default
# bitmap font is ~11px, which no OCR engine can read and which does not occur in
# an actual screenshot -- an earlier version of this case failed for that reason
# alone and sent the investigation down the wrong path.
import glob as _glob  # noqa: E402
from PIL import ImageFont as _IF  # noqa: E402

_SANS = next(iter(sorted(_glob.glob("/usr/share/fonts/**/NotoSans-Regular.ttf", recursive=True))
                   or _glob.glob("/usr/share/fonts/**/DejaVuSans.ttf", recursive=True)), None)
_F = _IF.truetype(_SANS, 44) if _SANS else _IF.load_default()
msg = Image.new("RGB", (1080, 900), (230, 221, 211))
dm = ImageDraw.Draw(msg)
dm.rectangle([60, 120, 1020, 620], fill=(255, 255, 255))
for _y, _t in [(160, "Invest 50000 today and get"),
               (235, "guaranteed 30% monthly return."),
               (330, "Pay to UPI ID:"),
               (405, "jaiswalrahul2427-1@oksbi"),
               (500, "Act fast, offer closes today!")]:
    dm.text((90, _y), _t, fill=(20, 20, 20), font=_F)
p = OUT / "g-textmsg.jpg"
save_jpeg(msg, p, 85)
cases.append(("G text-only UPI screenshot", p))

# ── run them all through the real pipeline ───────────────────────────────────
print("=" * 78)
print("%-34s %6s %8s  %-22s %s" % ("CASE", "SEC", "BYTES", "QR DECODED", "UPI EXTRACTED"))
print("=" * 78)
for label, path in cases:
    data = path.read_bytes()
    t0 = time.time()
    r = ocr.process_image(data)
    dt = time.time() - t0
    qr_hits = r.get("qr") or []
    qr_short = (qr_hits[0][:22] + "…") if qr_hits else "— NONE —"
    merged = "\n".join(([r.get("text") or ""] + qr_hits))
    upis = extract.extract_all(merged)["upis"]
    upi_short = upis[0] if upis else "— NONE —"
    flag = "🔴" if not upis else "✅"
    print("%s %-32s %6.1f %8d  %-22s %s" % (
        flag, label, dt, len(data), qr_short, upi_short))

print("=" * 78)
print()
print("─── detail: what tesseract actually read in the failing cases ───")
for label, path in cases:
    data = path.read_bytes()
    r = ocr.process_image(data)
    txt = (r.get("text") or "").strip()
    if not r.get("qr"):
        print("\n[%s]" % label)
        print("  qr   : %r" % (r.get("qr"),))
        print("  text : %r" % (txt[:220],))
