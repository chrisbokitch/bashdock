import tempfile
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch, Mock, call

from bashdock import external_shell


class ExternalShellTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'win32', 'Needs Git Bash on Windows')
    def test_temporary_git_bash_executes_command_and_exit_line(self):
        from bashdock.config import find_bash
        bash = find_bash()
        # If the external terminal hangs, preserve the assertion that explains
        # the failure instead of replacing it with a Windows cleanup error.
        with tempfile.TemporaryDirectory(prefix='bashdock external ', ignore_cleanup_errors=True) as temp:
            receipt = Path(temp) / 'command receipt.txt'
            cmd_receipt = Path(temp) / 'cmd receipt.txt'
            command = ("printf '%s' 'external Bash ran' > 'command receipt.txt'\n"
                       "cmd.exe //c echo cmd-ran > 'cmd receipt.txt'\nexit")
            process = external_shell.open_external(bash, temp, command=command)
            deadline = time.monotonic() + 15
            while not (receipt.is_file() and cmd_receipt.is_file()) and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertEqual('external Bash ran', receipt.read_text(encoding='utf-8'))
            process.wait(timeout=15)
            self.assertEqual('cmd-ran', cmd_receipt.read_text(encoding='utf-8').strip())
            receipt.unlink()
            cmd_receipt.unlink()
            # Windows cannot remove a process's current directory until the
            # Git Bash window has actually closed, even after it wrote output.
            deadline = time.monotonic() + 15
            while True:
                try:
                    Path(temp).rmdir()
                    break
                except PermissionError:
                    if time.monotonic() >= deadline:
                        self.fail('Temporary Git Bash window did not close after exit')
                    time.sleep(0.1)

    def test_temporary_command_passes_literal_text_to_mintty_and_bash(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'Git with spaces'
            bash = root / 'bin' / 'bash.exe'
            bash.parent.mkdir(parents=True)
            bash.touch()
            (root / 'git-bash.exe').touch()
            mintty = root / 'usr' / 'bin' / 'mintty.exe'
            mintty.parent.mkdir(parents=True)
            mintty.touch()
            folder = Path(temp) / 'Project & café'
            folder.mkdir()
            command = 'cmd.exe //c start "" "https://example.com/?a=1&b=2"'
            with patch.object(external_shell.sys, 'platform', 'win32'), \
                    patch.object(external_shell.subprocess, 'Popen') as launch:
                external_shell.open_external(str(bash), str(folder), command=command)
            args, options = launch.call_args
            self.assertEqual([str(mintty), '--hold=never', '--exec', str(bash),
                              '--login', '-i', '-c', command], args[0])
            self.assertEqual(str(folder), options['cwd'])
            self.assertEqual(0x208, options['creationflags'])
            for stream in ('stdin', 'stdout', 'stderr'):
                self.assertEqual(external_shell.subprocess.DEVNULL, options[stream])
            self.assertNotIn('shell', options)

    def test_temporary_command_falls_back_to_new_console_without_git_bash_launcher(self):
        with tempfile.TemporaryDirectory() as temp:
            bash = Path(temp) / 'bash.exe'
            bash.touch()
            with patch.object(external_shell.sys, 'platform', 'win32'), \
                    patch.object(external_shell.subprocess, 'Popen') as launch:
                external_shell.open_external(str(bash), temp, command='printf done')
            args, options = launch.call_args
            self.assertEqual([str(bash), '--login', '-i', '-c', 'printf done'], args[0])
            self.assertEqual(0x210, options['creationflags'])

    def test_m8_packaged_success_removes_only_runtime_paths_and_restores_parent_dll_lookup(self):
        import os

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bash = root / 'Git' / 'bin' / 'bash.exe'
            bash.parent.mkdir(parents=True)
            bash.touch()
            (root / 'Git' / 'git-bash.exe').touch()
            runtime = root / '_internal'
            retained = root / '_internal-other'
            original_path = os.pathsep.join(map(str, (runtime, runtime / 'Qt' / 'bin', retained, root)))
            dll = Mock()
            dll.SetDllDirectoryW.return_value = 1

            def launch(arguments, **options):
                self.assertEqual([call(None)], dll.SetDllDirectoryW.call_args_list)
                self.assertEqual(os.pathsep.join(map(str, (retained, root))), options['env']['PATH'])
                self.assertEqual('1', options['env']['CHERE_INVOKING'])
                for stream in ('stdin', 'stdout', 'stderr'):
                    self.assertEqual(external_shell.subprocess.DEVNULL, options[stream])
                self.assertEqual(0x208, options['creationflags'])
                self.assertTrue(options['close_fds'])

            with patch.object(external_shell.sys, 'platform', 'win32'), \
                    patch.object(external_shell.sys, '_MEIPASS', str(runtime), create=True), \
                    patch.object(external_shell.ctypes, 'WinDLL', return_value=dll, create=True), \
                    patch.dict(os.environ, PATH=original_path, CHERE_INVOKING='original'), \
                    patch.object(external_shell.subprocess, 'Popen', side_effect=launch) as popen:
                external_shell.open_external(str(bash), temp)
                popen.assert_called_once()
                self.assertEqual(original_path, os.environ['PATH'])
                self.assertEqual('original', os.environ['CHERE_INVOKING'])
            self.assertEqual([call(None), call(str(runtime))], dll.SetDllDirectoryW.call_args_list)

    def test_m8_failed_dll_reset_aborts_external_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            bash = Path(temp) / 'bash.exe'
            bash.touch()
            dll = Mock()
            dll.SetDllDirectoryW.return_value = 0
            with patch.object(external_shell.sys, 'platform', 'win32'), \
                    patch.object(external_shell.sys, '_MEIPASS', temp, create=True), \
                    patch.object(external_shell.ctypes, 'WinDLL', return_value=dll, create=True), \
                    patch.object(external_shell.subprocess, 'Popen') as launch:
                with self.assertRaisesRegex(OSError, 'DLL search path'):
                    external_shell.open_external(str(bash), temp)
                launch.assert_not_called()
                dll.SetDllDirectoryW.assert_called_once_with(None)

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
