BashDock 1.0 brings persistent Git Bash tabs, per-tab command buttons and saved
workspaces to Windows.

- Restore tabs, folders, command bars and window geometry in fresh shell sessions.
- Set terminal defaults and independent per-tab appearance overrides.
- Export/import settings and recover from backups.
- Copy/paste with multiline confirmation, jump to the bottom of terminal output,
  and open an independent external Git Bash window.
- Install verified, signed automatic updates after confirming restart, with
  startup checks and rollback protection. Developers can stage local builds.
- Export diagnostic reports without command text, terminal output or clipboard
  contents.

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
