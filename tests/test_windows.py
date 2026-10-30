"""Real Windows/ConPTY tests. Run on Windows with Git for Windows installed."""
import json
import os
import queue
import shlex
import sys
import tempfile
import threading
import time
import unittest
import warnings
from contextlib import contextmanager
from pathlib import Path

from bashdock.config import find_bash
from bashdock.shell_integration import create_init_file
from qt_lifecycle import GuiTestCase


@unittest.skipUnless(sys.platform == "win32", "Requires Windows ConPTY")
class WindowsTests(GuiTestCase):
    def setUp(self):
        super().setUp()
        from unittest.mock import patch
        from webengine_diagnostics import DiagnosticPage
        self._pages = patch('bashdock.terminal.LocalPage', DiagnosticPage)
        self._pages.start()
        self.addCleanup(self._pages.stop)

    def _formatMessage(self, message, standard):
        from webengine_diagnostics import startup_snapshot
        detail = super()._formatMessage(message, standard)
        return f'{detail}; WebEngine startup: {startup_snapshot(self.app)!r}'

    def fail(self, message=None):
        raise self.failureException(self._formatMessage(None, message))

    @contextmanager
    def interactive_session(self):
        """Real xterm/ConPTY session with a predictable prompt and file receipts."""
        from types import SimpleNamespace
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication
        from bashdock.terminal import Terminal
        from bashdock.update_helper import retry

        app = QApplication.instance() or QApplication([])
        temporary = tempfile.TemporaryDirectory(prefix='bashdock M4 ')
        folder = Path(temporary.name)
        terminal = Terminal()
        terminal.resize(900, 600)
        terminal.show()
        terminal.activateWindow()

        def wait(predicate):
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if predicate():
                    return
                app.processEvents()
                time.sleep(0.01)
            self.fail('Interactive terminal did not reach expected state')

        def evaluate(script):
            result = []
            terminal.page().runJavaScript(script, result.append)
            wait(lambda: bool(result))
            return result[0]

        def screen():
            return evaluate("""(() => {
                const b = terminal.buffer.active;
                return Array.from({length: terminal.rows}, (_, i) =>
                    b.getLine(b.viewportY + i)?.translateToString(true) || '').join('\\n');
            })()""")

        def prompt():
            try:
                wait(lambda: evaluate("terminal.modes.bracketedPasteMode") and
                     screen().rstrip().endswith('M4>'))
            except AssertionError:
                self.fail(f'Expected interactive M4 prompt; '
                          f'bracketed_paste={evaluate("terminal.modes.bracketedPasteMode")!r}; '
                          f'focus={QApplication.focusWidget()!r}; screen={screen()!r}')

        def key(code, modifiers=Qt.KeyboardModifier.NoModifier):
            QTest.keyClick(QApplication.focusWidget() or terminal.focusProxy() or terminal,
                           code, modifiers)

        def type_text(text):
            self.assertTrue(text.isascii(), 'QTest.keyClicks only supports ASCII here')
            QTest.keyClicks(QApplication.focusWidget() or terminal.focusProxy() or terminal, text)

        def command(text):
            type_text(text)
            key(Qt.Key.Key_Return)

        def receipt(name, expected):
            path = folder / name
            try:
                wait(lambda: path.is_file() and path.read_text(encoding='utf-8') == expected)
            except AssertionError:
                self.fail(f'{name}: expected {expected!r}; '
                          f'file={path.read_text(encoding="utf-8") if path.exists() else None!r}; '
                          f'focus={QApplication.focusWidget()!r}; screen={screen()!r}')
            prompt()

        try:
            wait(lambda: terminal.ready)
            terminal.start(find_bash(), str(folder))
            wait(lambda: terminal.command_startup.ready)
            # Avoid changing the runner's history. Use standard Emacs Readline
            # bindings and a short prompt so assertions do not depend on PS1.
            terminal.run_command("HISTFILE=/dev/null; HISTCONTROL=; set -o emacs; "
                                 "PS1='M4> '; printf ready > setup.txt")
            receipt('setup.txt', 'ready')
            terminal.focus_terminal()
            wait(lambda: evaluate("document.activeElement.classList.contains('xterm-helper-textarea')"))
            yield SimpleNamespace(terminal=terminal, folder=folder, wait=wait, evaluate=evaluate,
                                  screen=screen, prompt=prompt, key=key, type=type_text,
                                  command=command, receipt=receipt, qt=Qt)
        finally:
            terminal.stop()
            terminal.close()
            terminal.deleteLater()
            app.processEvents()
            retry(temporary.cleanup, timeout=5)

    def test_button_timing_covers_multiline_failure_interrupt_and_remote_style_input(self):
        with self.interactive_session() as s:
            terminal = s.terminal
            messages = []
            terminal.command_status.connect(messages.append)
            output = []
            terminal.bridge.output.connect(output.append)
            terminal.run_command("sleep 0.15\nexport BASHDOCK_TIMED=kept\nprintf '%s' 'café\tλ' > timed-unicode.txt\nprintf timed > timed.txt", label='Timed script')
            s.wait(lambda: any('completed in' in message for message in messages))
            self.assertEqual('timed', (s.folder / 'timed.txt').read_text())
            self.assertEqual('café\tλ', (s.folder / 'timed-unicode.txt').read_text(encoding='utf-8'))
            self.assertEqual(2, len(messages), messages)
            self.assertNotIn('__bashdock_command_', ''.join(output))
            self.assertNotIn('eval --', ''.join(output))
            self.assertFalse(terminal.init_file.with_suffix('.command').exists())
            self.assertEqual('Timed script running…', messages[0])
            self.assertGreaterEqual(float(messages[1].split()[-1][:-1]), 0.15)
            s.prompt()
            terminal.run_command('(exit 7)', label='Failure')
            s.wait(lambda: any('exit code 7' in message for message in messages))
            self.assertIn('Failure failed after', messages[-1])
            s.prompt()
            terminal.run_command("bash -c 'printf started > timing-started.txt; exec sleep 30'", label='Interrupt me')
            s.wait(lambda: (s.folder / 'timing-started.txt').is_file() and
                   (s.folder / 'timing-started.txt').read_text() == 'started')
            s.key(s.qt.Key.Key_C, s.qt.KeyboardModifier.ControlModifier)
            try:
                s.wait(lambda: any('exit code 130' in message for message in messages))
            except AssertionError:
                self.fail(f'Interrupt completion missing: messages={messages!r}; screen={s.screen()!r}')
            s.prompt()
            terminal.run_command('printf "%s" "$BASHDOCK_TIMED" > preserved.txt')
            s.wait(lambda: (s.folder / 'preserved.txt').is_file())
            self.assertEqual('kept', (s.folder / 'preserved.txt').read_text())
            s.prompt()
            terminal.run_command('set -o vi; printf ready > timed-vi-ready.txt')
            s.receipt('timed-vi-ready.txt', 'ready')
            s.wait(lambda: terminal.at_prompt and 'timed-vi-ready.txt' in s.screen() and
                   s.screen().rstrip().endswith('M4>'))
            terminal.run_command('printf vi > timed-vi.txt', label='Vi mode')
            try:
                s.wait(lambda: any('Vi mode completed in' in message for message in messages))
            except AssertionError:
                self.fail(f'Vi completion missing: messages={messages!r}, at_prompt={terminal.at_prompt!r}; screen={s.screen()!r}')
            self.assertEqual('vi', (s.folder / 'timed-vi.txt').read_text())
            terminal.run_command('set -o emacs; printf ready > timed-emacs-ready.txt')
            s.receipt('timed-emacs-ready.txt', 'ready')
            # The file can precede WebEngine receiving the new command echo.
            # Do not mistake an old M4 prompt/directory marker for this prompt.
            s.wait(lambda: terminal.at_prompt and 'timed-emacs-ready.txt' in s.screen() and
                   s.screen().rstrip().endswith('M4>'))
            # A typed interactive program has no host prompt. A labelled
            # button must stay plain input rather than invoke host-only helpers.
            terminal.run_command("printf ready > answer-ready.txt; IFS= read -er answer; printf '%s' \"$answer\" > answer.txt")
            try:
                s.wait(lambda: (s.folder / 'answer-ready.txt').is_file() and not terminal.at_prompt)
            except AssertionError:
                self.fail(f'Interactive read did not become ready: '
                          f'file={(s.folder / "answer-ready.txt").is_file()!r}; '
                          f'at_prompt={terminal.at_prompt!r}; screen={s.screen()!r}')
            terminal.run_command('literal answer', label='Answer')
            s.wait(lambda: (s.folder / 'answer.txt').is_file())
            self.assertEqual('literal answer', (s.folder / 'answer.txt').read_text())
            s.prompt()

    def test_button_timing_restores_multiline_prompt_and_current_directory(self):
        with self.interactive_session() as s:
            t = s.terminal
            messages = []
            t.command_status.connect(messages.append)
            # Match Git Bash's blank line, coloured directory header and final $.
            t.run_command("PS1='\\n\\[\\e[32m\\]HEADER \\w\\[\\e[0m\\]\\n$ '; "
                          "printf ready > multiline-prompt-ready.txt")
            s.wait(lambda: (s.folder / 'multiline-prompt-ready.txt').is_file())
            s.wait(lambda: s.screen().rstrip().endswith('$'))
            t.run_command('mkdir child; cd child; printf "TIMED-OUTPUT\\n"', label='Prompt test')
            s.wait(lambda: any('Prompt test completed in' in m for m in messages))
            def restored():
                lines = s.screen().rstrip().splitlines()
                return (len(lines) >= 4 and lines[-1] == '$' and
                        lines[-2].startswith('HEADER ') and lines[-2].endswith('/child') and
                        lines[-3] == '' and lines[-4] == 'TIMED-OUTPUT')
            s.wait(restored)
            self.assertNotIn('__bashdock_command_', s.screen())
            t.run_command('printf success > ../after-timed-prompt.txt')
            s.wait(lambda: (s.folder / 'after-timed-prompt.txt').is_file())
            self.assertEqual('success', (s.folder / 'after-timed-prompt.txt').read_text())

    def test_command_button_confirmation_sends_nothing_until_run_and_executes_once(self):
        from unittest.mock import patch
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QWidget, QTabWidget, QVBoxLayout
        from bashdock import config, terminal_preferences
        from bashdock.app import ShellTab, TabStrip
        from bashdock.command_confirmation import CommandConfirmation
        owner = QWidget()
        owner.tabs = QTabWidget(owner)
        owner.tabs.setTabBar(TabStrip(owner.tabs))
        owner.data = {'terminal': terminal_preferences.defaults()}
        QVBoxLayout(owner).addWidget(owner.tabs)
        errors = []
        try:
            with self.interactive_session() as s:
                body = ("printf '%s\\n' first >> confirmation.txt\n"
                        "printf '%s\\n' second >> confirmation.txt")
                profile = config.default_tab('Reviewed tab')
                profile['buttons'] = [{'label': 'Reviewed script', 'command': body,
                                       'confirm': True, 'confirmation_message': 'Run both lines?'}]
                tab = ShellTab(profile, owner, terminal_factory=lambda parent: s.terminal)
                owner.tabs.addTab(tab, 'Reviewed tab')
                owner.resize(900, 650)
                owner.show()
                with patch.object(s.terminal, 'run_command', wraps=s.terminal.run_command) as run:
                    for action in ('cancel', 'close', 'run'):
                        def respond(action=action):
                            dialog = QApplication.activeModalWidget()
                            try:
                                self.assertIsInstance(dialog, CommandConfirmation)
                                self.assertEqual('Reviewed script', dialog.windowTitle())
                                self.assertTrue(dialog.command.isHidden())
                                self.assertEqual(body, dialog.command.toPlainText())
                                run.assert_not_called()
                                self.assertFalse((s.folder / 'confirmation.txt').exists())
                                self.assertEqual([], s.terminal.command_startup.pending)
                                if action == 'run':
                                    dialog.details.click()
                                    self.assertTrue(dialog.command.isVisible())
                                    run.assert_not_called()
                                    dialog.run_button.click()
                                elif action == 'close':
                                    dialog.close()
                                else:
                                    dialog.cancel_button.click()
                            except BaseException as error:
                                errors.append(error)
                                dialog.reject()
                        QTimer.singleShot(0, respond)
                        tab.command_buttons[0].click()
                        if errors:
                            raise errors[0]
                        if action != 'run':
                            run.assert_not_called()
                            self.assertFalse((s.folder / 'confirmation.txt').exists())
                    run.assert_called_once_with(body)
                    s.receipt('confirmation.txt', 'first\nsecond\n')
                    s.wait(lambda: s.evaluate("document.activeElement.classList.contains('xterm-helper-textarea')"))
        finally:
            owner.close()
            owner.deleteLater()

    def test_command_button_multiline_script_preserves_syntax_order_and_shell_state(self):
        from bashdock.command_editor import CommandEditor
        with self.interactive_session() as s:
            process = s.terminal.process
            # The body passes through the real editor, WebChannel, xterm and ConPTY.
            body = ("mkdir 'script folder'\n"
                    "cd 'script folder'\n"
                    "export BASHDOCK_MULTILINE='café 世界'\n\n"
                    "write_lines() {\n"
                    "  for value in first second; do\n"
                    "    printf '%s\\n' \"$value\"\n"
                    "  done\n"
                    "}\n"
                    "write_lines > lines.txt\n"
                    "printf '%s' \\\n"
                    "  'continued' > continuation.txt\n"
                    "printf '%s' 'literal\ttab' > tab.txt\n"
                    "cat <<'BASHDOCK_END' > heredoc.txt\n"
                    "literal $HOME and \"quotes\"\n\n"
                    "  preserved spaces\n\tliteral tab\n"
                    "BASHDOCK_END\n"
                    "printf '%s' \"$BASHDOCK_MULTILINE\" > unicode.txt\n"
                    "false\n"
                    "printf done > ../script-done.txt")
            editor = CommandEditor('Script', body)
            editor.commit()
            self.assertEqual(body, editor.result_data['command'])
            s.terminal.run_command(editor.result_data['command'])
            s.receipt('script-done.txt', 'done')
            s.receipt('script folder/lines.txt', 'first\nsecond\n')
            s.receipt('script folder/heredoc.txt', 'literal $HOME and "quotes"\n\n  preserved spaces\n\tliteral tab\n')
            s.receipt('script folder/continuation.txt', 'continued')
            s.receipt('script folder/tab.txt', 'literal\ttab')
            s.receipt('script folder/unicode.txt', 'café 世界')
            # A later invocation sees the directory, variable and function.
            s.terminal.run_command("write_lines > later.txt; "
                                   "printf '%s' \"$BASHDOCK_MULTILINE\" > later-unicode.txt")
            s.receipt('script folder/later.txt', 'first\nsecond\n')
            s.receipt('script folder/later-unicode.txt', 'café 世界')
            self.assertIs(process, s.terminal.process)
            # Both standard Readline editing modes preserve literal tabs.
            s.terminal.run_command("set -o vi; printf ready > vi-ready.txt")
            s.receipt('script folder/vi-ready.txt', 'ready')
            s.terminal.run_command("printf '%s' 'vi\ttab' > vi-tab.txt")
            s.receipt('script folder/vi-tab.txt', 'vi\ttab')
            editor.deleteLater()

    def test_m4_history_editing_completion_interrupt_and_unicode(self):
        with self.interactive_session() as s:
            key, qt = s.key, s.qt
            s.command("printf '%s' first > history.txt")
            s.receipt('history.txt', 'first')
            key(qt.Key.Key_Up)
            key(qt.Key.Key_Home)
            for _ in "printf '%s' ":
                key(qt.Key.Key_Right)
            for _ in 'first':
                key(qt.Key.Key_Delete)
            s.type('second')
            key(qt.Key.Key_End)
            key(qt.Key.Key_Return)
            s.receipt('history.txt', 'second')
            # Down restores the unfinished line after visiting history.
            s.type('printf third > history.txt')
            key(qt.Key.Key_Up)
            key(qt.Key.Key_Down)
            key(qt.Key.Key_Return)
            s.receipt('history.txt', 'third')

            (s.folder / 'bashdock-completion-target').write_text('completed', encoding='utf-8')
            s.type('cat bashdock-completion-')
            key(qt.Key.Key_Tab)
            s.type(' > completion.txt')
            key(qt.Key.Key_Return)
            s.receipt('completion.txt', 'completed')

            # Signal readiness from the foreground child, after the interactive
            # shell has launched its job. A receipt written by the parent before
            # spawning sleep races Ctrl+C against foreground-job creation.
            # exec keeps the same foreground process through the handoff to sleep.
            s.command("bash -c 'printf running > started.txt; exec sleep 30'; "
                      'printf bad > not-interrupted.txt')
            s.wait(lambda: (s.folder / 'started.txt').is_file() and
                   (s.folder / 'started.txt').read_text(encoding='utf-8') == 'running')
            key(qt.Key.Key_C, qt.KeyboardModifier.ControlModifier)
            s.prompt()
            self.assertFalse((s.folder / 'not-interrupted.txt').exists())
            s.command('printf recovered > interrupt.txt')
            s.receipt('interrupt.txt', 'recovered')

            value = 'caf\u00e9 \u03bb \u4e2d\u6587 \U0001f600'
            # xterm's public input API exercises onData/WebChannel/ConPTY UTF-8.
            # Native keyboard layouts and IME composition remain manual checks.
            s.evaluate('terminal.input(' + json.dumps(f"printf '%s' '{value}' > unicode.txt\r") + ')')
            s.receipt('unicode.txt', value)
            s.command('cat unicode.txt; echo')
            s.prompt()
            s.wait(lambda: value in s.screen().splitlines())

    def test_m4_real_pager_navigation_resize_exit_preserves_shell_state(self):
        with self.interactive_session() as s:
            key, qt = s.key, s.qt
            (s.folder / 'pager.txt').write_text(
                ''.join(f'PAGE-{i:03d} pager content\n' for i in range(1, 151)), encoding='utf-8')
            s.command('export BASHDOCK_M4=kept; mkdir child; cd child; '
                      "printf '%s' \"$BASHDOCK_M4\" > ../state.txt")
            s.receipt('state.txt', 'kept')
            s.command('less -R ../pager.txt')
            s.wait(lambda: s.evaluate("terminal.buffer.active.type === 'alternate'") and
                   'PAGE-001' in s.screen())
            key(qt.Key.Key_Space)
            s.wait(lambda: 'PAGE-001' not in s.screen() and 'pager content' in s.screen())
            s.type('b')
            s.wait(lambda: 'PAGE-001' in s.screen())
            s.terminal.resize(713, 419)
            s.wait(lambda: s.evaluate("""terminal.buffer.active.type === 'alternate' &&
                Math.abs(innerWidth - 713) <= 1 && Math.abs(innerHeight - 419) <= 1 &&
                terminal.cols === fit.proposeDimensions().cols &&
                terminal.rows === fit.proposeDimensions().rows"""))
            key(qt.Key.Key_Down)
            s.type('q')
            s.wait(lambda: s.evaluate("terminal.buffer.active.type === 'normal'"))
            s.prompt()
            s.command("printf '%s' \"$BASHDOCK_M4\" > ../after-pager.txt; "
                      "[[ $PWD == */child ]] && printf cwd >> ../after-pager.txt")
            s.receipt('after-pager.txt', 'keptcwd')

    def test_scrollback_search_live_wrapped_unicode_navigation_and_focus_without_shell_input(self):
        with self.saved_clipboard() as clipboard, self.interactive_session() as s:
            t = s.terminal
            clipboard.setText('clipboard unchanged')
            t.apply_settings(dict(t.preferences, copy_on_select=True))
            t.run_command('export BASHDOCK_SEARCH=kept; printf ready > search-ready.txt')
            s.receipt('search-ready.txt', 'ready')
            process, dimensions = t.process, t.dimensions
            columns = int(s.evaluate('terminal.cols'))
            lines = [f'line {i}: ' + ('BD-NEEDLE' if i in (5, 90, 160) else 'ordinary output')
                     for i in range(180)]
            lines += ['café λ 界', 'w' * (columns - 4) + 'WRAP-NEEDLE', 'SEARCH END']
            t.bridge.output.emit('\r\n' + '\r\n'.join(lines) + '\r\n')
            s.wait(lambda: 'SEARCH END' in s.screen())
            s.key(s.qt.Key.Key_F, s.qt.KeyboardModifier.ControlModifier)
            s.wait(lambda: s.evaluate("document.activeElement.id === 'search-input'"))
            def query(value):
                s.evaluate("(() => {const q = document.getElementById('search-input'); "
                           f"q.value = {json.dumps(value)}; q.dispatchEvent(new Event('input'));}})()")
            def status():
                return s.evaluate("document.getElementById('search-status').textContent")
            def position():
                return s.evaluate('terminal.getSelectionPosition().start.y')
            query('bd-needle')
            s.wait(lambda: status() in ('1 of 3', '2 of 3', '3 of 3'))
            first = position()
            s.key(s.qt.Key.Key_Return)
            s.wait(lambda: position() != first)
            second = position()
            s.key(s.qt.Key.Key_Return, s.qt.KeyboardModifier.ShiftModifier)
            s.wait(lambda: position() == first)
            # Navigation wraps after visiting all three matches.
            positions = []
            previous = first
            for _ in range(3):
                s.key(s.qt.Key.Key_Return)
                s.wait(lambda: position() != previous)
                previous = position()
                positions.append(previous)
            self.assertEqual(first, positions[-1])
            self.assertEqual(3, len(set(positions)))
            t.bridge.output.emit('BD-NEEDLE new output\r\n')
            s.wait(lambda: status() in ('1 of 4', '2 of 4', '3 of 4', '4 of 4'))
            query('café λ 界')
            s.wait(lambda: status() == '1 of 1' and s.evaluate('terminal.getSelection()') == 'café λ 界')
            query('WRAP-NEEDLE')
            s.wait(lambda: status() == '1 of 1' and s.evaluate('terminal.getSelection()') == 'WRAP-NEEDLE')
            query('no-such-search-match')
            s.wait(lambda: status() == 'No matches')
            self.assertTrue(s.evaluate("document.getElementById('search-next').disabled"))
            t.bridge.output.emit('\x1b[?1049hALT-NEEDLE\r\n')
            s.wait(lambda: s.evaluate("terminal.buffer.active.type === 'alternate'"))
            query('ALT-NEEDLE')
            s.wait(lambda: status() == 'Match found' and s.evaluate('terminal.getSelection()') == 'ALT-NEEDLE')
            t.bridge.output.emit('\x1b[?1049l')
            s.wait(lambda: s.evaluate("terminal.buffer.active.type === 'normal'"))
            query('')
            s.wait(lambda: status() == '' and not s.evaluate('terminal.hasSelection()'))
            query('WRAP-NEEDLE')
            s.wait(lambda: status() == '1 of 1')
            viewport = s.evaluate('terminal.buffer.active.viewportY')
            s.key(s.qt.Key.Key_Escape)
            s.wait(lambda: s.evaluate("document.getElementById('terminal-search').hidden && "
                                     "document.activeElement.classList.contains('xterm-helper-textarea')"))
            self.assertEqual(viewport, s.evaluate('terminal.buffer.active.viewportY'))
            self.assertEqual('clipboard unchanged', clipboard.text())
            self.assertEqual(dimensions, t.dimensions, 'Overlay must not resize the PTY')
            self.assertIs(process, t.process)
            t.run_command('printf "%s" "$BASHDOCK_SEARCH" > search-after.txt')
            s.receipt('search-after.txt', 'kept')

    def test_font_zoom_window_shortcuts_and_menu_apply_once_to_the_active_tab(self):
        from unittest.mock import patch
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from bashdock import config
        from bashdock.app import MainWindow
        with tempfile.TemporaryDirectory() as temp:
            settings = Path(temp) / 'settings.json'
            data = config.defaults()
            data['bash_path'] = find_bash()
            data['confirm_on_exit'] = False
            config.save(data, settings)
            # A MagicMock on a QObject method can hang PySide's dynamic slot discovery.
            with patch('bashdock.config.config_path', return_value=settings), \
                 patch('bashdock.terminal.Terminal.start', new=lambda self, *args, **kwargs: None):
                window = MainWindow()
                def wait(predicate):
                    deadline = time.monotonic() + 20
                    while time.monotonic() < deadline:
                        self.app.processEvents()
                        if predicate():
                            return
                        time.sleep(0.01)
                    self.fail('Font zoom did not reach the expected state')
                def size(terminal):
                    result = []
                    terminal.page().runJavaScript('terminal.options.fontSize', result.append)
                    wait(lambda: bool(result))
                    return result[0]
                try:
                    window.show()
                    window.activateWindow()
                    first = window.current_tab().terminal
                    wait(lambda: first.ready)
                    window.new_tab()
                    second = window.current_tab().terminal
                    wait(lambda: second.ready)
                    second.focus_terminal()
                    wait(lambda: window.isActiveWindow() and
                         (self.app.focusWidget() is second or second.isAncestorOf(self.app.focusWidget())))
                    original = window.snapshot()
                    control = Qt.KeyboardModifier.ControlModifier
                    for key, modifiers, expected in (
                        (Qt.Key.Key_Equal, control, 16),
                        (Qt.Key.Key_Plus, control | Qt.KeyboardModifier.ShiftModifier, 17),
                        (Qt.Key.Key_Minus, control, 16),
                        (Qt.Key.Key_0, control, 15),
                    ):
                        QTest.keyClick(self.app.focusWidget(), key, modifiers)
                        wait(lambda: size(second) == expected)
                        QTest.qWait(50)
                        self.assertEqual(expected, size(second), 'Shortcut must run only once')
                    window.font_zoom_actions[0].trigger()
                    wait(lambda: size(second) == 16)
                    self.assertEqual(15, size(first))
                    self.assertEqual(original, window.snapshot())
                finally:
                    window.allow_save = False
                    window.close()
                    window.deleteLater()
                    self.app.processEvents()

    def test_font_zoom_shortcuts_resize_terminal_and_preserve_shell_state(self):
        with self.interactive_session() as s:
            t = s.terminal
            original = dict(t.preferences)
            process, reader, init_file = t.process, t.reader, t.init_file
            s.command('export BASHDOCK_ZOOM=kept; mkdir child; cd child; printf ready > ../zoom-ready.txt')
            s.receipt('zoom-ready.txt', 'ready')
            control = s.qt.KeyboardModifier.ControlModifier
            for key, modifiers, size in (
                (s.qt.Key.Key_Equal, control, 16),
                (s.qt.Key.Key_Plus, control | s.qt.KeyboardModifier.ShiftModifier, 17),
                (s.qt.Key.Key_Minus, control, 16),
                (s.qt.Key.Key_0, control, 15),
            ):
                s.key(key, modifiers)
                s.wait(lambda: s.evaluate(f"terminal.options.fontSize === {size} && "
                    "terminal.cols === fit.proposeDimensions().cols && "
                    "terminal.rows === fit.proposeDimensions().rows"))
                self.assertEqual(1.0, t.zoomFactor(), 'Chromium page zoom must not change')
                self.assertEqual(original, t.preferences)
                self.assertIs(process, t.process)
                self.assertIs(reader, t.reader)
                self.assertEqual(init_file, t.init_file)
            # Use the guarded command path, as in the live-preferences check:
            # Git Bash can discard the first immediately typed byte after resize.
            t.run_command('printf "%s" "$BASHDOCK_ZOOM" > ../zoom-after.txt; '
                          '[[ $PWD == */child ]] && printf cwd >> ../zoom-after.txt')
            s.receipt('zoom-after.txt', 'keptcwd')

    def test_m6_live_terminal_preferences_preserve_process_directory_and_environment(self):
        with self.interactive_session() as s:
            t = s.terminal
            original = dict(t.preferences)
            process, reader, init_file = t.process, t.reader, t.init_file
            s.command('export BASHDOCK_M6=kept; mkdir child; cd child; printf ready > ../m6-ready.txt')
            s.receipt('m6-ready.txt', 'ready')
            presets = [
                dict(original, font_family='Consolas', font_size=22, scrollback=2345,
                     cursor_style='bar', cursor_blink=False, background='#223344',
                     foreground='#efefef', cursor_color='#00ff88', selection_color='#445566'),
                dict(original, font_family='Courier New', font_size=13, scrollback=4567,
                     cursor_style='underline', cursor_blink=True, background='#f4f4f4',
                     foreground='#101010', cursor_color='#4400cc', selection_color='#bbccdd'),
                original,
            ]
            snapshot = """JSON.stringify({font_family:terminal.options.fontFamily,
                font_size:terminal.options.fontSize, scrollback:terminal.options.scrollback,
                cursor_style:terminal.options.cursorStyle, cursor_blink:terminal.options.cursorBlink,
                background:terminal.options.theme.background, foreground:terminal.options.theme.foreground,
                cursor_color:terminal.options.theme.cursor,
                selection_color:terminal.options.theme.selectionBackground,
                inactive_selection:terminal.options.theme.selectionInactiveBackground,
                frame_background:getComputedStyle(document.body).backgroundColor,
                frame_foreground:getComputedStyle(document.body).getPropertyValue('--terminal-foreground').trim(),
                fitted:terminal.cols === fit.proposeDimensions().cols &&
                       terminal.rows === fit.proposeDimensions().rows})"""
            for index, preset in enumerate(presets):
                with self.subTest(preset=index):
                    t.apply_settings(preset)
                    expected = {key: preset[key] for key in (
                        'font_size', 'scrollback', 'cursor_style', 'cursor_blink',
                        'background', 'foreground', 'cursor_color', 'selection_color')}
                    rgb = [int(preset['background'][i:i + 2], 16) for i in (1, 3, 5)]
                    expected.update(font_family=f"{json.dumps(preset['font_family'])}, Consolas, monospace",
                                    inactive_selection=preset['selection_color'],
                                    frame_background=f'rgb({rgb[0]}, {rgb[1]}, {rgb[2]})',
                                    frame_foreground=preset['foreground'], fitted=True)
                    s.wait(lambda: json.loads(s.evaluate(snapshot)) == expected)
                    self.assertIs(process, t.process)
                    self.assertIs(reader, t.reader)
                    self.assertEqual(init_file, t.init_file)
                    filename = f'm6-state-{index}.txt'
                    t.run_command(f'printf \'%s\' "$BASHDOCK_M6" > ../{filename}; '
                                  f'[[ $PWD == */child ]] && printf :cwd >> ../{filename}')
                    s.receipt(filename, 'kept:cwd')
                    self.assertIs(process, t.process)
                    self.assertIs(reader, t.reader)

    @contextmanager
    def saved_clipboard(self):
        from PySide6.QtCore import QMimeData
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        clipboard = app.clipboard()
        original = QMimeData()
        mime = clipboard.mimeData()
        if mime is not None:
            for kind in mime.formats():
                original.setData(kind, mime.data(kind))
        try:
            yield clipboard
        finally:
            if app.platformName() == 'offscreen':
                clipboard.clear()  # Process-local; avoid offscreen MIME teardown crashes.
            else:
                clipboard.setMimeData(original)
            app.processEvents()

    def test_m5_real_selection_copy_shortcut_and_mouse_preference_routing(self):
        from unittest.mock import Mock, patch
        from PySide6.QtTest import QTest

        with self.saved_clipboard() as clipboard, self.interactive_session() as s:
            t = s.terminal
            clipboard.setText('unchanged')
            text = 'COPY_M5 caf\u00e9'
            t.bridge.output.emit('\r\n' + text + '\r\n')
            s.wait(lambda: text in s.screen().splitlines())
            select = """(() => {
                const b = terminal.buffer.active;
                for (let i = 0; i < b.length; i++) {
                    if (b.getLine(i).translateToString(true) === %s) {
                        terminal.select(0, i, %d); return true;
                    }
                }
                return false;
            })()""" % (json.dumps(text), len(text))
            self.assertTrue(s.evaluate(select))
            self.assertEqual('unchanged', clipboard.text())
            s.key(s.qt.Key.Key_C, s.qt.KeyboardModifier.ControlModifier | s.qt.KeyboardModifier.ShiftModifier)
            s.wait(lambda: clipboard.text() == text)
            t.apply_settings(dict(t.preferences, copy_on_select=True, right_click_paste=True))
            s.evaluate("globalThis.m5Selections = []; terminal.onSelectionChange(() => m5Selections.push(terminal.getSelection()))")
            s.evaluate('terminal.clearSelection()')
            # xterm batches selection notifications on animation frames;
            # clear/reselect in one frame can retain the same selection and
            # legitimately emit no change, unlike a physical mouse gesture.
            s.wait(lambda: s.evaluate("m5Selections.includes('')"))
            clipboard.setText('pending copy')
            # Selecting the same range via the public API retains xterm's
            # cached range even after clearSelection. Use a distinct range to
            # exercise a real change rather than relying on that API quirk.
            prefix = text[:7]
            short_select = select.replace(f'terminal.select(0, i, {len(text)})',
                                          f'terminal.select(0, i, {len(prefix)})')
            self.assertTrue(s.evaluate(short_select))
            s.wait(lambda: clipboard.text() == prefix)
            s.evaluate('terminal.clearSelection()')
            self.assertEqual(prefix, clipboard.text())

            # Inspect real xterm/bridge routing without sending mouse reports
            # or synthetic clipboard text to the live shell's command line.
            fake_process = Mock()
            writes = []
            fake_process.write.side_effect = writes.append
            with patch.object(t, 'process', fake_process):
                clipboard.setText('right click text')
                click = """document.getElementById('terminal').dispatchEvent(
                    new MouseEvent('mousedown', {button: 2, bubbles: true, cancelable: true, shiftKey: %s}))"""
                s.evaluate(click % 'false')
                s.wait(lambda: any('right click text' in value for value in writes))
                writes.clear()
                t.bridge.output.emit('\x1b[?1000h\x1b[?1006h')
                s.wait(lambda: s.evaluate("terminal.modes.mouseTrackingMode !== 'none'"))
                requested = []
                t.bridge.clipboardPaste.connect(requested.append)
                s.evaluate(click % 'false')
                # Allow asynchronous WebChannel requests to arrive before
                # checking that a mouse-aware program did not trigger paste.
                QTest.qWait(150)
                self.assertEqual([], requested)
                s.evaluate(click % 'true')
                s.wait(lambda: requested == ['right click text'])
                t.apply_settings(dict(t.preferences, copy_on_select=False, right_click_paste=False))
                clipboard.setText('disabled')
                s.evaluate(click % 'true')
                QTest.qWait(150)
                self.assertEqual(['right click text'], requested)
                self.assertTrue(s.evaluate(select))
                QTest.qWait(150)
                self.assertEqual('disabled', clipboard.text())
                t.bridge.output.emit('\x1b[?1000l\x1b[?1006l')

    def test_m5_native_paste_confirmation_cancel_accept_and_explicit_enter(self):
        from unittest.mock import patch
        from PySide6.QtCore import QTimer
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication, QMessageBox

        with self.saved_clipboard() as clipboard, self.interactive_session() as s:
            pasted = []
            s.terminal.bridge.clipboardPaste.connect(pasted.append)
            shortcut = s.qt.KeyboardModifier.ControlModifier | s.qt.KeyboardModifier.ShiftModifier
            clipboard.setText('printf single > single.txt')
            with patch('bashdock.terminal.QMessageBox.question') as question:
                s.key(s.qt.Key.Key_V, shortcut)
                s.wait(lambda: bool(pasted))
                question.assert_not_called()
            self.assertEqual(['printf single > single.txt'], pasted)
            s.wait(lambda: 'single.txt' in s.screen())
            QTest.qWait(150)
            self.assertEqual(1, s.screen().count('printf single > single.txt'),
                             'Chromium must not duplicate the bridge paste')
            self.assertFalse((s.folder / 'single.txt').exists())
            s.key(s.qt.Key.Key_Return)
            s.receipt('single.txt', 'single')

            value = 'printf first > paste-first.txt\nprintf second > paste-second.txt'
            clipboard.setText(value)
            for accept in (False, True):
                with self.subTest(accept=accept):
                    dialogs = []

                    def answer_dialog():
                        dialog = QApplication.activeModalWidget()
                        dialogs.append((dialog.windowTitle(), dialog.standardButton(dialog.defaultButton())))
                        dialog.button(QMessageBox.StandardButton.Yes if accept else QMessageBox.StandardButton.No).click()

                    # The Qt key event reaches Chromium/WebChannel asynchronously;
                    # poll for the modal rather than assuming a fixed delay.
                    timer = QTimer(s.terminal)
                    timer.setInterval(10)

                    def when_visible():
                        if isinstance(QApplication.activeModalWidget(), QMessageBox):
                            timer.stop()
                            answer_dialog()

                    timer.timeout.connect(when_visible)
                    timer.start()
                    try:
                        s.key(s.qt.Key.Key_V, shortcut)
                        s.wait(lambda: bool(dialogs))
                        self.assertEqual([('Paste multiple lines?', QMessageBox.StandardButton.No)], dialogs)
                        if accept:
                            s.wait(lambda: len(pasted) == 2)
                            s.wait(lambda: 'paste-second.txt' in s.screen())
                        else:
                            s.prompt()  # A rejected paste must leave the input line empty.
                        self.assertEqual(['printf single > single.txt'] + ([value] if accept else []), pasted)
                        self.assertEqual(value, clipboard.text())
                        self.assertFalse((s.folder / 'paste-first.txt').exists())
                        self.assertFalse((s.folder / 'paste-second.txt').exists())
                    finally:
                        timer.stop()
                        timer.deleteLater()
            s.key(s.qt.Key.Key_Return)
            s.receipt('paste-first.txt', 'first')
            s.receipt('paste-second.txt', 'second')

    def test_m7_export_import_cancel_keeps_live_shell_and_accept_archives_then_starts_fresh(self):
        from unittest.mock import patch
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QMessageBox
        from bashdock import config
        from bashdock.app import MainWindow
        from bashdock.update_helper import retry

        app = QApplication.instance() or QApplication([])
        temporary = tempfile.TemporaryDirectory(prefix='bashdock M7 ')
        folder = Path(temporary.name)
        settings, exported = folder / 'settings.json', folder / 'export.json'
        data = config.defaults()
        data['bash_path'] = find_bash()
        data['confirm_on_exit'] = False
        data['tabs'][0].update(startup_folder=str(folder), current_folder=str(folder))
        config.save(data, settings)
        window = None

        def wait(predicate):
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if predicate():
                    return
                app.processEvents()
                time.sleep(0.01)
            self.fail('Settings import shell did not reach expected state')

        def ready(tab):
            wait(lambda: tab.terminal.ready and tab.terminal.command_startup.ready)

        def receipt(name, expected):
            path = folder / name
            wait(lambda: path.is_file() and path.read_text(encoding='utf-8') == expected)

        try:
            with patch('bashdock.config.config_path', return_value=settings):
                window = MainWindow()
                window.show()
                original = window.current_tab()
                ready(original)
                process = original.terminal.process
                original.terminal.run_command('export BASHDOCK_M7=kept; printf ready > original-ready.txt')
                receipt('original-ready.txt', 'ready')
                original.data['name'] = 'Exported snapshot'
                with patch('bashdock.app.QFileDialog.getSaveFileName', return_value=(str(exported), '')):
                    window.export_settings()
                self.assertEqual('Exported snapshot', config.read(exported)['tabs'][0]['name'])
                self.assertIs(process, original.terminal.process)
                with patch('bashdock.app.QFileDialog.getOpenFileName', return_value=('', '')):
                    window.import_settings()
                with patch('bashdock.app.QMessageBox.question', return_value=QMessageBox.StandardButton.No):
                    window.import_settings(path=exported)
                invalid = folder / 'invalid.json'
                invalid.write_text('{broken', encoding='utf-8')
                with patch('bashdock.app.QMessageBox.warning') as warning:
                    window.import_settings(path=invalid)
                    warning.assert_called_once()
                self.assertIs(original, window.current_tab())
                self.assertIs(process, original.terminal.process)
                original.terminal.run_command('printf \'%s\' "$BASHDOCK_M7" > still-running.txt')
                receipt('still-running.txt', 'kept')
                self.assertFalse(list((folder / 'backups').glob('settings-before-import-*.json')))

                # This edit deliberately has no scheduled autosave. The import
                # archive must capture the current in-memory workspace anyway.
                original.data['name'] = 'Unsaved immediately before import'
                observed = []
                timer = QTimer(window)
                timer.setInterval(10)

                def confirm():
                    dialog = QApplication.activeModalWidget()
                    if isinstance(dialog, QMessageBox):
                        timer.stop()
                        observed.append((dialog.windowTitle(), dialog.standardButton(dialog.defaultButton())))
                        button = dialog.button(QMessageBox.StandardButton.Yes)
                        button.click() if button is not None else dialog.reject()

                timer.timeout.connect(confirm)
                timer.start()
                try:
                    window.import_settings(path=exported)
                finally:
                    timer.stop()
                    timer.deleteLater()
                self.assertEqual([('Replace workspace?', QMessageBox.StandardButton.No)], observed)
                current = window.current_tab()
                ready(current)
                self.assertIsNot(original, current)
                self.assertIsNot(process, current.terminal.process)
                self.assertEqual('Exported snapshot', current.data['name'])
                archives = list((folder / 'backups').glob('settings-before-import-*.json'))
                self.assertEqual(1, len(archives))
                self.assertEqual('Unsaved immediately before import', config.read(archives[0])['tabs'][0]['name'])
                current.terminal.run_command('printf \'%s\' "${BASHDOCK_M7-unset}" > fresh-shell.txt')
                receipt('fresh-shell.txt', 'unset')
        finally:
            if window is not None:
                window.allow_save = False
                window.data['confirm_on_exit'] = False
                window.close()
                window.deleteLater()
                app.processEvents()
            retry(temporary.cleanup, timeout=5)

    @contextmanager
    def owned_windows_process(self, pid):
        """Track an exact test-owned process handle, avoiding PID reuse during cleanup."""
        import ctypes
        from ctypes import wintypes
        from types import SimpleNamespace

        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.TerminateProcess.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        handle = kernel.OpenProcess(0x00100001, False, pid)  # SYNCHRONIZE | PROCESS_TERMINATE
        self.assertTrue(handle, f'Cannot track test process {pid}: {ctypes.get_last_error()}')

        def alive():
            state = kernel.WaitForSingleObject(handle, 0)
            self.assertIn(state, (0, 258), f'Cannot query test process {pid}')
            return state == 258

        try:
            yield SimpleNamespace(pid=pid, alive=alive)
        finally:
            try:
                if alive():
                    # Only handles captured from this fixture may be stopped.
                    kernel.TerminateProcess(handle, 1)
                    kernel.WaitForSingleObject(handle, 5000)
            finally:
                kernel.CloseHandle(handle)

    def test_m8_close_cancels_then_stops_embedded_processes_and_keeps_independent_process(self):
        from contextlib import ExitStack
        import subprocess
        from unittest.mock import patch
        from PySide6.QtWidgets import QApplication
        from bashdock import config
        from bashdock.app import MainWindow
        from bashdock.update_helper import retry

        app = QApplication.instance() or QApplication([])
        temporary = tempfile.TemporaryDirectory(prefix='bashdock M8 ')
        folder = Path(temporary.name).resolve()
        settings = folder / 'settings.json'
        data = config.defaults()
        data['bash_path'] = find_bash()
        data['tabs'] = [config.default_tab('First'), config.default_tab('Second')]
        for tab in data['tabs']:
            tab.update(startup_folder=str(folder), current_folder=str(folder))
        config.save(data, settings)
        window, independent = None, None

        def wait(predicate):
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if predicate():
                    return
                app.processEvents()
                time.sleep(0.01)
            self.fail('Shutdown did not reach the expected process/thread state')

        try:
            with patch('bashdock.config.config_path', return_value=settings), ExitStack() as owned:
                window = MainWindow()
                window.show()
                tabs = [window.tabs.widget(i) for i in range(2)]
                wait(lambda: all(t.terminal.ready and t.terminal.command_startup.ready for t in tabs))
                processes = [owned.enter_context(self.owned_windows_process(t.terminal.process.pid)) for t in tabs]
                readers = [t.terminal.reader for t in tabs]
                init_files = [t.terminal.init_file for t in tabs]
                independent = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
                child_pid = folder / 'foreground.pid'
                program = (f'from pathlib import Path; import os,time; '
                           f'Path({str(child_pid)!r}).write_text(str(os.getpid()), encoding="ascii"); time.sleep(60)')
                tabs[0].terminal.run_command(f'{shlex.quote(Path(sys.executable).as_posix())} -c {shlex.quote(program)}')
                wait(lambda: child_pid.is_file() and child_pid.read_text(encoding='ascii').isdigit())
                child = owned.enter_context(self.owned_windows_process(int(child_pid.read_text(encoding='ascii'))))
                with patch.object(window, 'confirm_quit', return_value=(False, True)):
                    self.assertFalse(window.close())
                self.assertTrue(all(p.alive() for p in processes))
                self.assertTrue(child.alive())
                self.assertTrue(all(reader.is_alive() for reader in readers))
                self.assertTrue(window.data['confirm_on_exit'])
                with patch.object(window, 'confirm_quit', return_value=(True, False)):
                    self.assertTrue(window.close())
                wait(lambda: all(not p.alive() for p in processes) and not child.alive())
                wait(lambda: all(not reader.is_alive() for reader in readers))
                self.assertTrue(all(path is not None and not path.exists() for path in init_files))
                self.assertIsNone(independent.poll(), 'Closing embedded terminals stopped an independent process')
                self.assertEqual(['First', 'Second'], [t['name'] for t in config.read(settings)['tabs']])
        finally:
            if window is not None:
                window.allow_save = False
                window.data['confirm_on_exit'] = False
                window.close()
                window.deleteLater()
                app.processEvents()
            if independent is not None and independent.poll() is None:
                independent.terminate()
                independent.wait(timeout=10)
            retry(temporary.cleanup, timeout=5)

    def test_saved_workspace_buttons_require_click_after_add_replace_and_reopen(self):
        from unittest.mock import patch
        from PySide6.QtCore import QPoint
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication, QMessageBox
        from bashdock import config
        from bashdock.app import MainWindow, CommandScrollArea
        from bashdock.terminal import Terminal
        from bashdock.update_helper import retry

        class ObservedTerminal(Terminal):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.submitted = []

            def run_command(self, command, **options):
                self.submitted.append(command)
                super().run_command(command, **options)

        app = QApplication.instance() or QApplication([])
        temporary = tempfile.TemporaryDirectory(prefix='bashdock saved workspace ')
        folder = Path(temporary.name)
        settings = folder / 'settings.json'
        receipt = folder / 'button-receipt.txt'
        data = config.defaults()
        data['bash_path'] = find_bash()
        data['confirm_on_exit'] = False
        for tab in data['tabs']:
            tab.update(startup_folder=str(folder), current_folder=str(folder))
        profile = config.default_tab('Saved command')
        profile.update(startup_folder=str(folder), current_folder=str(folder),
                       buttons=[{'label': 'First', 'command': ':'}] +
                               [{'label': 'Write receipt', 'command':
                                 f"printf '%s' clicked > {shlex.quote(receipt.as_posix())}"}])
        data['workspaces'] = [{'name': 'Button project', 'tabs': [profile], 'active_tab': 0}]
        config.save(data, settings)

        def wait_for(predicate):
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if predicate():
                    return
                app.processEvents()
                time.sleep(0.01)
            tab = window.current_tab()
            area = tab.findChild(CommandScrollArea)
            self.fail(repr(dict(window=window.geometry(), viewport=area.viewport().size(),
                                buttons=[(b.geometry(), b.sizeHint()) for b in tab.command_buttons],
                                terminal=tab.terminal.size(), dimensions=tab.terminal.dimensions)))

        def fitted_rows(terminal):
            states = []

            def fitted():
                result = []
                terminal.page().runJavaScript(
                    'JSON.stringify({height:innerHeight, rows:terminal.rows, expected:fit.proposeDimensions()?.rows})',
                    result.append)
                wait_for(lambda: bool(result))
                state = json.loads(result[0])
                if (state['height'] == terminal.height() and
                        state['rows'] == state['expected'] == terminal.dimensions[0]):
                    states.append(state['rows'])
                    return True
                return False

            wait_for(fitted)
            return states[-1]

        window = None
        try:
            with patch('bashdock.config.config_path', return_value=settings), \
                    patch('bashdock.app.QMessageBox.question', return_value=QMessageBox.StandardButton.Yes):
                window = MainWindow(terminal_factory=ObservedTerminal)
                window.show()
                screen = window.screen().availableGeometry()
                wide = min(1200, screen.width() - 80)
                narrow = min(600, wide // 2)
                height = min(760, screen.height() - 100)
                for mode in ('add', 'replace', 'reopen'):
                    with self.subTest(mode=mode):
                        receipt.unlink(missing_ok=True)
                        if mode == 'reopen':
                            window.close()
                            window.deleteLater()
                            app.processEvents()
                            window = MainWindow(terminal_factory=ObservedTerminal)
                            window.show()
                        else:
                            self.assertTrue(window.open_workspace(0, replace=mode == 'replace'))
                        tab = window.current_tab()
                        wait_for(lambda: tab.terminal.ready and tab.terminal.command_startup.ready)
                        QTest.qWait(500)
                        process = tab.terminal.process
                        window.move(screen.topLeft() + QPoint(20, 20))
                        window.resize(wide, height)
                        fitted_rows(tab.terminal)
                        area = tab.findChild(CommandScrollArea)
                        wide_space = area.viewport().width()
                        window.resize(narrow, height)
                        fitted_rows(tab.terminal)
                        narrow_space = area.viewport().width()
                        self.assertLess(narrow_space, wide_space)
                        window.resize(wide, height)
                        # Size the fixture labels from the real viewport/font,
                        # rather than assuming a desktop width or font metrics.
                        target = (wide_space + narrow_space) // 2
                        label = 'First'
                        while True:
                            tab.command_buttons[0].setText(label)
                            total = sum(button.sizeHint().width() for button in tab.command_buttons) + 6
                            if total >= target:
                                break
                            label += 'x'
                        self.assertLess(total, wide_space)
                        wait_for(lambda: len({button.y() for button in tab.command_buttons}) == 1)
                        rows = fitted_rows(tab.terminal)
                        window.resize(narrow, height)
                        wait_for(lambda: tab.command_buttons[-1].y() > tab.command_buttons[0].y())
                        wait_for(lambda: fitted_rows(tab.terminal) < rows)
                        self.assertIs(process, tab.terminal.process)
                        self.assertEqual([], tab.terminal.submitted)
                        self.assertFalse(receipt.exists(), 'A saved button ran without a click')
                        tab.command_buttons[-1].click()
                        wait_for(lambda: receipt.exists() and receipt.read_text() == 'clicked')
                        self.assertEqual([profile['buttons'][-1]['command']], tab.terminal.submitted)
                        window.resize(wide, height)
                        wait_for(lambda: len({button.y() for button in tab.command_buttons}) == 1)
                        wait_for(lambda: fitted_rows(tab.terminal) == rows)
                        receipt.unlink()
        finally:
            if window is not None:
                window.allow_save = False
                window.data['confirm_on_exit'] = False
                window.close()
                window.deleteLater()
                app.processEvents()
            retry(temporary.cleanup, timeout=5)

    def test_first_button_in_hidden_tab_and_buttons_after_resize_execute_intact(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTabWidget, QPushButton
        from bashdock.terminal import Terminal
        from bashdock.update_helper import retry

        app = QApplication.instance() or QApplication([])
        window = QWidget()
        layout = QVBoxLayout(window)
        tabs = QTabWidget(window)
        terminals = [Terminal(tabs), Terminal(tabs)]
        output = [[], []]
        for index, terminal in enumerate(terminals):
            tabs.addTab(terminal, str(index + 1))
            terminal.bridge.output.connect(output[index].append)
        layout.addWidget(tabs)
        button = QPushButton('Run command', window)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        layout.addWidget(button)
        window.resize(900, 650)
        window.show()
        window.activateWindow()

        def wait_for(predicate, index=0):
            deadline = time.monotonic() + 15
            while not predicate() and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(0.01)
            self.assertTrue(predicate(), repr(''.join(output[index])[-2000:]))

        temporary = tempfile.TemporaryDirectory(prefix='bashdock hidden tab ')
        try:
            wait_for(lambda: all(terminal.ready for terminal in terminals))
            folder = temporary.name
            for terminal in terminals:
                terminal.start(find_bash(), folder)
            wait_for(lambda: all(terminal.command_startup.ready for terminal in terminals))
            receipt = Path(folder) / 'button-receipts.txt'
            command = ''
            button.clicked.connect(lambda: tabs.currentWidget().run_command(command))
            expected = ''
            # First tab succeeds, then the first button in a previously
            # hidden shell. Repeat visibility/focus changes and resizes at
            # several delays; sleeping alone must not be the mitigation.
            for attempt in range(18):
                index = attempt % 2
                tabs.setCurrentIndex(index)
                window.resize(900 + (attempt % 3) * 45, 650 + (attempt % 4) * 20)
                QTest.qWait((0, 2200, 50, 250)[attempt % 4])
                marker = f'{attempt},'
                command = f"printf '%s' {shlex.quote(marker)} >> {shlex.quote(receipt.as_posix())}"
                expected += marker
                QTest.mouseClick(button, Qt.MouseButton.LeftButton)
                # A real file receipt proves execution. Resizing can redraw
                # the prompt before the command runs, so a prompt signal or
                # echoed input cannot satisfy this check.
                wait_for(lambda: receipt.is_file() and
                         receipt.read_text(encoding='utf-8') == expected, index)
        finally:
            for terminal in terminals:
                terminal.stop()
            window.close()
            window.deleteLater()
            app.processEvents()
            retry(temporary.cleanup, timeout=5)

    def test_new_tab_receives_native_and_terminal_focus_for_immediate_typing(self):
        from unittest.mock import patch
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication, QPushButton
        from bashdock import config
        from bashdock.app import MainWindow
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory(prefix='bashdock new tab ') as temp:
            folder = Path(temp).resolve()
            settings = folder / 'settings.json'
            data = config.defaults()
            data['bash_path'] = find_bash()
            data['confirm_on_exit'] = False
            data['tabs'][0]['current_folder'] = str(folder)
            data['tabs'][0]['startup_folder'] = str(folder)
            config.save(data, settings)
            with patch('bashdock.config.config_path', return_value=settings):
                window = MainWindow()
                def wait(predicate):
                    deadline = time.monotonic() + 20
                    while time.monotonic() < deadline:
                        if predicate():
                            return
                        app.processEvents()
                        time.sleep(0.01)
                    self.fail('New tab did not become ready/focused or receive typed input')
                try:
                    window.show()
                    window.raise_()
                    window.activateWindow()
                    with warnings.catch_warnings():
                        warnings.filterwarnings('ignore', category=DeprecationWarning,
                            message=r"Function: 'QApplication\.setActiveWindow\b")
                        QApplication.setActiveWindow(window)
                    wait(lambda: window.current_tab().terminal.command_startup.ready)
                    first = window.current_tab()
                    receipt = folder / 'typed.txt'
                    for index, route in enumerate(('button', 'shortcut', 'menu'), 1):
                        with self.subTest(route=route):
                            if route == 'button':
                                QTest.mouseClick(window.findChild(QPushButton, 'newTab'), Qt.MouseButton.LeftButton)
                            elif route == 'shortcut':
                                QTest.keyClick(app.focusWidget(), Qt.Key.Key_T,
                                    Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
                            else:
                                menu = window.manage_menu
                                action = next(a for a in menu.actions() if a.text() == 'New tab')
                                if app.platformName() == 'offscreen':
                                    # Offscreen popups do not provide native
                                    # activation/keyboard grabs. The required
                                    # windows-backend CI step clicks the real menu.
                                    action.trigger()
                                else:
                                    bar = window.menuBar()
                                    QTest.mouseClick(bar, Qt.MouseButton.LeftButton,
                                        pos=bar.actionGeometry(menu.menuAction()).center())
                                    wait(menu.isVisible)
                                    QTest.mouseClick(menu, Qt.MouseButton.LeftButton,
                                        pos=menu.actionGeometry(action).center())
                            tab = window.current_tab()
                            self.assertIsNot(first, tab)
                            self.assertEqual(index + 1, window.tabs.count())
                            wait(lambda: tab.terminal.ready and tab.terminal.command_startup.ready)
                            wait(lambda: app.focusWidget() is tab.terminal or
                                 tab.terminal.isAncestorOf(app.focusWidget()))
                            focus = app.focusWidget()
                            self.assertTrue(focus is tab.terminal or tab.terminal.isAncestorOf(focus),
                                repr(dict(route=route, focus=type(focus).__name__,
                                    active=window.isActiveWindow(), popup=app.activePopupWidget(),
                                    modal=app.activeModalWidget())))
                            # No terminal click/focus call: the first typed command
                            # must reach this new shell and preserve its first byte.
                            QTest.keyClicks(focus, "printf '%s' x >> typed.txt")
                            QTest.keyClick(focus, Qt.Key.Key_Return)
                            wait(lambda: receipt.is_file() and receipt.read_text() == 'x' * index)
                            self.assertTrue(first.terminal.process)
                finally:
                    window.allow_save = False
                    window.close()
                    window.deleteLater()
                    app.processEvents()

    def test_command_button_restores_native_and_terminal_focus_for_typing(self):
        from unittest.mock import Mock
        from PySide6.QtCore import QEvent, Qt
        from PySide6.QtTest import QTest
        from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QPushButton
        from bashdock.terminal import Terminal

        app = QApplication.instance() or QApplication([])
        window = QWidget()
        layout = QVBoxLayout(window)
        terminal = Terminal(window)
        other = QLineEdit(window)
        button = QPushButton('Run command', window)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(lambda: terminal.run_command('pwd'))
        for widget in (terminal, other, button):
            layout.addWidget(widget)
        window.resize(900, 650)
        window.show()
        window.activateWindow()
        writes = []

        def wait_for(predicate):
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if predicate():
                    return
                app.processEvents()
                time.sleep(0.01)
            focus = QApplication.focusWidget()
            self.fail(repr({'writes': writes, 'window_active': window.isActiveWindow(),
                            'focus_widget': type(focus).__name__ if focus else None,
                            'other_focused': other.hasFocus()}))

        try:
            wait_for(lambda: terminal.ready)
            # Bridge.ready is emitted before JavaScript's final startup focus.
            # Fence that task before deliberately moving focus away from xterm.
            loaded = []
            terminal.page().runJavaScript('document.readyState', loaded.append)
            wait_for(lambda: bool(loaded))
            terminal.process = Mock()
            terminal.process.write.side_effect = writes.append
            terminal.shell_ready(terminal.command_startup.begin())
            for attempt in range(2):
                # show()/activateWindow() before asynchronous WebEngine loading
                # does not establish Qt activation at this later point, notably
                # when a parent BashDock button launches the test process.
                # QTest sends events directly; establish its active window first.
                window.raise_()
                window.activateWindow()
                # Still required for deterministic native focus in this harness.
                with warnings.catch_warnings():
                    warnings.filterwarnings('ignore', category=DeprecationWarning,
                        message=r"Function: 'QApplication\.setActiveWindow\b")
                    QApplication.setActiveWindow(window)
                QTest.mouseClick(other, Qt.MouseButton.LeftButton)
                wait_for(other.hasFocus)
                QTest.mouseClick(button, Qt.MouseButton.LeftButton)
                wait_for(lambda: len(writes) > attempt * 2)
                focus = QApplication.focusWidget()
                self.assertTrue(focus is terminal or terminal.isAncestorOf(focus))
                # Typing immediately after a real Qt button click must reach
                # the shell, not the widget that had focus beforehand.
                QTest.keyClicks(focus, 'x')
                wait_for(lambda: len(writes) >= (attempt + 1) * 2)
                self.assertEqual([' \x7fpwd\r', 'x'] * (attempt + 1), writes)
                self.assertEqual('', other.text())
        finally:
            terminal.stop()
            window.close()
            window.deleteLater()
            app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()

    def test_scroll_to_bottom_button_preserves_scrollback_and_restores_focus(self):
        from PySide6.QtWidgets import QApplication
        from bashdock.terminal import Terminal

        app = QApplication.instance() or QApplication([])
        terminal = Terminal()
        terminal.resize(900, 600)
        terminal.show()

        def evaluate(script):
            results = []
            terminal.page().runJavaScript(script, results.append)
            deadline = time.monotonic() + 10
            while not results and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(0.01)
            self.assertTrue(results, "Terminal JavaScript did not respond")
            return results[0]

        state_script = """JSON.stringify((() => {
            const button = document.getElementById('scroll-to-bottom');
            const rect = button.getBoundingClientRect();
            const frame = document.getElementById('terminal-frame').getBoundingClientRect();
            const viewport = document.querySelector('.xterm-viewport');
            return {hidden:button.hidden, viewport:terminal.buffer.active.viewportY,
                base:terminal.buffer.active.baseY, type:terminal.buffer.active.type,
                focused:document.activeElement.classList.contains('xterm-helper-textarea'),
                right:rect.right, bottom:rect.bottom, width:rect.width,
                frameRight:frame.right, frameBottom:frame.bottom,
                color:getComputedStyle(button).color,
                painted:window.__bashdock_scroll_painted === true,
                viewportTop:viewport.scrollTop,
                viewportBottom:viewport.scrollHeight - viewport.clientHeight};
        })())"""

        def wait_for(predicate):
            deadline = time.monotonic() + 15
            state = None
            while time.monotonic() < deadline:
                app.processEvents()
                if terminal.ready:
                    state = json.loads(evaluate(state_script))
                    if predicate(state):
                        return state
                time.sleep(0.01)
            self.fail(f"Unexpected scroll button state: {state}")

        def wait_for_painted_viewport():
            # Buffer activation/scrolling is synchronous, but xterm synchronizes
            # the native viewport on animation frames. A real mouse click
            # arrives after painting; do not click against a pending old
            # scroll event left by the alternate-screen transition.
            evaluate("""window.__bashdock_scroll_painted = false;
                requestAnimationFrame(() => requestAnimationFrame(() => {
                    window.__bashdock_scroll_painted = true;
                }));""")
            return wait_for(lambda s: s['painted'] and (
                s['base'] == 0 or
                abs(s['viewportTop'] - s['viewport'] * s['viewportBottom'] / s['base'])
                <= s['viewportBottom'] / s['base'] + 1))

        def at_bottom(s):
            return (s['hidden'] and s['viewport'] == s['base'] and s['focused']
                    and abs(s['viewportTop'] - s['viewportBottom']) <= 1)

        try:
            wait_for(lambda s: s['hidden'])
            terminal.bridge.output.emit('line\r\n' * 100)
            wait_for(lambda s: s['base'] > 20 and s['hidden'])
            evaluate('terminal.scrollLines(-10)')
            state = wait_for(lambda s: not s['hidden'])
            position, base = state['viewport'], state['base']
            self.assertEqual(34, state['width'])
            self.assertLessEqual(state['right'], state['frameRight'] - 12)
            self.assertLessEqual(state['bottom'], state['frameBottom'] - 12)
            terminal.bridge.output.emit('new output\r\n' * 5)
            state = wait_for(lambda s: s['base'] >= base + 5)
            self.assertEqual(position, state['viewport'])
            self.assertFalse(state['hidden'])
            terminal.apply_settings(dict(terminal.preferences, background='#341527', foreground='#f0ddee'))
            wait_for(lambda s: s['color'] == 'rgb(240, 221, 238)')
            for restored in range(3):
                if restored:
                    evaluate('terminal.scrollLines(-10)')
                    wait_for(lambda s: not s['hidden'])
                wait_for_painted_viewport()
                terminal.bridge.output.emit('\x1b[?1049h')
                wait_for(lambda s: s['type'] == 'alternate' and s['hidden'])
                terminal.bridge.output.emit('\x1b[?1049l')
                wait_for(lambda s: s['type'] == 'normal' and not s['hidden'])
                wait_for_painted_viewport()
                evaluate("document.getElementById('scroll-to-bottom').click()")
                wait_for(at_bottom)
            # No new output: native viewport scrolling suppresses xterm's
            # public onScroll notification, including after a button click.
            for attempt in range(3):
                # scrollToBottom updates the buffer before the native DOM
                # viewport catches up on its animation frame. Wait for both
                # before simulating a user's next scrollbar movement.
                wait_for(lambda s: abs(s['viewportTop'] - s['viewportBottom']) <= 1)
                evaluate("document.querySelector('.xterm-viewport').scrollTop -= 120")
                wait_for(lambda s: not s['hidden'] and s['viewport'] < s['base'])
                wait_for_painted_viewport()
                evaluate("document.getElementById('scroll-to-bottom').click()")
                wait_for(at_bottom)
        finally:
            terminal.stop()
            terminal.close()

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
            self.assertEqual([" \x7fpwd\r"], writes)
            terminal.run_command("printf 'first\\n'\nprintf 'second\\n'")
            wait_for(lambda: len(writes) >= 2)
            self.assertEqual(" \x7fprintf 'first\\n'\rprintf 'second\\n'\r", writes[1])
            # Clipboard paste still uses xterm's active bracketed-paste behavior.
            terminal.bridge.clipboardPaste.emit("clipboard text")
            wait_for(lambda: len(writes) >= 3)
            self.assertEqual("\x1b[200~clipboard text\x1b[201~", writes[2])
            events = [e for e in terminal.trace.recorder.snapshot()['events']
                      if e['terminal'] == terminal.trace.terminal_id]
            received = [e for e in events if e['event'] == 'command_received']
            self.assertEqual(2, len(received))
            self.assertTrue(all(e['recognized'] and e['unchanged'] for e in received))
            self.assertEqual([e['command'] for e in received],
                             [e['command'] for e in events if e['event'] == 'command_dispatched'])
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
                    if (abs(bounds["width"] - terminal.width()) <= 1 and
                            abs(bounds["height"] - terminal.height()) <= 1 and bounds["fitted"]):
                        break
                    self.assertLess(time.monotonic(), deadline, f"Terminal did not finish resizing: requested={(width, height)!r}, actual={terminal.size()!r}, bounds={bounds!r}")
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
