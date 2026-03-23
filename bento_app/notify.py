# MIT License — Copyright (c) 2026 HabiRabbu — see LICENSE
"""User-facing notification helpers using the system tray."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QSystemTrayIcon

logger = logging.getLogger(__name__)

_dnd_cache: bool = False
_dnd_cache_time: float = 0.0
_DND_CACHE_TTL: float = 5.0  # seconds


def _is_dnd_active() -> bool:
    """Check if Do Not Disturb is active via freedesktop Notifications."""
    global _dnd_cache, _dnd_cache_time  # noqa: PLW0603
    now = time.monotonic()
    if now - _dnd_cache_time < _DND_CACHE_TTL:
        return _dnd_cache
    try:
        import dbus
        bus = dbus.SessionBus()
        obj = bus.get_object("org.freedesktop.Notifications", "/org/freedesktop/Notifications")
        props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
        _dnd_cache = bool(props.Get("org.freedesktop.Notifications", "Inhibited"))
    except Exception:
        _dnd_cache = False
    _dnd_cache_time = now
    return _dnd_cache


class QueuedNotifier:
    """Buffers notifications until the tray icon is ready, then flushes."""

    def __init__(self) -> None:
        self._tray: QSystemTrayIcon | None = None
        self._queue: list[tuple[str, str, int]] = []

    def init(self, tray: QSystemTrayIcon) -> None:
        self._tray = tray
        for title, message, icon_type in self._queue:
            self._tray.showMessage(title, message, icon_type)
        self._queue.clear()

    def _show(self, title: str, message: str, icon_type: int) -> None:
        if self._tray is None:
            self._queue.append((title, message, icon_type))
            logger.debug("Tray not ready — queued notification: %s", title)
            return
        if _is_dnd_active():
            logger.debug("DND active — suppressing notification: %s", title)
            return
        self._tray.showMessage(title, message, icon_type)


_notifier = QueuedNotifier()


def init(tray: QSystemTrayIcon) -> None:
    """Set the tray icon instance used by all notification helpers."""
    _notifier.init(tray)


def notify_info(title: str, message: str) -> None:
    """Show an informational tray balloon."""
    from PyQt6.QtWidgets import QSystemTrayIcon

    _notifier._show(title, message, QSystemTrayIcon.MessageIcon.Information)


def notify_warning(title: str, message: str) -> None:
    """Show a warning tray balloon."""
    from PyQt6.QtWidgets import QSystemTrayIcon

    _notifier._show(title, message, QSystemTrayIcon.MessageIcon.Warning)


def notify_error(title: str, message: str) -> None:
    """Show an error tray balloon."""
    from PyQt6.QtWidgets import QSystemTrayIcon

    _notifier._show(title, message, QSystemTrayIcon.MessageIcon.Critical)
