# Migration previews and recovery

Read this before preparing the first move bundle. The folder design and the
user's rename choice remain unchanged.

## Dependency interview and scope

Ask: “Do any apps, shortcuts, scripts, scheduled jobs, shared links, or other
people rely on these files staying where they are?” Record the owner's answer
and any manual checks. Ask permission for specific additional reference folders
when needed. Do not scan the whole home to search for external consumers.

Every manifest must include `reference_roots`: absolute paths the owner approved
for read-only reference inspection. Every moved source must fall within those
roots. The checker reads UTF-8 Markdown, text, HTML, JSON and common text config
and script formats, up to 2 MiB per file and 10,000 visited filesystem entries per bundle (including directories and unsupported files).
A manifest may lower that budget with `reference_limit`, an integer from 1 to 10,000.
It finds ordinary Markdown links, HTML src/href, @ imports and quoted absolute
or explicitly relative paths. It deliberately includes .claude instruction
files. It excludes git metadata, private/vault directories, dependencies and
the migration metadata directory.

This is a bounded check, not proof of compatibility with every application.
Office/media-project files, shortcuts, large text and unreadable text are
uninspected. Record the owner's manual review of these in `dependency_review`.
An owner response about consumers outside the scan is always required. A found
broken link cannot be waived: revise the bundle to preserve it or hold the
affected files. Unknown external consumers remain an explicit coverage limit.
Never edit raw files or add copies or symlinks to make a check pass.

Example manifest:

```json
{
  "bundle": "03_course",
  "description": "Approved course folder, kept together to preserve links",
  "reference_roots": ["C:/Example/Desktop", "C:/Example/Documents"],
  "dependency_review": "Owner checked app projects and shortcuts; no known external consumers. Uninspected formats reviewed.",
  "moves": [
    {"src": "C:/Example/Desktop/MKT_4310", "dst": "10_Class/MKT_4310_Research/Resources/source_documents"}
  ]
}
```

The example keeps full-text course documents and their internal links together
inside the approved course Resources folder. The standard course Projects and
Resources/context.md remain at their agreed locations.

## Preview and approval

`move_bundle.py manifest.json --cowork PATH --dry-run` checks the bundle, hashes
its entire source trees and inspected referrers, and writes
`manifest.json.preview.json`. It moves nothing. Show the move table and the
saved preview's dependency results, uninspected items and scope limit to the
owner. Only after approval, run the same command without `--dry-run`.

Execution requires that saved preview and compares its manifest, source hashes
and dependency report with current files. A source edit, new tree entry,
changed referrer or changed manifest invalidates it. A new destination clash
also stops execution. Prepare a new preview under a new name with
`--approval NEW_PREVIEW.json`, then obtain approval again. Existing previews are
never overwritten. Store manifests and previews outside moved source trees;
the existing 00_Inbox/_migration folder is a suitable location.

PowerShell uses `-DryRun`, `-Cowork`, and `-Approval` for the same operations.
Create and consume a preview with the same language and platform.

Each moved item is checked again immediately before moving. Afterward its
destination tree must match the saved per-file hashes and the old source path
must be absent. Affected supported links are checked in the actual layout as
soon as both ends reach their final locations; links to a later item in the
same bundle are deferred until that move. The log records exact bundle/path
VERIFIED events, and a disappeared dependency stops subsequent moves. A failure stops later
moves; the immutable undo plan and all intent/completion log entries remain.
Do not automatically undo into locations that might now be occupied. Modern
undo plans also refuse changed destination contents.

## Save choices and resume

Save interview answers and the current pending bundle list to a JSON file:

```json
{
  "mode": "student",
  "renaming": "none",
  "courses": ["MKT_4310_Research"],
  "reference_roots": ["C:/Example/Desktop", "C:/Example/Documents"],
  "destination_roots": ["C:/Example/OneDrive/Cowork", "C:/Example/Code"],
  "pending_bundles": ["03_course", "04_notes"],
  "held_items": [],
  "phase": "migration"
}
```

Allowed renaming values are `none`, `fix the worst`, and `full`. Include the
approved floor plan, exclusions and any other interview choices as additional
fields. Save with `move_bundle.py --cowork PATH --save-session choices.json`
or `move_bundle.ps1 -Cowork PATH -SaveSession choices.json`. This adds a new
session snapshot in the migration folder; it preserves previous snapshots.

On resume, run `move_bundle.py --cowork PATH --resume` or its PowerShell
equivalent. The JSON result includes choices, observed bundle states, pending
IDs and blocked IDs. It checks undo fingerprints, actual files and exact bundle/path verification
log entries. Recovery inspects only original paths within saved reference_roots
and destination paths within Cowork or saved destination_roots. Include the
approved Code folder in destination_roots when moving repositories. Fully verified bundles drop out of pending; undone bundles remain
pending. Partial, modified, ambiguous or legacy bundles require inspection and
return a nonzero result. Do not guess missing preferences if no snapshot exists:
read existing logs and ask only for the decisions that cannot be recovered.

Session snapshots preserve choices. The move log, undo plans and verified file
state establish what actually happened. Resume reports do not execute moves.
