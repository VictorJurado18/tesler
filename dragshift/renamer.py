"""Batch rename with a pattern: "{name}", "{n}" (number), "{date}" (photo date or modified).

plan() only computes; apply() renames in two phases (via temporary names) so swaps like
a→b, b→a work, and returns what undo() needs to put everything back.
"""
from __future__ import annotations

import datetime as dt
import os
import re
import uuid
from pathlib import Path

from .util import UserError

INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
ORDERS = ("current", "name", "date")


def file_date(p: Path) -> dt.datetime:
    """Photo 'taken' date from EXIF when there is one, else the file's modified time."""
    if p.suffix.lower() in (".jpg", ".jpeg", ".tif", ".tiff", ".heic", ".heif", ".png", ".webp"):
        try:
            from PIL import Image
            with Image.open(p) as im:
                exif = im.getexif()
                raw = exif.get_ifd(0x8769).get(0x9003) or exif.get(0x0132)
            if raw:
                return dt.datetime.strptime(str(raw).strip()[:19], "%Y:%m:%d %H:%M:%S")
        except Exception:
            pass
    return dt.datetime.fromtimestamp(p.stat().st_mtime)


def plan(paths, pattern: str, start: int = 1, digits: int = 0, order: str = "current") -> list[tuple[Path, Path]]:
    files = [Path(p) for p in paths]
    if order == "name":
        files.sort(key=lambda p: p.name.lower())
    elif order == "date":
        files.sort(key=file_date)
    width = digits or max(2, len(str(start + len(files) - 1)))
    pattern = (pattern or "{name}").strip()
    for alias, token in (("{nome}", "{name}"), ("{num}", "{n}"), ("{data}", "{date}")):
        pattern = pattern.replace(alias, token)
    out = []
    for i, p in enumerate(files):
        d = file_date(p) if "{date}" in pattern else None
        stem = (pattern.replace("{name}", p.stem)
                       .replace("{n}", str(start + i).zfill(width))
                       .replace("{date}", d.strftime("%Y-%m-%d") if d else ""))
        stem = re.sub(r"\s+", " ", stem).strip(" .")
        out.append((p, p.with_name(stem + p.suffix)))
    return out


def problems(pairs: list[tuple[Path, Path]]) -> dict[int, str]:
    """{row: reason} for names that can't be used."""
    bad: dict[int, str] = {}
    olds = {os.path.normcase(str(o)) for o, _ in pairs}
    seen: dict[str, int] = {}
    for i, (old, new) in enumerate(pairs):
        stem = new.stem
        key = os.path.normcase(str(new))
        if not stem:
            bad[i] = "empty name"
        elif INVALID.search(new.name):
            bad[i] = 'not allowed: < > : " / \\ | ? *'
        elif stem.split(".")[0].upper() in RESERVED:
            bad[i] = "reserved name"
        elif len(str(new)) > 250:
            bad[i] = "name too long"
        elif key in seen:
            bad[i] = bad[seen[key]] = "duplicate name"
        elif new.exists() and key not in olds:
            bad[i] = "a file with this name already exists"
        seen.setdefault(key, i)
    return bad


def apply(pairs: list[tuple[Path, Path]]) -> list[tuple[Path, Path]]:
    """Rename; returns the (new, old) pairs to undo it. Unchanged names are skipped."""
    pairs = [(o, n) for o, n in pairs if o != n]
    if problems(pairs):
        raise UserError("Some names can't be used. Fix the ones marked in red.")
    tag = uuid.uuid4().hex[:8]
    temps = []
    done: list[tuple[Path, Path]] = []
    try:
        for o, n in pairs:                    # phase 1: everything to a temporary name
            t = o.with_name(f".{o.stem}.{tag}.renaming{o.suffix}")
            os.rename(o, t)
            temps.append((t, o, n))
        for t, o, n in temps:                 # phase 2: temporary → final
            os.rename(t, n)
            done.append((n, o))
    except OSError as e:
        for t, o, _ in temps:                 # roll back whatever moved
            for cur in (t,) + tuple(n for n, oo in done if oo == o):
                if cur.exists():
                    try:
                        os.rename(cur, o)
                    except OSError:
                        pass
        raise UserError(f"Couldn't rename: {e.strerror or e}") from e
    return done


def undo(done: list[tuple[Path, Path]]) -> int:
    back = [(n, o) for n, o in done if n.exists()]
    return len(apply(back)) if back else 0
