"""Updates from GitHub Releases, and the "what's new" notes.

- The installed app (Tesler-Setup.exe build) downloads the new installer, checks it against the
  SHA-256 GitHub publishes for the file, runs it silently and quits; the installer starts the new
  version, which then shows what changed once.
- Running from source there is nothing to install: the window says to update with git instead.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import __version__

REPO = "VictorJurado18/tesler"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
SETUP_NAME = "Tesler-Setup.exe"
CHECK_EVERY = 20 * 3600        # automatic check at most this often (seconds)
UA = {"User-Agent": f"Tesler/{__version__}", "Accept": "application/vnd.github+json"}


# ---------------------------------------------------------------- versions
def parse_version(v: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", (v or "").split("-")[0].split("+")[0])
    return tuple(int(n) for n in nums[:3]) + (0,) * (3 - min(3, len(nums)))


def is_newer(candidate: str, current: str = __version__) -> bool:
    return parse_version(candidate) > parse_version(current)


# ---------------------------------------------------------------- releases
@dataclass
class Release:
    version: str
    notes: str          # markdown
    page: str           # html_url
    setup_url: str = ""
    setup_size: int = 0
    sha256: str = ""    # from GitHub's asset digest, when present


def release_from_json(data: dict) -> Release | None:
    tag = data.get("tag_name") or ""
    if not re.match(r"^v?\d+\.\d+", tag) or data.get("draft") or data.get("prerelease"):
        return None
    rel = Release(version=tag.lstrip("v"), notes=data.get("body") or "", page=data.get("html_url") or RELEASES_PAGE)
    for a in data.get("assets") or []:
        if a.get("name") == SETUP_NAME:
            rel.setup_url = a.get("browser_download_url") or ""
            rel.setup_size = int(a.get("size") or 0)
            digest = a.get("digest") or ""
            if digest.startswith("sha256:"):
                rel.sha256 = digest.split(":", 1)[1].lower()
    return rel


def fetch_latest(timeout: float = 10) -> Release | None:
    """The newest published release, or None when there is none yet. Raises OSError when offline."""
    req = urllib.request.Request(API_LATEST, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:      # no release published yet
            return None
        raise
    return release_from_json(data)


# ---------------------------------------------------------------- installing
def installed_build() -> bool:
    """True for the app installed by Tesler-Setup.exe: it can update itself."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return False
    return (Path(sys.executable).parent / "unins000.exe").exists()   # installed, not the portable exe


def download(rel: Release, progress=None, cancelled=lambda: False) -> Path:
    """Download the installer to %TEMP% and verify it. progress(fraction) is called as it goes."""
    if not rel.setup_url:
        raise OSError("This release has no installer.")
    folder = Path(tempfile.gettempdir()) / "Tesler-update"
    folder.mkdir(exist_ok=True)
    dest = folder / f"Tesler-Setup-{rel.version}.exe"
    part = dest.with_suffix(".part")
    h = hashlib.sha256()
    req = urllib.request.Request(rel.setup_url, headers={"User-Agent": UA["User-Agent"]})
    with urllib.request.urlopen(req, timeout=30) as r, open(part, "wb") as f:
        total = int(r.headers.get("Content-Length") or rel.setup_size or 0)
        done = 0
        while True:
            if cancelled():
                raise InterruptedError
            chunk = r.read(256 * 1024)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            done += len(chunk)
            if progress and total:
                progress(done / total)
    if rel.setup_size and part.stat().st_size != rel.setup_size:
        part.unlink(missing_ok=True)
        raise OSError("The download was incomplete. Try again.")
    if rel.sha256 and h.hexdigest() != rel.sha256:
        part.unlink(missing_ok=True)
        raise OSError("The downloaded file didn't match the published one. Try again.")
    part.replace(dest)
    return dest


def run_installer(setup: Path) -> None:
    """Start the installer silently. It closes this app, updates it and starts it again."""
    flags = 0x00000008 | 0x00000200   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                      "/CLOSEAPPLICATIONS", "/RELAUNCH=1"], creationflags=flags, close_fds=True)


# ---------------------------------------------------------------- what's new
def changelog_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    for p in (base / "CHANGELOG.md", Path(__file__).resolve().parent.parent / "CHANGELOG.md"):
        if p.exists():
            return p
    return base / "CHANGELOG.md"


def notes_for(version: str = __version__, text: str | None = None) -> str:
    """The CHANGELOG section for `version` (markdown, without its heading)."""
    if text is None:
        try:
            text = changelog_path().read_text(encoding="utf-8")
        except OSError:
            return ""
    out, take = [], False
    for line in text.splitlines():
        m = re.match(r"^##\s+v?(\d+\.\d+(?:\.\d+)?)", line)
        if m:
            if take:
                break
            take = parse_version(m.group(1)) == parse_version(version)
            continue
        if take:
            out.append(line)
    return "\n".join(out).strip()


def tidy_notes(md: str) -> str:
    """Release bodies end with build details; keep only the notes."""
    return md.split("\n---", 1)[0].strip()


def open_page(url: str = RELEASES_PAGE):
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    QDesktopServices.openUrl(QUrl(url))


if __name__ == "__main__":   # python -m dragshift.updater  → prints what the app would see
    r = fetch_latest()
    print("current", __version__, "| latest", r.version if r else None, "| newer", bool(r and is_newer(r.version)))
