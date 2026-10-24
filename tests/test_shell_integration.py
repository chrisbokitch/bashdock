import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from gitbasher.shell_integration import INIT_SCRIPT, create_init_file, valid_reported_directory


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

    @unittest.skipUnless(os.name == "posix" and shutil.which("bash"), "Requires POSIX Bash for isolated hook test")
    def test_hook_preserves_user_prompt_commands_and_reports_new_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / ".bash_profile").write_text("PROMPT_COMMAND=('printf USER_HOOK')\n")
            rc = root / "init.bash"
            # Don't load the host's system profile in an isolated test.
            rc.write_text(INIT_SCRIPT.replace("source /etc/profile", ":"))
            result = subprocess.run(["bash", "--noprofile", "--rcfile", str(rc), "-ic",
                'cd /; for hook in "${PROMPT_COMMAND[@]}"; do eval "$hook"; done'],
                env=dict(os.environ, HOME=folder), capture_output=True, text=True, timeout=10)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("USER_HOOK", result.stdout)
            self.assertIn("\x1b]777;gitbasher-cwd;/\x07", result.stdout)
