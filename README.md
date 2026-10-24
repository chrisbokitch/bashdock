# gitbasher

A Python/Qt Windows desktop app that embeds a persistent Git Bash session, with your own command buttons across the top.

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

Git Bash is detected in common installation locations. If detection fails, open **Configure** and choose `C:\Program Files\Git\bin\bash.exe` (or your installation's equivalent). Use `bash.exe`, not `git-bash.exe`: the latter launches a separate terminal window.

## Command buttons

Click **Configure** to add, edit, delete, or reorder buttons. Each row has a label and a Bash command. Double-click a cell to edit. The startup folder and executable can be changed here too; those changes take effect after **Session → Restart shell**.

Examples:

| Label | Command |
| --- | --- |
| Project | `cd /c/Development/my-project` |
| Status | `git status --short --branch` |
| Tests | `python -m unittest discover -s tests` |
| Update | `git pull --ff-only` |

Commands run in the **existing shell**, preserving its directory, variables, aliases, and shell functions. Bash startup files are loaded with `--login -i`. Commands support normal Bash syntax, including pipes and `&&`.

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

The Windows tests exercise a real ConPTY Git Bash session (persistent variables and working directory, resize) and load the embedded terminal/WebChannel. Other systems run configuration tests and skip Windows integration tests.

Manual Windows acceptance checks: click Project then type `pwd`; run Status; test `git log`/`less`, arrows, Tab, Ctrl+C, Unicode, selection/copy/paste, a window resize, settings persistence, shell exit, and restart. Review button behavior in your usual interactive tools before relying on it.

## Architecture and status

PySide6 supplies the native window and Qt WebEngine. Vendored xterm.js 5.5.0 and fit addon 0.10.0 render terminal output. QWebChannel connects the local terminal page to Python; pywinpty starts Git Bash using Windows ConPTY. No localhost server, browser tab, runtime CDN, or separate terminal window is used.

This is a first source release. Configuration tests were run in the authoring environment. Windows shell and GUI smoke tests are included but have **not** been run there. No standalone `.exe` is included. Tabs, command shortcuts, profiles, job tracking, installer, and executable packaging can follow after Windows acceptance testing.

Third-party xterm.js/fit code is MIT licensed; see `gitbasher/assets/LICENSE`. PySide6/Qt and pywinpty retain their upstream licenses. Review those licenses before redistributing a packaged application.
