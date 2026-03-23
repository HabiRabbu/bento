"""Tests for manifest validation logic in bento_app.block_loader."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

_MINIMAL_BLOCK_PY = textwrap.dedent("""\
    from bento_app.blocks.base_block import BaseBlock, load_manifest

    class TestBlock(BaseBlock):
        @staticmethod
        def get_manifest():
            return load_manifest(__file__)
""")


def _make_block(parent: Path, dirname: str, manifest: dict) -> Path:
    """Create a block dir with the given manifest and a valid block.py."""
    block_dir = parent / dirname
    block_dir.mkdir(parents=True, exist_ok=True)
    (block_dir / "manifest.json").write_text(json.dumps(manifest))
    (block_dir / "block.py").write_text(_MINIMAL_BLOCK_PY)
    (block_dir / "icon.svg").write_text("<svg></svg>")
    return block_dir


def test_required_fields_present(loader_env):
    """A manifest with all required fields passes validation."""
    loader, _, user_dir = loader_env
    manifest = {"id": "valid", "name": "Valid", "version": "1.0.0"}
    block_dir = _make_block(user_dir, "valid", manifest)

    result = loader._load_block(block_dir)
    assert result is not None
    assert result[0]["id"] == "valid"


def test_missing_required_field_rejected(loader_env):
    """Each required field missing individually causes rejection."""
    loader, _, user_dir = loader_env

    for field in ("id", "name", "version"):
        manifest = {"id": "test", "name": "Test", "version": "1.0.0"}
        del manifest[field]
        block_dir = _make_block(user_dir, f"missing_{field}", manifest)

        result = loader._load_block(block_dir)
        assert result is None, f"Should reject manifest missing '{field}'"


def test_non_string_id_rejected(loader_env):
    """A numeric ID is rejected."""
    loader, _, user_dir = loader_env
    manifest = {"id": 123, "name": "Test", "version": "1.0.0"}
    block_dir = _make_block(user_dir, "numeric_id", manifest)

    result = loader._load_block(block_dir)
    assert result is None


def test_requires_config_must_be_list(loader_env):
    """Non-list requires_config is rejected."""
    loader, _, user_dir = loader_env
    manifest = {
        "id": "badconfig",
        "name": "Test",
        "version": "1.0.0",
        "requires_config": "not_a_list",
    }
    block_dir = _make_block(user_dir, "badconfig", manifest)

    result = loader._load_block(block_dir)
    assert result is None


def test_block_id_regex(loader_env):
    """Valid and invalid block IDs are correctly accepted/rejected."""
    loader, _, user_dir = loader_env

    valid_ids = ["my-block", "block_1", "SimpleBlock", "a"]
    for i, bid in enumerate(valid_ids):
        manifest = {"id": bid, "name": "Test", "version": "1.0.0"}
        block_dir = _make_block(user_dir, f"valid_{i}", manifest)
        result = loader._load_block(block_dir)
        assert result is not None, f"Valid ID '{bid}' should be accepted"

    invalid_ids = ["has spaces", "has/slash", "bad@char"]
    for i, bid in enumerate(invalid_ids):
        manifest = {"id": bid, "name": "Test", "version": "1.0.0"}
        block_dir = _make_block(user_dir, f"invalid_{i}", manifest)
        result = loader._load_block(block_dir)
        assert result is None, f"Invalid ID '{bid}' should be rejected"


def test_order_coercion(loader_env):
    """String '10' order is coerced to int 10."""
    loader, _, user_dir = loader_env
    manifest = {"id": "strorder", "name": "Test", "version": "1.0.0", "order": "10"}
    block_dir = _make_block(user_dir, "strorder", manifest)

    result = loader._load_block(block_dir)
    assert result is not None
    assert result[0]["order"] == 10
    assert isinstance(result[0]["order"], int)
