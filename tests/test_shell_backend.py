import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from gitbasher import shell_backend, packaged_smoke, config


class BackendTests(unittest.TestCase):
    def test_frozen_startup_requires_native_helpers_and_cleans_failed_init(self):
        with tempfile.TemporaryDirectory() as folder:
            fake = types.ModuleType("winpty")
            fake.__file__ = str(Path(folder) / "__init__.py")
            fake.PtyProcess = Mock()
            fake.Backend = types.SimpleNamespace(ConPTY=0)
            with patch.dict(sys.modules, winpty=fake), \
                    patch.object(shell_backend.sys, "platform", "win32"), \
                    patch.object(shell_backend.sys, "frozen", True, create=True):
                with self.assertRaisesRegex(RuntimeError, "OpenConsole.exe"):
                    shell_backend.spawn_shell("bash.exe", folder, (24, 80))
                fake.PtyProcess.spawn.assert_not_called()
                for name in ("conpty.dll", "OpenConsole.exe"):
                    (Path(folder) / name).touch()
                init = Path(folder) / "init.bash"
                init.touch()
                fake.PtyProcess.spawn.side_effect = OSError("Cannot start backend")
                with patch.object(shell_backend, "create_init_file", return_value=init):
                    with self.assertRaisesRegex(OSError, "Cannot start backend"):
                        shell_backend.spawn_shell("bash.exe", folder, (24, 80))
                self.assertFalse(init.exists())

    def test_spawn_preserves_arguments_and_uses_usable_startup_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            fake = types.ModuleType("winpty")
            fake.PtyProcess = Mock()
            fake.Backend = types.SimpleNamespace(ConPTY=0)
            with patch.dict(sys.modules, winpty=fake), \
                    patch.object(shell_backend.sys, "platform", "win32"), \
                    patch.object(shell_backend.sys, "frozen", False, create=True):
                process, init = shell_backend.spawn_shell("C:/Git/bin/bash.exe", folder, (30, 100))
                try:
                    self.assertIs(process, fake.PtyProcess.spawn.return_value)
                    args, kwargs = fake.PtyProcess.spawn.call_args
                    self.assertEqual(["C:/Git/bin/bash.exe", "--rcfile", init.as_posix(), "-i"], args[0])
                    self.assertEqual(folder, kwargs["cwd"])
                    self.assertEqual((30, 100), kwargs["dimensions"])
                    self.assertEqual(Path(folder).as_posix(), kwargs["env"]["GITBASHER_START_DIR"])
                finally:
                    init.unlink()

    def test_packaged_smoke_requires_actual_command_output_not_echo(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "report.json"
            init = Path(folder) / "init.bash"
            init.touch()
            process = Mock()
            process.read.side_effect = ["echo of command", "GITBASHER_PACKAGED_", "SHELL_READY"]
            settings = config.defaults()
            settings["bash_path"] = "bash.exe"
            with patch.object(packaged_smoke.config, "load", return_value=settings), \
                    patch.object(packaged_smoke, "spawn_shell", return_value=(process, init)):
                self.assertEqual(0, packaged_smoke.run(report, timeout=2))
            self.assertTrue(json.loads(report.read_text())["ok"])
            process.close.assert_called_once_with(force=True)
            self.assertFalse(init.exists())

    def test_packaged_smoke_reports_startup_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "report.json"
            with patch.object(packaged_smoke.config, "load", return_value=config.defaults()), \
                    patch.object(packaged_smoke.config, "find_bash", return_value="bash.exe"), \
                    patch.object(packaged_smoke, "spawn_shell", side_effect=OSError("missing helper")):
                self.assertEqual(1, packaged_smoke.run(report, timeout=2))
            self.assertIn("missing helper", json.loads(report.read_text())["error"])
