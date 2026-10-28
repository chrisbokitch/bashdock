BashDock 1.6 improves command buttons with multiline editing, optional confirmation prompts, and curated presets.

## Multiline command editor

Configure tab now opens a dedicated editor for a button's label and command body.
Write multiple lines with indentation, blank lines, quotes and Unicode, including
Bash loops, functions, continuation lines and heredocs. Commands run in the tab's
existing shell and retain its directory and environment. Bash syntax controls
whether later commands run after a failure; there is no automatic stop-on-error.

Use Add / Edit…, double-click a row, or press F2/Enter. Enter adds a line, Tab
inserts indentation, and Ctrl+Tab moves focus out of the command body. Save in the
editor stages changes until Configure tab is saved; Cancel discards staged edits.

## Confirm before using

Each command button can request confirmation with a custom message, defaulting
to “Are you sure?”. The message field is disabled until confirmation is enabled.
The execution prompt shows the message, button label, target tab and exact
command. Cancel is the default; Run command submits the reviewed command once
to the reviewed shell. Existing buttons keep confirmation off unless enabled.

Confirmation settings stay with buttons in saved workspaces, settings exports,
imports and backups. Editing, applying or restoring definitions never runs them.

## Command presets

Configure tab → Presets… offers 18 editable starter buttons in five groups:

- Git essentials
- Git recovery / AI Rescue
- Python / Backend
- Web / Node
- Docker Compose

Choose individual buttons or all new buttons in a group. Review exact commands,
required tools and confirmation messages before applying. Presets append by
default; replacement previews the removed buttons and requires confirmation.
Exact label-and-command duplicates are marked Already added and skipped by
Select all new buttons, with explicit duplicate selection still available.

Applying only stages ordinary editable buttons in Configure tab. Save keeps them;
Cancel preserves the existing buttons. Presets do not install tools. Commands
that discard, overwrite or stop work have confirmation enabled by default, with
specific messages that remain editable.

## Fixes and validation

- Preserve literal tabs in button commands with standard Bash Readline bindings.
- Fix Ctrl+Tab navigation from the command editor on Windows.
- Close the HTTPS response when rejecting an insecure update redirect, avoiding
  an unclosed response without weakening certificate or redirect verification.
- Improve Windows test cleanup and cover confirmation, preset persistence,
  cancellation, keyboard access and short-window layout across Python versions.

Download the Windows x64 ZIP, extract the complete `bashdock` folder, and run `bashdock.exe`. Git for Windows must be installed; Python and Node are not required.

The `.sha256` file verifies the ZIP. Build information records the source commit and dependency versions.

The Windows executables are not Authenticode-signed. Update metadata is signed
separately and verified by the updater. Window restoration starts fresh shells;
it does not restore running commands or remote connections.


BashDock is licensed under GNU GPL version 3 only. Third-party components keep
their own licenses; see `LICENSE`, `COPYRIGHT`, `THIRD-PARTY-NOTICES.md`, and
`licenses/` and `third-party-licenses.zip` in the app folder. The archive contains
the complete detailed notices and a hash index; open it in File Explorer or from
Help → About → License and notices. `SOURCE.txt` identifies matching source archives.

The application source ZIP and Qt, PySide, pywinpty, and Rust dependency source
archives are attached separately beside the executable ZIP. You do not need
these archives to run the app. `bashdock-VERSION-SHA256SUMS.txt` (with the release
version in its filename) checks all release assets. Preserve source access and
notices when redistributing.


Signed releases include `bashdock-update.json` and `bashdock-update.sig` for the
app's automatic updater. These are additional metadata assets, not application
or source downloads.
