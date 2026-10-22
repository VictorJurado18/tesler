"""Turns 'what just happened' into a short, useful summary for the notification:
sizes saved, new dimensions, pages, fields removed…"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .util import category, file_size, human_size
from .i18n import plural, tr


@dataclass
class Result:
    title: str
    detail: str
    outs: list[Path]
    srcs: list[Path] = field(default_factory=list)
    good: str = ""     # highlighted figure, e.g. "−75%"
    undo: object = None  # optional callable: custom undo (e.g. rename back) instead of trashing outs

    @property
    def thumb(self) -> Path | None:
        for o in self.outs:
            if category(o) == "image":
                return o
        return None


def dims(path: Path) -> tuple[int, int] | None:
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        return None


def pages(path: Path) -> int | None:
    try:
        from .convert import fitz
        with fitz.open(path) as d:
            return d.page_count
    except Exception:
        return None


def size_change(before: int, after: int) -> tuple[str, str]:
    """('2.4 MB → 610 KB', '75% smaller') — second part empty if no meaningful change."""
    text = f"{human_size(before)} → {human_size(after)}"
    if before <= 0:
        return text, ""
    pct = (1 - after / before) * 100
    if pct >= 1:
        return text, tr("{a}% smaller", a=f"{pct:.0f}")
    if pct <= -1:
        return text, tr("{a}% larger", a=f"{-pct:.0f}")
    return text, tr("same size")


def _dim_str(d) -> str:
    return f"{d[0]}×{d[1]}" if d else ""


def summarize(action: str, srcs: list, outs: list, extra: str = "") -> Result:
    srcs = [Path(s) for s in srcs]
    outs = [Path(o) for o in outs if o]
    if not outs:
        return Result(action, extra or tr("Nothing was written"), [], srcs)
    src = srcs[0] if srcs else outs[0]
    before = sum(file_size(s) for s in srcs if s.is_file())
    after = sum(file_size(o) for o in outs if o.is_file())
    kind, _, name = action.partition(":")
    o0 = outs[0]
    good = ""

    if kind == "convert":
        fmt = name
        if len(srcs) > 1 and len(outs) == 1:
            title = tr("{n} files → 1 {fmt}", n=len(srcs), fmt=fmt)
        elif len(outs) > 1 and len(srcs) == 1:
            n = pages(src)
            title = tr("{p} pages → {n} {fmt}s", p=n or len(outs), n=len(outs), fmt=fmt)
        elif len(outs) > 1:
            title = tr("{n} files → {fmt}", n=len(outs), fmt=fmt)
        else:
            title = f"{src.suffix.lstrip('.').upper()} → {fmt}"
        bits = [o0.name if len(outs) == 1 else f"{o0.parent.name}/{o0.name} …"]
        d = dims(o0) if category(o0) == "image" else None
        if d:
            bits.append(_dim_str(d))
        if o0.suffix.lower() == ".pdf":
            n = pages(o0)
            if n:
                bits.append(plural(n, "{n} page", "{n} pages"))
        bits.append(human_size(after))
        return Result(title, " · ".join(bits), outs, srcs)

    if name == "Compress":
        sizes, verdict = size_change(before, after)
        title = tr("Compressed {n} files", n=len(srcs)) if len(srcs) > 1 else tr("Compressed")
        if not before or after >= before * 0.99:
            verdict = tr("already well compressed")
        return Result(title, sizes + (f" · {extra}" if extra else ""), outs, srcs, good=verdict)

    if name in ("Crop", "Resize", "Edit"):
        d0, d1 = dims(src), dims(o0)
        verb = {"Crop": "Cropped", "Resize": "Resized", "Edit": "Edited"}[name]
        if len(outs) > 1:
            return Result(tr(f"{verb} {{n}} images", n=len(outs)), f"{human_size(before)} → {human_size(after)}", outs, srcs)
        detail = f"{_dim_str(d0)} → {_dim_str(d1)}" if d0 and d1 and d0 != d1 else _dim_str(d1)
        if extra:
            detail += f" · {extra}"
        return Result(tr(verb), f"{detail} · {o0.name}", outs, srcs)

    if name == "Add BG":
        return Result(tr("Background added"), f"{_dim_str(dims(o0))} PNG · {human_size(after)} · {o0.name}", outs, srcs)

    if name == "Annotate":
        return Result(tr("Annotated"), f"{extra} · {o0.name}" if extra else o0.name, outs, srcs)

    if name == "Redact":
        return Result(tr("Redacted"), f"{extra} · {o0.name}" if extra else o0.name, outs, srcs,
                      good=tr("burned into pixels"))

    if name == "Metadata":
        return Result(tr("Metadata removed"), f"{extra} · {o0.name}" if extra else o0.name, outs, srcs,
                      good=tr("private copy"))

    if name == "Split":
        return Result(tr("Split into {n} PDFs", n=len(outs)), f"{o0.name} …", outs, srcs)

    if name == "Merge":
        n = pages(o0)
        return Result(tr("Merged {n} PDFs", n=len(srcs)), f"{plural(n or 0, '{n} page', '{n} pages')} · {human_size(after)} · {o0.name}", outs, srcs)

    if name == "Rotate":
        n = pages(o0)
        return Result(tr("Rotated 90°"), f"{plural(n or 0, '{n} page', '{n} pages')} · {o0.name}", outs, srcs)

    if name == "Snip":
        return Result(tr("Snip saved"), f"{_dim_str(dims(o0))} PNG · {human_size(after)} · {o0.name}", outs, srcs)

    if name in ("Organize", "ExtractPages"):
        n = pages(o0)
        if name == "ExtractPages":
            label = tr("Pages extracted")
        else:
            label = tr("PDFs merged") if len(srcs) > 1 else tr("Pages organized")
        return Result(label, f"{plural(n or 0, '{n} page', '{n} pages')} · {human_size(after)} · {o0.name}", outs, srcs)

    if name == "Rename":
        first = f"{srcs[0].name} → {o0.name}" if srcs else o0.name
        return Result(plural(len(outs), "Renamed {n} file", "Renamed {n} files"),
                      first + (" …" if len(outs) > 1 else ""), outs, srcs)

    if name == "Cutout":
        if len(outs) > 1:
            return Result(tr("Background removed from {n} images", n=len(outs)), human_size(after), outs, srcs,
                          good=tr("transparent PNG"))
        return Result(tr("Background removed"), f"{_dim_str(dims(o0))} · {human_size(after)} · {o0.name}", outs, srcs,
                      good=tr("transparent PNG"))

    if name == "OCR":
        n = pages(o0)
        return Result(tr("Searchable PDF"), f"{plural(n or 0, '{n} page', '{n} pages')} · {o0.name}", outs, srcs,
                      good=tr("Ctrl+F works"))

    if name == "Unlock":
        return Result(tr("Password removed"), o0.name, outs, srcs, good=tr("no password"))

    if name == "Protect":
        return Result(tr("Password protected"), f"AES-256 · {o0.name}", outs, srcs, good=tr("encrypted"))

    if name == "Extract":
        return Result(plural(len(outs), "Extracted {n} image", "Extracted {n} images"),
                      f"{o0.parent.name}/ · {human_size(after)}", outs, srcs)

    # generic
    return Result(tr(name or action), f"{o0.name} · {human_size(after)}", outs, srcs)
