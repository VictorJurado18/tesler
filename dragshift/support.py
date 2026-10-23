"""'Curtiu o Tesler?' — a Pix QR code to say thanks. Using the app stays 100% free."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from . import theme
from .i18n import tr
from .window import GlassWindow

PIX_KEY = "f608aca6-81f0-4c41-a77f-347777f75b0e"
PIX_NAME = "Victor Nemeth Jurado"
PIX_QR = Path(__file__).with_name("assets") / "pix.png"
ORIGINAL_SUPPORT = "https://github.com/llamaboi55/DragShift#support"


class SupportWindow(GlassWindow):
    def __init__(self):
        super().__init__(tr("Support Tesler"), size=(600, 410))
        t = theme.current()
        row = QHBoxLayout()
        row.setSpacing(24)
        qr = QLabel()
        qr.setFixedSize(200, 200)
        qr.setAlignment(Qt.AlignCenter)
        qr.setStyleSheet("background: #FFFFFF; border-radius: 10px; padding: 8px;")
        pm = QPixmap(str(PIX_QR))
        if not pm.isNull():
            qr.setPixmap(pm.scaled(184, 184, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        row.addWidget(qr, 0, Qt.AlignTop)

        col = QVBoxLayout()
        col.setSpacing(8)
        head = QLabel(tr("Enjoying Tesler?"))
        head.setObjectName("heading")
        text = QLabel(tr("If it saved you some time, a coffee helps keep the project alive. "
                         "Using the app stays 100% free. ☕"))
        text.setWordWrap(True)
        col.addWidget(head)
        col.addWidget(text)
        col.addSpacing(6)
        lab = QLabel(tr("Pix key (copy and paste)"))
        lab.setObjectName("dim")
        col.addWidget(lab)
        key = QLineEdit(PIX_KEY)
        key.setReadOnly(True)
        key.setCursorPosition(0)
        col.addWidget(key)
        who = QLabel(tr("Recipient: {name} · São Paulo", name=PIX_NAME))
        who.setObjectName("dim")
        col.addWidget(who)
        col.addStretch(1)
        row.addLayout(col, 1)
        self.body.addLayout(row)
        self.body.addStretch(1)
        orig = QLabel(tr("Tesler is based on {link}: you can thank its original author too.",
                         link=f'<a href="{ORIGINAL_SUPPORT}" style="color:{t.accent_text}">DragShift</a>'))
        orig.setObjectName("dim")
        orig.setWordWrap(True)
        orig.setOpenExternalLinks(True)
        self.body.addWidget(orig)

        self.copy_btn = QPushButton(tr("Copy Pix key"))
        self.copy_btn.setObjectName("primary")
        self.copy_btn.clicked.connect(self._copy)
        close = QPushButton(tr("Close"))
        close.clicked.connect(self.close)
        self.set_footer([], [close, self.copy_btn])

    def _copy(self):
        QGuiApplication.clipboard().setText(PIX_KEY)
        self.copy_btn.setText(tr("Copied ✓"))
        QTimer.singleShot(1800, lambda: self.copy_btn.setText(tr("Copy Pix key")))


def open_original_support():
    QDesktopServices.openUrl(QUrl(ORIGINAL_SUPPORT))
