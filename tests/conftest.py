"""Shared fixtures for the Bento test suite."""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path

import pytest

# Run Qt in offscreen mode so tests work without a display server.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_MINIMAL_BLOCK_PY = textwrap.dedent("""\
    from bento_app.blocks.base_block import BaseBlock, load_manifest

    class TestBlock(BaseBlock):
        @staticmethod
        def get_manifest():
            return load_manifest(__file__)
""")



@pytest.fixture()
def tmp_config_dir(tmp_path, monkeypatch):
    """Redirect BentoConfig to a temp directory with empty config files."""
    import bento_app.config as cfg_mod

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.json").write_text("{}")
    (config_dir / ".env").write_text("")

    monkeypatch.setattr(cfg_mod, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(cfg_mod, "_CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(cfg_mod, "_ENV_FILE", config_dir / ".env")
    cfg_mod.BentoConfig._instance = None

    yield config_dir

    cfg_mod.BentoConfig._instance = None



@pytest.fixture()
def sample_manifest(tmp_path):
    """Create a valid block directory with manifest.json, block.py, and icon.svg."""
    block_dir = tmp_path / "sample_block"
    block_dir.mkdir()

    manifest = {
        "id": "sample",
        "name": "Sample Block",
        "description": "A sample block for testing",
        "version": "1.0.0",
        "author": "test",
        "requires_config": [],
    }
    (block_dir / "manifest.json").write_text(json.dumps(manifest))
    (block_dir / "block.py").write_text(_MINIMAL_BLOCK_PY)
    (block_dir / "icon.svg").write_text("<svg></svg>")

    return block_dir


@pytest.fixture()
def invalid_manifest_dir(tmp_path):
    """Create a block directory with an invalid manifest (missing required fields)."""
    block_dir = tmp_path / "invalid_block"
    block_dir.mkdir()

    manifest = {"description": "Missing id, name, version"}
    (block_dir / "manifest.json").write_text(json.dumps(manifest))
    (block_dir / "block.py").write_text("# placeholder")
    (block_dir / "icon.svg").write_text("<svg></svg>")

    return block_dir


@pytest.fixture()
def make_block_dir():
    """Factory fixture: create a block directory with a valid manifest and block.py."""

    def _factory(
        parent: Path,
        block_id: str,
        *,
        order: int | None = None,
        extra_manifest: dict | None = None,
    ) -> Path:
        block_dir = parent / block_id
        block_dir.mkdir(parents=True, exist_ok=True)

        manifest: dict = {
            "id": block_id,
            "name": f"Test {block_id}",
            "description": f"Test block {block_id}",
            "version": "1.0.0",
            "author": "test",
            "requires_config": [],
        }
        if order is not None:
            manifest["order"] = order
        if extra_manifest:
            manifest.update(extra_manifest)

        (block_dir / "manifest.json").write_text(json.dumps(manifest))
        (block_dir / "block.py").write_text(_MINIMAL_BLOCK_PY)
        (block_dir / "icon.svg").write_text("<svg></svg>")
        return block_dir

    return _factory



@pytest.fixture()
def loader_env(tmp_path, monkeypatch, qapp):
    """Set up a BlockLoader pointed at temp builtin and user directories."""
    import bento_app.config as cfg_mod

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.json").write_text("{}")
    (config_dir / ".env").write_text("")

    monkeypatch.setattr(cfg_mod, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(cfg_mod, "_CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(cfg_mod, "_ENV_FILE", config_dir / ".env")
    cfg_mod.BentoConfig._instance = None

    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir()
    (pkg_dir / "builtin_blocks").mkdir()
    user_dir = config_dir / "blocks"
    user_dir.mkdir()

    from bento_app.block_loader import BlockLoader

    loader = BlockLoader(pkg_dir)

    yield loader, pkg_dir / "builtin_blocks", user_dir

    cfg_mod.BentoConfig._instance = None
