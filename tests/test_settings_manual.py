"""The manual launcher must confine damaged-settings tests to its empty profile."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from bashdock import config
from scripts.check_settings_manual import DAMAGED, exercise


class SettingsManualTests(unittest.TestCase):
    def test_m7_launcher_isolates_appdata_and_checks_cancel_restore_without_touching_normal_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            normal, disposable = root / 'normal', root / 'disposable'
            original = normal / 'bashdock' / 'settings.json'
            config.save(config.defaults(), original)
            before = original.read_bytes()
            calls = []

            def launch(arguments, *, env, cwd, check):
                self.assertEqual(str(disposable), env['APPDATA'])
                self.assertEqual(str(root), cwd)
                self.assertEqual([str(root / 'bashdock.exe')], arguments)
                self.assertFalse(check)
                path = Path(env['APPDATA']) / 'bashdock' / 'settings.json'
                calls.append(arguments)
                if len(calls) == 1:
                    config.save(config.defaults(), path)
                elif len(calls) == 2:
                    self.assertEqual(DAMAGED, path.read_bytes())
                else:
                    config.save(config.read(config.backup_path(path)), path)
                return subprocess.CompletedProcess(arguments, 0)

            with patch.dict(os.environ, APPDATA=str(normal)), patch('builtins.print'):
                exercise(root / 'bashdock.exe', disposable, launch=launch)
                self.assertEqual(str(normal), os.environ['APPDATA'])
            self.assertEqual(3, len(calls))
            self.assertEqual(before, original.read_bytes())

    def test_m7_launcher_refuses_existing_profile_or_invalid_backup_before_damaging_any_file(self):
        with tempfile.TemporaryDirectory() as folder, patch('builtins.print'):
            root = Path(folder)
            existing = root / 'existing'
            existing.mkdir()
            sentinel = existing / 'keep.txt'
            sentinel.write_text('keep')
            with self.assertRaises(ValueError):
                exercise(root / 'bashdock.exe', existing, launch=lambda *a, **k: self.fail('Must not launch'))
            self.assertEqual('keep', sentinel.read_text())
            disposable = root / 'disposable'
            path = disposable / 'bashdock' / 'settings.json'
            before = []

            def invalid_backup(arguments, **kwargs):
                config.save(config.defaults(), path)
                before.append(path.read_bytes())
                config.backup_path(path).write_bytes(b'invalid backup')
                return subprocess.CompletedProcess(arguments, 0)

            with self.assertRaises(ValueError):
                exercise(root / 'bashdock.exe', disposable, launch=invalid_backup)
            self.assertEqual(before[0], path.read_bytes())
