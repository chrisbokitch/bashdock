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
            data["buttons"] = [{"label": "Dévelop", "command": "cd '/c/Development/my repo'\ngit status"},
                               {"label": "Next", "command": "printf '%s' '$HOME'"}]
            config.save(data, path)
            self.assertEqual(data, config.load(path))

    def test_replace_failure_preserves_existing_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            config.save(config.defaults(), path)
            original = path.read_bytes()
            changed = config.defaults()
            changed["buttons"] = []
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
            data["buttons"][0]["command"] = command
            with self.assertRaises(ValueError):
                config.validate(data)
        data["buttons"][0]["command"] = "export NAME='a b'\nprintf '%s\\n' \"$NAME\""
        config.validate(data)


if __name__ == "__main__":
    unittest.main()
