"""The same end-to-end self-test CI runs on the .exe: every library and every window,
in both looks (native Windows 11 and the classic liquid glass)."""
import pytest


@pytest.mark.parametrize("style", ["native", "classic"])
def test_selftest(style):
    from dragshift import app, glass, theme
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or app.DragShiftQApplication([])
    theme.set_style(style)
    theme.refresh()
    try:
        assert ("qradialgradient" in glass.qss()) == (style == "native")
        assert app.selftest() == 0
    finally:
        theme.set_style("native")
        theme.refresh()
