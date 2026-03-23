# MIT License — Copyright (c) 2026 HabiRabbu — see LICENSE
"""Testing utilities for Bento block developers.

Provides lightweight helpers that let you instantiate and test a block without
starting the full Bento application, reading disk config, or interacting with
the system tray.

Example usage
-------------
::

    from bento_app.testing import FakeConfig, MockNotifier, create_test_block
    from my_block.block import MyBlock

    def test_my_block_renders():
        config = FakeConfig({"api_key": "test-key"})
        block = create_test_block(MyBlock, config=config)
        assert block is not None
        assert block.get_manifest()["id"] == "my-block"

    def test_notifications():
        notifier = MockNotifier()
        notifier.notify_info("Hello", "World")
        assert notifier.calls[0] == ("info", "Hello", "World")

    def test_missing_config():
        config = FakeConfig({})
        block = create_test_block(MyBlock, config=config)
        missing = block.validate_config()
        assert "api_key" in missing
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from bento_app.blocks.base_block import BaseBlock, ManifestDict



class FakeConfig:
    """Drop-in replacement for :class:`~bento_app.config.BentoConfig`.

    Stores all values in a plain dict.  Supports the same public API
    (``get``, ``set``, ``save``, typed accessors) but never touches disk.

    Parameters
    ----------
    data:
        Initial configuration dictionary.  Sensitive-key detection still
        works, but nothing is written to an ``.env`` file.
    """

    _lock = threading.Lock()

    SENSITIVE_SUFFIXES = ("_KEY", "_SECRET", "_TOKEN", "_PASSWORD")

    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self._data: dict[str, Any] = dict(data) if data else {}
        self._loaded = True
        self._saved: list[dict[str, Any]] = []


    def load(self) -> None:
        """No-op (data is already in memory)."""

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def save(self) -> None:
        """Record a snapshot instead of writing to disk."""
        self._saved.append(dict(self._data))


    def get_int(self, key: str, default: int = 0) -> int:
        val = self.get(key, default)
        try:
            return int(val)
        except (TypeError, ValueError):
            return default

    def get_str(self, key: str, default: str = "") -> str:
        val = self.get(key, default)
        return str(val) if val is not None else default

    def get_bool(self, key: str, default: bool = False) -> bool:
        val = self.get(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes")
        return bool(val)

    def get_list(self, key: str, default: list | None = None) -> list:
        val = self.get(key, default if default is not None else [])
        return val if isinstance(val, list) else (default if default is not None else [])


    @staticmethod
    def is_sensitive(key: str) -> bool:
        upper = key.upper()
        return any(upper.endswith(s) for s in FakeConfig.SENSITIVE_SUFFIXES)

    @staticmethod
    def config_dir() -> Path:
        """Return a dummy path — nothing is written."""
        return Path("/tmp/bento-test-config")

    @staticmethod
    def env_file() -> Path:
        return Path("/tmp/bento-test-config/.env")



class MockNotifier:
    """Captures ``notify_*`` calls instead of showing tray balloons.

    After calling the helper methods, inspect :attr:`calls` to assert::

        notifier = MockNotifier()
        notifier.notify_warning("Oops", "Something broke")
        assert len(notifier.calls) == 1
        level, title, msg = notifier.calls[0]
        assert level == "warning"
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def notify_info(self, title: str, message: str) -> None:
        self.calls.append(("info", title, message))

    def notify_warning(self, title: str, message: str) -> None:
        self.calls.append(("warning", title, message))

    def notify_error(self, title: str, message: str) -> None:
        self.calls.append(("error", title, message))

    def clear(self) -> None:
        """Reset captured calls."""
        self.calls.clear()



_DEFAULT_MANIFEST: ManifestDict = {
    "id": "test-block",
    "name": "Test Block",
    "description": "Auto-generated manifest for testing",
    "version": "0.0.0",
    "author": "test",
    "requires_config": [],
    "order": 1000,
    "api_version": 1,
}


def create_test_block(
    block_class: type[BaseBlock],
    *,
    config: FakeConfig | None = None,
    manifest: ManifestDict | None = None,
) -> BaseBlock:
    """Instantiate a block with mocked dependencies for testing.

    Parameters
    ----------
    block_class:
        The ``BaseBlock`` subclass to instantiate.
    config:
        Optional :class:`FakeConfig`.  If supplied, it is monkey-patched into
        ``bento_app.config.BentoConfig`` for the duration of the block's
        ``validate_config()`` calls.
    manifest:
        Optional manifest dict.  Not currently patched onto the class (the
        block's own ``get_manifest()`` is used), but stored on the instance
        as ``_test_manifest`` for convenient access in tests.

    Returns
    -------
    BaseBlock
        A fully constructed block widget ready for assertion.
    """
    if config is not None:
        import bento_app.config as cfg_mod
        original_instance = cfg_mod.BentoConfig._instance
        cfg_mod.BentoConfig._instance = config  # type: ignore[assignment]
        try:
            instance = block_class()
        finally:
            cfg_mod.BentoConfig._instance = original_instance
    else:
        instance = block_class()

    instance._test_manifest = manifest or _DEFAULT_MANIFEST  # type: ignore[attr-defined]
    return instance
