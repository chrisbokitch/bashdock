# gitbasher

A Python/Qt Windows desktop app with multiple Git Bash tabs and a custom command bar beneath each terminal.

## Requirements

- Windows 10 (1809 or newer) or Windows 11
- Python 3.11 or newer (64-bit; Python 3.12/3.13 recommended)
- [Git for Windows](https://gitforwindows.org/)

## Run from source

Open PowerShell and clone the project into `C:\Development\gitbasher`:

```powershell
New-Item -ItemType Directory -Force C:\Development | Out-Null
Set-Location C:\Development
git clone https://github.com/chrisbokitch/gitbasher.git
Set-Location .\gitbasher
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\gitbasher.exe
```

The editable install picks up source edits without reinstalling. Virtual environment activation is optional; these commands use its executables directly and do not require changing PowerShell execution policy.

To launch it again later:

```powershell
Set-Location C:\Development\gitbasher
.\.venv\Scripts\gitbasher.exe
```

To update your checkout and dependencies:

```powershell
Set-Location C:\Development\gitbasher
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e .
```

Git Bash is detected in common installation locations. If detection fails, open **Configure tab** and choose `C:\Program Files\Git\bin\bash.exe` (or your installation's equivalent). Use `bash.exe`, not `git-bash.exe`: the latter launches a separate terminal window.

## Tabs and remembered workspace

- Use **+ New tab** or **Ctrl+Shift+T** for an independent Git Bash shell.
- Double-click a tab to rename it, or use **Session → Rename tab**.
- Drag tabs to reorder them. Use the tab's close button or **Ctrl+Shift+W** to close it.
- Each tab has its own configurable command bar at the **bottom**, immediately below its terminal.
- Names, tab order, selected tab, current folders, startup folders, and command buttons are saved automatically and restored at the next launch.
- A new tab starts in the selected tab's last reported folder with its own default buttons.

Restoring creates **fresh shells** in the remembered folders. Running programs, environment variables set during a session, and terminal scrollback are not restored. Working directories are reported at each shell prompt; if a job is still running when you close the app, the last reported folder is used. If a remembered folder has been removed, the configured startup folder is tried, then your home folder.

Existing version 0.1 settings migrate into the first tab automatically, including your custom buttons. Closing the last tab quits the application and remembers that tab for next time. Closing another tab removes it from the saved workspace.

## Command buttons

Click **Configure tab** at the bottom to add, edit, delete, or reorder that tab's buttons. Each row has a label and a Bash command. Double-click a cell to edit. You can change the tab name and startup folder here too. Changing the startup folder resets its remembered folder and applies when you restart that shell. The executable path is shared by all tabs and applies to new/restarted shells.

Examples:

| Label | Command |
| --- | --- |
| Project | `cd /c/Development/my-project` |
| Status | `git status --short --branch` |
| Tests | `python -m unittest discover -s tests` |
| Update | `git pull --ff-only` |

Commands run in the **tab's existing shell**, preserving its directory, variables, aliases, and shell functions. Commands support normal Bash syntax, including pipes and `&&`.

An interactive Bash init file loads `/etc/profile` followed by the first available `~/.bash_profile`, `~/.bash_login`, or `~/.profile`, then appends a directory-reporting hook to `PROMPT_COMMAND`. Existing prompt commands are preserved. This follows login startup-file order, but the shell itself runs with `--rcfile -i`, so Bash's `login_shell` flag is unset. User profile scripts that check that flag may behave differently. Commands are appended to Bash's configured history file at each prompt, so they survive normal app closure. Replacing `PROMPT_COMMAND` later in the session can disable directory tracking; restarting the shell reinstalls it.

Buttons send text followed by Enter to the active terminal, just like typing. Use them at an empty shell prompt: a running program, password prompt, or partially typed command will receive that input instead. There is no job queue or automatic idle detection in this first version.

- Type directly in the terminal; arrows, history, Tab, Ctrl+C, ANSI colours, and terminal resizing are forwarded.
- Select text with the mouse, then **Ctrl+Shift+C** to copy.
- **Ctrl+Shift+V** pastes from the clipboard. Multiline clipboard pastes require confirmation.
- `clear` clears the visible terminal; terminal scrollback holds up to 10,000 lines.
- Closing/restarting a shell ends the session. Stop long-running jobs first.

Settings are stored as JSON in `%APPDATA%\gitbasher\settings.json`. Changes save atomically. Buttons contain executable commands; only use commands you trust. Shell output and command history are not saved by the app; Bash itself may maintain its normal history file.

## Verify

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The Windows tests exercise a real ConPTY Git Bash session (persistent variables, working directory, resize), load the embedded terminal/WebChannel, and check directory reporting after `cd`. The portable tests cover configuration migration, prompt integration, independent tab command routing, tab closure, workspace restoration, and save failures.

Manual Windows acceptance checks: create and rename two tabs, give them different buttons and folders, then close and reopen the app. Confirm the active tab, tab order, folders (`pwd`), and buttons restore. Test a command in one tab while another is busy, `git log`/`less`, arrows, Tab, Ctrl+C, Unicode, selection/copy/paste, resizing, shell exit, and restart.

## Architecture and status

PySide6 supplies the native window and Qt WebEngine. Vendored xterm.js 5.5.0 and fit addon 0.10.0 render terminal output. QWebChannel connects the local terminal page to Python; pywinpty starts Git Bash using Windows ConPTY. No localhost server, browser tab, runtime CDN, or separate terminal window is used.

This is a source release. Configuration, migration, shell-hook, and Qt workspace tests were run in the authoring environment. Qt workspace tests use fake terminal processes to verify routing and restoration; Windows ConPTY and full terminal GUI smoke tests are included but have **not** been run there. No standalone `.exe` is included.

Third-party xterm.js/fit code is MIT licensed; see `gitbasher/assets/LICENSE`. PySide6/Qt and pywinpty retain their upstream licenses. Review those licenses before redistributing a packaged application.
