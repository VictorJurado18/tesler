"""Colours for the whole app, Windows 11 style.

- Light or dark follows Windows (Settings → Personalization → Colors), unless forced in Settings.
- The accent is the one the person picked in Windows. Like Windows itself, dark surfaces use a
  lighter shade of it and light surfaces a deeper one (from the system's AccentPalette).
- Everything else is neutral: the accent marks only what you can act on or what is selected.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass

from PySide6.QtGui import QColor

# Windows 11's default accent (blue) as the fallback: light shade for dark mode, deep for light
DEFAULT_ACCENT_DARK = "#4CC2FF"
DEFAULT_ACCENT_LIGHT = "#005FB8"


@dataclass(frozen=True)
class Palette:
    dark: bool
    desk: str           # what's "behind" previews (unused on Windows, used in screenshots)
    bg: str             # window surface
    footer: str         # dialog footer band
    card: str           # toast / flyout surface
    control: str        # buttons, inputs at rest
    control_hover: str
    control_pressed: str
    selected: str       # selected item in a segmented control / list
    text: str
    text2: str          # secondary
    text3: str          # tertiary / disabled
    stroke: str         # hairlines and card borders
    stroke_strong: str  # control bottom edge, checkbox outline
    track: str          # slider / progress rail
    thumb: str          # slider thumb ring
    accent: str         # fills, underlines, focus
    on_accent: str      # text and icons on an accent fill
    accent_text: str    # accent used as text colour on the surface
    danger: str
    danger_text: str
    success: str
    ring: str           # radial menu glass tint (RGBA)
    ring_slice: str
    ring_stroke: str
    ring_hub: str


def _rgba(c: QColor, a: float) -> str:
    return f"rgba({c.red()},{c.green()},{c.blue()},{a:.3f})"


def _luminance(c: QColor) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c.red()) + 0.7152 * ch(c.green()) + 0.0722 * ch(c.blue())


# ---------------------------------------------------------------- system settings
def system_dark() -> bool:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QGuiApplication
        hints = QGuiApplication.styleHints()
        scheme = hints.colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    except Exception:
        pass
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
                return winreg.QueryValueEx(k, "AppsUseLightTheme")[0] == 0
        except OSError:
            pass
    return True


def system_accent_palette() -> list[QColor] | None:
    """Windows' 8 accent shades: [light3, light2, light1, base, dark1, dark2, dark3, -]."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent") as k:
            raw = bytes(winreg.QueryValueEx(k, "AccentPalette")[0])
        if len(raw) < 28:
            return None
        return [QColor(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, 32, 4)]
    except OSError:
        return None


def accent_for(dark: bool) -> QColor:
    pal = system_accent_palette()
    if pal:
        return QColor(pal[1] if dark else pal[4])        # Windows: Light2 on dark, Dark1 on light
    try:  # Qt 6.6+: the platform's accent colour
        from PySide6.QtGui import QGuiApplication, QPalette
        c = QGuiApplication.palette().color(QPalette.Accent)
        if c.isValid() and c.saturation() > 30:
            return c.lighter(150) if dark and _luminance(c) < 0.25 else c
    except Exception:
        pass
    return QColor(DEFAULT_ACCENT_DARK if dark else DEFAULT_ACCENT_LIGHT)


# ---------------------------------------------------------------- palettes
def build(dark: bool, accent: QColor | None = None) -> Palette:
    a = accent or accent_for(dark)
    on = "#000000" if _luminance(a) > 0.36 else "#FFFFFF"
    if dark:
        return Palette(
            dark=True, desk="#1D2630", bg="#202020", footer="#1B1B1B", card="#2B2B2B",
            control="rgba(255,255,255,0.061)", control_hover="rgba(255,255,255,0.084)",
            control_pressed="rgba(255,255,255,0.033)", selected="rgba(255,255,255,0.10)",
            text="#FFFFFF", text2="rgba(255,255,255,0.72)", text3="rgba(255,255,255,0.46)",
            stroke="rgba(255,255,255,0.08)", stroke_strong="rgba(255,255,255,0.18)",
            track="rgba(255,255,255,0.22)", thumb="#454545",
            accent=a.name(), on_accent=on, accent_text=a.name(),
            danger="#C42B1C", danger_text="#FF99A4", success="#6CCB5F",
            ring="rgba(28,28,28,0.66)", ring_slice="rgba(255,255,255,0.045)",
            ring_stroke="rgba(255,255,255,0.10)", ring_hub="rgba(36,36,36,0.94)")
    return Palette(
        dark=False, desk="#DCE3EA", bg="#F9F9F9", footer="#F3F3F3", card="#FFFFFF",
        control="#FFFFFF", control_hover="#F6F6F6", control_pressed="#F0F0F0", selected="rgba(0,0,0,0.06)",
        text="#1B1B1B", text2="#5C5C5C", text3="#8A8A8A",
        stroke="rgba(0,0,0,0.08)", stroke_strong="rgba(0,0,0,0.22)",
        track="rgba(0,0,0,0.18)", thumb="#FFFFFF",
        accent=a.name(), on_accent=on, accent_text=a.name(),
        danger="#C42B1C", danger_text="#C42B1C", success="#0F7B0F",
        ring="rgba(249,249,249,0.80)", ring_slice="rgba(0,0,0,0.035)",
        ring_stroke="rgba(0,0,0,0.08)", ring_hub="rgba(255,255,255,0.96)")


_current: Palette | None = None
MODE = "auto"   # "auto" | "dark" | "light" (Settings)


def set_mode(mode: str) -> None:
    global MODE, _current
    MODE = mode if mode in ("auto", "dark", "light") else "auto"
    _current = None


def current() -> Palette:
    global _current
    if _current is None:
        dark = system_dark() if MODE == "auto" else MODE == "dark"
        _current = build(dark)
    return _current


def refresh() -> Palette:
    """Re-read Windows (theme or accent changed)."""
    global _current
    _current = None
    return current()


def qcolor(css: str) -> QColor:
    """QColor from '#hex' or 'rgba(r,g,b,a)' (a 0..1)."""
    css = css.strip()
    if css.startswith("rgba"):
        r, g, b, a = (float(x) for x in css[css.index("(") + 1:css.index(")")].split(","))
        c = QColor(int(r), int(g), int(b))
        c.setAlphaF(a)
        return c
    return QColor(css)
