import copy
import unittest

from bashdock import config, terminal_preferences


class TerminalPreferenceTests(unittest.TestCase):
    def test_inactive_tab_tints_match_scrollbar_track_and_keep_extreme_themes_visible(self):
        settings = dict(terminal_preferences.defaults(), background='#341527', foreground='#f7ce63')
        self.assertEqual(dict(background='#402334', hover='#503645', foreground='#dab25a'),
                         terminal_preferences.inactive_tab_colors(settings))
        self.assertEqual('#1e222a', terminal_preferences.inactive_tab_colors(
            terminal_preferences.defaults())['background'])
        for background, foreground in (('#000000', '#ffffff'), ('#ffffff', '#000000')):
            colors = terminal_preferences.inactive_tab_colors(dict(background=background, foreground=foreground))
            self.assertNotEqual(background, colors['background'])
            self.assertNotEqual(colors['background'], colors['hover'])
            self.assertNotEqual(colors['background'], colors['foreground'])

    def test_tab_inheritance_and_custom_preferences_validate_including_saved_workspaces(self):
        defaults = dict(terminal_preferences.defaults(), font_size=22, background="#223344")
        tab = config.default_tab()
        self.assertEqual(defaults, terminal_preferences.effective(tab, defaults))
        tab["terminal"] = None
        self.assertEqual(defaults, terminal_preferences.effective(tab, defaults))
        custom = dict(terminal_preferences.defaults(), background="#331122")
        tab["terminal"] = custom
        self.assertEqual(custom, terminal_preferences.effective(tab, defaults))
        data = config.defaults()
        data["workspaces"] = [{"name": "Server", "tabs": [tab], "active_tab": 0}]
        config.validate(data)
        tab["terminal"]["font_size"] = 1000
        with self.assertRaises(ValueError):
            config.validate(data)

    def test_tab_editor_default_toggle_disables_controls_and_preserves_custom_draft(self):
        from PySide6.QtWidgets import QApplication
        from bashdock.terminal_settings import TerminalSettingsDialog
        app = QApplication.instance() or QApplication([])
        defaults = dict(terminal_preferences.defaults(), font_size=22, background="#223344")
        dialog = TerminalSettingsDialog(defaults, defaults=defaults, inherit=True)
        try:
            self.assertTrue(dialog.use_defaults.isChecked())
            self.assertFalse(dialog.controls.isEnabled())
            dialog.use_defaults.setChecked(False)
            dialog.size.setValue(28)
            dialog.set_color("background", "#331122")
            dialog.use_defaults.setChecked(True)
            self.assertEqual(defaults, dialog.values())
            dialog.use_defaults.setChecked(False)
            self.assertTrue(dialog.controls.isEnabled())
            self.assertEqual(28, dialog.values()["font_size"])
            self.assertEqual("#331122", dialog.values()["background"])
            dialog.restore_button.click()
            self.assertTrue(dialog.use_defaults.isChecked())
            dialog.reject()
            self.assertEqual("#223344", defaults["background"])
        finally:
            dialog.deleteLater()
            app.processEvents()

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
