# BashDock 1.6.0 release record

Release preparation started on 2026-10-28 (America/Vancouver). **Not yet tagged
or published at preparation.** Latest public release remains 1.3.0.

## Candidate and completed checks

- Application version: 1.6.0, including multiline command editing, per-button
  confirmation with custom messages, and five groups containing 18 command presets.
- Runtime source tested: `a82f3af6fca56bdf60672a980e132000c4f95ccb`.
  Release preparation changes release notes and acceptance bookkeeping only;
  the final tagged source identity must be recorded after tagging.
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

- Pass the final committed candidate's Windows workflow and create the immutable
  v1.6.0 tag at that exact source commit.
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
