# MIT License — Copyright (c) 2026 HabiRabbu — see LICENSE
"""Abstract base class for all Bento blocks.

Every block must subclass :class:`BaseBlock` and live inside a folder that also
contains a ``manifest.json`` and an ``icon.svg``.  The block loader discovers
these folders automatically — no registration or static imports required.
"""

from __future__ import annotations

import abc
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, NotRequired, TypedDict

from PyQt6.QtWidgets import QWidget

# Increment when the block API changes in backward-incompatible ways.
BENTO_API_VERSION = 1


class _ABCQWidgetMeta(type(QWidget), abc.ABCMeta):
    """Resolve the metaclass conflict between QWidget and abc.ABC."""


class SettingField(TypedDict, total=False):
    """Schema for a single entry in the ``settings`` manifest array."""

    key: str
    label: str
    type: str  # "string", "bool", "int", "choice", "password"
    default: Any
    choices: list[str]
    min: int
    max: int


class Action(TypedDict, total=False):
    """Schema for an action returned by :meth:`BaseBlock.get_actions`."""

    id: str
    title: str
    description: str
    callback: Callable[[], None]



class ManifestDict(TypedDict):
    """Schema for a block's ``manifest.json``."""

    id: str
    name: str
    description: str
    version: str
    author: str
    order: NotRequired[int]
    requires_config: NotRequired[list[str]]
    api_version: NotRequired[int]
    settings: NotRequired[list[SettingField]]


class BaseBlock(QWidget, abc.ABC, metaclass=_ABCQWidgetMeta):
    """Abstract base class for all Bento blocks.

    Subclasses **must** implement :meth:`get_manifest`.  Override
    :meth:`on_focus` and :meth:`on_hide` as needed.

    Block lifecycle (call order)::

        __init__()
            ↓
        on_restore_state()      # restore persisted data
            ↓
        on_focus()              # block becomes visible (repeatable)
            ↓
        on_hide()               # window hidden (repeatable)
            ↓
        ...                     # on_focus / on_hide may repeat
            ↓
        on_save_state()         # persist data before quit
            ↓
        on_shutdown()           # release resources, final cleanup
    """

    def on_focus(self) -> None:
        """Called when this block becomes the active tab.

        Subclasses should auto-focus their primary input widget here.
        """

    def on_hide(self) -> None:
        """Called when the main window is hidden.

        Use to pause timers, cancel polling, stop ongoing work, etc.
        """

    def on_shutdown(self) -> None:
        """Called when the application is quitting.

        Override to clean up resources (close connections, flush caches).
        """

    def get_state_dir(self) -> Path:
        """Return a persistent state directory for this block.

        Uses ``$XDG_STATE_HOME/bento/<block_id>/`` (default ``~/.local/state/bento/<id>/``).
        """
        manifest = self.get_manifest()
        xdg_state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
        state_dir = xdg_state / "bento" / manifest["id"]
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir

    def on_save_state(self) -> None:
        """Called before app quits. Override to persist block state."""
        pass

    def on_restore_state(self) -> None:
        """Called after block instantiation. Override to restore saved state."""
        pass

    def get_actions(self) -> list[Action]:
        """Return searchable actions this block provides. Optional.

        Each action: {"id": "...", "title": "...", "description": "..."}
        """
        return []

    @staticmethod
    @abc.abstractmethod
    def get_manifest() -> ManifestDict:
        """Return the parsed ``manifest.json`` for this block.

        Subclasses **must** override this to return their own manifest.
        A convenience helper :func:`load_manifest` is provided below.
        """


    _manifest_cache: dict[str, ManifestDict] = {}

    @staticmethod
    def load_manifest(block_file: str) -> ManifestDict:
        """Load and cache ``manifest.json`` from the same directory as *block_file*."""
        manifest_path = str(Path(block_file).resolve().parent / "manifest.json")
        cached = BaseBlock._manifest_cache.get(manifest_path)
        if cached is not None:
            return cached
        with open(manifest_path, encoding="utf-8") as fh:
            data = json.load(fh)
        BaseBlock._manifest_cache[manifest_path] = data
        return data

    @classmethod
    def clear_manifest_cache(cls) -> None:
        """Clear cached manifests (called during hot-reload)."""
        cls._manifest_cache.clear()

    def validate_config(self) -> list[str]:
        """Return list of missing required config keys. Empty = valid."""
        from bento_app.config import BentoConfig
        config = BentoConfig()
        manifest = self.get_manifest()
        required = manifest.get("requires_config", [])
        missing = [k for k in required if config.get(k) is None]
        return missing


def load_manifest(block_file: str | Path) -> ManifestDict:
    """Load ``manifest.json`` from the same directory as *block_file*.

    Intended to be called from a block's :meth:`get_manifest` like::

        @staticmethod
        def get_manifest() -> dict:
            return load_manifest(__file__)

    Delegates to :meth:`BaseBlock.load_manifest` for caching.
    """
    return BaseBlock.load_manifest(str(block_file))
