"""Real Windows/ConPTY tests. Run on Windows with Git for Windows installed."""
import os
import queue
import sys
import tempfile
import threading
import time
import unittest

from gitbasher.config import find_bash


@unittest.skipUnless(sys.platform == "win32", "Requires Windows ConPTY")
class WindowsTests(unittest.TestCase):
    def test_persistent_shell_directory_environment_and_resize(self):
        from winpty import PtyProcess, Backend
        bash = find_bash()
        self.assertTrue(bash, "Install Git for Windows before running smoke tests")
        with tempfile.TemporaryDirectory(prefix="gitbasher space ") as folder:
            process = PtyProcess.spawn([bash, "--login", "-i"], cwd=folder,
                env=dict(os.environ, TERM="xterm-256color", CHERE_INVOKING="1"),
                dimensions=(24, 80), backend=Backend.ConPTY)
            output = queue.Queue()

            def reader():
                try:
                    while True:
                        output.put(process.read(4096))
                except (EOFError, OSError):
                    pass

            threading.Thread(target=reader, daemon=True).start()

            def wait_for(marker):
                text = ""
                deadline = time.monotonic() + 15
                while marker not in text and time.monotonic() < deadline:
                    try:
                        text += output.get(timeout=0.1)
                    except queue.Empty:
                        pass
                self.assertIn(marker, text)

            try:
                # Form markers from pieces so terminal echo cannot satisfy assertions.
                process.write("export GITBASHER_SMOKE=kept; printf 'READY%s' 123\r")
                wait_for("READY123")
                process.write("printf 'VALUE%s' \"$GITBASHER_SMOKE\"; [[ -d . ]] && printf 'DIR%s' OK\r")
                wait_for("VALUEkept")
                process.write("cd /; printf 'ROOT%s' \"$PWD\"\r")
                wait_for("ROOT/")
                process.write("printf 'STILL%s' \"$PWD\"\r")
                wait_for("STILL/")
                process.setwinsize(32, 110)
                process.write("printf 'SIZE%s:' OK; stty size\r")
                wait_for("32 110")
            finally:
                process.close(force=True)

    def test_local_terminal_loads_and_webchannel_is_ready(self):
        from PySide6.QtWidgets import QApplication
        from gitbasher.terminal import Terminal
        app = QApplication.instance() or QApplication([])
        terminal = Terminal()
        terminal.resize(900, 600)
        terminal.show()
        deadline = time.monotonic() + 20
        while not terminal.ready and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.01)
        try:
            self.assertTrue(terminal.ready, "Local xterm assets/WebChannel did not initialize")
            self.assertGreater(terminal.dimensions[0], 2)
            self.assertGreater(terminal.dimensions[1], 2)
        finally:
            terminal.stop()
            terminal.close()


if __name__ == "__main__":
    unittest.main()
