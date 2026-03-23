"""Tests for bento_app.testing — block developer test utilities."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from bento_app.testing import FakeConfig, MockNotifier, create_test_block



class TestFakeConfig:
    def test_get_set(self):
        cfg = FakeConfig({"key": "value"})
        assert cfg.get("key") == "value"
        assert cfg.get("missing") is None
        assert cfg.get("missing", "default") == "default"

    def test_set_and_retrieve(self):
        cfg = FakeConfig()
        cfg.set("foo", 42)
        assert cfg.get("foo") == 42

    def test_save_records_snapshot(self):
        cfg = FakeConfig({"a": 1})
        cfg.save()
        cfg.set("a", 2)
        cfg.save()
        assert len(cfg._saved) == 2
        assert cfg._saved[0] == {"a": 1}
        assert cfg._saved[1] == {"a": 2}

    def test_load_is_noop(self):
        cfg = FakeConfig({"x": 1})
        cfg.load()
        assert cfg.get("x") == 1

    def test_typed_accessors(self):
        cfg = FakeConfig({
            "count": "10",
            "enabled": "true",
            "name": "bento",
            "tags": ["a", "b"],
        })
        assert cfg.get_int("count") == 10
        assert cfg.get_int("missing", 5) == 5
        assert cfg.get_bool("enabled") is True
        assert cfg.get_str("name") == "bento"
        assert cfg.get_list("tags") == ["a", "b"]
        assert cfg.get_list("missing") == []

    def test_is_sensitive(self):
        assert FakeConfig.is_sensitive("API_KEY") is True
        assert FakeConfig.is_sensitive("db_password") is True
        assert FakeConfig.is_sensitive("username") is False

    def test_config_dir_and_env_file(self):
        assert FakeConfig.config_dir().name == "bento-test-config"
        assert FakeConfig.env_file().name == ".env"



class TestMockNotifier:
    def test_captures_info(self):
        n = MockNotifier()
        n.notify_info("Title", "Message")
        assert n.calls == [("info", "Title", "Message")]

    def test_captures_warning(self):
        n = MockNotifier()
        n.notify_warning("Warn", "Oops")
        assert n.calls == [("warning", "Warn", "Oops")]

    def test_captures_error(self):
        n = MockNotifier()
        n.notify_error("Err", "Boom")
        assert n.calls == [("error", "Err", "Boom")]

    def test_clear(self):
        n = MockNotifier()
        n.notify_info("A", "B")
        n.notify_warning("C", "D")
        assert len(n.calls) == 2
        n.clear()
        assert len(n.calls) == 0

    def test_multiple_calls(self):
        n = MockNotifier()
        n.notify_info("1", "a")
        n.notify_warning("2", "b")
        n.notify_error("3", "c")
        assert len(n.calls) == 3
        assert n.calls[0][0] == "info"
        assert n.calls[1][0] == "warning"
        assert n.calls[2][0] == "error"



class TestCreateTestBlock:
    def test_instantiates_demo_block(self, qapp, tmp_path, monkeypatch):
        """The demo block can be instantiated via create_test_block."""
        import bento_app.config as cfg_mod

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}")
        (config_dir / ".env").write_text("")
        monkeypatch.setattr(cfg_mod, "_CONFIG_DIR", config_dir)
        monkeypatch.setattr(cfg_mod, "_CONFIG_FILE", config_dir / "config.json")
        monkeypatch.setattr(cfg_mod, "_ENV_FILE", config_dir / ".env")
        cfg_mod.BentoConfig._instance = None

        from bento_app.builtin_blocks.demo.block import DemoBlock

        block = create_test_block(DemoBlock)
        assert block is not None
        manifest = block.get_manifest()
        assert manifest["id"] == "demo"
        assert manifest["name"] == "Demo"

        cfg_mod.BentoConfig._instance = None

    def test_with_fake_config(self, qapp, tmp_path, monkeypatch):
        """create_test_block patches config when FakeConfig is provided."""
        import bento_app.config as cfg_mod

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}")
        (config_dir / ".env").write_text("")
        monkeypatch.setattr(cfg_mod, "_CONFIG_DIR", config_dir)
        monkeypatch.setattr(cfg_mod, "_CONFIG_FILE", config_dir / "config.json")
        monkeypatch.setattr(cfg_mod, "_ENV_FILE", config_dir / ".env")
        cfg_mod.BentoConfig._instance = None

        from bento_app.builtin_blocks.demo.block import DemoBlock

        fake = FakeConfig({"custom_setting": "test_value"})
        block = create_test_block(DemoBlock, config=fake)
        assert block is not None
        # The demo block has no requires_config so validate_config returns []
        assert block.validate_config() == []

        cfg_mod.BentoConfig._instance = None

    def test_manifest_attachment(self, qapp, tmp_path, monkeypatch):
        """A custom manifest dict is attached as _test_manifest."""
        import bento_app.config as cfg_mod

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}")
        (config_dir / ".env").write_text("")
        monkeypatch.setattr(cfg_mod, "_CONFIG_DIR", config_dir)
        monkeypatch.setattr(cfg_mod, "_CONFIG_FILE", config_dir / "config.json")
        monkeypatch.setattr(cfg_mod, "_ENV_FILE", config_dir / ".env")
        cfg_mod.BentoConfig._instance = None

        from bento_app.builtin_blocks.demo.block import DemoBlock

        custom_manifest = {
            "id": "custom",
            "name": "Custom",
            "description": "test",
            "version": "2.0.0",
            "author": "tester",
        }
        block = create_test_block(DemoBlock, manifest=custom_manifest)
        assert block._test_manifest["id"] == "custom"
        assert block._test_manifest["version"] == "2.0.0"

        cfg_mod.BentoConfig._instance = None

    def test_lifecycle_hooks(self, qapp, tmp_path, monkeypatch):
        """Lifecycle hooks can be called on a test block."""
        import bento_app.config as cfg_mod

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / "config.json").write_text("{}")
        (config_dir / ".env").write_text("")
        monkeypatch.setattr(cfg_mod, "_CONFIG_DIR", config_dir)
        monkeypatch.setattr(cfg_mod, "_CONFIG_FILE", config_dir / "config.json")
        monkeypatch.setattr(cfg_mod, "_ENV_FILE", config_dir / ".env")
        cfg_mod.BentoConfig._instance = None

        from bento_app.builtin_blocks.demo.block import DemoBlock

        block = create_test_block(DemoBlock)
        block.on_focus()
        block.on_hide()
        block.on_save_state()
        block.on_restore_state()
        block.on_shutdown()

        cfg_mod.BentoConfig._instance = None
