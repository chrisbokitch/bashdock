# BashDock 1.6.8 release record

Published as the latest stable release on 2026-10-28 at 18:36 PDT
(2026-10-29 01:36:20 UTC):
<https://github.com/chrisbokitch/bashdock/releases/tag/v1.6.8>.
Owner smoke acceptance and independent signature verification are recorded below.

This replaces the [failed 1.6.7 candidate](RELEASE-1.6.7.md); no public 1.6.7
release or draft assets were created. Its immutable tag is retained. The UI
and optimization scope remains the same, with one added rendering-harness fix.

## Changes and validation

- Since public 1.6.0: update-backup cleanup, new/closed-tab typing focus,
  a small translucent circular New tab control beside the tabs, GUI-free
  updater packaging, release-only WebEngine resources, and test synchronization.
- The smoke wrapper now assigns each Windows rendering probe to its own
  kill-on-close job. A startup gate prevents Qt/shell children from starting
  before assignment. Closing the job also terminates orphaned descendants
  before temporary-folder cleanup, on success and failure. No global process
  names or unrelated app instances are targeted. Normal application startup
  and terminal shutdown behavior are unchanged.
- Native Windows regression coverage verifies an orphaned child holding a
  sandbox directory is terminated, its directory can be removed, and an
  unrelated process remains alive. Portable fixtures verify startup gating,
  job cleanup after success, and fail-closed assignment errors.
- Local suite passed: 281 Python tests with 27 Windows-only skips, and 17
  JavaScript tests.

## Completed Windows candidate checks

- Tested runtime/source commit: `2a11b3ebc5239178cb3ce3b89b0a3a78a756cd50`.
- Full Windows build/package workflow passed on its first attempt:
  <https://github.com/chrisbokitch/bashdock/actions/runs/40793573888>,
  build job `123184445822`.
- The native orphan-child job regression passed. The full 281-test suite,
  additional native/scaling checks, compilation, and independent updater
  verification with zero Qt entries passed.
- All eight actual frozen rendering checks passed: default rendering at 100%
  and software rendering at 100%, 125%, and 150%, in both the compiled folder
  and extracted ZIP. Their temporary directories were successfully cleaned up.
- Final ZIP integrity, source/license checks, and extracted startup passed.
- All four Git/Python compatibility jobs passed:
  <https://github.com/chrisbokitch/bashdock/actions/runs/40793573895>.
- The separately completed tagged build and exact draft identity are recorded
  below. Main-build success alone is not owner acceptance of the downloaded ZIP.

## Tagged build and signed draft

- Tag `v1.6.8`, annotated object `6695f35aa65f2444b1abddf000389f0e4f206cfa`,
  points to tested source `2a11b3ebc5239178cb3ce3b89b0a3a78a756cd50`.
- Tagged workflow passed on its first attempt:
  <https://github.com/chrisbokitch/bashdock/actions/runs/40797326556>.
  Build job `123196855850` and signing/draft job `123199969370` both succeeded.
- The native orphan-child regression, full 281-test suite, additional native
  and scaling checks, independent updater (zero Qt entries), all eight actual
  frozen rendering checks, temporary-folder cleanup, source/license verification,
  ZIP integrity, and extracted executable/startup checks passed.
- The actual eight frozen JSON reports in diagnostic artifact `12865465195`
  were inspected: all report success and the real-shell Unicode marker, at
  DPR 1 (default and software), 1.25 and 1.5, before and after ZIP extraction.
  Fixture-generated rendering log lines are not counted as frozen checks.
- Release ID: `427355494`, stable/non-prerelease. Initially created as a draft,
  then published after the owner smoke and independent metadata verification.
  All 12 expected application, source, checksum, provenance and signed metadata
  assets are present. Post-publication verification is recorded below.
- ZIP: `bashdock-1.6.8-windows-x64.zip`, 226,427,474 bytes (215.94 MiB).
  SHA-256: `bb9fee866df0948549c13b9d7799081814cabdd75d163b280d04a9a4299b9479`.
  Its GitHub asset size/digest match the tagged build's diagnostic size report.
  Installed file contents: 528,278,213 bytes, 2,924 files. The download is
  19.3% smaller than the public 1.6.0 ZIP.
- Manifest asset SHA-256:
  `93807098754d0c6b949d6bb48e18ae1f418906fbbaa450fe09f41d8147454d93`.
  Signature asset SHA-256:
  `1225a5edc91ed573375e9efb8b4acb7f32a883707164cc2f8a0b99e90887fcd7`.
- CI generated the metadata with the existing production signing key and
  checked that key against the public key in the actual ZIP. The owner supplied
  the draft manifest and signature. Independently verified RSA PKCS#1 v1.5 /
  SHA-256 using the embedded production public key; both supplied files match
  GitHub asset digests. The manifest passes the app parser and identifies the
  accepted ZIP version, filename, URL, exact size, and SHA-256.
- The owner responded “looks good” to the requested draft checksum/smoke checklist
  on 2026-10-28. Record this as owner acceptance of the requested quick checks;
  no checksum command output or separate environment/scaling details were supplied.
- The draft ZIP, manifest and signature asset sizes/digests were rechecked and
  remain unchanged through publication. No tag or uploaded asset was replaced.
- Published notes use the actual 1.6.8 ZIP measurement and compare the full
  changelog against the previous public 1.6.0 release, rather than failed 1.6.7.

## Focused release scope

Retained the recorded licensing entitlement, dependency pins, production signing
key and historical 1.0 acceptance evidence. Used the focused draft smoke checklist
for launch/version, typed/button commands, New tab appearance/focus, close-tab
focus, resize/overflow and close/reopen. No new full 1.0 manual matrix or installed
updater/rollback manual pass is claimed. The earlier owner acceptance of staged
1.6.5 remains separate from acceptance of this downloaded 1.6.8 draft.

## Public verification and website

- A fresh anonymous Python HTTP client fetched the public latest-release API:
  release `427355494`, v1.6.8, stable and non-draft, with all 12 assets.
- Fully downloaded all five metadata assets. Their byte counts and SHA-256
  values match GitHub asset metadata. Public manifest/signature bytes verify
  independently with the embedded production key. The all-assets checksum list
  agrees with GitHub digests, and public build information identifies the exact
  tagged source commit and version.
- Bounded anonymous reads succeeded for the executable ZIP and all application
  and dependency source archives. These establish access, not independent full
  binary/source hash downloads. Full-package integrity evidence remains the
  accepted owner draft check, validated CI package, signed manifest and recorded
  GitHub asset digests.
- Discovery using freshly fetched public responses offers 1.6.8 from 1.6.0
  and no same-version offer from 1.6.8. This is discovery verification, not a
  new installed update/rollback test.
- Website commit: `ec44dd45b4ab8d992b11531fa5287059c6f1e763` in
  `chrisbokitch/bashdock.com`. Updated versioned ZIP/checksum/source/release
  links, visible version labels, metadata, illustrative widget version, and
  checksum command together; checked all five versioned download links against
  published assets. Styles, scripts and historical UI captures are unchanged.
- After deployment, a fresh anonymous request to <https://www.bashdock.com/>
  returned HTTP 200 with 1.6.8 references and no remaining 1.6.0 references.
