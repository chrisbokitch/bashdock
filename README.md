# BashDock

A Python/Qt Windows desktop app with multiple Git Bash tabs and a custom command bar beneath each terminal.

Previously called GitBasher. The application, GitHub repository, Python package, and build output now use the BashDock name.

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
| `npm run package` | Compile and smoke-test the app, then create a portable ZIP, SHA-256 checksum, and build information in `release/`. |
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
git clone https://github.com/chrisbokitch/bashdock.git bashdock
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
- Use **Manage → Open external shell** to open a separate Git Bash window from the active tab's Git installation in its last reported current directory. This starts a fresh shell; it does not transfer running programs, unsaved environment changes, or scrollback. The external window stays open when BashDock closes. For deployment, open it first, close BashDock, then run `./copy.sh` there. If `git-bash.exe` is unavailable beside that installation, the configured Bash opens in a new Windows console instead.
- Double-click a tab to rename it, or use **Manage → Rename tab**.
- Drag tabs to reorder them. Use the tab's close button or **Ctrl+Shift+W** to close it.
- Each tab has its own configurable command bar at the **bottom**, immediately below its terminal.
- Names, tab order, selected tab, current folders, startup folders, and command buttons are saved automatically and restored at the next launch.
- A new tab starts in the selected tab's last reported folder with its own default buttons.

Restoring creates **fresh shells** in the remembered folders. Running programs, environment variables set during a session, and terminal scrollback are not restored. Working directories are reported at each shell prompt; if a job is still running when you close the app, the last reported folder is used. If a remembered folder has been removed, the configured startup folder is tried, then your home folder.

Existing version 0.1 settings migrate into the first tab automatically, including your custom buttons. Closing the last tab quits the application and remembers that tab for next time. Closing another tab removes it from the saved workspace.

The app-close confirmation includes **Don't show this again**. Check it and choose **Yes** to close without prompting next time. You can change this anytime under **Settings → Confirm before quitting**. This is an app-wide setting; tabs and folders are still saved before shells close. Confirmation starts enabled, and choosing **No** never changes the setting. Individual tab-close and shell-restart confirmations remain separate.

The **Manage** menu groups tab management and shell actions. **Settings → Configure current tab…** opens the same editor as the bottom command bar, including the shared Git Bash executable setting. **Help → About BashDock…** shows the app icon, current version, description, and a link to the GitHub repository.

**Settings → Terminal Defaults…** controls the default font family and size (8–48 pixels), text/background/cursor/selection colours, cursor shape and blinking, scrollback (0–100,000 lines), automatic copying of selected text, and right-click paste. Save applies to tabs using the defaults without restarting shells, and persists for future tabs and launches. Tabs with custom settings remain unchanged. Cancel leaves settings unchanged; Restore Defaults resets the dialog controls until you save. Reducing scrollback discards older lines. Copy-on-selection and right-click paste start disabled; Ctrl+Shift+C/V remain available, and multiline paste still requires confirmation. Mouse-aware terminal programs retain their right-click behaviour unless you hold Shift to paste. These settings affect BashDock's embedded terminals, not external Git Bash windows.

For a project or server-specific appearance, open **Configure tab → Terminal settings…**. **Use terminal defaults** starts checked for new and existing tabs. Uncheck it to customize that tab, save the terminal editor, then save Configure tab. The running terminal updates immediately after the tab is saved, without restarting its shell. Cancelling either editor discards the changes at that level. Recheck **Use terminal defaults** (or click **Use defaults**) to follow the current app defaults again. Each custom preset contains all terminal settings, so later default changes do not alter its font, colors, or interaction preferences. Custom presets stay with the tab through app restarts, saved workspaces, settings exports, imports, and recovery.

## Saved workspaces

Use **Manage → Workspaces → Configure…** to keep named groups of tabs for different projects. Saved workspaces also appear directly below Configure in that submenu; clicking one adds its missing tabs without closing existing shells. The list refreshes when the submenu opens, including after saving, renaming, deleting, or importing workspaces. With no saved workspaces, only Configure is shown.

- **Save selected tabs…** lets you name a workspace and check the current tabs to include. Tabs retain their visible order, names, startup/current folders, and command bars. The active tab is remembered when included; otherwise the first selected tab becomes active.
- **Open — add tabs** adds only saved tabs that are not already open and selects the workspace's saved active tab, whether existing or newly added. Existing tabs keep their running shells, names, edits, positions, and folders. Reopening the same workspace, or overlapping workspaces, does not create duplicate tabs.
- **Replace current tabs…** asks before closing current shells, backs up the current workspace, and opens the saved tabs. If the settings cannot be saved, existing shells stay open. Pre-replacement copies are stored as `backups/settings-before-workspace-*.json` under the settings folder.
- **Update from current tabs…** replaces a saved workspace with a new selection of current tabs after confirmation. **Rename…** and **Delete…** manage the saved entry; neither closes your open tabs. Workspace names must be unique.

Saved workspaces are reusable templates: editing an open tab does not update its saved workspace automatically. Use **Update from current tabs…** to capture those edits, including custom terminal presets. Terminal defaults, the Git Bash executable, window geometry, and quit-confirmation settings remain app-wide.

Each tab has a persistent random UUID, preserved across renaming, configuration edits, restarts, exports, and saved workspaces. Duplicate detection uses this ID, not the name: **New tab** always creates a separate identity, even if you give it the same name as another tab. Closing a saved tab allows it to be reopened from its workspace with that same ID. Existing settings receive IDs automatically; identical older saved/open profiles are linked where possible. Older tabs whose profiles differ cannot reliably be identified as the same tab and receive separate identities. **Replace current tabs…** still explicitly closes the current shells and starts the selected workspace fresh after confirmation.

Workspaces start fresh shell sessions. They preserve command buttons such as an SSH **Connect** button, but do not run those commands or reconnect SSH automatically. They are included in settings exports, imports, and automatic backups. Existing settings files start with an empty workspace library.

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

## Settings backup and recovery

- **Settings → Export settings…** saves your current tabs, command buttons, folders, terminal preferences, quit-confirmation preference, Git Bash path, and window geometry to a JSON file you choose. This includes recent changes that have not yet autosaved. Exports contain plain-text commands and local paths; store and share them accordingly.
- **Settings → Import settings…** validates an existing settings file before asking to replace your workspace. Confirmation closes the current shells and creates the imported tabs with fresh shell sessions. Only import files you trust. The import is saved before any shell is stopped; a save or backup failure leaves your existing shells open. Cancel changes nothing.
- **Settings → Restore automatic backup…** restores the previous valid saved settings from `%APPDATA%\bashdock\settings.json.bak`, using the same confirmation as an import. This is one rotating backup, not a full history. Identical saves do not rotate it.

Before an import or restore, BashDock also saves the current in-memory workspace to a separate `settings-before-import-*.json` file in `%APPDATA%\bashdock\backups`. These copies do not rotate; use **Import settings…** to restore one, and delete older copies yourself when no longer needed. This protects changes that had not yet autosaved.

If settings cannot be read at startup, a recovery dialog offers the automatic backup (when present), import, or starting fresh. Cancelling uses temporary defaults with autosaving paused. Replacing damaged settings preserves their original bytes in `backups\settings-damaged-*.json` and keeps the valid automatic backup. If the backup is also invalid, recovery reports the error and leaves the files untouched; choose another export or start fresh. Saving explicit tab changes can also replace the damaged settings after preserving them.

Backups restore configuration, not running commands, shell variables, terminal output, or scrollback. When moving an export to another computer, check the Git Bash executable and folder paths; missing folders fall back to the startup folder or your home folder.

## Verify

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The Windows tests exercise a real ConPTY Git Bash session (persistent variables, working directory, resize), load the embedded terminal/WebChannel, and check directory reporting after `cd`. The portable tests cover configuration migration, prompt integration, independent tab command routing, tab closure, workspace restoration, and save failures.

Manual Windows acceptance checks: create and rename two tabs, give them different buttons and folders, then close and reopen the app. Confirm the active tab, tab order, folders (`pwd`), and buttons restore. Test a command in one tab while another is busy, `git log`/`less`, arrows, Tab, Ctrl+C, Unicode, selection/copy/paste, resizing, shell exit, and restart.

## Automated Windows builds and releases

Pushes and pull requests to `main` run Windows tests and a locked Windows x64 package build in GitHub Actions. Download candidates from the successful run’s artifacts. Matching version tags create a draft GitHub Release after tests, compilation, and extracted-ZIP verification pass; publishing follows clean Windows VM acceptance. See [the release guide](docs/RELEASING.md) for exact steps, dependency updates, and the checklist.

## Architecture and status

PySide6 supplies the native window and Qt WebEngine. Vendored xterm.js 5.5.0 and fit addon 0.10.0 render terminal output. QWebChannel connects the local terminal page to Python; pywinpty starts Git Bash using Windows ConPTY. No localhost server, browser tab, runtime CDN, or separate terminal window is used.

The repository contains source and an automated Windows build/release workflow. Portable Qt workspace tests use fake terminal processes; the Windows workflow also exercises real ConPTY and Qt WebEngine and tests the packaged shell. Hosted-runner results and clean Windows VM acceptance should be checked for each release candidate. Compiled executables are distributed as build artifacts or GitHub Release assets rather than committed to the source tree.

## License

BashDock is free and open-source software under the **GNU General Public License,
version 3 only** (`GPL-3.0-only`). See [LICENSE](LICENSE), [COPYRIGHT](COPYRIGHT),
and the [licensing notes](docs/licensing/README.md). Personal and workplace use,
modification, and commercial redistribution are allowed under GPLv3. Distributed
covered derivatives must preserve GPL rights and provide corresponding source.
Using BashDock to develop an unrelated project does not make that project GPL.

Third-party components retain their own licenses. See
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). **Help → About BashDock → License
and notices…** displays the project license and dependency overview offline.

`npm run package` checks for a clean, committed checkout and matching runtime
versions **before compiling**, so the source archive matches the executable.
Runtime dependencies are pinned to the reviewed release sources; after pulling
a dependency change, run `npm run setup` to update your existing `.venv`.
A mismatch reports the installed and required versions and the repair command. In addition to the portable ZIP, checksum, and build
information, it produces the matching application source ZIP and dependency
source archives. Its first run downloads approximately 1.3 GB of Qt sources plus
smaller source packages; verified downloads are cached under `build/source-cache/`.
The application ZIP remains separate from these source downloads. Release builds
must use the versions in `requirements/windows-build.lock`; update source hashes
and notices deliberately when changing dependencies. See the release guide.

If sharing a build outside GitHub, provide its matching source assets and
checksums from the same download location. A link to a private repository is
insufficient. No repository visibility change is required for private testing
when recipients receive the source assets too.

## Automatic updates

Compiled Windows builds support signed stable-release updates, background
downloads, and a yellow **Version X is ready — Restart to update** footer action
beside the current version. Restarting requires confirmation and saves your
workspace before closing shell sessions. The independent helper keeps the prior
installation until the new version acknowledges startup and restores it if
startup fails. Preview runs do not update the source checkout.

Use **Help → Check for updates…** and **Settings → Updates** for automatic checks
and downloads. Public updates need the one-time signing-key setup described in
[the update guide](docs/AUTO-UPDATES.md); the initial development key is
unconfigured. Full signed-update VM validation is required before 1.0. See the
[current 1.0 roadmap](docs/ROADMAP-1.0.md).
