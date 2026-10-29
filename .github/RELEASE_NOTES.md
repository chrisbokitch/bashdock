BashDock 1.6.8 makes the download smaller, cleans up old update backups, and polishes tab controls and keyboard focus.

## Smaller downloads

- Keep the independent updater free of unnecessary Qt rendering dependencies.
- Omit five WebEngine debug resources from release builds, while retaining the release resources, translations, QML, and developer tools.
- Together these changes reduce the 1.6.8 ZIP by 19.3% compared with 1.6.0: from 267.61 MiB to 215.94 MiB. The attached ZIP is 226,427,474 bytes; use its matching checksum file to verify your download.
- Add checks for the updater's frozen dependencies and real packaged terminal rendering at 100%, 125%, and 150% scaling, repeated after ZIP extraction.

## Update backup cleanup

After a successful update, BashDock cleans up older backups that its update journals identify as safe to remove, retaining the latest healthy rollback copy for that installation. In-use files are retried later. Unrecognized folders and unfinished or failed update transactions are left for recovery or review.

## Tab controls and focus

- Move New tab directly after the tabs, with a small borderless circular + that brightens on hover or keyboard focus. It stays accessible when tabs overflow.
- Center the + precisely and leave a small gap above the terminal border.
- Restore terminal typing focus when opening a new tab and when closing a tab.

## Test reliability

Contain packaged Windows rendering probes in isolated process jobs so console and shell descendants cannot retain temporary folders after a probe exits.

Synchronize the interactive Ctrl+C test with foreground-job startup, removing a timing gap in the test. Repeat its interruption and recovery checks across the Windows Git/Python compatibility matrix, and include terminal state in prompt timeout failures.

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
