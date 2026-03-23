# MIT License — Copyright (c) 2026 HabiRabbu — see LICENSE
"""Demo block — welcome block introducing users to the Bento block system."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from bento_app.blocks.base_block import BaseBlock, ManifestDict, load_manifest

_BENTO_BLOCKS_URL = "https://github.com/HabiRabbu/bento-blocks"


class DemoBlock(BaseBlock):
    """A welcome block that explains how to get started with Bento."""

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        greeting = QLabel("Bento is working")
        greeting.setAlignment(Qt.AlignmentFlag.AlignCenter)
        greeting.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(greeting)

        subtitle = QLabel("Each compartment is a block — install more to fill your bento!")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 13px;")
        layout.addWidget(subtitle)

        layout.addSpacing(6)

        browse_btn = QPushButton("Browse Official Blocks")
        browse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        browse_btn.setStyleSheet(
            "QPushButton {"
            "  font-size: 15px; font-weight: bold;"
            "  padding: 10px 24px;"
            "  border-radius: 6px;"
            "  background-color: palette(highlight);"
            "  color: palette(highlighted-text);"
            "}"
            "QPushButton:hover {"
            "  opacity: 0.9;"
            "}"
        )
        browse_btn.clicked.connect(self._open_blocks_repo)
        layout.addWidget(browse_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(10)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        how_to_heading = QLabel("How to install a block")
        how_to_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        how_to_heading.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(how_to_heading)

        steps = QLabel(
            "1. Download a block folder from bento-blocks\n"
            "2. Copy it to ~/.config/bento/blocks/\n"
            "3. Restart Bento (or it auto-detects new blocks)"
        )
        steps.setAlignment(Qt.AlignmentFlag.AlignCenter)
        steps.setWordWrap(True)
        steps.setStyleSheet("font-size: 13px;")
        layout.addWidget(steps)

    def on_focus(self) -> None:
        pass

    @staticmethod
    def get_manifest() -> ManifestDict:
        return load_manifest(__file__)

    @staticmethod
    def _open_blocks_repo() -> None:
        QDesktopServices.openUrl(QUrl(_BENTO_BLOCKS_URL))
