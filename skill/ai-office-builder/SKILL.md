---
name: ai-office-builder
description: Guided setup that turns a messy or half-organized computer into an AI-ready "Cowork" office — interviews the user (professional or student), proposes and builds numbered agent folders with CLAUDE.md job descriptions, sets up a ~/Code folder, builds a second-brain Library, then migrates and optionally renames their existing files in approved, logged, undoable bundles. Use this whenever someone wants to organize their files for AI agents, set up a Cowork / agentic folder structure, clean up Desktop/Documents/OneDrive, "build my AI office", migrate files into a new folder system, or check whether an existing Cowork folder still follows the structure — even if they don't name the skill.
---

# AI Office Builder

Take someone from "files everywhere" to a Cowork folder their AI team can actually work in. The user ends up as the manager: an assistant at the root that sees everything, specialist agents in their own folders, client or job work in its own folders, and a Library that turns old material into short wiki cards.

The person is usually a knowledge worker or student, not a developer. Talk like a helpful colleague. When you introduce an idea, give one or two plain sentences of rationale at the moment it is used ("Each numbered folder in the 10s is one AI employee. Its CLAUDE.md is its job description."). Use the office-building metaphors (front door, floor plan, rooms, assembly line). Don't lecture up front, and don't name frameworks (Johnny Decimal, PARA, ICM, Karpathy) unless asked "why this way?".

Expect a 60–90 minute session. Offer natural stopping points after the skeleton is built, after the Code step, and every few bundles. Everything is resumable from the migration log.

## Reference files — read when you reach that phase

- `references/structure.md` — the target layout for professionals and students, what goes in every folder, and the conformance checklist. Read before Phase 4.
- `references/templates.md` — text for start_here.md, every CLAUDE.md, context.md, Library routing. Read before Phase 5.
- `references/naming.md` — rename rules, collision handling, the confidence bar. Read before Phase 6.
- `scripts/scan.py` — read-only inventory of chosen folders → JSON summary.
- `scripts/move_bundle.py` — executes one approved bundle: collision checks, moves, log, undo file.
- `scripts/audit.py` — checks a Cowork folder against the checklist.

Use Python 3.10+ when available (`python3 --version`, `python --version`, or
`py -3 --version` on Windows; verify this starts a real interpreter). Otherwise
on Windows use the bundled native `scripts/scan.ps1`, `move_bundle.ps1`, and
`audit.ps1`; they require no Python and work in Windows PowerShell 5.1+.
Use PowerShell parameter syntax: `-Out`, `-Cowork`, `-DryRun`, `-Undo`, `-Mode`,
`-Code`, `-Json`, and `-MaxFiles`. Quote every path and supply scan roots as an
array: `& scripts/scan.ps1 -Roots @('C:/Example/Desktop','C:/Example/Documents') -Out scan.json`.
Run a bundle with `& scripts/move_bundle.ps1 manifest.json -Cowork 'C:/Example/OneDrive/Cowork' -DryRun`;
remove `-DryRun` only after approval. Undo with the same engine that created it:
`& scripts/move_bundle.ps1 -Undo undo_03_client.json`.
Audit with `& scripts/audit.ps1 'C:/Example/OneDrive/Cowork' -Mode professional -Code 'C:/Example/Code'`.

Python is not guaranteed on Mac; developer tools may supply it but must be
checked. If absent, stop script execution and explain that Python 3.10+ is
needed. Do not invent shell equivalents of safety-critical moves.

The scripts refuse cross-filesystem moves instead of copying and deleting.
Explain that limitation if an approved source is on another drive. They also
refuse symlink/junction paths and overlapping moves. Do not change links or run
concurrent migrations during a bundle. Require cloud files to be downloaded.
Scan and audit output files must be new paths; choose a new output name when
resuming. Migration logs append; bundle IDs and undo plans are never reused.
Partial failure: stop, inspect the persisted undo plan and INTENT/MOVED log,
then undo or prepare only unfinished items under a new approved bundle ID.

## Ground rules (the why matters)

- **Nothing moves without approval.** The user sees each bundle as old path → new path before it runs. Their files, their call.
- **Never delete.** Exact duplicates go to `00_Inbox/_duplicates/` for the user to review. Deleting is irreversible; moving isn't.
- **Never overwrite.** Same-name clashes get resolved before a bundle runs (see naming.md).
- **Log every move** in `Cowork/00_Inbox/_migration/migration_log.md`, and write an undo file per bundle. This is what makes the whole thing safe and resumable.
- **Structure is the goal; renaming is optional.** If the user doesn't want their files renamed, don't push. The naming rules still go into CLAUDE.md so new files follow them.
- **Don't touch the inside of git repos.** A repo's structure belongs to that project.
- **Moves, not copies.** Copies double OneDrive storage and leave two versions of everything.

## Phase 0 — Orient (and resume)

1. Detect the OS and which folders you can actually read and write. If you can't reach the user's Desktop, Documents, or OneDrive, tell them exactly which folders to grant access to before anything else.
2. Find their OneDrive folder (often `OneDrive - <Organization>`). The new office goes at `<OneDrive>/Cowork/` because OneDrive backs it up automatically. If OneDrive is absent, explain that the agreed location is unavailable and ask before choosing another location.
3. If `Cowork/00_Inbox/_migration/migration_log.md` already exists, this is a resume: read the log, summarize what's done, and continue from the next unfinished phase or bundle. If they only want a check-up, jump to Phase 8.

## Phase 1 — Interview

Ask conversationally, a few at a time, not as a form:

1. Are you a student, a working professional, or both?
2. What eats your week? Name the 5–8 kinds of recurring work. (Students: classes, job search, money, fitness, a job or side hustle…)
3. Who do you do work *for*? Employers, clients, businesses you run. Students: any job or side hustle — those work like clients; skip if none.
4. Professionals only: what personal things need coordinating with work? (health, travel, house…) Students skip this — as a full-time student most of life is one bucket, so personal bots live alongside school bots in the 10s.
5. How much renaming do you want? **None** (keep every name) / **Fix the worst** (spaces, "final_final", clashes) / **Full cleanup** (apply the naming rules where confident).
6. Which places should I look through? Offer what you detected: Desktop, Documents, OneDrive, Google Drive, Dropbox. Downloads is opt-in and handled last. Never scan system or app folders or `Pictures/` (photo libraries break when moved).

## Phase 2 — The Code folder

Ask whether they have a GitHub account and a code folder.

- Create `~/Code/` at the user's home folder if it doesn't exist — deliberately **outside** OneDrive. Explain: this is where vibe-coded apps and code projects live; it's backed up through GitHub, not OneDrive, because OneDrive syncing a code project can corrupt it.
- If they have GitHub and the `gh` command is installed and logged in, list their repos and offer to clone any that aren't local. If `gh` isn't available, skip that and say why — don't derail into installing tools.
- Later, during the scan, any folder containing `.git` (especially inside OneDrive) becomes the first migration bundle: move to `~/Code/<repo-name>/`. Loose code that isn't a repo (scripts, unzipped projects): ask — move to `~/Code/`, treat as an ordinary file, or leave.

## Phase 3 — Scan (read-only)

Run `python scripts/scan.py <folder> [<folder> ...] --out <workspace>/scan.json` on the folders they chose. It reports file-type counts, clusters (folders full of invoices, syllabi, videos), git repos, big media folders, name clashes, likely duplicates, spaces in names, and deep nesting. Scanning may download cloud placeholders to hash their complete contents; explain that and use locally available files when possible. Nothing moves. Read the JSON and summarize it for the user in a few lines.

## Phase 4 — Propose the office

Read `references/structure.md`. Propose, with a one-line reason for each folder drawn from their answers or the scan ("11_Bookkeeping — you mentioned invoicing and I found 40 invoices"):

- The root assistant: **Office Manager** (professionals) or **Personal Assistant** (students). It lives at the root, reads the floor plan, and sees every folder.
- 4–7 agent folders in the 10s. Start from the starter catalog in structure.md, but only propose what the evidence supports. Fewer is better — empty folders are noise, and adding a bot later is just a new folder.
- 20s: one folder per client/employer/business (students: optional job/side-hustle folders).
- 30s (professionals only): personal areas.

Let the user add, cut, and rename. Don't build until they say yes.

## Phase 5 — Build the skeleton

Read `references/templates.md`. Create the folders and fill every CLAUDE.md, start_here.md, and context.md from the interview — real content, not empty placeholders. Keep each CLAUDE.md under 200 lines: only their decisions and standards, no step-by-step instructions.

Build the **Library last**, after the agent folders are final, because each agent gets its own wiki: `01_Library/raw_human/`, `raw_AI/`, one `1x_<Agent>_Wiki/` per agent, and a Library CLAUDE.md with the routing table. Explain: wikis hold general knowledge and things you don't need word-for-word (meeting transcripts, documents from finished projects), boiled down to short cards so agents read 50 lines instead of 20 transcripts. Active projects and current classes keep their full documents where the work is. One wiki per agent means granting access once, not every time a client or class is added.

Show the finished tree. This is a good stopping point.

## Phase 6 — Migrate in bundles

Read `references/naming.md`. Group files into bundles **by destination** ("→ 21_Acme", "→ 10_Class/MKT_4310"), worked in this order:

1. Code repos → `~/Code` (Phase 2).
2. High-confidence clusters (an obvious course folder, a client folder, a pile of invoices).
3. Mixed or ambiguous groups — ask questions as you go.
4. Library material: captured articles, PDFs, transcripts, notes from finished projects → `raw_human/`; AI-generated reports and chat exports → `raw_AI/`.
5. Downloads (only if opted in).
6. Leftovers: per bundle, the user chooses `00_Inbox/to_sort/` or leave in place.

Where client work goes: client projects live in that client's 20s folder (`Projects/` with the four ICM stages, brand assets in `Resources/`), never inside an agent folder. Agent folders hold the bot's know-how and its own non-client work.

For each bundle:

1. Write a manifest JSON (format in `scripts/move_bundle.py`), applying renames only at the level the user chose.
2. Run `python scripts/move_bundle.py <manifest> --cowork <Cowork path> --dry-run`. Fix every clash it reports before going further.
3. Show the user the table (old → new, renames side by side). Over ~50 files, show a summary plus a sample. They can approve all, edit lines, skip files, or skip the bundle.
4. Run without `--dry-run`. It logs every move and writes `undo_<bundle>.json`.
5. Warn before moving large media folders from a non-synced location into OneDrive — that starts a big upload.

If the user wants a bundle reversed: `python scripts/move_bundle.py --undo <undo file>`.

## Phase 7 — Library follow-through (optional)

The wikis start with just an index card. Offer either a first synthesis pass now (read new items in raw, write one-concept cards with YAML frontmatter: title, tags, source_raw) or a weekly scheduled task that does it. Filling wikis during migration would double the session, so it's always a separate, optional step.

## Phase 8 — Audit and report

Run `python scripts/audit.py <Cowork path> --mode professional|student --code ~/Code`. Structure problems are real problems; naming findings are suggestions only. Offer to fix structural gaps.

Write `00_Inbox/_migration/migration_report.md` and tell the user in a few lines:

- What was built (the tree, at two levels).
- How many files moved, how many renamed, what remains in old locations.
- Anything flagged: duplicates to review, dates guessed from file timestamps.
- The next 2–3 steps: give each agent access to its wiki folder, set up the weekly raw → wiki pass, review `_duplicates/`.

The audit can be run on its own later ("check my Cowork folder") — structures drift, and a periodic tidy-up keeps the office working.
