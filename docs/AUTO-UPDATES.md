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

The checked-in key initially has a null modulus. This intentionally makes
unconfigured development builds quiet at startup and unable to install unsigned
updates. They remain fully usable. Configure the key **before the first public
build**, otherwise that build cannot trust later automatic updates and needs a
manual bootstrap replacement.

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
APIs and the compiled helper outside the application directory. A real two-release
VM update remains a 1.0 acceptance gate.
