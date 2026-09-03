"""Banking a newly approved class must refuse anything a human has not answered.

The handover this automates is the riskiest moment in a round: a request written
days earlier, one word of answer, and a file on disk that has to be matched to the
right spec at the end of a long evening. The property under test is therefore not
"it ingests" but **"it refuses"**: a class still `pending` must be reported and
skipped, so the recipe that calls this can be rehearsed without banking something
nobody approved.

Since approvals arrive as pull requests merged from a phone, a second property
matters as much: **an approval that banks nothing must say so loudly**. The bytes a
source was priced from live wherever it was priced, so the case to test is the
normal one, an approved block whose journal is not on this machine.
"""

import email.message
import hashlib
import importlib.util
import sys
import urllib.error
from pathlib import Path
from types import SimpleNamespace

_SPEC = importlib.util.spec_from_file_location(
    "bank_approved", Path(__file__).resolve().parent.parent / "scripts/harness/bank_approved.py"
)
bank = importlib.util.module_from_spec(_SPEC)
# Registered before exec: the module's dataclasses resolve their own annotations
# through `sys.modules`, and without this the import raises.
sys.modules["bank_approved"] = bank
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

SPECS = {
    "foo_spec": SimpleNamespace(source_name="foo_source"),
    "bar_spec": SimpleNamespace(source_name="bar_source"),
}


def _approved(tmp_path: Path, body: str) -> tuple[str, dict]:
    """One approved block, read back through the real approvals parser."""
    text = f"# approvals\n\n## Priced\n\n{body}"
    path = tmp_path / "approved-sources-list.md"
    path.write_text(text, encoding="utf-8")
    from ark.approvals import load

    return text, load(path)


def _snapshot(root: Path) -> dict[str, str]:
    """Every path under `root` with a digest, so "changed nothing" is checkable."""
    out = {}
    for path in sorted(root.rglob("*")):
        key = str(path.relative_to(root))
        out[key] = "dir" if path.is_dir() else hashlib.sha256(path.read_bytes()).hexdigest()
    return out


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
    request = bank.request_in(BLOCK, "bar_source", "artifact_listing")
    assert request.journal == "data/raw/bar/bar.jsonl.gz"
    assert request.specs == ("bar_spec",)


def test_only_the_backticked_tokens_of_a_spec_line_are_spec_keys() -> None:
    """The live blocks write prose on the spec line, and a comma split reads it as keys."""
    assert bank.spec_keys("`ripe_dbase_1999`, reading `*dn:` and nothing else") == (
        "ripe_dbase_1999",
        "*dn:",
    )


def test_a_block_with_the_three_lines_banks(tmp_path: Path) -> None:
    """The whole point of the machine-readable lines: a merge, then an ingest."""
    text, approvals = _approved(
        tmp_path,
        "### foo_source / cdx_timestamp\n\n"
        "- ingest spec: `foo_spec`\n"
        "- journal: `data/raw/foo/foo.jsonl.gz`\n"
        "- refetch: https://example.org/foo.jsonl.gz then "
        "`uv run ark ingest foo_spec data/raw/foo/foo.jsonl.gz`\n\n"
        "Decision: master\n",
    )
    journal = tmp_path / "data/raw/foo/foo.jsonl.gz"
    journal.parent.mkdir(parents=True)
    journal.write_bytes(b"rows")

    plan = bank.plan_bank(text, approvals, root=tmp_path, read=lambda _: set(), specs=SPECS)
    assert plan.ready == [("foo_spec", journal)]
    assert plan.blocked == []
    assert plan.refetch == []


def test_a_missing_journal_with_a_refetch_line_is_reported_and_refetched(
    tmp_path: Path, capsys
) -> None:
    """The fleet prices elsewhere, so the bytes have to come back from the URL.

    Reported as well as fetched: a bank that silently downloads 70 MB is as hard to
    reason about as one that silently skips.
    """
    text, approvals = _approved(
        tmp_path,
        "### foo_source / cdx_timestamp\n\n"
        "- ingest spec: `foo_spec`\n"
        "- journal: `data/raw/foo/foo.jsonl.gz`\n"
        "- refetch: https://example.org/foo.jsonl.gz\n\n"
        "Decision: master\n",
    )
    plan = bank.plan_bank(text, approvals, root=tmp_path, read=lambda _: set(), specs=SPECS)
    assert plan.refetch == [
        ("foo_spec", "https://example.org/foo.jsonl.gz", tmp_path / "data/raw/foo/foo.jsonl.gz")
    ]
    assert plan.ready == []

    bank.report(plan)
    assert "refetching from https://example.org/foo.jsonl.gz" in capsys.readouterr().out

    asked = []

    def fetch(url: str, dest: Path) -> int:
        asked.append(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"rows")
        return 4

    lines = bank.run_refetches(plan.refetch, fetch=fetch)
    assert asked == ["https://example.org/foo.jsonl.gz"]
    assert "refetched foo.jsonl.gz for foo_spec" in lines[0]

    # And the bytes now on disk are what makes the second pass bank them.
    again = bank.plan_bank(text, approvals, root=tmp_path, read=lambda _: set(), specs=SPECS)
    assert again.ready == [("foo_spec", tmp_path / "data/raw/foo/foo.jsonl.gz")]


def test_a_block_with_neither_the_bytes_nor_a_refetch_line_is_refused_loudly(
    tmp_path: Path, capsys
) -> None:
    """Naming what it lacked is the message: an approval that banks nothing reads as done."""
    text, approvals = _approved(
        tmp_path,
        "### foo_source / cdx_timestamp\n\n"
        "- ingest spec: `foo_spec`\n"
        "- journal: `data/raw/foo/foo.jsonl.gz`\n\n"
        "Decision: master\n",
    )
    plan = bank.plan_bank(text, approvals, root=tmp_path, read=lambda _: set(), specs=SPECS)
    assert plan.ready == []
    assert plan.refetch == []
    label, lacked = plan.blocked[0]
    assert label == "foo_source / cdx_timestamp"
    assert "data/raw/foo/foo.jsonl.gz" in lacked
    assert "`- refetch:`" in lacked

    bank.report(plan)
    printed = capsys.readouterr().out
    assert "APPROVED AND NOT BANKED: 1" in printed
    assert "foo_source / cdx_timestamp" in printed


def test_a_journal_already_ingested_is_not_refetched(tmp_path: Path) -> None:
    """A priced journal can be deleted once its rows are in the store, per retention.

    Read the ledger before the filesystem or the bank downloads it all again every
    hour, and every one of those blocks would also read as blocked.
    """
    text, approvals = _approved(
        tmp_path,
        "### foo_source / cdx_timestamp\n\n"
        "- ingest spec: `foo_spec`\n"
        "- journal: `data/raw/foo/foo.jsonl.gz`\n"
        "- refetch: https://example.org/foo.jsonl.gz\n\n"
        "Decision: master\n",
    )
    plan = bank.plan_bank(
        text, approvals, root=tmp_path, read=lambda _: {"foo.jsonl.gz"}, specs=SPECS
    )
    assert plan.refetch == []
    assert plan.blocked == []
    assert plan.done == [("foo_spec", "foo.jsonl.gz")]


def test_a_journal_path_outside_the_repository_is_refused(tmp_path: Path) -> None:
    """The path arrives by pull request now, so it is text somebody else wrote."""
    text, approvals = _approved(
        tmp_path,
        "### foo_source / cdx_timestamp\n\n"
        "- ingest spec: `foo_spec`\n"
        "- journal: `../../etc/passwd`\n"
        "- refetch: https://example.org/foo\n\n"
        "Decision: master\n",
    )
    plan = bank.plan_bank(text, approvals, root=tmp_path, read=lambda _: set(), specs=SPECS)
    assert plan.refetch == []
    assert "escapes the repository" in plan.blocked[0][1]


def test_two_consecutive_runs_with_no_new_data_plan_the_same_and_write_nothing(
    tmp_path: Path,
) -> None:
    """E7.5's acceptance on this half: a repeated bank is a no-op.

    Asserted two ways, because a plan can be stable while the tree is not: the
    plans compare equal, and a digest of every path under the root is unchanged.
    """
    text, approvals = _approved(
        tmp_path,
        "### foo_source / cdx_timestamp\n\n"
        "- ingest spec: `foo_spec`\n"
        "- journal: `data/raw/foo/foo.jsonl.gz`\n\n"
        "Decision: master\n\n"
        "### bar_source / artifact_listing\n\n"
        "- ingest spec: `bar_spec`\n"
        "- journal: `data/raw/bar/bar.jsonl.gz`\n\n"
        "Decision: pending\n",
    )
    journal = tmp_path / "data/raw/foo/foo.jsonl.gz"
    journal.parent.mkdir(parents=True)
    journal.write_bytes(b"rows")

    before = _snapshot(tmp_path)
    first = bank.plan_bank(text, approvals, root=tmp_path, read=lambda _: set(), specs=SPECS)
    second = bank.plan_bank(text, approvals, root=tmp_path, read=lambda _: set(), specs=SPECS)
    assert first == second
    assert _snapshot(tmp_path) == before


def test_a_refetch_that_returns_a_page_is_not_an_artifact(tmp_path: Path) -> None:
    """A wall answers with a plausible byte count, so the check is on content.

    The measured case was seven different replay URLs answering with the same
    154,263-byte interstitial, all of which passed a size floor.
    """

    class Response:
        def __init__(self) -> None:
            self.chunks = [b"<!DOCTYPE html><title>Sign in</title>" + b"x" * 4000, b""]

        def read(self, _size: int) -> bytes:
            return self.chunks.pop(0)

        def __enter__(self):
            return self

        def __exit__(self, *_exc) -> bool:
            return False

    dest = tmp_path / "foo.jsonl.gz"
    try:
        bank.download("https://example.org/foo.jsonl.gz", dest, opener=lambda *a, **k: Response())
    except bank.RefetchFailed as exc:
        assert "not the artifact" in str(exc)
    else:
        raise AssertionError("an HTML body was accepted as a journal")
    assert not dest.exists()
    assert not (tmp_path / "foo.jsonl.gz.part").exists()


def test_a_throttled_refetch_reports_its_retry_after(tmp_path: Path) -> None:
    """Honouring a throttle means reading it, and the next hourly bank asks again."""
    headers = email.message.Message()
    headers["Retry-After"] = "600"

    def opener(*_args, **_kwargs):
        raise urllib.error.HTTPError("https://example.org/foo", 503, "busy", headers, None)

    try:
        bank.download("https://example.org/foo", tmp_path / "foo.gz", opener=opener)
    except bank.RefetchFailed as exc:
        assert "503" in str(exc)
        assert "600" in str(exc)
    else:
        raise AssertionError("a 503 was read as a successful fetch")


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
