import copy
import unittest

from bashdock import config, terminal_preferences


class TerminalPreferenceTests(unittest.TestCase):
    def test_old_workspaces_gain_defaults_without_changing_tabs_or_input(self):
        data = config.defaults()
        del data["terminal"]
        original = copy.deepcopy(data)
        migrated = config.migrate(data)
        self.assertEqual(terminal_preferences.defaults(), migrated["terminal"])
        self.assertEqual(original, data)
        self.assertEqual(data["tabs"], migrated["tabs"])
        partial = config.migrate(dict(data, terminal={"font_size": 19}))
        self.assertEqual(19, partial["terminal"]["font_size"])
        self.assertEqual(10000, partial["terminal"]["scrollback"])

    def test_invalid_preferences_are_rejected_before_storage_or_bridge(self):
        invalid = [("font_size", True), ("font_size", 0), ("font_size", 49),
                   ("font_family", ""), ("font_family", "bad\nfont"),
                   ("background", "red"), ("cursor_color", "#gggggg"),
                   ("scrollback", -1), ("scrollback", 100001),
                   ("cursor_style", "triangle"), ("cursor_blink", "false"),
                   ("copy_on_select", 1), ("right_click_paste", None)]
        for key, value in invalid:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                config.validate(dict(config.defaults(), terminal={key: value}))
        with self.assertRaises(ValueError):
            config.migrate(dict(config.defaults(), terminal=[]))

    def test_dialog_defaults_are_staged_until_accepted(self):
        from PySide6.QtWidgets import QApplication, QDialogButtonBox
        from bashdock.terminal_settings import TerminalSettingsDialog
        app = QApplication.instance() or QApplication([])
        original = dict(terminal_preferences.defaults(), font_size=24, right_click_paste=True)
        dialog = TerminalSettingsDialog(original)
        try:
            self.assertEqual(original, dialog.values())
            buttons = dialog.findChild(QDialogButtonBox)
            buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).click()
            self.assertEqual(terminal_preferences.defaults(), dialog.values())
            self.assertEqual(24, original["font_size"])
            buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
            self.assertEqual(0, dialog.result())
        finally:
            dialog.deleteLater()
            app.processEvents()
