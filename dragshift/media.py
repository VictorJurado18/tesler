"""Video and audio with ffmpeg (bundled by the `imageio-ffmpeg` package, nothing to install).

Video → MP4 / GIF / MP3, compress video. Audio → MP3 / WAV / M4A.
Every function takes an optional progress(fraction 0..1) callback.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

from .util import UserError, sibling

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".mpg", ".mpeg", ".3gp"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".flac", ".wma"}
VIDEO_TARGETS = ["MP4", "GIF", "MP3"]
AUDIO_TARGETS = ["MP3", "WAV", "M4A"]
GIF_MAX_SECONDS = 60   # longer videos: the GIF keeps the start, and the notification says so
GIF_WIDTH = 640

Progress = Callable[[float], None] | None
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0   # no console flashing from pythonw


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:  # noqa: BLE001
        raise UserError("The video component isn't installed yet. Open Tesler with "
                        "“Iniciar Tesler.bat” once to install it.") from e


def probe(src: str | Path) -> dict:
    """{'duration': seconds, 'width': w, 'height': h, 'video': bool, 'audio': bool}"""
    r = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(src)], capture_output=True,
                       creationflags=_NO_WINDOW)
    err = r.stderr.decode("utf-8", "replace")
    info = {"duration": 0.0, "width": 0, "height": 0, "video": False, "audio": False}
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", err)
    if m:
        info["duration"] = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    for line in err.splitlines():
        if "Stream #" in line and "Video:" in line and "attached pic" not in line and not info["video"]:
            info["video"] = True
            m = re.search(r", (\d{2,5})x(\d{2,5})", line)
            if m:
                info["width"], info["height"] = int(m[1]), int(m[2])
        elif "Stream #" in line and "Audio:" in line:
            info["audio"] = True
    if not (info["video"] or info["audio"]):
        raise UserError("This file doesn't look like a video or audio Tesler can read.")
    return info


def run_ffmpeg(args: list[str], duration: float, progress: Progress, out: Path) -> Path:
    tmp = out.with_name(f".{out.stem}.part{out.suffix}")
    cmd = [ffmpeg_exe(), "-hide_banner", "-nostdin", "-y", *args, "-progress", "pipe:1", "-nostats", str(tmp)]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=_NO_WINDOW)
    err_lines: list[str] = []
    import threading
    t = threading.Thread(target=lambda: err_lines.extend(
        ln.decode("utf-8", "replace") for ln in p.stderr), daemon=True)
    t.start()
    for raw in p.stdout:
        line = raw.decode("ascii", "replace").strip()
        if progress and duration > 0 and line.startswith("out_time_us="):
            try:
                progress(min(1.0, int(line.split("=", 1)[1]) / 1e6 / duration))
            except ValueError:
                pass
    p.wait()
    t.join(2)
    if p.returncode != 0 or not tmp.exists():
        tmp.unlink(missing_ok=True)
        tail = " ".join(err_lines[-3:]).strip()[-300:]
        raise UserError(f"ffmpeg couldn't convert this file. {tail}")
    tmp.replace(out)
    if progress:
        progress(1.0)
    return out


# ---------------------------------------------------------------- conversions
def to_mp4(src, progress: Progress = None) -> list[Path]:
    info = probe(src)
    out = sibling(src, ext=".mp4")
    args = ["-i", str(src), "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart"]
    return [run_ffmpeg(args, info["duration"], progress, out)]


def to_gif(src, progress: Progress = None) -> list[Path]:
    """Good-looking GIF: per-file palette, 12 fps, 640 px wide, first GIF_MAX_SECONDS at most."""
    info = probe(src)
    if not info["video"]:
        raise UserError("This file has no video.")
    dur = min(info["duration"] or GIF_MAX_SECONDS, GIF_MAX_SECONDS)
    w = min(GIF_WIDTH, info["width"] or GIF_WIDTH)
    out = sibling(src, ext=".gif")
    vf = (f"fps=12,scale={w}:-1:flags=lanczos,split[a][b];"
          f"[a]palettegen=max_colors=192:stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a")
    args = ["-t", f"{dur:.2f}", "-i", str(src), "-filter_complex", vf, "-loop", "0"]
    return [run_ffmpeg(args, dur, progress, out)]


def to_audio(src, fmt: str, progress: Progress = None) -> list[Path]:
    info = probe(src)
    if not info["audio"]:
        raise UserError("This file has no audio.")
    fmt = fmt.upper()
    codec = {"MP3": ["-c:a", "libmp3lame", "-q:a", "2"], "WAV": ["-c:a", "pcm_s16le"],
             "M4A": ["-c:a", "aac", "-b:a", "192k"]}[fmt]
    out = sibling(src, ext="." + fmt.lower())
    return [run_ffmpeg(["-i", str(src), "-vn", *codec], info["duration"], progress, out)]


def compress_video(src, progress: Progress = None) -> list[Path]:
    """H.264 at a quality that is hard to tell apart on a phone, max 1280 px wide (720p-ish)."""
    info = probe(src)
    if not info["video"]:
        raise UserError("This file has no video.")
    out = sibling(src, "Compressed", ".mp4")
    scale = "scale='min(1280,iw)':-2" if info["width"] >= info["height"] else "scale=-2:'min(1280,ih)'"
    args = ["-i", str(src), "-c:v", "libx264", "-preset", "medium", "-crf", "28", "-pix_fmt", "yuv420p",
            "-vf", scale, "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart"]
    return [run_ffmpeg(args, info["duration"], progress, out)]


def convert_media(src, cat: str, target: str, progress: Progress = None) -> list[Path]:
    target = target.upper()
    if target == "GIF":
        return to_gif(src, progress)
    if target == "MP4":
        return to_mp4(src, progress)
    if target in ("MP3", "WAV", "M4A"):
        return to_audio(src, target, progress)
    raise ValueError(f"Can't convert {cat} to {target}")


def targets(cat: str, src_ext: str) -> list[str]:
    ext = src_ext.lower().lstrip(".").upper()
    base = VIDEO_TARGETS if cat == "video" else AUDIO_TARGETS
    return [t for t in base if t != ext]
