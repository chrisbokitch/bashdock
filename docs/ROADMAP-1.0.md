# BashDock 1.0 readiness

The core 1.0 feature set is implemented: tabs and per-tab command bars,
remembered folders/geometry, saved workspaces with persistent tab identities,
terminal defaults/per-tab themes, settings backup/recovery, and automatic updates.

The current evidence and remaining checks are in
[ACCEPTANCE-1.0.md](ACCEPTANCE-1.0.md).
[Issue #2](https://github.com/chrisbokitch/bashdock/issues/2) tracks their completion.
The closed [first-release milestone #1](https://github.com/chrisbokitch/bashdock/issues/1)
retains the historical release/VM reports; earlier unchecked notes there are
superseded by later results.

## Completed milestones

- [x] Core tabs, command buttons, workspaces, appearance and settings persistence.
- [x] Windows CI, portable packages, checksums and matching source/license assets.
- [x] GPLv3 adoption, dependency notices/source collection, and the recorded
      Microsoft runtime publisher confirmation/inventory review.
- [x] Configure the production public key and Actions signing secret; exercise
      tag → signed draft → reviewed stable publication.
- [x] Validate real 0.11.4 → 0.11.11 → 0.11.12 public updates, restart cancellation
      and restored configuration in fresh shells.
- [x] Run the compiled-helper VM tamper and deliberate OS launch-failure rollback
      checks, including restored real-app startup.
- [x] Publish the pre-1.0 release and public download/install/help/source links
      and screenshots.
- [x] Add local stage-update support; owner confirmed normal restart after the
      0.14.2 startup-receipt fix.
- [x] Resolve the button-command first-character loss with the 0.14.6 guard;
      repeated native Windows tests and owner confirmation recorded.

These are scoped results, not blanket completion of manual Windows acceptance.
The first public beta/release is already available; no second initial public
launch is required.

## Remaining release gates

The owner selected **1.0.0** as the next candidate on 2026-10-27.
[RELEASE-1.0.0.md](RELEASE-1.0.0.md) tracks draft preparation, the exact ZIP
smoke, publication approval and the remaining public-update checks.


- [x] Complete manual Windows acceptance M1–M9; owner results and package
      evidence are recorded in [ACCEPTANCE-1.0.md](ACCEPTANCE-1.0.md).
- [x] Complete the local staged cancel/install/reopen smoke at a spaced path
      (U6/U7), owner-confirmed on 0.14.7 commit f085056.
- [ ] Complete normal public signed-update waiting plus candidate asset access
      (U1/U4) with the next intended public candidate. U2/U3/U5 failure and
      preference contracts are automated; preserve existing tamper/rollback
      evidence. See the acceptance record for coverage and limits.
- [x] Verify the production signing-key backup (P1): owner confirmed secure
      vault storage and a restored copy matching the original, 2026-10-27.
- [ ] Resolve blockers, deliberately choose 1.0.0 with the owner, and validate
      the exact candidate ZIP and any change-based retests (F1–F2).
- [ ] Review and publish the approved candidate with all required assets and
      matching public website links (F3).

A new candidate always needs its own identity/checksum/smoke evidence. This does
not require repeating every historical acceptance exercise without a relevant
change.

An update check and download never authorize closing running shell commands.
Installing an update always requires the user's restart confirmation.

Package-size reduction is optional release polish, not an added blocker.
Future features are tracked separately in the
[post-1.0 feature roadmap](FEATURE-ROADMAP.md); they do not block 1.0.
