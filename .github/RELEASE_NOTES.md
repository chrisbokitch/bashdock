BashDock 1.13.4 adds personal command preset groups, clearer button confirmations, and a few tab and editor refinements. These notes cover changes since public release 1.12.1.

## Personal command preset groups

- Create and edit your own groups in **Manage preset groups…** alongside the built-in groups.
- Import and export groups to share them or keep a backup. Review imported commands before applying them to a tab, especially commands from someone else.
- **Create group from current tab…** in the group manager copies that tab's configured buttons into a new personal group.
- Optional button descriptions now appear in **Edit command button**. They carry through preset application and group creation, and appear as hover help on command buttons and in the tab configuration list.

## Button and tab polish

- Buttons requiring confirmation now show the button label as the dialog title and the configured confirmation message prominently. **Show command** reveals the scrollable script when you want to inspect it.
- Clock and bell markers in the tab configuration list identify buttons with execution timing and confirmation enabled. Both markers appear before the command text.
- Closing the last tab asks for confirmation before closing BashDock, without a second exit prompt.
- Terminal focus returns after closing the Manage menu so the next typed character reaches the shell.

## Install and update

Download the Windows x64 ZIP, extract the complete `bashdock` folder, and run `bashdock.exe`. Git for Windows must be installed; Python and Node are not required. Check the ZIP using the accompanying `.sha256` file. The application source and matching dependency source archives are separate release assets.

The Windows executables are not Authenticode-signed. Automatic-update metadata is signed separately and verified by BashDock. BashDock is licensed under GNU GPL version 3 only; see the bundled notices and source information for third-party components. Window restoration starts fresh shells rather than restoring running commands or remote connections.
