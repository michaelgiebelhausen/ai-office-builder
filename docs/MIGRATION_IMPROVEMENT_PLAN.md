# AI Office Builder migration improvement plan

Draft for the next release. Reviewed November 5, 2026, against the local v0.1.0 implementation and the upstream source files linked below. This is a plan; no migration code or participant folders have been changed.

The priority is to preserve how an existing office works while changing where its files live. The current skill provides collision checks, logged moves, undo plans and structural auditing. Its next improvement should connect those protections to file dependencies, the owner's classification decisions, and verification that work remains usable afterward.

## Preserve the agreed design

Keep Cowork in the OneDrive root, code repositories in ~/Code, the professional and student numbering ranges, agent drawers, client project stages, course folders, and Library raw and wiki separation. Keep optional renaming, explicit bundle approvals, moves rather than copies, no deletion, no overwrite, and undo records. No additional workspace framework, service, package manager or mandatory task system is needed.

## What the sources contribute

| Source | Useful contribution | Boundary for our adaptation |
|---|---|---|
| [ICM paper](https://arxiv.org/html/2603.16021v1) | Explicit inputs and outputs, separation of stable reference from current work, visible checkpoints, and loading only the context needed for a step. | Treat these as design principles to test. Section 4.6 reports informal, self-selected practitioner evidence and no controlled staged-versus-monolithic comparison. Section 6 labels several tracing and debugging ideas as future work. |
| [ICM restructure instructions](https://github.com/RinDig/icm-architect/blob/main/SKILL.md) | Inventory before moving; classify by function; discover incoming references; propose a map; test whether a fresh agent can navigate the result. | Its copy-verify-remove procedure conflicts with our migration rules. Borrow the dependency reasoning and checks, retaining our move engine and CLAUDE.md layout. |
| [PARA inbox workflow](https://github.com/pageel/para-workspace/blob/main/templates/common/agents/workflows/inbox.md) | Inspect a destination project's actual structure before deciding where a file belongs. Leave uncertain material for clarification. | Translate this to the existing agent/client/course system. Do not import extension-based routing or its collision-handling commands. |
| [PARA migration script](https://github.com/pageel/para-workspace/blob/main/cli/commands/migrate.sh) and [audit skill](https://github.com/pageel/para-workspace/blob/main/templates/common/agents/skills/para-audit/SKILL.md) | Version-aware upgrades and an explicit registry of old paths and names. | PARA's migrator mainly upgrades an existing PARA installation; it is not a general messy-home converter. Retain our no-delete/no-overwrite guarantees instead of adopting its maintenance actions. |

These sources were inspected without installing or executing their code. A fork is unnecessary for the proposed original implementation. If code is later reused, review its license and retain required notices.

## Recommended improvements

### 1. Discover what a move could break

Add a bounded, read-only dependency pass after the existing inventory and before bundle approval. Within folders the owner has authorized, inspect supported text links, instruction-file imports and explicit file paths. Include relevant .claude instruction files deliberately rather than excluding every hidden folder. Report unsupported formats and unreadable files as uninspected.

Ask one practical interview question: “Do any apps, shortcuts, scripts, scheduled jobs, shared links, or other people rely on these files staying where they are?” References outside the approved scan cannot be inferred reliably. Ask for specific additional locations when needed; never expand the scan automatically.

The [ICM system-map reference](https://github.com/RinDig/icm-architect/blob/main/references/system-map.md) explains why incoming consumers outside a tree are invisible from inside it. Its [link checker](https://github.com/RinDig/icm-architect/blob/main/scripts/links.py) provides a useful starting pattern, but skips several path types and does not establish that Office documents, application projects or external consumers are safe.

For the first release, detect and hold risky moves. If moving a linked document and all its consumers together preserves their relative paths, propose them as one dependency group. Otherwise hold them until the owner resolves the dependency. Do not silently add symlinks, leave document copies, or rewrite raw evidence. Automatic link repair requires a separate reversible content-edit design later.

Example: moving a whole course folder can preserve a syllabus's link to a sibling reading. Moving only the syllabus into Resources can break it. A scheduled job pointing at either old location requires a separate decision even if every internal link still works.

### 2. Explain placement before requesting approval

Extend the review table from old path and new path to include owner/client/course, active work versus reusable reference versus completed material, placement reason, confidence, and dependency findings. These are planning labels, not new folders. Record unknowns explicitly; neither an old modification date nor a name such as “final” proves that work is finished.

Prefer coherent existing project or course bundles where the target rules allow them. Read existing context and folder conventions before merging into a destination. Where the fixed four client stages require splitting an old project, show that mapping and its dependency consequences first. Keep active full-text documents with the work. Library intake remains the already agreed raw_human/raw_AI decision.

Store the approved map under 00_Inbox/_migration/. Account for every scanned item as move, approved duplicate destination, leave, hold, or excluded. A hold is recoverable progress, not a reason to guess.

### 3. Make approvals and resumption precise

Save a small session record in the existing migration folder: approved roots and exclusions, professional/student mode, renaming choice, approved floor plan, tool/schema version, current phase, held items and bundle IDs. Use versioned snapshots or append-only records. The move log remains the authority for completed moves; the session record must not become a competing move ledger.

Bind each approved bundle to its manifest and source fingerprints. Before execution, check that sources and destinations still match the preview. A changed file, new collision, changed dependency or edited manifest returns that bundle to review. On resume, reconcile the record with the log, undo plans and actual filesystem before proposing remaining work.

Keep scope, floor-plan and per-bundle approvals. This saves people from answering the same questions after an interruption while ensuring that yesterday's approval does not authorize a different move today.

### 4. Verify the result of each bundle

Run one small, representative pilot bundle through move, verification and owner review before proceeding to large batches. Within a bundle, keep the existing durable intent/completion log and undo plan.

Record counts and per-file hashes before moving, then verify destination contents afterward and confirm moved sources no longer occupy their old locations. Check supported links against the proposed layout before execution and the actual layout afterward. On mismatch, stop and preserve recovery information; do not automatically roll back into locations someone may have occupied since the move.

Report structure, content preservation and supported-reference checks separately. Missing external-consumer coverage must remain visible; a clean link report cannot certify every app or shared URL. Keep naming findings advisory. A structurally valid tree alone does not establish a successful migration.

### 5. Test whether the office is usable without the conversation

Adopt the ICM fresh-agent navigation test in our existing naming scheme. Starting from start_here.md and the root .claude/CLAUDE.md, ask a new session to find a client draft, locate a course syllabus, distinguish stable brand guidance from current work, identify the next unfinished bundle, and explain how to undo the last one.

Use the existing Resources/context.md and routing files to fix navigation gaps. Keep Now/Done/Next/Decisions; add concise links to current work and standing references where useful. Do not introduce a mandatory CONTEXT.md in every directory or replace CLAUDE.md with AGENTS.md. Our adaptation of the [ICM core](https://github.com/RinDig/icm-architect/blob/main/references/core.md) is clearer routing and limited reads, without a new instruction hierarchy or arbitrary universal token limit.

Later, record the skill/schema version used to create an office and maintain a compact compatibility map. Upgrades should identify affected metadata and propose changes for review while preserving customized instructions and all user files. This borrows PARA's version-awareness without importing its framework.

## Implementation order

| Phase | Deliverable | Acceptance condition |
|---|---|---|
| A | Update the interview, placement table, pilot procedure and a focused references/migration.md. | A scripted session preserves existing ownership and workflow distinctions and holds unclear dependencies without changing our layout. |
| B | Add Python and PowerShell dependency analysis and approval-bound manifest validation. | Both engines identify supported link risks, report coverage limits, detect changed inputs, and refuse unresolved moves consistently. |
| C | Add session checkpoints, post-move verification and migration-specific reporting. | An interrupted run resumes from verified state, with preserved log and undo history; content mismatch stops further bundles. |
| D | Run expanded synthetic scenarios and fresh-session navigation checks; prepare a reviewed release. | Existing regression tests pass, new acceptance cases pass on supported platforms, and a live Claude scenario passes before claiming behavioral validation. |

Implement A through C as the next bounded improvement. Keep version-aware office upgrades for a later release unless a real existing installation needs them. Do not add background upkeep, automatic archiving, automatic link repair or a new Library synthesis system to this migration project.

## New acceptance cases

1. A client project with sibling links and media sidecars: preserve the bundle's working relationships or hold it; a nice-looking tree with broken dependencies fails.
2. A file used by an authorized external configuration: report the consumer and hold the move until its path is resolved. An owner who declines further scanning sees an explicit coverage limit.
3. An old but active contract, an ambiguously owned file, and an unknown human/AI origin: no guessed archiving, ownership or provenance.
4. A destination that already has customized instructions and working folders: preserve them and explain the merge without overwrite.
5. A resumed half-migration: retain renaming preferences, approved scope, completed bundle history and held items; do not move a source twice.
6. A source changed after approval, or a changed manifest: invalidate the affected approval before any move.
7. Case-only and Unicode-normalization path collisions: detect portable-name conflicts before migration without conflating name equivalence with identical content.
8. Post-move hash or link mismatch, plus an occupied undo destination: stop, report exactly what completed, and preserve both files and recovery records.
9. A fresh session with no transcript: find representative client/course work and the correct recovery instructions using only the office's files.

Run these in generated fake homes. Keep uninspected application formats and real cloud-sharing behavior outside any claim of fully verified compatibility.
