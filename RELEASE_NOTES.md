# v0.2.0

Adds four safeguards for student and professional migrations, preserving the agreed folder design.

- Checks supported local references within explicitly approved folders; holds moves that would break them and records manual review of unsupported or external dependencies.
- Requires a saved preview, binding the manifest, inspected references and complete source inventories to the approved plan. Changes invalidate that preview.
- Verifies destination contents after each move and stops subsequent moves on mismatch, preserving logs and undo records.
- Saves interview choices and pending bundles, then reconciles recovery using authorized paths, exact verification events, hashes and actual file locations.

Both Python and native PowerShell are supported, including Windows PowerShell 5.1 with UTF-8 filenames and answers. Existing v0.1.0 undo records remain available but require explicit inspection during session recovery. Manifests now require reference_roots and dependency_review; a successful dry run creates the preview needed for execution. See the bundled migration_safety reference and DEVELOPING.md.

Validation uses generated fake homes and includes reference failures, stale previews, interruption/corruption handling, session reconciliation, Unicode metadata and scan budgets. Reference inspection is pattern-based and bounded; it does not certify every application format, external consumer or real OneDrive behavior. Live Claude Desktop/Cowork installation remains unverified; the earlier optional Claude planning evaluation was blocked by an expired OAuth token.
