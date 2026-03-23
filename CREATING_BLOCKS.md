# Creating Bento Blocks

Plugin development guide for [Bento](https://github.com/HabiRabbu/bento), the popup control centre for KDE Plasma.

---

## Table of contents

- [Quick start](#quick-start)
- [Folder structure](#folder-structure)
- [manifest.json reference](#manifestjson-reference)
- [BaseBlock API reference](#baseblock-api-reference)
- [Reading config values](#reading-config-values)
- [Rich settings](#rich-settings)
- [KDE notifications via DBus](#kde-notifications-via-dbus)
- [Async work with QThread](#async-work-with-qthread)
- [State persistence](#state-persistence)
- [Command palette integration](#command-palette-integration)
- [Testing blocks](#testing-blocks)
- [Installation](#installation)
- [Scaffolding with the CLI](#scaffolding-with-the-cli)
- [Debugging](#debugging)
- [Common gotchas](#common-gotchas)
- [Complete example: note-taking block](#complete-example-note-taking-block)

---

## Quick start

### 1. Create the folder

```bash
mkdir -p ~/.config/bento/blocks/hello_world
```

### 2. Write `manifest.json`

```json
{
  "id": "hello_world",
  "name": "Hello World",
  "description": "My first block",
  "version": "0.1.0",
  "author": "Your Name",
  "order": 50,
  "api_version": 1,
  "requires_config": []
}
```

### 3. Write `block.py`

```python
from bento_app.blocks.base_block import BaseBlock, load_manifest
from PyQt6.QtWidgets import QLabel, QVBoxLayout
from PyQt6.QtCore import Qt


class HelloWorldBlock(BaseBlock):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(QLabel("Hello from my first block!"))

    @staticmethod
    def get_manifest():
        return load_manifest(__file__)
```

### 4. Add an icon

Drop an `icon.svg` into the folder. A 48×48 viewBox SVG works best. Here is a minimal placeholder:

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <rect width="48" height="48" rx="8" fill="#555"/>
  <text x="24" y="32" text-anchor="middle" fill="#fff"
        font-size="20" font-family="sans-serif">H</text>
</svg>
```

### 5. Launch Bento

Bento watches `~/.config/bento/blocks/` and live-reloads new or changed blocks — no restart needed.

---

## Folder structure

Every block is a self-contained directory with exactly three files:

```
my_block/
├── manifest.json   # Required — block metadata
├── block.py        # Required — contains your BaseBlock subclass
└── icon.svg        # Required — sidebar icon (48×48 recommended)
```

The directory name is not significant — the loader reads the `id` field from `manifest.json`. However, keeping the directory name and ID in sync avoids confusion.

---

## manifest.json reference

A complete manifest with every supported field:

```json
{
  "id": "my_block",
  "name": "My Block",
  "description": "What the block does",
  "version": "1.0.0",
  "author": "Your Name",
  "order": 10,
  "api_version": 1,
  "requires_config": ["MY_API_KEY"],
  "settings": [
    {
      "key": "my_api_key",
      "label": "API Key",
      "type": "password",
      "default": ""
    },
    {
      "key": "refresh_interval",
      "label": "Refresh interval (sec)",
      "type": "int",
      "default": 30,
      "min": 5,
      "max": 300
    }
  ]
}
```

### Field reference

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | `string` | **yes** | — | Unique identifier. Must match `^[a-zA-Z0-9_-]+$`. |
| `name` | `string` | **yes** | — | Display name shown in the sidebar and settings. |
| `version` | `string` | **yes** | — | Semver string (e.g. `"1.0.0"`). |
| `description` | `string` | no | `""` | Short description for settings and the command palette. |
| `author` | `string` | no | `""` | Author name. |
| `order` | `int` | no | `1000` | Sidebar position. Lower numbers appear first. Accepts string values that can be coerced to int. |
| `api_version` | `int` | no | `1` | Block API version. Must be ≤ the running Bento's `BENTO_API_VERSION` (currently `1`). Blocks requesting a higher version are skipped with a warning. |
| `requires_config` | `list[str]` | no | `[]` | Config keys the block needs to function (e.g. `["LINEAR_API_KEY"]`). Bento shows a red warning badge on the sidebar icon until every listed key has a value, and auto-generates input fields in Settings. |
| `settings` | `list[SettingField]` | no | `[]` | Rich typed settings. See [Rich settings](#rich-settings) below. |

### Validation rules

The block loader enforces these rules. Blocks that fail validation are skipped (they never crash Bento):

- `id`, `name`, and `version` must be present and non-empty strings.
- `id` must match `^[a-zA-Z0-9_-]+$`.
- `requires_config`, if present, must be a list of strings.
- `api_version`, if present, must be an integer ≤ `BENTO_API_VERSION`.
- `order` is coerced to `int`. Unparseable values default to `1000`.
- The manifest file itself must be valid JSON.

---

## BaseBlock API reference

Your block subclasses `BaseBlock`, which inherits from `QWidget`. Build any PyQt6 UI you want inside it.

```python
from bento_app.blocks.base_block import BaseBlock, load_manifest
```

### Required methods

#### `get_manifest() -> ManifestDict` (static, abstract)

Return the parsed `manifest.json` for this block. Use the `load_manifest` helper:

```python
@staticmethod
def get_manifest():
    return load_manifest(__file__)
```

`load_manifest(__file__)` reads `manifest.json` from the same directory as the calling `block.py`. You never need to hard-code a path.

### Lifecycle methods (all optional)

#### `on_focus() -> None`

Called every time this block becomes the active tab. Use it to focus your primary input widget (a search field, a text editor, etc.).

```python
def on_focus(self):
    self._search_input.setFocus()
```

#### `on_hide() -> None`

Called when the Bento popup is hidden. Use it to pause timers, cancel network requests, or stop background work.

```python
def on_hide(self):
    self._poll_timer.stop()
```

#### `on_shutdown() -> None`

Called when the application is quitting. Clean up resources — close connections, flush caches, stop threads.

```python
def on_shutdown(self):
    self._worker.quit()
    self._worker.wait()
```

#### `on_save_state() -> None`

Called before the app quits, right before `on_shutdown()`. Persist any block state you want to survive a restart.

```python
def on_save_state(self):
    state_file = self.get_state_dir() / "notes.json"
    state_file.write_text(json.dumps(self._notes), encoding="utf-8")
```

#### `on_restore_state() -> None`

Called after block instantiation during startup. Restore the state you saved in `on_save_state()`.

```python
def on_restore_state(self):
    state_file = self.get_state_dir() / "notes.json"
    if state_file.exists():
        self._notes = json.loads(state_file.read_text(encoding="utf-8"))
```

### Utility methods

#### `get_state_dir() -> Path`

Returns a persistent directory at `~/.config/bento/state/<block_id>/`, creating it if it does not exist. Use this for any files your block needs to persist across restarts.

```python
cache_dir = self.get_state_dir()
(cache_dir / "cache.json").write_text("{}")
```

#### `get_actions() -> list[dict[str, str]]`

Return a list of actions that appear in the command palette (`Ctrl+K`). Each action is a dict with `id`, `title`, and `description`:

```python
def get_actions(self):
    return [
        {"id": "new_note", "title": "New Note", "description": "Create a blank note"},
        {"id": "clear_all", "title": "Clear All", "description": "Delete all notes"},
    ]
```

See [Command palette integration](#command-palette-integration) for details.

#### `validate_config() -> list[str]`

Returns a list of missing config keys from `requires_config`. An empty list means the block's configuration is valid. Bento calls this internally to decide whether to show a warning badge.

```python
missing = self.validate_config()
if missing:
    self._show_setup_prompt(missing)
```

---

## Reading config values

Use the `BentoConfig` singleton to read settings and API keys:

```python
from bento_app.config import BentoConfig

config = BentoConfig()

# Generic getter
value = config.get("some_key", "default_value")

# Typed getters with coercion
api_key  = config.get_str("MY_API_KEY", "")
timeout  = config.get_int("timeout_seconds", 30)
enabled  = config.get_bool("feature_enabled", False)
items    = config.get_list("disabled_blocks", [])
```

### Typed accessor reference

| Method | Return type | Coercion |
|--------|------------|----------|
| `get(key, default=None)` | `Any` | None |
| `get_str(key, default="")` | `str` | `str(val)` |
| `get_int(key, default=0)` | `int` | `int(val)`, returns default on failure |
| `get_bool(key, default=False)` | `bool` | Accepts `True`/`False`, `"true"`/`"false"`, `"1"`/`"0"`, `"yes"`/`"no"` |
| `get_list(key, default=[])` | `list` | Returns default if the value is not already a list |

### Writing config values

```python
config.set("my_key", "my_value")
config.save()  # persist to disk
```

### Storage locations

- **Non-sensitive** settings → `~/.config/bento/config.json`
- **Sensitive** settings → `~/.config/bento/.env` (chmod 600)

A key is considered sensitive if its uppercase form ends with `_KEY`, `_SECRET`, `_TOKEN`, or `_PASSWORD`. Both are read transparently through the same `config.get()` call.

---

## Rich settings

The `settings` array in your manifest lets you declare typed, validated configuration fields. Bento renders them in the Settings dialog automatically — you never need to build your own config UI.

### Setting field schema

```json
{
  "key": "refresh_interval",
  "label": "Refresh interval (sec)",
  "type": "int",
  "default": 30,
  "min": 5,
  "max": 300
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `key` | `string` | **yes** | Config key used with `BentoConfig.get()`. |
| `label` | `string` | no | Display label. Defaults to `key`. |
| `type` | `string` | no | One of `"string"`, `"int"`, `"bool"`, `"choice"`, `"password"`. Defaults to `"string"`. |
| `default` | `any` | no | Default value. |
| `choices` | `list[str]` | no | Options list. Only used when `type` is `"choice"`. |
| `min` | `int` | no | Minimum value. Only used when `type` is `"int"`. |
| `max` | `int` | no | Maximum value. Only used when `type` is `"int"`. |

### Type → widget mapping

| `type` | Widget | Notes |
|--------|--------|-------|
| `"string"` | `QLineEdit` | Plain text input. |
| `"int"` | `QSpinBox` | Respects `min` and `max`. |
| `"bool"` | `QCheckBox` | On/off toggle. |
| `"choice"` | `QComboBox` | Dropdown. Requires `choices` array. |
| `"password"` | `QLineEdit` (masked) | Key is auto-detected as sensitive if it ends with `_KEY`, `_SECRET`, `_TOKEN`, or `_PASSWORD`; otherwise it is stored in `config.json`. |

### Examples

```json
"settings": [
  {
    "key": "github_token",
    "label": "GitHub Token",
    "type": "password",
    "default": ""
  },
  {
    "key": "theme",
    "label": "Theme",
    "type": "choice",
    "choices": ["light", "dark", "system"],
    "default": "system"
  },
  {
    "key": "show_previews",
    "label": "Show Previews",
    "type": "bool",
    "default": true
  },
  {
    "key": "max_results",
    "label": "Max Results",
    "type": "int",
    "default": 25,
    "min": 1,
    "max": 100
  }
]
```

---

## KDE notifications via DBus

Bento provides tray notification helpers (`notify_info`, `notify_warning`, `notify_error`), but you can also send full KDE desktop notifications directly through DBus:

```python
import dbus

bus = dbus.SessionBus()
notifications = dbus.Interface(
    bus.get_object(
        "org.freedesktop.Notifications",
        "/org/freedesktop/Notifications",
    ),
    "org.freedesktop.Notifications",
)

notifications.Notify(
    "My Block",     # app_name
    0,              # replaces_id (0 = new notification)
    "",             # app_icon (empty = default)
    "Title",        # summary
    "Message body", # body
    [],             # actions
    {},             # hints
    5000,           # timeout in ms (-1 = server default)
)
```

### Using Bento's built-in helpers

For simple tray balloon notifications, use the built-in module:

```python
from bento_app.notify import notify_info, notify_warning, notify_error

notify_info("My Block", "Operation completed")
notify_warning("My Block", "Rate limit approaching")
notify_error("My Block", "Connection failed")
```

These respect the system Do Not Disturb setting and queue messages if the tray icon is not ready yet.

---

## Async work with QThread

**Never block the main thread.** Network calls, file I/O on large datasets, and computation must happen off the main thread. Use `QThread` with signals:

```python
from PyQt6.QtCore import QThread, pyqtSignal


class FetchWorker(QThread):
    """Runs a network request off the main thread."""

    finished = pyqtSignal(str)   # emits the response body
    error = pyqtSignal(str)      # emits the error message

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self._url = url

    def run(self):
        try:
            import requests
            resp = requests.get(self._url, timeout=10)
            resp.raise_for_status()
            self.finished.emit(resp.text)
        except Exception as exc:
            self.error.emit(str(exc))
```

Use it from your block:

```python
class MyBlock(BaseBlock):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker = None
        # ... build UI ...

    def _fetch_data(self):
        self._worker = FetchWorker("https://api.example.com/data", parent=self)
        self._worker.finished.connect(self._on_data)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_data(self, body: str):
        self._label.setText(body[:200])

    def _on_error(self, msg: str):
        self._label.setText(f"Error: {msg}")

    def on_hide(self):
        # Stop worker when the window hides
        if self._worker and self._worker.isRunning():
            self._worker.quit()
            self._worker.wait(2000)

    def on_shutdown(self):
        self.on_hide()
```

### Key rules

1. **Never update widgets from a worker thread.** Emit a signal and connect it to a slot on the main thread.
2. **Always clean up workers** in `on_hide()` and `on_shutdown()`.
3. **Store a reference** to the worker (e.g. `self._worker`). If the worker is garbage-collected while running, you will get a segfault.

---

## State persistence

Blocks can persist data across restarts using the save/restore lifecycle:

### The lifecycle

1. **Startup**: Bento instantiates your block (`__init__`), then calls `on_restore_state()`.
2. **Shutdown**: Bento calls `on_save_state()`, then `on_shutdown()`.

### Using `get_state_dir()`

`get_state_dir()` returns `~/.config/bento/state/<block_id>/`, creating the directory if needed. Store whatever files you want there.

```python
import json
from pathlib import Path


class MyBlock(BaseBlock):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = {}

    def on_save_state(self):
        state_file = self.get_state_dir() / "data.json"
        state_file.write_text(json.dumps(self._data), encoding="utf-8")

    def on_restore_state(self):
        state_file = self.get_state_dir() / "data.json"
        if state_file.exists():
            try:
                self._data = json.loads(state_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}
```

### Tips

- Always wrap `on_restore_state()` in `try/except`. A corrupted state file should not crash your block.
- Use `json` for simple data. For larger datasets consider `sqlite3`.
- The state directory is per-block and survives block updates (it's keyed by `id`, not by folder name).

---

## Command palette integration

The command palette (`Ctrl+K`) lets users search and jump to blocks. Blocks can also register custom actions.

### Returning actions

Override `get_actions()` to add entries to the palette:

```python
def get_actions(self):
    return [
        {
            "id": "new_note",
            "title": "New Note",
            "description": "Create a blank note",
        },
        {
            "id": "search_notes",
            "title": "Search Notes",
            "description": "Full-text search across all notes",
        },
    ]
```

Each action dict has three keys:

| Key | Type | Description |
|-----|------|-------------|
| `id` | `str` | Unique action identifier within this block. |
| `title` | `str` | Display text in the palette. |
| `description` | `str` | Secondary text shown below the title. |

When a user selects an action, the command palette emits `action_selected(block_id, action_id)`. Bento switches to your block and you can handle the action however you want (the mechanism is signal-based — check `CommandPalette.action_selected`).

---

## Testing blocks

Bento uses `pytest` and `pytest-qt`. The test suite lives in `tests/` and uses fixtures from `tests/conftest.py`.

### Running tests

```bash
cd bento
pip install -e '.[dev]'
pytest
```

### Useful fixtures

The test suite provides fixtures you can reuse:

```python
# conftest.py provides:

@pytest.fixture
def tmp_config_dir(tmp_path, monkeypatch):
    """Redirect BentoConfig to a temp directory."""

@pytest.fixture
def sample_manifest(tmp_path):
    """Create a valid block directory with manifest.json, block.py, icon.svg."""

@pytest.fixture
def make_block_dir():
    """Factory: create block directories with custom manifests."""

@pytest.fixture
def loader_env(tmp_path, monkeypatch, qapp):
    """Set up a BlockLoader with temp builtin and user directories."""
```

### Example test

```python
import json
import os
import textwrap

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_my_block_loads(loader_env):
    """Verify the block loads without errors."""
    loader, _, user_dir = loader_env

    block_dir = user_dir / "my_block"
    block_dir.mkdir()

    (block_dir / "manifest.json").write_text(json.dumps({
        "id": "my_block",
        "name": "My Block",
        "version": "1.0.0",
    }))
    (block_dir / "block.py").write_text(textwrap.dedent("""\
        from bento_app.blocks.base_block import BaseBlock, load_manifest
        from PyQt6.QtWidgets import QLabel, QVBoxLayout

        class MyBlock(BaseBlock):
            def __init__(self, parent=None):
                super().__init__(parent)
                layout = QVBoxLayout(self)
                layout.addWidget(QLabel("test"))

            @staticmethod
            def get_manifest():
                return load_manifest(__file__)
    """))
    (block_dir / "icon.svg").write_text("<svg></svg>")

    result = loader._load_block(block_dir)
    assert result is not None
    assert result[0]["id"] == "my_block"
```

### Tips

- Always set `QT_QPA_PLATFORM=offscreen` for headless testing.
- Use `monkeypatch` to redirect `BentoConfig` to a temp directory so tests never touch your real config.
- Use the `qapp` fixture from `pytest-qt` whenever you instantiate Qt widgets.

---

## Installation

### Manual install

Drop your block folder into:

```
~/.config/bento/blocks/
```

Bento watches this directory. New or changed blocks are live-reloaded automatically (teardown + reimport) — no restart needed.

### User blocks override built-ins

If your block uses the same `id` as a built-in block, yours takes priority. This lets you fork and customise built-in blocks.

### Block search paths

1. **Built-in**: `<bento_package>/builtin_blocks/` (ships with Bento)
2. **User**: `~/.config/bento/blocks/` (your blocks)

---

## Scaffolding with the CLI

Bento includes CLI commands for block management:

```bash
# Scaffold a new block with manifest.json, block.py, and icon.svg
bento create-block my-cool-block

# List all discovered blocks and their status
bento list-blocks

# Enable/disable blocks
bento enable my_block
bento disable my_block
```

`create-block` creates a ready-to-run skeleton in `~/.config/bento/blocks/<name>/`.

---

## Debugging

### Debug mode

Run Bento with `--debug` for verbose logging:

```bash
bento --debug
```

This enables `DEBUG`-level logging and writes to `~/.config/bento/bento.log` (rotating, 1 MB max, 3 backups).

### Log to a specific file

```bash
bento --log-file /tmp/bento-debug.log
```

### Environment variable

```bash
BENTO_LOG_LEVEL=DEBUG bento
```

Accepted levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`.

### What to look for

- **Block loading failures** are logged as warnings with the reason (missing manifest, invalid JSON, syntax errors, import errors, missing `BaseBlock` subclass).
- **Notification failures** are logged when DBus is unavailable.
- **Hotkey registration** logs whether KDE global hotkey was registered or fell back to tray-only mode.

### Checking block loading

```bash
bento list-blocks
```

This prints a table of all discovered blocks, their source (built-in or user), and their enabled/disabled status — without starting the GUI.

---

## Common gotchas

### Never block the main thread

Any blocking call (network request, `time.sleep`, heavy computation) will freeze the entire Bento UI. Always use `QThread` with signals. See [Async work with QThread](#async-work-with-qthread).

### Always try/except in lifecycle methods

If `on_focus()`, `on_hide()`, `on_save_state()`, `on_restore_state()`, or `on_shutdown()` raises an exception, Bento catches it and logs a warning — but your block may end up in a broken state. Wrap risky operations in `try/except`:

```python
def on_restore_state(self):
    try:
        data = json.loads(self.get_state_dir().joinpath("state.json").read_text())
        self._load_data(data)
    except Exception:
        logging.getLogger(__name__).warning("Failed to restore state", exc_info=True)
```

### Use pathlib, not string concatenation

```python
# Good
state_file = self.get_state_dir() / "cache.json"

# Bad
state_file = str(self.get_state_dir()) + "/cache.json"
```

### Store worker references

If a `QThread` worker is garbage-collected while running, Python will segfault. Always store a reference on `self`:

```python
# Good
self._worker = FetchWorker(url, parent=self)
self._worker.start()

# Bad — worker may be garbage-collected
worker = FetchWorker(url)
worker.start()
```

### Sensitive key naming

Keys ending with `_KEY`, `_SECRET`, `_TOKEN`, or `_PASSWORD` are automatically stored in `.env` instead of `config.json`. Name your keys accordingly:

```python
# Stored in .env (good for secrets)
config.get("GITHUB_API_TOKEN")
config.get("MY_SERVICE_PASSWORD")

# Stored in config.json (good for preferences)
config.get("refresh_interval")
config.get("theme")
```

### Block ID format

Block IDs must match `^[a-zA-Z0-9_-]+$`. No spaces, slashes, dots, or special characters. Keep them lowercase with hyphens or underscores for consistency.

### A broken block never crashes Bento

The block loader wraps every load attempt in `try/except`. If your block has a syntax error, import error, or missing manifest field, it is skipped with a warning — the rest of Bento continues to work. Check the logs to find out why your block did not appear.

---

## Complete example: note-taking block

A fully working block that lets you create, view, and delete notes, with state persistence and command palette actions.

### Folder structure

```
notes/
├── manifest.json
├── block.py
└── icon.svg
```

### manifest.json

```json
{
  "id": "notes",
  "name": "Notes",
  "description": "A simple note-taking block",
  "version": "1.0.0",
  "author": "Your Name",
  "order": 10,
  "api_version": 1,
  "requires_config": [],
  "settings": [
    {
      "key": "notes_max_count",
      "label": "Max notes",
      "type": "int",
      "default": 50,
      "min": 1,
      "max": 500
    }
  ]
}
```

### block.py

```python
"""Bento block: Notes — a simple note-taking block."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from bento_app.blocks.base_block import BaseBlock, load_manifest
from bento_app.config import BentoConfig

logger = logging.getLogger(__name__)


class NotesBlock(BaseBlock):
    """A simple note-taking block with persistence."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._notes: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Header
        header = QLabel("Notes")
        header.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(header)

        # Input row
        input_row = QHBoxLayout()
        self._input = QLineEdit()
        self._input.setPlaceholderText("Type a note and press Enter...")
        self._input.returnPressed.connect(self._add_note)
        input_row.addWidget(self._input)

        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_note)
        input_row.addWidget(add_btn)
        layout.addLayout(input_row)

        # Note list
        self._list = QListWidget()
        layout.addWidget(self._list)

        # Delete button
        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self._delete_selected)
        layout.addWidget(delete_btn)

    def _add_note(self):
        text = self._input.text().strip()
        if not text:
            return

        max_count = BentoConfig().get_int("notes_max_count", 50)
        if len(self._notes) >= max_count:
            self._notes.pop(0)
            self._list.takeItem(0)

        note = {
            "text": text,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        self._notes.append(note)
        self._list.addItem(text)
        self._input.clear()

    def _delete_selected(self):
        row = self._list.currentRow()
        if row < 0:
            return
        self._list.takeItem(row)
        self._notes.pop(row)

    # -- Lifecycle -------------------------------------------------------

    def on_focus(self):
        self._input.setFocus()

    def on_hide(self):
        pass

    def on_save_state(self):
        try:
            state_file = self.get_state_dir() / "notes.json"
            state_file.write_text(
                json.dumps(self._notes, indent=2), encoding="utf-8"
            )
        except Exception:
            logger.warning("Failed to save notes", exc_info=True)

    def on_restore_state(self):
        try:
            state_file = self.get_state_dir() / "notes.json"
            if state_file.exists():
                self._notes = json.loads(
                    state_file.read_text(encoding="utf-8")
                )
                for note in self._notes:
                    self._list.addItem(note["text"])
        except Exception:
            logger.warning("Failed to restore notes", exc_info=True)
            self._notes = []

    def on_shutdown(self):
        pass

    # -- Command palette --------------------------------------------------

    def get_actions(self):
        return [
            {
                "id": "new_note",
                "title": "New Note",
                "description": "Focus the note input field",
            },
            {
                "id": "clear_notes",
                "title": "Clear All Notes",
                "description": "Delete every saved note",
            },
        ]

    # -- Manifest ---------------------------------------------------------

    @staticmethod
    def get_manifest():
        return load_manifest(__file__)
```

### icon.svg

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <rect width="48" height="48" rx="8" fill="#4a90d9"/>
  <text x="24" y="32" text-anchor="middle" fill="#fff"
        font-size="22" font-family="sans-serif">📝</text>
</svg>
```

---

## Further reading

- [Bento README](https://github.com/HabiRabbu/bento/blob/main/README.md) — installation, usage, configuration
- [bento-blocks](https://github.com/HabiRabbu/bento-blocks) — official block library with real-world examples
- [PyQt6 documentation](https://www.riverbankcomputing.com/static/Docs/PyQt6/) — widget reference
- [freedesktop Notifications spec](https://specifications.freedesktop.org/notification-spec/) — DBus notification details
