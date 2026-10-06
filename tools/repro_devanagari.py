"""Realistic Devanagari test: per-script font fallback, the way real apps render.

The first attempt drew the Latin UPI handle in NotoSansDevanagari. No tesseract
language or --psm combination could read it back ("Ooo0000000002427-1000000"),
which is a font artefact of the synthetic image, not a real-world case: WhatsApp,
Telegram and payment apps all fall back to a Latin face for Latin runs inside a
Devanagari message.

So this renders Hindi lines in the Devanagari face and the handle line in the
Latin face, then checks whether the eng+hin pass recovers the handle and whether
the Latin-only fallback in ocr.py is still needed.
"""
import glob
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from server import ocr, extract  # noqa: E402

OUT = pathlib.Path("/tmp/nrimg")
OUT.mkdir(exist_ok=True)


def ff(patterns):
    for pat in patterns:
        h = sorted(glob.glob(pat, recursive=True))
        if h:
            return h[0]
    return None


SANS = ff(["/usr/share/fonts/**/NotoSans-Regular.ttf", "/usr/share/fonts/**/DejaVuSans.ttf"])
DEVA = ff(["/usr/share/fonts/**/NotoSansDevanagari-Regular.ttf"])
print("latin face: %s" % SANS)
print("deva  face: %s" % DEVA)

UPI = "jaiswalrahul2427-1@oksbi"
# (text, is_devanagari)
LINES = [
    ("निवेश की शानदार योजना!", True),
    ("गारंटीड 30% मासिक रिटर्न", True),
    ("इस UPI पर पैसे भेजें:", True),
    (UPI, False),
    ("आज ही भुगतान करें, ऑफर सीमित समय के लिए", True),
]


def render(px, mixed):
    """mixed=True uses per-script fonts (realistic); False forces Devanagari for all."""
    w, h = 1080, 140 + 95 * len(LINES)
    im = Image.new("RGB", (w, h), (230, 221, 211))
    d = ImageDraw.Draw(im)
    d.rectangle([50, 60, w - 50, h - 60], fill=(255, 255, 255))
    y = 95
    for text, is_deva in LINES:
        path = DEVA if (is_deva or not mixed) else SANS
        try:
            f = ImageFont.truetype(path, px)
        except Exception:
            f = ImageFont.load_default()
        d.text((80, y), text, fill=(18, 18, 18), font=f)
        y += int(px * 1.75)
    return im


print()
print("%-34s %-8s %-28s %s" % ("CASE", "GLYPH", "HANDLE FOUND", "OCR TEXT (tail)"))
print("-" * 104)
for mixed in (True, False):
    for px in (36, 44, 56):
        im = render(px, mixed)
        p = OUT / ("k-deva-%s-%dpx.jpg" % ("mixed" if mixed else "singlefont", px))
        im.save(p, "JPEG", quality=88)
        r = ocr.process_image(p.read_bytes())
        merged = "\n".join(([r.get("text") or ""] + (r.get("qr") or [])))
        upis = extract.extract_all(merged)["upis"]
        label = "per-script fonts" if mixed else "all-Devanagari font"
        tail = (r.get("text") or "").strip().replace("\n", " | ")[-58:]
        print("%-34s %-8s %-28s %r" % (
            label, "%dpx" % px, (upis[0] if upis else "— NONE —"), tail))
print("-" * 104)
print()
print("Reading: 'per-script fonts' is what a real Hindi WhatsApp screenshot looks")
print("like. 'all-Devanagari font' is the pathological case where an app renders")
print("Latin text in an Indic face — no OCR engine recovers that, and it is not")
print("worth chasing.")
