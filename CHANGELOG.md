# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-07-14

### Added

- **Popup window** — Yakuake-style frameless popup with sidebar navigation and stacked block content.
- **System tray icon** — left-click toggles the popup; right-click opens a menu with Settings and Quit.
- **KDE global hotkey** — registers `Meta+Shift+Space` via `org.kde.kglobalaccel` DBus (Wayland-safe) with automatic health checks and re-registration.
- **Modular block system** — blocks are self-contained folders (`manifest.json` + `block.py` + `icon.svg`) discovered and loaded dynamically via `importlib`.
- **Block loader** — scans built-in and user block directories, validates manifests, supports user blocks overriding built-ins by ID, and sorts by `(order, id)`.
- **Hot-reload** — file system watcher on `~/.config/bento/blocks/` with 500 ms debounce; live-reloads blocks automatically (teardown + reimport, no restart needed).
- **Configuration manager** (`BentoConfig`) — singleton config store with typed accessors (`get_str`, `get_int`, `get_bool`, `get_list`), atomic JSON writes, and `.env` storage (chmod 600) for sensitive keys.
- **Rich settings dialog** — General, LM Studio, and per-block sections; auto-generates widgets from manifest `settings` arrays (string, int, bool, choice, password types).
- **Command palette** (`Ctrl+K`) — fuzzy search over block names, descriptions, and block-provided actions.
- **Block lifecycle** — `on_focus()`, `on_hide()`, `on_shutdown()`, `on_save_state()`, `on_restore_state()` hooks with graceful error handling.
- **State persistence** — per-block state directories at `~/.config/bento/state/<id>/` via `get_state_dir()`.
- **Notification system** — tray balloon helpers (`notify_info`, `notify_warning`, `notify_error`) with queuing and Do Not Disturb detection via freedesktop DBus.
- **CLI tools** — `bento create-block`, `bento list-blocks`, `bento enable`, `bento disable` subcommands.
- **First-run welcome dialog** — shown on initial launch with links to the block library and settings.
- **Autostart** — optional `.desktop` file creation in `~/.config/autostart/`.
- **Window animations** — slide, fade, or none; configurable style and duration.
- **Multi-screen support** — follow mouse, follow focused window, or primary screen modes.
- **Keyboard navigation** — `Ctrl+1-9` jump to block, `Ctrl+Tab`/`Ctrl+Shift+Tab` cycle, `↑/↓` sidebar navigation, `Escape` to hide.
- **Config import/export** — export all settings to JSON; import from a previously exported file.
- **Demo block** — built-in welcome block with ASCII art, block installation instructions, and a link to the official block library.
- **Arch Linux packaging** — PKGBUILD and `.desktop` entry in `packaging/`.
- **Test suite** — pytest + pytest-qt tests for manifest validation, block loading, configuration, and integration smoke tests.

[0.1.0]: https://github.com/HabiRabbu/bento/releases/tag/v0.1.0
