# MIT License — Copyright (c) 2026 HabiRabbu — see LICENSE
"""Placeholder widgets for loading, error, and empty states."""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class LoadingPlaceholder(QWidget):
    """Spinner/busy indicator shown while a block is being initialized."""

    def __init__(self, block_name: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._spinner_label = QLabel()
        self._spinner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self._spinner_label.font()
        font.setPointSize(22)
        self._spinner_label.setFont(font)

        self._text_label = QLabel(
            f"Loading {block_name}\u2026" if block_name else "Loading\u2026"
        )
        self._text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(self._spinner_label)
        layout.addWidget(self._text_label)

        self._frames = ["\u25d0", "\u25d3", "\u25d1", "\u25d2"]
        self._frame_idx = 0
        self._spinner_label.setText(self._frames[0])

        self._timeout_label = QLabel("")
        self._timeout_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timeout_label.setStyleSheet("color: palette(mid); font-size: 10pt;")
        self._timeout_label.setWordWrap(True)
        layout.addWidget(self._timeout_label)

        self._timer = QTimer(self)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._advance)
        self._timer.start()

        QTimer.singleShot(15000, self._show_timeout_hint)

    def _show_timeout_hint(self) -> None:
        if self.isVisible():
            self._timeout_label.setText("Loading is taking longer than expected\u2026")

    def _advance(self) -> None:
        self._frame_idx = (self._frame_idx + 1) % len(self._frames)
        self._spinner_label.setText(self._frames[self._frame_idx])


class ErrorPlaceholder(QWidget):
    """Error card shown when a block crashes, with traceback and Reload button."""

    def __init__(
        self,
        block_name: str,
        exc: Exception,
        tb_text: str = "",
        on_reload: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        header = QLabel(f"Block '{block_name}' crashed")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_font = header.font()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        exc_label = QLabel(f"{type(exc).__name__}: {exc}")
        exc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        exc_label.setWordWrap(True)
        layout.addWidget(exc_label)

        if tb_text:
            tb_label = QLabel(tb_text)
            tb_label.setFont(QFont("monospace", 9))
            tb_label.setWordWrap(True)
            tb_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )

            scroll = QScrollArea()
            scroll.setWidget(tb_label)
            scroll.setWidgetResizable(True)
            scroll.setMaximumHeight(200)
            layout.addWidget(scroll)

        if on_reload is not None:
            btn_row = QHBoxLayout()
            btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
            reload_btn = QPushButton("Reload Block")
            reload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            reload_btn.setAccessibleName(f"Reload {block_name} block")
            reload_btn.clicked.connect(on_reload)
            btn_row.addWidget(reload_btn)
            layout.addLayout(btn_row)

        layout.addStretch()


class EmptyPlaceholder(QWidget):
    """'No blocks installed' view when only the demo block is present."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(16)

        title = QLabel("No blocks installed")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = title.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        desc = QLabel(
            "Bento uses modular blocks to provide functionality.\n"
            "Browse and install community blocks to get started."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        link = QLabel(
            '<a href="https://github.com/HabiRabbu/bento-blocks">'
            "Browse Official Blocks</a>"
        )
        link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        link.setAccessibleName("Browse official blocks on GitHub")
        link.setOpenExternalLinks(True)
        layout.addWidget(link)

        hint = QLabel(
            "Install blocks to ~/.config/bento/blocks/\n"
            "They will be detected automatically."
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        layout.addWidget(hint)

        layout.addStretch()
