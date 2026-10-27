import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from bashdock.shell_integration import INIT_SCRIPT, create_init_file, valid_reported_directory
from bashdock.config import find_bash

BASH = find_bash() if os.name == "nt" else shutil.which("bash")


class ShellIntegrationTests(unittest.TestCase):
    def test_reported_paths_must_be_absolute_windows_paths(self):
        for value in ("C:/Development/a b", "D:\\répo\\test", "//server/share/path"):
            self.assertTrue(valid_reported_directory(value), value)
        for value in ("relative", "/c/project", "C:relative", "C:/bad\x1bpath", ""):
            self.assertFalse(valid_reported_directory(value), value)

    def test_private_init_script_has_lf_line_endings(self):
        path = create_init_file()
        try:
            self.assertNotIn(b"\r", path.read_bytes())
            self.assertIn(b"PROMPT_COMMAND+=", path.read_bytes())
        finally:
            path.unlink()

    @unittest.skipUnless(BASH, "Requires Bash (Git for Windows on Windows)")
    def test_hook_preserves_user_prompt_commands_and_reports_new_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "child").mkdir()
            (root / ".bash_profile").write_text("PROMPT_COMMAND=('printf USER_HOOK')\n")
            rc = root / "init.bash"
            # Don't load the host's system profile in an isolated test.
            rc.write_text(INIT_SCRIPT.replace("source /etc/profile", ":"))
            result = subprocess.run([BASH, "--noprofile", "--rcfile", rc.as_posix(), "-ic",
                'cd -- "$HOME/child"; for i in 1 2; do for hook in "${PROMPT_COMMAND[@]}"; do eval "$hook"; done; done'],
                env=dict(os.environ, HOME=root.as_posix(), BASHDOCK_SESSION="session-test"), capture_output=True, text=True,
                encoding="utf-8", timeout=10)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("USER_HOOK", result.stdout)
            self.assertEqual(1, result.stdout.count("\x1b]777;bashdock-ready;session-test\x07"))
            self.assertIn(f"\x1b]777;bashdock-cwd;{(root / 'child').as_posix()}\x07", result.stdout)
