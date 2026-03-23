"""Tests for bento_app.cli — block management CLI commands."""

from __future__ import annotations

import json
from pathlib import Path


def test_create_block_scaffolds_files(tmp_path, monkeypatch):
    """create_block creates manifest.json, block.py, and icon.svg."""
    import bento_app.config as cfg_mod
    from bento_app import cli

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.json").write_text("{}")
    (config_dir / ".env").write_text("")

    monkeypatch.setattr(cfg_mod, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(cfg_mod, "_CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(cfg_mod, "_ENV_FILE", config_dir / ".env")
    cfg_mod.BentoConfig._instance = None

    try:
        cli.create_block("my-test-block")

        block_dir = config_dir / "blocks" / "my-test-block"
        assert block_dir.is_dir()
        assert (block_dir / "manifest.json").exists()
        assert (block_dir / "block.py").exists()
        assert (block_dir / "icon.svg").exists()

        manifest = json.loads((block_dir / "manifest.json").read_text())
        assert manifest["id"] == "my-test-block"

        block_py = (block_dir / "block.py").read_text()
        assert "MyTestBlockBlock" in block_py
    finally:
        cfg_mod.BentoConfig._instance = None


def test_create_block_rejects_invalid_name(tmp_path, monkeypatch, capsys):
    """Names with spaces or special characters are rejected."""
    import bento_app.config as cfg_mod
    from bento_app import cli

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.json").write_text("{}")
    (config_dir / ".env").write_text("")

    monkeypatch.setattr(cfg_mod, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(cfg_mod, "_CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(cfg_mod, "_ENV_FILE", config_dir / ".env")
    cfg_mod.BentoConfig._instance = None

    try:
        for bad_name in ["has space", "UPPER", "special@char", "", "a/b"]:
            cli.create_block(bad_name)
            captured = capsys.readouterr()
            assert "Error" in captured.out, f"Expected error for name '{bad_name}'"

            blocks_dir = config_dir / "blocks"
            if blocks_dir.exists():
                assert not (blocks_dir / bad_name).exists()
    finally:
        cfg_mod.BentoConfig._instance = None


def test_list_blocks_shows_builtin(monkeypatch, capsys, tmp_path):
    """list_blocks prints a table including built-in blocks."""
    import bento_app.config as cfg_mod
    from bento_app import cli

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.json").write_text("{}")
    (config_dir / ".env").write_text("")

    monkeypatch.setattr(cfg_mod, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(cfg_mod, "_CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(cfg_mod, "_ENV_FILE", config_dir / ".env")
    cfg_mod.BentoConfig._instance = None

    try:
        cli.list_blocks()
        captured = capsys.readouterr()
        # Should show column headers
        assert "ID" in captured.out
        assert "Name" in captured.out
        assert "Source" in captured.out
        # Should show at least the demo block
        assert "demo" in captured.out
        assert "built-in" in captured.out
    finally:
        cfg_mod.BentoConfig._instance = None


def test_enable_disable_toggles_config(tmp_config_dir, capsys):
    """disable_block adds to disabled_blocks; enable_block removes it."""
    import bento_app.config as cfg_mod
    from bento_app.cli import disable_block, enable_block
    from bento_app.config import BentoConfig

    cfg = BentoConfig()
    cfg.load()

    disable_block("my-block")
    disabled = cfg.get_list("disabled_blocks", [])
    assert "my-block" in disabled

    # Disabling again should say already disabled
    disable_block("my-block")
    captured = capsys.readouterr()
    assert "already disabled" in captured.out

    # Reset singleton to re-read from disk
    cfg_mod.BentoConfig._instance = None
    cfg2 = BentoConfig()
    cfg2.load()
    assert "my-block" in cfg2.get_list("disabled_blocks", [])

    enable_block("my-block")
    disabled = cfg2.get_list("disabled_blocks", [])
    assert "my-block" not in disabled

    # Enabling again should say already enabled
    enable_block("my-block")
    captured = capsys.readouterr()
    assert "already enabled" in captured.out
