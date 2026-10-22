"""The same end-to-end self-test CI runs on the .exe: every library and every window."""


def test_selftest():
    from dragshift import app
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or app.DragShiftQApplication([])
    assert app.selftest() == 0
