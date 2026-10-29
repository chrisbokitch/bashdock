"""Test-only local-page startup evidence; no production logging or commands."""
from collections import deque
from bashdock.terminal import LocalPage


class DiagnosticPage(LocalPage):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.startup_events = deque(maxlen=12)
        self.loadStarted.connect(lambda: self.startup_events.append(('load_started',)))
        self.loadFinished.connect(lambda ok: self.startup_events.append(('load_finished', ok)))
        self.loadingChanged.connect(lambda info: self.startup_events.append(
            ('loading', info.status().name, info.errorCode(), info.errorDomain().name)))
        self.renderProcessTerminated.connect(lambda status, code: self.startup_events.append(
            ('renderer_terminated', status.name, code)))

    def javaScriptConsoleMessage(self, level, message, line, source):
        # Only the error location, never arbitrary console content or shell data.
        self.startup_events.append(('javascript_console', level.name, line, source.rsplit('/', 1)[-1]))


def startup_snapshot(app):
    from bashdock.terminal import Terminal
    result = []
    for view in app.allWidgets():
        if isinstance(view, Terminal):
            try:
                page = view.page()
                result.append(dict(ready=view.ready, visible=view.isVisible(),
                                   size=(view.width(), view.height()),
                                   renderer_pid=page.renderProcessPid(),
                                   lifecycle=page.lifecycleState().name,
                                   events=list(getattr(page, 'startup_events', []))))
            except RuntimeError:
                result.append({'page': 'already deleted'})
    return result
