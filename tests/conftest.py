"""All tests pass, then a native library (Qt, onnxruntime) can crash while the interpreter tears
down, turning a green run into a red exit code. Leave with pytest's own result instead."""
import os

_status = {"code": 0}


def pytest_sessionfinish(session, exitstatus):
    _status["code"] = int(exitstatus)


def pytest_unconfigure(config):
    if os.environ.get("TESLER_HARD_EXIT", "1") != "1":
        return
    from dragshift.util import hard_exit
    hard_exit(_status["code"])
