# MIT License — Copyright (c) 2026 HabiRabbu — see LICENSE
"""CLI tools for Bento block management."""

from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path

from bento_app.config import BentoConfig

_MANIFEST_TEMPLATE = """\
{{
  "id": "{block_id}",
  "name": "{name}",
  "description": "",
  "version": "0.1.0",
  "author": "",
  "order": 1000,
  "requires_config": []
}}
"""

_BLOCK_PY_TEMPLATE = textwrap.dedent("""\
    \"\"\"Bento block: {name}.\"\"\"

    from __future__ import annotations

    from PyQt6.QtWidgets import QLabel, QVBoxLayout

    from bento_app.blocks.base_block import BaseBlock, load_manifest


    class {class_name}(BaseBlock):
        \"\"\"Main widget for the {name} block.\"\"\"

        def __init__(self, parent=None):
            super().__init__(parent)
            layout = QVBoxLayout(self)
            layout.addWidget(QLabel("{name} block"))

        @staticmethod
        def get_manifest():
            return load_manifest(__file__)

        def on_focus(self):
            pass

        def on_hide(self):
            pass
""")

_ICON_SVG_TEMPLATE = textwrap.dedent("""\
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
      <rect width="48" height="48" rx="8" fill="#555"/>
      <text x="24" y="32" text-anchor="middle" fill="#fff"
            font-size="20" font-family="sans-serif">{letter}</text>
    </svg>
""")


def _blocks_dir() -> Path:
    return BentoConfig.config_dir() / "blocks"


_VALID_BLOCK_NAME = re.compile(r"^[a-z0-9]([a-z0-9_-]*[a-z0-9])?$")


def _to_class_name(name: str) -> str:
    """Convert a block name like 'my-block' to 'MyBlockBlock'."""
    parts = name.replace("-", "_").split("_")
    return "".join(p.capitalize() for p in parts) + "Block"


def create_block(name: str) -> None:
    """Scaffold a new block directory in ~/.config/bento/blocks/<name>/."""
    if not _VALID_BLOCK_NAME.match(name):
        print(
            f"Error: invalid block name '{name}'. "
            "Use lowercase letters, digits, hyphens, and underscores only."
        )
        return

    block_dir = _blocks_dir() / name
    if block_dir.exists():
        print(f"Error: block directory already exists: {block_dir}")
        return

    block_dir.mkdir(parents=True, exist_ok=True)

    display_name = name.replace("-", " ").replace("_", " ").title()
    class_name = _to_class_name(name)

    (block_dir / "manifest.json").write_text(
        _MANIFEST_TEMPLATE.format(block_id=name, name=display_name),
        encoding="utf-8",
    )
    (block_dir / "block.py").write_text(
        _BLOCK_PY_TEMPLATE.format(name=display_name, class_name=class_name),
        encoding="utf-8",
    )
    (block_dir / "icon.svg").write_text(
        _ICON_SVG_TEMPLATE.format(letter=name[0].upper() if name else "?"),
        encoding="utf-8",
    )

    print(f"Created block scaffold: {block_dir}")
    print(f"  manifest.json")
    print(f"  block.py ({class_name})")
    print(f"  icon.svg")


def list_blocks() -> None:
    """List all discovered blocks (built-in and user)."""
    pkg_dir = Path(__file__).resolve().parent
    builtin_dir = pkg_dir / "builtin_blocks"
    user_dir = _blocks_dir()
    found: list[tuple[str, str, str]] = []


    for source_label, directory in [("built-in", builtin_dir), ("user", user_dir)]:
        if not directory.is_dir():
            continue
        for entry in sorted(directory.iterdir()):
            manifest_path = entry / "manifest.json"
            if not manifest_path.exists():
                continue
            try:
                with manifest_path.open("r", encoding="utf-8") as fh:
                    manifest = json.load(fh)
                found.append((manifest.get("id", "?"), manifest.get("name", "?"), source_label))
            except (json.JSONDecodeError, OSError):
                found.append((entry.name, "(invalid manifest)", source_label))

    disabled = BentoConfig().get_list("disabled_blocks", [])

    if not found:
        print("No blocks found.")
        return

    print(f"{'ID':<20} {'Name':<25} {'Source':<10} {'Status'}")
    print("-" * 65)
    for block_id, name, source in found:
        status = "disabled" if block_id in disabled else "enabled"
        print(f"{block_id:<20} {name:<25} {source:<10} {status}")


def enable_block(block_id: str) -> None:
    """Enable a disabled block."""
    config = BentoConfig()
    config.load()
    disabled = config.get_list("disabled_blocks", [])
    if block_id not in disabled:
        print(f"Block '{block_id}' is already enabled.")
        return
    disabled.remove(block_id)
    config.set("disabled_blocks", disabled)
    config.save()
    print(f"Enabled block '{block_id}'.")


def disable_block(block_id: str) -> None:
    """Disable a block."""
    config = BentoConfig()
    config.load()
    disabled = config.get_list("disabled_blocks", [])
    if block_id in disabled:
        print(f"Block '{block_id}' is already disabled.")
        return
    disabled.append(block_id)
    config.set("disabled_blocks", disabled)
    config.save()
    print(f"Disabled block '{block_id}'.")
