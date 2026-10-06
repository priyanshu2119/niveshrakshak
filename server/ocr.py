"""Image intake: QR decode (zbarimg) + OCR (tesseract eng+hin).

Both are CLI subprocesses — installed system tools, no fragile native wheels
(docs/DECISIONS.md §1). Input is re-encoded to PNG via PIL first so JPEG/WEBP/
PNG screenshots all take one path.

ponytail: single OCR pass (psm 3); add a sparse-text second pass (psm 11) if
real-world screenshot recall falls short.
"""
import os
import re
import shutil
import subprocess
import tempfile

from PIL import Image, ImageOps

TESSDATA = os.path.join(os.path.dirname(__file__), "tessdata")
MAX_BYTES = 10 * 1024 * 1024
_MAGIC = {b"\x89PNG": "png", b"\xff\xd8": "jpeg", b"RIFF": "webp", b"GIF8": "gif"}

# Tesseract gains nothing past roughly 300 dpi-equivalent glyph height, while a
# 50 MP phone photo costs seconds and hundreds of megabytes to process at full
# size. The test device (Realme 12 Pro+ / RMX3870) shoots 8160x6120. Audit check
# #23 spent 20.8 s and extracted nothing; capping the long edge brings that back
# into the low seconds without hurting recall on chat screenshots.
MAX_OCR_EDGE = 2000

# Only upscale for a QR retry when the source is small. The previous code built
# the 2x image eagerly for EVERY input, so a 50 MP photo allocated a 200 MP
# (~600 MB) RGB buffer inside a container capped at 2 GB.
QR_UPSCALE_MAX_PIXELS = 2_000_000


def _sniff(data: bytes) -> bool:
    return any(data.startswith(m) for m in _MAGIC)


def _to_png(data: bytes) -> Image.Image:
    from io import BytesIO
    im = Image.open(BytesIO(data))
    im = ImageOps.exif_transpose(im)          # phone screenshots carry EXIF rotation
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    return im


def _langs() -> str:
    have = []
    for l in ("eng", "hin"):
        if os.path.exists(os.path.join(TESSDATA, f"{l}.traineddata")):
            have.append(l)
    return "+".join(have) if have else "eng"


def _fit_long_edge(im: Image.Image, max_edge: int) -> Image.Image:
    """Scale down so the long edge is at most max_edge. Never scales up."""
    w, h = im.size
    long_edge = max(w, h)
    if long_edge <= max_edge:
        return im
    scale = max_edge / float(long_edge)
    return im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)


def decode_qr(im: Image.Image) -> list[str]:
    """zbarimg --raw; one retry at 2× upscale for small/soft QRs."""
    if shutil.which("zbarimg") is None:
        return []
    out = []
    with tempfile.TemporaryDirectory() as td:
        for attempt in (0, 1):
            if attempt == 1:
                # Retry larger only when doubling stays cheap. A big photo already
                # has plenty of pixels for zbar, and building the 2x buffer for it
                # was the single largest cost in the whole pipeline.
                if im.width * im.height > QR_UPSCALE_MAX_PIXELS:
                    break
                img = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
            else:
                img = im
            p = os.path.join(td, f"q{attempt}.png")
            img.save(p, "PNG")
            try:
                r = subprocess.run(["zbarimg", "--raw", "-q", p],
                                   capture_output=True, text=True, timeout=30)
            except (subprocess.TimeoutExpired, OSError):
                return out
            for line in r.stdout.splitlines():
                line = line.strip()
                if line and line not in out:
                    out.append(line)
            if out:
                break
    return out


def _run_tesseract(path: str, langs: str) -> str:
    env = dict(os.environ, TESSDATA_PREFIX=TESSDATA)
    try:
        r = subprocess.run(["tesseract", path, "stdout", "-l", langs, "--psm", "3"],
                           capture_output=True, text=True, timeout=60, env=env)
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return r.stdout


def ocr(im: Image.Image) -> str:
    if shutil.which("tesseract") is None:
        return ""
    # Upscale small images (tesseract wants ~300dpi-equivalent glyph height) and
    # cap large ones. Both directions matter: a 480px thumbnail is unreadable
    # without enlargement, a 50 MP photo is slow and no more accurate.
    if im.width < 1200:
        scale = min(3.0, 1400.0 / max(im.width, 1))
        im = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)
    im = _fit_long_edge(im, MAX_OCR_EDGE)
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "o.png")
        im.save(p, "PNG")
        langs = _langs()
        text = _run_tesseract(p, langs)
        # The Devanagari model mangles Latin runs embedded in Indic text. A real
        # screenshot reading "इस UPI पर पैसे भेजें: handle@psp" came back as
        # "इस 000 पर पैसे भेजें: [1717070777707772427-17707777" — the word UPI and
        # the whole handle destroyed. A UPI handle is always Latin, so when the
        # combined pass finds no "@" at all, run Latin-only and keep both: the
        # Indic pass supplies the red-flag phrases, the Latin pass the handle.
        if "+" in langs and "@" not in text:
            latin = _run_tesseract(p, "eng")
            if "@" in latin:
                text = f"{text}\n{latin}"
    return text


def process_image(data: bytes) -> dict:
    """One entry point for uploads: {ok, text, qr, error}."""
    if not data or len(data) > MAX_BYTES:
        return {"ok": False, "text": "", "qr": [], "error": "size"}
    if not _sniff(data):
        return {"ok": False, "text": "", "qr": [], "error": "format"}
    try:
        im = _to_png(data)
    except Exception:
        return {"ok": False, "text": "", "qr": [], "error": "decode"}
    qr = decode_qr(im)
    text = ocr(im)
    # QR payloads often contain the handle too; keep both for cross-checking
    return {"ok": True, "text": text, "qr": qr, "error": None}


# --- self-check (uses the real Taurus QR image if present) --------------------
if __name__ == "__main__":
    sample = os.path.join(os.path.dirname(__file__), "..", ".research", "taurus_cf_brk.png")
    if not os.path.exists(sample):
        sample = "/home/any/Desktop/Tushar/.research/taurus_cf_brk.png"
    if os.path.exists(sample):
        r = process_image(open(sample, "rb").read())
        assert r["ok"], r
        assert any("taurus.cf.brk@validaxis" in q for q in r["qr"]), r["qr"]
        print("ocr.py self-check OK — QR decoded:", r["qr"])
    else:
        print("ocr.py self-check SKIPPED (sample image missing)")
