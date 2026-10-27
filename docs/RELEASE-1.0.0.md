# BashDock 1.0.0 candidate

Candidate selected with the owner on 2026-10-27. This is preparation for the
first 1.0 release; it is not a publication or final acceptance record.

## Scope and retained evidence

The application changes from the accepted 0.14.7 runtime are the synchronized
version files only. Release notes describe the implemented feature set.
M1–M9, automated updater contracts U2/U3/U5, the owner-confirmed local staged
update at a spaced path (U6/U7), and signing-key backup P1 are complete in
[ACCEPTANCE-1.0.md](ACCEPTANCE-1.0.md). Historical signed public updates and
tamper/rollback evidence remain valid for their tested versions. Do not repeat
the entire manual matrix solely because the version changes to 1.0.

## Candidate build and draft

1. Commit the version and release notes; pass the main Windows workflow.
2. Create `v1.0.0` at that exact tested commit. The tag workflow rebuilds it and
   creates a signed **draft** release. Never move or reuse a published tag.
3. Wait for the tag workflow, including independent helper, extracted executable,
   source/license packaging and update-signing checks. Download the actual
   application ZIP and checksum from that draft, not a local stage-update build
   or the enclosing Actions artifact wrapper.
4. Record the tag, commit, application ZIP SHA-256, Windows/Git versions and
   results in issue #2. This record is still pending until that exact file exists
   and has been exercised by the owner.

## Exact-candidate owner smoke (F2)

Use the existing disposable Windows test profile. Keep the downloaded
`bashdock-1.0.0-windows-x64.zip` and its `.sha256` file together, then verify in
Git Bash:

```bash
sha256sum -c bashdock-1.0.0-windows-x64.sha256
```

Extract the complete folder and check:

1. Launch, confirm Help → About reports 1.0.0, inspect License and notices, type
   a harmless command and execute a command button.
2. Prepare two distinguishable tabs/folders, close/reopen, and confirm restored
   configuration, usable fresh shells and normal quit behavior.

The final ZIP has different bytes from the 0.14.7 package; its checksum and smoke
must be recorded separately. Existing M1–M9 and U6/U7 results need no full rerun
unless a regression or relevant source/dependency change warrants it.

## Asset review and public update (U1/U4/F3)

Before publication, review the draft notes and all required application,
checksum/build-info, application/dependency source and signed-update assets.
Review the generated source/license inventory from this locked build. Prepare
matching public website/download links; change them only when approved assets
are published. No website/public release is updated by candidate preparation.

Public release publication requires the owner's approval after reviewing the
candidate and F2 result. A draft is not discoverable by the normal updater and
its private asset links cannot establish anonymous access. Therefore U1/U4 can
only be completed after the approved publication is reachable. They remain
open until those results are recorded; preparing a draft does not close F1–F3.

For the approved release, use two idle instances from the same disposable
published 0.11.12-or-later installation, with one minimized. Update the other
through the app's normal public updater. Confirm visible waiting guidance,
close the remaining instance normally, and verify startup of 1.0.0 and closure
of the helper window. Check anonymous access to the matching application,
source/license, checksum and signed-update assets. Record the baseline/target
and results in issue #2; then finish the public website/link review. Do not
create a dummy release or modify production signing keys for these checks.

## Status

- Candidate version selected: **1.0.0**.
- Exact tested/tagged commit: `ec4348991b463c0e6bdeacb5a6ffe3008b733033`.
- Main and tagged Windows package validation, update signing and draft creation
  passed in [the tag workflow](https://github.com/chrisbokitch/bashdock/actions/runs/40593899149).
- Signed draft: [v1.0.0](https://github.com/chrisbokitch/bashdock/releases/tag/untagged-3521df38cf43ede33446), still unpublished.
- Exact application ZIP SHA-256:
  `71f89c4c10f7657779988d27fbaa62ffbe8f8be0aecd222f6088908daca2f54e`.
- F2 owner smoke: **passed — owner confirmation, 2026-10-27**.
- Publication approval and U1/U4/public-link results: pending.

## Focus-test follow-up

On 2026-10-27, the owner reported a local focus regression test failing while
establishing focus on the alternate input, before clicking the command button.
Test-only commit `f9e718c171910e80f30732db749d9848b1802e09` waits for startup
JavaScript, establishes Qt's active fixture window and clicks the alternate
input; the button-focus and typing assertions remain intact. It also explicitly
runs this regression with native Windows Qt in CI and disposes of the fixture.
The full Windows suite and native focus case passed, and the owner subsequently
confirmed the local rerun passed. The focus-test publication hold is cleared.

Application runtime/version files were unchanged by that follow-up, and the
existing `v1.0.0` tag remains at `ec43489`. The published source snapshot, when
approved, is the tagged revision; this later test-harness correction is on main.
F2 exact-draft ZIP smoke subsequently passed as recorded below. Publication
approval and U1/U4 remain pending.

## F2 exact-package result

**Passed — owner confirmation, 2026-10-27.** The owner confirmed all requested
checks passed using the signed draft's `bashdock-1.0.0-windows-x64.zip`:
checksum verification, launch, About 1.0.0, License and notices, typed and button
commands, two-tab/folder restoration after close/reopen with usable fresh shells,
and normal quit behavior.

- Tag: `v1.0.0`.
- Source commit: `ec4348991b463c0e6bdeacb5a6ffe3008b733033`.
- ZIP SHA-256 supplied by the owner:
  `71f89c4c10f7657779988d27fbaa62ffbe8f8be0aecd222f6088908daca2f54e`.
- GitHub's uploaded ZIP asset digest independently reports the same SHA-256.
  This metadata comparison is not an independent download/rehash of the ZIP.
- No additional Windows/Git version or installation-path report was supplied for
  this final smoke; earlier environment reports are not assumed to describe it.

The draft's notes and required 12-asset inventory were reviewed: application
ZIP/checksum/build info, combined checksums, application source, signed manifest
and signature, Qt/PySide/pywinpty/truststore sources and Rust dependency sources.
The application ZIP is 244,500,578 bytes. The release remains a draft; public
recipient access, normal public-update waiting and public website/link checks
remain U1/U4/F3 and cannot be claimed from the draft's existence.
