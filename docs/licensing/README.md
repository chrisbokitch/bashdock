# BashDock licensing

BashDock adopts **GNU GPL version 3 only**, SPDX `GPL-3.0-only`, from this
revision. See the root `LICENSE` and `COPYRIGHT`. The earlier restrictive
source-available proposals were not adopted and have been removed; Git history
retains them as discussion drafts. They impose no additional conditions.

People may use BashDock personally or at work, modify it, and redistribute it,
including selling copies, under GPLv3. Using BashDock to work on another project
does not license that project under GPL. Private/internal modifications need not
be published. Distribution of covered derivatives requires GPL compliance,
including corresponding source; changes need not be submitted upstream.

Contributions intended for inclusion are offered under GPL-3.0-only unless
expressly identified otherwise and accepted as compatible third-party material.
Contributors retain their copyright. This project does not require copyright
assignment or grant the maintainer a special right to relicense contributions.

## Distribution while the repository is private

The repository need not be public. Every executable recipient must have access
to the corresponding source under the applicable license. The release workflow
therefore includes source archives alongside binaries; a private GitHub URL is
not used as a substitute. If binaries are shared outside GitHub, share the
matching source assets and checksums too. Recipients can redistribute them.

For a public launch, making the repository public provides a useful additional
source location. Review history, secrets, personal data, Actions logs/artifacts,
and repository settings before changing visibility. Publishing source does not
revoke rights granted for existing versions, and later pricing changes do not
withdraw GPL permissions from compliant recipients.

## Dependency review and maintenance

The pinned baseline is Qt/PySide 6.10.3, pywinpty 3.0.5, and PyInstaller 6.16.0.
The reviewed x64 pywinpty wheel includes Microsoft ConPTY/OpenConsole version
1.24.260512001; both files were matched byte-for-byte to that MIT-licensed NuGet
package. Legacy winpty binaries are MIT licensed and identify GCC 5.3.0 (MSYS2 Rev5); MinGW notices and the GCC Runtime Library Exception are included. `requirements/native-runtime.json` records their exact wheel hashes and notice provenance. The Rust source bundle covers
all registry crates in pywinpty's published Cargo.lock, including build-only and
platform-specific crates as a conservative superset.

Qt/PySide source archive hashes in `requirements/release-sources.json` come from
Qt's official `.sha256` downloads. pywinpty's source hash comes from PyPI release
metadata. Rust crate hashes come from that pywinpty source Cargo.lock. Downloads
are verified before use and mirrored in release assets. Qt sources include the
Chromium tree and bundled third-party source, license, notice, and attribution
files. PySide wheel metadata alone is insufficient: the pinned wheels include
only the commercial-license text despite declaring open-source options.

Builds record all frozen-file SHA-256 hashes and collect source notices plus
installed package license/notice files, including CPython's aggregate license
and PyInstaller's exception. This is an inventory and distribution mechanism,
not a claim that filename matching independently proves legal compliance.

When updating dependencies, review new/changed license and attribution metadata,
update the source manifest and native notices/provenance, and inspect the actual
Windows artifact before publishing. Do not substitute sources for a different
version or discard LGPL source/replacement rights. Release review includes
runtime components not represented by Python package metadata, especially Qt
plugins, Chromium, native helpers, and Microsoft runtime files.

No public download should be announced until the generated license/source
assets and exact Windows candidate pass the release checklist.
