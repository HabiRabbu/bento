# MIT License — Copyright (c) 2026 HabiRabbu — see LICENSE
"""System tray icon for Bento.

Provides left-click toggle, right-click context menu with Open / Settings / Quit.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QMenu, QSystemTrayIcon, QApplication

from bento_app import __version__

logger = logging.getLogger(__name__)


class BentoTray(QSystemTrayIcon):
    """KDE system tray icon for Bento."""

    def __init__(
        self,
        icon_path: Path,
        toggle_callback: Callable[[], None],
        settings_callback: Callable[[], None],
        parent: object | None = None,
    ) -> None:
        icon = self._load_icon(icon_path)
        super().__init__(icon, parent)  # type: ignore[arg-type]

        self._toggle = toggle_callback
        self._settings = settings_callback

        self.activated.connect(self._on_activated)

        self._menu = QMenu()
        open_action = self._menu.addAction("Open Bento")
        open_action.triggered.connect(self._toggle)

        settings_action = self._menu.addAction("Settings")
        settings_action.triggered.connect(self._settings)

        self._menu.addSeparator()

        quit_action = self._menu.addAction("Quit")
        quit_action.triggered.connect(QApplication.quit)

        self.setContextMenu(self._menu)
        self.setToolTip(f"Bento v{__version__}")
        self.show()

        logger.info("System tray icon active")


    @staticmethod
    def _load_icon(icon_path: Path) -> QIcon:
        """Load the best available icon, preferring PNG over SVG."""
        assets_dir = icon_path.parent
        png_icon = assets_dir / "bento-icon-64.png"
        if png_icon.exists():
            return QIcon(str(png_icon))
        return QIcon(str(icon_path))


    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._toggle()
