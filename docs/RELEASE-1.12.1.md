# BashDock 1.12.1 release record

Status: signed draft accepted and ready to publish. Owner ZIP checksum,
exact-draft runtime/UI smoke and independent metadata signature verification
passed. Public publication is still pending.

## Scope since public 1.6.8

- 96 original generic tab icons and live icon-picker filtering.
- Tab and command-button context menus, fresh-shell tab duplication,
  middle-click tab closing, and reliable Explorer folder dispatch.
- Optional per-button timing, disabled by default, with footer elapsed time and
  exit status, quiet execution, interruption handling and multiline prompt restoration.
- Temporary per-tab font zoom with increase/decrease/reset shortcuts.
- Live per-tab scrollback search with match navigation, Unicode/wrapped text,
  current alternate-screen search and terminal focus restoration.
- Read-only Help → Keyboard shortcuts reference and Help menu grouping polish.

The signed updater format, production signing key, Python/Qt dependency pins,
settings schema and portable installation layout are unchanged. The local
terminal page additionally bundles the MIT-licensed xterm search add-on 0.15.0;
its copyright/license is included and attribution is updated.

## Validation already completed

- Application changes through `b2ece30f3ec4649f5095ae27625096fa7f601082`.
- Local `npm test`: 324 Python tests, 32 Windows-only skips; 22 JavaScript tests pass.
- Owner confirmed the latest local tests pass and requested a public release.
- Owner interaction checks confirmed the new icons/context menus, timing,
  font zoom, prompt restoration and scrollback search during development.
- The main revision's Windows input compatibility run passed all four Git/Python
  jobs: <https://github.com/chrisbokitch/bashdock/actions/runs/40940815302>.
- Its full Windows build/package run passed tests, scaling checks, compilation,
  package creation, update-startup checks and all extracted rendering probes,
  then failed removing a temporary extracted folder because an orphaned
  OpenConsole process retained a file lock. This is not a successful package
  verification result. The failed job was retried. The release-preparation commit supersedes that
  retry with a fresh package build, which must pass before tagging. Original run:
  <https://github.com/chrisbokitch/bashdock/actions/runs/40940815377>.

## Tagged build and verified draft identity

- Annotated tag v1.12.1: `46b67ab244f8ac093cf2a4bb60ca9683dd1f2b83`,
  pointing to release source `f3630622b0df9194f1a5fa23d5df93edc468089a`.
- Fresh main build/package run 40944842516 and all four compatibility jobs in
  run 40944842592 passed. The earlier temporary-file lock did not recur.
- Tagged run 40945319866 passed: build job 123699043449 and signing/draft job
  123703971336. Tests, scaling checks, independent updater checks (zero Qt),
  public/local startup-health checks, all eight compiled/extracted rendering
  checks, ZIP/source/license verification and temporary cleanup passed.
- Draft release ID: 428346016. All 12 expected assets are uploaded.
- ZIP: `bashdock-1.12.1-windows-x64.zip`, 226,462,422 bytes.
  SHA-256: `586d8fa1bf2f8e55b904d468f4a16afb749bc70e241da749e609b9a094237980`.
- The owner supplied Git Bash checksum output: the matching ZIP checksum file
  reports `bashdock-1.12.1-windows-x64.zip: OK`.
- Uploaded manifest (302 bytes) SHA-256:
  `7e99c4c505f9d29573507f0e3a5c6b5711f85bd9d606aed63e825bca225c99f4`.
- Uploaded signature (384 bytes) SHA-256:
  `11fcb23900c16f4427b88ee796a3c2674060dea4033aa84efe95d8aabfe0cb6a`.
- Both uploaded files match the draft asset sizes and digests. Independently
  verified RSA PKCS#1 v1.5 / SHA-256 using cryptography and the production public
  key from the exact tagged source. The signing job also checks that key against
  the public key embedded in the actual ZIP. No private key was accessed.
- Manifest structure validation passed with the independent verifier (the native
  Windows verifier is not runnable on this Linux host). Version, filename, HTTPS
  URL, exact ZIP size and SHA-256 agree with the draft asset identity.
- The large Actions delivery bundle was removed after draft attachment. Only
  the small windows-build-diagnostics artifact remains for this tagged run.

## Owner acceptance

The owner supplied the exact ZIP checksum result and then explicitly confirmed
that the requested extracted-ZIP launch/UI check passed on 2026-10-29. This
accepts the focused smoke checklist: launch/version, typed/button commands,
timing and normal prompt layout, zoom/search, Help reference, and close/reopen.
No additional full 1.0 acceptance matrix is claimed.

Before publication, draft release 428346016 was fetched again: it is still a
draft for v1.12.1 with all 12 expected assets. ZIP, manifest and signature sizes
and SHA-256 digests are unchanged from those accepted and independently verified.

## Remaining publication work

Publish the accepted draft. The connected GitHub tools do not provide a release
publication operation, so the owner must use GitHub's Publish release button.
After publication, recheck public asset access and immutable identity, updater
discovery, and website download links; record the final evidence here. The
website remains on public 1.6.8 until publication is confirmed.
