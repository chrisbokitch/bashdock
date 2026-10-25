import ctypes
import os
import sys
import unittest
from unittest.mock import Mock, patch

from bashdock import window_theme

if sys.platform != "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class WindowThemeTests(unittest.TestCase):
    def test_dialogs_and_pickers_receive_theme_on_every_show_without_theming_children(self):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (QApplication, QDialog, QMessageBox, QInputDialog,
                                       QFileDialog, QColorDialog, QWidget)

        app = QApplication.instance() or QApplication([])
        original_filter = getattr(app, "_bashdock_titlebar_theme", None)
        original_native = app.testAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
        windows = [QDialog(), QMessageBox(), QInputDialog(), QFileDialog(), QColorDialog()]
        child = QWidget(windows[0])
        tooltip = QWidget(None, Qt.WindowType.ToolTip)
        try:
            with patch.object(window_theme.sys, "platform", "win32"), \
                    patch.object(window_theme, "apply_titlebar") as apply:
                window_theme.install_titlebar_theme(app)
                theme = app._bashdock_titlebar_theme
                window_theme.install_titlebar_theme(app)
                self.assertIs(theme, app._bashdock_titlebar_theme)
                self.assertTrue(app.testAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs))
                for window in windows:
                    window.show()
                    app.processEvents()
                    self.assertIn(int(window.winId()), [c.args[0] for c in apply.call_args_list])
                self.assertFalse(child.isWindow())
                tooltip.show()
                app.processEvents()
                self.assertNotIn(int(tooltip.winId()), [c.args[0] for c in apply.call_args_list])
                apply.reset_mock()
                windows[0].hide()
                windows[0].show()
                app.processEvents()
                apply.assert_called_once_with(int(windows[0].winId()))
        finally:
            for window in windows + [tooltip]:
                window.close()
                window.deleteLater()
            if original_filter is None and hasattr(app, "_bashdock_titlebar_theme"):
                app.removeEventFilter(app._bashdock_titlebar_theme)
                app._bashdock_titlebar_theme.deleteLater()
                del app._bashdock_titlebar_theme
            app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, original_native)
            app.processEvents()

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
