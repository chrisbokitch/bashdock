# BashDock licensing policy and review notes — draft

**DRAFT FOR REVIEW — NOT ADOPTED.** Prepared October 25, 2026. This document explains a proposed policy and identifies decisions for Chris Bokitch and legal counsel. It does not grant a license, adopt the accompanying draft, complete the dependency audit, or announce a paid product.

The proposed license is [LICENSE-DRAFT.md](LICENSE-DRAFT.md). Its draft revision is separate from BashDock's application version.

## Intended policy

BashDock should be available at no charge for personal and workplace use. People may use it while developing or operating commercial software. They may not sell BashDock or make a commercial offering from its code without separate permission from the relevant copyright holders.

The proposed permission boundaries are:

| Activity | Proposed treatment |
| --- | --- |
| Run BashDock at home, school, a company, a nonprofit, or a public body | Allowed without charge |
| Build, sell, test, deploy, or administer an unrelated product using BashDock | Allowed |
| Use BashDock to SSH into a paid server | Allowed |
| Modify it privately for personal or internal organizational use | Allowed; no obligation to publish internal changes |
| Share an official build or a modified fork without charge | Allowed under the same restrictions, with notices and corresponding source |
| Charge for BashDock, a fork, a license, a download, or a required subscription | Requires separate permission |
| Include BashDock or its code in a paid product, installer, or software bundle | Requires separate permission |
| Sell access to BashDock itself as a hosted or managed software service | Requires separate permission |
| Offer development, training, or administration services using BashDock as an ordinary tool | Allowed when the software itself is not the paid offering |
| Seek genuinely optional donations or sponsorships | Proposed as allowed, with no access, feature, or license advantage purchased |
| Sell independently written software with similar ideas or features | Not restricted by this copyright license merely because of similarity |
| Exercise rights granted by a bundled library's own license | Preserved; those components keep their separate licenses |

A free fork must identify that it is modified and must not imply it is an official BashDock release. The draft imposes source-sharing on redistributed modifications; this is a proposed policy choice, not an existing adopted obligation.

## Source-available terminology

Use **source-available** for the proposed licensing model. Do not label it MIT, GPL, OSI-approved, or open source. The commercial restrictions do not meet the Open Source Definition's redistribution requirements.

A proposed short website/README description, for use only after adoption, is:

> BashDock 1.x is free to use for personal and business work. Its source is available for inspection, internal customization, and free redistribution under the BashDock license. Selling BashDock or incorporating its code into a commercial offering requires separate written permission. Third-party components retain their own licenses.

This summary must link to the final operative license and cannot replace its terms.

## Version 1.x and future commercial versions

The proposed project commitment is that **all BashDock 1.x releases remain free of charge for permitted use**, including workplace use. The current pre-1.0 line should use the same policy if Chris chooses to adopt it before 1.0.

Future major versions, such as 2.x, may have different pricing or licensing. No paid version or release date is promised. A future paid release does not introduce charges for a 1.x release already licensed on a perpetual, royalty-free basis to compliant users.

This distinguishes a project commitment about future 1.x releases from the operative permission granted for each existing release. The copyright holder must actually apply the chosen terms to each release; publishing a policy alone does not automatically license every future contribution or artifact.

BashDock's owner may choose terms for code the owner has the authority to license. Third-party code and outside contributions require their own rights analysis. Renaming a fork to "2.0" does not avoid restrictions on code copied from a covered 1.x release.

## Contributions and future licensing flexibility

No contributor agreement is created or accepted by these documents. The redistribution clause in the proposed license does not give Chris automatic permission to relicense someone else's contributions commercially.

Before accepting outside code or assets into the maintained project, establish contributor terms that expressly address permission to use and sublicense contributions in future commercial and proprietary editions, alongside any relevant patent rights. Contributors should understand those terms and confirm that they have authority to grant them. Keep a record of the permissions received.

A contribution sign-off or a public pull request should not simply be assumed to provide the commercial relicensing rights the project needs. Have counsel select or prepare a suitable contributor agreement rather than treating the draft application license as one.

## Third-party dependencies: separate work still required

The draft license is intended to cover BashDock-owned material. It does not convert Qt/PySide, Qt WebEngine/Chromium, Python, xterm.js, pywinpty, native console helpers, or other included components to this license.

Before public distribution:

1. Inventory the **actual packaged Windows artifact**, including DLLs, helpers, resources, plugins, vendored JavaScript, and transitive dependencies. The Python dependency list alone is insufficient.
2. Determine each included component's exact version, applicable license option, notices, and redistribution requirements. Check for components incompatible with the proposed application terms; a generic third-party exception cannot fix every license conflict.
3. Assemble the required copyright notices and license texts and expose them from the application and release ZIP.
4. Fulfill corresponding-source obligations for LGPL components using a compliant method. Do not assume a generic upstream homepage link satisfies them.
5. Verify that the packaged application permits required library replacement, relinking, running modified libraries, and reverse engineering for debugging those changes. The existing onedir build is a starting point, not proof of compliance.
6. Preserve evidence of the audit and source availability for each distributed version, and add packaging checks for required notice files.

The draft's third-party exception deliberately preserves those rights. Final compatibility still depends on what is actually distributed and the terms selected for each component.

## Items to resolve before adoption

These are review points, not claims that the draft is already enforceable or complete:

- **Rights and authority:** confirm the ownership and licensing authority for the proposed Covered Code and assets, and the identity of the Licensor(s).
- **Commercial boundary:** review the definitions and examples so ordinary workplace use remains permitted while commercial forks, incorporation, paid bundles, and paid access to BashDock itself remain restricted.
- **Donations and services:** the draft allows genuinely optional donations and ordinary paid help/training. Confirm that this fits Chris's intent. Review paid customization delivered to clients, contractors' private modifications, affiliate distribution, ad-funded sites, and bundled distributions against that intent.
- **Free-fork source sharing:** confirm the requirement to provide corresponding source and build instructions with free binary redistribution, and decide whether any source-availability period after distribution should also be required.
- **Version commitment:** confirm the treatment of the pre-1.0 line and the promise for all future 1.x releases. Ensure neither existing user rights nor later commercial options are misrepresented.
- **Patent grant:** review the limited patent permission, its scope, and whether patent-defense language is wanted. No patent ownership or clearance has been established by preparing this draft.
- **Breach and cure:** review the 30-day notice/cure process, consequences, and practical enforcement approach.
- **Jurisdiction and assent:** British Columbia/Canada is proposed. Review mandatory consumer rights, international users, how permission conditions are presented, and whether further contractual acceptance is appropriate.
- **Branding:** review name/logo rights and modified-build attribution without claiming unverified trademark registration.
- **Dependencies:** complete the actual binary audit and the LGPL/Chromium notice, source, and replacement work described above.
- **Contributor terms:** adopt appropriate terms before accepting contributions intended for possible future commercial editions.

## Adoption procedure

1. Review the intended policy with Chris and obtain legal review of the final text and dependency compatibility.
2. Resolve the items above and give the final license a distinct title and revision identifier.
3. Adopt an operative root `LICENSE` expressly; do not merely remove the draft banner from a documentation page and assume release packaging has changed.
4. Update project metadata, README, About/licensing UI, and website wording consistently, without claiming OSI approval. License the separate website repository deliberately rather than assuming the app license applies to it.
5. Configure the build and packaging scripts to include the final project license, complete notices, required license texts, and source/replacement instructions. Check the resulting ZIP.
6. Establish contributor terms, record adoption, and tag the intended release with those exact materials.

Preparing these drafts does not perform any of these adoption steps. They are not copied into executable builds or release ZIPs by the current packaging rules.

## Reference material for review

These sources informed the review topics; they do not endorse this custom draft or establish that it complies with law or dependency licenses:

- [Open Source Initiative — Open Source Definition](https://opensource.org/osd): commercial redistribution and other requirements for the open-source designation.
- [Qt — LGPL obligations](https://www.qt.io/development/open-source-lgpl-obligations): notices, corresponding source, and recipients' library-modification rights.
- [Qt WebEngine licensing](https://doc.qt.io/qt-6/qtwebengine-licensing.html): Qt and Chromium licensing layers; use version-specific materials during the release audit.
- [GNU — LGPL version 3](https://www.gnu.org/licenses/lgpl-3.0.en.html): the operative license text, including combined-work provisions.
- [Apache Software Foundation — Individual Contributor License Agreement](https://www.apache.org/licenses/icla.pdf): an example showing that contributor copyright and patent grants need express terms. This is not proposed for adoption unchanged.
- [PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/): an existing broad noncommercial model. The BashDock draft is a custom proposal; it is not PolyForm Noncommercial, and broad noncommercial-use restrictions would not express the intended unrestricted workplace use.
