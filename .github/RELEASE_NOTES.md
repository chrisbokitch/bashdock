Download the Windows x64 ZIP, extract the complete `bashdock` folder, and run `bashdock.exe`. Git for Windows must be installed; Python and Node are not required.

The `.sha256` file verifies the ZIP. Build information records the source commit and dependency versions.

Before publishing this draft, complete the clean Windows VM acceptance checklist in `docs/RELEASING.md`. These executables are currently unsigned.


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
or source downloads. Before publishing, complete the actual update/rollback
checks in `docs/AUTO-UPDATES.md` and confirm the public signing key was configured
before building this candidate.
