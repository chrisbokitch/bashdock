# BashDock 1.6.8 release record

Prepared on 2026-10-28 (America/Vancouver). Publication, tagged build, exact
ZIP identity, and owner draft-ZIP acceptance are pending.

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
- Signed tagged build, exact draft-ZIP identity and owner smoke remain pending.
  This successful main build is not acceptance of a future downloaded draft.

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
download/version links. Measure this candidate's own ZIP; the 19.3% reduction
reported for 1.6.5 remains historical measurement evidence.
