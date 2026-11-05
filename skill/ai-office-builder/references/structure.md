# Target structure

The first digit of a top-level folder says what kind of folder it is. Two-digit prefixes keep the order fixed.

| Range | What | Professionals | Students |
|---|---|---|---|
| 00–09 | Assets: things that mostly get stored | `00_Inbox/`, `01_Library/` | same |
| 10–19 | Agents: one AI employee per folder | 4–7 specialist bots | school *and* personal bots together |
| 20–29 | Who you work for | clients, employers, businesses | optional: a job or side hustle |
| 30–39 | Personal areas that touch work | health, travel, house… | none — lives in the 10s |

The root assistant (Office Manager / Personal Assistant) is not a numbered folder. It lives at the root: it reads the floor plan (root CLAUDE.md) and can see every folder.

## Starter agent catalog

Suggest only what the interview or scan supports. Rename freely.

- Professionals: Email, Writing, Social, Analytics, CRM, Bookkeeping, Legal, Creative, Calendar/Coordination.
- Students: Class, Calendar, Money, Fitness, Career.

## Professional layout

```
<OneDrive>/Cowork/
├── .claude/
│   └── CLAUDE.md                 # floor plan: routing table + house rules
├── start_here.md                 # front door
├── 00_Inbox/
│   ├── to_sort/
│   ├── _duplicates/
│   └── _migration/               # migration_log.md, undo files, report
├── 01_Library/
│   ├── CLAUDE.md                 # which wiki each raw file feeds
│   ├── raw_human/                # what you captured; never edited
│   ├── raw_AI/                   # what AI made for you; never edited
│   ├── 10_Email_Wiki/            # one wiki per agent
│   └── 11_Writing_Wiki/
├── 10_Email/                     # an agent folder
│   ├── .claude/
│   │   └── CLAUDE.md             # who works here
│   ├── Projects/                 # the bot's own, non-client work
│   ├── Resources/
│   │   └── context.md            # Now / Done / Next / Decisions
│   └── Archive/
├── 11_Writing/ …
├── 21_Acme_Co/                   # a client
│   ├── .claude/
│   │   └── CLAUDE.md
│   ├── Resources/                # logos, brand files, contracts
│   └── Projects/
│       └── 2026_Q4_Holiday_Launch/
│           ├── 01_brief/         # the intake
│           ├── 02_spec/          # the blueprint
│           ├── 03_build/         # the workshop
│           └── 04_output/        # the loading dock
└── 30_Health/                    # personal
    ├── Projects/
    └── Resources/
```

Notes:

- **Client projects** use the four stages (`01_brief`→`04_output`). Drafts are made in `03_build/`; finished files go to `04_output/`. Media-heavy projects add `Footage/`, `Audio/`, `Thumbnails/` (etc.) buckets inside `03_build/`.
- **Agent Projects/** are plain project folders (`YYYY_Q#_Name/`) without the four stages — the stages are for client work with briefs and deliverables.
- **Personal folders** get `Projects/` and `Resources/` too, for consistency — people have lots of personal projects.
- A finished project moves whole into that folder's `Archive/`.

## Student layout

```
<OneDrive>/Cowork/
├── .claude/CLAUDE.md
├── start_here.md
├── 00_Inbox/ …
├── 01_Library/ …                  # one wiki per agent, e.g. 10_Class_Wiki/
├── 10_Class/
│   ├── .claude/CLAUDE.md
│   ├── Projects/
│   ├── Resources/context.md
│   ├── MKT_4310_Consumer_Behavior/   # one folder per current class
│   │   ├── Projects/                 # papers, group projects, exam prep
│   │   └── Resources/                # syllabus, notes, context.md
│   ├── ACCT_2100_Financial_Accounting/
│   ├── …
│   └── Archive/                      # past semesters
│       ├── major_classes/
│       ├── gened_classes/
│       └── job_search/
├── 11_Calendar/   (standard agent drawers: Projects/ Resources/ Archive/)
├── 12_Money/
├── 13_Fitness/
├── 14_Career/
├── 21_[Job]/          # optional
└── 22_[Side_Hustle]/  # optional
```

Class folders are named by course code + short title. When a semester ends, each class moves to `Archive/major_classes/` or `Archive/gened_classes/`; job-search material goes to `Archive/job_search/`.

## Code (outside Cowork)

```
~/Code/                 # user home, NOT inside OneDrive
├── <repo-name>/        # one folder per GitHub repo; insides untouched
└── …
```

## Depth rule

At most 5 folder levels below `Cowork/`; level 6 is for files only. If a move would land deeper, flatten (merge a level into the name) and say so.

## Conformance checklist (what audit.py checks)

Structure — these are pass/fail:

- Top-level folders under Cowork are numbered `NN_Name`, in valid ranges (students: no 30s).
- Root has `start_here.md` and `.claude/CLAUDE.md`; the root CLAUDE.md mentions every agent folder.
- `00_Inbox/` and `01_Library/` exist; Library has `raw_human/`, `raw_AI/`, its own `CLAUDE.md`, and a `*_Wiki/` for each agent.
- Every agent (10s), including Class, has `.claude/CLAUDE.md`, `Projects/`, `Resources/context.md`, and `Archive/`. Class also has one folder per course and the three specified Archive categories.
- Every 20s and 30s folder has `Projects/` and `Resources/`.
- Client project folders contain the four stage folders.
- Every CLAUDE.md is under 200 lines.
- Nothing is nested more than 5 folder levels deep.
- No `.git` folders inside Cowork/OneDrive; repos live in `~/Code`.

Naming — advisory only:

- Spaces in names, "final"/"FINAL"/"copy" in names, project folders not starting `YYYY_Q#_`.
