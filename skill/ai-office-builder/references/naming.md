# Naming rules

Apply only at the level the user chose in the interview:

- **None** — keep every name. Still resolve clashes (below), because a move must never overwrite.
- **Fix the worst** — spaces → underscores, strip "final", "FINAL", "copy", "(1)", resolve clashes.
- **Full cleanup** — everything below, where confident.

The confidence bar: if you aren't sure what a file is or what date it belongs to, keep its name. A wrong rename is worse than an ugly one. Always show renames side by side with the original before a bundle runs.

## The patterns

| Kind of file | Pattern | Example |
|---|---|---|
| Standalone documents, knowledge | short, descriptive keywords | `brand_guidelines.pdf`, `voice_principles.md` |
| Project folders | `YYYY_Q#_Project_Name/` | `2026_Q4_Holiday_Launch/` |
| Transactions, records, events | `Vendor_DocType_YYYY-MM-DD.ext` | `Chase_Statement_2026-10-15.pdf` |
| Client creative assets | `[Project#]_[ClientCode]_[Sub]_[v#]_[Tag].ext` | `03_AC_02_v3_9x16.mp4` |
| Scheduled releases / dated drafts | `YYYY-MM-DD_...` | `2026-11-20_IG_Reel_script_v2.md` |
| Class folders | `DEPT_NNNN_Short_Title/` | `MKT_4310_Consumer_Behavior/` |

Everywhere: underscores, no spaces. ISO dates (YYYY-MM-DD) so files sort in time order. Versions frozen as `_v1`, `_v2`, `_v3`; never "final_final". Placement or device tags at the end (`_9x16`, `_FR`, `_Pocket3`).

Dates: take them from the file's content (invoice date, statement period) where possible. If you fall back to the file's modified date, flag it in the bundle table and the report.

Client creative formula: only when the user has given client codes (two letters, e.g. AC = Acme) and the file clearly belongs to a numbered project.

## Clashes

Before every bundle, the dry run reports two files heading to the same path, or a destination that already exists. Resolve each one:

| Situation | Resolution |
|---|---|
| Identical contents | Move the extra copy to `00_Inbox/_duplicates/` (keep its original name; add `_dupN` if needed). |
| Versions of the same document | Order by modified date → `_v1`, `_v2`, … |
| Unrelated files, same name | Add a descriptor from the content or the old parent folder: `syllabus.pdf` → `MKT_4310_syllabus.pdf`. |

Never resolve a clash by overwriting.
