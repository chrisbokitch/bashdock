# BashDock 1.3.0 release record

Published as latest stable on 2026-10-27 (America/Vancouver), at
`2026-10-28T03:37:52Z`. Release:
<https://github.com/chrisbokitch/bashdock/releases/tag/v1.3.0>.

## Package identity

- Tag: `v1.3.0`, source commit `b7a1a06e7b17daedccde0b2e43bc60cf2d90ef09`.
- ZIP: `bashdock-1.3.0-windows-x64.zip`, 280,590,450 bytes.
- SHA-256: `7320c699b91a18810af7df27722c460a8647cfb82f7065760562430ff5b2926d`.
- Release ID: `426200208`; published without replacing the tested draft assets.
- Tag workflow: <https://github.com/chrisbokitch/bashdock/actions/runs/40620316401>.
- Pre-tag Windows build and compatibility jobs passed:
  <https://github.com/chrisbokitch/bashdock/actions/runs/40616997571> and
  <https://github.com/chrisbokitch/bashdock/actions/runs/40616997477>.

## Focused acceptance scope

The owner explicitly chose a small-update release check rather than repeating
the exhaustive 1.0 acceptance matrix. Dependencies, production signing key and
updater installation code are unchanged from 1.0.0. This release adds wrapping
command buttons, automatic/custom tab icons and compact overflow, the workspace
Replace current mode, and a dark initial terminal background.

- Owner feature checks passed during development.
- Local suite: 222 Python tests, including 20 Windows-only skips, and 17
  JavaScript tests passed. Windows CI ran the Windows integration cases and
  native UI checks, including 100%, 125% and 150% scaling.
- Hosted-desktop size/font assumptions and asynchronous renderer measurements
  in the new tests were corrected before tagging. Those follow-ups did not
  change application runtime code or version; the candidate's complete Windows
  build, compatibility and tag-release workflows subsequently passed.
- The owner confirmed the exact draft ZIP smoke passed: launch/version 1.3.0,
  typed command and wrapped-row button execution, and close/reopen restoring
  tabs and icons. In Git Bash under `/c/Development/test`, the owner ran
  `sha256sum -c bashdock-1.3.0-windows-x64.sha256` and reported
  `bashdock-1.3.0-windows-x64.zip: OK`.
- No new Windows version, Git version or scaling report was supplied for this
  final smoke. The previous clean-VM and updater failure matrices were retained
  as historical evidence; no new full-matrix pass or compiled updater handoff is
  claimed for 1.3.0.

## Public verification

After publication, a fresh HTTP client without GitHub credentials or browser
cookies verified:

- The latest-release API exposes `v1.3.0`, with draft and prerelease flags false.
- All 12 uploaded assets allow successful byte-range download requests. This
  checks access without downloading every large archive in full.
- The live update manifest's RSA/SHA-256 signature verifies with the production
  public key. Its ZIP hash matches the package identity above.
- The ZIP checksum and combined checksum list agree with GitHub's uploaded
  asset digests. The combined list covers the other 11 assets, not itself.
- Public build information identifies version 1.3.0 and the tagged source commit.
- Live source discovery offers 1.3.0 to 1.0.0 and offers no replay to 1.3.0.

The assistant did not independently download and hash the entire application
ZIP. The owner's exact-ZIP checksum/smoke, GitHub digests and signed manifest are
recorded separately above.

Website download, checksum, source, release-note and version labels were updated
together in `chrisbokitch/bashdock.com` commit
`1d225945b6e7c271e6f22ba8963b989b49539eb4`. Existing illustrative images were
retained; no new 1.3.0 screenshot set is claimed.

The automatic website deployment was checked at <https://www.bashdock.com/>:
it serves the 1.3.0 download links with no stale 1.0.0 version labels.
