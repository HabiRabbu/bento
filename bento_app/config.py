# MIT License — Copyright (c) 2026 HabiRabbu — see LICENSE
"""Bento configuration manager.

Reads non-sensitive settings from ~/.config/bento/config.json and sensitive
settings (API keys, secrets) from ~/.config/bento/.env.  Provides a singleton
accessor so every module shares the same configuration state.
"""

from __future__ import annotations

import json
import logging
import os
import stat
import tempfile
import threading
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "bento"
_CONFIG_FILE = _CONFIG_DIR / "config.json"
_ENV_FILE = _CONFIG_DIR / ".env"

_DEFAULTS: dict[str, Any] = {
    "window_height": 420,
    "window_width_percent": 70,
    "hotkey": "Meta+Shift+Space",
    "autostart": False,
    "lm_studio_base_url": "http://localhost:1234/v1",
    "lm_studio_model": "",
    "screen_mode": "follow_mouse",
    "animation_style": "slide",
    "animation_duration": 200,
    "window_position": "top",
    "disabled_blocks": [],
    "config_version": 1,
}

SENSITIVE_SUFFIXES = ("_KEY", "_SECRET", "_TOKEN", "_PASSWORD")


class BentoConfig:
    """Singleton configuration store for Bento."""

    _instance: BentoConfig | None = None
    _lock = threading.RLock()

    _SCHEMA: dict[str, type] = {
        "window_height": int,
        "window_width_percent": int,
        "autostart": bool,
        "hotkey": str,
        "lm_studio_base_url": str,
        "lm_studio_model": str,
        "disabled_blocks": list,
        "animation_style": str,
        "screen_mode": str,
        "window_position": str,
        "animation_duration": int,
        "config_version": int,
    }

    def __new__(cls) -> BentoConfig:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._loaded = False
                cls._instance._config_was_corrupted = False
            return cls._instance


    def load(self) -> None:
        """Load (or reload) config from disk."""
        with self._lock:
            self._load_unlocked()

    def _load_unlocked(self) -> None:
        """Internal load without acquiring the lock (caller must hold it)."""
        self._ensure_config_dir()
        self._data: dict[str, Any] = dict(_DEFAULTS)

        if _CONFIG_FILE.exists():
            try:
                with _CONFIG_FILE.open("r", encoding="utf-8") as fh:
                    self._data.update(json.load(fh))
            except json.JSONDecodeError as exc:
                logger.warning("Failed to parse %s: %s — backing up and using defaults", _CONFIG_FILE, exc)
                backup = _CONFIG_FILE.with_suffix(".json.bak")
                try:
                    _CONFIG_FILE.rename(backup)
                    logger.info("Corrupted config backed up to %s", backup)
                except OSError as rename_exc:
                    logger.warning("Could not back up corrupted config: %s", rename_exc)
                self._config_was_corrupted = True
            except OSError as exc:
                logger.warning("Failed to read %s: %s", _CONFIG_FILE, exc)

        if _ENV_FILE.exists():
            try:
                # Fix #6: enforce 0o600 permissions on .env at load time
                current_mode = _ENV_FILE.stat().st_mode & 0o777
                if current_mode != 0o600:
                    logger.warning(
                        ".env file has permissions %o, fixing to 600", current_mode
                    )
                    _ENV_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)
                env = dotenv_values(_ENV_FILE)
                self._data.update({k: v for k, v in env.items() if v is not None})
            except OSError as exc:
                logger.warning("Failed to read %s: %s", _ENV_FILE, exc)

        self._loaded = True

    def as_dict(self, *, mask_sensitive: bool = True) -> dict[str, Any]:
        """Return a copy of all config values. Sensitive values are masked by default."""
        with self._lock:
            if not self._loaded:
                self._load_unlocked()
            data = dict(self._data)
        if mask_sensitive:
            data = {k: ("****" if self.is_sensitive(k) else v) for k, v in data.items()}
        return data

    def get(self, key: str, default: Any = None) -> Any:
        """Return a config value, falling back to *default*."""
        with self._lock:
            if not self._loaded:
                self._load_unlocked()
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a config value in memory (call :meth:`save` to persist)."""
        with self._lock:
            if not self._loaded:
                self._load_unlocked()
            if key in self._SCHEMA and not isinstance(value, self._SCHEMA[key]):
                try:
                    value = self._SCHEMA[key](value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Invalid value for '{key}': expected {self._SCHEMA[key].__name__}"
                    ) from exc
            self._data[key] = value


    def get_int(self, key: str, default: int = 0) -> int:
        """Get a config value as int, with type coercion."""
        val = self.get(key, default)
        try:
            return int(val)
        except (TypeError, ValueError):
            return default

    def get_str(self, key: str, default: str = "") -> str:
        """Get a config value as string."""
        val = self.get(key, default)
        return str(val) if val is not None else default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a config value as bool."""
        val = self.get(key, default)
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes")
        return bool(val)

    def get_list(self, key: str, default: list | None = None) -> list:
        """Get a config value as list."""
        val = self.get(key, default if default is not None else [])
        return val if isinstance(val, list) else (default if default is not None else [])


    def save(self) -> None:
        """Persist current config to disk.

        Non-sensitive values go to ``config.json``; values whose key ends with
        a sensitive suffix go to ``.env`` (chmod 600).
        """
        with self._lock:
            self._ensure_config_dir()

            json_data: dict[str, Any] = {}
            env_data: dict[str, str] = {}

            for key, value in self._data.items():
                if self.is_sensitive(key):
                    env_data[key.upper()] = str(value) if value is not None else ""
                else:
                    json_data[key] = value

            config_file = str(_CONFIG_FILE)
            try:
                tmp_fd, tmp_path = tempfile.mkstemp(
                    dir=str(_CONFIG_DIR), suffix=".tmp"
                )
                try:
                    with os.fdopen(tmp_fd, "w") as fh:
                        json.dump(json_data, fh, indent=2)
                    os.replace(tmp_path, config_file)
                except BaseException:
                    os.unlink(tmp_path)
                    raise
            except OSError as exc:
                logger.error("Failed to write %s: %s", _CONFIG_FILE, exc)

            try:
                env_lines = []
                for k, v in sorted(env_data.items()):
                    escaped = v.replace("\\", "\\\\").replace('"', '\\"')
                    env_lines.append(f'{k}="{escaped}"')
                env_content = "\n".join(env_lines) + ("\n" if env_lines else "")

                env_fd, env_tmp = tempfile.mkstemp(
                    dir=str(_CONFIG_DIR), suffix=".env.tmp"
                )
                try:
                    os.fchmod(env_fd, stat.S_IRUSR | stat.S_IWUSR)
                    with os.fdopen(env_fd, "w") as fh:
                        fh.write(env_content)
                    os.replace(env_tmp, str(_ENV_FILE))
                except BaseException:
                    os.unlink(env_tmp)
                    raise
            except OSError as exc:
                logger.error("Failed to write %s: %s", _ENV_FILE, exc)


    def export_config(self, path: Path, *, include_secrets: bool = False) -> None:
        """Export config to a single JSON file.

        When *include_secrets* is ``False`` (default), sensitive keys are
        stripped.  When ``True``, the file is created with mode 0o600.
        """
        with self._lock:
            if not self._loaded:
                self._load_unlocked()
            data = dict(self._data)

        if not include_secrets:
            data = {k: v for k, v in data.items() if not self.is_sensitive(k)}

        dest = Path(path)
        if include_secrets:
            fd, tmp = tempfile.mkstemp(
                dir=str(dest.parent), suffix=".tmp"
            )
            try:
                os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, indent=2)
                os.replace(tmp, str(dest))
            except BaseException:
                os.unlink(tmp)
                raise
        else:
            dest.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def import_config(self, path: Path) -> None:
        """Import config from an exported file.

        Sensitive keys (matching :data:`SENSITIVE_SUFFIXES`) are silently
        skipped and a warning is logged for each one.
        """
        imported = json.loads(path.read_text(encoding="utf-8"))
        filtered: dict[str, Any] = {}
        for key, value in imported.items():
            if self.is_sensitive(key):
                logger.warning(
                    "import_config: skipping sensitive key '%s'", key
                )
            else:
                filtered[key] = value
        with self._lock:
            if not self._loaded:
                self._load_unlocked()
            self._data.update(filtered)
        self.save()


    @staticmethod
    def is_sensitive(key: str) -> bool:
        """Return ``True`` if *key* should be stored in ``.env``."""
        upper = key.upper()
        return any(upper.endswith(s) for s in SENSITIVE_SUFFIXES)

    @staticmethod
    def config_dir() -> Path:
        """Return the resolved config directory path."""
        return _CONFIG_DIR

    @staticmethod
    def env_file() -> Path:
        """Return the resolved .env file path."""
        return _ENV_FILE

    @staticmethod
    def _ensure_config_dir() -> None:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
