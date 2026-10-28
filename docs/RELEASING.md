# Building and releasing BashDock

## What happens automatically

Every push to `main`, pull request to `main`, and manual **Actions → Windows build and release → Run workflow** runs on a fresh Windows Server 2022 x64 runner:

1. Install CPython 3.12 and Node 24.
2. Check the version files; a `v*` tag must match the app version exactly.
3. Install the exact Windows wheels in `requirements/windows-build.lock`, checking SHA-256 hashes. Install the local project without re-resolving dependencies or using an isolated build environment.
4. Run Python tests, real Windows ConPTY/WebEngine integration tests, and JavaScript tests. The isolated Bash prompt-hook test also runs with Git for Windows.
5. Compile with PyInstaller and run the built executable's shell smoke test.
6. Assemble project/dependency licenses and attribution files from the exact source releases and installed packages. Download and hash-check dependency sources, create a clean committed application source ZIP, and mirror dependency source archives as separate release assets. ZIP the application with `_internal`, license/source information, and frozen-file hashes; record build provenance.
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

This section is the reusable procedure, not a ledger of unfinished work. See
[ACCEPTANCE-1.0.md](ACCEPTANCE-1.0.md) for completed evidence and the remaining
M1–M9/U1–U7 checks. Preserve recorded historical passes; select outstanding cases
and retests warranted by the candidate's changes. A new candidate still needs
its own identity/checksum and final smoke result (F1–F3).

For a small UI update with unchanged dependencies and updater/install behavior,
use a focused release check: passing Windows CI and compatibility jobs, owner
checks of the changed UI, and a short smoke of the exact draft ZIP (checksum,
launch/version, typed and button commands, changed UI, close/reopen). Record the
selected scope and package identity. Do not repeat the entire 1.0 clean-VM,
recovery and updater failure matrix unless relevant changes warrant it. Keep
the signed metadata, asset/source inventory and public download checks.

Download the ZIP attached to the draft and test that exact file on the clean Windows VM:

- Start without Git installed: check the missing-Git guidance.
- Install Git for Windows, then launch from a standard user account without Python or Node installed.
- Create, rename, cancel rename, reorder, switch, and close tabs; verify close icons stay in place.
- Give tabs different commands and folders, then close/reopen and check restoration.
- Save a subset of tabs as a workspace. Add it without closing existing shells, then replace current tabs after confirmation. Check tab order, active tab, folders, command bars, independent copies, update/rename/delete, and settings export/import. A saved SSH button must not connect automatically.
- Exercise typing, arrows, completion, Ctrl+C, Unicode, and pagers such as `git log`/`less`.
- Check selection, copy/paste, multiline confirmation, and optional mouse behaviour.
- Change Terminal Defaults, verify inheriting tabs update, and verify settings survive reopening.
- Give one tab custom terminal settings through Configure tab. Change Terminal Defaults and confirm only inheriting tabs update. Return the custom tab to defaults, verify neither operation restarts shells, and check cancel/save failure behavior and preset restoration through workspaces and settings export/import.
- Export settings, change tab names/buttons, then import the export; confirm the restored workspace and the separate pre-import backup. Cancel an import and try an invalid file; existing shells must remain open.
- In the disposable VM, close BashDock, damage `%APPDATA%\bashdock\settings.json`, and relaunch. Restore the automatic backup and confirm the damaged file is preserved in the `backups` folder. Also check cancelling recovery and starting fresh.
- Open an external shell in the expected folder; confirm it survives closing BashDock.
- Resize/maximize and inspect at 100%, 125%, and 150% scaling.
- Check quit confirmation and the saved opt-out setting; confirm embedded shells stop on exit.

Record the tag, source commit, ZIP SHA-256, Windows version, scaling, and results in a release-testing issue. After acceptance, review the draft notes and click **Publish release**. The executables are unsigned; signing is a separate release improvement. GPLv3 is adopted. Before publishing, verify that all source assets and notices described below are attached and accessible to every binary recipient.

## Verify a downloaded ZIP in Git Bash

Keep the ZIP and matching checksum file together, then run:

```bash
sha256sum -c bashdock-0.6.4-windows-x64.sha256
```

Checksum lists use UTF-8 with LF line endings so this command works in Git Bash
on Windows without converting the downloaded file.

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

## License and source release checks

The project is GPL-3.0-only. `npm run package` refuses an uncommitted checkout:
commit changes before packaging so `git archive HEAD` describes the binary's
application source. Local ignored deployment helpers and settings are excluded.
The source ZIP includes the exact commit ID, build scripts, workflow, lock file,
original assets, license, and documentation. Build and release from that revision.

Each release must include:

- The Windows application ZIP, its `.sha256`, and build-info JSON.
- `bashdock-VERSION-source.zip` from the matching source commit.
- Matching Qt and PySide source `.tar.xz` archives, pywinpty source `.tar.gz`,
  and the ZIP of Rust crate sources pinned by pywinpty's Cargo.lock.
- `bashdock-VERSION-SHA256SUMS.txt` covering all these assets.

The first package run downloads about 1.3 GB of Qt sources plus smaller sources;
verified copies are reused from `build/source-cache/`. Separate source assets
keep the app download small and work with a private repository. Do not publish
only the executable ZIP or rely on a private commit URL for source access.

Inspect `licenses/manifest.json`, `licenses/runtime-files.json`, full license
texts/notices, and `SOURCE.txt` in the **actual Windows ZIP**. Detailed source and Python-package notices are bundled in
`third-party-licenses.zip`; the archive retains their `licenses/` paths and
contains `INDEX.json` with a SHA-256 for every notice. Source-derived notice
names are shortened for Windows path compatibility; source-specific `.index.json`
files inside the archive map them to their original paths. Principal license
texts, CPython and xterm licenses, and release metadata remain directly accessible
in `licenses/`. Help → About → License and notices opens the detailed archive
in File Explorer without extracting it during installation. Packaging and ZIP
verification read every archived notice and verify the complete index before
accepting a release. Source collections deliberately include some
optional components and build tools. Recheck new dependencies and native DLLs
when updating the lock or Python version. See `docs/licensing/README.md`.

Run `scripts/verify_release.py` with all assets present: it checks required
license/source files, source-asset hashes, and the extracted executable. Before
publishing a draft, download all its assets and run `sha256sum -c
bashdock-VERSION-SHA256SUMS.txt`; confirm source downloads work with the same
access as the executable. For public launch, check anonymously, not only as the
repository owner. Retain released source assets alongside the binaries.

The app's About dialog exposes GPLv3 and the dependency overview without a
network connection. Test this in the VM. Third-party rights, including LGPL
modification/replacement rights, must remain intact; libraries are dynamically
loaded and builds do not enforce signing or activation.

Repository visibility is independent of the license. Keep it private during
preparation if desired. Before making it public, review history, personal data,
secrets, and Actions logs/artifacts. Under repository **Settings → General →
Danger Zone → Change repository visibility**, select public and follow GitHub's
confirmation steps. Making the repository public does not publish a draft
release automatically; review and publish the release separately.

## Publisher prerequisite: Microsoft runtime

The pinned Windows Qt wheel contains MSVCP/VCRUNTIME DLLs. Before publishing a
binary release, the publisher must confirm eligibility under Microsoft's Visual
Studio / Visual C++ redistributable terms. This is not granted by GPLv3 or by
adding notices. Microsoft's documentation limits redistribution of the package
and individual binaries to licensed Visual Studio users:
<https://learn.microsoft.com/en-us/cpp/windows/redistributing-visual-cpp-files>.
Record this confirmation in the release-testing issue. This owner-side license
entitlement is not verified by CI. BashDock's owner confirmation and runtime
inventory review are already recorded in
[issue #1](https://github.com/chrisbokitch/bashdock/issues/1) and summarized as E5
in [ACCEPTANCE-1.0.md](ACCEPTANCE-1.0.md). Do not reopen the unchanged dependency
baseline as unconfirmed; review relevant runtime/dependency changes. A new
publisher must establish their own applicable entitlement.

The Qt wheel also contains Mesa llvmpipe (Mesa 11.2.2 / LLVM 3.6.2, identified in
the actual DLL). Its standalone MIT/Boost/NCSA notices are included separately
because the binary's Mesa/LLVM sources are not part of qt-everywhere.

## Packaging prerequisites and runtime mismatch recovery

`npm run package` checks the Git checkout and runtime versions before starting
compilation. Dirty-checkout errors list the affected paths; keep local helpers
ignored rather than committing them. The checks run again during packaging.

Setup pins PySide6/Qt and pywinpty to the versions in the reviewed source
manifest. If an older development environment has different versions, run:

```bash
npm run setup
npm test
npm run package
```

This updates the existing virtual environment in place. There is no need to
delete settings, tabs, source caches, or `.venv`. Runtime version errors show
installed and expected values. Official CI still uses Python 3.12 x64 and the
complete hash-locked build environment described above. Update the runtime pins,
Windows lock, matching source archives, and native notices together when
intentionally updating dependencies.

## Automatic-update release assets

See [AUTO-UPDATES.md](AUTO-UPDATES.md) for the publisher signing-key setup,
independent helper and two-version Windows VM acceptance checklist. Automatic
updates are required for 1.0. The first public build must embed the configured
public key. The trusted tag-release job signs `bashdock-update.json` and
`bashdock-update.sig` after Windows validation; the release must stay a draft
until the normal acceptance checklist and actual update/rollback checks pass.

A missing signing key is permitted only for unconfigured pre-1.0 development
drafts. A 1.0-or-later draft-release job refuses to continue without signing.

## Long-running packaging steps

The “Keep the entire dist/bashdock folder together” message marks the end of
compilation, not the end of `npm run package`. Packaging also verifies cached
dependency sources, scans their license notices (including the large Qt source
archive), copies source assets, compresses the application and writes checksums.
These steps can take several minutes even when nothing needs downloading.

Packaging prints each operation immediately, reports elapsed time every five
seconds while it is running, and prints completion or interruption. Elapsed time
is not a percentage or a guarantee that an operation is making progress. If a
run appears stuck, capture the last named operation and its elapsed time.
Keep `build/source-cache` between builds to reuse verified downloads. A failed
partial download is removed and retried; completed cached archives are verified
before reuse. Successful packaging ends with “Packaging complete. Release files:”
and the generated paths.
