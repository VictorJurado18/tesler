"""Liquid-glass look: frosted blur, specular highlights and an iridescent (rainbow)
rim. Used by the radial menu and every editor window."""
from __future__ import annotations

import ctypes
import os
import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QImage, QLinearGradient,
                           QPainter, QPainterPath, QPen, QPixmap, QRadialGradient)

# Rainbow stops for the iridescent rim (soft, pastel-ish so it reads as "glass").
IRIDESCENT = ["#ff6b9d", "#ffb36b", "#ffe66b", "#7dffb0", "#6bd5ff", "#8a7bff", "#e07bff", "#ff6b9d"]

TEXT = "#ffffff"
TEXT_DIM = "rgba(255,255,255,0.68)"
ACCENT_A = "#5ac8ff"
ACCENT_B = "#2f7bff"
ACCENT_C = "#5b5bff"


def iridescent_pen(center: QPointF, width: float, alpha: int = 200, angle: float = 30) -> QPen:
    g = QConicalGradient(center, angle)
    n = len(IRIDESCENT) - 1
    for i, c in enumerate(IRIDESCENT):
        col = QColor(c)
        col.setAlpha(alpha)
        g.setColorAt(i / n, col)
    return QPen(QBrush(g), width)


def iridescent_brush(rect: QRectF, alpha: int = 60) -> QBrush:
    g = QLinearGradient(rect.topLeft(), rect.bottomRight())
    n = len(IRIDESCENT) - 1
    for i, c in enumerate(IRIDESCENT):
        col = QColor(c)
        col.setAlpha(alpha)
        g.setColorAt(i / n, col)
    return QBrush(g)


def blur_pixmap(pm: QPixmap, radius: int = 18) -> QPixmap:
    """Fast frosted blur: downscale, light box blur via repeated scaling, upscale."""
    if pm.isNull():
        return pm
    w, h = pm.width(), pm.height()
    f = max(2, radius // 3)
    small = pm.scaled(max(1, w // f), max(1, h // f), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    small = small.scaled(max(1, w // (f * 2)), max(1, h // (f * 2)), Qt.IgnoreAspectRatio,
                         Qt.SmoothTransformation)
    return small.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)


def paint_glass(p: QPainter, path: QPainterPath, backdrop: QPixmap | None = None,
                backdrop_offset: QPointF = QPointF(0, 0), tint: QColor | None = None,
                rim: bool = True, rainbow_alpha: int = 170, highlight: float = 1.0) -> None:
    """Paint a liquid-glass surface filling `path`."""
    rect = path.boundingRect()
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.setClipPath(path)

    # 1. frosted backdrop (blurred desktop snapshot), slightly magnified = refraction
    if backdrop is not None and not backdrop.isNull():
        p.save()
        c = rect.center()
        p.translate(c)
        p.scale(1.04, 1.04)
        p.translate(-c)
        p.drawPixmap(backdrop_offset, backdrop)
        p.restore()

    # 2. tint – keeps white text readable on any wallpaper
    p.fillPath(path, tint or QColor(28, 24, 40, 105))

    # 3. faint rainbow wash across the body
    p.fillPath(path, iridescent_brush(rect, 26))

    # 4. top specular sheen
    sheen = QLinearGradient(rect.topLeft(), QPointF(rect.left(), rect.top() + rect.height() * 0.55))
    sheen.setColorAt(0.0, QColor(255, 255, 255, int(70 * highlight)))
    sheen.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.fillPath(path, sheen)

    # 5. soft caustic glow lower-right
    glow = QRadialGradient(QPointF(rect.right() - rect.width() * 0.2, rect.bottom() - rect.height() * 0.15),
                           max(rect.width(), rect.height()) * 0.55)
    glow.setColorAt(0.0, QColor(255, 255, 255, int(22 * highlight)))
    glow.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.fillPath(path, glow)
    p.restore()

    if rim:
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        # inner bezel glow: a wide, soft white stroke clipped to the inside of the shape
        p.setClipPath(path)
        for w, a in ((14, 10), (7, 16), (3, 26)):
            p.setPen(QPen(QColor(255, 255, 255, int(a * highlight)), w))
            p.drawPath(path)
        p.setClipping(False)
        # specular rim: bright on the edge facing the light (top-left), softer opposite
        spec = QLinearGradient(rect.topLeft(), rect.bottomRight())
        spec.setColorAt(0.0, QColor(255, 255, 255, int(235 * min(1.0, highlight))))
        spec.setColorAt(0.35, QColor(255, 255, 255, 60))
        spec.setColorAt(0.65, QColor(255, 255, 255, 35))
        spec.setColorAt(1.0, QColor(255, 255, 255, 150))
        p.setPen(QPen(QBrush(spec), 1.3))
        p.drawPath(path)
        # iridescent dispersion just outside the rim
        p.setPen(iridescent_pen(rect.center(), 1.4, rainbow_alpha))
        p.drawPath(path.translated(0.0, 0.0))
        p.restore()


# ---------------------------------------------------------------- Qt stylesheet
def _build_qss() -> str:
    """Windows 11 look on top of theme.current(): neutral surfaces, one accent, 4 px radii."""
    from . import icons, theme
    t = theme.current()
    acc = theme.qcolor(t.accent)
    acc_hover = (acc.darker(108) if not t.dark else acc.lighter(108)).name()
    acc_press = (acc.darker(116) if not t.dark else acc.darker(108)).name()
    edge = "rgba(255,255,255,0.08)" if t.dark else "rgba(0,0,0,0.10)"
    check = icons.write_svg_file("check", t.on_accent)
    chevron = icons.write_svg_file("chevron-down", t.text2 if t.text2.startswith("#") else ("#BFBFBF" if t.dark else "#5C5C5C"))
    warn = "#FCE100" if t.dark else "#9D5D00"
    return f"""
* {{ color: {t.text}; font-family: "@FONT@", sans-serif; font-size: 10pt; }}
QWidget#glassRoot {{ background: transparent; }}
QLabel {{ background: transparent; }}
QLabel#title {{ font-size: 9pt; color: {t.text2}; }}
QLabel#heading {{ font-family: "@DISPLAY@"; font-size: 15pt; font-weight: 600; }}
QLabel#dim, QLabel.dim {{ color: {t.text2}; font-size: 9pt; }}
QLabel#section {{ color: {t.text2}; font-size: 9pt; font-weight: 600; }}
QLabel#big {{ font-family: "@DISPLAY@"; font-size: 16pt; font-weight: 600; }}
QLabel#good {{ color: {t.accent_text}; font-weight: 600; }}
QLabel#warn {{ color: {warn}; font-weight: 600; }}
QLabel#error {{ color: {t.danger_text}; }}

QPushButton {{
  background: {t.control}; border: 1px solid {t.stroke}; border-bottom-color: {t.stroke_strong};
  border-radius: 4px; padding: 5px 14px; min-height: 20px;
}}
QPushButton:hover {{ background: {t.control_hover}; }}
QPushButton:pressed {{ background: {t.control_pressed}; color: {t.text2}; }}
QPushButton:disabled {{ color: {t.text3}; border-bottom-color: {t.stroke}; }}
QPushButton:checked {{ background: {t.selected}; border-color: {t.stroke_strong}; font-weight: 600; }}
QPushButton#primary {{
  background: {t.accent}; color: {t.on_accent}; border: 1px solid {edge}; font-weight: 600; padding: 5px 20px;
}}
QPushButton#primary:hover {{ background: {acc_hover}; }}
QPushButton#primary:pressed {{ background: {acc_press}; }}
QPushButton#primary:disabled {{ background: {t.control}; color: {t.text3}; border: 1px solid {t.stroke}; }}
QPushButton#subtle {{ background: transparent; border: 1px solid transparent; }}
QPushButton#subtle:hover {{ background: {t.control_hover}; }}

QWidget#segbar {{ background: {t.control}; border: 1px solid {t.stroke}; border-radius: 6px; }}
QPushButton#seg {{
  background: transparent; border: 1px solid transparent; border-radius: 4px; padding: 4px 12px;
  color: {t.text2}; min-height: 18px;
}}
QPushButton#seg:hover {{ background: {t.control_hover}; color: {t.text}; }}
QPushButton#seg:checked {{ background: {t.selected}; color: {t.text}; border-color: {t.stroke}; font-weight: 600; }}

QWidget#tabbar {{ border-bottom: 1px solid {t.stroke}; }}
QPushButton#tab {{
  background: transparent; border: none; border-bottom: 3px solid transparent; border-radius: 0;
  padding: 7px 14px 7px 14px; color: {t.text2}; font-size: 10pt;
}}
QPushButton#tab:hover {{ color: {t.text}; }}
QPushButton#tab:checked {{ color: {t.text}; font-weight: 600; border-bottom: 3px solid {t.accent}; background: transparent; }}

QPushButton#chrome {{ background: transparent; border: none; border-radius: 0; padding: 0; min-width: 46px; min-height: 40px; }}
QPushButton#chrome:hover {{ background: {t.control_hover}; }}
QPushButton#chromeClose {{ background: transparent; border: none; border-radius: 0; padding: 0; min-width: 46px; min-height: 40px; }}
QPushButton#chromeClose:hover {{ background: #C42B1C; }}
QPushButton#swatch {{ border-radius: 12px; padding: 0; min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px; }}
QPushButton#swatch:checked {{ border: 2px solid {t.text}; }}

QSlider {{ min-height: 22px; }}
QSlider::groove:horizontal {{ height: 4px; background: {t.track}; border-radius: 2px; }}
QProgressBar {{ background: {t.track}; border: none; border-radius: 3px; }}
QProgressBar::chunk {{ background: {t.accent}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {t.accent}; border-radius: 2px; }}
QSlider::handle:horizontal {{
  width: 20px; height: 20px; margin: -8px 0; border-radius: 10px; border: 1px solid {t.stroke};
  background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                              stop:0 {t.accent}, stop:0.46 {t.accent}, stop:0.52 {t.thumb}, stop:1 {t.thumb});
}}
QSlider::handle:horizontal:hover {{
  background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
                              stop:0 {t.accent}, stop:0.56 {t.accent}, stop:0.62 {t.thumb}, stop:1 {t.thumb});
}}

QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox {{
  background: {t.control}; border: 1px solid {t.stroke}; border-bottom: 1px solid {t.stroke_strong};
  border-radius: 4px; padding: 4px 10px; min-height: 22px; selection-background-color: {t.accent};
  selection-color: {t.on_accent};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-bottom: 2px solid {t.accent}; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0; border: none; }}
QComboBox::drop-down {{ border: none; width: 28px; }}
QComboBox::down-arrow {{ image: url({chevron}); width: 12px; height: 12px; }}
QComboBox QAbstractItemView {{
  background: {t.card}; border: 1px solid {t.stroke}; border-radius: 6px; padding: 4px;
  selection-background-color: {t.selected}; selection-color: {t.text}; outline: none;
}}

QCheckBox {{ spacing: 10px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 4px; border: 1px solid {t.stroke_strong}; background: {t.control}; }}
QCheckBox::indicator:hover {{ background: {t.control_hover}; }}
QCheckBox::indicator:checked {{ background: {t.accent}; border: 1px solid {t.accent}; image: url({check}); }}

QFrame#card {{ background: {t.card}; border: 1px solid {t.stroke}; border-radius: 8px; }}
QFrame#footer {{ background: {t.footer}; border: none; border-top: 1px solid {t.stroke}; }}

QTableWidget, QListWidget {{
  background: transparent; border: 1px solid {t.stroke}; border-radius: 6px; gridline-color: {t.stroke};
  selection-background-color: {t.selected}; selection-color: {t.text}; outline: none;
}}
QHeaderView {{ background: transparent; }}
QTableCornerButton::section {{ background: transparent; border: none; }}
QHeaderView::section {{
  background: transparent; border: none; border-bottom: 1px solid {t.stroke}; padding: 6px 8px;
  font-weight: 600; color: {t.text2};
}}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t.track}; border-radius: 3px; min-height: 30px; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {t.track}; border-radius: 3px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ width: 0; height: 0; background: none; }}
QToolTip {{ background: {t.card}; color: {t.text}; border: 1px solid {t.stroke}; border-radius: 4px; padding: 5px 8px; }}
QMenu {{ background: {t.card}; border: 1px solid {t.stroke}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 7px 24px 7px 14px; border-radius: 4px; }}
QMenu::item:selected {{ background: {t.selected}; }}
QMenu::separator {{ height: 1px; background: {t.stroke}; margin: 4px 8px; }}
QMenu::indicator {{ width: 14px; height: 14px; }}
"""


_QSS_CLASSIC = f"""
* {{ color: {TEXT}; font-family: "@FONT@", sans-serif; font-size: 10pt; }}
QWidget#glassRoot {{ background: transparent; }}
QLabel#title {{ font-size: 11pt; font-weight: 600; }}
QLabel#dim, QLabel.dim {{ color: {TEXT_DIM}; font-size: 9pt; }}
QLabel#section {{ color: {TEXT_DIM}; font-size: 8.5pt; font-weight: 600; letter-spacing: 1px; }}
QPushButton {{
  background: rgba(255,255,255,0.13); border: 1px solid rgba(255,255,255,0.30);
  border-top-color: rgba(255,255,255,0.55); border-bottom-color: rgba(255,255,255,0.16);
  border-radius: 15px; padding: 6px 15px; min-height: 18px;
}}
QPushButton:hover {{ background: rgba(255,255,255,0.22); }}
QPushButton:pressed {{ background: rgba(255,255,255,0.08); }}
QPushButton:checked {{
  background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(255,138,92,0.85), stop:1 rgba(255,79,139,0.85));
  border: 1px solid rgba(255,255,255,0.55);
}}
QPushButton#primary {{
  background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {ACCENT_A}, stop:0.55 {ACCENT_B}, stop:1 {ACCENT_C});
  border: 1px solid rgba(255,255,255,0.55); border-top-color: rgba(255,255,255,0.9);
  font-weight: 600; padding: 7px 20px; border-radius: 16px;
}}
QPushButton#primary:hover {{ border: 1px solid #ffffff; }}
QPushButton#chrome {{ background: transparent; border: none; padding: 2px 8px; font-size: 11pt; border-radius: 6px; }}
QPushButton#chrome:hover {{ background: rgba(255,80,100,0.6); }}
QPushButton#swatch {{ border-radius: 12px; padding: 0; min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px; }}
QPushButton#swatch:checked {{ border: 2px solid #ffffff; }}
QSlider::groove:horizontal {{ height: 4px; background: rgba(255,255,255,0.22); border-radius: 2px; }}
QSlider::sub-page:horizontal {{
  background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {ACCENT_A}, stop:0.5 {ACCENT_B}, stop:1 {ACCENT_C}); border-radius: 2px;
}}
QSlider::handle:horizontal {{
  background: #ffffff; width: 14px; height: 14px; margin: -6px 0; border-radius: 7px;
  border: 1px solid rgba(0,0,0,0.15);
}}
QSpinBox, QLineEdit, QComboBox {{
  background: rgba(0,0,0,0.16); border: 1px solid rgba(255,255,255,0.22);
  border-bottom-color: rgba(255,255,255,0.40);
  border-radius: 10px; padding: 4px 8px; selection-background-color: {ACCENT_B};
}}
QLineEdit:focus, QSpinBox:focus {{ border: 1px solid rgba(255,255,255,0.7); }}
QFrame#card {{ background: rgba(255,255,255,0.07); border: 1px solid rgba(255,255,255,0.14); border-radius: 14px; }}
QLabel#big {{ font-size: 17pt; font-weight: 700; }}
QLabel#good {{ color: #8dffb8; font-weight: 600; }}
QLabel#warn {{ color: #ffd36b; font-weight: 600; }}
QComboBox QAbstractItemView {{ background: #2a2438; border: 1px solid rgba(255,255,255,0.25); }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 5px; border: 1px solid rgba(255,255,255,0.5); background: rgba(255,255,255,0.1); }}
QCheckBox::indicator:checked {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {ACCENT_A}, stop:1 {ACCENT_B}); }}
QTableWidget {{ background: rgba(0,0,0,0.12); border: 1px solid rgba(255,255,255,0.18); border-radius: 8px; gridline-color: rgba(255,255,255,0.08); }}
QHeaderView {{ background: transparent; }}
QTableCornerButton::section {{ background: transparent; border: none; }}
QHeaderView::section {{ background: rgba(255,255,255,0.10); border: none; padding: 4px; font-weight: 600; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: rgba(255,255,255,0.3); border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QToolTip {{ background: #2a2438; color: white; border: 1px solid rgba(255,255,255,0.3); border-radius: 6px; padding: 4px; }}
QMenu {{ background: #2a2438; border: 1px solid rgba(255,255,255,0.25); border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 5px; }}
QMenu::item:selected {{ background: rgba(255,255,255,0.15); }}
"""

_QSS_CLASSIC_EXTRA = f"""
QProgressBar {{ background: rgba(255,255,255,0.18); border: none; border-radius: 3px; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #5b8cff, stop:1 #c86bff); border-radius: 3px; }}
QLabel#heading {{ font-size: 13pt; font-weight: 600; }}
QWidget#segbar {{ background: transparent; border: none; }}
QPushButton#seg {{ border-radius: 15px; padding: 6px 15px; }}
QPushButton#seg:checked {{
  background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(255,138,92,0.85), stop:1 rgba(255,79,139,0.85));
  border: 1px solid rgba(255,255,255,0.55);
}}
QWidget#tabbar {{ background: transparent; border: none; }}
QPushButton#tab {{ border-radius: 15px; padding: 6px 15px; }}
QPushButton#tab:checked {{
  background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 rgba(255,138,92,0.85), stop:1 rgba(255,79,139,0.85));
  border: 1px solid rgba(255,255,255,0.55);
}}
QPushButton#subtle {{ background: transparent; border: 1px solid transparent; }}
QPushButton#chromeClose {{ background: transparent; border: none; padding: 2px 8px; border-radius: 6px; }}
QPushButton#chromeClose:hover {{ background: rgba(255,80,100,0.6); }}
QFrame#footer {{ background: transparent; border: none; }}
QDoubleSpinBox {{
  background: rgba(0,0,0,0.16); border: 1px solid rgba(255,255,255,0.22);
  border-bottom-color: rgba(255,255,255,0.40); border-radius: 10px; padding: 4px 8px;
}}
QListWidget {{ background: rgba(0,0,0,0.12); border: 1px solid rgba(255,255,255,0.18); border-radius: 8px; }}
"""


def qss() -> str:
    """The stylesheet for the chosen look, with font families that are really installed."""
    from . import theme
    from .util import ui_family
    css = (_QSS_CLASSIC + _QSS_CLASSIC_EXTRA) if theme.classic() else _build_qss()
    return css.replace("@FONT@", ui_family(False)).replace("@DISPLAY@", ui_family(True))


def __getattr__(name):        # keep `glass.QSS` working
    if name == "QSS":
        return qss()
    raise AttributeError(name)



# ---------------------------------------------------------------- Windows 11 native frame
class _MARGINS(ctypes.Structure):
    _fields_ = [("l", ctypes.c_int), ("r", ctypes.c_int), ("t", ctypes.c_int), ("b", ctypes.c_int)]


def native_frame(hwnd: int, dark: bool = True) -> bool:
    """Frameless window that still gets Windows 11's rounded corners and soft system shadow
    (DWM draws both outside our client area, like on any normal app window)."""
    if sys.platform != "win32":
        return False
    try:
        dwm = ctypes.windll.dwmapi
        h = ctypes.c_void_p(hwnd)
        pref = ctypes.c_int(2)                                   # DWMWCP_ROUND
        dwm.DwmSetWindowAttribute(h, 33, ctypes.byref(pref), ctypes.sizeof(pref))
        on = ctypes.c_int(1 if dark else 0)                      # DWMWA_USE_IMMERSIVE_DARK_MODE
        dwm.DwmSetWindowAttribute(h, 20, ctypes.byref(on), ctypes.sizeof(on))
        m = _MARGINS(1, 1, 1, 1)                                 # 1 px of "frame" = system shadow
        dwm.DwmExtendFrameIntoClientArea(h, ctypes.byref(m))
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- Windows acrylic
class _ACCENT(ctypes.Structure):
    _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_uint), ("AnimationId", ctypes.c_int)]


class _WCAD(ctypes.Structure):
    _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.c_void_p), ("SizeOfData", ctypes.c_size_t)]


def enable_acrylic(hwnd: int, tint_abgr: int = 0x40281E28) -> bool:
    """Real blur-behind for a frameless translucent window (Windows 10/11).
    Returns False elsewhere so callers can fall back to a painted frost."""
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.windll.user32
        accent = _ACCENT(4, 2, tint_abgr, 0)  # 4 = ACCENT_ENABLE_ACRYLICBLURBEHIND
        data = _WCAD(19, ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p), ctypes.sizeof(accent))
        ok = bool(user32.SetWindowCompositionAttribute(ctypes.c_void_p(hwnd), ctypes.byref(data)))
        try:  # rounded corners on Windows 11
            pref = ctypes.c_int(2)  # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), 33,
                                                       ctypes.byref(pref), ctypes.sizeof(pref))
        except Exception:
            pass
        return ok
    except Exception:
        return False


def qimage_from_pil(im) -> QImage:
    im = im.convert("RGBA")
    data = im.tobytes("raw", "RGBA")
    qi = QImage(data, im.width, im.height, im.width * 4, QImage.Format_RGBA8888)
    return qi.copy()  # detach from the Python buffer


def pil_from_qimage(qi: QImage):
    from PIL import Image
    qi = qi.convertToFormat(QImage.Format_RGBA8888)
    ptr = qi.constBits()
    return Image.frombuffer("RGBA", (qi.width(), qi.height()), bytes(ptr), "raw", "RGBA",
                            qi.bytesPerLine(), 1).copy()


def rounded_rect_path(r: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(r, radius, radius)
    return path


# ---------------------------------------------------------------- live liquid backing
def exclude_from_capture(hwnd: int) -> bool:
    """Hide a window from screen capture (Windows 10 2004+), so we can re-capture what's
    behind it while it's visible. Skipped while recording demos (it would hide us)."""
    import os
    if sys.platform == "darwin":
        from . import platform_mac
        return platform_mac.OK      # macOS: we capture "below our window" instead
    if sys.platform != "win32" or os.environ.get("DRAGSHIFT_RECORDING"):
        return False
    try:
        return bool(ctypes.windll.user32.SetWindowDisplayAffinity(ctypes.c_void_p(hwnd), 0x11))
    except Exception:
        return False


from PySide6.QtCore import QObject, QRect, QRunnable, QThreadPool, QTimer, Signal  # noqa: E402


class _LiquidSig(QObject):
    done = Signal(int, QImage, bool)


class _LiquidJob(QRunnable):
    def __init__(self, serial, backdrop, w, h, radius, style):
        super().__init__()
        self.args = (serial, backdrop, w, h, radius, style)
        self.sig = _LiquidSig()

    def run(self):
        serial, backdrop, w, h, radius, style = self.args
        try:
            from . import liquid
            sdf = liquid.sdf_rounded_rect(w, h, 0.5, 0.5, w - 0.5, h - 0.5, radius)
            img, light = liquid.render(backdrop, sdf, style)
            try:
                self.sig.done.emit(serial, qimage_from_pil(img), light)
            except RuntimeError:
                pass  # window closed before the render finished
        except Exception:
            import traceback
            traceback.print_exc()


def grab_screen(x: int, y: int, w: int, h: int, below_window: int = 0):
    """Screen pixels under a rect (logical coords) as a PIL image of size w×h.
    macOS: native capture that leaves out the drag picture (and `below_window` and above)."""
    if sys.platform == "darwin":
        from . import platform_mac
        if platform_mac.OK:
            im = platform_mac.capture(x, y, w, h, below_window)
            if im is not None:
                return im
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QGuiApplication
    scr = QGuiApplication.screenAt(QPoint(x + w // 2, y + h // 2)) or QGuiApplication.primaryScreen()
    g = scr.geometry()
    try:
        shot = scr.grabWindow(0, x - g.x(), y - g.y(), w, h)
    except Exception:
        return None
    if shot.isNull():
        return None
    return pil_from_qimage(shot.toImage().scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))


class LiquidBacking(QObject):
    """Keeps a refracted snapshot of whatever is behind a rounded-rect window."""
    changed = Signal()

    def __init__(self, widget, radius: float, style=None):
        super().__init__(widget)
        from .liquid import GlassStyle
        self.w = widget
        self.radius = radius
        self.style = style or GlassStyle(blur=16, strength=14, bezel=20)
        self.image: QImage | None = None
        self.is_light = False
        self.excluded = False
        self._serial = 0
        self._debounce = QTimer(self, singleShot=True, interval=140, timeout=self.refresh)

    def capture_at(self, rect: QRect):
        """Grab the screen under `rect` (call before the window is shown, or when excluded)."""
        below = 0
        if sys.platform == "darwin" and self.w.isVisible():
            from . import platform_mac
            below = platform_mac.window_number(self.w)
        pil = grab_screen(rect.x(), rect.y(), rect.width(), rect.height(), below)
        if pil is None:
            return
        self._serial += 1
        job = _LiquidJob(self._serial, pil, rect.width(), rect.height(), self.radius, self.style)
        from .util import keep, release
        job.sig.done.connect(lambda *a, j=job: (release(j), self._done(*a)))
        QThreadPool.globalInstance().start(keep(job))

    def _done(self, serial, img, light):
        if serial == self._serial:
            self.image, self.is_light = img, light
            self.changed.emit()

    def moved(self):
        """Window moved/resized: refresh once it settles (only possible when excluded)."""
        if self.excluded:
            self.image = None if self.image is not None and self.image.size() != self.w.size() else self.image
            self._debounce.start()

    def refresh(self):
        if self.excluded and self.w.isVisible():
            self.capture_at(self.w.frameGeometry())


# ---------------------------------------------------------------- drag-image hiding
class hidden_drag_images:
    """While dragging, Windows draws a translucent picture of the file under the cursor.
    Hide it for the instant we capture the screen behind the menu, so it doesn't get frozen
    into the glass, then show it again. We hide every visible top-level window of another
    process that sits under the cursor and is layered + click-through (that is what drag
    images are), plus the known drag-image classes."""

    CLASSES = ("SysDragImage", "DragImageWindow", "DragWindow")
    WS_EX_LAYERED, WS_EX_TRANSPARENT = 0x00080000, 0x00000020

    def __init__(self, point=None):
        self.point = point
        self.hwnds: list[int] = []
        self.info: list[str] = []
        self.rects: list[tuple[int, int, int, int]] = []   # screen px, for inpainting

    def __enter__(self):
        if sys.platform != "win32":
            return self
        try:
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            user32.GetWindowLongW.restype = ctypes.c_long
            pt = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            mypid = os.getpid()
            found = []
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

            def cb(hwnd, _):
                h = ctypes.c_void_p(hwnd)
                if not user32.IsWindowVisible(h):
                    return True
                r = wintypes.RECT()
                user32.GetWindowRect(h, ctypes.byref(r))
                near = r.left - 40 <= pt.x <= r.right + 40 and r.top - 40 <= pt.y <= r.bottom + 40
                if not near or (r.right - r.left) > 900 or (r.bottom - r.top) > 900:
                    return True
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
                if pid.value == mypid:
                    return True
                buf = ctypes.create_unicode_buffer(64)
                user32.GetClassNameW(h, buf, 64)
                ex = user32.GetWindowLongW(h, -20)  # GWL_EXSTYLE
                drag_like = (ex & self.WS_EX_LAYERED) and (ex & self.WS_EX_TRANSPARENT)
                if buf.value in self.CLASSES or drag_like:
                    found.append(hwnd)
                    self.rects.append((r.left, r.top, r.right, r.bottom))
                    self.info.append(f"{buf.value} ex=0x{ex & 0xffffffff:08x} {r.right - r.left}x{r.bottom - r.top}")
                return True
            user32.EnumWindows(WNDENUMPROC(cb), 0)
            for h in found:
                user32.ShowWindow(ctypes.c_void_p(h), 0)  # SW_HIDE
            self.hwnds = found
            if found:
                ctypes.windll.gdi32.GdiFlush()
                ctypes.windll.dwmapi.DwmFlush()  # wait for the compositor to drop them
                ctypes.windll.dwmapi.DwmFlush()
        except Exception as e:
            self.info.append(f"error: {e}")
        return self

    def __exit__(self, *exc):
        if self.hwnds:
            try:
                for h in self.hwnds:
                    ctypes.windll.user32.ShowWindow(ctypes.c_void_p(h), 8)  # SW_SHOWNA
            except Exception:
                pass
        return False


def inpaint_rects(im, rects, pad: int = 6):
    """Fill rectangles of a PIL image from their surroundings (normalised convolution):
    a smooth, colour-matched patch — invisible once refracted and blurred by the glass."""
    import numpy as np
    from PIL import Image, ImageFilter
    if not rects:
        return im
    rgb = im.convert("RGB")
    w, h = rgb.size
    mask = Image.new("L", (w, h), 255)
    from PIL import ImageDraw
    d = ImageDraw.Draw(mask)
    any_hit = False
    for (x0, y0, x1, y1) in rects:
        x0, y0, x1, y1 = max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)
        if x1 > x0 and y1 > y0:
            d.rectangle((x0, y0, x1, y1), fill=0)
            any_hit = True
    if not any_hit:
        return im
    a = np.asarray(rgb, np.float32)
    m = np.asarray(mask, np.float32)[..., None] / 255
    radius = 28
    num = np.asarray(Image.fromarray(np.clip(a * m, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius)), np.float32)
    den = np.asarray(mask.filter(ImageFilter.GaussianBlur(radius)), np.float32)[..., None] / 255
    fill = num / np.maximum(den, 1e-3)
    fill = np.asarray(Image.fromarray(np.clip(fill, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), np.float32)
    # feather the seam: the glass bezel magnifies any hard edge into a visible line
    soft = np.asarray(mask.filter(ImageFilter.GaussianBlur(12)), np.float32)[..., None] / 255
    soft = np.minimum(soft, m)  # never let the drag picture bleed back in
    out = a * soft + fill * (1 - soft)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------- no-compositor mode (XFCE etc.)
_NO_COMP = None


def no_compositor() -> bool:
    """Linux/X11 without a compositing manager: translucency would render black, so glass
    surfaces are cut to their exact shape with a window mask instead (XShape)."""
    global _NO_COMP
    if _NO_COMP is None:
        _NO_COMP = False
        if sys.platform.startswith("linux") and not os.environ.get("QT_QPA_PLATFORM", "").startswith("offscreen"):
            try:
                from . import platform_linux
                _NO_COMP = not platform_linux.composited()
            except Exception:
                _NO_COMP = False
    return _NO_COMP


def apply_shape(widget, path: QPainterPath):
    """Clip a top-level window to `path` when there's no compositor (no-op otherwise)."""
    if not no_compositor():
        return
    from PySide6.QtGui import QRegion
    region = QRegion()
    for poly in path.simplified().toFillPolygons():   # one polygon per separate piece
        region = region.united(QRegion(poly.toPolygon()))
    widget.setMask(region)
