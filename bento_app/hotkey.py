# MIT License — Copyright (c) 2026 HabiRabbu — see LICENSE
"""KDE global hotkey via a native C++ helper process.

KDE Plasma's ``kglobalaccel`` daemon only fires shortcut signals for components
registered through the C++ ``KGlobalAccel`` API (which sets *isActive = true*).
Raw DBus calls from Python leave the component inactive.

This module spawns a small compiled helper (``bento-hotkey-helper``) that links
against ``libKF6GlobalAccel`` and prints ``PRESSED`` to stdout whenever the
configured shortcut is activated.  If the helper is missing or crashes, Bento
falls back to tray-icon-only operation.
"""

from __future__ import annotations

import logging
import os
import shutil
from collections.abc import Callable
from pathlib import Path

from PyQt6.QtCore import QObject, QProcess, QTimer, pyqtSignal

logger = logging.getLogger(__name__)

# Search order: system paths first, then user/development paths, then $PATH.
_HELPER_NAME = "bento-hotkey-helper"
_HELPER_SEARCH_PATHS = [
    Path("/usr/lib/bento") / _HELPER_NAME,
    Path("/usr/libexec") / _HELPER_NAME,
    Path(__file__).resolve().parent.parent / "helpers" / _HELPER_NAME,
    Path.home() / ".local" / "lib" / "bento" / _HELPER_NAME,
]

_MAX_RESTART_ATTEMPTS = 5
_RESTART_DELAYS = [5_000, 10_000, 20_000, 40_000, 60_000]


def _find_helper() -> str | None:
    """Return the absolute path to an executable helper, or *None*."""
    for candidate in _HELPER_SEARCH_PATHS:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    # Fall back to $PATH
    return shutil.which(_HELPER_NAME)


class HotkeyManager(QObject):
    """Register and listen for a KDE global shortcut via a native helper."""

    triggered = pyqtSignal()

    def __init__(
        self,
        shortcut: str = "Meta+Shift+Space",
        callback: Callable[[], None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._shortcut = shortcut
        self._registered = False
        self._stopped = False
        self._restart_attempts = 0
        self._process: QProcess | None = None
        self._health_timer: QTimer | None = None

        if callback is not None:
            self.triggered.connect(callback)

        self._start_helper()

    # ----- helper lifecycle ------------------------------------------------

    def _start_helper(self) -> None:
        if self._stopped:
            return

        helper = _find_helper()
        if helper is None:
            logger.warning(
                "%s not found. Global hotkey unavailable — use the tray icon.",
                _HELPER_NAME,
            )
            return

        self._stop_helper()

        proc = QProcess(self)
        # Use SeparateChannels so stderr from KDE libs doesn't corrupt
        # the READY/PRESSED protocol on stdout.
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        proc.readyReadStandardOutput.connect(self._on_stdout)
        proc.finished.connect(self._on_finished)
        proc.start(helper, [self._shortcut])

        if not proc.waitForStarted(3000):
            logger.warning(
                "Failed to start %s: %s",
                _HELPER_NAME,
                proc.errorString(),
            )
            return

        self._process = proc
        logger.info(
            "Hotkey helper started (PID %d): %s",
            proc.processId(),
            self._shortcut,
        )
        self._start_health_check()

    def _stop_helper(self) -> None:
        if self._process is not None:
            self._process.finished.disconnect(self._on_finished)
            self._process.terminate()
            if not self._process.waitForFinished(2000):
                self._process.kill()
                self._process.waitForFinished(1000)
            self._process.deleteLater()
            self._process = None
            self._registered = False

    # ----- stdout parsing --------------------------------------------------

    def _on_stdout(self) -> None:
        if self._process is None:
            return
        while self._process.canReadLine():
            line = bytes(self._process.readLine()).decode("utf-8", errors="replace").strip()
            if line == "READY":
                self._registered = True
                self._restart_attempts = 0  # successful start resets backoff
                logger.info(
                    "Global hotkey registered: %s (via %s)",
                    self._shortcut,
                    _HELPER_NAME,
                )
            elif line.startswith("ERROR"):
                logger.warning("Hotkey helper reported: %s", line)
                self._registered = False
            elif line == "PRESSED":
                logger.debug("Global shortcut activated")
                self.triggered.emit()
            elif line:
                logger.debug("hotkey helper: %s", line)

    def _on_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self._registered = False
        if self._stopped:
            return

        self._restart_attempts += 1
        if self._restart_attempts > _MAX_RESTART_ATTEMPTS:
            logger.error(
                "Hotkey helper crashed %d times — giving up. Use the tray icon.",
                self._restart_attempts,
            )
            return

        delay_idx = min(self._restart_attempts - 1, len(_RESTART_DELAYS) - 1)
        delay = _RESTART_DELAYS[delay_idx]
        logger.warning(
            "Hotkey helper exited (code %d) — attempt %d/%d, restart in %d s",
            exit_code,
            self._restart_attempts,
            _MAX_RESTART_ATTEMPTS,
            delay // 1000,
        )
        QTimer.singleShot(delay, self._start_helper)

    # ----- health check ----------------------------------------------------

    def _start_health_check(self) -> None:
        if self._health_timer is not None:
            self._health_timer.stop()
            self._health_timer.deleteLater()
        self._health_timer = QTimer(self)
        self._health_timer.setInterval(60_000)
        self._health_timer.timeout.connect(self._check_health)
        self._health_timer.start()

    def _check_health(self) -> None:
        if self._stopped:
            return
        if self._process is None or self._process.state() == QProcess.ProcessState.NotRunning:
            logger.warning("Hotkey helper not running — restarting")
            self._start_helper()

    # ----- public API ------------------------------------------------------

    def unregister(self) -> None:
        """Stop the helper and release the shortcut."""
        self._stopped = True
        if self._health_timer is not None:
            self._health_timer.stop()
        self._stop_helper()
        logger.info("Global hotkey unregistered")

    def rebind(self, new_shortcut: str) -> None:
        """Restart the helper with a different shortcut."""
        self._stopped = False
        self._restart_attempts = 0
        self._shortcut = new_shortcut
        self._start_helper()

    @property
    def is_registered(self) -> bool:
        """Whether the hotkey was successfully registered with KDE."""
        return self._registered
