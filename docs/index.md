# Index of docs/

**One line per page: what it is and when to read it.** `lore/` holds the measured facts, `brief/` the
task in the reviewer's words, `registers/` the current-state ledgers, `round/` the inputs to one
delivery, `orq/` the open research questions package, `ops/` how to run it; the report and this page
sit at the root. Hard rules live in `AGENTS.md`. *Generated* pages name the script that writes them
(AGENTS.md, Frozen); *not shipped* pages are export-ignored and stay out of the delivery archive.

| Page | What it is | Read it when |
|---|---|---|
| [lore/laws.md](lore/laws.md) | Every measured fact in force, one line each with its figure and pointer | before pricing a source or trusting a number |
| [brief/ding/project-brief.md](brief/ding/project-brief.md) | His task brief, verbatim (*generated*: after each package, `uv run python scripts/round/extract_ding_docs.py --package <dir> --archive '<archive> (<delivery date>)' --stamp <date>`) | when checking a requirement or citing a clause |
| [brief/brief_amendments.md](brief/brief_amendments.md) | What his later messages make true that the brief does not say, the D1 to D4 names, and the ledger of changes | when a message from him changes the brief |
| [brief/metric-explained.md](brief/metric-explained.md) | The equivalent-English metric, explained and runnable (D4) | when a score needs defending |
| [registers/sources.md](registers/sources.md) | One row per source not closed, with what dates one item and its link; search it with `just find <term>` | before proposing, pricing or briefing anything |
| [registers/approved-sources-list.md](registers/approved-sources-list.md) | One `Decision:` line per (source, evidence type); `ark ingest` enforces it | before an ingest, and when writing a `Decision:` line |
| [registers/sources-closed.md](registers/sources-closed.md) | One row per source measured and closed, with the figure and the reason; `just find <term>` first | before proposing or briefing a lens |
| [registers/queue.md](registers/queue.md) | What only the owner can settle, the send and a new evidence class, at its measured figure (*generated* by `scripts/round/lead_queue.py`) | when the owner has a moment to rule |
| [registers/releases.md](registers/releases.md) | Every reviewer release: whether received, per-year line counts, sha256 (`just releases` fills it) | before deleting or trusting a release tree |
| [registers/retention.md](registers/retention.md) | One row per local data entry with its class, digest and refetch route (*generated* by `scripts/round/verify_raw.py`); a path with no row is not deletable | before deleting anything under `data/`, `output/` or `ding/` |
| [registers/rounds.md](registers/rounds.md) | Sent against credited per round, and the ranking score (`just rounds` writes a row; *not shipped*) | when a round's score or credit is quoted |
| [registers/questions.md](registers/questions.md) | Questions put to the reviewer; `just ship` copies the open rows into the mail (*not shipped*) | before drafting a round email |
| [ROUND.md](ROUND.md) | Where the round stands (*generated* by `scripts/round/build_round_state.py`, git-ignored) | whenever a figure about the round is needed |
| [report.template.md](report.template.md) | The round report with its stubs | when a five-figure source banks |
| [report.md](report.md) | The filled report (*generated* by `scripts/round/fill_report.py`) | to read what shipped |
| [report.docx](report.docx) | The Word rendering of the report (*generated* by `scripts/round/build_report_docx.py`) | before sending |
| [round/reproduction.txt](round/reproduction.txt) | The verification-run paragraph `fill_report.py` quotes into the report | when that paragraph is in question |
| [round/delivery_readme.md](round/delivery_readme.md) | The README at the archive root | before packaging |
| [round/experience-summary.md](round/experience-summary.md) | What worked, what did not, the limits (D2) | when writing up a round |
| [round/findings.md](round/findings.md) | The round's research findings and the measurement behind each | when writing up a round |
| [round/assets/](round/assets/) | `report-reference.docx`, the Word style reference | when the report styling changes |
| [orq/orq.template.md](orq/orq.template.md) | The two open research question answers with their tokens, filled by `scripts/round/orq.py` into both research-questions folders | when an answer to either open question changes |
| [ops/runbook.md](ops/runbook.md) | The commands and procedures of the loop as built, in the order a session runs them | before running anything |
| [ops/security-posture.md](ops/security-posture.md) | Threat model and incident handling for a public repository that parses dated mail corpora | when an AV alert fires or before a first request to a new host |
