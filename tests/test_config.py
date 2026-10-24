import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gitbasher import config


class ConfigTests(unittest.TestCase):
    def test_roundtrip_preserves_unicode_order_and_multiline_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested/settings.json"
            data = config.defaults()
            data["tabs"][0]["buttons"] = [{"label": "Dévelop", "command": "cd '/c/Development/my repo'\ngit status"},
                               {"label": "Next", "command": "printf '%s' '$HOME'"}]
            config.save(data, path)
            self.assertEqual(data, config.load(path))

    def test_replace_failure_preserves_existing_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            config.save(config.defaults(), path)
            original = path.read_bytes()
            changed = config.defaults()
            changed["tabs"][0]["buttons"] = []
            with patch("gitbasher.config.os.replace", side_effect=PermissionError("locked")):
                with self.assertRaises(PermissionError):
                    config.save(changed, path)
            self.assertEqual(original, path.read_bytes())
            self.assertEqual([path], list(path.parent.iterdir()))

    def test_invalid_settings_do_not_get_overwritten_on_read(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text('{"buttons": 42}', encoding="utf-8")
            original = path.read_bytes()
            with self.assertRaises(ValueError):
                config.load(path)
            self.assertEqual(original, path.read_bytes())

    def test_rejects_embedded_terminal_controls_but_allows_bash_syntax(self):
        for command in ("pwd\x03", "\x1b[31m", "echo\x00bad"):
            data = config.defaults()
            data["tabs"][0]["buttons"][0]["command"] = command
            with self.assertRaises(ValueError):
                config.validate(data)
        data["tabs"][0]["buttons"][0]["command"] = "export NAME='a b'\nprintf '%s\\n' \"$NAME\""
        config.validate(data)

    def test_migrates_original_single_shell_without_modifying_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            old = {"bash_path": "C:/Git/bin/bash.exe", "startup_folder": "C:/Development",
                   "buttons": [{"label": "Tests", "command": "python -m unittest"}]}
            path.write_text(json.dumps(old), encoding="utf-8")
            data = config.load(path)
            self.assertEqual(old["buttons"], data["tabs"][0]["buttons"])
            self.assertEqual(old["startup_folder"], data["tabs"][0]["current_folder"])
            self.assertEqual(old, json.loads(path.read_text()))
            config.save(data, path)
            self.assertEqual(data, config.load(path))

    def test_workspace_roundtrip_and_independent_default_button_lists(self):
        data = config.defaults()
        data["tabs"].append(config.default_tab("Build"))
        data["active_tab"] = 1
        data["tabs"][1]["current_folder"] = "C:/Development/build"
        data["tabs"][1]["buttons"][0]["command"] = "make"
        self.assertNotEqual(data["tabs"][0]["buttons"], data["tabs"][1]["buttons"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            config.save(data, path)
            self.assertEqual(data, config.load(path))

    def test_invalid_tab_and_future_version_are_rejected(self):
        for key, value in (("version", 999), ("tabs", []), ("active_tab", -1), ("active_tab", True)):
            data = config.defaults()
            data[key] = value
            with self.assertRaises(ValueError):
                config.validate(data)


if __name__ == "__main__":
    unittest.main()
