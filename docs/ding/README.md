# Professor Ding's own documents, transcribed

Everything in this directory is **his**, not ours. It is the task specification in his
words, and where anything in this repository disagrees with it, this directory wins.

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

    uv run python scripts/round/extract_ding_docs.py --package feedback-phase-6

The body of each is pandoc's conversion of his original, never retyped, and the header
carries the source file's sha256 so a reader can prove the transcription belongs to that
exact document. A paraphrase of the brief is the one document here that must not exist,
because it is the thing every later argument gets settled against.

**These are not the whole instruction set.** Three other surfaces carry things he has
said that are not in a `.docx`:

- `docs/SPEC.md` is the reviewer's original brief, cited by clause from across the repo.
- `docs/brief_amendments.md` is what he changed by email after a package was issued.
- `private/personal-context.md` holds his emails verbatim, and is git-ignored.

An email of his outranks a brief of his when the two disagree, because it is later. The
equivalent-English metric arrived that way.

## Provenance

Delivered as `Domain_Data_Collection_Task_0817_Update.zip` from
https://www.transfernow.net/dl/20260817w4qMbvxo on 2026-08-17, unpacked to
`feedback-phase-6/`. The original archive is kept at
`feedback-phase-6/original-archive/`.

The three files above are **byte-identical to the ones in the phase-5 package**: he
reissued the same brief with a new baseline rather than changing the instructions. What
changed for phase 6 is the corpus, `merged260817-2`, and the email that came with it.
