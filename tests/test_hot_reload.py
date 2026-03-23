"""Tests for hot-reload paths in BlockLoader and BentoWindow."""

from __future__ import annotations

import json
import os
import sys
import textwrap

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

import pytest


_BLOCK_PY_V1 = textwrap.dedent("""\
    from bento_app.blocks.base_block import BaseBlock, load_manifest

    VERSION = 1

    class TestBlock(BaseBlock):
        @staticmethod
        def get_manifest():
            return load_manifest(__file__)
""")

_BLOCK_PY_V2 = textwrap.dedent("""\
    from bento_app.blocks.base_block import BaseBlock, load_manifest

    VERSION = 2

    class TestBlock(BaseBlock):
        @staticmethod
        def get_manifest():
            return load_manifest(__file__)
""")


def _write_block(parent: Path, block_id: str, block_py: str, *, order: int = 0) -> Path:
    """Write a block directory with the given source."""
    bdir = parent / block_id
    bdir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "id": block_id,
        "name": f"Test {block_id}",
        "description": f"Desc {block_id}",
        "version": "1.0.0",
        "author": "test",
        "requires_config": [],
        "order": order,
    }
    (bdir / "manifest.json").write_text(json.dumps(manifest))
    (bdir / "block.py").write_text(block_py)
    (bdir / "icon.svg").write_text("<svg></svg>")
    return bdir



def test_bust_clears_sys_modules(loader_env):
    """_bust_block_caches() removes bento_block_* entries from sys.modules."""
    loader, _builtin, _user = loader_env

    sys.modules["bento_block_alpha"] = type(sys)("bento_block_alpha")
    sys.modules["bento_block_beta"] = type(sys)("bento_block_beta")
    sys.modules["unrelated_module"] = type(sys)("unrelated_module")

    loader._bust_block_caches()

    assert "bento_block_alpha" not in sys.modules
    assert "bento_block_beta" not in sys.modules
    assert "unrelated_module" in sys.modules

    del sys.modules["unrelated_module"]


def test_bust_clears_pycache(loader_env, make_block_dir):
    """_bust_block_caches() removes __pycache__ in user block dirs."""
    loader, _builtin, user_dir = loader_env

    make_block_dir(user_dir, "cachetest")
    pycache = user_dir / "cachetest" / "__pycache__"
    pycache.mkdir()
    (pycache / "block.cpython-311.pyc").write_bytes(b"fake")

    loader._bust_block_caches()

    assert not pycache.exists()



def test_reload_block_reimports(loader_env, make_block_dir):
    """reload_block() picks up a modified block.py."""
    loader, builtin_dir, _user = loader_env

    _write_block(builtin_dir, "reloadme", _BLOCK_PY_V1)
    loaded = loader.load_all()
    assert any(m["id"] == "reloadme" for m, _ in loaded)

    (builtin_dir / "reloadme" / "block.py").write_text(_BLOCK_PY_V2)

    result = loader.reload_block("reloadme")
    assert result is not None
    manifest, cls = result
    assert manifest["id"] == "reloadme"

    mod_name = "bento_block_reloadme"
    assert mod_name not in sys.modules or hasattr(sys.modules[mod_name], "VERSION")


def test_reload_nonexistent_returns_none(loader_env):
    """reload_block() returns None for an ID that doesn't exist."""
    loader, _b, _u = loader_env
    assert loader.reload_block("no_such_block") is None



def test_handle_blocks_changed_updates_sidebar(qapp, tmp_path, monkeypatch):
    """handle_blocks_changed() rebuilds sidebar buttons to match new blocks."""
    import bento_app.config as cfg_mod

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(json.dumps({"animation_style": "none"}))
    (config_dir / ".env").write_text("")

    monkeypatch.setattr(cfg_mod, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(cfg_mod, "_CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(cfg_mod, "_ENV_FILE", config_dir / ".env")
    cfg_mod.BentoConfig._instance = None

    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir()
    builtin_dir = pkg_dir / "builtin_blocks"
    builtin_dir.mkdir()

    _write_block(builtin_dir, "blk-a", _BLOCK_PY_V1, order=0)
    _write_block(builtin_dir, "blk-b", _BLOCK_PY_V1, order=1)

    from bento_app.block_loader import BlockLoader
    from bento_app.window import BentoWindow

    loader = BlockLoader(pkg_dir)
    original = loader.load_all()
    assert len(original) == 2

    window = BentoWindow(original)
    window.set_loader(loader)
    assert len(window._buttons) == 2

    _write_block(builtin_dir, "blk-c", _BLOCK_PY_V1, order=2)
    new_data = loader.load_all()
    assert len(new_data) == 3

    window.handle_blocks_changed(new_data)
    assert len(window._buttons) == 3
    assert len(window._block_data) == 3

    window.close()
    cfg_mod.BentoConfig._instance = None
