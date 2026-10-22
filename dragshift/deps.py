"""Install/update the Python packages when requirements.txt changed (used by the launcher).

`python -m dragshift.deps` → exit code 0 when everything is in place."""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQ = ROOT / "requirements.txt"


def marker() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "DragShift"
    base.mkdir(parents=True, exist_ok=True)
    return base / "requirements.sha256"


def main() -> int:
    if not REQ.exists():
        return 0
    digest = hashlib.sha256(REQ.read_bytes()).hexdigest()
    m = marker()
    if m.exists() and m.read_text().strip() == digest:
        return 0
    print("DragShift: instalando/atualizando componentes (so desta vez)...", flush=True)
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--disable-pip-version-check",
                        "-r", str(REQ)])
    if r.returncode != 0:
        print("Falha ao instalar os componentes. Veja a mensagem acima.", flush=True)
        return r.returncode
    m.write_text(digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
