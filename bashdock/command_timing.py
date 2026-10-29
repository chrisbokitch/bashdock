"""Track one foreground button script using shell-generated timestamps."""
import re
import shlex
from uuid import uuid4

STAMP = re.compile(r'([0-9]{1,14})\.([0-9]{6})\Z')


class CommandTiming:
    def __init__(self):
        self.reset()

    def reset(self):
        self.session = None
        self.token = None
        self.label = None
        self.started = None

    def prepare(self, command, label, session):
        self.session, self.token, self.label = session, uuid4().hex, label
        self.started = None
        # eval runs the literal script in the current shell, without a function
        # or subshell scope. One prompt follows the whole multiline script.
        return f'__bashdock_command_begin {self.token} "$?"; eval -- {shlex.quote(command)}'

    def event(self, payload):
        if len(payload) > 160:
            return None
        parts = payload.split(';')
        if len(parts) not in (4, 5) or parts[:2] != [self.session, self.token] or not self.token:
            return None
        match = STAMP.fullmatch(parts[-1])
        if not match:
            return None
        stamp = int(match[1]) * 1_000_000 + int(match[2])
        if parts[2] == 'start' and len(parts) == 4 and self.started is None:
            self.started = stamp
            return f'{self.label} running…'
        if parts[2] != 'done' or len(parts) != 5 or self.started is None:
            return None
        if not parts[3].isascii() or not parts[3].isdigit() or not 0 <= int(parts[3]) <= 255:
            return None
        status = int(parts[3])
        elapsed = stamp - self.started
        duration = f'{elapsed / 1_000_000:.3f}s' if elapsed >= 0 else '(duration unavailable: system clock changed)'
        if status == 0:
            text = f'{self.label} completed in {duration}'
        elif status == 130:
            text = f'{self.label} interrupted after {duration} · exit code 130'
        else:
            text = f'{self.label} failed after {duration} · exit code {status}'
        self.reset()
        return text
