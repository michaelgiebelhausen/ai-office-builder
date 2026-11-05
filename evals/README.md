# Scenario evaluation

`scenarios.json` contains scripted interview answers for a professional with two
clients, a student with five courses and a side hustle, and a resumed migration.
`tests/test_evals.py` creates a fresh messy fake home for each scenario, builds the
agreed floor plan, inventories the mess, dry-runs approved bundles, moves code and
documents, and asserts a passing final audit and preserved contents. The resumed
case also verifies existing log entries and undo files remain unchanged.

Run `python -m pytest tests/test_evals.py -v`. On Windows every scenario runs with
both Python and native PowerShell. Nothing points at a participant's actual home.

These deterministic replays verify the workflow scripts and layout. They do not
prove that Claude independently interviews, routes ambiguous files or obtains
approval correctly. A separate tool-free Claude planning evaluation can assess
those decisions using the same answers and synthetic inventory; record its
results separately. A full Claude Desktop/Cowork installation smoke test remains
distinct from either kind of evaluation.
