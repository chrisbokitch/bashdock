"""Split button text into Bash scripts and explicit terminal interrupts."""


def command_steps(command):
    steps = []
    lines = []
    for line in command.splitlines(keepends=True):
        if line.strip() == '<<interrupt>>':
            script = ''.join(lines).rstrip('\r\n')
            if script.strip():
                steps.append(('command', script))
            steps.append(('interrupt', None))
            lines = []
        else:
            lines.append(line)
    script = ''.join(lines).rstrip('\r\n')
    if script.strip():
        steps.append(('command', script))
    return steps
