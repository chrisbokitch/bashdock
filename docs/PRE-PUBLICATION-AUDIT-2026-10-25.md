# BashDock pre-publication secret and privacy audit

Completed October 25, 2026 (America/Vancouver).

## Result

No exposed BashDock credentials or private keys were detected in the audited reachable Git history, available Actions logs, or inspected release/build material. No signing-key rotation or history rewrite is indicated by these findings. A personal Gmail address is present in the existing author, committer and tagger metadata; the owner should be comfortable with that metadata becoming public before changing visibility.

This report contains finding locations and provenance, not secret values.

## Audited snapshot

- Repository: `chrisbokitch/bashdock`.
- Original `main`: `174ad7954a4d92ecc37f85649a2d32e5c9bb56f8`.
- Release: `v0.11.5`, pointing to that tested commit.
- Original refs: one branch and one annotated tag; no pull requests or issues were present.
- All 76 original reachable commits, their messages, and all deleted/previous file versions were included. The commit-parent graph had no missing ancestors.
- All 452 unique historical file blobs (4,796,085 bytes) were retrieved and checked against their Git object hashes. Binary icon/image metadata was also reviewed.
- The separate audit-tools branch was created during this review. Its scanner code was checked for credentials. It does not change the application, `main`, the release tag, or published release assets.

## Methods and coverage

The scanner was Gitleaks 8.30.1, with its official Linux archive verified against SHA-256 `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb`. Scanner output was redacted; the GitHub-side report omits candidate values entirely.

Additional checks covered complete private PEM blocks, PuTTY keys, credential-bearing URLs, sensitive filenames, signing-key data flow, workflow secret references and credential persistence.

### Git and metadata

Every original reachable file version and commit message was scanned. Tag annotation and draft release notes were scanned. No private key blocks, PuTTY keys, credential-bearing URLs, or personal SSH connection details were detected. No `.secrets/`, `.env`, private PEM/PPK files, SSH identity files, or local `copy.sh`/`copy.bat` helpers were ever tracked in this reachable history.

### Actions history

All 37 pre-existing workflow runs were inventoried. All 37 executed job logs were retrieved and scanned (3,295,238 UTF-8 bytes); skipped jobs have no execution log. No truncated log responses or unavailable executed-job logs were identified. The secret scanner and additional private-key/credential-URL checks found no credential leaks in these logs.

### Retained artifacts

All 57 pre-existing retained build/diagnostic artifacts were covered:

- 29 diagnostic artifacts and 12 earlier application artifacts were inspected through ZIP inventory and bounded archive reads: 34,749 nested entries and 231 relevant text files.
- The remaining 16 artifacts exceeded the connector's 512 MiB download limit. A separate GitHub Actions job downloaded and inspected them inside GitHub, using only `contents: read` and `actions: read`. It received no update-signing secret.
- Those 16 artifact archives were verified against their GitHub SHA-256 digests. Their extracted application and project-source contents were scanned: 157,661 files in total.
- Large upstream Qt, PySide, pywinpty and truststore source archives were verified against the reviewed upstream SHA-256 values. Rust source crates were checked against their recorded checksums. Known public upstream archives were hash-verified rather than treating their test/documentation contents as BashDock secrets.
- No sensitive private-key filenames were found in the artifact contents.

Successful artifact-audit run: <https://github.com/chrisbokitch/bashdock/actions/runs/40277382045>. Redacted per-artifact results are attached to that run as `pre-publication-audit-results`.

The v0.11.5 release's application/source contents are covered by the tag-build artifact in this set. The signed draft release's expected assets, public signature size and manifest binding to the uploaded ZIP were checked separately. Application ZIP SHA-256: `b02f51f1fb85bdb6c0a084953baa02bf98950a5cbc9377c09cab7a037b0deb7a`.

## Scanner matches reviewed

There were no actionable BashDock credential findings.

The source scan produced two occurrences of one xterm.js match under its old/new project paths. Earlier artifacts produced 12 equivalent matches. The 16 large artifacts each produced the same seven matches (112 occurrences):

| Location | Classification |
| --- | --- |
| xterm.js, source and bundled runtime | Generic-key false positive on the JavaScript alias assignment `FourKeyMap=TwoKeyMap=void 0`; not a credential. |
| Qt license collection: `13d5e2e0e0e18e71c3574a70-README.md`, lines 173, 178 and 183 | Public upstream documentation strings from the hash-verified Qt source archive; not BashDock credentials. |
| Qt license collection: `43d753637e512f3a0a92b93e-README.chromium`, line 22 | Public upstream documentation string from the hash-verified Qt source archive; not a BashDock credential. |
| `qtwebengine_devtools_resources.debug.pak`, line 93723 | Google-key-format match also reproduced at the same line and entropy in the official PySide6 Addons 6.10.3 Windows wheel. That wheel's SHA-256 matches the release lock: `b465b38d1ec3476a9197441fe6a62a1fac97c45a8094f11c2d7e318aee1e3fb3`. This is public upstream dependency content, not a project or update-signing credential. |

No matched credential value is reproduced in this report.

## Update-signing key handling

- Historical `update-key.json` versions contain only the expected public fields: algorithm, public exponent and public modulus. The initial unconfigured version has a null modulus.
- The private `.secrets/update-signing-key.pem` is ignored and absent from all audited Git trees.
- The release signer reads `BASHDOCK_UPDATE_SIGNING_KEY` from the Actions secret environment, writes it to a temporary directory outside the release upload directory, and removes that directory on exit.
- The signer checks that the secret matches the public key embedded in the ZIP before creating metadata and its signature. The signed v0.11.5 job passed this check.
- The signing key is available only to the trusted tag release job, not the Windows package job or this audit job. The release upload includes `release/*`, not the temporary key directory.
- The five historical workflow versions have no `pull_request_target` trigger. Checkout credential persistence is disabled. No plaintext credential values were found in workflow files or logs.

## Privacy item for the owner

The original commit and tag metadata uses the owner's personal Gmail address and the names `Chris Bokitch`/`ChrisB`. These are public metadata after a visibility change, not authentication secrets. The application copyright/author naming is intentional. This report does not duplicate the email address.

## Boundaries

This is a secret/privacy exposure audit of the reachable repository history and available retained Actions material, not a proof against every possible undiscovered credential format or a dependency security assessment. Compiled binaries were scanned as files, not decompiled. Public upstream source archives were verified by their reviewed hashes. Already deleted/unreachable GitHub objects, previously deleted logs/artifacts, the owner's local ignored files, and GitHub's encrypted secret-store values are not accessible through this audit. Local private-key backups and machine/account security are outside this repository audit.

No repository visibility or release publication changes were made during the audit.
