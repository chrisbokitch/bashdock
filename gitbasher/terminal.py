"""Qt/WebChannel bridge to a Windows pseudoterminal. No network listener."""
import os
import queue
import sys
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QMessageBox
from .shell_integration import create_init_file, valid_reported_directory


class LocalPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        return url.scheme() in ("file", "qrc", "about")


class Bridge(QObject):
    output = Signal(str)
    paste = Signal(str)
    clipboardPaste = Signal(str)
    focus = Signal()

    def __init__(self, terminal):
        super().__init__(terminal)
        self.terminal = terminal

    @Slot(int, int)
    def ready(self, cols, rows):
        if not self.terminal.ready:
            self.terminal.ready = True
            self.terminal.dimensions = (rows, cols)
            self.terminal.loaded.emit()

    @Slot(str)
    def input(self, data):
        self.terminal.write(data)

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
        self.terminal.dimensions = (max(2, rows), max(2, cols))
        if self.terminal.process:
            try:
                self.terminal.process.setwinsize(*self.terminal.dimensions)
            except (OSError, RuntimeError):
                pass


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
        self.setPage(LocalPage(self))
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

    def start(self, bash_path, folder):
        if self.process:
            raise RuntimeError("A shell is already running.")
        if self.reader and self.reader.is_alive():
            raise RuntimeError("The previous shell is still closing. Try again shortly.")
        if sys.platform != "win32":
            raise RuntimeError("gitbasher currently requires Windows 10/11.")
        from winpty import PtyProcess, Backend
        env = dict(os.environ, TERM="xterm-256color", COLORTERM="truecolor", CHERE_INVOKING="1",
                   GITBASHER_START_DIR=Path(folder).as_posix())
        self.stopping.clear()
        self.cleanup_init_file()
        self.init_file = create_init_file()
        try:
            self.process = PtyProcess.spawn(
                [bash_path, "--rcfile", self.init_file.as_posix(), "-i"], cwd=folder, env=env,
                dimensions=self.dimensions, backend=Backend.ConPTY,
            )
        except Exception:
            self.cleanup_init_file()
            raise
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
                self.cleanup_init_file()
                self.ended.emit(data)
        if chunks:
            self.bridge.output.emit("".join(chunks))

    def write(self, data):
        if self.process:
            try:
                self.process.write(data)
            except (OSError, RuntimeError, EOFError) as error:
                self.problem.emit(str(error))

    def run_command(self, command):
        # Terminal.paste uses bracketed-paste mode when enabled by the active program.
        if self.process:
            self.bridge.paste.emit(command)
            self.bridge.focus.emit()

    def cleanup_init_file(self):
        if self.init_file:
            try:
                self.init_file.unlink(missing_ok=True)
            except OSError:
                pass
            self.init_file = None

    def stop(self):
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
