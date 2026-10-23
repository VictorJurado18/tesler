"""The update window (check · offer · download) and the "what's new" window."""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QProgressBar, QPushButton,
                               QTextBrowser, QVBoxLayout)

from . import __version__, theme, updater
from .i18n import tr
from .window import GlassWindow, app_mark


class _Bridge(QObject):
    found = Signal(object)        # Release | None
    failed = Signal(str)
    progress = Signal(float)
    downloaded = Signal(str)


def _notes_view(md: str) -> QTextBrowser:
    t = theme.current()
    v = QTextBrowser()
    v.setOpenExternalLinks(True)
    v.setFrameShape(QTextBrowser.NoFrame)
    v.setStyleSheet(f"QTextBrowser {{ background: {t.control}; border: 1px solid {t.stroke}; "
                    f"border-radius: 8px; padding: 10px 14px; color: {t.text}; }}")
    pal = v.palette()
    pal.setColor(QPalette.Link, theme.qcolor(t.accent_text))
    v.setPalette(pal)
    v.setMarkdown(md or tr("No notes for this version."))
    _tint_links(v, theme.qcolor(t.accent_text))
    return v


def _tint_links(view: QTextBrowser, color):
    """Markdown links come out in Qt's default blue: give them the accent colour."""
    from PySide6.QtGui import QTextCursor
    doc = view.document()
    block = doc.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.isValid() and frag.charFormat().isAnchor():
                fmt = frag.charFormat()
                fmt.setForeground(color)
                cur = QTextCursor(doc)
                cur.setPosition(frag.position())
                cur.setPosition(frag.position() + frag.length(), QTextCursor.KeepAnchor)
                cur.setCharFormat(fmt)
            it += 1
        block = block.next()


class _Base(GlassWindow):
    def __init__(self, title: str, size=(560, 520)):
        super().__init__(title, size=size)
        head = QHBoxLayout()
        head.setSpacing(14)
        mark = QLabel()
        mark.setFixedSize(44, 44)
        mark.setPixmap(app_mark(44))
        head.addWidget(mark)
        col = QVBoxLayout()
        col.setSpacing(1)
        self.heading = QLabel()
        self.heading.setObjectName("heading")
        self.subtitle = QLabel()
        self.subtitle.setObjectName("dim")
        self.subtitle.setWordWrap(True)
        col.addWidget(self.heading)
        col.addWidget(self.subtitle)
        head.addLayout(col, 1)
        self.body.addLayout(head)
        self.body.addSpacing(10)
        self.content = QVBoxLayout()
        self.content.setSpacing(10)
        self.body.addLayout(self.content, 1)

    def _clear(self):
        while self.content.count():
            it = self.content.takeAt(0)
            if it.widget():
                it.widget().hide()
                it.widget().deleteLater()

    def _button(self, text, slot, primary=False):
        b = QPushButton(tr(text))
        if primary:
            b.setObjectName("primary")
        b.clicked.connect(slot)
        return b


class WhatsNewWindow(_Base):
    """Shown once, the first time a new version starts."""

    def __init__(self, version: str = __version__, notes: str | None = None):
        super().__init__(tr("What's new"))
        self.heading.setText(tr("What's new in Tesler {v}", v=version))
        self.subtitle.setText(tr("You're up to date. Here is what changed."))
        self.content.addWidget(_notes_view(updater.notes_for(version) if notes is None else notes), 1)
        self.set_footer([self._button("All versions", lambda: updater.open_page())],
                        [self._button("Got it", self.close, primary=True)])


class UpdateWindow(_Base):
    """Checks for a newer release; offers it; downloads, installs and restarts."""

    def __init__(self, release: updater.Release | None = None):
        super().__init__(tr("Updates"))
        self.bridge = _Bridge()
        self.bridge.found.connect(self._found)
        self.bridge.failed.connect(self._failed)
        self.bridge.progress.connect(self._progress)
        self.bridge.downloaded.connect(self._install)
        self._cancel = False
        self.release = None
        if release is not None:
            self._found(release)
        else:
            self.check()

    # ---- check
    def check(self):
        self._clear()
        self.heading.setText(tr("Checking for updates…"))
        self.subtitle.setText(tr("You have version {v}", v=__version__))
        self.set_footer([], [self._button("Close", self.close)])

        def work():
            try:
                self.bridge.found.emit(updater.fetch_latest())
            except Exception as e:  # noqa: BLE001  (offline, rate limit, proxy…)
                self.bridge.failed.emit(str(e))
        threading.Thread(target=work, daemon=True).start()

    def _found(self, rel):
        self._clear()
        self.release = rel
        if rel is None or not updater.is_newer(rel.version):
            self.heading.setText(tr("Tesler is up to date"))
            self.subtitle.setText(tr("You have the latest version ({v}).", v=__version__))
            self.content.addStretch(1)
            self.set_footer([self._button("What's new", lambda: self._show_notes(__version__))],
                            [self._button("Done", self.close, primary=True)])
            return
        self.heading.setText(tr("Tesler {v} is available", v=rel.version))
        self.subtitle.setText(tr("You have version {v}", v=__version__))
        self.content.addWidget(_notes_view(updater.tidy_notes(rel.notes)), 1)
        later = self._button("Later", self.close)
        if updater.installed_build() and rel.setup_url:
            go = self._button("Update now", self.start_download, primary=True)
            self.set_footer([self._button("Release page", lambda: updater.open_page(rel.page))], [later, go])
        else:
            hint = QLabel(tr("Running from source: update with git pull, then reopen Tesler."))
            hint.setObjectName("dim")
            hint.setWordWrap(True)
            self.content.addWidget(hint)
            go = self._button("Release page", lambda: updater.open_page(rel.page), primary=True)
            self.set_footer([], [later, go])

    def _show_notes(self, version):
        self._clear()
        self.heading.setText(tr("What's new in Tesler {v}", v=version))
        self.content.addWidget(_notes_view(updater.notes_for(version)), 1)

    def _failed(self, msg):
        self._clear()
        self.heading.setText(tr("Couldn't check for updates"))
        self.subtitle.setText(tr("Check your internet connection and try again."))
        self.content.addStretch(1)
        self.set_footer([], [self._button("Close", self.close), self._button("Try again", self.check, primary=True)])

    # ---- download and install
    def start_download(self):
        rel = self.release
        self._clear()
        self._cancel = False
        self.heading.setText(tr("Downloading Tesler {v}…", v=rel.version))
        self.subtitle.setText(tr("Tesler closes and reopens by itself when it's done."))
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.pct = QLabel("0%")
        self.pct.setObjectName("dim")
        self.content.addWidget(self.bar)
        self.content.addWidget(self.pct)
        self.content.addStretch(1)
        self.set_footer([], [self._button("Cancel", self._abort)])

        def work():
            try:
                path = updater.download(rel, self.bridge.progress.emit, lambda: self._cancel)
                self.bridge.downloaded.emit(str(path))
            except InterruptedError:
                pass
            except Exception as e:  # noqa: BLE001
                self.bridge.failed.emit(str(e))
        threading.Thread(target=work, daemon=True).start()

    def _progress(self, f):
        if hasattr(self, "bar"):
            self.bar.setValue(int(f * 1000))
            self.pct.setText(f"{f * 100:.0f}%")

    def _abort(self):
        self._cancel = True
        self._found(self.release)

    def _install(self, path):
        self.heading.setText(tr("Installing…"))
        self.subtitle.setText(tr("Tesler closes and reopens by itself when it's done."))
        try:
            updater.run_installer(updater.Path(path))
        except OSError as e:
            self._failed(str(e))
            return
        QTimer.singleShot(400, QApplication.instance().quit)

    def closeEvent(self, e):
        self._cancel = True
        super().closeEvent(e)

