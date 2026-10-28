# BashDock 1.6.0 release record

Release preparation started on 2026-10-28 (America/Vancouver). Tagged as
**v1.6.0**, published as the latest stable release on 2026-10-28 at 09:32 PDT
(16:32 UTC): <https://github.com/chrisbokitch/bashdock/releases/tag/v1.6.0>.
The accepted draft assets were published without replacement.

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
same immutable tagged revision passed: build job `122919679110` and signed
draft/upload job `122924769591`. All 12 expected release assets are uploaded.

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

## Exact draft acceptance and metadata integrity

- Draft release: `426868099`, tag v1.6.0, source commit a686d06 above.
- ZIP: `bashdock-1.6.0-windows-x64.zip`, 280,610,070 bytes.
- ZIP SHA-256: `2ac51716cdb391794169519d111a1d6e8b5a0da9ffa0bbdd0b0986851c6dab13`.
- On 2026-10-28 the owner reported `sha256sum -c` returned
  `bashdock-1.6.0-windows-x64.zip: OK` and the requested quick smoke checks
  looked right. This accepts the exact downloaded draft ZIP, separately from
  the earlier preview/local tests. No new environment/scaling matrix is claimed.
- The owner supplied the draft's `bashdock-update.json` and `.sig`. Independently
  verified RSA PKCS#1 v1.5/SHA-256 with the embedded production public key.
  Both files match GitHub's asset digests; the signed manifest passes the app's
  parser and matches version, final URL, filename, size and ZIP SHA-256.
- Manifest SHA-256: `39df0f0a1ed2d5aaf7b9a7eadebdfacb46bdfc65d87271f7861e8c925ecbb017`.
- Signature SHA-256: `37004340e843ca346f4e7d4b6caf728d9a5d6302f8a741d5405d537a1de527cf`.
- The later main-only harness follow-up passed all four compatibility jobs
  (run `40718459806`). Its full Windows run `40718459865` passed the repaired
  rename test but failed waiting for the M4 prompt after Ctrl+C. One controlled
  retry of the unchanged revision passed the full Python/Windows/JavaScript
  suite (job `122950998653`), including the Ctrl+C case and repaired rename test.
  Subsequent main build/package steps were still running at publication.
  The failed attempt remains recorded; the tagged release already passed its
  complete build/package workflow.

## Publication and public verification

- Published release `426868099` as Latest, stable/non-draft. Tag and the 12
  uploaded assets retain their accepted identities.
- A fresh anonymous Python HTTP client (no GitHub credentials or browser cookies)
  fetched the public latest-release API and all five metadata assets. Their full
  byte counts and SHA-256 digests match GitHub asset metadata. Publicly downloaded
  manifest/signature independently verify with the production public key.
- Bounded anonymous range reads succeeded for the executable ZIP, application
  source ZIP and all five dependency source archives. These prove public access;
  they are not full independent binary/source downloads or full hash checks.
  The owner ZIP checksum, CI checks, signed manifest and GitHub asset digests
  provide the recorded full-package integrity evidence.
- The all-assets checksum list agrees with GitHub's asset digests. Build info
  records version 1.6.0 and the exact a686d06 tagged source commit. App discovery
  using freshly retrieved public responses offers 1.6.0 from 1.3.0 and no
  same-version update from 1.6.0. This is discovery verification, not a new
  end-to-end installed updater/rollback manual pass.
- Website repository commit: `a9d7670016075334107db4bd7dae76a9a3c77065`.
  Updated pinned ZIP/checksum/source/release links, metadata, visible labels,
  illustrative widget version and checksum command together. Historical UI
  captures remain identified as historical captures in the site README.
- A fresh anonymous HTTP request to <https://www.bashdock.com/> returned 200
  with the 1.6.0 download label and no remaining 1.3.0 references. All versioned
  download names match the published release assets. No CSS/JavaScript or
  screenshot assets changed.

No new production key setup or backup confirmation is required for this unchanged
signing key. No new Windows/Git version or display-scaling report has been supplied
for the eventual owner ZIP smoke; record only what is actually reported.
