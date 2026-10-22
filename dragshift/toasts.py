"""Liquid-glass notifications, bottom-right, stacked.

A card appears immediately while work runs (spinner), then turns into the result:
thumbnail, what changed (e.g. "2.4 MB → 610 KB · 75% smaller") and actions:
Open · Show in folder · Undo (moves the new files to the Recycle Bin)."""
from __future__ import annotations

import math
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import (QEasingCurve, QFile, QPointF, QRect, QRectF, Qt, QTimer, QUrl,
                            QVariantAnimation, Signal)
from PySide6.QtGui import (QColor, QCursor, QDesktopServices, QFont, QFontMetrics,
                           QGuiApplication, QPainter, QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import QWidget

from . import glass
from .util import ui_family
from .report import Result
from .i18n import plural, tr

W, H = 420, 104
GAP = 10
MARGIN = 18


def reveal(path: str | Path):
    path = str(path)
    if sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", path])
    else:
        from . import platform_linux
        if not platform_linux.reveal(path):
            subprocess.Popen(["xdg-open", str(Path(path).parent)])


def open_file(path: str | Path):
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def trash(paths: list[Path]) -> int:
    n = 0
    for p in paths:
        p = Path(p)
        if p.is_file():
            if QFile.moveToTrash(str(p)):
                n += 1
            else:
                try:
                    p.unlink()
                    n += 1
                except OSError:
                    pass
    # remove now-empty output folders we created (e.g. "x images/")
    for d in {Path(p).parent for p in paths}:
        try:
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
        except OSError:
            pass
    return n


def copy_files(paths) -> None:
    """Put the files on the clipboard: paste into Explorer, WhatsApp, Teams, e-mail…
    A single image also goes as picture data, for apps that only take images."""
    from PySide6.QtCore import QMimeData
    from PySide6.QtGui import QGuiApplication, QImage
    paths = [Path(p) for p in paths if Path(p).exists()]
    if not paths:
        return
    md = QMimeData()
    md.setUrls([QUrl.fromLocalFile(str(p.resolve())) for p in paths])
    if len(paths) == 1 and paths[0].suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"):
        img = QImage(str(paths[0]))
        if not img.isNull():
            md.setImageData(img)
    QGuiApplication.clipboard().setMimeData(md)


class ToastCard(QWidget):
    closed = Signal(object)

    def __init__(self, stack: "ToastStack"):
        super().__init__(None)
        self.stack = stack
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint |
                            Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.resize(W, H)
        self.state = "working"     # working | done | error | info
        self.copied = False
        self.title = ""
        self.detail = ""
        self.good = ""
        self.result: Result | None = None
        self.thumb: QPixmap | None = None
        self.spin = 0.0
        self.hover_btn = -1
        self.buttons: list[tuple[str, QRectF]] = []
        self._fade = 0.0
        from .liquid import GlassStyle
        self.liquid = glass.LiquidBacking(self, 20, GlassStyle(blur=8, strength=12, bezel=16))
        self.liquid.changed.connect(self.update)
        self.fade = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=200,
                                      easingCurve=QEasingCurve.OutCubic)
        self.fade.valueChanged.connect(self._set_fade)
        self.spinner = QTimer(self, interval=16, timeout=self._spin)
        self.life = QTimer(self, singleShot=True, timeout=self.dismiss)

    # ------------------------------------------------------------ state
    def working(self, title: str, detail: str = ""):
        self.state, self.title, self.detail = "working", title, detail
        self.spinner.start()
        self.update()

    def done(self, r: Result):
        self.spinner.stop()
        self.state, self.result = "done", r
        self.title, self.detail, self.good = r.title, r.detail, r.good
        self.thumb = None
        if r.thumb is not None:
            pm = QPixmap(str(r.thumb))
            if not pm.isNull():
                self.thumb = pm.scaled(64, 64, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        self.life.start(6500)
        self.update()

    def error(self, title: str, detail: str):
        self.spinner.stop()
        self.state, self.title, self.detail = "error", title, detail
        self.life.start(9000)
        self.update()

    def info(self, title: str, detail: str, ms: int = 4500):
        self.spinner.stop()
        self.state, self.title, self.detail = "info", title, detail
        self.life.start(ms)
        self.update()

    def _spin(self):
        self.spin = (self.spin + 7) % 360
        self.update()

    def _set_fade(self, v):
        self._fade = float(v)
        self.setWindowOpacity(self._fade)
        self.update()

    def appear(self, rect: QRect):
        self.setGeometry(rect)
        glass.apply_shape(self, glass.rounded_rect_path(QRectF(0, 0, W, H), 20))
        self.liquid.capture_at(rect)
        self.setWindowOpacity(0.0)
        self.show()
        self.liquid.excluded = glass.exclude_from_capture(int(self.winId()))
        self.fade.start()

    def relocate(self, rect: QRect):
        if rect == self.geometry():
            return
        self.setGeometry(rect)
        if self.liquid.excluded:
            self.liquid.refresh()
        else:
            self.liquid.image = None
            self.update()

    def dismiss(self):
        self.spinner.stop()
        self.life.stop()
        self.hide()
        self.closed.emit(self)
        self.deleteLater()

    # ------------------------------------------------------------ input
    def enterEvent(self, e):
        self.life.stop()

    def leaveEvent(self, e):
        self.hover_btn = -1
        if self.state in ("done", "info"):
            self.life.start(2500)
        elif self.state == "error":
            self.life.start(4000)
        self.update()

    def mouseMoveEvent(self, e):
        hb = -1
        for i, (_, r) in enumerate(self.buttons):
            if r.contains(e.position()):
                hb = i
        if hb != self.hover_btn:
            self.hover_btn = hb
            self.setCursor(Qt.PointingHandCursor if hb >= 0 else Qt.ArrowCursor)
            self.update()

    def mouseReleaseEvent(self, e):
        if QRectF(W - 30, 6, 24, 24).contains(e.position()):
            self.dismiss()
            return
        for name, r in self.buttons:
            if r.contains(e.position()):
                self._act(name)
                return
        if self.state == "done" and self.result and self.result.outs:
            reveal(self.result.outs[0])
            self.dismiss()

    def _act(self, name: str):
        r = self.result
        if not r:
            return
        if name == "Open":
            open_file(r.outs[0])
            self.dismiss()
        elif name == "Show":
            reveal(r.outs[0])
            self.dismiss()
        elif name == "Copy":
            copy_files(r.outs)
            self.copied = True
            self.update()
            QTimer.singleShot(1600, self._uncopy)
        elif name == "Undo":
            n = trash(r.outs)
            self.result = None
            self.thumb = None
            self.good = ""
            bin_name = tr("Recycle Bin" if sys.platform == "win32" else "Trash")
            self.info(tr("Undone"), plural(n, "Moved {n} file to the {bin}", "Moved {n} files to the {bin}", bin=bin_name), 2500)

    def _uncopy(self):
        self.copied = False
        self.update()

    # ------------------------------------------------------------ paint
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = glass.rounded_rect_path(r, 20)
        img = self.liquid.image
        err = self.state == "error"
        if img is not None and not img.isNull() and img.size() == self.size():
            p.drawImage(0, 0, img)
            tint = QColor(140, 30, 50, 150) if err else QColor(20, 16, 32, 120)
        else:
            tint = QColor(120, 30, 45, 230) if err else QColor(34, 27, 52, 232)
        glass.paint_glass(p, path, tint=tint, rainbow_alpha=170)

        x = 16
        # leading visual: spinner / thumbnail / icon
        lead = QRectF(14, (H - 56) / 2 - 8, 56, 56)
        if self.state == "working":
            p.setPen(QPen(QColor(255, 255, 255, 50), 4))
            p.drawEllipse(lead.center(), 16, 16)
            p.setPen(glass.iridescent_pen(lead.center(), 4, 255, angle=-self.spin))
            p.drawArc(QRectF(lead.center().x() - 16, lead.center().y() - 16, 32, 32), int(-self.spin * 16), 100 * 16)
            x = 82
        elif self.thumb is not None:
            clip = QPainterPath()
            clip.addRoundedRect(lead, 12, 12)
            p.save()
            p.setClipPath(clip)
            p.drawPixmap(lead.toRect(), self.thumb,
                         QRect((self.thumb.width() - 64) // 2, (self.thumb.height() - 64) // 2, 64, 64))
            p.restore()
            p.setPen(QPen(QColor(255, 255, 255, 110), 1))
            p.drawRoundedRect(lead, 12, 12)
            x = 82
        else:
            icon = {"done": "✓", "error": "!", "info": "↺"}.get(self.state, "✓")
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 34))
            p.drawEllipse(lead.center(), 22, 22)
            f = QFont(ui_family(False))
            f.setPixelSize(22)
            f.setBold(True)
            p.setFont(f)
            p.setPen(QColor("#8dffb8") if self.state == "done" else QColor("#ffd36b") if err else QColor(255, 255, 255))
            p.drawText(QRectF(lead.center().x() - 22, lead.center().y() - 22, 44, 44), Qt.AlignCenter, icon)
            x = 82

        tw = W - x - 34
        f = QFont(ui_family(True))
        f.setPixelSize(15)
        f.setBold(True)
        p.setFont(f)
        fm = QFontMetrics(f)
        title = fm.elidedText(self.title, Qt.ElideRight, int(tw))
        p.setPen(QColor(255, 255, 255))
        p.drawText(QRectF(x, 13, tw, 20), Qt.AlignLeft | Qt.AlignVCenter, title)
        # highlighted figure chip (e.g. "75% smaller")
        if self.good:
            gx = x + fm.horizontalAdvance(title) + 8
            f2 = QFont(ui_family(False))
            f2.setPixelSize(11)
            f2.setBold(True)
            fm2 = QFontMetrics(f2)
            gw = fm2.horizontalAdvance(self.good) + 14
            if gx + gw < W - 34:
                chip = QRectF(gx, 14, gw, 18)
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(80, 220, 140, 70))
                p.drawRoundedRect(chip, 9, 9)
                p.setFont(f2)
                p.setPen(QColor("#a8ffc9"))
                p.drawText(chip, Qt.AlignCenter, self.good)
        f.setPixelSize(12)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor(255, 255, 255, 200))
        p.drawText(QRectF(x, 35, tw + 18, 34), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,
                   QFontMetrics(f).elidedText(self.detail, Qt.ElideMiddle, int(tw * 1.9)))

        # close ×
        f.setPixelSize(13)
        p.setFont(f)
        p.setPen(QColor(255, 255, 255, 150))
        p.drawText(QRectF(W - 30, 6, 24, 24), Qt.AlignCenter, "✕")

        # action buttons
        self.buttons = []
        if self.state == "done" and self.result and self.result.outs:
            names = ["Open", "Copy", "Show", "Undo"]
            labels = {"Open": tr("Open"), "Copy": tr("Copied ✓") if self.copied else tr("Copy"),
                      "Show": tr("Show in folder"), "Undo": tr("Undo")}
            f.setPixelSize(12)
            f.setBold(True)
            p.setFont(f)
            fm = QFontMetrics(f)
            bx = x
            for i, nme in enumerate(names):
                bw = fm.horizontalAdvance(labels[nme]) + 22
                br = QRectF(bx, H - 32, bw, 22)
                self.buttons.append((nme, br))
                p.setPen(QPen(QColor(255, 255, 255, 120 if self.hover_btn == i else 60), 1))
                p.setBrush(QColor(255, 255, 255, 60 if self.hover_btn == i else 26))
                p.drawRoundedRect(br, 11, 11)
                p.setPen(QColor(255, 255, 255))
                p.drawText(br, Qt.AlignCenter, labels[nme])
                bx += bw + 6


class ToastStack:
    """Owns the cards and keeps them stacked bottom-right of the active screen."""

    def __init__(self):
        self.cards: list[ToastCard] = []

    def _screen_rect(self) -> QRect:
        scr = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        return scr.availableGeometry()

    def _slot(self, i: int) -> QRect:
        g = self._screen_rect()
        x = g.right() - W - MARGIN
        y = g.bottom() - MARGIN - H - i * (H + GAP)
        return QRect(x, y, W, H)

    def new(self) -> ToastCard:
        c = ToastCard(self)
        c.closed.connect(self._closed)
        while len(self.cards) >= 4:
            self.cards[0].dismiss()
        self.cards.append(c)
        c.appear(self._slot(len(self.cards) - 1))
        return c

    def _closed(self, card):
        if card in self.cards:
            self.cards.remove(card)
        for i, c in enumerate(self.cards):
            c.relocate(self._slot(i))

    # conveniences
    def info(self, title: str, detail: str, ms: int = 4500) -> ToastCard:
        c = self.new()
        c.info(title, detail, ms)
        return c

    def error(self, title: str, detail: str) -> ToastCard:
        c = self.new()
        c.error(title, detail)
        return c
