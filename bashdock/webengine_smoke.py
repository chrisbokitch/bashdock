"""Exercise the frozen WebEngine renderer, WebChannel and real shell together."""
import json
from pathlib import Path
import sys
import time
import traceback


def run(report_path, timeout=45):
    from PySide6.QtCore import QEvent, QLibraryInfo, QTimer
    from PySide6.QtGui import QImage
    from PySide6.QtWebEngineCore import qWebEngineVersion
    from PySide6.QtWidgets import QApplication
    from .config import find_bash
    from .terminal import Terminal
    from .webengine_resources import validate_runtime_resources

    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    result = dict(ok=False, frozen=bool(getattr(sys, 'frozen', False)))
    terminal = None
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName('BashDock WebEngine resource check')
    try:
        resources = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.DataPath)) / 'resources'
        if result['frozen'] and not resources.resolve().is_relative_to(Path(sys._MEIPASS).resolve()):
            raise ValueError('WebEngine resources are outside the frozen application.')
        result['resources'] = validate_runtime_resources(resources, debug_build=QLibraryInfo.isDebugBuild())
        result['qt_version'] = QLibraryInfo.version().toString()
        result['webengine_version'] = qWebEngineVersion()
        terminal = Terminal()
        terminal.resize(900, 600)
        terminal.show()
        deadline = time.monotonic() + timeout
        state = dict(sent=False, pending=False, finished=False)
        timer = QTimer(terminal)
        timer.setInterval(50)

        def finish(error=None):
            if state['finished']:
                return
            state['finished'] = True
            timer.stop()
            result['ok'] = error is None
            result['terminal_ready'] = terminal.ready
            result['shell_ready'] = terminal.command_startup.ready
            if error:
                result['error'] = str(error)
            app.exit(0 if error is None else 1)

        def start():
            try:
                bash = find_bash()
                if not bash:
                    raise RuntimeError('Git for Windows was not found.')
                terminal.start(bash, str(report_path.parent))
            except Exception:
                finish(traceback.format_exc())

        def rendered(data):
            state['pending'] = False
            if isinstance(data, str):
                try:
                    data = json.loads(data)
                except ValueError:
                    data = None
            if state['finished'] or not isinstance(data, dict) or not data.get('marker'):
                return
            try:
                image = terminal.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
                if image.isNull():
                    return
                colors = len(set(image.constBits().cast('I')))
                result['painted_colors'] = colors
                if colors < 2:
                    return  # Allow painting to catch up with xterm's parsed buffer.
                screenshot = report_path.with_suffix('.png')
                if not image.save(str(screenshot)):
                    raise OSError('Could not save the WebEngine rendering proof.')
                result.update(renderer=data, painted_colors=colors, screenshot=screenshot.name)
                finish()
            except Exception:
                finish(traceback.format_exc())

        def poll():
            try:
                if state['finished']:
                    return
                if time.monotonic() >= deadline:
                    raise TimeoutError('Packaged WebEngine did not render real shell output.')
                if not terminal.command_startup.ready:
                    return
                if not state['sent']:
                    state['sent'] = True
                    terminal.run_command("HISTFILE=/dev/null; printf '\\033[32mBASHDOCK_%s café λ 中文\\033[0m\\n' 'WEBENGINE_READY'")
                if not state['pending']:
                    state['pending'] = True
                    terminal.page().runJavaScript("""(() => {
                        const b = terminal.buffer.active;
                        const text = Array.from({length:b.length}, (_, i) =>
                            b.getLine(i)?.translateToString(true) || '').join('\\n');
                        return JSON.stringify({marker:text.includes('BASHDOCK_WEBENGINE_READY café λ 中文'),
                                rows:terminal.rows, cols:terminal.cols,
                                devicePixelRatio:window.devicePixelRatio});
                    })()""", rendered)
            except Exception:
                finish(traceback.format_exc())

        terminal.loaded.connect(start)
        timer.timeout.connect(poll)
        timer.start()
        app.exec()
    except Exception:
        result['error'] = traceback.format_exc()
    finally:
        if terminal is not None:
            terminal.stop()
            terminal.close()
            terminal.deleteLater()
            app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            app.processEvents()
        report_path.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return 0 if result['ok'] else 1
