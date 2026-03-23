# MIT License — Copyright (c) 2026 HabiRabbu — see LICENSE
"""Dynamic block discovery and loading.

Scans built-in and user block directories, parses manifests, and dynamically
imports block modules via :mod:`importlib`.  No block is ever statically
imported anywhere in the core application.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import logging
import re
import shutil
import sys
from pathlib import Path

from PyQt6.QtCore import QFileSystemWatcher, QObject, QTimer, pyqtSignal

from bento_app.blocks.base_block import BENTO_API_VERSION, BaseBlock, ManifestDict
from bento_app.config import BentoConfig
from bento_app.notify import notify_warning

logger = logging.getLogger(__name__)

_REQUIRED_MANIFEST_KEYS = {"id", "name", "version"}
_VALID_BLOCK_ID = re.compile(r"^[a-zA-Z0-9_-]+$")


class BlockLoader(QObject):
    """Discovers, loads, and watches Bento block folders."""

    blocks_changed = pyqtSignal()

    def __init__(self, pkg_dir: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pkg_dir = pkg_dir
        self._config = BentoConfig()

        self._builtin_dir = pkg_dir / "builtin_blocks"
        self._user_dir = BentoConfig.config_dir() / "blocks"
        self._user_dir.mkdir(parents=True, exist_ok=True)

        self._block_paths: dict[str, Path] = {}

        self._watcher = QFileSystemWatcher(self)
        self._watcher.addPath(str(self._user_dir))
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(500)
        self._debounce.timeout.connect(self._on_debounce)
        self._watcher.directoryChanged.connect(self._on_dir_changed)
        self._watcher.fileChanged.connect(self._on_dir_changed)

        self._blocks: list[tuple[ManifestDict, type[BaseBlock]]] = []


    def load_all(self) -> list[tuple[ManifestDict, type[BaseBlock]]]:
        """Scan both block directories and return loaded blocks.

        Returns a list of ``(manifest, BlockClass)`` sorted by
        ``(order, id)`` for deterministic ordering.  User blocks override
        built-in blocks that share the same ID.
        """
        self._block_paths.clear()
        found: dict[str, tuple[ManifestDict, type[BaseBlock]]] = {}

        for result in self._scan_directory(self._builtin_dir):
            found[result[0]["id"]] = result

        for result in self._scan_directory(self._user_dir):
            block_id = result[0]["id"]
            if block_id in found:
                logger.info("User block '%s' overrides built-in block", block_id)
            found[block_id] = result

        results = sorted(
            found.values(),
            key=lambda item: (item[0].get("order", 1000), item[0]["id"]),
        )

        disabled = self._config.get_list("disabled_blocks", [])
        results = [(m, cls) for m, cls in results if m["id"] not in disabled]

        self._blocks = results
        self._refresh_watcher()
        return self._blocks

    @property
    def blocks(self) -> list[tuple[ManifestDict, type[BaseBlock]]]:
        """Return the most recently loaded block list."""
        return self._blocks


    def _scan_directory(
        self, directory: Path
    ) -> list[tuple[ManifestDict, type[BaseBlock]]]:
        results: list[tuple[ManifestDict, type[BaseBlock]]] = []
        failures: list[str] = []
        if not directory.is_dir():
            return results

        for entry in sorted(directory.iterdir()):
            if not entry.is_dir():
                continue
            try:
                result = self._load_block(entry)
                if result is not None:
                    results.append(result)
                    self._block_paths[result[0]["id"]] = entry
            except Exception:
                logger.warning("Failed to load block from '%s'", entry.name, exc_info=True)
                failures.append(entry.name)

        if failures:
            if len(failures) <= 3:
                detail = ", ".join(failures)
                notify_warning("Block error", f"Failed to load: {detail}")
            else:
                notify_warning(
                    "Block error",
                    f"{len(failures)} block(s) failed to load \u2014 check logs for details",
                )

        return results

    def _load_block(
        self, block_dir: Path
    ) -> tuple[ManifestDict, type[BaseBlock]] | None:
        manifest_path = block_dir / "manifest.json"
        block_py = block_dir / "block.py"

        if not manifest_path.exists():
            logger.warning("Skipping '%s': missing manifest.json", block_dir.name)
            return None
        if not block_py.exists():
            logger.warning("Skipping '%s': missing block.py", block_dir.name)
            return None

        try:
            with manifest_path.open("r", encoding="utf-8") as fh:
                manifest: ManifestDict = json.load(fh)
        except json.JSONDecodeError as exc:
            logger.warning("Invalid JSON in %s/manifest.json (line %d): %s", block_dir.name, exc.lineno, exc.msg)
            notify_warning("Block error", f"Invalid JSON in '{block_dir.name}/manifest.json' at line {exc.lineno}")
            return None

        missing = _REQUIRED_MANIFEST_KEYS - manifest.keys()
        if missing:
            logger.warning(
                "Skipping '%s': manifest missing keys %s", block_dir.name, missing
            )
            return None

        for key in ("id", "name", "version"):
            if not isinstance(manifest.get(key), str) or not manifest[key].strip():
                logger.warning(
                    "Skipping '%s': manifest '%s' must be a non-empty string",
                    block_dir.name, key,
                )
                return None

        if not _VALID_BLOCK_ID.match(manifest["id"]):
            logger.warning(
                "Skipping '%s': block ID contains invalid characters", block_dir.name
            )
            return None

        req_config = manifest.get("requires_config", [])
        if not isinstance(req_config, list) or not all(isinstance(k, str) for k in req_config):
            logger.warning(
                "Skipping '%s': requires_config must be a list of strings",
                block_dir.name,
            )
            return None

        block_api = manifest.get("api_version", 1)
        if not isinstance(block_api, int) or block_api > BENTO_API_VERSION:
            logger.warning(
                "Block '%s' requires API version %s but Bento supports up to %s",
                manifest["id"], block_api, BENTO_API_VERSION,
            )
            notify_warning("Block incompatible", f"'{manifest['id']}' requires a newer Bento version")
            return None

        if "order" in manifest:
            try:
                manifest["order"] = int(manifest["order"])
            except (TypeError, ValueError):
                logger.warning(
                    "Block '%s': invalid order value, defaulting to 1000",
                    block_dir.name,
                )
                manifest["order"] = 1000
        else:
            manifest["order"] = 1000

        module_name = f"bento_block_{manifest['id']}"
        spec = importlib.util.spec_from_file_location(module_name, block_py)
        if spec is None or spec.loader is None:
            logger.warning("Skipping '%s': could not create module spec", block_dir.name)
            return None

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except SyntaxError as exc:
            logger.warning("Syntax error in %s/block.py (line %s): %s", block_dir.name, exc.lineno, exc.msg)
            notify_warning("Block error", f"Syntax error in '{block_dir.name}/block.py' line {exc.lineno}")
            return None
        except ImportError as exc:
            logger.warning("Import error in %s/block.py: %s", block_dir.name, exc)
            notify_warning("Block error", f"Import error in '{block_dir.name}/block.py': {exc.name}")
            return None

        block_cls: type[BaseBlock] | None = None
        for _name, cls in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(cls, BaseBlock)
                and cls is not BaseBlock
                and cls.__module__ == module_name
            ):
                block_cls = cls
                break

        if block_cls is None:
            logger.warning(
                "Skipping '%s': no BaseBlock subclass found in block.py",
                block_dir.name,
            )
            return None

        logger.info("Loaded block '%s' v%s", manifest["id"], manifest.get("version", "?"))
        return manifest, block_cls


    def _on_dir_changed(self, _path: str) -> None:
        self._debounce.start()

    def _on_debounce(self) -> None:
        logger.info("User blocks directory changed — hot-reloading")
        try:
            self._bust_block_caches()
            self.load_all()
            self.blocks_changed.emit()
        except Exception:
            logger.error("Hot-reload failed", exc_info=True)
            notify_warning("Hot-reload failed", "An error occurred while reloading blocks.")

    def _bust_block_caches(self) -> None:
        """Remove cached block modules from sys.modules to force reimport."""
        if hasattr(BaseBlock, "clear_manifest_cache"):
            BaseBlock.clear_manifest_cache()
        importlib.invalidate_caches()
        to_remove = [n for n in sys.modules if n.startswith("bento_block_")]
        for name in to_remove:
            del sys.modules[name]
        if to_remove:
            logger.debug("Busted cache for %d block module(s)", len(to_remove))

        if self._user_dir.is_dir():
            for child in self._user_dir.iterdir():
                if child.is_dir():
                    pycache = child / "__pycache__"
                    if pycache.is_dir():
                        shutil.rmtree(pycache, ignore_errors=True)
                        logger.debug("Removed %s", pycache)

    def reload_block(
        self, block_id: str
    ) -> tuple[ManifestDict, type[BaseBlock]] | None:
        """Bust cache and reimport a single block by ID.

        Returns the fresh ``(manifest, class)`` or ``None`` on failure.
        """
        block_dir = self._block_paths.get(block_id)
        if block_dir is None:
            logger.warning("No known path for block '%s'", block_id)
            return None

        module_name = f"bento_block_{block_id}"
        if module_name in sys.modules:
            del sys.modules[module_name]
        importlib.invalidate_caches()

        try:
            return self._load_block(block_dir)
        except Exception:
            logger.warning(
                "Failed to reload block '%s'", block_id, exc_info=True
            )
        return None

    def _refresh_watcher(self) -> None:
        """Update watcher to cover user block subdirectories and files."""
        current_dirs = set(self._watcher.directories())
        desired_dirs = {str(self._user_dir)}
        if self._user_dir.is_dir():
            for child in self._user_dir.iterdir():
                if child.is_dir():
                    desired_dirs.add(str(child))
        dirs_to_add = desired_dirs - current_dirs
        dirs_to_remove = current_dirs - desired_dirs
        if dirs_to_remove:
            self._watcher.removePaths(list(dirs_to_remove))
        if dirs_to_add:
            self._watcher.addPaths(list(dirs_to_add))

        current_files = set(self._watcher.files())
        desired_files: set[str] = set()
        for block_dir in self._block_paths.values():
            for fname in ("block.py", "manifest.json"):
                fpath = block_dir / fname
                if fpath.exists():
                    desired_files.add(str(fpath))
        files_to_add = desired_files - current_files
        files_to_remove = current_files - desired_files
        if files_to_remove:
            self._watcher.removePaths(list(files_to_remove))
        if files_to_add:
            self._watcher.addPaths(list(files_to_add))
