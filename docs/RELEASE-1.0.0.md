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
- Exact tested/tagged commit: pending candidate commit and CI.
- Signed draft and exact application ZIP checksum: pending tag workflow.
- F2 owner smoke: pending.
- Publication approval and U1/U4/public-link results: pending.
