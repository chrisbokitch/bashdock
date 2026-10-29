# BashDock 1.6.7 release record

Release preparation started on 2026-10-28 (America/Vancouver).
Publication and exact draft-ZIP acceptance are pending.

## Candidate and automated evidence

- Application version: 1.6.7. Runtime source:
  `453f1a03e6ac694bcaca257d355a2962a2b00df0`.
- Full Windows build/package workflow passed:
  <https://github.com/chrisbokitch/bashdock/actions/runs/40790199189>.
- All four Windows input compatibility jobs passed:
  <https://github.com/chrisbokitch/bashdock/actions/runs/40790199200>.
- Local suite passed: 278 Python tests with 26 Windows-only skips, and all
  17 JavaScript tests. Focused new-tab geometry and behavior checks also passed
  at 150% scaling. Normal and hover rendering were inspected locally.
- Owner confirmed local tests and a successful staged installation of 1.6.5.
  This covers the updater/resource optimizations, not the exact 1.6.7 draft ZIP.
- This preparation changes release notes and records only; the tagged build
  must record its own final source commit, ZIP identity, and workflow results.

## Selected scope

Changes since public 1.6.0 include update-backup cleanup, terminal focus fixes,
the new-tab control, GUI-free updater packaging, release-only WebEngine
resources, and test synchronization. Dependency pins and the production signing
key are unchanged. Preserve the recorded licensing entitlement and historical
1.0 acceptance evidence.

The independent helper and extracted package must pass the automated dependency,
startup-health, real-shell rendering, source/license, and ZIP checks. The tagged
workflow signs update metadata using the existing repository secret; no private
key is needed outside that job.

Before publication, check the exact draft ZIP checksum and a short owner smoke:
launch/version, typed and button commands, new-tab hover/placement and typing
focus, close-tab typing focus, resize/overflow, and close/reopen. Record only
the environment and results actually reported. Verify signed metadata and the
asset/source inventory, then publish the accepted assets without replacement.

After publication, check anonymous binary/source access, signed update discovery,
and the website download/version links. The existing 1.6.5 size measurement is
historical evidence; record the tagged 1.6.7 ZIP's own exact size and checksum.
