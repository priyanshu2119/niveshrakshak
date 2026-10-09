"""Generate realistic demo assets for the live MVP demo.

Three images that exercise the three verdict states, rendered the way a real
WhatsApp screenshot looks -- per-script fonts, real glyph heights, JPEG
re-encoded. The lesson from the image-scan bug: synthetic inputs must be
realistic, or they test the wrong thing.
"""
import glob
import pathlib

from PIL import Image, ImageDraw, ImageFont

OUT = pathlib.Path("/tmp/nrdemo")
OUT.mkdir(exist_ok=True)


def ff(patterns):
    for pat in patterns:
        h = sorted(glob.glob(pat, recursive=True))
        if h:
            return h[0]
    return None


SANS = ff(["/usr/share/fonts/**/NotoSans-Regular.ttf",
           "/usr/share/fonts/**/NotoSans-Bold.ttf",
           "/usr/share/fonts/**/DejaVuSans.ttf"])
BOLD = ff(["/usr/share/fonts/**/NotoSans-Bold.ttf"]) or SANS
DEVA = ff(["/usr/share/fonts/**/NotoSansDevanagari-Regular.ttf"])
print("sans:", SANS)
print("bold:", BOLD)
print("deva:", DEVA)


def f(size, path=None):
    try:
        return ImageFont.truetype(path or SANS, size)
    except Exception:
        return ImageFont.load_default()


def bubble(im, d, x, y, w, text, size, colour=(255, 255, 255),
           text_colour=(17, 27, 33), path=None, pad=22):
    """Draw a WhatsApp-style message bubble and return the new y."""
    font = f(size, path)
    # crude word wrap
    words, lines, cur = text.split(), [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if d.textlength(trial, font=font) < w - 2 * pad:
            cur = trial
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    lh = int(size * 1.45)
    h = pad * 2 + lh * len(lines)
    d.rounded_rectangle([x, y, x + w, y + h], radius=16, fill=colour)
    ty = y + pad
    for ln in lines:
        d.text((x + pad, ty), ln, fill=text_colour, font=font)
        ty += lh
    return y + h + 26


# ── 1. RED FLAG: the classic impersonation pitch ─────────────────────────────
W, H = 1080, 1500
im = Image.new("RGB", (W, H), (230, 221, 211))
d = ImageDraw.Draw(im)
d.rectangle([0, 0, W, 130], fill=(0, 128, 105))                 # WhatsApp header
d.text((40, 45), "Investment Tips VIP  ·  online", fill=(255, 255, 255), font=f(34, BOLD))
y = 175
y = bubble(im, d, 60, y, 900,
           "🚀 Join our VIP tips group! SEBI registered advisor "
           "Rakesh Capital Securities (Reg No INZ000031633).", 40)
y = bubble(im, d, 60, y, 900,
           "Guaranteed 30% monthly return. Double your money in 60 days!", 40)
y = bubble(im, d, 60, y, 900,
           "Pay ₹50,000 today only to this UPI ID:", 40)
y = bubble(im, d, 60, y, 900,
           "jaiswalrahul2427-1@oksbi", 46, colour=(223, 255, 218), path=BOLD)
y = bubble(im, d, 60, y, 900,
           "Act fast! Offer closes today. Kisi ko batana mat.", 40)
im.save(OUT / "demo-1-redflag.jpg", "JPEG", quality=90)
print("wrote demo-1-redflag.jpg")

# ── 2. VERIFIED: the genuine Taurus QR from the repo ─────────────────────────
# 🔴 The caption must NOT name an intermediary category. This QR encodes
# taurus.cf.brk@validaxis -- a BROKER handle. An earlier version of this asset
# said "Taurus Mutual Fund", which extract_claimed_category() read as an `mf`
# claim; mf != brk, so verdict.cross_checks() raised category_mismatch and the
# headline came out RED_FLAG. That was the product working correctly on a
# mislabelled demo image. Keep the caption category-neutral.
qr = Image.open("docs/demo-assets/taurus-official-qr.png").convert("RGB")
qr = qr.resize((760, 855), Image.LANCZOS)
im2 = Image.new("RGB", (1080, 1400), (247, 243, 236))
d2 = ImageDraw.Draw(im2)
d2.text((60, 60), "Official payment QR", fill=(28, 27, 25), font=f(38, BOLD))
im2.paste(qr, (160, 160))
d2.text((60, 1080), "Scan in any UPI app. The handle ends in @validaxis", fill=(74, 70, 62), font=f(34))
d2.text((60, 1140), "Green triangle + thumbs-up confirms it on the payment screen.", fill=(74, 70, 62), font=f(32))
im2.save(OUT / "demo-2-verified-qr.jpg", "JPEG", quality=92)
print("wrote demo-2-verified-qr.jpg")

# ── 3. HINDI pitch (tests Devanagari OCR + the space-around-@ fix) ───────────
im3 = Image.new("RGB", (1080, 1300), (230, 221, 211))
d3 = ImageDraw.Draw(im3)
d3.rectangle([0, 0, 1080, 130], fill=(0, 128, 105))
d3.text((40, 45), "Share Bazaar Tips", fill=(255, 255, 255), font=f(34, BOLD))
y = 175
y = bubble(im3, d3, 60, y, 900, "निवेश की शानदार योजना! गारंटीड 30% मासिक रिटर्न।", 40, path=DEVA)
y = bubble(im3, d3, 60, y, 900, "इस UPI पर आज ही पैसे भेजें:", 40, path=DEVA)
y = bubble(im3, d3, 60, y, 900, "scam99@paytm", 48, colour=(223, 255, 218), path=BOLD)
y = bubble(im3, d3, 60, y, 900, "जल्दी करें, ऑफर सीमित समय के लिए। तुरंत भुगतान करें।", 40, path=DEVA)
im3.save(OUT / "demo-3-hindi.jpg", "JPEG", quality=90)
print("wrote demo-3-hindi.jpg")

print()
for p in sorted(OUT.glob("*.jpg")):
    from PIL import Image as I
    i = I.open(p)
    print("  %-26s %dx%d  %d KB" % (p.name, i.size[0], i.size[1], p.stat().st_size // 1024))
