# What the brief does not say

[The brief](ding/project-brief.md) is the specification; this page holds what his later messages make
true that it does not state.

- **D1 to D4** name the code and method deliverables section X of the brief requires in every
  submission: D1 the runnable code, configurations, dependencies and commands; D2 the experience
  summary; D3 the baseline merge and deduplication code and explanation, with overlap counts, the
  accepted increment and the reconciliation checks; D4 the Equivalent-English calculation code and
  explanation.
- **t counts whole days from the task assignment, 2 August 2026, one t for both parts**
  (`TASK_ASSIGNED_DATE`, `src/ark/figures.py`).

## Ledger

A message from him that changes the brief gets one row: the date on his message, what it says, the
category (scoring, evidence, format or method hint), what changed here, and where it landed. A cell
reads `pending` until the change has a home; `just state` copies every pending row into the session
brief, and `just brief` prints them while that snapshot is fresh.

| date | what it says | category | what changed here | landed in |
|---|---|---|---|---|
| 2026-10-09 | The primary period is 1996 to 2013, 2013 included; 1996 to 2001 stays first; 2014 on is kept apart at very low priority; 1996 to 2001 and 2002 to 2013 are scored apart, each with its own growth and S | scoring | the window is 1996 to 2013 and the gate on either part; each part reports its growth and S, never summed | AGENTS.md The window; `src/ark/baseline.py`, `src/ark/figures.py` `score_line`, `scripts/round/round_figures.py`, `docs/report.template.md` |
| 2026-10-09 | The next package carries a folder "Open Research Questions" answering the two questions of section IV.A of his specification: the proposed approaches, the work and tests done, and a preliminary validation of feasibility and applicability | format | every package carries the Open Research Questions folder | `docs/orq/orq.template.md`, `scripts/round/orq.py` |
| 2026-10-14 | The submission threshold is 3%, not 5%, the same EE growth after the merge and within-year dedup against the latest baseline | scoring | the gate is 3% on either part | `src/ark/baseline.py` `GATE_PCT`, AGENTS.md The window |
| 2026-10-16 | "Every complete submission must be supplied as exactly one 7z archive", `KnowledgeDiscoveryCompetition_Submission_{SubmissionTime}_{Name}.7z`, where "{SubmissionTime} denotes the timestamp when the complete submission is received"; "a separate folder named Open Research Questions. The folder must contain a Word document named Open Research Questions.docx"; "Earlier wording referring to another folder name or plain-text-only responses is superseded" | format | the package is one multithreaded 7z by that name; its one research-questions folder holds the .docx and the files it cites, and the plain-text folder is gone | `scripts/round/package_delivery.sh`, `scripts/round/orq.py`, `scripts/round/verify_delivery.sh`, `docs/round/delivery_readme.md` |
