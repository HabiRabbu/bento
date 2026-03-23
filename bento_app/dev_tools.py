# MIT License — Copyright (c) 2026 HabiRabbu — see LICENSE
"""Developer tools panel for ``bento --dev``.

Provides a toggleable panel with live log viewer, manifest inspector,
config dump, and block hot-reload controls.
"""

from __future__ import annotations

import json
import logging
import threading
from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QTextCursor
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bento_app.config import BentoConfig, SENSITIVE_SUFFIXES

if TYPE_CHECKING:
    from bento_app.block_loader import BlockLoader
    from bento_app.blocks.base_block import BaseBlock, ManifestDict

logger = logging.getLogger(__name__)

_dev_mode: bool = False


def is_dev_mode() -> bool:
    """Return ``True`` when ``--dev`` was passed on the command line."""
    return _dev_mode


def set_dev_mode(enabled: bool) -> None:
    """Toggle developer mode (called once from __main__.py)."""
    global _dev_mode
    _dev_mode = enabled



class _LogCapture(logging.Handler):
    """Captures log records so the DevPanel can display them live."""

    def __init__(self) -> None:
        super().__init__()
        self._lock_records = threading.Lock()
        self._records: list[logging.LogRecord] = []
        self._callbacks: list[Callable[[logging.LogRecord], None]] = []

    def emit(self, record: logging.LogRecord) -> None:
        with self._lock_records:
            self._records.append(record)
            callbacks = list(self._callbacks)
        for cb in callbacks:
            try:
                cb(record)  # type: ignore[operator]
            except Exception:
                pass

    def subscribe(self, callback: object) -> None:
        with self._lock_records:
            self._callbacks.append(callback)

    def unsubscribe(self, callback: object) -> None:
        with self._lock_records:
            try:
                self._callbacks.remove(callback)
            except ValueError:
                pass

    @property
    def records(self) -> list[logging.LogRecord]:
        with self._lock_records:
            return list(self._records)


_log_capture = _LogCapture()
_log_capture.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s"))


def install_log_capture() -> None:
    """Attach the capture handler to the root logger."""
    logging.getLogger().addHandler(_log_capture)



class _LogViewer(QWidget):
    """Scrollable live log viewer with level filtering."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Filter:"))
        self._level_combo = QComboBox()
        self._level_combo.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR"])
        self._level_combo.currentTextChanged.connect(self._refilter)
        toolbar.addWidget(self._level_combo)
        toolbar.addStretch()
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._clear)
        toolbar.addWidget(self._clear_btn)
        layout.addLayout(toolbar)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setFont(QFont("monospace", 9))
        self._text.setStyleSheet(
            "QTextEdit { background-color: palette(base); color: palette(text); "
            "font-family: monospace; font-size: 10pt; }"
        )
        layout.addWidget(self._text)

        self._records: deque[logging.LogRecord] = deque(maxlen=5000)
        self._auto_scroll = True

        self._pending_records: list[logging.LogRecord] = []
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(100)  # flush every 100ms
        self._flush_timer.timeout.connect(self._flush_pending)
        self._flush_timer.start()

        _log_capture.subscribe(self._on_record)

        for rec in _log_capture.records:
            self._records.append(rec)
            self._append_record(rec)

    def _level_color(self, level: str) -> str:
        """Return a color string for the log level, adapting to the theme."""
        pal = self.palette()
        base_lightness = pal.color(pal.ColorRole.Base).lightness()
        is_dark = base_lightness < 128
        if level == "DEBUG":
            return "#888888" if is_dark else "#666666"
        elif level == "WARNING":
            return "#f0ad4e" if is_dark else "#b8860b"
        elif level == "ERROR" or level == "CRITICAL":
            return "#e74c3c" if is_dark else "#cc0000"
        else:  # INFO
            return pal.color(pal.ColorRole.Text).name()

    def _on_record(self, record: logging.LogRecord) -> None:
        self._pending_records.append(record)

    def _flush_pending(self) -> None:
        if not self._pending_records:
            return
        records = self._pending_records[:]
        self._pending_records.clear()
        for record in records:
            self._records.append(record)
            self._append_record(record)

    def _append_record(self, record: logging.LogRecord) -> None:
        level = record.levelname
        min_level = self._level_combo.currentText()
        if min_level != "ALL" and record.levelno < getattr(logging, min_level, 0):
            return
        color = self._level_color(level)
        line = _log_capture.formatter.format(record) if _log_capture.formatter else str(record)
        self._text.append(f'<span style="color:{color}">{line}</span>')
        if self._auto_scroll:
            self._text.moveCursor(QTextCursor.MoveOperation.End)

    def _refilter(self) -> None:
        self._text.clear()
        for rec in _log_capture.records:
            self._append_record(rec)

    def _clear(self) -> None:
        self._text.clear()



class _ManifestInspector(QWidget):
    """Tree view of parsed manifests for each loaded block."""

    def __init__(
        self,
        blocks: list[tuple[ManifestDict, BaseBlock]],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._blocks = blocks

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Loaded block manifests"))
        toolbar.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._populate)
        toolbar.addWidget(refresh_btn)
        layout.addLayout(toolbar)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Key", "Value"])
        self._tree.setAlternatingRowColors(True)
        self._tree.setColumnWidth(0, 180)
        layout.addWidget(self._tree)

        self._populate()

    def _populate(self) -> None:
        self._tree.clear()
        for manifest, block in self._blocks:
            block_id = manifest.get("id", "?")
            root = QTreeWidgetItem(self._tree, [f"{manifest.get('name', block_id)}", ""])
            root.setExpanded(True)
            for key, value in manifest.items():
                child = QTreeWidgetItem(root, [str(key), str(value)])
                child.setToolTip(1, str(value))

    def update_blocks(self, blocks: list[tuple[ManifestDict, BaseBlock]]) -> None:
        self._blocks = blocks
        self._populate()



class _ConfigDump(QWidget):
    """Shows current config.json + .env keys (values masked for sensitive keys)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Current configuration"))
        toolbar.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._populate)
        toolbar.addWidget(refresh_btn)
        layout.addLayout(toolbar)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setFont(QFont("monospace", 10))
        layout.addWidget(self._text)

        self._populate()

    def _populate(self) -> None:
        config = BentoConfig()
        lines: list[str] = []
        lines.append("config.json")

        all_data: dict[str, object] = {}
        with config._lock:
            all_data = dict(config._data)

        json_keys: dict[str, object] = {}
        env_keys: list[str] = []

        for key, value in sorted(all_data.items()):
            if BentoConfig.is_sensitive(key):
                env_keys.append(key)
            else:
                json_keys[key] = value

        lines.append(json.dumps(json_keys, indent=2, default=str))
        lines.append("")
        lines.append(".env keys (values hidden)")
        for key in sorted(env_keys):
            lines.append(f"  {key} = ********")
        if not env_keys:
            lines.append("  (none)")

        self._text.setPlainText("\n".join(lines))



class _BlockReloader(QWidget):
    """Select a block and trigger hot-reload."""

    def __init__(
        self,
        blocks: list[tuple[ManifestDict, BaseBlock]],
        loader: BlockLoader | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._blocks = blocks
        self._loader = loader

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        layout.addWidget(QLabel("Select a block to hot-reload:"))

        self._combo = QComboBox()
        self._refresh_combo()
        layout.addWidget(self._combo)

        self._reload_btn = QPushButton("Reload Selected Block")
        self._reload_btn.setStyleSheet("padding: 8px; font-weight: bold;")
        self._reload_btn.clicked.connect(self._reload_selected)
        layout.addWidget(self._reload_btn)

        self._reload_all_btn = QPushButton("Reload All Blocks")
        self._reload_all_btn.clicked.connect(self._reload_all)
        layout.addWidget(self._reload_all_btn)

        self._status = QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)
        layout.addStretch()

    def _refresh_combo(self) -> None:
        self._combo.clear()
        for manifest, _block in self._blocks:
            self._combo.addItem(
                f"{manifest.get('name', '?')}  ({manifest.get('id', '?')})",
                manifest.get("id"),
            )

    def _reload_selected(self) -> None:
        block_id = self._combo.currentData()
        if not block_id:
            self._status.setText("No block selected.")
            return
        if self._loader is None:
            self._status.setText("Loader not available — cannot reload.")
            return
        logger.info("Dev: triggering reload for block '%s'", block_id)
        self._loader.load_all()
        self._loader.blocks_changed.emit()
        self._status.setText(f"Reload signal sent for '{block_id}'. Check logs.")

    def _reload_all(self) -> None:
        if self._loader is None:
            self._status.setText("Loader not available — cannot reload.")
            return
        logger.info("Dev: triggering reload for all blocks")
        self._loader.load_all()
        self._loader.blocks_changed.emit()
        self._status.setText("Reload signal sent for all blocks. Check logs.")

    def update_blocks(self, blocks: list[tuple[ManifestDict, BaseBlock]]) -> None:
        self._blocks = blocks
        self._refresh_combo()



class DevPanel(QWidget):
    """Dockable developer tools panel shown when ``--dev`` is active.

    Contains four tabs:
    - Live Log Viewer
    - Manifest Inspector
    - Config Dump
    - Block Reload
    """

    def __init__(
        self,
        blocks: list[tuple[ManifestDict, BaseBlock]],
        loader: BlockLoader | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._blocks = blocks

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(8, 4, 8, 4)
        title = QLabel("Dev Tools")
        title.setStyleSheet("font-weight: bold; font-size: 12px;")
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        self._tabs = QTabWidget()
        self._log_viewer = _LogViewer()
        self._manifest_inspector = _ManifestInspector(blocks)
        self._config_dump = _ConfigDump()
        self._block_reloader = _BlockReloader(blocks, loader)

        self._tabs.addTab(self._log_viewer, "Logs")
        self._tabs.addTab(self._manifest_inspector, "Manifests")
        self._tabs.addTab(self._config_dump, "Config")
        self._tabs.addTab(self._block_reloader, "Reload")

        layout.addWidget(self._tabs)

    def update_blocks(self, blocks: list[tuple[ManifestDict, BaseBlock]]) -> None:
        """Refresh panels when blocks are reloaded."""
        self._blocks = blocks
        self._manifest_inspector.update_blocks(blocks)
        self._block_reloader.update_blocks(blocks)
