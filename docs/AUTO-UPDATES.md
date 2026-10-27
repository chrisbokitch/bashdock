# Automatic updates — required for 1.0

## App behaviour

Compiled Windows builds check the latest published GitHub release after startup
and every 12 hours. **Help → Check for updates…** checks on demand. **Settings →
Updates** contains **Check automatically** and **Download automatically**; both
start enabled and are included in settings export/import and recovery. Preview
and source runs never replace the source checkout and do not check automatically.

Downloads run on a background thread. The updater downloads only the application
ZIP, not the separate dependency source archives. A verified, staged update adds
**Version X is ready — Restart to update** immediately after the current footer
version. This is a yellow, keyboard-accessible button; status/error messages stay
separate and cannot clear it. With automatic downloads disabled, the footer first
offers **Version X is available — Download update**.

Clicking the ready notice always asks before restarting, even if ordinary quit
confirmation is disabled. The dialog explains that running commands and shell
sessions will close. Tabs, folders, command bars, appearance, workspaces, window
position and settings are saved; they reopen in **fresh shells**, not resumed
processes or SSH connections. Cancelling or a save/helper-launch failure keeps
the current shells open.

The helper is a separate one-file executable copied to the per-user update cache.
It waits for BashDock to exit and for other processes using that installation to
finish. It never kills unrelated processes or requests elevation. An unwritable
installation requires a manual download to a writable location. The complete
application folder, including `_internal`, is replaced; keep personal project
files outside the installation folder. Settings remain in `%APPDATA%\bashdock`.

The previous installation stays in a `.bashdock-previous-*` folder beside the
installation. A new process must acknowledge startup with the expected version
and a per-update token. If startup fails, the helper terminates that newly
launched process, restores the previous folder and settings snapshot, and
relaunches the old app. Failed settings are retained in the update cache.
A restart failure is reported rather than silently deleting the previous build.

Backups and diagnostic files remain available for manual recovery. In a power
failure during the brief folder-swap interval, restore the retained previous
folder to the installation name if necessary; this first implementation is not
a system service or a transactional Windows installer. Do not delete a previous
folder or `%LOCALAPPDATA%\BashDock\updates` while an update is running.

## Trust and public access

The client uses the public GitHub Releases API with no GitHub credentials. A
private repository or no public release yields no available update. Public
release assets must be accessible to an unsigned-in recipient. Drafts,
prereleases, older versions and the already installed version are ignored.
Only plain stable `MAJOR.MINOR.PATCH` versions are supported initially.

Each update needs `bashdock-update.json` plus its detached RSA PKCS#1 SHA-256
signature, `bashdock-update.sig`. The public RSA 3072-bit key is embedded in both
executables. Windows CNG verifies the signature before the metadata is trusted.
The signed metadata binds the version, Windows x64 platform, exact official ZIP
URL, byte count and SHA-256. Downloads reject HTTP redirects, invalid hashes,
truncated/oversized content, and unsafe archive paths/links/aliases. The helper
checks the signature and hash again immediately before installation.

The private signing key is **never** included in the application, source ZIP or
repository. Signing protects the update channel; it is not an execution or
license restriction on modified builds. Forks may change the key and release
location and build their own updater under GPLv3. Authenticode code signing is a
separate Windows trust/SmartScreen decision.

## One-time publisher setup

BashDock's production signing configuration has already been exercised by
published signed releases; see E1 in [ACCEPTANCE-1.0.md](ACCEPTANCE-1.0.md).
These setup instructions apply to a new publisher/fork. Do not regenerate the
existing production key as part of acceptance reconciliation.

A null public-key modulus marks an unconfigured development build: it stays
quiet at startup and cannot install unsigned updates, but remains usable.
A new publisher must configure the key **before their first public build**;
otherwise that build cannot trust later automatic updates and needs a manual
bootstrap replacement.

From Git Bash in the project, run:

```bash
npm run updates:keygen
```

Git for Windows supplies OpenSSL. The command generates:

- `.secrets/update-signing-key.pem`: the private key, ignored by Git; restricted
  to the current user on Windows and mode 600 on POSIX. Back it up securely.
- `bashdock/assets/update-key.json`: the public key; commit this file.

Do not paste the private key into chat, commit it, or attach it to a release.
In the repository's **Settings → Secrets and variables → Actions**, create the
repository secret **BASHDOCK_UPDATE_SIGNING_KEY**, containing the complete PEM
private key. This one-time GitHub setting is performed by the repository owner;
the current connector cannot configure secrets. Use the repository secret only
in the trusted tag release job, never in pull-request jobs.

After committing the public key and a deliberate version bump, build/test a
candidate normally. Keep the same signing key for subsequent releases; do not
regenerate it per release. Key rotation requires a separate compatibility plan.

## Release integration

`npm run compile` builds the main app and `bashdock-updater.exe`, then copies the
helper outside the application and exercises its independent self-test. The
helper requires neither installed Python nor the app's `_internal` directory.
Packaging and ZIP verification require the helper to be present.

The existing tag workflow first validates the Windows package. The trusted
Ubuntu draft-release job then signs update metadata using the Actions secret.
The secret is placed in an ephemeral private file and removed after signing.
It must match the public key in the source revision. Both signed assets are
attached beside the ZIP and source assets; the complete checksum list includes
them. Nothing is offered automatically while the release is a draft. Publishing
the release enables discovery.

Unconfigured pre-1.0 drafts may be produced without automatic-update assets.
A 1.0-or-later release **fails** the signing step if the public key or signing
secret is missing. Do not publish a 1.0 candidate until the tests below pass.

## Required Windows VM validation

This is the reusable procedure. Current results and outstanding cases U1–U7
are recorded in [ACCEPTANCE-1.0.md](ACCEPTANCE-1.0.md). Real public two-version
updates, cancellation/restoration, compiled-helper tamper rejection and an OS
launch-failure rollback have already passed within their recorded scope. Keep
that evidence; do not interpret this unmarked procedure as a list of tests that
have never been run.

Test the exact release ZIP, not only source preview:

- Verify a signed newer release appears, downloads, and produces the yellow
  clickable notice beside the current version. Check 100%, 125% and 150% scaling.
- Cancel restart: shells and commands keep running and the ready notice remains.
- Restart after stopping important work: tabs/settings/geometry return, the
  version advances, the helper exits, and `_internal` is completely replaced.
- Test a second app instance, locked files, an unwritable destination, a failed
  settings save and a helper launch failure. No forced closure/elevation.
- Test altered metadata/signature, a changed/truncated ZIP and a version replay.
  They must never install. Confirm source archives remain publicly available.
- Exercise deliberate failed startup: previous binaries and the prior settings
  must be restored, with failed settings retained for inspection.
- Test a path with spaces, interrupted downloads, a source preview, automatic
  downloads disabled and all automatic checks disabled.

The portable suite tests discovery, signed metadata validation, archive rejection,
exact downloads, folder replacement, rollback and GUI cancellation/save failures.
Windows CI additionally checks real CNG/OpenSSL interoperability, process handoff
APIs and the compiled helper outside the application directory. The real two-release VM update milestone is recorded as completed (E3).
Outstanding manual/error cases and the exact final-candidate check remain open;
automated results do not stand in for those manual results.

## Secure connection failures

Update requests use truststore with Windows CryptoAPI for certificate-chain
validation, including Windows-managed roots and intermediate retrieval. Hostname
and certificate checks remain mandatory; HTTP redirects are still rejected.
No global SSL overrides or separate CA bundle are used. The compiled helper's
self-test creates this context so missing native TLS modules fail the build.
If validation still fails, check Windows date/time, Windows certificate updates
and any organization-managed HTTPS proxy. Never disable certificate checks.

## Visible installation progress (0.11.12+)

The independent helper opens a native status window while verifying, extracting,
waiting, replacing files and checking startup. If another instance holds the
installation, it asks you to close other BashDock windows, including minimized
windows. Locked-folder retries show guidance too. Each wait still has a timeout;
an unsuccessful update retains/restores the previous installation and reports
an error. The window can be minimized, but cannot be closed during replacement.
It requires no Qt files from the installation being replaced.

This feedback belongs to the **installed helper**: a v0.11.4 installation updating
to a newer version still uses its old helper for that transition. Validate the
new feedback with a 0.11.12-or-later baseline and a subsequent signed release.

## Repeatable compiled-helper recovery and tamper checks

Use a disposable Windows VM with Git for Windows installed. This command needs
no Python or Node. It uses the compiled 0.11.12+ helper, real Windows signature
verification, actual directory replacement, and Windows process creation. It
never changes the supplied baseline or downloaded release assets.

1. Extract a known-working release into a baseline folder (for example,
   `C:\UpdateTest\baseline\bashdock`). Close that copy. Keep the ordinary
   installation separate.
2. Download the **same release's** `bashdock-update.json`, `bashdock-update.sig`
   and application ZIP into `C:\UpdateTest\assets`. The assets must have the
   production signature; source archives are unnecessary. The baseline can be
   an older version; the supplied assets can be the existing published v0.11.11.
3. Obtain the **new** `bashdock-updater.exe` from a 0.11.12+ compiled package.
   Put it outside the baseline, for example `C:\UpdateTest\bashdock-updater.exe`.
4. Ensure several GB of free space. In Git Bash, run (the `run-1` folder must
   **not already exist**):

   ```bash
   cd /c/UpdateTest
   ./bashdock-updater.exe --acceptance-test 'C:\UpdateTest\run-1' \
     --baseline 'C:\UpdateTest\baseline\bashdock' \
     --assets 'C:\UpdateTest\assets'
   ```

The harness copies the baseline into the new output folder and uses isolated
APPDATA/LOCALAPPDATA settings with automatic checks disabled. It tests:

- A changed manifest (valid JSON with an added newline).
- A changed signature.
- A changed ZIP byte with the original size.
- A truncated ZIP.
- A genuine Windows failure to launch the replacement: **after** verifying and
  extracting the signed ZIP, it deliberately replaces only the disposable
  executable with invalid bytes and changes the disposable settings. The real
  installer must restore all previous file hashes and both settings files, and
  retain failed settings and a `rolled-back` transaction record.
- Launching the restored real app and receiving its version/token startup
  acknowledgment. Inspect the tab named **Rollback test — disposable copy**,
  then close that test app.

Each tamper case must be rejected before waiting for an app or writing an
installation transaction. All original assets and the baseline remain unchanged.
`run-1/acceptance-results.json` must contain `"ok": true` and six passing cases.
A native success/failure message identifies the outcome. Keep the report with
acceptance evidence; test folders are retained for inspection. Close the test
app before deleting the output folder or restoring the VM checkpoint. Use a new
output folder for each run.

This deliberately skips the normal running-app handoff because no baseline app
is running in the copy. It tests an OS launch failure, not every possible crash
or hang after a successful launch. Normal GUI handoff, second-instance feedback,
and real two-release updating still need their separate VM checks. It does not
weaken signature verification or add a failure switch to normal app startup.

## Local development updates

Starting with **0.14.0**, an installed Windows copy can accept a package built from
another source checkout on the same machine/user account. This is a separate,
explicitly enrolled local development channel. Public downloads still require
the embedded publisher key; local keys are never tried as a fallback for public
updates. Source/preview runs never watch an installed copy's inbox.

### One-time bootstrap

Older installations cannot discover local staged builds or verify their separate
signatures. On the source checkout, pull 0.14.0 or newer, then build/package:

```bash
cd /c/Development/bashdock
npm run test:with-pull
npm run package
```

Open an external Git Bash, close the installed BashDock, and run the existing
ignored `./copy.sh` once. Reopen `C:\Development\tools\bashdock\bashdock.exe`.
This is the final manual copy needed to introduce the capability.

### Everyday workflow

From the source checkout (including a shell inside the installed BashDock):

```bash
npm run test:with-pull
npm run stage-update -- "C:/Development/tools/bashdock"
```

The command validates the installed target, builds and smoke-tests the compiled
application/helper, creates the normal package with its source/licensing assets,
and stages it without replacing any running installation files. Packaging still
requires a clean, committed checkout. Do not point it at `dist/bashdock`.

The installed app polls its local inbox every two seconds, independently of the
public automatic-check preference. Signature, checksum and archive checks run in
the background; after validation the footer offers **Local build X is ready —
Restart to update**. Finish running work, click the notice and confirm the restart.
Cancellation leaves the running shells open. Settings backups, waiting for other
instances/locked files, application replacement, startup health checks and rollback
use the same transaction as public updates. The independent helper verifies the
local signature and package again before modifying the installation.

To stage an existing package without rebuilding it:

```bash
npm run stage-update -- "C:/Development/tools/bashdock" --reuse-package
```

That package must match the checkout's exact version and HEAD commit. Older
versions, stale packages, and a version/commit already installed are rejected.
A different commit with the same version is allowed for local development; a
version downgrade is not. A second staging command publishes a fresh offer
atomically. An update already confirmed installs the build named in its dialog,
even if another build is staged meanwhile.

### Local trust and revocation

Running `stage-update` explicitly enrolls only the named installation. The command
creates/reuses `.secrets/local-update-signing-key.pem` in the source checkout,
separate from the public release signing key. It is ignored by Git and must not
be committed or shared. The trusted public key and staged packages live under
`%LOCALAPPDATA%\BashDock\local-updates\<installation-id>`. Signed metadata binds the
package to that installation; packages cannot be redirected to another target.
Public-key enrollment survives application replacement because it is outside the
installation folder. A different development key cannot silently replace it.

Disable local staging for that target with:

```bash
npm run stage-update -- "C:/Development/tools/bashdock" --disable
```

This revokes its local public key and removes the offer, without rebuilding,
closing the app, changing settings, or disabling public updates. Already-confirmed
transactions may be in progress. To enroll a replacement development key, disable
first, then stage again. Old staging directories and retained previous installations
are left for inspection/manual cleanup; revocation does not delete them.

### Windows validation

After bootstrapping, validate a subsequent committed build against the running
installed copy: stage it, cancel once (shells must remain usable), then confirm.
Check version/About, tabs, commands, colours, settings and a normal second launch.
Confirm the staged notice is consumed and a new staging command is detected.
The automated suite checks real local signatures (Windows CNG on Windows), target
binding, tampering, atomic publication, isolation from the public trust path, and
transactional startup rollback with disposable installation/settings fixtures.

Every `npm run compile` also starts disposable copies of the compiled GUI and
checks its actual startup receipt for both public-cache and installation-scoped
local-inbox paths. User settings and cache directories are isolated, public
network checks are disabled, and only the test process trees are stopped after
verification. Results are in `build/startup-health-smoke.json`. ZIP verification
repeats this check on the extracted executable. A local startup receipt must be
inside the running installation's own `pending-*` inbox; other installations and
arbitrary paths remain rejected. Diagnostic reports include receipt acceptance
and write-success flags, without paths or update tokens.
