# MIT License — Copyright (c) 2026 HabiRabbu — see LICENSE
"""Main Bento popup window.

Frameless, centered, pinned to the top (or bottom) of the target screen.
Contains a narrow icon sidebar on the left and a stacked content area on the
right that displays the active block's widget.
"""

from __future__ import annotations

import contextlib
import logging
import traceback as _tb_mod
from typing import TYPE_CHECKING

from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QCursor, QGuiApplication, QKeyEvent, QPainter, QPaintEvent, QRegion
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from bento_app.blocks.base_block import BaseBlock, ManifestDict
from bento_app.config import BentoConfig
from bento_app.notify import notify_warning
from bento_app.placeholder_widgets import (
    EmptyPlaceholder,
    ErrorPlaceholder,
    LoadingPlaceholder,
)

if TYPE_CHECKING:
    from bento_app.block_loader import BlockLoader

logger = logging.getLogger(__name__)


class _SidebarButton(QToolButton):
    """Icon button used in the sidebar, with optional warning badge."""

    def __init__(self, icon_path: str, tooltip: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        from PyQt6.QtGui import QIcon

        self.setIcon(QIcon(icon_path))
        self.setToolTip(tooltip)
        self.setFixedSize(44, 44)
        self.setIconSize(QSize(36, 36))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setStyleSheet("""
            QToolButton {
                border: none;
                border-radius: 6px;
                padding: 4px;
            }
            QToolButton:hover {
                background-color: palette(midlight);
            }
            QToolButton:checked {
                background-color: palette(midlight);
            }
            QToolButton:focus {
                border: 2px solid palette(highlight);
            }
        """)
        self._show_badge = False

    def set_warning_badge(self, show: bool) -> None:
        self._show_badge = show
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.isChecked():
            painter.setBrush(self.palette().color(self.palette().ColorRole.Highlight))
            painter.setPen(Qt.PenStyle.NoPen)
            bar_h = self.height() - 8
            painter.drawRoundedRect(2, 4, 3, bar_h, 1.5, 1.5)
        if self._show_badge:
            painter.setBrush(self.palette().color(self.palette().ColorRole.Link))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(self.width() - 12, 2, 10, 10)
        painter.end()


class _ResizeHandle(QWidget):
    """Thin draggable strip for resizing the window."""

    def __init__(self, parent: BentoWindow) -> None:  # type: ignore[forward-ref]
        super().__init__(parent)
        self.setFixedHeight(10)
        self.setCursor(Qt.CursorShape.SizeVerCursor)
        self.setToolTip("Drag to resize")
        self._dragging = False
        self._start_y = 0
        self._start_height = 0

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        """Draw three small horizontal grip lines centered in the handle."""
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self.palette().color(self.palette().ColorRole.Mid)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        cx = self.width() // 2
        cy = self.height() // 2
        dot_w, dot_h, gap = 16, 2, 4
        for offset in (-gap, 0, gap):
            painter.drawRoundedRect(cx - dot_w // 2, cy + offset - dot_h // 2, dot_w, dot_h, 1, 1)
        painter.end()

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._start_y = event.globalPosition().y()
            self._start_height = self.parent().height()
            self._cached_position = BentoConfig().get_str("window_position", "top")

    def mouseMoveEvent(self, event):  # noqa: N802
        if self._dragging:
            delta = event.globalPosition().y() - self._start_y
            parent = self.parent()
            screen = QGuiApplication.screenAt(self.window().geometry().center())
            if screen is None:
                screen = QGuiApplication.primaryScreen()
            max_h = screen.geometry().height() if screen is not None else 800
            if self._cached_position == "bottom":
                new_height = max(200, min(max_h, int(self._start_height - delta)))
            else:
                new_height = max(200, min(max_h, int(self._start_height + delta)))
            parent.setFixedHeight(new_height)
            window = self.window()
            if hasattr(window, "_update_content_mask"):
                window._update_content_mask()

    def mouseReleaseEvent(self, event):  # noqa: N802
        if self._dragging:
            self._dragging = False
            BentoConfig().set("window_height", self.parent().height())
            BentoConfig().save()


class BentoWindow(QWidget):
    """The main Bento popup window."""

    settings_requested = pyqtSignal()

    def __init__(
        self,
        block_data: list[tuple[ManifestDict, type[BaseBlock]]],
        parent: QWidget | None = None,
        *,
        loader: BlockLoader | None = None,
    ) -> None:
        super().__init__(parent)
        self._config = BentoConfig()
        self._block_data: list[tuple[ManifestDict, type[BaseBlock]]] = list(block_data)
        self._instances: dict[int, BaseBlock] = {}
        self._active_index = 0
        self._dialog_open = False
        self._loader: BlockLoader | None = loader
        self._close_check_pending = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            geo = screen.geometry()
            try:
                height = max(200, min(geo.height(), int(self._config.get("window_height", 420))))
            except (TypeError, ValueError):
                height = 420
            width_pct = max(20, min(100, self._config.get_int("window_width_percent", 70)))
            win_w = int(geo.width() * width_pct / 100)
            win_x = geo.x() + (geo.width() - win_w) // 2
            self.setGeometry(win_x, geo.y(), win_w, height)

        self._anim_group = QParallelAnimationGroup(self)
        self._fade = QPropertyAnimation(self, b"windowOpacity")
        self._slide = QPropertyAnimation(self, b"contentHeight")
        self._anim_group.addAnimation(self._fade)
        self._anim_group.addAnimation(self._slide)
        self._anim_group.finished.connect(self._on_animation_done)
        self._is_hiding = False

        # Content container with solid background (window itself is transparent)
        self._content_container = QWidget(self)
        self._content_container.setAutoFillBackground(True)

        content_layout = QVBoxLayout(self._content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        root = QHBoxLayout()
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._sidebar = QWidget(self)
        self._sidebar.setAutoFillBackground(True)
        pal = self._sidebar.palette()
        pal.setColor(pal.ColorRole.Window, pal.color(pal.ColorRole.Dark))
        self._sidebar.setPalette(pal)

        sidebar_layout = QVBoxLayout(self._sidebar)
        sidebar_layout.setContentsMargins(6, 6, 6, 6)
        sidebar_layout.setSpacing(6)

        self._buttons: list[_SidebarButton] = []
        self._stack = QStackedWidget(self)

        for i, (manifest, _block_cls) in enumerate(self._block_data):
            icon_path = self._resolve_icon(manifest)
            name = manifest.get("name", manifest["id"])
            tooltip = f"{name} (Ctrl+{i + 1})" if i < 9 else name
            btn = _SidebarButton(icon_path, tooltip)
            btn.setAccessibleName(f"Switch to {manifest['name']} block")
            btn.clicked.connect(lambda checked, idx=i: self._switch_block(idx))
            sidebar_layout.addWidget(btn)
            self._buttons.append(btn)

            self._update_badge(btn, manifest)

            placeholder = LoadingPlaceholder(manifest.get("name", ""))
            self._stack.addWidget(placeholder)

        sidebar_layout.addStretch()

        self._create_settings_button(sidebar_layout)

        self._sidebar.setAccessibleName("Block sidebar")
        self._stack.setAccessibleName("Block content area")

        self._sidebar.setFixedWidth(56)

        root.addWidget(self._sidebar)

        sidebar_sep = QFrame(self)
        sidebar_sep.setFrameShape(QFrame.Shape.VLine)
        sidebar_sep.setFrameShadow(QFrame.Shadow.Plain)
        sidebar_sep.setStyleSheet("QFrame { color: palette(mid); }")
        root.addWidget(sidebar_sep)

        root.addWidget(self._stack)

        content_layout.addLayout(root, 1)

        self._resize_handle = _ResizeHandle(self)
        position = self._config.get_str("window_position", "top")
        if position == "bottom":
            content_layout.insertWidget(0, self._resize_handle)
        else:
            content_layout.addWidget(self._resize_handle)

        # Window layout: position content at screen edge
        window_layout = QVBoxLayout(self)
        window_layout.setContentsMargins(0, 0, 0, 0)
        window_layout.setSpacing(0)
        if position == "bottom":
            window_layout.addStretch()
        window_layout.addWidget(
            self._content_container, 0, Qt.AlignmentFlag.AlignHCenter
        )
        if position != "bottom":
            window_layout.addStretch()

        self._empty_widget: QWidget | None = None
        if self._is_empty_state():
            self._show_empty_state()

        if self._buttons:
            self._buttons[0].setChecked(True)
            self._stack.setCurrentIndex(0)
            self._ensure_block_loaded(0)
            for i in range(1, len(self._block_data)):
                self._deferred_load(i * 100, i)

        self.setWindowOpacity(0.0)


    def set_loader(self, loader: BlockLoader) -> None:
        """Store a reference to the BlockLoader for hot-reload."""
        self._loader = loader

    def _create_settings_button(self, layout: QVBoxLayout) -> None:
        """Add the settings gear button to the bottom of a sidebar layout."""
        self._settings_btn = QToolButton(self._sidebar)
        self._settings_btn.setText("\u2699")
        self._settings_btn.setFixedSize(44, 44)
        self._settings_btn.setToolTip("Settings")
        self._settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._settings_btn.setStyleSheet(
            "QToolButton { font-size: 20px; border: none; border-radius: 6px;"
            " color: palette(light); }"
            "QToolButton:hover { background-color: rgba(255,255,255,0.1); }"
        )
        self._settings_btn.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self._settings_btn)

    def _deferred_load(self, delay_ms: int, index: int) -> None:
        """Schedule a block load that's safe against early widget destruction."""
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(delay_ms)
        timer.timeout.connect(lambda: self._ensure_block_loaded(index))
        timer.start()

    def toggle(self) -> None:
        """Show or hide the window with a fade animation."""
        if self.isVisible():
            self._hide_animated()
        else:
            self._show_animated()

    def set_dialog_open(self, state: bool) -> None:
        """Tell the window a child dialog (e.g. Settings) is open."""
        self._dialog_open = state

    def refresh_badges(self) -> None:
        """Re-check required config badges for all blocks."""
        for btn, (manifest, _cls) in zip(self._buttons, self._block_data):
            self._update_badge(btn, manifest)

    def get_loaded_instances(self) -> list[tuple[ManifestDict, BaseBlock]]:
        """Return all currently instantiated blocks (for shutdown)."""
        result = []
        for idx in sorted(self._instances):
            if idx < len(self._block_data):
                result.append((self._block_data[idx][0], self._instances[idx]))
        return result


    def _ensure_block_loaded(self, index: int) -> None:
        """Lazily instantiate a block and replace its loading placeholder."""
        if index in self._instances:
            return
        if index < 0 or index >= len(self._block_data):
            return

        manifest, block_cls = self._block_data[index]

        required_config = manifest.get("requires_config", [])
        if required_config:
            config = BentoConfig()
            missing = [k for k in required_config if not config.get(k)]
            if missing:
                placeholder = QWidget()
                layout = QVBoxLayout(placeholder)
                layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                icon_label = QLabel("\u2699")
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                font = icon_label.font()
                font.setPointSize(24)
                icon_label.setFont(font)
                layout.addWidget(icon_label)
                msg = QLabel(
                    f"This block requires configuration.\n\n"
                    f"Missing: {', '.join(missing)}"
                )
                msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
                msg.setWordWrap(True)
                layout.addWidget(msg)
                settings_btn = QPushButton("Open Settings")
                settings_btn.setAccessibleName(f"Open settings for {manifest.get('name', '')}")
                settings_btn.setFixedWidth(150)
                settings_btn.clicked.connect(lambda: self._open_settings_for_block(manifest))
                layout.addWidget(settings_btn, alignment=Qt.AlignmentFlag.AlignCenter)
                self._replace_stack_widget(index, placeholder)
                return

        try:
            instance = block_cls()
        except Exception as exc:
            logger.error(
                "Failed to instantiate block '%s': %s",
                manifest.get("id"), exc, exc_info=True,
            )
            notify_warning(
                "Block failed",
                f"Could not load block '{manifest.get('id')}': {exc}",
            )
            tb_text = _tb_mod.format_exc()
            error_widget = ErrorPlaceholder(
                manifest.get("name", "?"),
                exc,
                tb_text,
                on_reload=lambda idx=index: self._reload_block(idx),
            )
            self._replace_stack_widget(index, error_widget)
            return

        try:
            instance.on_restore_state()
        except Exception:
            logger.warning(
                "Error restoring state for block '%s'",
                manifest.get("id"),
                exc_info=True,
            )

        self._instances[index] = instance
        self._replace_stack_widget(index, instance)

    def _reload_block(self, index: int) -> None:
        """Re-import and reinstantiate a single block (error-card reload or hot-reload)."""
        if index < 0 or index >= len(self._block_data):
            return

        manifest = self._block_data[index][0]
        block_id = manifest.get("id", "")

        old = self._instances.pop(index, None)
        if old is not None:
            try:
                old.on_save_state()
            except Exception:
                logger.warning("Error saving state for block '%s'", block_id, exc_info=True)
            try:
                old.on_shutdown()
            except Exception:
                logger.warning("Error during shutdown of block '%s'", block_id, exc_info=True)

        loading = LoadingPlaceholder(manifest.get("name", ""))
        self._replace_stack_widget(index, loading)

        if self._loader is not None:
            try:
                result = self._loader.reload_block(block_id)
                if result is not None:
                    new_manifest, new_cls = result
                    self._block_data[index] = (new_manifest, new_cls)
            except Exception:
                logger.warning("Failed to reimport block '%s'", block_id, exc_info=True)

        self._ensure_block_loaded(index)

        if index == self._active_index:
            self._stack.setCurrentIndex(index)
            self._focus_active_block()

    def _replace_stack_widget(self, index: int, new_widget: QWidget) -> None:
        """Replace the widget at *index* in the stack."""
        old = self._stack.widget(index)
        self._stack.removeWidget(old)
        self._stack.insertWidget(index, new_widget)
        # insertWidget() may auto-change currentIndex — restore it.
        self._stack.setCurrentIndex(self._active_index)
        if old is not None:
            old.deleteLater()


    def _is_empty_state(self) -> bool:
        """True when no blocks are loaded at all."""
        return len(self._block_data) == 0

    def _show_empty_state(self) -> None:
        if self._empty_widget is not None:
            return
        self._empty_widget = EmptyPlaceholder()
        self._stack.addWidget(self._empty_widget)

    def _remove_empty_state(self) -> None:
        if self._empty_widget is not None:
            self._stack.removeWidget(self._empty_widget)
            self._empty_widget.deleteLater()
            self._empty_widget = None


    def handle_blocks_changed(
        self, new_block_data: list[tuple[ManifestDict, type[BaseBlock]]]
    ) -> None:
        """Rebuild the UI after the block loader detects changes."""
        try:
            active_id = (
                self._block_data[self._active_index][0]["id"]
                if self._block_data
                else None
            )

            for idx, instance in list(self._instances.items()):
                m = self._block_data[idx][0] if idx < len(self._block_data) else {}
                try:
                    instance.on_save_state()
                except Exception:
                    logger.warning("Error saving state for block '%s'", m.get("id"), exc_info=True)
                try:
                    instance.on_shutdown()
                except Exception:
                    logger.warning("Error during shutdown of block '%s'", m.get("id"), exc_info=True)
                instance.deleteLater()
            self._instances.clear()

            self._remove_empty_state()

            sidebar_layout = self._sidebar.layout()
            for btn in self._buttons:
                sidebar_layout.removeWidget(btn)
                btn.deleteLater()
            self._buttons.clear()

            while sidebar_layout.count() > 0:
                item = sidebar_layout.takeAt(0)
                w = item.widget() if item else None
                if w is not None:
                    w.deleteLater()

            while self._stack.count() > 0:
                w = self._stack.widget(0)
                self._stack.removeWidget(w)
                w.deleteLater()

            self._block_data = list(new_block_data)
            self._active_index = 0

            for i, (manifest, _block_cls) in enumerate(self._block_data):
                icon_path = self._resolve_icon(manifest)
                name = manifest.get("name", manifest["id"])
                tooltip = f"{name} (Ctrl+{i + 1})" if i < 9 else name
                btn = _SidebarButton(icon_path, tooltip)
                btn.setAccessibleName(f"Switch to {manifest['name']} block")
                btn.clicked.connect(lambda checked, idx=i: self._switch_block(idx))
                sidebar_layout.addWidget(btn)
                self._buttons.append(btn)
                self._update_badge(btn, manifest)

                placeholder = LoadingPlaceholder(manifest.get("name", ""))
                self._stack.addWidget(placeholder)

            sidebar_layout.addStretch()

            self._create_settings_button(sidebar_layout)

            if active_id:
                for i, (m, _) in enumerate(self._block_data):
                    if m["id"] == active_id:
                        self._active_index = i
                        break

            if self._buttons:
                self._buttons[self._active_index].setChecked(True)
                self._ensure_block_loaded(self._active_index)
                self._stack.setCurrentIndex(self._active_index)
                for i in range(len(self._block_data)):
                    if i != self._active_index:
                        self._deferred_load(i * 100, i)

            if self._is_empty_state():
                self._show_empty_state()

            logger.info("Hot-reload complete — %d block(s)", len(self._block_data))

        except Exception:
            logger.error("Hot-reload UI rebuild failed", exc_info=True)
            notify_warning("Hot-reload failed", "An error occurred while reloading blocks.")

    # -- Content height property (animated for yakuake-style slide) ----------

    def _get_content_height(self) -> int:
        if hasattr(self, "_content_container"):
            return self._content_container.height()
        return 0

    def _set_content_height(self, h: int) -> None:
        self._content_container.setFixedHeight(max(0, int(h)))
        self._update_content_mask()

    contentHeight = pyqtProperty(int, fget=_get_content_height, fset=_set_content_height)

    def _update_content_mask(self) -> None:
        """Update the window input/render mask to match the content area."""
        if not hasattr(self, "_content_container"):
            return
        layout = self.layout()
        if layout:
            layout.activate()
        geo = self._content_container.geometry()
        if geo.height() > 0:
            self.setMask(QRegion(geo))
        else:
            self.setMask(QRegion())


    def _show_animated(self) -> None:
        cfg = self._config
        position = cfg.get_str("window_position", "top")
        style = cfg.get_str("animation_style", "slide")
        duration = max(50, min(500, cfg.get_int("animation_duration", 250)))

        screen_mode = BentoConfig().get_str("screen_mode", "follow_mouse")
        if screen_mode == "follow_mouse":
            screen = QGuiApplication.screenAt(QCursor.pos())
        elif screen_mode == "follow_focus":
            focused = QGuiApplication.focusWindow()
            screen = focused.screen() if focused else None
        else:
            screen = None

        if screen is None:
            screen = QGuiApplication.primaryScreen()

        if screen is not None:
            geo = screen.geometry()
            try:
                height = max(200, min(geo.height(), int(cfg.get("window_height", 420))))
            except (TypeError, ValueError):
                height = 420

            width_pct = max(20, min(100, cfg.get_int("window_width_percent", 70)))
            win_w = int(geo.width() * width_pct / 100)

            # Window covers the full screen (transparent background).
            # Content container is positioned by the layout at the screen edge.
            # This sidesteps Wayland compositor placement — screen-sized windows
            # are placed at the screen origin.
            self.setGeometry(geo)
            self._content_container.setFixedWidth(win_w)

        if style == "none":
            self._content_container.setFixedHeight(height)
            self._update_content_mask()
            self.setWindowOpacity(1.0)
            self.show()
            self.activateWindow()
            app = QApplication.instance()
            if app is not None:
                app.focusChanged.connect(self._on_focus_changed)
        else:
            self._anim_group.stop()

            if style == "slide" and screen is not None:
                # Yakuake-style: grow content height from 0 at the screen edge.
                self.setWindowOpacity(1.0)
                self._content_container.setFixedHeight(0)
                self._update_content_mask()

                self._fade.setDuration(0)
                self._fade.setStartValue(1.0)
                self._fade.setEndValue(1.0)

                self._slide.setDuration(duration)
                self._slide.setStartValue(0)
                self._slide.setEndValue(height)
                self._slide.setEasingCurve(QEasingCurve.Type.OutExpo)
            else:
                # Fade-only
                self._content_container.setFixedHeight(height)
                self._update_content_mask()
                self.setWindowOpacity(0.0)

                self._fade.setDuration(duration)
                self._fade.setStartValue(0.0)
                self._fade.setEndValue(1.0)
                self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)

                self._slide.setDuration(0)
                self._slide.setStartValue(height)
                self._slide.setEndValue(height)

            self.show()
            self.activateWindow()
            app = QApplication.instance()
            if app is not None:
                app.focusChanged.connect(self._on_focus_changed)

            self._anim_group.start()

        QTimer.singleShot(0, self._focus_active_block)

    def _hide_animated(self) -> None:
        if self._is_hiding:
            return
        self._is_hiding = True

        cfg = self._config
        style = cfg.get_str("animation_style", "slide")
        duration = max(50, min(500, cfg.get_int("animation_duration", 250)))
        position = cfg.get_str("window_position", "top")

        if style == "none":
            app = QApplication.instance()
            if app is not None:
                with contextlib.suppress(TypeError):
                    app.focusChanged.disconnect(self._on_focus_changed)
            self.hide()
            self._is_hiding = False
            self._notify_active_block_hidden()
            return

        self._anim_group.stop()

        if style == "slide":
            # Yakuake-style: shrink content height back to 0.
            self._fade.setDuration(0)
            self._fade.setStartValue(1.0)
            self._fade.setEndValue(1.0)

            current_h = self._content_container.height()
            self._slide.setDuration(duration)
            self._slide.setStartValue(current_h)
            self._slide.setEndValue(0)
            self._slide.setEasingCurve(QEasingCurve.Type.InExpo)
        else:
            # Fade-only
            self._fade.setDuration(duration)
            self._fade.setStartValue(self.windowOpacity())
            self._fade.setEndValue(0.0)
            self._fade.setEasingCurve(QEasingCurve.Type.InCubic)

            self._slide.setDuration(0)

        self._anim_group.start()

    @pyqtSlot()
    def _on_animation_done(self) -> None:
        if not self._is_hiding:
            return
        self._is_hiding = False
        app = QApplication.instance()
        if app is not None:
            with contextlib.suppress(TypeError):
                app.focusChanged.disconnect(self._on_focus_changed)
        self.setWindowOpacity(0.0)
        self.hide()
        self._notify_active_block_hidden()


    def _safe_block_lifecycle(self, index: int, method: str) -> None:
        """Call a lifecycle method on the active block, handling crashes."""
        block = self._instances.get(index)
        if block is None:
            return
        try:
            getattr(block, method)()
        except Exception as exc:
            name = self._block_data[index][0].get("name", "?")
            logger.error("Block '%s' crashed in %s(): %s", name, method, exc, exc_info=True)
            notify_warning("Block error", f"Block '{name}' crashed")
            self._show_block_error(index, name, exc)

    def _switch_block(self, index: int) -> None:
        if index == self._active_index and index in self._instances:
            return
        self._safe_block_lifecycle(self._active_index, "on_hide")

        self._active_index = index
        self._stack.setCurrentIndex(index)
        self._ensure_block_loaded(index)
        self._focus_active_block()

    def _focus_active_block(self) -> None:
        self._safe_block_lifecycle(self._active_index, "on_focus")

    def _notify_active_block_hidden(self) -> None:
        self._safe_block_lifecycle(self._active_index, "on_hide")

    def _get_active_block(self) -> BaseBlock | None:
        return self._instances.get(self._active_index)

    def _show_block_error(self, index: int, block_name: str, exc: Exception) -> None:
        """Replace a crashed block with an error card."""
        self._instances.pop(index, None)
        tb_text = _tb_mod.format_exc()
        error_widget = ErrorPlaceholder(
            block_name,
            exc,
            tb_text,
            on_reload=lambda idx=index: self._reload_block(idx),
        )
        self._replace_stack_widget(index, error_widget)


    def _update_badge(self, btn: _SidebarButton, manifest: ManifestDict) -> None:
        required = manifest.get("requires_config", [])
        if not required:
            btn.set_warning_badge(False)
            return
        config = BentoConfig()
        missing = any(not config.get(k) for k in required)
        btn.set_warning_badge(missing)

    @staticmethod
    def _resolve_icon(manifest: ManifestDict) -> str:
        """Best-effort icon path for a block manifest."""
        block_id = manifest.get("id", "")
        from pathlib import Path
        for candidate_dir in [
            Path(__file__).resolve().parent / "builtin_blocks" / block_id,
            BentoConfig.config_dir() / "blocks" / block_id,
        ]:
            icon = candidate_dir / "icon.svg"
            if icon.exists():
                return str(icon)
        return ""


    def _open_settings_for_block(self, manifest: ManifestDict) -> None:
        """Request settings dialog for a specific block."""
        self.settings_requested.emit()

    def _show_command_palette(self) -> None:
        """Create and display the Ctrl+K command palette."""
        if self._dialog_open:
            return
        from bento_app.command_palette import CommandPalette

        blocks_for_palette: list[tuple[ManifestDict, BaseBlock | None]] = []
        for i, (manifest, _cls) in enumerate(self._block_data):
            blocks_for_palette.append((manifest, self._instances.get(i)))

        palette = CommandPalette(blocks_for_palette, parent=self)
        palette.block_selected.connect(self._switch_block)
        palette.action_selected.connect(self._on_palette_action)

        self._dialog_open = True

        def _on_palette_closed() -> None:
            self._dialog_open = False

        palette.destroyed.connect(_on_palette_closed)
        cpos = self.mapToGlobal(self._content_container.pos())
        palette.show_centered(QRect(cpos, self._content_container.size()))

    def _on_palette_action(self, block_id: str, action_id: str) -> None:
        """Execute a block action chosen from the command palette."""
        for idx, (manifest, _cls) in enumerate(self._block_data):
            if manifest.get("id") == block_id:
                instance = self._instances.get(idx)
                if instance is not None and hasattr(instance, "get_actions"):
                    try:
                        for action in instance.get_actions():
                            if action.get("id") == action_id:
                                callback = action.get("callback")
                                if callable(callback):
                                    callback()
                                return
                    except Exception:
                        logger.warning("Failed to run action '%s' on block '%s'", action_id, block_id, exc_info=True)
                break

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_K and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self._show_command_palette()
            return

        if event.key() == Qt.Key.Key_Escape:
            self._hide_animated()
            return

        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            key = event.key()
            if Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
                idx = key - Qt.Key.Key_1
                if idx < len(self._buttons):
                    self._switch_block(idx)
                    return

        if event.key() == Qt.Key.Key_Tab and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            count = len(self._block_data)
            if count > 0:
                current = self._stack.currentIndex()
                self._switch_block((current + 1) % count)
            return

        if event.key() == Qt.Key.Key_Backtab and event.modifiers() == (
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            count = len(self._block_data)
            if count > 0:
                current = self._stack.currentIndex()
                self._switch_block((current - 1) % count)
            return

        if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            focused = QApplication.focusWidget()
            if focused is not None and self._sidebar.isAncestorOf(focused):
                current = self._stack.currentIndex()
                count = len(self._block_data)
                if event.key() == Qt.Key.Key_Down:
                    new_idx = min(current + 1, count - 1)
                else:
                    new_idx = max(current - 1, 0)
                self._switch_block(new_idx)
                self._buttons[new_idx].setFocus()
                return
            super().keyPressEvent(event)
            return

        if event.key() == Qt.Key.Key_Tab and event.modifiers() == Qt.KeyboardModifier.NoModifier:
            focused = QApplication.focusWidget()
            if focused is not None and self._sidebar.isAncestorOf(focused):
                block = self._get_active_block()
                if block is not None:
                    block.setFocus()
                    return
            super().keyPressEvent(event)
            return

        super().keyPressEvent(event)

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """Auto-hide when the window is deactivated (e.g. user clicks elsewhere)."""
        super().changeEvent(event)
        if (
            event.type() == QEvent.Type.ActivationChange
            and not self.isActiveWindow()
            and self.isVisible()
            and not self._dialog_open
            and not self._is_hiding
            and not self._close_check_pending
        ):
            self._close_check_pending = True
            QTimer.singleShot(50, self._check_should_close)

    def _on_focus_changed(self, _old: QWidget | None, new: QWidget | None) -> None:
        """Close the window when focus leaves it entirely."""
        if not self.isVisible() or self._dialog_open:
            return
        if new is None:
            return
        if (  # noqa: SIM102
            not self.isAncestorOf(new) and new is not self
            and not self._close_check_pending
        ):
            self._close_check_pending = True
            QTimer.singleShot(50, self._check_should_close)

    def _check_should_close(self) -> None:
        """Deferred close check — avoids race with tray menu clicks."""
        self._close_check_pending = False
        if not self.isVisible() or self._dialog_open:
            return
        focus = QApplication.focusWidget()
        if focus is not None and (self.isAncestorOf(focus) or focus is self):
            return
        self._hide_animated()
