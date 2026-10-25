# BashDock

A Python/Qt Windows desktop app with multiple Git Bash tabs and a custom command bar beneath each terminal.

Previously called GitBasher. The GitHub repository is still named `chrisbokitch/gitbasher`; the application, Python package, and build output are now named BashDock.

## Updating from GitBasher

Close the app and pull the latest source before renaming your checkout to `C:\Development\bashdock`. Run `npm run setup` from the renamed folder to refresh the editable Python installation and create the `bashdock` launcher, then use `npm run preview`. If a moved virtual environment reports path errors, delete `.venv` and run `npm run setup` again to recreate it.

On first launch, if BashDock has no settings yet, it imports and validates `%APPDATA%\gitbasher\settings.json`, saving a copy to `%APPDATA%\bashdock\settings.json`. Existing tabs, folders, command bars, selected tab, and preferences are preserved. The original file stays intact; subsequent launches use BashDock's settings.

Local `copy.sh`/`copy.bat` helpers remain ignored. Update their source to `C:\Development\bashdock\dist\bashdock` and destination to `C:\Development\tools\bashdock`, and update any executable checks or shortcuts to `bashdock.exe`. Copy the complete build folder, including `_internal`. Existing deployed GitBasher builds are not removed automatically.

## Requirements

- Windows 10 (1809 or newer) or Windows 11
- Python 3.11 or newer (64-bit; Python 3.12/3.13 recommended)
- [Git for Windows](https://gitforwindows.org/)
- Node.js 20+ and npm for the shortcut commands below (the app itself is Python)

## Everyday npm commands

Run these from the project folder in Git Bash or PowerShell:

| Command | Action |
| --- | --- |
| `npm test` or `npm run test` | Run the Python test suite in `.venv`. |
| `npm run go` | Run `git pull --ff-only`, then the test suite. A failed pull stops the command. |
| `npm run preview` | Launch the desktop app from source using `.venv`. Close and relaunch to pick up edits. |
| `npm run compile` | Install optional build tools and package the Windows app with PyInstaller. |
| `npm run setup` | Create `.venv` if missing and install/update the Python project and dependencies. |

Your existing `.venv` works with these commands. No activation or `npm install` is required: there are no JavaScript dependencies. For a fresh clone, run `npm run setup` once, then `npm run preview`.


The executable build must run **on Windows**. Output is `dist/bashdock/bashdock.exe`. Keep the entire `dist/bashdock` folder together when copying it; the `_internal` folder includes Python, Qt WebEngine, and other runtime files. Python and Node are not required to run the built app, but Git for Windows must still be installed. This creates a runnable app folder rather than an installer.

Quit the built app before rebuilding it, so Windows can replace its files. Build output is ignored by Git. The Windows executable build still needs validation on Windows.

The executable and app window use the BashDock terminal-and-buttons icon. Its PNG artwork and multi-size Windows `.ico` are in `bashdock/assets/`. Rebuild with `npm run compile` to embed the icon in the executable.

`compile` explicitly bundles pywinpty's native DLLs and helper executables, then launches the **built executable** to check that Git Bash accepts a command and returns output. Compilation fails if that check fails; its report is at `build/packaged-shell-smoke.json`. The check briefly starts a shell and loads your usual Bash profile scripts. Close other copies of the built app before rebuilding.

If a shell cannot start, the app shows the error. Startup and terminal-reader errors are also recorded in `%APPDATA%\bashdock\bashdock.log`, including when the executable runs without a console window.

## Versioning

BashDock uses `MAJOR.MINOR.PATCH`. While pre-1.0, patch releases cover fixes and UI polish; minor releases cover new features or substantial changes. We will choose the 1.0 milestone explicitly. Versions are deliberate release decisions, not automatic commit counters; bump the patch for a new shipped revision rather than silently changing an already distributed version.

`package.json` is the version source. Use npm's standard commands when deciding a new version:

```bash
npm version patch --no-git-tag-version  # e.g. 0.3.0 -> 0.3.1
npm version minor --no-git-tag-version  # e.g. 0.3.1 -> 0.4.0
```

These update `package.json`, `package-lock.json`, and the generated `bashdock/_version.py`. Commit those files together. Python package metadata, the footer, and the compiled app use the generated module; they do not need Git or npm installed at runtime. Tests, preview, and compilation check that the version files agree. Rebuild the executable after changing a version. These commands do not create Git commits or tags.

The darker blue footer always starts with the version, followed by status/error messages. An empty message leaves the version visible.

## Run from source

Open PowerShell and clone the project into `C:\Development\bashdock`:

```powershell
New-Item -ItemType Directory -Force C:\Development | Out-Null
Set-Location C:\Development
git clone https://github.com/chrisbokitch/gitbasher.git bashdock
Set-Location .\bashdock
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\bashdock.exe
```

The editable install picks up source edits without reinstalling. Virtual environment activation is optional; these commands use its executables directly and do not require changing PowerShell execution policy.

To launch it again later:

```powershell
Set-Location C:\Development\bashdock
.\.venv\Scripts\bashdock.exe
```

To update your checkout and dependencies:

```powershell
Set-Location C:\Development\bashdock
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e .
```

Git Bash is detected in common installation locations. If detection fails, open **Configure tab** and choose `C:\Program Files\Git\bin\bash.exe` (or your installation's equivalent). Use `bash.exe`, not `git-bash.exe`: the latter launches a separate terminal window.

## Tabs and remembered workspace

- Use **+ New tab** or **Ctrl+Shift+T** for an independent Git Bash shell.
- Use **Open External**, to the right of **+ New tab**, to open a separate Git Bash window from the active tab's Git installation in its last reported current directory. This starts a fresh shell; it does not transfer running programs, unsaved environment changes, or scrollback. The external window stays open when BashDock closes. For deployment, open it first, close BashDock, then run `./copy.sh` there. If `git-bash.exe` is unavailable beside that installation, the configured Bash opens in a new Windows console instead.
- Double-click a tab to rename it, or use **Session → Rename tab**.
- Drag tabs to reorder them. Use the tab's close button or **Ctrl+Shift+W** to close it.
- Each tab has its own configurable command bar at the **bottom**, immediately below its terminal.
- Names, tab order, selected tab, current folders, startup folders, and command buttons are saved automatically and restored at the next launch.
- A new tab starts in the selected tab's last reported folder with its own default buttons.

Restoring creates **fresh shells** in the remembered folders. Running programs, environment variables set during a session, and terminal scrollback are not restored. Working directories are reported at each shell prompt; if a job is still running when you close the app, the last reported folder is used. If a remembered folder has been removed, the configured startup folder is tried, then your home folder.

Existing version 0.1 settings migrate into the first tab automatically, including your custom buttons. Closing the last tab quits the application and remembers that tab for next time. Closing another tab removes it from the saved workspace.

The app-close confirmation includes **Don't show this again**. Check it and choose **Yes** to close without prompting next time. You can change this anytime under **Session → Confirm before quitting**. This is an app-wide setting; tabs and folders are still saved before shells close. Confirmation starts enabled, and choosing **No** never changes the setting. Individual tab-close and shell-restart confirmations remain separate.

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

Settings are stored as JSON in `%APPDATA%\bashdock\settings.json`. Changes save atomically. Buttons contain executable commands; only use commands you trust. Shell output and command history are not saved by the app; Bash itself may maintain its normal history file.

## Verify

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The Windows tests exercise a real ConPTY Git Bash session (persistent variables, working directory, resize), load the embedded terminal/WebChannel, and check directory reporting after `cd`. The portable tests cover configuration migration, prompt integration, independent tab command routing, tab closure, workspace restoration, and save failures.

Manual Windows acceptance checks: create and rename two tabs, give them different buttons and folders, then close and reopen the app. Confirm the active tab, tab order, folders (`pwd`), and buttons restore. Test a command in one tab while another is busy, `git log`/`less`, arrows, Tab, Ctrl+C, Unicode, selection/copy/paste, resizing, shell exit, and restart.

## Architecture and status

PySide6 supplies the native window and Qt WebEngine. Vendored xterm.js 5.5.0 and fit addon 0.10.0 render terminal output. QWebChannel connects the local terminal page to Python; pywinpty starts Git Bash using Windows ConPTY. No localhost server, browser tab, runtime CDN, or separate terminal window is used.

This is a source release with an executable build recipe. Configuration, migration, shell-hook, and Qt workspace tests were run in the authoring environment. Qt workspace tests use fake terminal processes to verify routing and restoration; Windows ConPTY, full terminal GUI smoke tests, and the packaged executable have **not** been run there. No prebuilt `.exe` is included.

Third-party xterm.js/fit code is MIT licensed; see `bashdock/assets/LICENSE`. PySide6/Qt and pywinpty retain their upstream licenses. Review those licenses before redistributing a packaged application.
