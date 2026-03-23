"""Integration smoke test — verifies the app starts without crashing."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_app_starts_and_exits(qapp, tmp_path, monkeypatch):
    """Full app initialization with mocked externals."""
    import bento_app.config as cfg_mod

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.json").write_text("{}")
    (config_dir / ".env").write_text("")

    monkeypatch.setattr(cfg_mod, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(cfg_mod, "_CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(cfg_mod, "_ENV_FILE", config_dir / ".env")
    cfg_mod.BentoConfig._instance = None

    # Mock dbus to avoid actual DBus calls
    mock_dbus = MagicMock()
    mock_dbus_glib = MagicMock()
    with patch.dict("sys.modules", {"dbus": mock_dbus, "dbus.mainloop": MagicMock(), "dbus.mainloop.glib": mock_dbus_glib}):
        from bento_app.block_loader import BlockLoader
        from bento_app.config import BentoConfig
        from bento_app.window import BentoWindow

        config = BentoConfig()
        config.load()

        pkg_dir = Path(__file__).resolve().parent.parent / "bento_app"
        loader = BlockLoader(pkg_dir)
        loaded = loader.load_all()

        assert len(loaded) >= 1
        block_ids = [m["id"] for m, _ in loaded]
        assert "demo" in block_ids

        window = BentoWindow(loaded)
        assert window is not None

        assert len(window.get_loaded_instances()) >= 1

        window.close()
        cfg_mod.BentoConfig._instance = None


def test_toggle_show_hide(qapp, tmp_path, monkeypatch):
    """toggle() shows the window, then hides it, with no crashes."""
    import json
    import bento_app.config as cfg_mod

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    # Disable animation to avoid timer-based async issues in tests
    (config_dir / "config.json").write_text(json.dumps({"animation_style": "none"}))
    (config_dir / ".env").write_text("")

    monkeypatch.setattr(cfg_mod, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(cfg_mod, "_CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(cfg_mod, "_ENV_FILE", config_dir / ".env")
    cfg_mod.BentoConfig._instance = None

    mock_dbus = MagicMock()
    mock_dbus_glib = MagicMock()
    with patch.dict("sys.modules", {"dbus": mock_dbus, "dbus.mainloop": MagicMock(), "dbus.mainloop.glib": mock_dbus_glib}):
        from bento_app.block_loader import BlockLoader
        from bento_app.config import BentoConfig
        from bento_app.window import BentoWindow

        config = BentoConfig()
        config.load()

        pkg_dir = Path(__file__).resolve().parent.parent / "bento_app"
        loader = BlockLoader(pkg_dir)
        loaded = loader.load_all()

        window = BentoWindow(loaded)

        assert not window.isVisible()

        window.toggle()
        assert window.isVisible()

        window.toggle()
        assert not window.isVisible()

        window.close()
        cfg_mod.BentoConfig._instance = None
