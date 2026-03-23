<p align="center">
  <img src="bento_app/assets/bento-icon-256.png" width="128" alt="Bento">
</p>

# Bento

A popup control centre for KDE Plasma.

Like a bento box: one container, many compartments. Each compartment is a "block" you can install, remove, or write yourself. The app lives in your system tray and pops open with a hotkey.

![License: MIT](https://img.shields.io/badge/license-MIT-green)

## What it is

Bento is a Yakuake-style popup window for KDE Plasma. Press a hotkey, get a tabbed panel of tools. Each tab is a self-contained block: a PyQt6 widget in a folder. The hotkey is registered through KDE's `kglobalaccel` DBus service, so it works on Wayland without root or `xdotool` hacks.

## Two repos

The project is split in two:

- [**bento**](https://github.com/HabiRabbu/bento) (this repo) is the core app: the window, tray icon, hotkey, settings dialog, and block loader.
- [**bento-blocks**](https://github.com/HabiRabbu/bento-blocks) is the official block library: Linear, Terminal, and others.

Blocks are separate so you can pick only the ones you need, and so block development doesn't touch the core. The core ships a demo block to show how the system works. Everything else comes from `bento-blocks` or blocks you write.

## Installation

### pip (any distro with KDE Plasma)

```bash
git clone https://github.com/HabiRabbu/bento.git
cd bento
pip install .
```

Requires Python 3.11+.

> **Note:** On Arch, Fedora 38+, Ubuntu 23.04+, and other distros enforcing [PEP 668](https://peps.python.org/pep-0668/), `pip install` outside a virtual environment will fail. Use pipx or a venv instead:
>
> ```bash
> pipx install .
> # or
> python -m venv .venv && source .venv/bin/activate && pip install .
> ```

### Development

```bash
git clone https://github.com/HabiRabbu/bento.git
cd bento
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
```

Installs in editable mode with dev dependencies (pytest, pytest-qt, mypy, ruff).

### Installing blocks

Clone the block library and copy whichever blocks you want:

```bash
git clone https://github.com/HabiRabbu/bento-blocks.git
cp -r bento-blocks/linear ~/.config/bento/blocks/
cp -r bento-blocks/terminal ~/.config/bento/blocks/
```

Each block is a self-contained folder. Bento detects new blocks automatically (or on next launch).

## Usage

Run `bento` from a terminal, or enable autostart in the settings dialog.

A tray icon appears. `Meta+Shift+Space` toggles the popup. You can change the hotkey in KDE System Settings -> Shortcuts -> Bento, or through the link in Bento's own settings dialog.

Right-click the tray icon for settings, where you can set API keys, adjust window height, and toggle autostart.

If the hotkey fails to register (outside KDE, or DBus unavailable), Bento logs a warning and keeps running. The tray icon still works as a fallback.

## Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `Meta+Shift+Space` | Toggle Bento window (global, via KDE) |
| `Ctrl+K` | Command palette (search blocks + actions) |
| `Ctrl+1`–`9` | Jump to block by position |
| `Ctrl+Tab` | Next block |
| `Ctrl+Shift+Tab` | Previous block |
| `Escape` | Close window |
| `↑` / `↓` | Navigate sidebar (when sidebar focused) |
| `Tab` | Move between sidebar and content |

## Creating a block

A block is a folder with three files:

```
my_block/
    manifest.json
    block.py
    icon.svg
```

### manifest.json

```json
{
  "id": "my_block",
  "name": "My Block",
  "description": "What it does",
  "version": "1.0.0",
  "author": "you",
  "order": 10,
  "requires_config": ["SOME_API_KEY"]
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `id` | yes | Unique identifier. Letters, numbers, hyphens, underscores only. |
| `name` | yes | Display name shown in the sidebar. |
| `description` | no | Short description for the settings dialog. |
| `version` | yes | Semver string. |
| `author` | no | Author name. |
| `order` | no | Sidebar position. Lower numbers appear first. Default: 1000. |
| `requires_config` | no | List of config keys the block needs (e.g. `["LINEAR_API_KEY"]`). Bento shows a red warning badge on the sidebar icon until every listed key has a value, and auto-generates input fields in Settings. |

### block.py (minimal example)

```python
from bento_app.blocks.base_block import BaseBlock, load_manifest
from PyQt6.QtWidgets import QLabel, QVBoxLayout
from PyQt6.QtCore import Qt


class MyBlock(BaseBlock):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(QLabel("Hello from my block"))

    def on_focus(self):
        pass

    def on_hide(self):
        pass

    @staticmethod
    def get_manifest():
        return load_manifest(__file__)
```

### BaseBlock API

Your block subclasses `BaseBlock`, which is a `QWidget`. Build any UI you want inside it.

`on_focus()` is called when this block becomes the active tab. Focus your primary input widget here (a search field, a text area, etc.).

`on_hide()` is called when the Bento window hides. Stop timers, cancel requests, pause background work.

`get_manifest()` is a required static method. Return the parsed manifest. The `load_manifest(__file__)` helper reads `manifest.json` from the same directory as your `block.py`.

### Reading config values

Use the `BentoConfig` singleton to read settings and API keys:

```python
from bento_app.config import BentoConfig

config = BentoConfig()
api_key = config.get("SOME_API_KEY", "")
base_url = config.get("lm_studio_base_url", "http://localhost:1234/v1")
```

Keys ending in `_KEY`, `_SECRET`, `_TOKEN`, or `_PASSWORD` are treated as sensitive and stored in `.env` instead of `config.json`. Everything else goes in `config.json`. Both are read transparently through the same `config.get()` call.

### Async work

Never block the main thread with network calls or long operations. Use `QThread`:

```python
from PyQt6.QtCore import QThread, pyqtSignal


class FetchWorker(QThread):
    finished = pyqtSignal(str)

    def run(self):
        import requests
        resp = requests.get("https://api.example.com/data", timeout=10)
        self.finished.emit(resp.text)
```

Start the worker from your block and connect `finished` to a method that updates the UI.

### KDE notifications via DBus

```python
import dbus

bus = dbus.SessionBus()
notify = dbus.Interface(
    bus.get_object("org.freedesktop.Notifications", "/org/freedesktop/Notifications"),
    "org.freedesktop.Notifications",
)
notify.Notify("Bento", 0, "", "Title", "Message body", [], {}, 5000)
```

### Installing your block

Drop the folder into `~/.config/bento/blocks/` and you're done. Bento watches that directory and live-reloads blocks automatically (teardown + reimport, no restart needed).

## Configuration

All config lives in `~/.config/bento/`:

- `config.json` holds non-sensitive settings (window height, hotkey, autostart, LM Studio URL).
- `.env` holds sensitive values (API keys, tokens). Created with mode 600 (owner read/write only).

Both files are managed through the settings dialog. You can also edit them by hand.

## Security

API keys are stored in `~/.config/bento/.env`, not in `config.json`. The `.env` file is chmod 600 and listed in `.gitignore`.

The repo includes a `.env.example` with placeholder values. Copy it to `~/.config/bento/.env` and fill in your real keys.

Installing a block means running its code on your machine. This is the same trust model as browser extensions or editor plugins. Only install blocks from sources you trust. The official blocks in [bento-blocks](https://github.com/HabiRabbu/bento-blocks) are maintained by the project.

## Troubleshooting

**Hotkey not working**
- Open KDE System Settings -> Shortcuts and look for "Bento". If it's missing, DBus registration failed. Check terminal output for warnings.
- The tray icon always works as a fallback.

**Block not appearing**
- Check that the folder is in `~/.config/bento/blocks/` and contains both `manifest.json` and `block.py`.
- `manifest.json` must have at least `id`, `name`, and `version`, all non-empty strings.
- Check terminal output. Bento logs a warning for each block that fails to load, with the reason.
- A broken block never crashes Bento. The rest of the app keeps working.

**LM Studio blocks showing errors**
- Verify LM Studio is running and its server is listening on the configured URL (default: `http://localhost:1234/v1`).
- Check that a model is loaded in LM Studio.
- Blocks that depend on LM Studio will show errors when it's offline, but the rest of Bento works fine.

## License

MIT. See [LICENSE](LICENSE).
