# MIT License — Copyright (c) 2026 HabiRabbu — see LICENSE
"""Ctrl+K command palette for block switching and actions."""

from __future__ import annotations

import logging

from PyQt6.QtCore import QEvent, QObject, QRect, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from bento_app.blocks.base_block import BaseBlock, ManifestDict

logger = logging.getLogger(__name__)


class CommandPalette(QWidget):
    """Floating search overlay for quick block switching."""

    action_selected = pyqtSignal(str, str)
    block_selected = pyqtSignal(int)


    def __init__(self, blocks: list[tuple[ManifestDict, BaseBlock | None]], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)

        self._container = QFrame()
        container_layout = QVBoxLayout(self._container)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Search blocks and actions\u2026 (Esc to close)")
        self._input.textChanged.connect(self._filter)
        self._input.returnPressed.connect(self._select_current)
        self._input.installEventFilter(self)
        self._input.setAccessibleName("Command palette search")

        self._list = QListWidget()
        self._list.itemActivated.connect(self._on_select)
        self._list.setAccessibleName("Command palette results")

        self._no_results = QLabel("No matching blocks or actions")
        self._no_results.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_results.setStyleSheet("color: palette(mid); padding: 16px;")
        self._no_results.setVisible(False)

        container_layout.addWidget(self._input)
        container_layout.addWidget(self._list)
        container_layout.addWidget(self._no_results)
        layout.addWidget(self._container, alignment=Qt.AlignmentFlag.AlignCenter)

        self._blocks = blocks
        self._populate()

    def _populate(self) -> None:
        self._list.clear()
        for i, (manifest, block) in enumerate(self._blocks):
            name = manifest['name']
            desc = manifest.get('description', '')
            shortcut_hint = f"  Ctrl+{i + 1}" if i < 9 else ""
            item = QListWidgetItem(f"{name} — {desc}{shortcut_hint}")
            item.setData(Qt.ItemDataRole.UserRole, i)
            item.setForeground(self.palette().color(self.palette().ColorRole.WindowText))
            self._list.addItem(item)

            if block is not None and hasattr(block, "get_actions"):
                block_id = manifest["id"]
                try:
                    for action in block.get_actions():
                        action_item = QListWidgetItem(f"  → {action.get('title', '')}")
                        action_item.setData(
                            Qt.ItemDataRole.UserRole,
                            (block_id, action.get("id", "")),
                        )
                        action_item.setForeground(
                            self.palette().color(self.palette().ColorRole.PlaceholderText)
                        )
                        self._list.addItem(action_item)
                except Exception:
                    logger.debug("Failed to get actions for block '%s'", block_id, exc_info=True)

    def _filter(self, text: str) -> None:
        query = text.lower()
        any_visible = False
        for i in range(self._list.count()):
            item = self._list.item(i)
            if not query:
                item.setHidden(False)
                any_visible = True
            else:
                match = self._fuzzy_match(query, item.text().lower())
                item.setHidden(not match)
                if match:
                    any_visible = True
        self._no_results.setVisible(not any_visible and bool(query))
        for i in range(self._list.count()):
            if not self._list.item(i).isHidden():
                self._list.setCurrentRow(i)
                break

    @staticmethod
    def _fuzzy_match(query: str, text: str) -> bool:
        """Return True if all characters in query appear in text in order."""
        it = iter(text)
        return all(c in it for c in query)

    def _on_select(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(data, int):
            self.block_selected.emit(data)
        elif isinstance(data, tuple):
            self.action_selected.emit(*data)
        self.close()

    def _select_current(self) -> None:
        """Activate the currently highlighted list item (for Enter on QLineEdit)."""
        current = self._list.currentItem()
        if current and not current.isHidden():
            self._on_select(current)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        """Forward Up/Down arrow keys from the input to the list widget."""
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                self._list.keyPressEvent(event)
                return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            current = self._list.currentItem()
            if current:
                self._on_select(current)
        elif event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            self._list.keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    def show_centered(self, parent_geometry: QRect) -> None:
        """Position the palette centered near the top of *parent_geometry* and show."""
        palette_width = min(500, int(parent_geometry.width() * 0.4))
        palette_width = max(300, palette_width)  # minimum usable width
        self._container.setFixedWidth(palette_width)
        center = parent_geometry.center()
        self.move(center.x() - palette_width // 2, parent_geometry.y() + 50)
        self.show()
        self._input.setFocus()
        self._input.clear()
        self._filter("")
