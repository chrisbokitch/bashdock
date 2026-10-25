# Building and releasing BashDock

## What happens automatically

Every push to `main`, pull request to `main`, and manual **Actions → Windows build and release → Run workflow** runs on a fresh Windows Server 2022 x64 runner:

1. Install CPython 3.12 and Node 24.
2. Check the version files; a `v*` tag must match the app version exactly.
3. Install the exact Windows wheels in `requirements/windows-build.lock`, checking SHA-256 hashes. Install the local project without re-resolving dependencies or using an isolated build environment.
4. Run Python tests, real Windows ConPTY/WebEngine integration tests, and JavaScript tests. The isolated Bash prompt-hook test also runs with Git for Windows.
5. Compile with PyInstaller and run the built executable's shell smoke test.
6. ZIP the complete application, including `_internal`, and record its source commit, Python, OS, Git, dependency versions, and lock-file hash.
7. Verify the ZIP checksum, extract into a path containing spaces, and run the extracted executable with fresh app settings.
8. Upload `bashdock-windows-x64` and build diagnostics to that workflow run. Artifacts are retained for 14 days.

Download the artifact from the completed run's **Artifacts** section. Extract the downloaded artifact wrapper to get the actual distributable ZIP, `.sha256`, and build-info JSON. Extract that ZIP to run the app.

GitHub Actions versions are pinned by commit SHA. Python/Node patch versions, runner images, and the installed Git version can change; their actual versions are recorded where relevant. This is a controlled dependency build, not a promise of byte-for-byte identical binaries. Hosted Windows Server testing complements the clean Windows 11 VM; it does not replace it.

## Preparing a release

Choose a SemVer version deliberately. Fixes and polish increment PATCH; features increment MINOR while pre-1.0. Version changes use the existing npm lifecycle to update all three version files:

```bash
npm version patch --no-git-tag-version
# Or npm version minor --no-git-tag-version
npm test
```

Commit the source and version files, push, and wait for the Windows workflow to pass. Only tag the intended committed revision. For example, if `package.json` says `0.6.4`:

```bash
git pull --ff-only
git status --short
# Ensure the worktree is clean and HEAD is the tested commit.
git tag -a v0.6.4 -m "BashDock 0.6.4"
git push origin v0.6.4
```

The tag rebuilds and validates that exact revision, then creates a **draft GitHub Release** with the ZIP, checksum, build details, and generated change notes. No public release is created automatically. An existing draft can have its assets refreshed by rerunning the same tag workflow; an already published release is never overwritten. Do not move published tags or reuse a published version for different binaries.

The workflow uses GitHub's built-in token; no personal access token is required. Actions must be enabled for the repository and allowed by any organization policy. The build job has read-only contents access; only the tag's draft-release job receives contents-write access.

## Validate the draft before publishing

Download the ZIP attached to the draft and test that exact file on the clean Windows VM:

- Start without Git installed: check the missing-Git guidance.
- Install Git for Windows, then launch from a standard user account without Python or Node installed.
- Create, rename, cancel rename, reorder, switch, and close tabs; verify close icons stay in place.
- Give tabs different commands and folders, then close/reopen and check restoration.
- Save a subset of tabs as a workspace. Add it without closing existing shells, then replace current tabs after confirmation. Check tab order, active tab, folders, command bars, independent copies, update/rename/delete, and settings export/import. A saved SSH button must not connect automatically.
- Exercise typing, arrows, completion, Ctrl+C, Unicode, and pagers such as `git log`/`less`.
- Check selection, copy/paste, multiline confirmation, and optional mouse behaviour.
- Change terminal settings, verify every tab updates, and verify settings survive reopening.
- Export settings, change tab names/buttons, then import the export; confirm the restored workspace and the separate pre-import backup. Cancel an import and try an invalid file; existing shells must remain open.
- In the disposable VM, close BashDock, damage `%APPDATA%\bashdock\settings.json`, and relaunch. Restore the automatic backup and confirm the damaged file is preserved in the `backups` folder. Also check cancelling recovery and starting fresh.
- Open an external shell in the expected folder; confirm it survives closing BashDock.
- Resize/maximize and inspect at 100%, 125%, and 150% scaling.
- Check quit confirmation and the saved opt-out setting; confirm embedded shells stop on exit.

Record the tag, source commit, ZIP SHA-256, Windows version, scaling, and results in a release-testing issue. After acceptance, review the draft notes and click **Publish release**. The executables are unsigned; signing is a separate release improvement. Project licensing and dependency notices still need their own review before the public open-source launch.

## Verify a downloaded ZIP in Git Bash

Keep the ZIP and matching checksum file together, then run:

```bash
sha256sum -c bashdock-0.6.4-windows-x64.sha256
```

On PowerShell, `Get-FileHash .\bashdock-0.6.4-windows-x64.zip -Algorithm SHA256` displays the value for comparison.

## Local packages

`npm run package` compiles, checks the built shell, and writes a ZIP/checksum/build-info bundle under ignored `release/`. Local builds use the existing developer environment; official release candidates should come from CI's locked environment.

To recreate the release dependency environment locally, use a fresh **Python 3.12 x64** virtual environment and:

```bash
.venv/Scripts/python.exe -m pip install --require-hashes --only-binary=:all: -r requirements/windows-build.lock
.venv/Scripts/python.exe -m pip install --no-deps --no-build-isolation -e .
BASHDOCK_LOCKED_BUILD=1 npm run package
.venv/Scripts/python.exe scripts/verify_release.py
```

`BASHDOCK_LOCKED_BUILD=1` prevents compile from installing newer dependencies and checks dependency consistency. It does not itself install the lock file. `npm run setup` remains the normal developer setup command.

## Updating dependencies

Update the lock deliberately, using CPython 3.12 on Windows x64. Resolve all runtime/build dependencies and include the SHA-256 of each selected wheel. Retain `--require-hashes` and `--only-binary=:all:` installation in CI. Validate the complete Windows workflow and VM checklist after updates; do not copy hashes from an unrelated platform or Python ABI.
