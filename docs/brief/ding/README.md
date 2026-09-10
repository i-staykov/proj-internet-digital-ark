# Professor Ding's own documents, transcribed

The three transcriptions below are **his documents**, not our summaries.
[project-brief.md](project-brief.md) is the canonical packaged task specification.
It outranks repository guidance; a later message from him overrides it where they disagree.

| file | what it is |
|---|---|
| [project-brief.md](project-brief.md) | the task brief: objectives, the equivalent-English standard, the evidence rules (section IV), the priority workstreams, the delivery format |
| [update-log.md](update-log.md) | his log of what each brief revision changed and why |
| [task-package-file-guide.md](task-package-file-guide.md) | what each file in the delivered task package is |

## How to use these, and how not to

**Read `project-brief.md` section IV before proposing any source.** Those eleven rules are
the ones the whole evidence model in this repository implements, and they are the reason
`domain_year.evidence_id` is `NOT NULL`.

**Do not edit these files.** They are generated:

    uv run python scripts/round/extract_ding_docs.py --package <document-directory> \
        --archive '<archive or URL> (<delivery date>)' --stamp <transcription-date>

Pass the directory containing all three originals, not the enclosing release directory.
The package and provenance arguments are required; all inputs are converted before any
transcription is replaced. The header records each original's sha256. Pandoc converts the
body; only escaped backticks and curly quotation marks are normalised. Wording, order and
section numbering stay his, including the two sections numbered VIII.

**Later messages still matter.** Two other surfaces retain his clarifications:

- [brief_amendments.md](../brief_amendments.md) records dated changes and email clarifications.
- `private/personal-context.md` holds his emails verbatim, and is git-ignored.

Historical entries describe the instructions in force on their dates, not a competing
current specification. Cite the current brief by section and title; qualify older citations
with the brief's date rather than silently changing what an old decision relied on.

## Provenance

Each generated header names the source file, source hash, delivery and transcription date.
The originals remain under `feedback/`; archive identities are recorded in
[releases.md](../../registers/releases.md). Refresh all three transcriptions after a new
task package arrives. Baseline intake does not run this step automatically.

## Original brief

The [2026-07-21 brief](https://github.com/i-staykov/proj-internet-digital-ark/blob/e398e2064e4b5a286fceed122e30ec0a9b3e45b4/docs/SPEC.md)
is retained in Git history, not as a second live specification. Frozen submissions and
historical approval citations keep that version's numbering. Its registered-domain-only
rule was superseded by the current brief's IV.8, which retains qualifying exact hostnames.
