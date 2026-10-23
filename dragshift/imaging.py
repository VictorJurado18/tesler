"""Pure image/PDF processing used by the tools (no UI here, so it's testable)."""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageOps
from PIL.ExifTags import GPSTAGS, TAGS

from .convert import atomic_save, fitz, flatten, open_image, open_pdf, save_image
from .util import UserError, app_data_dir, sibling
from .i18n import tr

EXT_TARGET = {".jpg": "JPG", ".jpeg": "JPG", ".png": "PNG", ".webp": "WEBP", ".tif": "TIFF",
              ".tiff": "TIFF", ".bmp": "BMP", ".heic": "HEIC", ".heif": "HEIC",
              ".avif": "AVIF", ".gif": "GIF", ".ico": "ICO"}


def target_for(path: str | Path) -> str:
    return EXT_TARGET.get(Path(path).suffix.lower(), "PNG")


def save_like(im: Image.Image, src: str | Path, label: str, force_ext: str | None = None) -> Path:
    """Save `im` next to `src` as '<name> <label>.<ext>' in the source's format."""
    ext = force_ext or Path(src).suffix.lower()
    if ext in (".gif", ".ico"):
        ext = ".png"
    out = sibling(src, label, ext)
    save_image(im, out, target_for(out))
    return out


# ---------------------------------------------------------------- compress
def compress_image(src: str | Path, quality: int = 72, max_side: int | None = None,
                   to_webp: bool = False) -> Path:
    im = open_image(src)
    if max_side and max(im.size) > max_side:
        im.thumbnail((max_side, max_side), Image.LANCZOS)
    ext = ".webp" if to_webp else Path(src).suffix.lower()
    out = sibling(src, "Compressed", ext)
    tgt = target_for(out)
    if tgt == "PNG":
        # lossy PNG: quantise to a palette (like pngquant), keeps transparency
        colors = max(16, min(256, int(quality * 2.56)))
        q = im.convert("RGBA").quantize(colors=colors, method=Image.Quantize.FASTOCTREE,
                                        dither=Image.Dither.FLOYDSTEINBERG)
        atomic_save(lambda dst: q.save(dst, "PNG", optimize=True), out)
    elif tgt in ("BMP", "TIFF", "GIF", "ICO"):
        out = sibling(src, "Compressed", ".jpg")
        save_image(im, out, "JPG", quality=quality)
    else:
        save_image(im, out, tgt, quality=quality)
    return out


def compress_pdf(src: str | Path, image_dpi: int = 150, quality: int = 70) -> Path:
    out = sibling(src, "Compressed", ".pdf")
    with open_pdf(src) as doc:
        try:
            doc.rewrite_images(dpi_threshold=image_dpi + 10, dpi_target=image_dpi,
                               quality=quality, lossy=True, lossless=True, bitonal=True,
                               color=True, gray=True, set_to_gray=False)
        except Exception:
            pass  # older PyMuPDF: still get structural compression below
        doc.save(out, garbage=4, deflate=True, deflate_images=True, deflate_fonts=True,
                 clean=True, use_objstms=1)
    return out


def encode_size(im: Image.Image, target: str, quality: int) -> int:
    """Bytes `im` would take saved as `target` at `quality` (PNG = palette-quantised)."""
    buf = io.BytesIO()
    if target == "PNG":
        colors = max(16, min(256, int(quality * 2.56)))
        im.convert("RGBA").quantize(colors=colors, method=Image.Quantize.FASTOCTREE).save(buf, "PNG", optimize=True)
    else:
        save_image(im, buf, target, quality=quality)
    return buf.tell()


def lossy_target(src: str | Path, to_webp: bool = False) -> str:
    """Format a compressed copy is written in (BMP/TIFF/GIF/ICO become JPG)."""
    if to_webp:
        return "WEBP"
    t = target_for(src)
    return t if t in ("JPG", "PNG", "WEBP", "AVIF", "HEIC") else "JPG"


def plan_target_size(im: Image.Image, target: str, max_bytes: int) -> tuple[int, int | None]:
    """Find (quality, max_side) that fits under max_bytes: binary-search quality, then shrink."""
    side = None
    work = im
    for _ in range(8):
        lo, hi, best = 30, 92, None
        while lo <= hi:
            q = (lo + hi) // 2
            if encode_size(work, target, q) <= max_bytes:
                best, lo = q, q + 1
            else:
                hi = q - 1
        if best is not None:
            return best, side
        side = int(max(work.size) * 0.8)
        work = im.copy()
        work.thumbnail((side, side), Image.LANCZOS)
        if side < 200:
            return 30, side
    return 30, side


def compress_to(src: str | Path, quality: int, max_side: int | None, target: str) -> Path:
    im = open_image(src)
    if max_side and max(im.size) > max_side:
        im.thumbnail((max_side, max_side), Image.LANCZOS)
    out = sibling(src, "Compressed", "." + ("jpg" if target == "JPG" else target.lower()))
    if target == "PNG":
        colors = max(16, min(256, int(quality * 2.56)))
        q = im.convert("RGBA").quantize(colors=colors, method=Image.Quantize.FASTOCTREE,
                                        dither=Image.Dither.FLOYDSTEINBERG)
        atomic_save(lambda dst: q.save(dst, "PNG", optimize=True), out)
    else:
        save_image(im, out, target, quality=quality)
    return out


# ---------------------------------------------------------------- resize
def resize_dims(size: tuple[int, int], mode: str, value: int) -> tuple[int, int]:
    """mode: 'pct' (value %), 'long' (longest side px), 'w' (width px), 'h' (height px)."""
    w, h = size
    if mode == "pct":
        k = value / 100
    elif mode == "long":
        k = value / max(w, h)
    elif mode == "w":
        k = value / w
    else:
        k = value / h
    return max(1, round(w * k)), max(1, round(h * k))


def resize_image(src: str | Path, dims: tuple[int, int]) -> Path:
    im = open_image(src)
    im = im.resize(dims, Image.LANCZOS)
    return save_like(im, src, f"{dims[0]}x{dims[1]}")


# ---------------------------------------------------------------- metadata
def read_image_metadata(src: str | Path) -> dict[str, str]:
    info: dict[str, str] = {}
    with Image.open(src) as im:
        info["Dimensions"] = f"{im.width} × {im.height}"
        info["Format"] = str(im.format)
        info["Mode"] = im.mode
        exif = im.getexif()
        for k, v in exif.items():
            info[TAGS.get(k, str(k))] = _fmt(v)
        try:
            for k, v in exif.get_ifd(0x8769).items():  # Exif sub-IFD (camera settings)
                info[TAGS.get(k, str(k))] = _fmt(v)
            gps = exif.get_ifd(0x8825)
            if gps:
                for k, v in gps.items():
                    info["GPS " + GPSTAGS.get(k, str(k))] = _fmt(v)
        except Exception:
            pass
        for k, v in (im.info or {}).items():
            if k in ("exif", "icc_profile", "xmp"):
                info[k.upper()] = f"{len(v)} bytes" if hasattr(v, "__len__") else "yes"
            elif isinstance(v, (str, int, float)):
                info[k] = str(v)
    return info


def _fmt(v) -> str:
    if isinstance(v, bytes):
        return f"<{len(v)} bytes>"
    s = str(v)
    return s if len(s) < 120 else s[:117] + "…"


def metadata_summary(src: str | Path) -> dict[str, str]:
    """The handful of fields people actually care about, human-readable."""
    out: dict[str, str] = {}
    with Image.open(src) as im:
        out["Size"] = f"{im.width} × {im.height}"
        exif = im.getexif()
        sub = {}
        gps = {}
        try:
            sub = exif.get_ifd(0x8769)
            gps = exif.get_ifd(0x8825)
        except Exception:
            pass
        make, model = str(exif.get(0x010F, "")).strip(), str(exif.get(0x0110, "")).strip()
        if make or model:
            out["Camera"] = model if make and model.startswith(make) else f"{make} {model}".strip()
        taken = sub.get(0x9003) or exif.get(0x0132)
        if taken:
            out["Taken"] = str(taken)
        if exif.get(0x0131):
            out["Software"] = str(exif.get(0x0131))
        if sub.get(0x829A):
            t = float(sub[0x829A])
            out["Exposure"] = f"1/{round(1 / t)} s" if 0 < t < 1 else f"{t:g} s"
        if sub.get(0x829D):
            out["Aperture"] = f"f/{float(sub[0x829D]):.1f}"
        if sub.get(0x8827):
            out["ISO"] = str(sub[0x8827])
        loc = gps_decimal(gps)
        if loc:
            out["Location"] = f"{loc[0]:.5f}, {loc[1]:.5f}"
    return out


def gps_decimal(gps) -> tuple[float, float] | None:
    try:
        def conv(v, ref):
            d, m, s_ = (float(x) for x in v)
            val = d + m / 60 + s_ / 3600
            return -val if ref in ("S", "W") else val
        return conv(gps[2], gps[1]), conv(gps[4], gps[3])
    except Exception:
        return None


def count_metadata(src: str | Path) -> tuple[int, bool]:
    """(number of EXIF/XMP/ICC entries, has GPS)."""
    with Image.open(src) as im:
        exif = im.getexif()
        n = len(exif)
        has_gps = False
        try:
            n += len(exif.get_ifd(0x8769))
            g = exif.get_ifd(0x8825)
            has_gps = bool(g)
            n += len(g)
        except Exception:
            pass
        n += sum(1 for k in ("xmp", "XML:com.adobe.xmp", "comment") if k in (im.info or {}))
    return n, has_gps


def strip_location(src: str | Path) -> Path:
    """Remove only GPS tags, keep camera info and everything else."""
    with Image.open(src) as im:
        exif = im.getexif()
        if 0x8825 in exif:
            del exif[0x8825]
        exif_bytes = exif.tobytes()
    im = open_image(src)
    out = sibling(src, "No Location", Path(src).suffix.lower() if Path(src).suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff") else ".jpg")
    # orientation already baked in by open_image → reset tag to 1
    ex = Image.Exif()
    ex.load(exif_bytes)
    ex[0x0112] = 1
    save_image(im, out, target_for(out), exif=ex.tobytes())
    return out


def strip_image_metadata(src: str | Path) -> Path:
    im = open_image(src)  # exif_transpose applied, so orientation is baked in
    clean = Image.new(im.mode, im.size)
    clean.paste(im)
    return save_like(clean, src, "Clean")


def read_pdf_metadata(src: str | Path) -> dict[str, str]:
    with open_pdf(src) as doc:
        info = {k: str(v) for k, v in (doc.metadata or {}).items() if v}
        info["Pages"] = str(doc.page_count)
        if doc.get_xml_metadata():
            info["XMP"] = "present"
    return info


def strip_pdf_metadata(src: str | Path) -> Path:
    out = sibling(src, "Clean", ".pdf")
    with open_pdf(src) as doc:
        doc.set_metadata({})
        try:
            doc.del_xml_metadata()
        except Exception:
            pass
        doc.save(out, garbage=3, deflate=True)
    return out


# ---------------------------------------------------------------- pdf extras
def split_pdf(src: str | Path) -> list[Path]:
    outs = []
    with open_pdf(src) as doc:
        for i in range(doc.page_count):
            nd = fitz.open()
            nd.insert_pdf(doc, from_page=i, to_page=i)
            out = sibling(src, tr("page {n}", n=i + 1), ".pdf")
            nd.save(out)
            nd.close()
            outs.append(out)
    return outs


def merge_pdfs(srcs: list[str | Path]) -> Path:
    out = sibling(srcs[0], "Merged", ".pdf")
    nd = fitz.open()
    for s in srcs:
        with open_pdf(s) as d:
            nd.insert_pdf(d)
    nd.save(out, garbage=3, deflate=True)
    nd.close()
    return out


def protect_pdf(src: str | Path, password: str) -> Path:
    out = sibling(src, "Protected", ".pdf")
    with open_pdf(src) as doc:
        perms = int(fitz.PDF_PERM_ACCESSIBILITY | fitz.PDF_PERM_PRINT | fitz.PDF_PERM_COPY)
        doc.save(out, encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw=password, user_pw=password,
                 permissions=perms, garbage=3, deflate=True)
    return out


# (image dpi, jpeg quality) from best to smallest
PDF_LADDER = [(220, 85), (200, 80), (170, 75), (150, 70), (130, 62), (110, 55), (96, 48), (80, 42),
              (72, 36), (60, 30), (50, 25)]


def _pdf_bytes(src: str | Path, dpi: int | None, quality: int) -> bytes:
    with open_pdf(src) as doc:
        if dpi:
            try:
                doc.rewrite_images(dpi_threshold=dpi + 10, dpi_target=dpi, quality=quality, lossy=True,
                                   lossless=True, bitonal=True, color=True, gray=True, set_to_gray=False)
            except Exception:
                pass
        return doc.tobytes(garbage=4, deflate=True, deflate_images=True, deflate_fonts=True,
                           clean=True, use_objstms=1)


def compress_pdf_to(src: str | Path, max_bytes: int, progress=None) -> tuple[Path, bool]:
    """Best-looking version under `max_bytes` (binary search over PDF_LADDER).
    Returns (out, reached). If even the smallest setting is too big (PDF is mostly text/
    vector, nothing left to squeeze), the smallest version is saved and reached=False."""
    out = sibling(src, "Compressed", ".pdf")
    tries = 0

    def attempt(i):
        nonlocal tries
        tries += 1
        if progress:
            progress(tries)
        return _pdf_bytes(src, *PDF_LADDER[i]) if i >= 0 else _pdf_bytes(src, None, 0)

    best = attempt(-1)                     # lossless only: images untouched
    if len(best) <= max_bytes:
        out.write_bytes(best)
        return out, True
    lo, hi, fit = 0, len(PDF_LADDER) - 1, None
    smallest = attempt(hi)
    if len(smallest) > max_bytes:
        out.write_bytes(smallest)
        return out, False
    fit = smallest
    hi -= 1
    while lo <= hi:                        # first (= best quality) index that fits
        mid = (lo + hi) // 2
        data = attempt(mid)
        if len(data) <= max_bytes:
            fit, hi = data, mid - 1
        else:
            lo = mid + 1
    out.write_bytes(fit)
    return out, True


def pdf_lock_state(src: str | Path) -> str:
    """'open' (no encryption), 'password' (needs a password to open),
    'restricted' (opens, but encrypted with an owner password / restrictions)."""
    try:
        with fitz.open(src) as doc:
            if doc.needs_pass:
                return "password"
            return "restricted" if doc.is_encrypted else "open"
    except Exception:
        return "open"


def check_pdf_password(src: str | Path, password: str) -> bool:
    with fitz.open(src) as doc:
        return not doc.needs_pass or bool(doc.authenticate(password))


def unlock_pdf(src: str | Path, password: str = "") -> Path:
    """Save an unencrypted copy (the password must be right, of course)."""
    out = sibling(src, "Unlocked", ".pdf")
    with fitz.open(src) as doc:
        if doc.needs_pass and not doc.authenticate(password):
            raise UserError("Wrong password.")
        doc.save(out, encryption=fitz.PDF_ENCRYPT_NONE, garbage=3, deflate=True)
    return out


def extract_pdf_images(src: str | Path) -> list[Path]:
    from .util import output_dir, unique_path
    folder = unique_path(output_dir(src) / tr("{name} images", name=Path(src).stem))
    outs: list[Path] = []
    seen: set[int] = set()
    with open_pdf(src) as doc:
        for pno, page in enumerate(doc):
            for img in page.get_images(full=True):
                xref = img[0]
                if xref in seen:
                    continue
                seen.add(xref)
                try:
                    info = doc.extract_image(xref)
                except Exception:
                    continue
                if not info or info.get("width", 0) < 16:
                    continue
                folder.mkdir(exist_ok=True)
                ext = info.get("ext", "png")
                if ext not in ("jpg", "jpeg", "png"):
                    pix = fitz.Pixmap(doc, xref)
                    if pix.n - pix.alpha >= 4:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    p = folder / (tr("page {p} image {n}", p=pno + 1, n=len(outs) + 1) + ".png")
                    pix.save(p)
                else:
                    p = folder / (tr("page {p} image {n}", p=pno + 1, n=len(outs) + 1) + f".{ext}")
                    p.write_bytes(info["image"])
                outs.append(p)
    if not outs:
        from .util import UserError
        raise UserError("No images found in this PDF.")
    return outs


def pdf_page_count(src: str | Path) -> int:
    with fitz.open(src) as d:
        return d.page_count


def rotate_pdf(src: str | Path, degrees: int = 90) -> Path:
    out = sibling(src, "Rotated", ".pdf")
    with open_pdf(src) as doc:
        for p in doc:
            p.set_rotation((p.rotation + degrees) % 360)
        doc.save(out)
    return out


# ---------------------------------------------------------------- redact
def redact(im: Image.Image, rects: list[tuple[int, int, int, int]], mode: str = "black") -> Image.Image:
    im = im.copy()
    for (x0, y0, x1, y1) in rects:
        box = (max(0, min(x0, x1)), max(0, min(y0, y1)),
               min(im.width, max(x0, x1)), min(im.height, max(y0, y1)))
        if box[2] - box[0] < 1 or box[3] - box[1] < 1:
            continue
        if mode == "black":
            ImageDraw.Draw(im).rectangle(box, fill=(0, 0, 0, 255) if im.mode == "RGBA" else 0)
        else:
            region = im.crop(box)
            if mode == "pixelate":
                w, h = region.size
                f = max(8, min(w, h) // 6)
                region = region.resize((max(1, w // f), max(1, h // f)), Image.BILINEAR)
                region = region.resize((w, h), Image.NEAREST)
            else:  # blur – strong enough that text can't be recovered
                region = region.filter(ImageFilter.GaussianBlur(max(12, min(region.size) / 3)))
            im.paste(region, box[:2])
    return im


# ---------------------------------------------------------------- edit
@dataclass
class Adjust:
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    sharpness: float = 1.0
    warmth: float = 0.0       # -1 … 1
    rotate: int = 0           # multiples of 90
    flip_h: bool = False
    flip_v: bool = False
    grayscale: bool = False
    resize_pct: int = 100


def auto_enhance(im: Image.Image) -> Adjust:
    """Pick gentle adjustments from the histogram (like a phone's 'auto' button)."""
    from PIL import ImageStat
    g = im.convert("L")
    st = ImageStat.Stat(g)
    mean, std = st.mean[0], st.stddev[0]
    a = Adjust()
    a.brightness = max(0.85, min(1.25, 1 + (118 - mean) / 400))
    a.contrast = max(0.95, min(1.3, 1 + (58 - std) / 160))
    sat = ImageStat.Stat(im.convert("HSV").split()[1]).mean[0]
    a.saturation = max(1.0, min(1.3, 1 + (110 - sat) / 400))
    a.sharpness = 1.15
    return a


def apply_adjust(im: Image.Image, a: Adjust) -> Image.Image:
    alpha = im.split()[3] if im.mode == "RGBA" else None
    rgb = im.convert("RGB")
    if a.brightness != 1.0:
        rgb = ImageEnhance.Brightness(rgb).enhance(a.brightness)
    if a.contrast != 1.0:
        rgb = ImageEnhance.Contrast(rgb).enhance(a.contrast)
    if a.saturation != 1.0:
        rgb = ImageEnhance.Color(rgb).enhance(a.saturation)
    if a.sharpness != 1.0:
        rgb = ImageEnhance.Sharpness(rgb).enhance(a.sharpness)
    if a.warmth:
        r, g, b = rgb.split()
        k = a.warmth * 25
        r = r.point(lambda v: max(0, min(255, v + k)))
        b = b.point(lambda v: max(0, min(255, v - k)))
        rgb = Image.merge("RGB", (r, g, b))
    if a.grayscale:
        rgb = ImageOps.grayscale(rgb).convert("RGB")
    out = rgb
    if alpha is not None:
        out = rgb.convert("RGBA")
        out.putalpha(alpha)
    if a.flip_h:
        out = ImageOps.mirror(out)
    if a.flip_v:
        out = ImageOps.flip(out)
    if a.rotate % 360:
        out = out.rotate(-a.rotate, expand=True)
    if a.resize_pct != 100:
        w = max(1, round(out.width * a.resize_pct / 100))
        h = max(1, round(out.height * a.resize_pct / 100))
        out = out.resize((w, h), Image.LANCZOS)
    return out


# ---------------------------------------------------------------- add background
@dataclass
class Background:
    colors: list[str] = field(default_factory=lambda: ["#ff9a5a", "#ff3d6e", "#7b5cff"])
    angle: float = 135.0       # degrees, CSS-style
    padding: float = 0.12      # fraction of the longer image side
    radius: int = 24           # px on the source image scale
    shadow: float = 0.5        # 0 … 1
    aspect: str = "Auto"       # Auto, 1:1, 4:3, 16:9, 9:16, 4:5


def _hex(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore


def gradient(size: tuple[int, int], colors: list[str], angle: float) -> Image.Image:
    import math
    w, h = size
    if len(colors) == 1:
        return Image.new("RGB", size, _hex(colors[0]))
    # Build a 1-px ramp, then stretch + rotate a big square and crop the centre.
    stops = [_hex(c) for c in colors]
    n = 512
    ramp = Image.new("RGB", (n, 1))
    px = ramp.load()
    for i in range(n):
        t = i / (n - 1) * (len(stops) - 1)
        j = min(int(t), len(stops) - 2)
        f = t - j
        a, b = stops[j], stops[j + 1]
        px[i, 0] = tuple(round(a[k] + (b[k] - a[k]) * f) for k in range(3))
    diag = int(math.hypot(w, h)) + 2
    big = ramp.resize((diag, diag), Image.BILINEAR)
    big = big.rotate(-(angle - 90), resample=Image.BICUBIC)
    left, top = (diag - w) // 2, (diag - h) // 2
    return big.crop((left, top, left + w, top + h))


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    scale = 4  # supersample for smooth corners
    m = Image.new("L", (size[0] * scale, size[1] * scale), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, m.width - 1, m.height - 1),
                                        radius=radius * scale, fill=255)
    return m.resize(size, Image.LANCZOS)


ASPECTS = {"1:1": 1.0, "4:3": 4 / 3, "16:9": 16 / 9, "9:16": 9 / 16, "4:5": 4 / 5, "3:2": 1.5}


def add_background(im: Image.Image, bg: Background) -> Image.Image:
    im = im.convert("RGBA")
    w, h = im.size
    pad = int(max(w, h) * bg.padding)
    cw, ch = w + 2 * pad, h + 2 * pad
    if bg.aspect in ASPECTS:
        r = ASPECTS[bg.aspect]
        if cw / ch < r:
            cw = int(round(ch * r))
        else:
            ch = int(round(cw / r))
    canvas = gradient((cw, ch), bg.colors, bg.angle).convert("RGBA")
    x, y = (cw - w) // 2, (ch - h) // 2
    radius = min(bg.radius, min(w, h) // 2)
    mask = rounded_mask((w, h), radius) if radius > 0 else Image.new("L", (w, h), 255)
    if im.mode == "RGBA":
        mask = ImageChops.multiply(mask, im.split()[3])
    if bg.shadow > 0:
        blur = max(4, int(max(w, h) * 0.035))
        sh = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        smask = Image.new("L", (cw, ch), 0)
        smask.paste(mask, (x, y + int(blur * 0.6)))
        smask = smask.filter(ImageFilter.GaussianBlur(blur))
        smask = smask.point(lambda v: int(v * 0.65 * bg.shadow))
        sh.putalpha(smask)
        canvas = Image.alpha_composite(canvas, sh)
    layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    layer.paste(im, (x, y), mask)
    return Image.alpha_composite(canvas, layer)


# ---------------------------------------------------------------- Qt bridge
def pil_to_png_bytes(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


# ---------------------------------------------------------------- PDF snip (area → image)
def pdf_page_count(src: str | Path) -> int:
    with open_pdf(src) as doc:
        return doc.page_count


def render_pdf_page(src: str | Path, page: int, dpi: float) -> Image.Image:
    """The page as shown on screen (rotation applied)."""
    with open_pdf(src) as doc:
        pix = doc[page].get_pixmap(dpi=dpi, alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def snip_pdf(src: str | Path, page: int, frac: tuple[float, float, float, float], dpi: int = 300) -> Image.Image:
    """Render only an area of a page, re-rasterised from the PDF at `dpi` (sharp text, not an
    upscaled preview). `frac` = (x0, y0, x1, y1) as fractions 0..1 of the page as displayed."""
    x0, y0, x1, y1 = (min(max(v, 0.0), 1.0) for v in frac)
    if x1 - x0 <= 0 or y1 - y0 <= 0:
        raise ValueError("empty selection")
    with open_pdf(src) as doc:
        pg = doc[page]
        r = pg.rect                                # displayed (rotated) page size
        shown = fitz.Rect(r.x0 + x0 * r.width, r.y0 + y0 * r.height,
                          r.x0 + x1 * r.width, r.y0 + y1 * r.height)
        clip = shown                               # get_pixmap clips in displayed coordinates
        pix = pg.get_pixmap(dpi=dpi, clip=clip, alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def save_pdf_snip(src: str | Path, page: int, frac, dpi: int = 300) -> Path:
    im = snip_pdf(src, page, frac, dpi)
    out = sibling(src, tr("page {n} snip", n=page + 1), ".png")
    save_image(im, out, "PNG")
    return out


# ---------------------------------------------------------------- organize / merge / extract pages
@dataclass
class PageRef:
    src: int            # index into the list of source PDFs
    page: int           # 0-based page number in that PDF
    rotate: int = 0     # extra rotation chosen by the user (multiple of 90)


def list_pages(srcs: list[str | Path]) -> list[PageRef]:
    refs: list[PageRef] = []
    for i, s in enumerate(srcs):
        with open_pdf(s) as doc:
            refs += [PageRef(i, n) for n in range(doc.page_count)]
    return refs


def page_thumbnail(src: str | Path, page: int, height: int = 150) -> Image.Image:
    with open_pdf(src) as doc:
        pg = doc[page]
        k = height / max(1.0, pg.rect.height)
        pix = pg.get_pixmap(matrix=fitz.Matrix(k, k), alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)


def parse_page_ranges(text: str, n: int) -> list[int]:
    """'1-3, 7, 10-' → 0-based indices (in order, no duplicates). Raises UserError on bad input."""
    out: list[int] = []
    text = text.replace(";", ",").replace(" ", "")
    if not text:
        return out
    for part in text.split(","):
        if not part:
            continue
        try:
            if "-" in part:
                a, b = part.split("-", 1)
                lo = int(a) if a else 1
                hi = int(b) if b else n
            else:
                lo = hi = int(part)
        except ValueError:
            raise UserError("Use page numbers like 1-3, 7, 10") from None
        if lo < 1 or hi > n or lo > hi:
            raise UserError("Use page numbers like 1-3, 7, 10")
        for i in range(lo - 1, hi):
            if i not in out:
                out.append(i)
    return out


def build_pdf(srcs: list[str | Path], refs: list[PageRef], label: str) -> Path:
    """New PDF with `refs` in order (pages from any of `srcs`, rotated as asked)."""
    if not refs:
        raise UserError("No pages to save.")
    out = sibling(srcs[refs[0].src], label, ".pdf")
    docs = [open_pdf(s) for s in srcs]
    try:
        nd = fitz.open()
        for r in refs:
            nd.insert_pdf(docs[r.src], from_page=r.page, to_page=r.page)
            if r.rotate % 360:
                pg = nd[-1]
                pg.set_rotation((pg.rotation + r.rotate) % 360)
        nd.save(out, garbage=3, deflate=True)
        nd.close()
    finally:
        for d in docs:
            d.close()
    return out


# ---------------------------------------------------------------- signatures
def signatures_dir() -> Path:
    base = app_data_dir() / "signatures"
    base.mkdir(parents=True, exist_ok=True)
    return base


def list_signatures() -> list[Path]:
    return sorted(signatures_dir().glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)


def save_signature(im: Image.Image) -> Path:
    import time
    im = trim_alpha(im.convert("RGBA"), pad=6)
    out = signatures_dir() / f"assinatura {time.strftime('%Y%m%d-%H%M%S')}.png"
    im.save(out)
    return out


def trim_alpha(im: Image.Image, pad: int = 0) -> Image.Image:
    box = im.getchannel("A").point(lambda v: 255 if v > 10 else 0).getbbox()
    if not box:
        raise UserError("The signature is empty.")
    x0, y0, x1, y1 = box
    return im.crop((max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad)))


def signature_from_photo(im: Image.Image) -> Image.Image:
    """Photo/scan of a signature on paper → ink only, transparent background.
    Paper brightness is measured locally so shadows on the photo don't become ink."""
    from PIL import ImageOps
    im = ImageOps.exif_transpose(im).convert("RGB")
    if max(im.size) > 2000:
        im.thumbnail((2000, 2000), Image.LANCZOS)
    gray = im.convert("L")
    paper = gray.filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(25))   # local paper level
    diff = ImageChops.subtract(paper, gray)                                               # how much darker than paper
    alpha = diff.point(lambda v: 0 if v < 18 else min(255, int((v - 18) * 4)))
    if not alpha.getbbox():
        raise UserError("No signature found in this image. Use a photo of dark ink on light paper.")
    rgb = ImageEnhance.Brightness(im).enhance(0.75)          # ink a bit darker/cleaner
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return trim_alpha(out, pad=6)


def sign_pdf(src: str | Path, signature: str | Path, page: int | None, frac: tuple[float, float, float, float]) -> Path:
    """Stamp the signature PNG on one page (or every page when page is None) at `frac`
    = (x0, y0, x1, y1), fractions of the page as displayed (rotation applied)."""
    out = sibling(src, "Signed", ".pdf")
    x0, y0, x1, y1 = frac
    with open_pdf(src) as doc:
        targets = range(doc.page_count) if page is None else [page]
        for i in targets:
            pg = doc[i]
            r = pg.rect
            shown = fitz.Rect(r.x0 + x0 * r.width, r.y0 + y0 * r.height, r.x0 + x1 * r.width, r.y0 + y1 * r.height)
            pg.insert_image(shown * pg.derotation_matrix, filename=str(signature), keep_proportion=True,
                            overlay=True, rotate=pg.rotation)
        doc.save(out, garbage=3, deflate=True)
    return out


# ---------------------------------------------------------------- collage
def collage(images: list[Image.Image], layout: str = "row", gap: int = 20, bg: str = "white",
            max_cell: int = 2000) -> Image.Image:
    """layout: 'row' (side by side, same height), 'column' (stacked, same width),
    'grid' (equal cells, each image fitted inside). bg: 'white' | 'black' | 'transparent'."""
    import math
    import statistics
    if not images:
        raise UserError("No images.")
    ims = [ImageOps.exif_transpose(im).convert("RGBA") for im in images]
    fill = {"white": (255, 255, 255, 255), "black": (0, 0, 0, 255), "transparent": (0, 0, 0, 0)}[bg]
    n = len(ims)
    if layout == "row":
        h = int(min(statistics.median(im.height for im in ims), max_cell))
        ims = [im.resize((max(1, round(im.width * h / im.height)), h), Image.LANCZOS) for im in ims]
        W = sum(im.width for im in ims) + gap * (n + 1)
        out = Image.new("RGBA", (W, h + 2 * gap), fill)
        x = gap
        for im in ims:
            out.alpha_composite(im, (x, gap))
            x += im.width + gap
        return out
    if layout == "column":
        w = int(min(statistics.median(im.width for im in ims), max_cell))
        ims = [im.resize((w, max(1, round(im.height * w / im.width))), Image.LANCZOS) for im in ims]
        H = sum(im.height for im in ims) + gap * (n + 1)
        out = Image.new("RGBA", (w + 2 * gap, H), fill)
        y = gap
        for im in ims:
            out.alpha_composite(im, (gap, y))
            y += im.height + gap
        return out
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    aspect = statistics.median(im.width / im.height for im in ims)
    cw = int(min(statistics.median(im.width for im in ims), max_cell // 2))
    ch = max(1, round(cw / aspect))
    out = Image.new("RGBA", (cols * cw + gap * (cols + 1), rows * ch + gap * (rows + 1)), fill)
    for i, im in enumerate(ims):
        r, c = divmod(i, cols)
        fit = ImageOps.contain(im, (cw, ch), Image.LANCZOS)
        x = gap + c * (cw + gap) + (cw - fit.width) // 2
        y = gap + r * (ch + gap) + (ch - fit.height) // 2
        out.alpha_composite(fit, (x, y))
    return out


def save_collage(paths: list[str | Path], layout: str, gap: int, bg: str) -> Path:
    from .convert import open_image
    im = collage([open_image(p) for p in paths], layout, gap, bg)
    if bg != "transparent":
        im = im.convert("RGB")
    out = sibling(paths[0], "Collage file", ".png" if bg == "transparent" else ".jpg")
    save_image(im, out, "PNG" if bg == "transparent" else "JPG", quality=92)
    return out
