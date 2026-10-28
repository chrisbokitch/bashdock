"""Qt/WebChannel bridge to a Windows pseudoterminal. No network listener."""
import queue
import threading
import logging
import json
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Qt, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMessageBox
from .shell_integration import valid_reported_directory
from .shell_backend import spawn_shell
from .command_startup import CommandStartup
from .input_diagnostics import CommandTrace
from . import terminal_preferences


class LocalPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        return url.scheme() in ("file", "qrc", "about")


class Bridge(QObject):
    output = Signal(str)
    paste = Signal(int, str)
    clipboardPaste = Signal(str)
    focus = Signal()
    settingsChanged = Signal(str)

    def __init__(self, terminal):
        super().__init__(terminal)
        self.terminal = terminal

    @Slot()
    def requestSettings(self):
        self.settingsChanged.emit(json.dumps(self.terminal.preferences))

    @Slot(int, int)
    def ready(self, cols, rows):
        if not self.terminal.ready:
            self.terminal.ready = True
            self.terminal.dimensions = (rows, cols)
            self.terminal.loaded.emit()

    @Slot(str)
    def input(self, data):
        self.terminal.trace.record('terminal_input', characters=len(data),
            utf8_bytes=len(data.encode('utf-8', errors='surrogatepass')),
            has_escape='\x1b' in data, has_enter='\r' in data or '\n' in data)
        self.terminal.write(data)

    @Slot(int, str)
    def commandInput(self, command_id, data):
        self.terminal.trace.receive(command_id, data)
        self.terminal.write(data, command_id=command_id)

    @Slot(bool)
    def viewFocus(self, focused):
        self.terminal.trace.record('web_focus', focused=focused)

    @Slot(str)
    def shellReady(self, session_id):
        self.terminal.shell_ready(session_id)

    @Slot(str)
    def directory(self, path):
        if valid_reported_directory(path):
            self.terminal.directory_changed.emit(path)

    @Slot(str)
    def copy(self, text):
        QApplication.clipboard().setText(text)

    @Slot()
    def requestPaste(self):
        text = QApplication.clipboard().text()
        if any(ch in text for ch in "\r\n"):
            answer = QMessageBox.question(self.terminal, "Paste multiple lines?",
                "The clipboard contains multiple lines. Paste into the active terminal?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.clipboardPaste.emit(text)

    @Slot(int, int)
    def resize(self, cols, rows):
        dimensions = (max(2, rows), max(2, cols))
        self.terminal.trace.record('resize_requested', rows=dimensions[0], cols=dimensions[1],
            changed=dimensions != self.terminal.dimensions, running=bool(self.terminal.process))
        self.terminal.dimensions = dimensions
        if self.terminal.process:
            try:
                self.terminal.process.setwinsize(*self.terminal.dimensions)
                self.terminal.trace.record('resize_complete')
            except (OSError, RuntimeError) as error:
                self.terminal.trace.record('resize_failed', errno=getattr(error, 'errno', None),
                    winerror=getattr(error, 'winerror', None))


class Terminal(QWebEngineView):
    loaded = Signal()
    ended = Signal(str)
    problem = Signal(str)
    directory_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self.ready = False
        self.dimensions = (30, 100)
        self.messages = queue.Queue(maxsize=128)
        self.stopping = threading.Event()
        self.reader = None
        self.init_file = None
        self.command_startup = CommandStartup()
        self.trace = CommandTrace()
        self.preferences = terminal_preferences.defaults()
        self.setPage(LocalPage(self))
        # Cover Chromium's empty page before the terminal HTML is painted.
        self.page().setBackgroundColor(QColor(self.preferences['background']))
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        self.channel = QWebChannel(self.page())
        self.bridge = Bridge(self)
        self.channel.registerObject("bridge", self.bridge)
        self.page().setWebChannel(self.channel)
        self.setUrl(QUrl.fromLocalFile(str(Path(__file__).parent / "assets/terminal.html")))
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.drain)
        self.timer.start()

    def apply_settings(self, settings):
        self.preferences = terminal_preferences.validated(settings)
        self.page().setBackgroundColor(QColor(self.preferences['background']))
        self.bridge.settingsChanged.emit(json.dumps(self.preferences))

    def start(self, bash_path, folder):
        if self.process:
            raise RuntimeError("A shell is already running.")
        if self.reader and self.reader.is_alive():
            raise RuntimeError("The previous shell is still closing. Try again shortly.")
        self.stopping.clear()
        self.cleanup_init_file()
        session_id = self.command_startup.begin()
        self.trace.reset()
        self.trace.record('shell_start', rows=self.dimensions[0], cols=self.dimensions[1])
        self.process, self.init_file = spawn_shell(
            bash_path, folder, self.dimensions, session_id=session_id)
        self.reader = threading.Thread(target=self.read_loop, args=(self.process,), daemon=True)
        self.reader.start()

    def enqueue(self, kind, data):
        while not self.stopping.is_set():
            try:
                self.messages.put((kind, data), timeout=0.1)
                return
            except queue.Full:
                pass

    def read_loop(self, process):
        try:
            while not self.stopping.is_set():
                chunk = process.read(16384)
                if not chunk:
                    break
                self.enqueue("data", chunk)
        except EOFError:
            pass
        except Exception as error:
            if not self.stopping.is_set():
                logging.exception("Terminal reader failed")
                self.enqueue("error", str(error))
        finally:
            self.enqueue("end", "Shell exited. Use Restart shell to open a new session.")

    def drain(self):
        # Bound work per UI tick to keep the window responsive during heavy output.
        chunks = []
        for _ in range(32):
            try:
                kind, data = self.messages.get_nowait()
            except queue.Empty:
                break
            if kind == "data":
                chunks.append(data)
            elif kind == "error":
                self.problem.emit(data)
            else:
                self.process = None
                self.command_startup.reset()
                self.trace.reset()
                self.trace.record('shell_stop')
                self.cleanup_init_file()
                self.ended.emit(data)
        if chunks:
            self.bridge.output.emit("".join(chunks))

    def write(self, data, command_id=0):
        if command_id:
            # Git Bash can drop the first input character after a resize.
            # At the empty prompt required for command buttons, this space
            # and Backspace cancel out even when the space is swallowed.
            # Unlike a leading-space workaround, no space remains in history.
            data = ' \x7f' + data
        self.trace.record('write_attempt', command=command_id, characters=len(data),
            utf8_bytes=len(data.encode('utf-8', errors='surrogatepass')), running=bool(self.process))
        if self.process:
            try:
                count = self.process.write(data)
                self.trace.record('write_complete', command=command_id, reported_count=count)
            except (OSError, RuntimeError, EOFError) as error:
                self.trace.record('write_failed', command=command_id,
                    errno=getattr(error, 'errno', None), winerror=getattr(error, 'winerror', None))
                self.problem.emit(str(error))

    def run_command(self, command):
        # The button-command signal sends plain input plus Enter, not a clipboard paste.
        command_id = self.trace.prepare(command, ready=self.command_startup.ready, running=bool(self.process))
        if self.process:
            if not self.command_startup.submit((command_id, command)):
                self.trace.record('command_queued', command=command_id)
                self.focus_terminal()
                return
            self.dispatch_command(command_id, command)

    def dispatch_command(self, command_id, command):
        self.trace.record('command_dispatched', command=command_id)
        self.focus_terminal()
        self.bridge.paste.emit(command_id, command)

    def focus_terminal(self):
        # Focusing xterm's textarea alone does not transfer native Qt focus
        # from another widget into the WebEngine view.
        self.setFocus(Qt.FocusReason.OtherFocusReason)
        self.trace.record('focus_requested', native_focus=self.hasFocus() or
                          (self.focusProxy() is not None and self.focusProxy().hasFocus()))
        self.bridge.focus.emit()

    def shell_ready(self, session_id):
        # A late browser callback from a stopped shell cannot release a new
        # shell's commands. Terminal-generated replies still bypass this queue.
        if not self.process:
            return
        self.trace.record('shell_ready', accepted=session_id == self.command_startup.session_id)
        for command_id, command in self.command_startup.release(session_id):
            self.dispatch_command(command_id, command)

    def cleanup_init_file(self):
        if self.init_file:
            try:
                self.init_file.unlink(missing_ok=True)
            except OSError:
                pass
            self.init_file = None

    def stop(self):
        self.trace.record('shell_stop')
        self.trace.reset()
        self.command_startup.reset()
        self.stopping.set()
        process, self.process = self.process, None
        if process:
            try:
                process.close(force=True)
            except (OSError, RuntimeError):
                pass
        if self.reader:
            self.reader.join(timeout=0.5)
        self.cleanup_init_file()
        while True:
            try:
                self.messages.get_nowait()
            except queue.Empty:
                break
