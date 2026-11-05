# v0.1.0

First workshop release, MIT licensed.

- Adds native Windows PowerShell scan, migration and audit scripts; Python remains preferred when available.
- Fixes partial-content duplicate hashing and course-code detection.
- Refuses overwrite races, reused bundle IDs, linked paths, overlapping bundles, metadata moves and over-deep folder contents.
- Persists undo plans before moving and logs intent/completion per item, preserving recovery after interruptions.
- Makes required structure failures fail the audit in both professional and student modes.
- Retains standard drawers in the student Class agent, plus course folders and the three Archive categories.
- Adds automated script tests, three synthetic workflow scenarios, packaging and cross-platform release CI.

Renaming remains optional. Exact duplicates are reported; an approved manifest must route extras to `00_Inbox/_duplicates/`. All migrations are moves, never copies; cross-filesystem moves are refused.

Verification scope: automated tests and generated fake-home workflow replays. The optional live Claude planning evaluation was attempted with user approval but returned HTTP 401 (expired OAuth token), including after reauthentication was reported. No live Claude planning evaluation passed. Claude Desktop/Cowork installation and real OneDrive sync behavior were not exercised. No participant files were scanned or migrated.
