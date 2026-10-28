# BashDock 1.6.0 release record

Release preparation started on 2026-10-28 (America/Vancouver). Tagged as
**v1.6.0**; draft generation and publication remain pending. Latest public
release remains 1.3.0.

## Candidate and completed checks

- Application version: 1.6.0, including multiline command editing, per-button
  confirmation with custom messages, and five groups containing 18 command presets.
- Runtime source tested: `a82f3af6fca56bdf60672a980e132000c4f95ccb`.
  Release preparation changes release notes and acceptance bookkeeping only;
  final tagged source is `a686d06ea1eb51ae2b80d90506cf85acb931246a`.
- Annotated tag object: `972d3570e53a21513648b6c0eeea753f6605e3a8`.
- Final candidate main build/package and compatibility workflows passed:
  <https://github.com/chrisbokitch/bashdock/actions/runs/40714043988> and
  <https://github.com/chrisbokitch/bashdock/actions/runs/40714043461>.
- Owner confirmed the feature checks and local tests pass, including the preset
  append/replace staging flow, on 2026-10-28. This is source/preview acceptance,
  not acceptance of a downloaded release ZIP.
- Local automated suite: 249 Python tests passed, including 23 Windows-only
  skips, and 17 JavaScript tests passed.
- Complete Windows test, native UI/scaling, compile, packaged startup and extracted
  ZIP checks passed: <https://github.com/chrisbokitch/bashdock/actions/runs/40708631520>.
- All four Windows input compatibility jobs passed, covering runner Git and
  Git 2.55.0.windows.4 with Python 3.12 and 3.14:
  <https://github.com/chrisbokitch/bashdock/actions/runs/40708631433>.

## Tagged workflow and harness follow-up

Tag workflow: <https://github.com/chrisbokitch/bashdock/actions/runs/40715865665>.
Attempt 1 passed the full test suite, then stalled in the native 100% scaling
rename-dialog test. Its 25 ms callback ran before a visible QInputDialog existed,
raised StopIteration, and left the subsequently opened modal waiting indefinitely.
Job `122913251228` was cancelled after inspecting the live log; one retry of the
same immutable tagged revision was requested. Its result is still pending.

The main-branch test-only follow-up uses a bounded visibility-polling timer,
collects callback exceptions and rethrows them in unittest, and closes the modal
on failure. The existing acceptance/cancellation/blank-name and persistence
assertions remain. A deliberate pre-dialog event-loop wait exercises the race
that previously caused the hang. This follow-up does not change the app version
or application runtime and is not part of the frozen v1.6.0 source archive.

## Selected release scope

Use the focused release process established for 1.3.0. Preserve the completed
1.0 clean-VM, recovery and updater-installation evidence. Do not claim a new
full manual matrix pass from preview acceptance.

Dependency pins, public signing key, updater installation helper, signature
verification and startup-health handoff are unchanged from 1.3.0. The updater
network change closes the response when an insecure redirect is rejected;
rejection and certificate-verification policy are unchanged. A regression test
first reproduced the unclosed response, then passed after the fix; real local-TLS
checks also passed across the Windows compatibility matrix. No global warning
suppression or relaxed TLS checks were introduced.

The exact draft ZIP needs a short owner smoke: checksum verification, launch
and version, typed and button commands, the changed button UI, and close/reopen
preserving buttons and confirmation settings. Use a harmless command for the
execution check. No destructive preset needs to be run for acceptance.

## Remaining publication checks

- Complete the tag workflow and review the signed draft's complete asset inventory.
- Record tag/source identity, application ZIP SHA-256/size, matching checksum,
  and owner acceptance of that exact downloaded ZIP.
- Publish the tested draft without replacing its assets.
- Check anonymous asset access, signed manifest verification and update discovery.
- Update the website's version/download/checksum/source/release links together,
  then verify the live deployment and record its source commit.

No new production key setup or backup confirmation is required for this unchanged
signing key. No new Windows/Git version or display-scaling report has been supplied
for the eventual owner ZIP smoke; record only what is actually reported.
