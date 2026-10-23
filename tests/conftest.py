"""All tests pass, then a native library (Qt, onnxruntime) can crash while the interpreter tears
down, turning a green run into a red exit code. Leave with pytest's own result instead."""
import os
import sys

_status = {"code": 0}


def pytest_sessionfinish(session, exitstatus):
    _status["code"] = int(exitstatus)


def pytest_unconfigure(config):
    if os.environ.get("TESLER_HARD_EXIT", "1") != "1":
        return
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception:
            pass
    os._exit(_status["code"])
