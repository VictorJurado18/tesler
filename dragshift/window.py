"""Windows 11 style window + an image view used by all editors."""
from __future__ import annotations

import sys

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QSizeGrip, QVBoxLayout,
                               QWidget)

from . import glass, icons, theme
from .i18n import tr

IS_WIN = sys.platform == "win32"


class GlassWindow(QWidget):
    """Top-level window, Windows 11 style: solid surface, our own title bar (icon, title,
    minimise, close), content in `self.body`, an optional footer band via `set_footer()`.
    (The name stays for compatibility; the glass look now lives only in the radial menu.)"""

    def __init__(self, title: str, parent=None, size=(760, 640)):
        super().__init__(parent)
        self.setWindowTitle(f"{title} — DragShift")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setObjectName("glassRoot")
        self.setStyleSheet(glass.QSS)
        self.resize(*size)
        self._drag: QPoint | None = None
        self._native = False
        self.classic = theme.classic()
        self.radius = 18 if self.classic else 8
        self._acrylic = False
        self.liquid = None
        if self.classic:   # the original liquid-glass window: translucent, refracts what's behind
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.liquid = glass.LiquidBacking(self, self.radius)
            self.liquid.changed.connect(self.update)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(*((8, 4, 8, 8) if self.classic else (1, 1, 1, 1)))
        outer.setSpacing(0)

        bar = QHBoxLayout()
        bar.setContentsMargins(14, 0, 0, 0)
        bar.setSpacing(0)
        mark = QLabel()
        mark.setFixedSize(16, 16)
        mark.setPixmap(app_mark(16))
        bar.addWidget(mark)
        bar.addSpacing(10)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("title")
        bar.addWidget(self.title_label)
        bar.addStretch(1)
        t = theme.current()
        for name, obj, tip, fn in (("minimize", "chrome", tr("Minimize"), self.showMinimized),
                                   ("close", "chromeClose", tr("Close (Esc)"), self.close)):
            b = QPushButton()
            b.setObjectName(obj)
            b.setFixedSize(46, 40)
            b.setIcon(icons.qicon(name, theme.qcolor(t.text2), 16))
            b.setIconSize(QSize(16, 16))
            b.setToolTip(tip)
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(fn)
            bar.addWidget(b)
        outer.addLayout(bar)

        holder = QWidget()
        self.body = QVBoxLayout(holder)
        self.body.setContentsMargins(28, 8, 28, 22)
        self.body.setSpacing(14)
        outer.addWidget(holder, 1)

        self.footer_host = QVBoxLayout()
        self.footer_host.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(self.footer_host)

        self.grip = QSizeGrip(self)
        self.grip.setFixedSize(14, 14)
        self.grip.setStyleSheet("background: transparent;")

    def set_footer(self, left=(), right=()) -> QFrame:
        """The dialog's bottom band: info on the left, buttons on the right."""
        frame = QFrame()
        frame.setObjectName("footer")
        row = QHBoxLayout(frame)
        row.setContentsMargins(28, 16, 28, 16)
        row.setSpacing(8)
        for w in left:
            row.addWidget(w) if isinstance(w, QWidget) else row.addLayout(w)
        row.addStretch(1)
        for w in right:
            row.addWidget(w)
        while self.footer_host.count():
            old = self.footer_host.takeAt(0).widget()
            if old is not None:
                old.deleteLater()
        self.footer_host.addWidget(frame)
        self.grip.raise_()
        return frame

    # ---- window behaviour
    def present(self):
        """Centre on the cursor's screen and show."""
        from PySide6.QtGui import QCursor, QGuiApplication
        scr = (QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()).availableGeometry()
        self.resize(min(self.width(), scr.width() - 40), min(self.height(), scr.height() - 40))
        self.move(scr.center() - self.rect().center())
        self._placed = True
        if self.classic:
            self.liquid.capture_at(self.frameGeometry())
        self.show()
        if sys.platform == "darwin":
            from . import platform_mac
            platform_mac.activate()   # menu-bar apps aren't brought forward automatically
        self.raise_()
        self.activateWindow()

    def showEvent(self, e):
        super().showEvent(e)
        if not getattr(self, "_placed", False):
            scr = self.screen().availableGeometry()
            self.move(scr.center() - self.rect().center())
            self._placed = True
            if self.classic:
                self.liquid.capture_at(self.frameGeometry())
        if self.classic:
            self.liquid.excluded = glass.exclude_from_capture(int(self.winId()))
        elif not self._native:
            self._native = glass.native_frame(int(self.winId()), theme.current().dark)

    def moveEvent(self, e):
        super().moveEvent(e)
        self._stale()

    def _stale(self):
        """Classic look: the glass shows what was behind; after a move, refresh or fall back."""
        if not self.classic or not self.isVisible():
            return
        if self.liquid.excluded:
            self.liquid.moved()
        elif self.liquid.image is not None:
            self.liquid.image = None
            if IS_WIN and not self._acrylic:
                self._acrylic = glass.enable_acrylic(int(self.winId()))
            self.update()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.grip.move(self.width() - self.grip.width() - 2, self.height() - self.grip.height() - 2)
        self.grip.raise_()
        if self.classic:
            glass.apply_shape(self, glass.rounded_rect_path(QRectF(self.rect()), self.radius))
            self._stale()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and e.position().y() < 40:
            handle = self.windowHandle()
            if handle is not None and handle.startSystemMove():
                return  # native move: snapping etc.
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def paintEvent(self, e):
        if self.classic:
            self._paint_classic()
            return
        t = theme.current()
        p = QPainter(self)
        p.fillRect(self.rect(), theme.qcolor(t.bg))
        if not self._native:   # no DWM frame (macOS/Linux/screenshots): draw the hairline ourselves
            p.setPen(theme.qcolor(t.stroke))
            p.drawRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))


def _classic_paint(self):
    """The original look: liquid glass over a capture of the screen behind the window."""
    p = QPainter(self)
    p.setRenderHint(QPainter.Antialiasing)
    r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
    path = glass.rounded_rect_path(r, self.radius)
    img = self.liquid.image
    if img is not None and not img.isNull() and img.size() == self.size():
        p.drawImage(0, 0, img)
        glass.paint_glass(p, path, tint=QColor(22, 17, 34, 150), rainbow_alpha=150)
    else:
        tint = QColor(30, 24, 44, 125) if self._acrylic else QColor(38, 30, 56, 228)
        glass.paint_glass(p, path, tint=tint, rainbow_alpha=150)


GlassWindow._paint_classic = _classic_paint


def app_mark(px: int) -> QPixmap:
    """The app's small mark: a ring with a dot, in the accent colour."""
    t = theme.current()
    dpr = 2.0
    pm = QPixmap(int(px * dpr), int(px * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    c = theme.qcolor(t.accent)
    from PySide6.QtGui import QPen
    p.setPen(QPen(c, px * 0.125))
    p.drawEllipse(QPointF(px / 2, px / 2), px * 0.35, px * 0.35)
    p.setPen(Qt.NoPen)
    p.setBrush(c)
    p.drawEllipse(QPointF(px / 2, px / 2), px * 0.125, px * 0.125)
    p.end()
    return pm


class ImageView(QWidget):
    """Shows an image scaled to fit, with helpers to map between widget and image coords.
    Subclasses override `paint_overlay` and the mouse hooks."""

    changed = Signal()

    def __init__(self, image: QImage, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 240)
        self.setMouseTracking(True)
        self.set_image(image)

    def set_image(self, image: QImage):
        self.image = image
        self.pix = QPixmap.fromImage(image)
        self.update()

    # geometry
    def target_rect(self) -> QRectF:
        if self.image.isNull():
            return QRectF()
        avail = QRectF(self.rect()).adjusted(8, 8, -8, -8)
        s = min(avail.width() / self.image.width(), avail.height() / self.image.height())
        w, h = self.image.width() * s, self.image.height() * s
        return QRectF(avail.center().x() - w / 2, avail.center().y() - h / 2, w, h)

    def scale(self) -> float:
        t = self.target_rect()
        return t.width() / max(1, self.image.width())

    def to_image(self, pt: QPointF) -> QPointF:
        t = self.target_rect()
        s = self.scale() or 1
        return QPointF((pt.x() - t.left()) / s, (pt.y() - t.top()) / s)

    def to_widget(self, pt: QPointF) -> QPointF:
        t = self.target_rect()
        s = self.scale()
        return QPointF(t.left() + pt.x() * s, t.top() + pt.y() * s)

    def rect_to_widget(self, r: QRectF) -> QRectF:
        a = self.to_widget(r.topLeft())
        b = self.to_widget(r.bottomRight())
        return QRectF(a, b)

    def clamp_image(self, pt: QPointF) -> QPointF:
        return QPointF(min(max(pt.x(), 0), self.image.width()), min(max(pt.y(), 0), self.image.height()))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.setRenderHint(QPainter.Antialiasing)
        t = self.target_rect()
        # subtle backing so transparent areas read as "nothing here"
        p.fillRect(t, theme.qcolor(theme.current().control))
        p.drawPixmap(t, self.pix, QRectF(self.pix.rect()))
        self.paint_overlay(p, t)

    def paint_overlay(self, p: QPainter, t: QRectF):
        pass
