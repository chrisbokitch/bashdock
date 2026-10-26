# BashDock 1.0 readiness

The intended feature set includes tabs and per-tab command bars, remembered
folders/geometry, saved workspaces with persistent tab identities, terminal
defaults and per-tab themes, settings backup/recovery, and **automatic updates**.

Implemented foundations:

- Core tabs, workspace groups, command buttons and terminal customization.
- Window/session configuration persistence and settings export/recovery.
- Windows CI, full portable packages, checksums and matching source archives.
- GPLv3 adoption and dependency-notice/source collection.
- Signed-update discovery/download, yellow clickable footer action, independent
  installer helper, user-controlled restart and startup-failure rollback.

Remaining release gates:

- [ ] Configure/back up the update signing key and GitHub Actions signing secret
      before the first public candidate; see [AUTO-UPDATES.md](AUTO-UPDATES.md).
- [ ] Validate an actual signed update between two packaged versions on the
      Windows VM, including intentional failed-start rollback.
- [ ] Confirm Microsoft runtime redistribution entitlement.
- [ ] Exercise the tag → signed draft-release → reviewed publication workflow.
- [ ] Finish screenshots, troubleshooting/support documentation and public
      download/source links.
- [ ] Run the complete candidate ZIP acceptance checklist, including workspaces,
      settings recovery, terminal behaviour and 100%/125%/150% display scaling.
- [ ] Publish a public beta, address findings, then deliberately choose 1.0.0.

An update check and download never authorize closing running shell commands.
Installing an update always requires the user's restart confirmation.

Future feature investigations are tracked separately in the
[post-1.0 feature roadmap](FEATURE-ROADMAP.md); they do not block this release.
