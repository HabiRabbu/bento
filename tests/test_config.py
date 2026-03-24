"""Tests for bento_app.config.BentoConfig."""

from __future__ import annotations

import json
import os
import stat


def test_defaults(tmp_config_dir):
    """Fresh config has all default values."""
    from bento_app.config import BentoConfig, _DEFAULTS

    cfg = BentoConfig()
    cfg.load()

    for key, value in _DEFAULTS.items():
        assert cfg.get(key) == value, f"Default mismatch for '{key}'"


def test_load_json(tmp_config_dir):
    """Custom values in config.json override defaults."""
    from bento_app.config import BentoConfig

    config_file = tmp_config_dir / "config.json"
    config_file.write_text(json.dumps({"window_height": 800, "custom_key": "hello"}))

    cfg = BentoConfig()
    cfg.load()

    assert cfg.get("window_height") == 800
    assert cfg.get("custom_key") == "hello"


def test_load_env(tmp_config_dir):
    """Uppercase .env keys are loaded preserving their original case."""
    from bento_app.config import BentoConfig

    env_file = tmp_config_dir / ".env"
    env_file.write_text("MY_API_KEY=secret123\nANOTHER_TOKEN=tok456\n")

    cfg = BentoConfig()
    cfg.load()

    assert cfg.get("MY_API_KEY") == "secret123"
    assert cfg.get("ANOTHER_TOKEN") == "tok456"


def test_save_roundtrip(tmp_config_dir):
    """Values set and saved persist across singleton resets."""
    import bento_app.config as cfg_mod

    cfg = cfg_mod.BentoConfig()
    cfg.load()
    cfg.set("window_height", 800)
    cfg.set("MY_API_KEY", "secret123")
    cfg.save()

    # Reset singleton to simulate a fresh load
    cfg_mod.BentoConfig._instance = None

    cfg2 = cfg_mod.BentoConfig()
    cfg2.load()
    assert cfg2.get("window_height") == 800
    assert cfg2.get("MY_API_KEY") == "secret123"


def test_env_permissions(tmp_config_dir):
    """After save, .env file has mode 0o600."""
    from bento_app.config import BentoConfig

    cfg = BentoConfig()
    cfg.load()
    cfg.set("my_api_key", "secret")
    cfg.save()

    env_file = tmp_config_dir / ".env"
    mode = stat.S_IMODE(os.stat(env_file).st_mode)
    assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"


def test_missing_dir_created(tmp_path, monkeypatch):
    """Config directory is created if it does not exist."""
    import bento_app.config as cfg_mod

    new_dir = tmp_path / "nonexistent" / "config"
    monkeypatch.setattr(cfg_mod, "_CONFIG_DIR", new_dir)
    monkeypatch.setattr(cfg_mod, "_CONFIG_FILE", new_dir / "config.json")
    monkeypatch.setattr(cfg_mod, "_ENV_FILE", new_dir / ".env")
    cfg_mod.BentoConfig._instance = None

    try:
        cfg = cfg_mod.BentoConfig()
        cfg.load()
        assert new_dir.exists()
    finally:
        cfg_mod.BentoConfig._instance = None


def test_is_sensitive():
    """Keys ending with _KEY, _SECRET, _TOKEN, _PASSWORD are sensitive."""
    from bento_app.config import BentoConfig

    assert BentoConfig.is_sensitive("my_api_key") is True
    assert BentoConfig.is_sensitive("MY_API_KEY") is True
    assert BentoConfig.is_sensitive("db_secret") is True
    assert BentoConfig.is_sensitive("auth_token") is True
    assert BentoConfig.is_sensitive("user_password") is True
    assert BentoConfig.is_sensitive("window_height") is False
    assert BentoConfig.is_sensitive("hotkey") is False
    assert BentoConfig.is_sensitive("autostart") is False



def test_export_strips_secrets(tmp_config_dir, tmp_path):
    """export_config(include_secrets=False) strips sensitive keys."""
    from bento_app.config import BentoConfig

    cfg = BentoConfig()
    cfg.load()
    cfg.set("window_height", 600)
    cfg.set("my_api_key", "super-secret")
    cfg.set("db_password", "hunter2")

    out = tmp_path / "export.json"
    cfg.export_config(out, include_secrets=False)

    exported = json.loads(out.read_text())
    assert "window_height" in exported
    assert exported["window_height"] == 600
    assert "my_api_key" not in exported
    assert "db_password" not in exported


def test_export_includes_secrets_with_permissions(tmp_config_dir, tmp_path):
    """export_config(include_secrets=True) includes secrets and chmod 0o600."""
    from bento_app.config import BentoConfig

    cfg = BentoConfig()
    cfg.load()
    cfg.set("window_height", 600)
    cfg.set("my_api_key", "super-secret")

    out = tmp_path / "export_secret.json"
    cfg.export_config(out, include_secrets=True)

    exported = json.loads(out.read_text())
    assert "window_height" in exported
    assert exported["my_api_key"] == "super-secret"

    mode = stat.S_IMODE(os.stat(out).st_mode)
    assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"


def test_import_skips_sensitive_keys(tmp_config_dir, tmp_path):
    """import_config silently skips sensitive keys."""
    from bento_app.config import BentoConfig

    payload = {"window_height": 999, "my_api_key": "leaked", "auth_token": "tok"}
    import_file = tmp_path / "import.json"
    import_file.write_text(json.dumps(payload))

    cfg = BentoConfig()
    cfg.load()
    cfg.import_config(import_file)

    assert cfg.get("my_api_key") is None or cfg.get("my_api_key") != "leaked"
    assert cfg.get("auth_token") is None or cfg.get("auth_token") != "tok"


def test_import_applies_non_sensitive_keys(tmp_config_dir, tmp_path):
    """import_config correctly imports non-sensitive keys and persists them."""
    import bento_app.config as cfg_mod
    from bento_app.config import BentoConfig

    payload = {"window_height": 777, "animation_style": "fade"}
    import_file = tmp_path / "import.json"
    import_file.write_text(json.dumps(payload))

    cfg = BentoConfig()
    cfg.load()
    cfg.import_config(import_file)

    assert cfg.get("window_height") == 777
    assert cfg.get("animation_style") == "fade"

    # Verify persistence: reset singleton and reload
    cfg_mod.BentoConfig._instance = None
    cfg2 = cfg_mod.BentoConfig()
    cfg2.load()
    assert cfg2.get("window_height") == 777


def test_corrupted_config_backup(tmp_config_dir):
    """Corrupted config.json creates a .bak and falls back to defaults."""
    import bento_app.config as cfg_mod
    from bento_app.config import BentoConfig, _DEFAULTS

    config_file = tmp_config_dir / "config.json"
    config_file.write_text("{invalid json!!! ~~~")

    cfg_mod.BentoConfig._instance = None
    cfg = BentoConfig()
    cfg.load()

    bak = tmp_config_dir / "config.json.bak"
    assert bak.exists(), "Backup file was not created"
    assert bak.read_text() == "{invalid json!!! ~~~"

    for key, value in _DEFAULTS.items():
        assert cfg.get(key) == value, f"Expected default for '{key}'"
