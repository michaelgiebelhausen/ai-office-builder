# Development

Use Python 3.10+ and pytest. Runtime Python scripts use only the standard library.

```sh
python -m venv .venv
# Activate the environment using your shell's normal command.
python -m pip install pytest
python -m pytest tests -q
python tools/package_skill.py --out dist/ai-office-builder.skill
```

On Windows the same pytest cases launch all three PowerShell scripts as separate
processes. This provides broader parity checks than a separate partial Pester
suite. Pester is not required. CI tests Windows PowerShell 5.1 and PowerShell 7,
plus Python on Windows, macOS and Linux. Every test uses a new temporary fake home.

Python CLI:
```sh
python skill/ai-office-builder/scripts/scan.py FAKE_HOME/Desktop --out scan.json
python skill/ai-office-builder/scripts/move_bundle.py manifest.json --cowork FAKE_HOME/OneDrive/Cowork --dry-run
python skill/ai-office-builder/scripts/move_bundle.py manifest.json --cowork FAKE_HOME/OneDrive/Cowork
python skill/ai-office-builder/scripts/move_bundle.py --undo UNDO_FILE --dry-run
python skill/ai-office-builder/scripts/audit.py FAKE_HOME/OneDrive/Cowork --mode professional --code FAKE_HOME/Code
```

PowerShell has the same parameter names and JSON schemas, with PowerShell's
single leading dash: `-Cowork`, `-DryRun` (or `-dry-run`), `-Undo`, `-Out`,
`-MaxFiles` (or `-max-files`), `-Mode`, `-Code`, `-Json`. Quote paths containing
spaces. Pass multiple scan roots as an array when calling within PowerShell.
Undo JSON files are engine-specific: use the same script language that made
them. Python tracks file identity; PowerShell tracks file hashes. Both refuse
occupied restore paths. Output wording is human-readable; JSON key names and
exit codes are the compatibility contract (0 success, nonzero failure).

Manifests require `reference_roots` (explicit authorized absolute inspection roots),
`dependency_review` (owner response about uninspected and external consumers),
and `{ "bundle": "03_client", "description": "...", "moves": [
{ "src": "/absolute/source", "dst": "21_Client/Resources/file.txt", "note": "optional" }
] }`. Absolute destinations permit approved repo moves to `~/Code`. Resolve
duplicates in the approved manifest by redirecting extras to
`00_Inbox/_duplicates/`, adding `_dupN` when needed. The tool never silently
reroutes user files. Relative destinations cannot escape Cowork.

Undo plans are exclusively created before the first move; reuse of a bundle ID
is refused. Intent and completion log lines are flushed to disk per move. After
an interruption, inspect the log and undo plan before continuing with a new ID.
No-replace rename primitives prevent overwrite races; cross-filesystem moves
stop rather than copying and deleting. Files and destination parents must not
be symlinks/junctions. Do not run concurrent migrations or change folder links
while a bundle is running. Cloud files must be fully downloaded first; ensure
OneDrive is healthy before proceeding. Undo does not remove empty directories.

Tag `v*` to run CI, package the single top-level `ai-office-builder/` skill
folder, and attach `ai-office-builder.skill` to a GitHub Release. No test homes,
caches, credentials, or local environment files enter the release archive.

## Preview and session safeguards

See [migration_safety.md](skill/ai-office-builder/references/migration_safety.md).
Successful dry runs create an immutable MANIFEST.preview.json by default. Real
runs require this snapshot. Use --approval NEW.json for a changed plan, with
renewed owner approval; PowerShell uses -Approval. Source inventories and
inspected references are rechecked. Each move logs MOVED and then VERIFIED only
after comparing the destination inventory with the approved hashes.

Use --save-session CHOICES.json to add an interview snapshot and --resume to
reconcile the latest choices against fingerprints, actual files and verification
logs. Both require --cowork. Native parameters are -SaveSession and -Resume.
Legacy undo records without fingerprints are reported as blocked on resume.
Migration and undo remain available for them; inspect them explicitly.

Reference inspection is bounded and pattern-based, not a complete language or
application parser. Unsupported formats and external consumers require owner
review. Broken supported references cannot be waived. No automatic link repair
is performed. Preview files must be outside moved source trees.
