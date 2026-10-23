"""Instant hand-off: if Tesler is already running, pass files to it and exit *before*
importing Qt. Right-click → Tesler / Send To then opens the menu in milliseconds."""
from __future__ import annotations

import json
import os
import sys


def ipc_name() -> str:
    return "Tesler-" + (os.environ.get("USERNAME") or os.environ.get("USER") or "user")


def wait_for_previous(argv: list[str], timeout: float = 10.0) -> None:
    """--after-pid=N (a restart): wait until that copy has quit, so we start fresh instead of handing off."""
    pid = next((a.split("=", 1)[1] for a in argv if a.startswith("--after-pid=")), "")
    if not pid.isdigit():
        return
    pid = int(pid)
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
            k32 = ctypes.WinDLL("kernel32")
            k32.OpenProcess.restype = wintypes.HANDLE
            k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            k32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            k32.CloseHandle.argtypes = [wintypes.HANDLE]
            h = k32.OpenProcess(0x00100000, False, pid)   # SYNCHRONIZE
            if h:
                k32.WaitForSingleObject(h, int(timeout * 1000))
                k32.CloseHandle(h)
        except Exception:
            pass
        return
    import time
    end = time.time() + timeout
    while time.time() < end:
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.1)


def try_handoff(argv: list[str]) -> bool:
    if "--selftest" in argv:
        return False
    wait_for_previous(argv)
    files = [os.path.abspath(a) for a in argv[1:] if not a.startswith("-") and os.path.exists(a)]
    payload = {"files": files} if files else {"show": "--quiet" not in argv}
    data = json.dumps(payload).encode("utf-8")
    try:
        if sys.platform == "win32":
            path = "\\\\.\\pipe\\" + ipc_name()       # QLocalServer's named pipe: \\.\pipe\<name>
            with open(path, "wb", buffering=0) as f:
                f.write(data)
                import time
                time.sleep(0.15)  # let the running copy read before the pipe closes
            return True
        import socket
        import tempfile
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(0.3)
        s.connect(os.path.join(tempfile.gettempdir(), ipc_name()))
        s.sendall(data)
        s.close()
        return True
    except OSError:
        return False
