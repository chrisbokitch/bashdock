"""Bundled starter definitions; applying a preset never executes its commands."""
from dataclasses import dataclass

from .config import DEFAULT_CONFIRMATION_MESSAGE


@dataclass(frozen=True)
class PresetButton:
    label: str
    command: str
    description: str
    confirm: bool = False
    message: str = DEFAULT_CONFIRMATION_MESSAGE

    def definition(self):
        return dict(label=self.label, command=self.command, confirm=self.confirm,
                    confirmation_message=self.message)


@dataclass(frozen=True)
class PresetGroup:
    name: str
    description: str
    requirements: str
    buttons: tuple[PresetButton, ...]


GROUPS = (
    PresetGroup('Git essentials', 'Inspect repository changes and recent history.',
                'Git repository. Copy diff uses the Windows clipboard and includes unstaged tracked changes only.', (
        PresetButton('Status', 'git status --short --branch', 'Show branch and changed files.'),
        PresetButton('Diff', 'git diff', 'Show unstaged changes to tracked files.'),
        PresetButton('Recent commits', 'git log --oneline -15', 'Show the latest 15 commits.'),
        PresetButton('Copy diff', 'git diff | clip', 'Copy the unstaged tracked diff to the clipboard.'),
    )),
    PresetGroup('Git recovery', 'AI Rescue: review and discard unwanted working-tree changes.',
                'Git repository. Restore and cleanup operate under the current directory; preview cleanup first.', (
        PresetButton('Discard unstaged changes', 'git restore --worktree .',
                     'Discard unstaged tracked edits; staged changes remain.', True,
                     'Discard unstaged changes to tracked files under the current directory?'),
        PresetButton('Preview untracked cleanup', 'git clean -nd',
                     'List untracked files and directories that cleanup would delete.'),
        PresetButton('Delete untracked files', 'git clean -fd',
                     'Delete untracked files and directories, respecting Git ignore rules.', True,
                     'Delete untracked files and directories under the current directory?'),
    )),
    PresetGroup('Python / Backend', 'Test, format and capture dependencies for a Python project.',
                'Use the intended Python environment, with pytest, Black and Ruff installed. No tools are installed by this picker.', (
        PresetButton('Run tests', 'python -m pytest -v', 'Run pytest with verbose output.'),
        PresetButton('Format and fix', 'black . && ruff check --fix .',
                     'Format Python files, then apply Ruff fixes if formatting succeeds.', True,
                     'Format Python files and apply Ruff fixes under the current directory?'),
        PresetButton('Freeze dependencies', 'python -m pip freeze > requirements.txt',
                     'Write installed packages from the current Python environment; overwrites requirements.txt.', True,
                     'Overwrite requirements.txt with packages from the current Python environment?'),
    )),
    PresetGroup('Web / Node', 'Run the project scripts and reinstall locked dependencies.',
                'Node.js and npm. Dev, test and build scripts must exist in package.json; npm ci needs a matching lockfile.', (
        PresetButton('Dev server', 'npm run dev', 'Start the project dev script; Ctrl+C stops a foreground server.'),
        PresetButton('Run tests', 'npm test', 'Run the project test script.'),
        PresetButton('Build', 'npm run build', 'Run the project build script.'),
        PresetButton('Clean install', 'npm ci',
                     'Replace node_modules using the existing lockfile; does not rewrite the lockfile.', True,
                     'Replace node_modules and reinstall dependencies from the existing lockfile?'),
    )),
    PresetGroup('Docker Compose', 'Start, inspect and stop a project’s services.',
                'Docker with Compose, a running Docker engine, and a project Compose file.', (
        PresetButton('Start services', 'docker compose up -d', 'Start services in the background; may recreate changed containers.'),
        PresetButton('Service status', 'docker compose ps', 'Show service container status.'),
        PresetButton('Follow logs', 'docker compose logs --tail=100 -f', 'Follow recent service logs; Ctrl+C stops following.'),
        PresetButton('Stop services', 'docker compose stop', 'Stop services without removing containers or volumes.', True,
                     'Stop this Compose project’s running services?'),
    )),
)
