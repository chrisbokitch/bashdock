BashDock 1.14.0 adds an interrupt instruction to command buttons. These notes cover changes since public release 1.13.4.

## Interrupt from a button

- Put `<<interrupt>>` on its own line in a button's Bash command to send Ctrl+C to the active terminal.
- Put a Bash command on the next line to run it after the interrupted program returns to the local shell prompt. For example, a button can stop a development server and restart it.
- A button containing only `<<interrupt>>` can interrupt a foreground program, including one in an interactive or remote session. Following commands wait for the local Bash prompt, so they do not automatically run inside a remote session.
- The marker must use the exact spelling shown above. Existing button settings and presets need no migration.

## Install and update

Download the Windows x64 ZIP, extract the complete `bashdock` folder, and run `bashdock.exe`. Git for Windows must be installed; Python and Node are not required. Check the ZIP using the accompanying `.sha256` file. The application source and matching dependency source archives are separate release assets.

The Windows executables are not Authenticode-signed. Automatic-update metadata is signed separately and verified by BashDock. BashDock is licensed under GNU GPL version 3 only; see the bundled notices and source information for third-party components.
