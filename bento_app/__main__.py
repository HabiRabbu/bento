#!/usr/bin/env python3
# MIT License — Copyright (c) 2026 HabiRabbu — see LICENSE
"""Bento — A Yakuake-style popup control centre for KDE Plasma.

Entry point.  Starts the system tray icon, registers the global hotkey,
and loads all discovered blocks.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
import sys
from pathlib import Path

from bento_app import __version__

logger = logging.getLogger("bento")

_PKG_DIR = Path(__file__).resolve().parent


def main() -> int:
    """Application entry point."""
    parser = argparse.ArgumentParser(description="Bento — popup control centre for KDE Plasma")
    parser.add_argument("--version", action="version", version=f"Bento {__version__}")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--dev", action="store_true",
                        help="Enable developer mode (shows DevPanel with logs, manifests, config, reload)")
    parser.add_argument("--log-file", type=str, default=None,
                        help="Log to file (default: ~/.config/bento/bento.log in debug mode)")

    subparsers = parser.add_subparsers(dest="command")
    create_parser = subparsers.add_parser("create-block", help="Scaffold a new block")
    create_parser.add_argument("name", help="Block name/ID")
    subparsers.add_parser("list-blocks", help="List all blocks")
    enable_parser = subparsers.add_parser("enable", help="Enable a block")
    enable_parser.add_argument("block_id")
    disable_parser = subparsers.add_parser("disable", help="Disable a block")
    disable_parser.add_argument("block_id")

    args, _ = parser.parse_known_args()

    if args.command:
        from bento_app.cli import create_block, disable_block, enable_block, list_blocks

        if args.command == "create-block":
            create_block(args.name)
        elif args.command == "list-blocks":
            list_blocks()
        elif args.command == "enable":
            enable_block(args.block_id)
        elif args.command == "disable":
            disable_block(args.block_id)
        return 0

    log_level = logging.DEBUG if args.debug else logging.INFO

    env_level = os.environ.get("BENTO_LOG_LEVEL", "").upper()
    if env_level in ("DEBUG", "INFO", "WARNING", "ERROR"):
        log_level = getattr(logging, env_level)

    handlers: list[logging.Handler] = [logging.StreamHandler()]

    log_file = args.log_file
    if log_file is None and args.debug:
        log_dir = Path.home() / ".config" / "bento"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = str(log_dir / "bento.log")

    if log_file:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(log_file, maxBytes=1_048_576, backupCount=3)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s"
        ))
        handlers.append(file_handler)

    logging.basicConfig(level=log_level, handlers=handlers,
                        format="%(name)s %(levelname)s: %(message)s")

    if args.dev:
        from bento_app.dev_tools import install_log_capture, set_dev_mode
        set_dev_mode(True)
        install_log_capture()
        logger.info("Developer mode enabled")

    from PyQt6.QtWidgets import QApplication

    from bento_app import notify
    from bento_app.block_loader import BlockLoader
    from bento_app.config import BentoConfig
    from bento_app.first_run import FirstRunDialog, should_show_first_run
    from bento_app.hotkey import HotkeyManager
    from bento_app.notify import notify_warning
    from bento_app.settings import SettingsDialog
    from bento_app.tray import BentoTray
    from bento_app.window import BentoWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Bento")
    app.setQuitOnLastWindowClosed(False)

    config = BentoConfig()
    config.load()

    if config._config_was_corrupted:
        notify_warning(
            "Config Reset",
            "config.json was corrupted \u2014 using defaults. Backup saved as config.json.bak",
        )

    loader = BlockLoader(_PKG_DIR)
    loaded = loader.load_all()

    window = BentoWindow(loaded, loader=loader)

    def open_settings() -> None:
        window.set_dialog_open(True)
        dialog = SettingsDialog(loaded, _PKG_DIR, parent=window)
        dialog.finished.connect(lambda: _on_settings_closed(window, loader))
        dialog.show()

    def _on_settings_closed(win: BentoWindow, ldr: BlockLoader) -> None:
        win.set_dialog_open(False)
        win.refresh_badges()

    window.settings_requested.connect(open_settings)

    want_settings = False
    if should_show_first_run():
        dlg = FirstRunDialog()
        dlg.exec()
        want_settings = dlg.open_settings_requested

    icon_path = _PKG_DIR / "assets" / "icon.svg"
    tray = BentoTray(
        icon_path=icon_path,
        toggle_callback=window.toggle,
        settings_callback=open_settings,
    )

    notify.init(tray)

    hotkey = HotkeyManager(
        shortcut=str(config.get("hotkey", "Meta+Shift+Space")),
        callback=window.toggle,
    )
    if not hotkey.is_registered:
        notify_warning(
            "Hotkey unavailable",
            "Global hotkey could not be registered. Use the tray icon to toggle Bento.",
        )

    if want_settings:
        open_settings()

    def _on_blocks_changed() -> None:
        logger.info("Blocks changed — performing live hot-reload")
        try:
            window.handle_blocks_changed(loader.blocks)
            tray.showMessage("Bento", "Blocks reloaded successfully.")
        except Exception:
            logger.error("Hot-reload failed", exc_info=True)
            tray.showMessage("Bento", "Blocks directory changed but reload failed.")

    loader.blocks_changed.connect(_on_blocks_changed)

    def _shutdown_blocks() -> None:
        for manifest, block in window.get_loaded_instances():
            try:
                block.on_save_state()
            except Exception:
                logger.warning("Error saving state for block '%s'", manifest.get("id"), exc_info=True)
            try:
                block.on_shutdown()
            except Exception:
                logger.warning("Error during shutdown of block '%s'", manifest.get("id"), exc_info=True)

    app.aboutToQuit.connect(_shutdown_blocks)

    app.aboutToQuit.connect(hotkey.unregister)

    logger.info(
        "Bento started — %d block(s) discovered, hotkey %s",
        len(loaded),
        "registered" if hotkey.is_registered else "not registered (use tray icon)",
    )

    # Unix signals cannot safely call Qt methods directly; use a socket pair
    # to wake the Qt event loop and dispatch from there.
    _sig_rsock, _sig_wsock = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
    _sig_rsock.setblocking(False)
    _sig_wsock.setblocking(False)

    _reload_requested = False

    def _sig_handler(signum: int, _frame: object) -> None:
        nonlocal _reload_requested
        if signum == signal.SIGTERM:
            _sig_wsock.send(b"\x00")
        elif hasattr(signal, "SIGUSR1") and signum == signal.SIGUSR1:
            _reload_requested = True
            _sig_wsock.send(b"\x01")

    from PyQt6.QtCore import QSocketNotifier

    notifier = QSocketNotifier(_sig_rsock.fileno(), QSocketNotifier.Type.Read, app)

    def _on_signal_activated() -> None:
        nonlocal _reload_requested
        try:
            data = _sig_rsock.recv(1)
        except BlockingIOError:
            return
        if data == b"\x00":
            logger.info("SIGTERM received — shutting down gracefully")
            app.quit()
        elif data == b"\x01" and _reload_requested:
            _reload_requested = False
            logger.info("SIGUSR1 received — reloading blocks")
            new_blocks = loader.load_all()
            window.handle_blocks_changed(new_blocks)

    notifier.activated.connect(_on_signal_activated)

    signal.signal(signal.SIGTERM, _sig_handler)
    if hasattr(signal, "SIGUSR1"):
        signal.signal(signal.SIGUSR1, _sig_handler)

    try:
        return app.exec()
    except Exception:
        logger.critical("Bento crashed", exc_info=True)
        if log_file:
            print(f"Crash log: {log_file}", file=sys.stderr)
        return 1
    finally:
        _sig_rsock.close()
        _sig_wsock.close()


if __name__ == "__main__":
    sys.exit(main())
