"""Tests for bento_app.block_loader.BlockLoader."""

from __future__ import annotations

import json
import shutil


def test_valid_block_loads(loader_env, sample_manifest):
    """A valid block loads correctly, returning manifest and class."""
    loader, _, user_dir = loader_env
    dest = user_dir / sample_manifest.name
    shutil.copytree(sample_manifest, dest)

    blocks = loader.load_all()
    assert len(blocks) == 1

    manifest, cls = blocks[0]
    assert manifest["id"] == "sample"
    assert manifest["name"] == "Sample Block"

    from bento_app.blocks.base_block import BaseBlock

    assert issubclass(cls, BaseBlock)


def test_missing_manifest_skipped(loader_env):
    """A directory without manifest.json is silently skipped."""
    loader, _, user_dir = loader_env
    nodir = user_dir / "no_manifest"
    nodir.mkdir()
    (nodir / "block.py").write_text("# nothing")

    blocks = loader.load_all()
    assert len(blocks) == 0


def test_missing_block_py_skipped(loader_env):
    """A directory with manifest.json but no block.py is skipped."""
    loader, _, user_dir = loader_env
    block_dir = user_dir / "no_blockpy"
    block_dir.mkdir()
    manifest = {"id": "no_blockpy", "name": "Test", "version": "1.0.0"}
    (block_dir / "manifest.json").write_text(json.dumps(manifest))

    blocks = loader.load_all()
    assert len(blocks) == 0


def test_invalid_manifest_skipped(loader_env, invalid_manifest_dir):
    """An invalid manifest (missing required keys) causes the block to be skipped."""
    loader, _, user_dir = loader_env
    dest = user_dir / invalid_manifest_dir.name
    shutil.copytree(invalid_manifest_dir, dest)

    blocks = loader.load_all()
    assert len(blocks) == 0


def test_invalid_block_id_rejected(loader_env):
    """A manifest with special characters in ID is rejected."""
    loader, _, user_dir = loader_env
    block_dir = user_dir / "bad_id"
    block_dir.mkdir()
    manifest = {
        "id": "bad/id!@#",
        "name": "Bad ID",
        "version": "1.0.0",
        "description": "test",
        "author": "test",
    }
    (block_dir / "manifest.json").write_text(json.dumps(manifest))
    (block_dir / "block.py").write_text("# placeholder")

    blocks = loader.load_all()
    assert len(blocks) == 0


def test_order_defaults(loader_env, make_block_dir):
    """A manifest without 'order' gets default order 1000."""
    loader, _, user_dir = loader_env
    make_block_dir(user_dir, "noorder")

    blocks = loader.load_all()
    assert len(blocks) == 1
    assert blocks[0][0].get("order") == 1000


def test_user_overrides_builtin(loader_env, make_block_dir):
    """User block with the same ID as a builtin takes precedence."""
    loader, builtin_dir, user_dir = loader_env
    make_block_dir(builtin_dir, "shared", extra_manifest={"description": "builtin"})
    make_block_dir(user_dir, "shared", extra_manifest={"description": "user"})

    blocks = loader.load_all()
    assert len(blocks) == 1
    assert blocks[0][0]["description"] == "user"


def test_sort_order(loader_env, make_block_dir):
    """Blocks are sorted by (order, id)."""
    loader, _, user_dir = loader_env
    make_block_dir(user_dir, "charlie", order=10)
    make_block_dir(user_dir, "alpha", order=10)
    make_block_dir(user_dir, "bravo", order=5)

    blocks = loader.load_all()
    ids = [b[0]["id"] for b in blocks]
    assert ids == ["bravo", "alpha", "charlie"]
