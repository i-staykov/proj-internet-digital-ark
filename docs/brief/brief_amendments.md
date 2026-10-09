# What the brief does not say

[The brief](ding/project-brief.md) is the specification; this page holds what his later messages make
true that it does not state.

- **D1 to D4** name the code and method deliverables section X of the brief requires in every
  submission: D1 the runnable code, configurations, dependencies and commands; D2 the experience
  summary; D3 the baseline merge and deduplication code and explanation, with overlap counts, the
  accepted increment and the reconciliation checks; D4 the Equivalent-English calculation code and
  explanation.
- **t counts days from the task assignment, 2 August 2026, one t for both parts.** The brief counts
  whole calendar days from the assignment but gives no date; his own scores put it there: round 8 is
  10 x 18.769714 / 33 and round 9 is 10 x 3.682488 / 39 (`TASK_ASSIGNED_DATE` in `src/ark/figures.py`).

## Ledger

A message from him that changes the brief gets one row: the date on his message, his words, the
category (scoring, evidence, format or method hint), what changed here, and where it landed. A cell
reads `pending` until the change has a home; `just state` copies every pending row into the session
brief, and `just brief` prints them while that snapshot is fresh.

| date | his words | category | what changed here | landed in |
|---|---|---|---|---|
| 2026-10-09 | The primary period is 1996 to 2013, 2013 included; 1996 to 2001 stays first; 2014 on is kept apart at very low priority; 1996 to 2001 and 2002 to 2013 are scored apart, each with its own growth and S | scoring | the window is 1996 to 2013 and the gate 5% on either part; each part reports its growth and S, never summed | AGENTS.md The window; `src/ark/baseline.py`, `src/ark/figures.py` `score_line`, `scripts/round/round_figures.py`, `docs/report.template.md` |
| 2026-10-09 | The next package carries a folder "Open Research Questions" answering the two questions of section IV.A of his specification: the proposed approaches, the work and tests done, and a preliminary validation of feasibility and applicability | format | none yet | pending |
