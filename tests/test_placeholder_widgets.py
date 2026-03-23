"""Tests for bento_app.placeholder_widgets — loading, error, empty states."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock

import pytest

from bento_app.placeholder_widgets import (
    EmptyPlaceholder,
    ErrorPlaceholder,
    LoadingPlaceholder,
)


def test_loading_placeholder_creates(qapp):
    """LoadingPlaceholder instantiates without error."""
    widget = LoadingPlaceholder("TestBlock")
    assert widget is not None
    assert "Loading" in widget._text_label.text()
    widget.close()


def test_loading_placeholder_spinner_updates(qapp, qtbot):
    """Spinner advances through frames on timer tick."""
    widget = LoadingPlaceholder("TestBlock")
    initial_frame = widget._frame_idx

    # Manually advance the spinner
    widget._advance()
    assert widget._frame_idx == (initial_frame + 1) % len(widget._frames)
    assert widget._spinner_label.text() == widget._frames[widget._frame_idx]

    widget._advance()
    assert widget._frame_idx == (initial_frame + 2) % len(widget._frames)

    widget.close()


def test_error_placeholder_shows_info(qapp):
    """ErrorPlaceholder displays the exception name and traceback."""
    exc = ValueError("something broke")
    tb = "Traceback (most recent call last):\n  File test.py, line 1\nValueError: something broke"

    widget = ErrorPlaceholder("MyBlock", exc, tb_text=tb)
    assert widget is not None

    # Walk all labels and verify content is present
    from PyQt6.QtWidgets import QLabel

    labels = widget.findChildren(QLabel)
    all_text = " ".join(lbl.text() for lbl in labels)
    assert "MyBlock" in all_text
    assert "ValueError" in all_text
    assert "something broke" in all_text

    widget.close()


def test_error_placeholder_reload_callback(qapp):
    """Reload button fires the on_reload callback when clicked."""
    callback = MagicMock()
    exc = RuntimeError("crash")

    widget = ErrorPlaceholder("MyBlock", exc, on_reload=callback)

    from PyQt6.QtWidgets import QPushButton

    buttons = widget.findChildren(QPushButton)
    assert len(buttons) == 1
    buttons[0].click()
    callback.assert_called_once()

    widget.close()


def test_empty_placeholder_creates(qapp):
    """EmptyPlaceholder instantiates without error."""
    widget = EmptyPlaceholder()
    assert widget is not None

    from PyQt6.QtWidgets import QLabel

    labels = widget.findChildren(QLabel)
    all_text = " ".join(lbl.text() for lbl in labels)
    assert "No blocks installed" in all_text

    widget.close()
