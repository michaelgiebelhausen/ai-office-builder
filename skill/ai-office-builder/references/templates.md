# Templates

Fill these from the interview. Write real content in the user's terms; delete any section that has nothing to say. Every CLAUDE.md stays under 200 lines and holds only decisions, preferences, and standards — not step-by-step instructions the AI could figure out on its own.

## start_here.md (the front door)

```markdown
# Start here

**Who I am:** <name>, <role / program>. <one line on what they do>.
**What this folder is:** my AI office. Each numbered folder is a room with one job.

## How it's organized
- 00–09 Assets: 00_Inbox (drop zone), 01_Library (second brain)
- 10–19 My AI team: <list each agent and its one-line job>
- 20–29 <Clients / Jobs>: <list>
- 30–39 Personal: <list>          ← professionals only

## My <Office Manager | Personal Assistant>
Lives at this level and can see every folder. Ask it anything that spans rooms.

## Code
Apps and code live in ~/Code (outside OneDrive), backed up to GitHub.
```

## Root .claude/CLAUDE.md (the floor plan)

```markdown
# Floor plan

You are my <Office Manager | Personal Assistant>. You can see every folder. Route work to the right room; don't do specialist work in the wrong one.

## Routing
| When the task is… | Go to | Read first |
|---|---|---|
| <email triage, replies> | 10_Email/ | 10_Email/.claude/CLAUDE.md |
| <anything for Acme> | 21_Acme_Co/ | 21_Acme_Co/.claude/CLAUDE.md |
| <looking something up> | 01_Library/ | 01_Library/CLAUDE.md |

## House rules
- Never delete. Never overwrite a version: save _v2, _v3.
- New files land in 00_Inbox/ unless I say where.
- Client work lives in that client's 2x folder, never in an agent folder.
- Naming: <the rules the user accepted from naming.md, or "keep my names as they are">
- Max 5 folder levels deep.
```

## Agent .claude/CLAUDE.md (who works here)

```markdown
# <Agent name> — <one-line job>

## What I do
- <3–6 bullets in the user's words>

## What I don't do
- <boundaries: e.g. "I draft; I never send email">

## Where things are
- My playbooks and standing context: Resources/ (start with Resources/context.md)
- My wiki: ../01_Library/<NN>_<Agent>_Wiki/
- Client work: in the client's 2x folder; follow that folder's CLAUDE.md.

## Standards
- <voice, formats, tools, naming specific to this agent>
```

Student Class agent: retain the standard Projects/, Resources/context.md and Archive/ drawers; replace "Where things are" with: one folder per current class (course code + title), each with Projects/ and Resources/; at semester end, move a class to Archive/major_classes/ or Archive/gened_classes/; job-search material goes to Archive/job_search/.

## Client .claude/CLAUDE.md

```markdown
# <Client name> (<client code, e.g. AC>)

- Brand files and standards: Resources/
- Projects: Projects/YYYY_Q#_Name/ with 01_brief, 02_spec, 03_build, 04_output
- Drafts in 03_build/, finished files in 04_output/. Never overwrite a version.
- File names: <formula from naming.md, if the user opted in>
```

## Resources/context.md

```markdown
# Context

## Now
## Done
## Next
## Decisions
```

## 01_Library/CLAUDE.md (routing for the second brain)

```markdown
# Library

raw_human/ holds what I captured (transcripts, articles, notes, documents from finished projects). raw_AI/ holds what AI made for me. Raw files are never edited.

Wikis hold general knowledge and things I don't need word-for-word: one concept per card, with YAML frontmatter (title, tags, source_raw).

## Which wiki a raw file feeds
| If the raw file is about… | Update |
|---|---|
| <email, clients' comms habits> | 10_Email_Wiki/ |
| <writing, voice, past campaigns> | 11_Writing_Wiki/ |

Active projects and current classes are NOT summarized here — their full documents stay with the work.
```

## Wiki index card (`<NN>_<Agent>_Wiki/index.md`)

```markdown
---
title: <Agent> wiki index
tags: [index]
---
# <Agent> wiki
One card per concept. Link cards with [[card_name]].
```
