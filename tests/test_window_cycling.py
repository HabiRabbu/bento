"""Tests for Ctrl+Tab / Ctrl+Shift+Tab block cycling in BentoWindow."""

from __future__ import annotations

import json
import os
import textwrap

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication



_BLOCK_PY = textwrap.dedent("""\
    from bento_app.blocks.base_block import BaseBlock, load_manifest

    class TestBlock(BaseBlock):
        @staticmethod
        def get_manifest():
            return load_manifest(__file__)
""")


def _make_block_data(tmp_path: Path, count: int):
    """Create *count* block dirs and return block_data via BlockLoader."""
    import bento_app.config as cfg_mod
    from bento_app.block_loader import BlockLoader

    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "config.json").write_text('{"animation_style": "none"}')
    (config_dir / ".env").write_text("")

    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir(exist_ok=True)
    builtin_dir = pkg_dir / "builtin_blocks"
    builtin_dir.mkdir(exist_ok=True)

    for i in range(count):
        bid = f"testblk{i}"
        bdir = builtin_dir / bid
        bdir.mkdir(exist_ok=True)
        manifest = {
            "id": bid,
            "name": f"Block {i}",
            "description": f"Test block {i}",
            "version": "1.0.0",
            "author": "test",
            "requires_config": [],
            "order": i,
        }
        (bdir / "manifest.json").write_text(json.dumps(manifest))
        (bdir / "block.py").write_text(_BLOCK_PY)
        (bdir / "icon.svg").write_text("<svg></svg>")

    loader = BlockLoader(pkg_dir)
    return loader.load_all()


def _make_window(tmp_path, monkeypatch, block_count):
    """Fully set up BentoWindow with *block_count* blocks."""
    import bento_app.config as cfg_mod

    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "config.json").write_text('{"animation_style": "none"}')
    (config_dir / ".env").write_text("")

    monkeypatch.setattr(cfg_mod, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(cfg_mod, "_CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(cfg_mod, "_ENV_FILE", config_dir / ".env")
    cfg_mod.BentoConfig._instance = None

    block_data = _make_block_data(tmp_path, block_count)

    from bento_app.window import BentoWindow
    window = BentoWindow(block_data)
    return window


def _key_event(key, modifiers=Qt.KeyboardModifier.NoModifier):
    """Create a QKeyEvent for a key press."""
    return QKeyEvent(QKeyEvent.Type.KeyPress, key, modifiers)



def test_ctrl_tab_wraps_last_to_first(qapp, tmp_path, monkeypatch):
    """Ctrl+Tab from the last block wraps back to block 0."""
    window = _make_window(tmp_path, monkeypatch, 3)

    window._switch_block(2)
    assert window._active_index == 2

    # Simulate Ctrl+Tab wrapping: (last + 1) % count == 0
    count = len(window._block_data)
    window._switch_block((window._active_index + 1) % count)

    assert window._active_index == 0
    window.close()


def test_ctrl_shift_tab_wraps_first_to_last(qapp, tmp_path, monkeypatch):
    """Ctrl+Shift+Tab from block 0 wraps to the last block."""
    window = _make_window(tmp_path, monkeypatch, 3)

    assert window._active_index == 0

    # Simulate Ctrl+Shift+Tab wrapping: (0 - 1) % 3 == 2
    count = len(window._block_data)
    window._switch_block((window._active_index - 1) % count)

    assert window._active_index == 2
    window.close()


def test_cycling_uses_block_data_length(qapp, tmp_path, monkeypatch):
    """Cycling modulo is based on len(block_data), not stack widget count."""
    window = _make_window(tmp_path, monkeypatch, 4)

    count = len(window._block_data)
    assert count == 4

    for expected in [1, 2, 3, 0]:
        window._switch_block((window._active_index + 1) % count)
        assert window._active_index == expected, f"Expected {expected}, got {window._active_index}"

    window.close()


def test_zero_blocks_no_crash(qapp, tmp_path, monkeypatch):
    """Ctrl+Tab with 0 blocks does not crash."""
    import bento_app.config as cfg_mod

    config_dir = tmp_path / "config"
    config_dir.mkdir(exist_ok=True)
    (config_dir / "config.json").write_text('{"animation_style": "none"}')
    (config_dir / ".env").write_text("")

    monkeypatch.setattr(cfg_mod, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(cfg_mod, "_CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(cfg_mod, "_ENV_FILE", config_dir / ".env")
    cfg_mod.BentoConfig._instance = None

    from bento_app.window import BentoWindow
    window = BentoWindow([])

    event_fwd = _key_event(Qt.Key.Key_Tab, Qt.KeyboardModifier.ControlModifier)
    window.keyPressEvent(event_fwd)

    event_back = _key_event(
        Qt.Key.Key_Backtab,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )
    window.keyPressEvent(event_back)

    window.close()
