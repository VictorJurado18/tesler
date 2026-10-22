"""Notifications, bottom-right, stacked (Windows 11 style cards).

A card appears immediately while work runs (indeterminate bar, or a real percentage for long
jobs), then turns into the result: thumbnail, what changed ("4,5 MB → 1,2 MB  73% menor") and
actions: Open · Copy · Show in folder · Undo (moves the new files to the Recycle Bin)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import (QEasingCurve, QFile, QRect, QRectF, Qt, QTimer, QUrl,
                            QVariantAnimation, Signal)
from PySide6.QtGui import (QCursor, QDesktopServices, QFont, QFontMetrics,
                           QGuiApplication, QPainter, QPainterPath, QPixmap)
from PySide6.QtWidgets import QWidget

from . import glass, icons, theme
from .util import ui_family
from .report import Result
from .i18n import plural, tr

W, H = 440, 104
GAP = 12
MARGIN = 18
HEIGHTS = {"working": 96, "done": 132, "error": 92, "info": 76}


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
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.resize(W, H)
        self.progress: float | None = None     # 0..1 when a job reports it, else indeterminate
        self._native = False
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
        self.fade = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=200,
                                      easingCurve=QEasingCurve.OutCubic)
        self.fade.valueChanged.connect(self._set_fade)
        self.spinner = QTimer(self, interval=16, timeout=self._spin)
        self.life = QTimer(self, singleShot=True, timeout=self.dismiss)

    # ------------------------------------------------------------ state
    def height_for_state(self) -> int:
        h = HEIGHTS.get(self.state, H)
        if self.state == "done" and not (self.result and self.result.outs):
            h = HEIGHTS["info"]
        return h

    def _restack(self):
        if self.height() != self.height_for_state():
            self.stack.restack()
        self.update()

    def working(self, title: str, detail: str = ""):
        self.state, self.title, self.detail = "working", title, detail
        self.spinner.start()
        self._restack()

    def set_progress(self, fraction: float | None):
        self.progress = None if fraction is None or fraction < 0 else max(0.0, min(1.0, float(fraction)))
        self.update()

    def done(self, r: Result):
        self.spinner.stop()
        self.state, self.result = "done", r
        self.title, self.detail, self.good = r.title, r.detail, r.good
        self.thumb = None
        if r.thumb is not None:
            pm = QPixmap(str(r.thumb))
            if not pm.isNull():
                self.thumb = pm.scaled(112, 112, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        self.life.start(6500)
        self._restack()

    def error(self, title: str, detail: str):
        self.spinner.stop()
        self.state, self.title, self.detail = "error", title, detail
        self.life.start(9000)
        self._restack()

    def info(self, title: str, detail: str, ms: int = 4500):
        self.spinner.stop()
        self.state, self.title, self.detail = "info", title, detail
        self.life.start(ms)
        self._restack()

    def _spin(self):
        self.spin = (self.spin + 7) % 360
        self.update()

    def _set_fade(self, v):
        self._fade = float(v)
        self.setWindowOpacity(self._fade)
        self.update()

    def appear(self, rect: QRect):
        self.setGeometry(rect)
        self.setWindowOpacity(0.0)
        self.show()
        if not self._native:
            self._native = glass.native_frame(int(self.winId()), theme.current().dark)
        self.fade.start()

    def relocate(self, rect: QRect):
        if rect != self.geometry():
            self.setGeometry(rect)
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
        if QRectF(W - 40, 8, 30, 30).contains(e.position()):
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
        elif name == "Undo" and callable(r.undo):
            try:
                n = r.undo()
            except Exception as e:  # noqa: BLE001
                self.result = None
                self.error(tr("Couldn't undo"), tr(str(e)))
                return
            self.result = None
            self.thumb = None
            self.good = ""
            self.info(tr("Undone"), plural(n, "Renamed {n} file back", "Renamed {n} files back"), 2500)
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
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        Wd, Hd = self.width(), self.height()
        p.fillRect(self.rect(), theme.qcolor(t.card))
        if not self._native:
            p.setPen(theme.qcolor(t.stroke))
            p.drawRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5))
        f_title = QFont(ui_family(False))
        f_title.setPixelSize(14)
        f_title.setWeight(QFont.DemiBold)
        f_body = QFont(ui_family(False))
        f_body.setPixelSize(12)
        text, text2, text3 = theme.qcolor(t.text), theme.qcolor(t.text2), theme.qcolor(t.text3)
        pad = 16
        x = pad

        # close
        icons.draw(p, "close", QRectF(Wd - 32, 14, 16, 16), text3)

        if self.state == "working":
            p.setFont(f_title)
            p.setPen(text)
            tw = Wd - pad * 2 - 70
            p.drawText(QRectF(x, 14, tw, 20), Qt.AlignLeft | Qt.AlignVCenter,
                       QFontMetrics(f_title).elidedText(self.title, Qt.ElideRight, int(tw)))
            if self.progress is not None:
                p.setFont(f_body)
                p.setPen(text2)
                p.drawText(QRectF(Wd - pad - 90, 14, 52, 20), Qt.AlignRight | Qt.AlignVCenter, f"{self.progress * 100:.0f}%")
            bar = QRectF(x, 46, Wd - pad * 2, 3)
            p.setPen(Qt.NoPen)
            p.setBrush(theme.qcolor(t.track))
            p.drawRoundedRect(bar, 1.5, 1.5)
            p.setBrush(theme.qcolor(t.accent))
            if self.progress is not None:
                p.drawRoundedRect(QRectF(bar.left(), bar.top(), bar.width() * self.progress, 3), 1.5, 1.5)
            else:   # indeterminate: a segment sweeping across
                k = (self.spin % 360) / 360
                seg = bar.width() * 0.3
                x0 = bar.left() - seg + (bar.width() + seg) * k
                p.save()
                p.setClipRect(bar)
                p.drawRoundedRect(QRectF(x0, bar.top(), seg, 3), 1.5, 1.5)
                p.restore()
            p.setFont(f_body)
            p.setPen(text2)
            p.drawText(QRectF(x, 60, Wd - pad * 2, 20), Qt.AlignLeft | Qt.AlignVCenter,
                       QFontMetrics(f_body).elidedText(self.detail, Qt.ElideMiddle, int(Wd - pad * 2)))
            self.buttons = []
            return

        # leading visual
        lead = QRectF(pad, pad, 56, 56)
        if self.state == "done" and self.thumb is not None:
            clip = QPainterPath()
            clip.addRoundedRect(lead, 6, 6)
            p.save()
            p.setClipPath(clip)
            src = QRectF((self.thumb.width() - 112) / 2, (self.thumb.height() - 112) / 2, 112, 112)
            p.drawPixmap(lead, self.thumb, src)
            p.restore()
            x = lead.right() + 14
        else:
            name, col = {"done": ("check-circle", theme.qcolor(t.success)),
                         "error": ("alert", theme.qcolor(t.danger_text)),
                         "info": ("info", text2)}.get(self.state, ("info", text2))
            if self.state == "info" and self.title == tr("Undone"):
                name = "undo"
            icons.draw(p, name, QRectF(pad, pad + 1, 20, 20), col)
            x = pad + 20 + 12

        tw = Wd - x - 40
        p.setFont(f_title)
        p.setPen(text)
        p.drawText(QRectF(x, pad - 1, tw, 22), Qt.AlignLeft | Qt.AlignVCenter,
                   QFontMetrics(f_title).elidedText(self.title, Qt.ElideRight, int(tw)))
        p.setFont(f_body)
        fm = QFontMetrics(f_body)
        if self.state == "done" and self.good:
            # what changed + the figure that matters, in the accent colour
            good_w = fm.horizontalAdvance(self.good) + 4
            detail = fm.elidedText(self.detail, Qt.ElideMiddle, int(tw - good_w - 10))
            p.setPen(text2)
            p.drawText(QRectF(x, pad + 22, tw, 18), Qt.AlignLeft | Qt.AlignVCenter, detail)
            fb = QFont(f_body)
            fb.setWeight(QFont.DemiBold)
            p.setFont(fb)
            p.setPen(theme.qcolor(t.accent_text))
            p.drawText(QRectF(x + fm.horizontalAdvance(detail) + 10, pad + 22, good_w + 8, 18),
                       Qt.AlignLeft | Qt.AlignVCenter, self.good)
            p.setFont(f_body)
        else:
            p.setPen(text2)
            lines = 2 if self.state == "error" else 1
            r = QRectF(x, pad + 23, tw + 20, 18 * lines)
            body = self.detail if lines > 1 else fm.elidedText(self.detail, Qt.ElideMiddle, int(tw + 20))
            p.drawText(r, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, body)
        if self.state == "done" and self.result and self.result.outs:
            p.setPen(text3)
            p.drawText(QRectF(x, pad + 40, tw, 18), Qt.AlignLeft | Qt.AlignVCenter, self._where())

        # actions
        self.buttons = []
        if self.state == "done" and self.result and self.result.outs:
            acts = [("Open", "open", tr("Open")),
                    ("Copy", "check" if self.copied else "copy", tr("Copied ✓").rstrip(" ✓") if self.copied else tr("Copy")),
                    ("Show", "folder", tr("Show in folder")),
                    ("Undo", "undo", tr("Undo"))]
            f_btn = QFont(f_body)
            p.setFont(f_btn)
            fmb = QFontMetrics(f_btn)
            bx, by = pad, Hd - pad - 28
            for i, (key, ic, label) in enumerate(acts):
                bw = fmb.horizontalAdvance(label) + 20 + 16 + 6
                br = QRectF(bx, by, bw, 28)
                self.buttons.append((key, br))
                subtle = key == "Undo"
                hov = self.hover_btn == i
                p.setPen(theme.qcolor(t.stroke) if (not t.dark and not subtle) else Qt.NoPen)
                if hov:
                    p.setBrush(theme.qcolor(t.control_hover))
                elif not subtle:
                    p.setBrush(theme.qcolor(t.control))
                else:
                    p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(br.adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)
                col = text2 if subtle and not hov else text
                icons.draw(p, ic, QRectF(br.left() + 10, br.top() + 6, 16, 16), col)
                p.setPen(col)
                p.drawText(QRectF(br.left() + 32, br.top(), bw - 36, 28), Qt.AlignLeft | Qt.AlignVCenter, label)
                bx += bw + 6

    def _where(self) -> str:
        from .util import CONFIG
        return tr("Saved in a “DragShift” subfolder") if CONFIG.get("output") == "folder" else tr("Saved next to the original")


class ToastStack:
    """Owns the cards and keeps them stacked bottom-right of the active screen."""

    def __init__(self):
        self.cards: list[ToastCard] = []

    def _screen_rect(self) -> QRect:
        scr = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        return scr.availableGeometry()

    def _slot(self, i: int, h: int | None = None) -> QRect:
        """Newest card at the bottom; each older one sits above, whatever its height."""
        g = self._screen_rect()
        x = g.right() - W - MARGIN
        y = g.bottom() - MARGIN
        heights = [c.height_for_state() for c in self.cards]
        if h is not None:
            heights[i] = h
        below = sum(heights[i + 1:]) + GAP * (len(heights) - 1 - i)
        hi = heights[i]
        return QRect(x, y - below - hi, W, hi)

    def new(self) -> ToastCard:
        c = ToastCard(self)
        c.closed.connect(self._closed)
        while len(self.cards) >= 4:
            self.cards[0].dismiss()
        self.cards.append(c)
        c.appear(self._slot(len(self.cards) - 1))
        self.restack()
        return c

    def restack(self):
        for i, c in enumerate(self.cards):
            c.relocate(self._slot(i))

    def _closed(self, card):
        if card in self.cards:
            self.cards.remove(card)
        self.restack()

    # conveniences
    def info(self, title: str, detail: str, ms: int = 4500) -> ToastCard:
        c = self.new()
        c.info(title, detail, ms)
        return c

    def error(self, title: str, detail: str) -> ToastCard:
        c = self.new()
        c.error(title, detail)
        return c
