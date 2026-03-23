"""Tests for bento_app.first_run — first-run welcome dialog."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_should_show_first_run_true_by_default(tmp_config_dir):
    """A fresh config directory has no first_run_shown flag → returns True."""
    from bento_app.first_run import should_show_first_run

    assert should_show_first_run() is True


def test_should_show_first_run_false_after_shown(tmp_config_dir):
    """After setting first_run_shown=True, should_show_first_run returns False."""
    from bento_app.config import BentoConfig
    from bento_app.first_run import should_show_first_run

    cfg = BentoConfig()
    cfg.load()
    cfg.set("first_run_shown", True)
    cfg.save()

    assert should_show_first_run() is False


def test_first_run_dialog_creates(qapp, tmp_config_dir):
    """FirstRunDialog can be instantiated without error."""
    from bento_app.first_run import FirstRunDialog

    dialog = FirstRunDialog()
    assert dialog is not None
    assert dialog.windowTitle() == "Welcome to Bento"
    dialog.close()


def test_open_settings_requested_default_false(qapp, tmp_config_dir):
    """open_settings_requested is False by default."""
    from bento_app.first_run import FirstRunDialog

    dialog = FirstRunDialog()
    assert dialog.open_settings_requested is False
    dialog.close()
