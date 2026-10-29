"""Zoom uses transient terminal state, leaving saved preferences independent."""
import json
import os
import sys

if sys.platform != 'win32':
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from bashdock.terminal import Terminal
from qt_lifecycle import GuiTestCase


class FontZoomTests(GuiTestCase):
    def test_independent_zoom_limits_reset_and_late_settings_request(self):
        first, second = Terminal(), Terminal()
        first.apply_settings(dict(first.preferences, font_size=22))
        messages = []
        first.bridge.settingsChanged.connect(lambda data: messages.append(json.loads(data)))
        first.zoom_font(1)
        first.bridge.requestSettings()  # A late renderer must get the zoomed size too.
        self.assertEqual([23, 23], [m['font_size'] for m in messages])
        self.assertEqual(22, first.preferences['font_size'])
        self.assertEqual(15, second.display_preferences()['font_size'])
        for _ in range(60):
            first.zoom_font(1)
        self.assertEqual(48, first.display_preferences()['font_size'])
        first.zoom_font(-1)
        self.assertEqual(47, first.display_preferences()['font_size'])
        for _ in range(60):
            first.zoom_font(-1)
        self.assertEqual(8, first.display_preferences()['font_size'])
        first.zoom_font(1)
        self.assertEqual(9, first.display_preferences()['font_size'])
        first.zoom_font(0)
        self.assertEqual(22, first.display_preferences()['font_size'])
        first.zoom_font(100)
        self.assertEqual(22, first.display_preferences()['font_size'])
        first.timer.stop()
        second.timer.stop()

    def test_saving_preferences_resets_temporary_zoom_without_restarting_shell(self):
        terminal = Terminal()
        sentinel = object()
        terminal.process = sentinel
        original = dict(terminal.preferences)
        terminal.zoom_font(1)
        terminal.apply_settings(dict(original, font_size=18, background='#223344'))
        self.assertEqual(18, terminal.display_preferences()['font_size'])
        self.assertEqual('#223344', terminal.display_preferences()['background'])
        self.assertIs(sentinel, terminal.process)
        terminal.process = None
        terminal.timer.stop()
