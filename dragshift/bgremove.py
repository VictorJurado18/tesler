"""Remove the background of a photo with a local AI model (no upload, runs on the CPU).

Model: IS-Net general use (same one the `rembg` project ships), run with onnxruntime,
which is already installed as a PyMuPDF dependency. It is downloaded once (~170 MB) to
%LOCALAPPDATA%\\DragShift\\models on first use.
"""
from __future__ import annotations

import hashlib
import os
import threading
import urllib.request
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image, ImageFilter

from .util import UserError

MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx"
MODEL_SHA256 = "60920e99c45464f2ba57bee2ad08c919a52bbf852739e96947fbb4358c0d964a"
MODEL_FILE = "isnet-general-use.onnx"
SIZE = 1024

_session = None
_lock = threading.Lock()


def models_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "DragShift" / "models"
    base.mkdir(parents=True, exist_ok=True)
    return base


def model_path() -> Path:
    return models_dir() / MODEL_FILE


def model_ready() -> bool:
    return model_path().exists()


def download_model(progress: Callable[[int, int], None] | None = None) -> Path:
    """Download (once) and verify the model. progress(bytes_done, bytes_total)."""
    dest = model_path()
    if dest.exists():
        return dest
    tmp = dest.with_suffix(".part")
    h = hashlib.sha256()
    try:
        with urllib.request.urlopen(MODEL_URL, timeout=30) as r, open(tmp, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    except Exception as e:  # noqa: BLE001
        tmp.unlink(missing_ok=True)
        raise UserError("Couldn't download the background-removal model. Check your internet "
                        "connection and try again.") from e
    if h.hexdigest() != MODEL_SHA256:
        tmp.unlink(missing_ok=True)
        raise UserError("The downloaded model is corrupted. Try again.")
    tmp.replace(dest)
    return dest


def _get_session():
    global _session
    with _lock:
        if _session is None:
            import onnxruntime as ort
            opts = ort.SessionOptions()
            opts.log_severity_level = 3
            _session = ort.InferenceSession(str(download_model()), opts, providers=["CPUExecutionProvider"])
        return _session


def predict_mask(im: Image.Image) -> Image.Image:
    """Foreground probability as an 'L' image the size of `im` (255 = keep)."""
    sess = _get_session()
    rgb = im.convert("RGB")
    x = np.asarray(rgb.resize((SIZE, SIZE), Image.BILINEAR), dtype=np.float32) / 255.0
    x = x / max(float(x.max()), 1e-6)
    x = (x - 0.5) / 1.0                                     # IS-Net normalisation
    x = x.transpose(2, 0, 1)[None]
    out = sess.run(None, {sess.get_inputs()[0].name: x})[0][0, 0]
    lo, hi = float(out.min()), float(out.max())
    out = (out - lo) / max(hi - lo, 1e-6)
    mask = Image.fromarray((out * 255).astype(np.uint8), "L").resize(rgb.size, Image.LANCZOS)
    return mask


def remove_background(im: Image.Image) -> Image.Image:
    """RGBA cut-out. Soft edges are kept (hair, fur), stray low-confidence haze is dropped."""
    mask = predict_mask(im)
    a = np.asarray(mask, dtype=np.float32) / 255.0
    a = np.clip((a - 0.04) / 0.92, 0.0, 1.0)              # drop faint haze, keep soft edges
    alpha = Image.fromarray((a * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(0.6))
    out = im.convert("RGBA")
    out.putalpha(alpha)
    return out


def trim_transparent(im: Image.Image, pad: int = 8) -> Image.Image:
    """Crop to the visible subject (plus a little padding)."""
    box = im.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    if not box:
        return im
    x0, y0, x1, y1 = box
    return im.crop((max(0, x0 - pad), max(0, y0 - pad), min(im.width, x1 + pad), min(im.height, y1 + pad)))
