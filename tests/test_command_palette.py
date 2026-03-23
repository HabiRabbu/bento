"""Tests for bento_app.command_palette.CommandPalette."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock

import pytest
from PyQt6.QtCore import Qt

from bento_app.command_palette import CommandPalette



def _make_blocks(names: list[str], *, with_actions: bool = False):
    """Build a list of (manifest, block_or_None) tuples for the palette."""
    blocks = []
    for i, name in enumerate(names):
        manifest = {"id": f"block-{i}", "name": name, "description": f"Desc {name}"}
        block = None
        if with_actions:
            block = MagicMock()
            block.get_actions.return_value = [
                {"id": f"act-{i}", "title": f"Action for {name}"},
            ]
        blocks.append((manifest, block))
    return blocks



def test_palette_populates_with_block_names(qapp):
    """List contains one item per block."""
    blocks = _make_blocks(["Alpha", "Bravo", "Charlie"])
    palette = CommandPalette(blocks)

    assert palette._list.count() == 3
    texts = [palette._list.item(i).text() for i in range(palette._list.count())]
    assert any("Alpha" in t for t in texts)
    assert any("Bravo" in t for t in texts)
    assert any("Charlie" in t for t in texts)

    palette.close()


def test_filtering_hides_non_matching(qapp):
    """Typing into the filter hides blocks that don't match."""
    blocks = _make_blocks(["Alpha", "Bravo", "Charlie"])
    palette = CommandPalette(blocks)

    palette._filter("bra")

    visible = [
        palette._list.item(i).text()
        for i in range(palette._list.count())
        if not palette._list.item(i).isHidden()
    ]
    assert len(visible) == 1
    assert "Bravo" in visible[0]

    palette.close()


def test_filtering_empty_shows_all(qapp):
    """Empty filter text shows every item."""
    blocks = _make_blocks(["Alpha", "Bravo", "Charlie"])
    palette = CommandPalette(blocks)

    palette._filter("alpha")
    palette._filter("")

    hidden_count = sum(
        palette._list.item(i).isHidden() for i in range(palette._list.count())
    )
    assert hidden_count == 0

    palette.close()


def test_enter_selects_current_item(qapp):
    """Pressing Enter on the current item emits block_selected."""
    blocks = _make_blocks(["Alpha", "Bravo"])
    palette = CommandPalette(blocks)

    received = []
    palette.block_selected.connect(lambda idx: received.append(idx))

    palette._list.setCurrentRow(1)
    palette._select_current()

    assert received == [1]


def test_action_items_listed_alongside_blocks(qapp):
    """Blocks with get_actions() get their actions added to the list."""
    blocks = _make_blocks(["Alpha", "Bravo"], with_actions=True)
    palette = CommandPalette(blocks)

    assert palette._list.count() == 4

    action_texts = [
        palette._list.item(i).text()
        for i in range(palette._list.count())
        if "→" in palette._list.item(i).text()
    ]
    assert len(action_texts) == 2

    palette.close()


def test_action_selection_emits_action_signal(qapp):
    """Selecting an action item emits action_selected(block_id, action_id)."""
    blocks = _make_blocks(["Alpha"], with_actions=True)
    palette = CommandPalette(blocks)

    received = []
    palette.action_selected.connect(lambda bid, aid: received.append((bid, aid)))

    palette._list.setCurrentRow(1)
    palette._select_current()

    assert len(received) == 1
    assert received[0] == ("block-0", "act-0")
