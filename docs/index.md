# Index of docs/

**One line per page: what it is and when to read it.** `docs/` is a tree since 2026-09-06, five
directories by what a page IS rather than what it is about: `lore/` standing knowledge we wrote,
`brief/` the task as the reviewer stated it, `registers/` the append-only ledgers, `round/` the
inputs to one delivery, `ops/` how to run the thing. The report cluster and this page stay at the
root because they are the entry points. It was flat until then, on the argument that code pins
`docs/<file>` paths; that was true and 33 of 35 pages had to be repointed, which is exactly why the
flat version had stopped being navigable.

A page marked *generated* is written by the named script and never edited by hand; a page marked
*frozen* is never edited at all. Pages marked *not shipped* are export-ignored and stay out of
the delivery archive.

## Rules and lore

| Page | What it is | Read it when |
|---|---|---|
| [rules.md](lore/rules.md) | The standing rules, one line each, by family | before any ingest, commit or delivery step |
| [laws.md](lore/laws.md) | The measured laws of source pricing, with every figure | before pricing or proposing a source |
| [traps.md](lore/traps.md) | Mistakes already paid for, one paragraph each | before trusting a number or sending a first request |
| [discovery.md](lore/discovery.md) | How to find and price a new source, the long form | when a lens is new to you |
| [retired.md](lore/retired.md) | Capabilities deleted from the tree, one line each with the commit that removed them | before rebuilding something that was retired on purpose |
| [key-decisions.md](lore/key-decisions.md) | Open and closed asks to Ivo, two lines each (*not shipped*) | when something needs a human decision |
| [ADRs.md](lore/ADRs.md) | Architecture decision records, structural changes only | before changing the schema, the gate or the evidence classes |
| [documentation.md](lore/documentation.md) | Why the code is shaped the way it is | before a refactor |

## The task, in Ding's words

| Page | What it is | Read it when |
|---|---|---|
| [SPEC.md](SPEC.md) | The original task brief of 2026-07-21, verbatim (*frozen*) | when a clause is cited by roman numeral |
| [brief_amendments.md](brief/brief_amendments.md) | The brief as amended, one dated row per change | when the brief and current practice disagree |
| [ding/README.md](brief/ding/README.md) | What the transcribed documents are and how they win over ours | once |
| [ding/project-brief.md](brief/ding/project-brief.md) | His task brief (*generated* by `scripts/round/extract_ding_docs.py`) | when checking what he actually asked for |
| [ding/task-package-file-guide.md](brief/ding/task-package-file-guide.md) | His file guide for the delivery package (*generated*, same script) | before packaging |
| [ding/update-log.md](brief/ding/update-log.md) | His dated log of brief changes (*generated*, same script) | when dating an amendment |
| [metric-explained.md](brief/metric-explained.md) | The equivalent-English metric, explained and runnable (D4 of the standard) | when a score needs defending |

## Registers

| Page | What it is | Read it when |
|---|---|---|
| [sources.md](registers/sources.md) | Every source tried, admitted or closed, with what dates one item and its link; grep it, never read it whole | before proposing, pricing or briefing anything |
| [approved-sources-list.md](registers/approved-sources-list.md) | One `Decision:` line per (source, evidence type); `ark ingest` enforces it | before an ingest, and when writing a `Decision:` line |
| [sources-closed.md](registers/sources-closed.md) | One row per source measured and closed, with the date, the figure and the reason; grep it before proposing | before proposing or briefing a lens |
| [hypotheses-pending.md](registers/hypotheses-pending.md) | The open triage entries, verbatim, still `pending` until a `Decision:` line lands | when picking a hypothesis or writing a `Decision:` line |
| [hypotheses.tsv](registers/hypotheses.tsv) | The hypothesis ledger (*generated*: appended by `scripts/harness/hypothesis_ledger.py`) | when opening or closing a hypothesis |
| [releases.md](registers/releases.md) | Every reviewer release: date, whether received, per-year line counts, sha256 of his zip or of our zstd copy (`just releases` fills it) | before deleting or trusting a release tree |
| [retention.md](registers/retention.md) | One row per local data entry with its class, checksum digest and refetch route (*generated* by `scripts/round/verify_raw.py`); a path with no row is not deletable | before deleting anything under `data/`, `output/` or `feedback/` |
| [rounds.md](registers/rounds.md) | Sent against credited figures per round, and the ranking score from the two mail stamps (*not shipped*) | when a round's score or credit is quoted |
| [questions.md](registers/questions.md) | Questions put to the reviewer, with his answers as they come; `just ship` copies the open rows (*not shipped*) | before drafting a round email |

## Round output

| Page | What it is | Read it when |
|---|---|---|
| [ROUND.md](ROUND.md) | Where the round stands right now (*generated* by `scripts/round/build_round_state.py`, git-ignored) | whenever a figure about the round is needed |
| [report.template.md](report.template.md) | The round report with its stubs; findings are drafted here as they land | when a five-figure source banks |
| [report.md](report.md) | The filled report (*generated* by `scripts/round/fill_report.py`; *frozen*) | to read what shipped, never to edit |
| [report.docx](report.docx) | The Word rendering of the report (*generated* by `scripts/round/build_report_docx.py`) | before sending |
| [report-sendable.md](report-sendable.md) | The report's prose as sent (*generated*, same script; *not shipped*) | when checking what he received |
| [email-sections.md](round/email-sections.md) | The round email prose, one block per heading, read by `fill_report.py` (*not shipped*) | when drafting the round email |
| [reproduction.txt](round/reproduction.txt) | The paragraph on the verification run, quoted into the report by `fill_report.py` | when the report's reproduction paragraph is in question |
| [delivery_readme.md](round/delivery_readme.md) | The README that ships at the archive root | before packaging |
| [experience-summary.md](round/experience-summary.md) | What worked, what did not, the limits (D2 of the standard) | when writing up a round |
| [assets/](round/assets/) | `report-reference.docx`, the Word style reference for the report | never, unless the report styling changes |

## Operations

| Page | What it is | Read it when |
|---|---|---|
| [how-the-work-runs.md](ops/how-the-work-runs.md) | Who does what, where each artifact lands, and what only Ivo can do | when the shape of the process is unclear |
| [brief-compliance.md](brief/brief-compliance.md) | Every bullet of his newest numbered brief section against the file that satisfies it | when an update from him lands |
| [runbook.md](ops/runbook.md) | What to run and what each command should print | when running anything for the first time |
| [security-posture.md](ops/security-posture.md) | Threat model and incident handling for a public repository that parses dated mail corpora | when an AV alert fires or before a first request to a new host |
