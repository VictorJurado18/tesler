"""Persistent settings + the Settings and Welcome windows."""
from __future__ import annotations

import sys

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel,
                               QPushButton, QSlider, QVBoxLayout)

from . import __version__
from .util import CONFIG
from .window import GlassWindow
from .i18n import LANGUAGES, set_language, tr

i18n_applied = [False]

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
APP = "Tesler"
OLD_APP = "DragShift"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

DEFAULTS = {
    "output": "next",
    "jpg_quality": 90,
    "pdf_dpi": 200,
    "trigger": "shift",
    "welcomed": False,
    "language": "auto",
    "theme": "auto",
    "style": "native",
}


class Settings:
    def __init__(self):
        self.q = QSettings(APP, APP)
        if not self.q.allKeys():   # first run as Tesler: bring the Tesler settings along
            old = QSettings(OLD_APP, OLD_APP)
            for k in old.allKeys():
                self.q.setValue(k, old.value(k))
            migrate_autostart()

    def get(self, key):
        v = self.q.value(key, DEFAULTS[key])
        d = DEFAULTS[key]
        if isinstance(d, bool):
            return v in (True, "true", "1", 1)
        if isinstance(d, int):
            try:
                return int(v)
            except (TypeError, ValueError):
                return d
        return v

    def set(self, key, value):
        self.q.setValue(key, value)
        self.apply()

    def apply(self):
        for k in ("output", "jpg_quality", "pdf_dpi"):
            CONFIG[k] = self.get(k)
        if not i18n_applied[0]:   # the UI is built once: language changes apply after a restart
            set_language(self.get("language"))
            from . import theme
            theme.set_mode(self.get("theme"))
            theme.set_style(self.get("style"))
            i18n_applied[0] = True


# ---------------------------------------------------------------- autostart (Windows)
def launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --quiet'
    return f'"{sys.executable}" -m dragshift --quiet'


def autostart_enabled() -> bool:
    if IS_LINUX:
        from . import platform_linux
        return platform_linux.autostart_enabled()
    if IS_MAC:
        from . import platform_mac
        return platform_mac.autostart_enabled()
    if not IS_WIN:
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP)
            return True
    except OSError:
        return False


def migrate_autostart():
    """If the old Tesler entry starts with Windows, re-register it under the new name."""
    if not IS_WIN:
        return
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as k:
            winreg.QueryValueEx(k, OLD_APP)
            winreg.DeleteValue(k, OLD_APP)
            winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, launch_command())
    except OSError:
        pass


def set_autostart(on: bool):
    if IS_LINUX:
        from . import platform_linux
        platform_linux.set_autostart(on)
        return
    if IS_MAC:
        from . import platform_mac
        platform_mac.set_autostart(on)
        return
    if not IS_WIN:
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, launch_command())
        else:
            try:
                winreg.DeleteValue(k, APP)
            except OSError:
                pass


TRIGGERS = ([("shift", "Shift ⇧"), ("ctrl", "Control ⌃"), ("alt", "Option ⌥")] if IS_MAC
            else [("shift", "Shift"), ("ctrl", "Ctrl"), ("alt", "Alt")])
OUTPUTS = [("next", "Next to the original"), ("folder", "In a “Tesler” subfolder")]
STYLES = [("native", "Native (Windows 11)"), ("classic", "Liquid glass (classic)")]
THEMES = [("auto", "Same as Windows"), ("dark", "Dark"), ("light", "Light")]
DPIS = [(150, "150 dpi · small"), (200, "200 dpi · balanced"), (300, "300 dpi · print")]


class SettingsWindow(GlassWindow):
    changed = Signal()

    def __init__(self, settings: Settings):
        super().__init__(tr("Settings"), size=(560, 640))
        self.s = settings
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(12)
        r = 0

        def combo(options, current):
            c = QComboBox()
            for v, label in options:
                c.addItem(tr(label), v)
            idx = max(0, [v for v, _ in options].index(current) if current in [v for v, _ in options] else 0)
            c.setCurrentIndex(idx)
            return c

        grid.addWidget(QLabel(tr("Open the menu with")), r, 0)
        self.trigger = combo(TRIGGERS, self.s.get("trigger"))
        self.trigger.currentIndexChanged.connect(lambda _: self._save("trigger", self.trigger.currentData()))
        grid.addWidget(self.trigger, r, 1)
        r += 1
        hint = QLabel(tr("…pressed while you’re dragging a file"))
        hint.setObjectName("dim")
        grid.addWidget(hint, r, 1)
        r += 1

        grid.addWidget(QLabel(tr("Save results")), r, 0)
        self.output = combo(OUTPUTS, self.s.get("output"))
        self.output.currentIndexChanged.connect(lambda _: self._save("output", self.output.currentData()))
        grid.addWidget(self.output, r, 1)
        r += 1

        grid.addWidget(QLabel(tr("JPG / WebP quality")), r, 0)
        row = QHBoxLayout()
        self.q = QSlider(Qt.Horizontal)
        self.q.setRange(60, 100)
        self.q.setValue(self.s.get("jpg_quality"))
        self.qv = QLabel(str(self.q.value()))
        self.qv.setObjectName("dim")
        self.qv.setFixedWidth(30)
        self.q.valueChanged.connect(lambda v: (self.qv.setText(str(v)), self._save("jpg_quality", v)))
        row.addWidget(self.q)
        row.addWidget(self.qv)
        grid.addLayout(row, r, 1)
        r += 1

        grid.addWidget(QLabel(tr("PDF → image resolution")), r, 0)
        self.dpi = combo(DPIS, self.s.get("pdf_dpi"))
        self.dpi.currentIndexChanged.connect(lambda _: self._save("pdf_dpi", self.dpi.currentData()))
        grid.addWidget(self.dpi, r, 1)
        r += 1

        grid.addWidget(QLabel(tr("Language")), r, 0)
        self.lang = combo(LANGUAGES, self.s.get("language"))
        self.lang.currentIndexChanged.connect(lambda _: self._save("language", self.lang.currentData()))
        grid.addWidget(self.lang, r, 1)
        r += 1
        grid.addWidget(QLabel(tr("Look")), r, 0)
        self.style_box = combo(STYLES, self.s.get("style"))
        self.style_box.currentIndexChanged.connect(lambda _: self._save("style", self.style_box.currentData()))
        grid.addWidget(self.style_box, r, 1)
        r += 1
        grid.addWidget(QLabel(tr("Theme")), r, 0)
        self.theme = combo(THEMES, self.s.get("theme"))
        self.theme.currentIndexChanged.connect(lambda _: self._save("theme", self.theme.currentData()))
        grid.addWidget(self.theme, r, 1)
        r += 1
        lang_hint = QLabel(tr("Takes effect after restarting Tesler"))
        lang_hint.setObjectName("dim")
        grid.addWidget(lang_hint, r, 1)
        r += 1

        if IS_WIN or IS_MAC or IS_LINUX:
            self.auto = QCheckBox(tr("Start Tesler with Windows" if IS_WIN else "Open Tesler at login"))
            self.auto.setChecked(autostart_enabled())
            self.auto.toggled.connect(set_autostart)
            grid.addWidget(self.auto, r, 1)
            r += 1
        if IS_MAC:
            from . import platform_mac
            if not platform_mac.has_screen_recording():
                glass_btn = QPushButton(tr("Enable full liquid glass…"))
                glass_btn.setToolTip(tr("Lets the glass refract the windows behind it (Screen Recording permission)"))
                glass_btn.clicked.connect(platform_mac.request_screen_recording)
                grid.addWidget(glass_btn, r, 1)
                r += 1
        self.body.addLayout(grid)
        self.body.addStretch(1)
        about = QLabel(tr("Tesler {v}  ·  originals are never modified", v=__version__) + "<br>"
                       + tr("Based on {link} by llamaboi55",
                            link='<a href="https://github.com/llamaboi55/DragShift">DragShift</a>'))
        about.setObjectName("dim")
        about.setOpenExternalLinks(True)
        done = QPushButton(tr("Done"))
        done.setObjectName("primary")
        done.clicked.connect(self.close)
        self.set_footer([about], [done])

    def _save(self, key, value):
        self.s.set(key, value)
        self.changed.emit()


class WelcomeWindow(GlassWindow):
    def __init__(self, settings: Settings, trigger_label: str = "Shift"):
        super().__init__(tr("Welcome to Tesler"), size=(560, 430))
        self.s = settings
        steps = [
            ("1", tr("Start dragging any file"), tr("in Finder or on the desktop" if IS_MAC else
             "in your file manager (Thunar, Nautilus…)" if IS_LINUX else "in File Explorer or on the desktop")),
            ("2", tr("Press {key}", key=trigger_label), tr("the glass menu opens right under your cursor")),
            ("3", tr("Drop it on a slice"), tr("the result is saved next to the original")),
            ("4", tr("Tap {key} again", key=trigger_label), tr("to switch between Convert and Tools")),
        ]
        from . import theme
        t = theme.current()
        for n, head, sub in steps:
            row = QHBoxLayout()
            badge = QLabel(n)
            badge.setAlignment(Qt.AlignCenter)
            badge.setFixedSize(32, 32)
            badge.setStyleSheet(f"background: {t.control}; border: 1px solid {t.stroke}; border-radius: 16px;"
                                f"color: {t.accent_text}; font-weight: 600; font-size: 11pt;")
            row.addWidget(badge)
            col = QVBoxLayout()
            col.setSpacing(1)
            h = QLabel(head)
            h.setStyleSheet("font-size: 11.5pt; font-weight: 600;")
            d = QLabel(sub)
            d.setObjectName("dim")
            col.addWidget(h)
            col.addWidget(d)
            row.addSpacing(8)
            row.addLayout(col, 1)
            self.body.addLayout(row)
        self.body.addStretch(1)
        if IS_MAC:
            from . import platform_mac
            if not platform_mac.has_screen_recording():
                note = QLabel(tr("Optional: allow Screen Recording so the glass can refract the windows "
                                 "behind it (otherwise it shows your wallpaper). Tesler never saves or sends it."))
                note.setObjectName("dim")
                note.setWordWrap(True)
                self.body.addWidget(note)
                b = QPushButton(tr("Allow Screen Recording…"))
                b.clicked.connect(platform_mac.request_screen_recording)
                self.body.addWidget(b, 0, Qt.AlignLeft)
        if IS_LINUX:
            from . import platform_linux
            if platform_linux.is_wayland():
                note = QLabel(tr("You're on a Wayland session: the Shift-while-dragging trigger needs X11 (e.g. XFCE). "
                                 "Right-click a file → Open With → Tesler still works."))
                note.setObjectName("warn")
                note.setWordWrap(True)
                self.body.addWidget(note)
        left = []
        if IS_WIN or IS_MAC or IS_LINUX:
            self.auto = QCheckBox(tr("Start with Windows" if IS_WIN else "Open at login"))
            self.auto.setChecked(True)
            left.append(self.auto)
        ok = QPushButton(tr("Got it"))
        ok.setObjectName("primary")
        ok.clicked.connect(self._done)
        self.set_footer(left, [ok])

    def _done(self):
        self.s.set("welcomed", True)
        if IS_WIN or IS_MAC or IS_LINUX:
            set_autostart(self.auto.isChecked())
        self.close()
