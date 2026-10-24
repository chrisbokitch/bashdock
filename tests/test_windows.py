"""Real Windows/ConPTY tests. Run on Windows with Git for Windows installed."""
import json
import os
import queue
import sys
import tempfile
import threading
import time
import unittest

from gitbasher.config import find_bash
from gitbasher.shell_integration import create_init_file


@unittest.skipUnless(sys.platform == "win32", "Requires Windows ConPTY")
class WindowsTests(unittest.TestCase):
    def test_persistent_shell_directory_environment_and_resize(self):
        from winpty import PtyProcess, Backend
        bash = find_bash()
        self.assertTrue(bash, "Install Git for Windows before running smoke tests")
        with tempfile.TemporaryDirectory(prefix="gitbasher space ") as folder:
            init_file = create_init_file()
            self.addCleanup(lambda: init_file.unlink(missing_ok=True))
            process = PtyProcess.spawn([bash, "--rcfile", init_file.as_posix(), "-i"], cwd=folder,
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

    def test_terminal_reports_actual_working_directory_after_cd(self):
        from PySide6.QtWidgets import QApplication
        from gitbasher.terminal import Terminal
        app = QApplication.instance() or QApplication([])
        terminal = Terminal()
        terminal.resize(900, 600)
        terminal.show()
        directories = []
        terminal.directory_changed.connect(directories.append)

        def wait_for(predicate):
            deadline = time.monotonic() + 20
            while not predicate() and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(0.01)
            self.assertTrue(predicate(), f"Timed out; reported folders: {directories}")

        try:
            wait_for(lambda: terminal.ready)
            with tempfile.TemporaryDirectory(prefix="gitbasher cwd ") as folder:
                terminal.start(find_bash(), folder)
                wait_for(lambda: bool(directories))
                self.assertEqual(os.path.normcase(os.path.normpath(folder)),
                                 os.path.normcase(os.path.normpath(directories[-1])))
                target = os.path.join(folder, "child with spaces")
                os.mkdir(target)
                terminal.run_command("cd 'child with spaces'")
                wait_for(lambda: os.path.normcase(os.path.normpath(directories[-1])) ==
                                os.path.normcase(os.path.normpath(target)))
                terminal.stop()
        finally:
            terminal.stop()
            terminal.close()

    def test_terminal_rows_fit_inside_view_after_resize(self):
        from PySide6.QtWidgets import QApplication
        from gitbasher.terminal import Terminal
        app = QApplication.instance() or QApplication([])
        terminal = Terminal()
        terminal.show()

        def evaluate(script):
            results = []
            terminal.page().runJavaScript(script, results.append)
            deadline = time.monotonic() + 10
            while not results and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(0.01)
            self.assertTrue(results, "Timed out measuring terminal layout")
            return results[0]

        try:
            deadline = time.monotonic() + 20
            while not terminal.ready and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(0.01)
            self.assertTrue(terminal.ready)
            geometry = """JSON.stringify((() => {
                const r = document.querySelector('.xterm-screen').getBoundingClientRect();
                const proposed = fit.proposeDimensions();
                return {bottom:r.bottom,right:r.right,height:innerHeight,width:innerWidth,
                    fitted:terminal.rows === proposed.rows && terminal.cols === proposed.cols};
            })())"""
            for width, height in ((900, 600), (713, 419), (1040, 701)):
                terminal.resize(width, height)
                deadline = time.monotonic() + 10
                while True:
                    app.processEvents()
                    bounds = json.loads(evaluate(geometry))
                    if (abs(bounds["width"] - width) <= 1 and
                            abs(bounds["height"] - height) <= 1 and bounds["fitted"]):
                        break
                    self.assertLess(time.monotonic(), deadline, "Terminal did not finish resizing")
                    time.sleep(0.01)
                self.assertLessEqual(bounds["bottom"], bounds["height"] - 12 + 1, bounds)
                self.assertLessEqual(bounds["right"], bounds["width"] - 12 + 1, bounds)
        finally:
            terminal.stop()
            terminal.close()


if __name__ == "__main__":
    unittest.main()
