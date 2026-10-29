BashDock 1.12.1 adds terminal search, quick font zoom, optional command timing, and more tab and command-button controls. These notes cover the changes since public release 1.6.8.

## Find text in terminal output

- Press **Ctrl+F** or choose **Manage → Find in terminal…** to open search in the active tab.
- Matches update as you type. Search ignores case, treats the query as literal text, and handles wrapped lines and Unicode.
- Use **Enter / Shift+Enter** or the arrow buttons for next / previous match. Navigation wraps at the end.
- **Escape** closes search and restores terminal focus without jumping to the bottom.
- Each tab keeps its own query for the session. Normal scrollback shows match counts and highlights up to 1,000 matches; alternate-screen programs can search their current screen.
- Search stays inside the terminal page. Queries are not sent to Bash, saved in settings, or included in diagnostic reports. Search highlights do not trigger automatic clipboard copying.

## Quick font zoom and shortcut reference

- **Ctrl++** (also **Ctrl+=**), **Ctrl+-**, and **Ctrl+0** increase, decrease, and reset the current tab’s font size. Matching actions are available under Settings.
- Zoom is temporary and independent for each tab, stays within 8–48 pixels, and resets to the tab’s configured size. It leaves saved preferences unchanged.
- **Help → Keyboard shortcuts…** lists the existing app, search, and command-editor keys in a read-only reference.
- **Check for updates…** now sits directly above **About BashDock…** in the bottom Help menu group.

## More tab icons and useful context menus

- Choose from 96 original generic tab icons, with live filtering by name and keywords.
- Right-click a tab to configure, rename, duplicate, open its folder in Explorer, copy its folder path, or close it.
- Middle-click a tab to close it using the existing shell-session confirmation behavior.
- Right-click a command button to edit, duplicate, move left/right, or delete it.
- Duplicating a tab preserves its configuration and opens a fresh shell. It does not copy running commands or connections.
- Explorer folder shortcuts correctly distinguish similarly named folders such as `bashdock` and `bashdock.com`.

## Optional command-button timing

- Enable **Show execution time** in an individual command button’s editor to show its elapsed time and exit status in that tab’s footer.
- Timing starts disabled for existing and new buttons. It applies to button scripts started at the local Bash prompt; additional input to a foreground program or remote session remains untimed.
- Timed scripts run in the existing shell, preserving directory and environment changes. Their implementation wrapper is kept out of the terminal and shell history, and the normal multiline prompt is restored afterward.
- Diagnostics continue to exclude command text, terminal output, clipboard contents, and search queries.

## Windows validation

The test runner isolates native terminal tests from the general Qt suite, reports WebEngine startup evidence on failures, and repeats command execution, timing, scrolling, zoom and search checks across the Git/Python compatibility matrix.

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
