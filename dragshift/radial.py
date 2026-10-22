"""The radial drop menu that pops up under the cursor while you Shift+drag a file.

Look: frosted neutral glass (the screen behind it, captured the moment the menu opens, blurred
and toned to the Windows theme), slices with constant gaps, one accent: the slice under the
cursor. Below the ring a small switch shows which list is up and that Shift flips it."""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import (QEasingCurve, QObject, QPoint, QPointF, QRectF, QRunnable, Qt,
                            QThreadPool, QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import (QColor, QCursor, QFont, QFontMetrics, QGuiApplication, QImage, QPainter,
                           QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import QWidget

from . import glass, icons, theme
from .util import resolve_shortcuts, ui_family
from .i18n import tr


@dataclass
class Item:
    label: str
    glyph: str = ""
    run: Callable[[list[str]], None] | None = None
    key: str = ""
    hint: str = ""


SIZE = 460          # window size (room for shadow, hover pop and the Converter/Tools switch)
CX, CY = 230, 208   # ring centre = where the cursor is
R_OUT = 176         # outer radius of slices
R_IN = 66           # inner radius of slices
R_HUB = 58          # hub radius
GAP_PX = 3.0        # half the gap between slices, constant in pixels (not degrees)
GAP_DEG = 0.0       # (slices are cut in slice_path, so hit-testing has no dead angles)
CORNER = 10


def sector_path(c: QPointF, r0: float, r1: float, a0: float, a1: float) -> QPainterPath:
    """Annular sector between angles a0..a1 (degrees, Qt convention: 0 = 3 o'clock, CCW)."""
    path = QPainterPath()
    outer = QRectF(c.x() - r1, c.y() - r1, 2 * r1, 2 * r1)
    inner = QRectF(c.x() - r0, c.y() - r0, 2 * r0, 2 * r0)
    path.arcMoveTo(outer, a0)
    path.arcTo(outer, a0, a1 - a0)
    path.arcTo(inner, a1, -(a1 - a0))
    path.closeSubpath()
    return path


def slice_path(c: QPointF, r0: float, r1: float, a0: float, a1: float, gap: float = GAP_PX) -> QPainterPath:
    """A slice with a gap of constant width to its neighbours (the gap is `gap` px on each side,
    so it doesn't widen towards the outside like a fixed angle would)."""
    g0, g1 = math.degrees(gap / r0), math.degrees(gap / r1)
    path = QPainterPath()
    outer = QRectF(c.x() - r1, c.y() - r1, 2 * r1, 2 * r1)
    inner = QRectF(c.x() - r0, c.y() - r0, 2 * r0, 2 * r0)
    path.arcMoveTo(outer, a0 + g1)
    path.arcTo(outer, a0 + g1, (a1 - a0) - 2 * g1)
    path.arcTo(inner, a1 - g0, -((a1 - a0) - 2 * g0))
    path.closeSubpath()
    return path


def angles(n: int, i: int) -> tuple[float, float]:
    span = 360.0 / n
    start = 90 + span / 2 - (i + 1) * span   # first petal centred at 12 o'clock, clockwise
    return start + GAP_DEG / 2, start + span - GAP_DEG / 2


# ---------------------------------------------------------------- background render
class _RenderSig(QObject):
    done = Signal(int, int, QImage, bool)   # serial, petal count, image, is_light


class _RenderJob(QRunnable):
    def __init__(self, serial: int, n: int, backdrop):
        super().__init__()
        self.serial, self.n, self.backdrop = serial, n, backdrop
        self.sig = _RenderSig()

    def run(self):
        try:
            from . import liquid
            c = SIZE / 2
            fields = [liquid.sdf_circle(SIZE, SIZE, c, c, R_HUB)]
            for i in range(self.n):
                a0, a1 = angles(self.n, i)
                fields.append(liquid.sdf_ring_sector(SIZE, SIZE, c, c, R_IN, R_OUT, a0, a1, CORNER))
            sdf = liquid.union(*fields)
            img, light = liquid.render(self.backdrop, sdf, liquid.GlassStyle())
            sh = liquid.shadow(sdf, spread=26, opacity=0.42 if light else 0.30, offset=(0, 8))
            sh.alpha_composite(img)
            try:
                self.sig.done.emit(self.serial, self.n, glass.qimage_from_pil(sh), light)
            except RuntimeError:
                pass
        except Exception:  # pragma: no cover - fall back to the painted glass
            import traceback
            traceback.print_exc()


class RadialMenu(QWidget):
    activated = Signal(object, list)     # Item, paths
    dismissed = Signal()

    def __init__(self, build_rings: Callable[[list[str]], dict[str, list[Item]]],
                 describe: Callable[[list[str]], str]):
        super().__init__(None)
        self.build_rings = build_rings
        self.describe = describe
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint |
                            Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.resize(SIZE, SIZE)

        self.paths: list[str] = []
        self.rings: dict[str, list[Item]] = {}
        self.ring_names: list[str] = []
        self.ring_idx = 0
        self.hover = -1          # petal index, -2 = hub, -1 = none
        self.cursor_pos = QPointF(CX, CY)
        self.hub_text = ""
        self.backdrop: QPixmap | None = None     # blurred, for the instant fallback
        self._raw_backdrop = None                 # PIL image for the liquid renderer
        self.liquid: dict[int, QImage] = {}       # petal count -> rendered glass
        self.is_light = False
        self._serial = 0
        self.got_drag = False
        self.hub_armed = False
        self.click_mode = False  # opened from tray/menu instead of a drag
        self._t = 1.0            # pop-in animation 0..1
        self._swap = 1.0         # ring-swap animation 0..1
        self.spring: list[float] = []   # per-petal hover amount 0..1 (eased every frame)
        self.hub_spring = 0.0

        self.anim = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=190,
                                      easingCurve=QEasingCurve.OutBack)
        self.anim.valueChanged.connect(self._set_t)
        self.swap_anim = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=220,
                                           easingCurve=QEasingCurve.OutCubic)
        self.swap_anim.valueChanged.connect(self._set_swap)
        self.hub_timer = QTimer(self, singleShot=True, interval=420, timeout=self.next_ring)
        self.frame = QTimer(self, interval=16, timeout=self._tick)   # 60 fps springs

    # ------------------------------------------------------------ show / hide
    def popup(self, pos: QPoint | None = None, paths: list[str] | None = None):
        pos = pos or QCursor.pos()
        tl = pos - QPoint(CX, CY)
        scr = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        g = scr.geometry()
        tl.setX(min(max(tl.x(), g.left()), g.right() - SIZE))
        tl.setY(min(max(tl.y(), g.top()), g.bottom() - SIZE))
        # snapshot what's underneath *before* we appear
        self._serial += 1
        self.liquid = {}
        try:
            if sys.platform == "darwin":
                # macOS captures "below the drag window": the drag picture never gets in
                raw = glass.grab_screen(tl.x(), tl.y(), SIZE, SIZE)
                if raw is None:
                    raise RuntimeError("capture failed")
                from . import platform_mac
                print("menu: mac windows at cursor:", "; ".join(platform_mac.LAST_SWEEP), flush=True)
                if self.got_drag or paths is None:
                    # belt and braces: Finder's drag picture (icon + name label) sits on the
                    # cursor; erase that area — it ends up under the hub, blurred anyway
                    cx, cy = pos.x() - tl.x(), pos.y() - tl.y()
                    raw = glass.inpaint_rects(raw, [(cx - 70, cy - 64, cx + 70, cy + 64)])
                shot = QPixmap.fromImage(glass.qimage_from_pil(raw))
            else:
                with glass.hidden_drag_images() as hid:
                    shot = scr.grabWindow(0, tl.x() - g.left(), tl.y() - g.top(), SIZE, SIZE)
                if hid.hwnds:
                    print(f"menu: hid {len(hid.hwnds)} drag image(s) during capture: {'; '.join(hid.info)}", flush=True)
                elif hid.info:
                    print(f"menu: drag-image sweep: {'; '.join(hid.info)}", flush=True)
                raw = glass.pil_from_qimage(
                    shot.toImage().scaled(SIZE, SIZE, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
                if sys.platform.startswith("linux") and paths is None:
                    # X11 drag icons (Thunar/GTK) sit on the cursor: erase that patch
                    cx, cy = pos.x() - tl.x(), pos.y() - tl.y()
                    hid.rects = [(pos.x() - 60, pos.y() - 60, pos.x() + 60, pos.y() + 60)]
                if hid.rects:
                    # belt and braces: erase where the drag picture was, in case it was captured anyway
                    k = SIZE / max(1, shot.width())
                    local = [(int((x0 - tl.x()) * k), int((y0 - tl.y()) * k), int((x1 - tl.x()) * k), int((y1 - tl.y()) * k))
                             for (x0, y0, x1, y1) in hid.rects]
                    raw = glass.inpaint_rects(raw, local)
                    shot = QPixmap.fromImage(glass.qimage_from_pil(raw))
            self._raw_backdrop = raw
            self.backdrop = glass.blur_pixmap(shot, 24)
        except Exception:
            self.backdrop = None
            self._raw_backdrop = None
        self.move(tl)
        self.hover = -1
        self.got_drag = False
        self.hub_armed = False  # drags start on the hub; don't flip until they leave it
        self.click_mode = paths is not None
        early = []
        if paths is None and sys.platform == "darwin":
            from . import platform_mac
            early = platform_mac.drag_files()
            if early:
                print(f"menu: {len(early)} file(s) from the drag pasteboard", flush=True)
        if paths is not None:
            self._load(paths)
        elif early:
            self._load(early)           # slices show at once; drop still comes via dragEnter
        else:
            self.paths, self.rings, self.ring_names = [], {}, []
            self.hub_text = tr("Drop here")
            for n in (4, 7):  # most common rings: render speculatively
                self._render(n)
        self._t = 0.0
        self._shape()
        self.show()
        self.raise_()
        self.anim.start()
        self.frame.start()
        if self.click_mode:
            # behave like a popup: a click anywhere outside dismisses it
            QTimer.singleShot(0, self.grabMouse)

    def close_menu(self):
        if self.isVisible():
            self.hide()
            self.frame.stop()
            self.hub_timer.stop()
            self.dismissed.emit()

    def hideEvent(self, e):
        self.frame.stop()
        if QWidget.mouseGrabber() is self:
            self.releaseMouse()
        super().hideEvent(e)

    def _render(self, n: int):
        return  # the redesigned ring is frosted directly from the blurred capture (no refraction pass)
        if n <= 0 or n in self.liquid or self._raw_backdrop is None:
            return
        self.liquid[n] = QImage()  # placeholder: in flight
        job = _RenderJob(self._serial, n, self._raw_backdrop)
        from .util import keep, release
        job.sig.done.connect(lambda *a, j=job: (release(j), self._rendered(*a)))
        QThreadPool.globalInstance().start(keep(job))

    def _rendered(self, serial: int, n: int, img: QImage, light: bool):
        if serial == self._serial:
            self.liquid[n] = img
            self.is_light = light
            self.update()

    def _load(self, paths: list[str]):
        paths = resolve_shortcuts(paths)
        self.paths = paths
        self.rings = {k: v for k, v in self.build_rings(paths).items() if v}
        self.ring_names = list(self.rings)
        self.ring_idx = 0
        self.hub_text = self.describe(paths)
        for items in self.rings.values():
            self._render(len(items))
        self.spring = [0.0] * len(self.items)
        self._shape()
        self.update()

    def _shape(self):
        """No compositor (XFCE etc.): cut the window to the menu's outline."""
        if not glass.no_compositor():
            return
        c = QPointF(CX, CY)
        path = QPainterPath()
        path.addEllipse(c, R_HUB + 2, R_HUB + 2)
        n = len(self.items) or 0
        if n:
            for i in range(n):
                a0, a1 = angles(n, i)
                path = path.united(sector_path(c, R_IN - 2, R_OUT + 14, a0 - 1, a1 + 1))
        else:
            outer = QPainterPath()
            outer.addEllipse(c, R_OUT + 14, R_OUT + 14)
            path = path.united(outer)       # united, not added: odd-even fill would punch a hole
        glass.apply_shape(self, path)

    def next_ring(self):
        if len(self.ring_names) > 1:
            self.ring_idx = (self.ring_idx + 1) % len(self.ring_names)
            self.hover = -1
            # one flip per visit: resting on the hub must not keep cycling the rings
            # (Windows keeps sending drag-move events while the cursor is still, and
            # each one re-entered the hub and restarted the timer)
            self.hub_armed = False
            self.hub_timer.stop()
            self.spring = [0.0] * len(self.items)
            self._swap = 0.0
            self.swap_anim.start()
            self._shape()
            self.update()

    def _set_t(self, v):
        self._t = float(v)
        self.update()

    def _set_swap(self, v):
        self._swap = float(v)
        self.update()

    def _tick(self):
        moved = False
        for i in range(len(self.spring)):
            target = 1.0 if i == self.hover else 0.0
            v = self.spring[i]
            nv = v + (target - v) * 0.32
            if abs(nv - target) < 0.003:
                nv = target
            if nv != v:
                self.spring[i] = nv
                moved = True
        ht = 1.0 if self.hover == -2 else 0.0
        nh = self.hub_spring + (ht - self.hub_spring) * 0.3
        if abs(nh - ht) < 0.003:
            nh = ht
        if nh != self.hub_spring:
            self.hub_spring = nh
            moved = True
        if moved:
            self.update()

    # ------------------------------------------------------------ geometry
    @property
    def items(self) -> list[Item]:
        if not self.ring_names:
            return []
        return self.rings[self.ring_names[self.ring_idx]]

    def _angles(self, n: int, i: int) -> tuple[float, float]:
        return angles(n, i)

    def hit(self, pos: QPointF) -> int:
        c = QPointF(CX, CY)
        dx, dy = pos.x() - c.x(), c.y() - pos.y()
        d = math.hypot(dx, dy)
        if d <= R_HUB + 4:
            return -2
        if d > R_OUT + 30 or not self.items:
            return -1
        ang = math.degrees(math.atan2(dy, dx)) % 360
        n = len(self.items)
        rel = (90 + 180.0 / n - ang) % 360
        return int(rel // (360.0 / n)) % n

    def _set_hover(self, h: int, pos: QPointF | None = None):
        if pos is not None:
            self.cursor_pos = QPointF(pos)
        if h != self.hover:
            self.hover = h
            if h >= 0:
                self.hub_armed = True  # visited a petal: hovering the hub may now flip rings
            if h == -2 and self.hub_armed and len(self.ring_names) > 1:
                self.hub_timer.start()
            else:
                self.hub_timer.stop()
        self.update()

    # ------------------------------------------------------------ drag & drop
    @staticmethod
    def _local_paths(md) -> list[str]:
        if not md.hasUrls():
            return []
        return [u.toLocalFile() for u in md.urls() if u.isLocalFile() and u.toLocalFile()]

    def dragEnterEvent(self, e):
        paths = self._local_paths(e.mimeData())
        if not paths:
            e.ignore()
            return
        self.got_drag = True
        if resolve_shortcuts(paths) != self.paths:
            self._load(paths)
        e.setDropAction(Qt.CopyAction)  # never let a Shift(=move) drop delete the source
        e.accept()

    def dragMoveEvent(self, e):
        self._set_hover(self.hit(e.position()), e.position())
        e.setDropAction(Qt.CopyAction)
        e.accept()

    def dragLeaveEvent(self, e):
        self._set_hover(-1)

    def dropEvent(self, e):
        idx = self.hit(e.position())
        items = self.items
        if 0 <= idx < len(items):
            e.setDropAction(Qt.CopyAction)
            e.accept()
            item, paths = items[idx], list(self.paths)
            self.hide()
            # return to Explorer's drag loop immediately; do the work after
            QTimer.singleShot(0, lambda: self.activated.emit(item, paths))
        else:
            e.ignore()
            self.close_menu()

    # ------------------------------------------------------------ click mode
    def mouseMoveEvent(self, e):
        if self.click_mode:
            self._set_hover(self.hit(e.position()), e.position())

    def mouseReleaseEvent(self, e):
        if not self.click_mode:
            return
        if e.button() == Qt.RightButton:
            self.close_menu()
            return
        idx = self.hit(e.position())
        if idx == -2:
            self.next_ring()
        elif 0 <= idx < len(self.items):
            item, paths = self.items[idx], list(self.paths)
            self.hide()
            QTimer.singleShot(0, lambda: self.activated.emit(item, paths))
        else:
            self.close_menu()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close_menu()
        elif e.key() in (Qt.Key_Tab, Qt.Key_Shift):
            self.next_ring()

    def leaveEvent(self, e):
        if self.click_mode:
            self._set_hover(-1)

    # ------------------------------------------------------------ painting
    # ------------------------------------------------------------ painting
    def paintEvent(self, e):
        t = theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        c = QPointF(CX, CY)
        k = self._t
        p.setOpacity(min(1.0, max(0.0, k * 1.6)))
        p.translate(c)
        sc = 0.86 + 0.14 * k
        p.scale(sc, sc)
        p.translate(-c)

        items = self.items
        n = len(items)
        self._paint_disc(p, c, t)
        rot = (1 - self._swap) * -18
        for i, it in enumerate(items):
            a0, a1 = angles(n, i)
            h = self.spring[i] if i < len(self.spring) else 0.0
            self._paint_slice(p, c, a0 + rot, a1 + rot, h, t)
        for i, it in enumerate(items):
            a0, a1 = angles(n, i)
            h = self.spring[i] if i < len(self.spring) else 0.0
            self._petal_label(p, c, it, (a0 + a1) / 2 + rot, (R_IN + R_OUT) / 2 + 4, h, t)
        if not n and self.paths:
            self._paint_unsupported(p, c, t)
        self._paint_hub(p, c, t)
        if len(self.ring_names) > 1:
            self._paint_switch(p, t)

    def _paint_disc(self, p: QPainter, c: QPointF, t):
        """Frosted, neutral glass: the blurred screen behind, toned down to the theme."""
        # soft shadow (the window is translucent, so we draw it ourselves)
        for i, a in enumerate((26, 18, 12, 7, 3)):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, a if t.dark else a // 2))
            p.drawEllipse(QPointF(c.x(), c.y() + 10), R_OUT + 4 + i * 4, R_OUT + 4 + i * 4)
        disc = QPainterPath()
        disc.addEllipse(c, R_OUT + 3, R_OUT + 3)
        p.save()
        p.setClipPath(disc)
        if self.backdrop is not None and not self.backdrop.isNull():
            p.drawPixmap(0, 0, self.backdrop)
            p.fillPath(disc, theme.qcolor(t.ring))
        else:
            solid = theme.qcolor(t.ring)
            solid.setAlphaF(0.96)
            p.fillPath(disc, solid)
        p.restore()
        p.setPen(QPen(theme.qcolor(t.ring_stroke), 1))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(c, R_OUT + 3, R_OUT + 3)

    def _paint_slice(self, p: QPainter, c: QPointF, a0: float, a1: float, h: float, t):
        mid = math.radians((a0 + a1) / 2)
        push = 6 * h
        path = slice_path(c, R_IN, R_OUT, a0, a1).translated(push * math.cos(mid), -push * math.sin(mid))
        p.setPen(QPen(theme.qcolor(t.ring_stroke), 1))
        p.setBrush(theme.qcolor(t.ring_slice))
        p.drawPath(path)
        if h > 0.001:
            acc = theme.qcolor(t.accent)
            acc.setAlphaF(min(1.0, h))
            p.setPen(Qt.NoPen)
            p.setBrush(acc)
            p.drawPath(path)

    def _petal_label(self, p: QPainter, c: QPointF, it: Item, ang: float, r: float, h: float, t):
        rad = math.radians(ang)
        r += 6 * h
        pt = QPointF(c.x() + r * math.cos(rad), c.y() - r * math.sin(rad))
        base = theme.qcolor(t.text)
        base.setAlphaF(0.88)
        on = theme.qcolor(t.on_accent)
        col = QColor(
            int(base.red() + (on.red() - base.red()) * h), int(base.green() + (on.green() - base.green()) * h),
            int(base.blue() + (on.blue() - base.blue()) * h), int(base.alpha() + (255 - base.alpha()) * h))
        p.save()
        p.setOpacity(p.opacity() * (0.2 + 0.8 * self._swap))
        n = max(1, len(self.items))
        max_w = min(100.0, 2 * r * math.sin(math.pi / n) + 4)   # the slice's width at the label
        if it.glyph in icons.PATHS:
            icons.draw(p, it.glyph, QRectF(pt.x() - 10, pt.y() - 22, 20, 20), col)
            f = QFont(ui_family(False))
            f.setPixelSize(12)
            f.setWeight(QFont.DemiBold if h > 0.5 else QFont.Medium)
            label = tr(it.label)
            lines = [label]
            if QFontMetrics(f).horizontalAdvance(label) > max_w and " " in label:
                lines = label.split(" ", 1)
            px = 12
            while px > 9 and max(QFontMetrics(f).horizontalAdvance(ln) for ln in lines) > max_w:
                px -= 0.5
                f.setPixelSize(int(px)) if float(px).is_integer() else f.setPointSizeF(px * 0.75)
            p.setFont(f)
            p.setPen(col)
            lh = QFontMetrics(f).height()
            for k, ln in enumerate(lines):
                p.drawText(QRectF(pt.x() - 50, pt.y() + 3 + k * (lh - 2), 100, lh), Qt.AlignHCenter | Qt.AlignTop, ln)
        else:   # a format (PNG, PDF…): the name is the icon
            f = QFont(ui_family(True))
            f.setPixelSize(16)
            f.setWeight(QFont.DemiBold)
            p.setFont(f)
            p.setPen(col)
            p.drawText(QRectF(pt.x() - 50, pt.y() - 11, 100, 22), Qt.AlignCenter, tr(it.label))
            # (its description shows in the hub while hovered: no truncated text in the slice)
        p.restore()

    def _paint_hub(self, p: QPainter, c: QPointF, t):
        p.setPen(QPen(theme.qcolor(t.ring_stroke), 1))
        p.setBrush(theme.qcolor(t.ring_hub))
        p.drawEllipse(c, R_HUB, R_HUB)
        items = self.items
        hov = items[self.hover] if 0 <= self.hover < len(items) else None
        if hov is not None:
            top, sub = tr(hov.label), tr(hov.hint or "")
        elif len(self.paths) == 1:
            top, sub = Path(self.paths[0]).name, self.hub_text
        else:
            top, sub = self.hub_text, ""
        w = 2 * R_HUB - 18
        f = QFont(ui_family(True))
        f.setPixelSize(14)
        f.setWeight(QFont.DemiBold)
        fm = QFontMetrics(f)
        top = fm.elidedText(top, Qt.ElideMiddle, int(w))
        f2 = QFont(ui_family(False))
        f2.setPixelSize(11)
        fm2 = QFontMetrics(f2)
        sub_rect = fm2.boundingRect(QRectF(0, 0, w, 60).toRect(), Qt.AlignHCenter | Qt.TextWordWrap, sub)
        sub_h = min(sub_rect.height(), fm2.lineSpacing() * 2) if sub else 0
        total = fm.height() + (2 + sub_h if sub else 0)
        y = c.y() - total / 2
        p.setFont(f)
        p.setPen(theme.qcolor(t.text))
        p.drawText(QRectF(c.x() - w / 2, y, w, fm.height()), Qt.AlignCenter, top)
        if sub:
            p.setFont(f2)
            p.setPen(theme.qcolor(t.text2))
            p.drawText(QRectF(c.x() - w / 2, y + fm.height() + 2, w, sub_h),
                       Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, sub)

    def _paint_switch(self, p: QPainter, t):
        """[Converter | Ferramentas]  Shift troca — which ring is showing, and how to flip it."""
        p.save()
        p.resetTransform()
        p.setOpacity(min(1.0, max(0.0, self._t * 1.6)))
        f = QFont(ui_family(False))
        f.setPixelSize(12)
        fb = QFont(f)
        fb.setWeight(QFont.DemiBold)
        fk = QFont(f)
        fk.setPixelSize(11)
        names = [tr(n) for n in self.ring_names]
        seg_w = [max(QFontMetrics(fb).horizontalAdvance(nm), QFontMetrics(f).horizontalAdvance(nm)) + 24 for nm in names]
        key, verb = "Shift", tr("flips")
        key_w = QFontMetrics(fk).horizontalAdvance(key) + 14
        verb_w = QFontMetrics(f).horizontalAdvance(verb)
        h = 32
        inner_w = sum(seg_w) + 2 * (len(names) - 1) + 4
        total = 6 + inner_w + 12 + key_w + 6 + verb_w + 10
        x0, y0 = CX - total / 2, CY + R_OUT + 18
        box = QRectF(x0, y0, total, h)
        bg = theme.qcolor(t.card)
        bg.setAlphaF(0.94)
        p.setPen(QPen(theme.qcolor(t.ring_stroke), 1))
        p.setBrush(bg)
        p.drawRoundedRect(box, 8, 8)
        tray = QRectF(x0 + 6, y0 + 4, inner_w, h - 8)
        p.setPen(Qt.NoPen)
        p.setBrush(theme.qcolor(t.control))
        p.drawRoundedRect(tray, 6, 6)
        x = tray.left() + 2
        for i, (nm, w) in enumerate(zip(names, seg_w)):
            r = QRectF(x, tray.top() + 2, w, tray.height() - 4)
            if i == self.ring_idx:
                p.setBrush(theme.qcolor(t.selected))
                p.drawRoundedRect(r, 4, 4)
                p.setFont(fb)
                p.setPen(theme.qcolor(t.text))
            else:
                p.setFont(f)
                p.setPen(theme.qcolor(t.text2))
            p.drawText(r, Qt.AlignCenter, nm)
            p.setPen(Qt.NoPen)
            x += w + 2
        kx = tray.right() + 12
        kr = QRectF(kx, y0 + 7, key_w, h - 14)
        p.setPen(QPen(theme.qcolor(t.stroke_strong), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(kr, 4, 4)
        p.setFont(fk)
        p.setPen(theme.qcolor(t.text))
        p.drawText(kr, Qt.AlignCenter, key)
        p.setFont(f)
        p.setPen(theme.qcolor(t.text2))
        p.drawText(QRectF(kr.right() + 6, y0, verb_w + 4, h), Qt.AlignVCenter | Qt.AlignLeft, verb)
        p.restore()

    def _paint_unsupported(self, p: QPainter, c: QPointF, t):
        """Nothing to offer: say so across the ring, clear of the cursor and the drag image."""
        ext = Path(self.paths[0]).suffix.lower() or tr("this file")
        f = QFont(ui_family(True))
        f.setPixelSize(14)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(theme.qcolor(t.text))
        r_mid = (R_IN + R_OUT) / 2
        p.drawText(QRectF(c.x() - R_OUT, c.y() - r_mid - 20, 2 * R_OUT, 20), Qt.AlignCenter,
                   tr("Can't convert {ext}", ext=ext))
        f.setPixelSize(11)
        f.setWeight(QFont.Normal)
        p.setFont(f)
        p.setPen(theme.qcolor(t.text2))
        p.drawText(QRectF(c.x() - R_OUT, c.y() - r_mid + 2, 2 * R_OUT, 16), Qt.AlignCenter,
                   tr("Images · PDF · Office · Video · Audio"))
