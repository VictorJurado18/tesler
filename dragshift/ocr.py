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
        return False, ("The OCR component isn't installed yet. Open DragShift with "
                       "“Iniciar DragShift.bat” once to install it.")
    return True, ""


def image_to_text(im: Image.Image) -> str:
    ok, why = windows_ocr_available()
    if not ok:
        raise UserError(why)
    import asyncio
    return tidy(asyncio.run(_windows_ocr(im)))


def image_file_to_text(path: str | Path) -> str:
    return image_to_text(open_image(path))


def _prepare(im: Image.Image, max_side: int) -> Image.Image:
    """RGBA, within the engine's size limit; small images upscaled (OCR misses tiny text)."""
    im = im.convert("RGBA")
    w, h = im.size
    if max(w, h) > max_side:
        k = max_side / max(w, h)
        im = im.resize((max(1, int(w * k)), max(1, int(h * k))), Image.LANCZOS)
    elif max(w, h) < 800:
        k = min(2.0, max_side / max(w, h))
        im = im.resize((int(w * k), int(h * k)), Image.LANCZOS)
    return im


async def _windows_ocr(im: Image.Image) -> str:
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

    im = _prepare(im, int(OcrEngine.max_image_dimension or 2600))
    w, h = im.size
    writer = DataWriter()
    writer.write_bytes(im.tobytes("raw", "BGRA"))
    bitmap = SoftwareBitmap.create_copy_with_alpha_from_buffer(writer.detach_buffer(), BitmapPixelFormat.BGRA8,
                                                               w, h, BitmapAlphaMode.PREMULTIPLIED)
    result = await engine.recognize_async(bitmap)
    return "\n".join(line.text for line in result.lines)
