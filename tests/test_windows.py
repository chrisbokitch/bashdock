"""Real Windows/ConPTY tests. Run on Windows with Git for Windows installed."""
import json
import os
import queue
import sys
import tempfile
import threading
import time
import unittest

from bashdock.config import find_bash
from bashdock.shell_integration import create_init_file


@unittest.skipUnless(sys.platform == "win32", "Requires Windows ConPTY")
class WindowsTests(unittest.TestCase):
    def test_first_button_waits_out_startup_input_probe_including_after_restart(self):
        from unittest.mock import patch
        from PySide6.QtWidgets import QApplication
        from bashdock.terminal import Terminal
        from bashdock import shell_backend

        app = QApplication.instance() or QApplication([])
        terminal = Terminal()
        terminal.resize(900, 600)
        terminal.show()
        output = []
        terminal.bridge.output.connect(output.append)

        def wait_for(predicate):
            deadline = time.monotonic() + 20
            while not predicate() and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(0.01)
            self.assertTrue(predicate(), repr(''.join(output)[-4000:]))

        def slow_init():
            init = create_init_file()
            # Simulate startup code probing terminal input. Sending a button
            # before this completes would lose the command's first character.
            init.write_text("IFS= read -r -t 0.4 -n 1 __bashdock_probe || :\n" +
                            init.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
            return init

        try:
            wait_for(lambda: terminal.ready)
            with tempfile.TemporaryDirectory(prefix="bashdock first button ") as folder:
                for attempt in range(2):
                    output.clear()
                    with patch.object(shell_backend, "create_init_file", side_effect=slow_init):
                        terminal.start(find_bash(), folder)
                    terminal.run_command("printf 'BUTTON_%s\\n' PRESERVED")
                    self.assertFalse(terminal.command_startup.ready)
                    self.assertEqual(1, len(terminal.command_startup.pending))
                    wait_for(lambda: "BUTTON_PRESERVED" in ''.join(output))
                    self.assertTrue(terminal.command_startup.ready)
                    self.assertEqual([], terminal.command_startup.pending)
                    self.assertNotIn("command not found", ''.join(output))
                    terminal.stop()
                    wait_for(lambda: not terminal.reader.is_alive())
        finally:
            terminal.stop()
            terminal.close()

    def test_command_button_uses_plain_input_with_real_xterm_bracketed_paste_enabled(self):
        from unittest.mock import Mock
        from PySide6.QtWidgets import QApplication
        from bashdock.terminal import Terminal

        app = QApplication.instance() or QApplication([])
        terminal = Terminal()
        terminal.resize(900, 600)
        terminal.show()

        def wait_for(predicate):
            deadline = time.monotonic() + 20
            while not predicate() and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(0.01)
            self.assertTrue(predicate(), "Timed out waiting for real xterm input")

        writes = []
        try:
            wait_for(lambda: terminal.ready)
            terminal.process = Mock()
            terminal.shell_ready(terminal.command_startup.begin())
            terminal.process.write.side_effect = writes.append
            # Simulate output enabling paste mode, as Readline does at a prompt.
            terminal.bridge.output.emit("\x1b[?2004h")
            modes = []

            def mode_ready():
                terminal.page().runJavaScript("terminal.modes.bracketedPasteMode", modes.append)
                return bool(modes and modes[-1] is True)

            wait_for(mode_ready)
            terminal.run_command("pwd")
            wait_for(lambda: bool(writes))
            self.assertEqual(["pwd\r"], writes)
            terminal.run_command("printf 'first\\n'\nprintf 'second\\n'")
            wait_for(lambda: len(writes) >= 2)
            self.assertEqual("printf 'first\\n'\rprintf 'second\\n'\r", writes[1])
            # Clipboard paste still uses xterm's active bracketed-paste behavior.
            terminal.bridge.clipboardPaste.emit("clipboard text")
            wait_for(lambda: len(writes) >= 3)
            self.assertEqual("\x1b[200~clipboard text\x1b[201~", writes[2])
        finally:
            terminal.stop()
            terminal.close()

    def test_persistent_shell_directory_environment_and_resize(self):
        from winpty import PtyProcess, Backend
        bash = find_bash()
        self.assertTrue(bash, "Install Git for Windows before running smoke tests")
        with tempfile.TemporaryDirectory(prefix="bashdock space ") as folder:
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
                process.write("export BASHDOCK_SMOKE=kept; printf 'READY%s' 123\r")
                wait_for("READY123")
                process.write("printf 'VALUE%s' \"$BASHDOCK_SMOKE\"; [[ -d . ]] && printf 'DIR%s' OK\r")
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
        from bashdock.terminal import Terminal
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
            # Verify the real WebChannel/xterm path, including live updates.
            from bashdock import terminal_preferences
            settings = dict(terminal_preferences.defaults(), font_size=21, cursor_style="bar",
                            background="#223344", scrollback=500)
            terminal.apply_settings(settings)
            observed = []
            expected = [21, "bar", "#223344", 500, "rgb(47, 63, 79)", "rgb(83, 96, 109)"]
            # Return a string across the Qt/Python boundary rather than relying
            # on conversion of a JavaScript array into a Python list.
            script = """(() => {
                try {
                    const viewport = document.querySelector('.xterm-viewport');
                    return JSON.stringify([terminal.options.fontSize, terminal.options.cursorStyle,
                        terminal.options.theme.background, terminal.options.scrollback,
                        getComputedStyle(viewport, '::-webkit-scrollbar-track').backgroundColor,
                        getComputedStyle(viewport, '::-webkit-scrollbar-thumb').backgroundColor]);
                } catch (error) {
                    return JSON.stringify({error: String(error)});
                }
            })()"""

            def receive(value):
                try:
                    observed.append(json.loads(value))
                except (TypeError, ValueError):
                    observed.append({"invalid_result": repr(value)})

            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                terminal.page().runJavaScript(script, receive)
                until = time.monotonic() + 0.1
                while time.monotonic() < until:
                    app.processEvents()
                    time.sleep(0.005)
                if observed and observed[-1] == expected:
                    break
            self.assertTrue(observed)
            self.assertEqual(expected, observed[-1])
        finally:
            terminal.stop()
            terminal.close()

    def test_terminal_reports_actual_working_directory_after_cd(self):
        from PySide6.QtWidgets import QApplication
        from bashdock.terminal import Terminal
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
            with tempfile.TemporaryDirectory(prefix="bashdock cwd ") as folder:
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
        from bashdock.terminal import Terminal
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
                const viewport = document.querySelector('.xterm-viewport').getBoundingClientRect();
                return {bottom:r.bottom,right:r.right,viewportBottom:viewport.bottom,height:innerHeight,width:innerWidth,
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
                self.assertAlmostEqual(bounds["viewportBottom"], bounds["height"] - 12, delta=1,
                                       msg="Scrollbar bottom inset must match the terminal frame")
        finally:
            terminal.stop()
            terminal.close()


if __name__ == "__main__":
    unittest.main()
