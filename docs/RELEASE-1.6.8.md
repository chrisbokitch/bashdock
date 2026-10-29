# BashDock 1.6.8 release record

Prepared on 2026-10-28 (America/Vancouver). The signed draft is ready;
owner smoke acceptance is recorded below. Independent downloaded metadata
verification and publication remain pending.

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
- Draft release ID: `427355494`, stable/non-prerelease and still unpublished.
  All 12 expected application, source, checksum, provenance and signed metadata
  assets are present. Public accessibility will be checked after publication.
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
  checked that key against the public key in the actual ZIP. Independent
  verification of the downloaded manifest/signature bytes is pending owner
  provision of those two draft files. Do not confuse asset digests or successful
  signing with independent verification of their downloaded bytes.
- The owner responded “looks good” to the requested draft checksum/smoke checklist
  on 2026-10-28. Record this as owner acceptance of the requested quick checks;
  no checksum command output or separate environment/scaling details were supplied.
- The draft ZIP, manifest and signature asset sizes/digests were rechecked and
  remain unchanged. Independent downloaded metadata verification and publication
  are still pending; no public release is claimed.

## Focused release scope

Keep the prior recorded licensing entitlement, dependency pins, production
signing key and historical 1.0 acceptance evidence. The independent helper,
real-shell rendering, startup health, extracted ZIP and source/license checks
must pass for this candidate.

The owner confirmed local tests and a successful staged installation of 1.6.5;
this is optimization acceptance, not acceptance of the eventual 1.6.8 draft.
Before publishing, request the exact draft ZIP checksum and a short smoke:
launch/version, typed and button commands, New tab placement/hover/focus,
close-tab typing focus, resize/overflow, close/reopen. Verify signed update
metadata and all asset/source identities. Do not repeat the full 1.0 manual
matrix. After publication, check anonymous access, signed discovery, and website
download/version links. This candidate's own ZIP measurement is recorded above;
the 1.6.5 report remains separate historical evidence.
