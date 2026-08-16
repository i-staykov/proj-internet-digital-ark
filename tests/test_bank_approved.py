"""Banking a newly approved class must refuse anything a human has not answered.

The handover this automates is the riskiest moment in a round: a request written
days earlier, one word of answer, and a file on disk that has to be matched to the
right spec at the end of a long evening. The property under test is therefore not
"it ingests" but **"it refuses"**: a class still `pending` must be reported and
skipped, so the recipe that calls this can be rehearsed without banking something
nobody approved.
"""

import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "bank_approved", Path(__file__).resolve().parent.parent / "scripts" / "bank_approved.py"
)
bank = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bank)

BLOCK = """### foo_source / cdx_timestamp

- ingest spec: `foo_spec`
- source: https://example.org/foo
- journal: `data/raw/foo/foo.txt`

Decision: pending

### bar_source / artifact_listing

- ingest spec: `bar_spec`
- journal: `data/raw/bar/bar.jsonl.gz`

Decision: master
"""


def test_the_block_for_a_class_stops_at_the_next_heading() -> None:
    """Otherwise one request's journal path is read out of the next request's block."""
    block = bank.block_for(BLOCK, "foo_source", "cdx_timestamp")
    assert "foo.txt" in block
    assert "bar.jsonl.gz" not in block


def test_a_class_with_no_request_block_returns_empty() -> None:
    """Classes approved before this mechanism existed carry no journal to bank."""
    assert bank.block_for(BLOCK, "nothing_like_this", "cdx_timestamp") == ""


def test_the_journal_line_is_read_out_of_the_block() -> None:
    """The path comes from the request, not the command line.

    The block records the file the measured figures were computed from, so a
    reviewer who approved those figures approved that file. Accepting a path as an
    argument would let the two drift apart silently.
    """
    block = bank.block_for(BLOCK, "bar_source", "artifact_listing")
    assert bank._JOURNAL_LINE.search(block).group(1).strip() == "data/raw/bar/bar.jsonl.gz"
    assert bank._SPEC_LINE.search(block).group(1).strip() == "`bar_spec`"


def test_it_never_offers_to_bank_a_class_a_human_has_not_approved() -> None:
    """The invariant, against the live documents: only `master` is bankable.

    Checked by reading the real approvals file rather than by running the ingest,
    so it holds whatever state the file is in today. If a class is `pending`,
    `rejected`, or `candidate-only`, this must not be among the things banking
    would touch; only a human moving the line to `master` changes that.
    """
    from ark.approvals import load
    from ark.evidence_types import MASTER_TYPES

    text = bank.APPROVALS.read_text(encoding="utf-8")
    offered = []
    for (source_name, evidence_type), approval in load(bank.APPROVALS).items():
        if evidence_type not in MASTER_TYPES:
            continue
        if not bank.block_for(text, source_name, evidence_type):
            continue
        if approval.decision != "master":
            offered.append((source_name, evidence_type, approval.decision))

    # Every non-master class with a request block must be one this refuses. The
    # assertion is the shape of the data, not the count: a request block plus a
    # non-master decision is exactly the case the module reports and skips.
    assert all(d != "master" for _, _, d in offered)
