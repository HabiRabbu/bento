# MIT License — Copyright (c) 2026 HabiRabbu — see LICENSE
"""First-run welcome dialog for Bento.

Shown once on initial launch to introduce the user to Bento and point them
towards the official block repository.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from bento_app.config import BentoConfig

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

_BENTO_BLOCKS_URL = "https://github.com/HabiRabbu/bento-blocks"


class FirstRunDialog(QDialog):
    """Modal welcome dialog displayed on the very first launch of Bento.

    Attributes:
        open_settings_requested: Set to ``True`` when the user clicks
            *Open Settings* so the caller can react after the dialog closes.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.open_settings_requested: bool = False
        self.setWindowTitle("Welcome to Bento")
        self.setFixedWidth(500)
        self.setModal(True)

        self._build_ui()

        self.adjustSize()
        if screen := self.screen():
            geo = screen.availableGeometry()
            self.move(
                geo.center().x() - self.width() // 2,
                geo.center().y() - self.height() // 2,
            )


    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(16)

        heading = QLabel("Welcome to Bento")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("font-size: 22px; font-weight: bold;")
        root.addWidget(heading)

        desc = QLabel(
            "Bento is a popup control centre for KDE Plasma. Install blocks "
            "to add functionality\u200a—\u200aeach block is a self-contained "
            "plugin that appears as a tab in the sidebar."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 14px;")
        root.addWidget(desc)

        shortcuts = QLabel(
            "<b>Keyboard shortcuts:</b> Ctrl+K search · Ctrl+1\u20139 switch blocks · Escape to close"
        )
        shortcuts.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shortcuts.setWordWrap(True)
        shortcuts.setStyleSheet("font-size: 12px; color: palette(mid);")
        root.addWidget(shortcuts)

        root.addSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        browse_btn = QPushButton("Browse Official Blocks")
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.setAccessibleName("Browse official blocks on GitHub")
        browse_btn.clicked.connect(self._open_blocks_repo)
        btn_row.addWidget(browse_btn)

        settings_btn = QPushButton("Open Settings")
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.setAccessibleName("Open Bento settings")
        settings_btn.clicked.connect(self._request_settings)
        btn_row.addWidget(settings_btn)

        get_started_btn = QPushButton("Get Started")
        get_started_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        get_started_btn.setAccessibleName("Close welcome dialog and get started")
        get_started_btn.setDefault(True)
        get_started_btn.clicked.connect(self.accept)
        btn_row.addWidget(get_started_btn)

        root.addLayout(btn_row)

        root.addSpacing(4)

        self._dont_show_cb = QCheckBox("Don't show this welcome dialog again")
        self._dont_show_cb.setChecked(True)
        root.addWidget(self._dont_show_cb, alignment=Qt.AlignmentFlag.AlignCenter)


    @staticmethod
    def _open_blocks_repo() -> None:
        QDesktopServices.openUrl(QUrl(_BENTO_BLOCKS_URL))

    def _request_settings(self) -> None:
        self.open_settings_requested = True
        self.accept()


    def done(self, result: int) -> None:  # noqa: D401
        """Persist the 'don't show again' preference before closing."""
        if self._dont_show_cb.isChecked():
            try:
                cfg = BentoConfig()
                cfg.set("first_run_shown", True)
                cfg.save()
            except Exception:
                logger.warning("Could not persist first_run_shown flag", exc_info=True)
        super().done(result)


def should_show_first_run() -> bool:
    """Return ``True`` when the first-run dialog has not yet been dismissed."""
    cfg = BentoConfig()
    return not cfg.get("first_run_shown", False)
