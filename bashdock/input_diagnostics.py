"""Bounded input telemetry: numerical metadata only, never shell contents."""
from collections import OrderedDict, deque
from datetime import datetime, timezone
import hashlib
import hmac
from importlib.metadata import version, PackageNotFoundError
import itertools
import json
from pathlib import Path
import re
import secrets
import sys
import threading
import time

from ._version import __version__


# Reject unknown keys and string values so command/path/output text cannot
# accidentally enter a report through this API, including error messages.
SCHEMA = {
    'shell_start': {'rows', 'cols'}, 'shell_ready': {'accepted'}, 'shell_stop': set(),
    'button_clicked': {'characters', 'utf8_bytes', 'ready', 'running'},
    'command_queued': set(), 'command_dispatched': set(),
    'command_received': {'characters', 'utf8_bytes', 'recognized', 'unchanged'},
    'terminal_input': {'characters', 'utf8_bytes', 'has_escape', 'has_enter'},
    'write_attempt': {'characters', 'utf8_bytes', 'running'},
    'write_complete': {'reported_count'}, 'write_failed': {'errno', 'winerror'},
    'resize_requested': {'rows', 'cols', 'changed', 'running'},
    'resize_complete': set(), 'resize_failed': {'errno', 'winerror'},
    'focus_requested': {'native_focus'}, 'web_focus': {'focused'},
    'window_resize': {'width', 'height'}, 'tab_selected': set(),
}


class Recorder:
    def __init__(self, capacity=4096):
        self._events = deque(maxlen=capacity)
        self._lock = threading.Lock()
        self._started = time.monotonic_ns()
        self._sequence = 0
        self._terminals = itertools.count(1)

    def terminal_id(self):
        with self._lock:
            return next(self._terminals)

    def record(self, event, *, terminal=0, command=0, **fields):
        if event not in SCHEMA:
            return
        safe = {key: value for key, value in fields.items()
                if key in SCHEMA[event] and type(value) in (bool, int)}
        with self._lock:
            self._sequence += 1
            self._events.append(dict(sequence=self._sequence,
                elapsed_ms=(time.monotonic_ns() - self._started) // 1_000_000,
                event=event, terminal=terminal if type(terminal) is int else 0,
                command=command if type(command) is int else 0, **safe))

    def snapshot(self):
        with self._lock:
            events = [dict(event) for event in self._events]
            return dict(capacity=self._events.maxlen, dropped_events=self._sequence - len(events),
                        events=events)

    def save(self, filename):
        runtime = dict(bashdock=__version__, python='.'.join(map(str, sys.version_info[:3])),
                       platform=sys.platform, packaged=bool(getattr(sys, 'frozen', False)),
                       terminal_backend='ConPTY')
        for package in ('PySide6', 'pywinpty'):
            try:
                runtime[package] = version(package)
            except PackageNotFoundError:
                pass
        if sys.platform == 'win32':
            windows = sys.getwindowsversion()
            runtime['windows'] = dict(major=windows.major, minor=windows.minor, build=windows.build)
        report = dict(schema_version=1, saved_at=datetime.now(timezone.utc).isoformat(),
                      runtime=runtime, recent_activity=self.snapshot())
        Path(filename).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


recorder = Recorder()


class CommandTrace:
    def __init__(self, target=recorder):
        self.recorder = target
        self.terminal_id = target.terminal_id()
        self._commands = itertools.count(1)
        self._key = secrets.token_bytes(32)
        self._expected = OrderedDict()

    def record(self, event, *, command=0, **fields):
        self.recorder.record(event, terminal=self.terminal_id, command=command, **fields)

    def _digest(self, text):
        return hmac.digest(self._key, text.encode('utf-8', errors='surrogatepass'), hashlib.sha256)

    def prepare(self, text, *, ready, running):
        command = next(self._commands)
        normalized = re.sub(r'\r?\n', '\r', text) + '\r'
        self._expected[command] = self._digest(normalized)
        while len(self._expected) > 128:
            self._expected.popitem(last=False)
        self.record('button_clicked', command=command, ready=ready, running=running,
                    characters=len(text), utf8_bytes=len(text.encode('utf-8', errors='surrogatepass')))
        return command

    def receive(self, command, text):
        expected = self._expected.pop(command, None)
        self.record('command_received', command=command, recognized=expected is not None,
                    unchanged=expected is not None and hmac.compare_digest(expected, self._digest(text)),
                    characters=len(text), utf8_bytes=len(text.encode('utf-8', errors='surrogatepass')))

    def reset(self):
        self._expected.clear()
