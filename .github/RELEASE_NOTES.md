BashDock 1.2 adds tab icons and compact tab overflow.

Tabs receive generic shape icons automatically. **Configure tab → Tab icon**
offers 36 bundled shapes and symbols. Icons are remembered with tabs, saved
workspaces, settings exports and backups. When tab labels no longer fit, the
bar switches to icons with full names in tooltips. Widening the window restores
labels; scroll arrows remain available when compact tabs also overflow.

Also included from 1.1: **Manage → Workspaces → Replace current**.

Leave it unchecked to add missing workspace tabs. Check it to replace the current
tabs, using the existing confirmation and backup. The mode is remembered across
launches; changing the toggle alone leaves running shells untouched.

New terminal views start with a dark background while loading, avoiding a white
flash when adding tabs or replacing a workspace. The background follows the
terminal's configured theme.

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
