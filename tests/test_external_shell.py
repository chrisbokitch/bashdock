import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock, call

from bashdock import external_shell


class ExternalShellTests(unittest.TestCase):
    def test_packaged_launch_restores_dll_lookup_even_when_process_creation_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            bash = Path(temp) / "bash.exe"
            bash.touch()
            runtime = str(Path(temp) / "_internal")
            dll = Mock()
            dll.SetDllDirectoryW.return_value = 1
            with patch.object(external_shell.sys, "platform", "win32"), \
                    patch.object(external_shell.sys, "_MEIPASS", runtime, create=True), \
                    patch.object(external_shell.ctypes, "WinDLL", return_value=dll, create=True), \
                    patch.dict(external_shell.os.environ, {"PATH": runtime + external_shell.os.pathsep + temp}), \
                    patch.object(external_shell.subprocess, "Popen", side_effect=OSError("locked")) as launch:
                with self.assertRaisesRegex(OSError, "locked"):
                    external_shell.open_external(str(bash), temp)
            self.assertEqual([call(None), call(runtime)], dll.SetDllDirectoryW.call_args_list)
            self.assertEqual(temp, launch.call_args.kwargs["env"]["PATH"])

    def test_launcher_comes_from_selected_install_and_paths_are_single_arguments(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Git with spaces"
            folder = Path(temp) / "Project & café"
            folder.mkdir()
            launcher = root / "git-bash.exe"
            for sub in ("bin", "usr/bin"):
                bash = root / sub / "bash.exe"
                bash.parent.mkdir(parents=True, exist_ok=True)
                bash.touch()
                launcher.touch()
                with patch.object(external_shell.sys, "platform", "win32"), \
                        patch.object(external_shell.subprocess, "Popen") as launch:
                    external_shell.open_external(str(bash), str(folder))
                args, options = launch.call_args
                self.assertEqual([str(launcher), f"--cd={folder.as_posix()}"], args[0])
                self.assertEqual(str(folder), options["cwd"])
                self.assertEqual(0x208, options["creationflags"])
                self.assertTrue(options["close_fds"])
                self.assertEqual("1", options["env"]["CHERE_INVOKING"])
                self.assertNotIn("shell", options)

    def test_missing_launcher_uses_configured_bash_in_an_interactive_new_console(self):
        with tempfile.TemporaryDirectory() as temp:
            bash = Path(temp) / "bash.exe"
            bash.touch()
            with patch.object(external_shell.sys, "platform", "win32"), \
                    patch.object(external_shell.subprocess, "Popen") as launch:
                external_shell.open_external(str(bash), temp)
            args, options = launch.call_args
            self.assertEqual([str(bash), "--login", "-i"], args[0])
            self.assertEqual(0x210, options["creationflags"])
            for stream in ("stdin", "stdout", "stderr"):
                self.assertNotIn(stream, options)

    def test_missing_directory_or_bash_does_not_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            bash = Path(temp) / "bash.exe"
            bash.touch()
            with patch.object(external_shell.sys, "platform", "win32"), \
                    patch.object(external_shell.subprocess, "Popen") as launch:
                with self.assertRaises(ValueError):
                    external_shell.open_external(str(bash), str(Path(temp) / "missing"))
                with self.assertRaises(ValueError):
                    external_shell.open_external(str(Path(temp) / "missing.exe"), temp)
                launch.assert_not_called()
