"""Text from a PDF area or an image ("Copy text").

1. PDF with a real text layer (exported from Word, systems, etc.): read the text straight
   from the PDF. Instant and exact, no OCR involved.
2. Otherwise (scans, screenshots, photos): OCR with the engine built into Windows 10/11
   (Windows.Media.Ocr via the `winrt` packages). It uses the OCR languages installed in
   Windows, so a Portuguese Windows reads accents correctly. No extra install needed.

Everything here is UI-free and safe to call from a worker thread.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

from .convert import fitz, open_image, open_pdf
from .util import UserError

OCR_DPI = 300           # rasterisation for OCR: small text needs ~300 dpi to be read reliably
MIN_TEXT_CHARS = 2      # a text layer with less than this is treated as "no text" (scan)


# ---------------------------------------------------------------- PDF text layer
def pdf_area_text_layer(src: str | Path, page: int, frac: tuple[float, float, float, float]) -> str:
    """Text inside an area of a page, from the PDF's own text layer ('' if it has none).
    `frac` = (x0, y0, x1, y1) as fractions of the page as displayed (rotation applied)."""
    x0, y0, x1, y1 = (min(max(v, 0.0), 1.0) for v in frac)
    with open_pdf(src) as doc:
        pg = doc[page]
        r = pg.rect
        shown = fitz.Rect(r.x0 + x0 * r.width, r.y0 + y0 * r.height,
                          r.x0 + x1 * r.width, r.y0 + y1 * r.height)
        clip = shown * pg.derotation_matrix   # get_text works in unrotated page space
        return tidy(pg.get_text("text", clip=clip, sort=True))


def pdf_area_text(src: str | Path, page: int, frac, ocr=None) -> tuple[str, str]:
    """(text, how) where how is 'pdf' (text layer) or 'ocr'."""
    text = pdf_area_text_layer(src, page, frac)
    if len(text.strip()) >= MIN_TEXT_CHARS:
        return text, "pdf"
    from .imaging import snip_pdf
    im = snip_pdf(src, page, frac, OCR_DPI)
    return (ocr or image_to_text)(im), "ocr"


def tidy(text: str) -> str:
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").replace("\x0c", "\n").split("\n")]
    out: list[str] = []
    for ln in lines:                      # collapse runs of blank lines
        if ln or (out and out[-1]):
            out.append(ln)
    return "\n".join(out).strip()


# ---------------------------------------------------------------- OCR
def windows_ocr_available() -> tuple[bool, str]:
    if sys.platform != "win32":
        return False, "Text recognition (OCR) needs Windows 10 or 11."
    try:
        from winrt.windows.media.ocr import OcrEngine  # type: ignore  # noqa: F401
    except Exception:
        return False, ("The OCR component isn't installed yet. Open Tesler with "
                       "“Iniciar Tesler.bat” once to install it.")
    return True, ""


def image_to_text(im: Image.Image) -> str:
    return tidy("\n".join(" ".join(w.text for w in line) for line in image_to_lines(im)))


class Word:
    __slots__ = ("text", "x", "y", "w", "h")

    def __init__(self, text: str, x: float, y: float, w: float, h: float):
        self.text, self.x, self.y, self.w, self.h = text, x, y, w, h


def image_to_lines(im: Image.Image) -> list[list[Word]]:
    """OCR → lines of words with boxes in `im`'s pixel coordinates."""
    ok, why = windows_ocr_available()
    if not ok:
        raise UserError(why)
    import asyncio
    return asyncio.run(_windows_ocr(im))


def image_file_to_text(path: str | Path) -> str:
    return image_to_text(open_image(path))


def _prepare(im: Image.Image, max_side: int) -> tuple[Image.Image, float]:
    """RGBA, within the engine's size limit; small images upscaled (OCR misses tiny text).
    Returns (image, k) where k = new size / original size."""
    im = im.convert("RGBA")
    w, h = im.size
    k = 1.0
    if max(w, h) > max_side:
        k = max_side / max(w, h)
    elif max(w, h) < 800:
        k = min(2.0, max_side / max(w, h))
    if k != 1.0:
        im = im.resize((max(1, round(w * k)), max(1, round(h * k))), Image.LANCZOS)
    return im, k


async def _windows_ocr(im: Image.Image) -> list[list[Word]]:
    from winrt.windows.globalization import Language  # type: ignore
    from winrt.windows.graphics.imaging import (BitmapAlphaMode, BitmapPixelFormat,  # type: ignore
                                                SoftwareBitmap)
    from winrt.windows.media.ocr import OcrEngine  # type: ignore
    from winrt.windows.storage.streams import DataWriter  # type: ignore

    engine = None
    for tag in ("pt-BR", "pt-PT"):        # prefer Portuguese if Windows has it installed
        try:
            lang = Language(tag)
            if OcrEngine.is_language_supported(lang):
                engine = OcrEngine.try_create_from_language(lang)
                break
        except Exception:
            pass
    if engine is None:
        engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        raise UserError("Windows has no OCR language installed. Add one in Settings → "
                        "Time & language → Language (e.g. Português (Brasil)).")

    im, k = _prepare(im, int(OcrEngine.max_image_dimension or 2600))
    w, h = im.size
    writer = DataWriter()
    writer.write_bytes(im.tobytes("raw", "BGRA"))
    bitmap = SoftwareBitmap.create_copy_with_alpha_from_buffer(writer.detach_buffer(), BitmapPixelFormat.BGRA8,
                                                               w, h, BitmapAlphaMode.PREMULTIPLIED)
    result = await engine.recognize_async(bitmap)
    lines = []
    for line in result.lines:
        words = []
        for wd in line.words:
            r = wd.bounding_rect
            words.append(Word(wd.text, r.x / k, r.y / k, r.width / k, r.height / k))
        if words:
            lines.append(words)
    return lines


# ---------------------------------------------------------------- searchable PDF
def make_searchable_pdf(src: str | Path, ocr_lines=None, progress=None) -> tuple[Path, int, int]:
    """Copy of the PDF with an invisible text layer on pages that have no text, so they can
    be searched (Ctrl+F) and copied. Returns (out, pages_recognised, pages_already_text)."""
    from .util import sibling
    ocr_lines = ocr_lines or image_to_lines
    out = sibling(src, "Searchable", ".pdf")
    done = skipped = 0
    with open_pdf(src) as doc:
        n = doc.page_count
        for i, pg in enumerate(doc):
            if progress:
                progress(i, n)
            if len(pg.get_text("text").strip()) >= 20:      # already has real text
                skipped += 1
                continue
            pix = pg.get_pixmap(dpi=OCR_DPI, alpha=False)
            im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            lines = ocr_lines(im)
            if not lines:
                continue
            _add_invisible_text(pg, lines, 72.0 / OCR_DPI)
            done += 1
        if not done and not skipped:
            raise UserError("No text found to recognise in this PDF.")
        if not done:
            raise UserError("This PDF already has selectable text.")
        doc.save(out, garbage=3, deflate=True)
    return out, done, skipped


def _add_invisible_text(pg, lines, k: float) -> None:
    """Words placed over the scan with render_mode=3 (invisible) at their OCR boxes.
    Boxes are in displayed (rotated) pixels; PDF drawing happens in unrotated space."""
    derot = pg.derotation_matrix
    font = fitz.Font("helv")
    for line in lines:
        for w in line:
            text = w.text.strip()
            if not text:
                continue
            x0, y0, x1, y1 = w.x * k, w.y * k, (w.x + w.w) * k, (w.y + w.h) * k
            h = max(1.0, y1 - y0)
            fs = h * 0.85
            tl = font.text_length(text, fontsize=fs)
            if tl > 0:  # stretch horizontally so selection covers the whole word
                fs = min(fs * (x1 - x0) / tl, h * 1.6)
            origin = fitz.Point(x0, y1 - h * 0.18) * derot
            pg.insert_text(origin, text, fontsize=fs, fontname="helv", render_mode=3,
                           rotate=pg.rotation)
