"""Hold button commands until this shell's startup output is acknowledged."""
from uuid import uuid4


class CommandStartup:
    def __init__(self):
        self.reset()

    def reset(self):
        self.session_id = None
        self.ready = False
        self.pending = []

    def begin(self):
        self.reset()
        self.session_id = uuid4().hex
        return self.session_id

    def submit(self, command):
        if self.ready:
            return True
        self.pending.append(command)
        return False

    def release(self, session_id):
        if not self.session_id or session_id != self.session_id or self.ready:
            return []
        self.ready = True
        commands, self.pending = self.pending, []
        return commands
