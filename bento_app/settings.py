# MIT License — Copyright (c) 2026 HabiRabbu — see LICENSE
"""Settings dialog for Bento.

Sections: General, LM Studio, and dynamically generated per-block settings
for any block that declares ``requires_config`` in its manifest.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from bento_app import __version__
from bento_app.blocks.base_block import ManifestDict, SettingField
from bento_app.config import BentoConfig
from bento_app.notify import notify_error, notify_info

logger = logging.getLogger(__name__)

_DESKTOP_ENTRY_TEMPLATE = """\
[Desktop Entry]
Type=Application
Name=Bento
Comment=Popup control centre for KDE Plasma
Exec={exec_line}
Icon={icon_path}
Terminal=false
Categories=Utility;
StartupNotify=false
"""


class SettingsDialog(QDialog):
    """Bento settings dialog."""

    def __init__(
        self,
        blocks: list[tuple[ManifestDict, type]],
        repo_root: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Bento Settings")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self._config = BentoConfig()
        self._blocks = blocks
        self._repo_root = repo_root
        self._field_map: dict[str, QLineEdit | QCheckBox | QSpinBox | QComboBox] = {}

        layout = QVBoxLayout(self)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        container = QWidget()
        self._form = QVBoxLayout(container)

        self._build_general_section()
        self._build_lm_studio_section()
        self._build_block_sections()

        self._form.addStretch()

        version_label = QLabel(f"Bento v{__version__}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("font-size: 11px; color: palette(mid);")
        self._form.addWidget(version_label)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        ie_row = QHBoxLayout()
        export_btn = QPushButton("Export Settings…")
        export_btn.setAccessibleName("Export settings to file")
        export_btn.clicked.connect(self._export_settings)
        import_btn = QPushButton("Import Settings…")
        import_btn.setAccessibleName("Import settings from file")
        import_btn.clicked.connect(self._import_settings)
        ie_row.addWidget(export_btn)
        ie_row.addWidget(import_btn)
        ie_row.addStretch()
        layout.addLayout(ie_row)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._save)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)


    def _build_general_section(self) -> None:
        group = QGroupBox("General")
        form = QFormLayout(group)

        hotkey_row = QHBoxLayout()
        hotkey_label = QLabel(str(self._config.get("hotkey", "Meta+Shift+Space")))
        hotkey_label.setAccessibleName("Current hotkey")
        hotkey_btn = QPushButton("Change in KDE Settings…")
        hotkey_btn.setAccessibleName("Open KDE shortcut settings")
        hotkey_btn.clicked.connect(self._open_kde_shortcuts)
        hotkey_row.addWidget(hotkey_label)
        hotkey_row.addWidget(hotkey_btn)
        form.addRow("Hotkey:", hotkey_row)

        height_row = QHBoxLayout()
        height_slider = QSlider(Qt.Orientation.Horizontal)
        height_slider.setRange(200, 800)
        height_slider.setAccessibleName("Window height slider")
        height_spin = QSpinBox()
        height_spin.setRange(200, 800)
        height_spin.setSuffix(" px")
        height_spin.setAccessibleName("Window height value")
        current_h = int(self._config.get("window_height", 420))
        height_slider.setValue(current_h)
        height_spin.setValue(current_h)
        height_slider.valueChanged.connect(height_spin.setValue)
        height_spin.valueChanged.connect(height_slider.setValue)
        height_row.addWidget(height_slider)
        height_row.addWidget(height_spin)
        form.addRow("Window height:", height_row)
        self._field_map["window_height"] = height_spin

        width_row = QHBoxLayout()
        width_slider = QSlider(Qt.Orientation.Horizontal)
        width_slider.setRange(20, 100)
        width_slider.setAccessibleName("Window width percentage slider")
        width_spin = QSpinBox()
        width_spin.setRange(20, 100)
        width_spin.setSuffix(" %")
        width_spin.setAccessibleName("Window width percentage value")
        current_w = int(self._config.get("window_width_percent", 70))
        width_slider.setValue(current_w)
        width_spin.setValue(current_w)
        width_slider.valueChanged.connect(width_spin.setValue)
        width_spin.valueChanged.connect(width_slider.setValue)
        width_row.addWidget(width_slider)
        width_row.addWidget(width_spin)
        form.addRow("Window width:", width_row)
        self._field_map["window_width_percent"] = width_spin

        screen_combo = QComboBox()
        screen_combo.setAccessibleName("Open on screen selector")
        _screen_options = [
            ("Follow mouse cursor", "follow_mouse"),
            ("Follow focused window", "follow_focus"),
            ("Primary screen only", "primary"),
        ]
        for label, value in _screen_options:
            screen_combo.addItem(label, value)
        current_mode = self._config.get("screen_mode", "follow_mouse")
        for i, (_, value) in enumerate(_screen_options):
            if value == current_mode:
                screen_combo.setCurrentIndex(i)
                break
        form.addRow("Open on screen:", screen_combo)
        self._field_map["screen_mode"] = screen_combo

        pos_combo = QComboBox()
        pos_combo.setAccessibleName("Window position selector")
        _pos_options = [
            ("Top", "top"),
            ("Bottom", "bottom"),
        ]
        for label, value in _pos_options:
            pos_combo.addItem(label, value)
        current_pos = self._config.get("window_position", "top")
        for i, (_, value) in enumerate(_pos_options):
            if value == current_pos:
                pos_combo.setCurrentIndex(i)
                break
        form.addRow("Window position (restart required):", pos_combo)
        self._field_map["window_position"] = pos_combo

        autostart = QCheckBox("Start Bento on login")
        autostart.setAccessibleName("Enable autostart on login")
        autostart.setChecked(bool(self._config.get("autostart", False)))
        form.addRow(autostart)
        self._field_map["autostart"] = autostart

        anim_combo = QComboBox()
        anim_combo.setAccessibleName("Animation style selector")
        _anim_options = [
            ("Slide", "slide"),
            ("Fade", "fade"),
            ("None", "none"),
        ]
        for label, value in _anim_options:
            anim_combo.addItem(label, value)
        current_anim = self._config.get("animation_style", "slide")
        for i, (_, value) in enumerate(_anim_options):
            if value == current_anim:
                anim_combo.setCurrentIndex(i)
                break
        form.addRow("Animation style (restart required):", anim_combo)
        self._field_map["animation_style"] = anim_combo

        anim_duration = QSpinBox()
        anim_duration.setAccessibleName("Animation duration in milliseconds")
        anim_duration.setRange(50, 500)
        anim_duration.setSingleStep(10)
        anim_duration.setSuffix(" ms")
        anim_duration.setValue(int(self._config.get("animation_duration", 200)))
        form.addRow("Animation duration:", anim_duration)
        self._field_map["animation_duration"] = anim_duration

        self._form.addWidget(group)

    def _build_lm_studio_section(self) -> None:
        group = QGroupBox("LM Studio")
        form = QFormLayout(group)

        url_input = QLineEdit(
            str(self._config.get("lm_studio_base_url", "http://localhost:1234/v1"))
        )
        url_input.setAccessibleName("LM Studio base URL")
        form.addRow("Base URL:", url_input)
        self._field_map["lm_studio_base_url"] = url_input

        model_input = QLineEdit(str(self._config.get("lm_studio_model", "")))
        model_input.setPlaceholderText("e.g. llama-3.1-8b-instruct")
        model_input.setAccessibleName("LM Studio model name")
        form.addRow("Model:", model_input)
        self._field_map["lm_studio_model"] = model_input

        self._form.addWidget(group)

    def _build_block_sections(self) -> None:
        disabled = self._config.get_list("disabled_blocks", [])
        self._block_enabled_checks: dict[str, QCheckBox] = {}

        for manifest, _block_cls in self._blocks:
            block_id = manifest["id"]
            group = QGroupBox(manifest.get("name", block_id))
            form = QFormLayout(group)

            enabled_cb = QCheckBox("Enabled")
            enabled_cb.setAccessibleName(f"Enable {block_id} block")
            enabled_cb.setChecked(block_id not in disabled)
            form.addRow(enabled_cb)
            self._block_enabled_checks[block_id] = enabled_cb

            settings: list[SettingField] | None = manifest.get("settings")  # type: ignore[assignment]
            if settings:
                for field in settings:
                    key = field.get("key", "")
                    if not key:
                        continue
                    label = field.get("label", key)
                    field_type = field.get("type", "string")
                    default = field.get("default")
                    current = self._config.get(key, default)

                    widget: QLineEdit | QCheckBox | QSpinBox | QComboBox

                    if field_type == "bool":
                        widget = QCheckBox()
                        widget.setChecked(bool(current))
                        widget.setAccessibleName(f"{label} setting")
                    elif field_type == "int":
                        widget = QSpinBox()
                        if "min" in field:
                            widget.setMinimum(field["min"])
                        if "max" in field:
                            widget.setMaximum(field["max"])
                        widget.setValue(int(current) if current is not None else 0)
                        widget.setAccessibleName(f"{label} setting")
                    elif field_type == "choice":
                        widget = QComboBox()
                        choices = field.get("choices", [])
                        for choice in choices:
                            widget.addItem(choice, choice)
                        if current is not None:
                            idx = widget.findData(current)
                            if idx >= 0:
                                widget.setCurrentIndex(idx)
                        widget.setAccessibleName(f"{label} setting")
                    elif field_type == "password":
                        widget = QLineEdit(str(current) if current is not None else "")
                        widget.setEchoMode(QLineEdit.EchoMode.Password)
                        widget.setAccessibleName(f"{label} setting")
                    else:
                        widget = QLineEdit(str(current) if current is not None else "")
                        widget.setAccessibleName(f"{label} setting")

                    form.addRow(f"{label}:", widget)
                    self._field_map[key] = widget
            else:
                required: list[str] = manifest.get("requires_config", [])
                for key in required:
                    line = QLineEdit(str(self._config.get(key, "")))
                    if BentoConfig.is_sensitive(key):
                        line.setEchoMode(QLineEdit.EchoMode.Password)
                    line.setAccessibleName(f"{key} configuration field")
                    form.addRow(f"{key}:", line)
                    self._field_map[key] = line

            self._form.addWidget(group)


    def _save(self) -> None:
        _RESTART_KEYS = {
            "disabled_blocks", "animation_style",
            "window_position", "window_width_percent",
        }
        old_values = {k: self._config.get(k) for k in _RESTART_KEYS}

        for key, widget in self._field_map.items():
            if isinstance(widget, QCheckBox):
                self._config.set(key, widget.isChecked())
            elif isinstance(widget, QSpinBox):
                self._config.set(key, widget.value())
            elif isinstance(widget, QComboBox):
                self._config.set(key, widget.currentData())
            elif isinstance(widget, QLineEdit):
                self._config.set(key, widget.text())

        disabled_blocks = [
            bid for bid, cb in self._block_enabled_checks.items()
            if not cb.isChecked()
        ]
        self._config.set("disabled_blocks", disabled_blocks)

        try:
            self._config.save()
        except Exception:
            logger.error("Failed to save settings", exc_info=True)
            notify_error("Settings", "Failed to save settings")
            return

        try:
            if self._config.get("autostart", False):
                self._enable_autostart()
            else:
                self._disable_autostart()
        except Exception:
            logger.error("Failed to update autostart", exc_info=True)
            notify_error("Settings", "Failed to save settings")
            return

        new_values = {k: self._config.get(k) for k in _RESTART_KEYS}
        needs_restart = any(old_values[k] != new_values[k] for k in _RESTART_KEYS)

        msg = "Settings saved"
        if needs_restart:
            msg += ". Some changes will take effect after restart."

        logger.info("Settings saved")
        notify_info("Settings", msg)
        self.accept()

    def _enable_autostart(self) -> None:
        xdg_config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        autostart_dir = xdg_config / "autostart"
        autostart_dir.mkdir(parents=True, exist_ok=True)
        desktop_file = autostart_dir / "bento.desktop"

        bento_bin = shutil.which("bento")
        if bento_bin:
            exec_line = bento_bin
        else:
            exec_line = f"{sys.executable} -m bento_app"

        icon_svg = Path(__file__).resolve().parent / "assets" / "icon.svg"

        desktop_file.write_text(
            _DESKTOP_ENTRY_TEMPLATE.format(
                exec_line=exec_line,
                icon_path=str(icon_svg),
            ),
            encoding="utf-8",
        )
        logger.info("Autostart enabled: %s", desktop_file)

    @staticmethod
    def _disable_autostart() -> None:
        xdg_config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        desktop_file = xdg_config / "autostart" / "bento.desktop"
        if desktop_file.exists():
            desktop_file.unlink()
            logger.info("Autostart disabled")

    @staticmethod
    def _open_kde_shortcuts() -> None:
        try:
            subprocess.Popen(
                ["systemsettings", "kcm_keys"],
                start_new_session=True,
            )
        except FileNotFoundError:
            logger.warning("systemsettings not found — cannot open KDE Shortcuts")

    def _export_settings(self) -> None:
        include_secrets = False
        reply = QMessageBox.question(
            self,
            "Include secrets?",
            "Include API keys and other sensitive values in the export?\n\n"
            "If yes, the file will be restricted to owner-only access (chmod 600).",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        include_secrets = reply == QMessageBox.StandardButton.Yes

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Settings", "bento-settings.json", "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            self._config.export_config(Path(path), include_secrets=include_secrets)
            notify_info("Settings", f"Settings exported to {path}")
        except Exception:
            logger.error("Failed to export settings", exc_info=True)
            notify_error("Settings", "Failed to export settings")

    def _import_settings(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Settings", "", "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            self._config.import_config(Path(path))
            notify_info("Settings", "Settings imported — restart Bento to apply all changes")
        except Exception:
            logger.error("Failed to import settings", exc_info=True)
            notify_error("Settings", "Failed to import settings")

