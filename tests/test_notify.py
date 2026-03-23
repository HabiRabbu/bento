"""Tests for bento_app.notify — queued notifications and DND cache."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_queued_notifier_buffers_before_init():
    """Messages are queued when no tray icon has been set."""
    from bento_app.notify import QueuedNotifier

    notifier = QueuedNotifier()
    notifier._show("Title1", "Msg1", 1)
    notifier._show("Title2", "Msg2", 2)

    assert len(notifier._queue) == 2
    assert notifier._queue[0] == ("Title1", "Msg1", 1)
    assert notifier._queue[1] == ("Title2", "Msg2", 2)


def test_queued_notifier_flushes_on_init():
    """Queued messages are sent when the tray icon is provided."""
    from bento_app.notify import QueuedNotifier

    notifier = QueuedNotifier()
    notifier._show("A", "a", 1)
    notifier._show("B", "b", 2)

    tray = MagicMock()
    notifier.init(tray)

    assert tray.showMessage.call_count == 2
    tray.showMessage.assert_any_call("A", "a", 1)
    tray.showMessage.assert_any_call("B", "b", 2)
    assert len(notifier._queue) == 0


def test_dnd_cache_prevents_repeated_dbus_calls():
    """The DND cache avoids calling dbus within the TTL window."""
    import bento_app.notify as notify_mod

    # Save original state and reset
    orig_cache = notify_mod._dnd_cache
    orig_time = notify_mod._dnd_cache_time
    try:
        notify_mod._dnd_cache = False
        notify_mod._dnd_cache_time = 0.0

        call_count = 0
        original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else None

        mock_dbus = MagicMock()
        mock_bus = MagicMock()
        mock_obj = MagicMock()
        mock_props = MagicMock()
        mock_dbus.SessionBus.return_value = mock_bus
        mock_bus.get_object.return_value = mock_obj
        mock_dbus.Interface.return_value = mock_props
        mock_props.Get.return_value = False

        fake_time = [100.0]

        with patch.object(notify_mod, "_dnd_cache", False), \
             patch.object(notify_mod, "_dnd_cache_time", 0.0), \
             patch("time.monotonic", side_effect=lambda: fake_time[0]), \
             patch.dict("sys.modules", {"dbus": mock_dbus}):

            # First call — should call dbus
            notify_mod._dnd_cache = False
            notify_mod._dnd_cache_time = 0.0
            result1 = notify_mod._is_dnd_active()
            dbus_call_count_1 = mock_props.Get.call_count

            # Second call at same time — should use cache (within TTL)
            result2 = notify_mod._is_dnd_active()
            dbus_call_count_2 = mock_props.Get.call_count

            assert dbus_call_count_2 == dbus_call_count_1, \
                "dbus should not be called again within TTL"

            # Advance time past TTL
            fake_time[0] = 200.0
            result3 = notify_mod._is_dnd_active()
            dbus_call_count_3 = mock_props.Get.call_count

            assert dbus_call_count_3 == dbus_call_count_1 + 1, \
                "dbus should be called again after TTL expires"
    finally:
        notify_mod._dnd_cache = orig_cache
        notify_mod._dnd_cache_time = orig_time
