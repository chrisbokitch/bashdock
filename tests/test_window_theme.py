import ctypes
import unittest
from unittest.mock import Mock, patch

from gitbasher import window_theme


class WindowThemeTests(unittest.TestCase):
    def test_windows_caption_uses_app_colors_with_four_byte_payloads(self):
        values = []

        def apply(hwnd, attribute, pointer, size):
            values.append((hwnd, attribute, ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32)).contents.value, size))
            return 0

        library = Mock()
        library.DwmSetWindowAttribute.side_effect = apply
        with patch.object(window_theme.sys, "platform", "win32"), \
                patch.object(window_theme.ctypes, "WinDLL", return_value=library, create=True):
            self.assertTrue(window_theme.apply_titlebar(123))
        self.assertEqual([(123, 20, 1, 4), (123, 35, 0x291e18, 4), (123, 36, 0xefe4dd, 4)], values)

    def test_older_windows_can_use_dark_mode_without_custom_caption_colors(self):
        library = Mock()
        library.DwmSetWindowAttribute.side_effect = [0, -1, -1]
        with patch.object(window_theme.sys, "platform", "win32"), \
                patch.object(window_theme.ctypes, "WinDLL", return_value=library, create=True):
            self.assertTrue(window_theme.apply_titlebar(123))

    def test_missing_api_and_other_platforms_leave_native_frame_unchanged(self):
        with patch.object(window_theme.sys, "platform", "win32"), \
                patch.object(window_theme.ctypes, "WinDLL", side_effect=OSError("unavailable"), create=True):
            self.assertFalse(window_theme.apply_titlebar(123))
        with patch.object(window_theme.sys, "platform", "linux"):
            self.assertFalse(window_theme.apply_titlebar(123))
