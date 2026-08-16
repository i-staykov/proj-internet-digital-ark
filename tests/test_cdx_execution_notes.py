"""The campaign measurement must count every journal, however it was named.

This file exists because of one recurring failure: measuring the collectors that
were named the way somebody expected rather than the ones that actually ran. It
cost 31 hours once, when a yield check hardcoded two prefixes and the VPS wrote a
third for 3,219 answered queries and zero captures while every line read clean.

The same mistake came back in a smaller form. `scan` required a `_<UTC>` stamp in
the filename, so `cdx_discovered.jsonl.gz` was skipped in silence and the shipped
report understated the campaign by 298 queries. A journal with no stamp is still a
journal, and a source with no rows is the only thing that should count as nothing.
"""

import gzip
import importlib.util
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "cdx_execution_notes", _HERE / "scripts" / "cdx_execution_notes.py"
)
notes = importlib.util.module_from_spec(_SPEC)
# Registered before exec because the module defines a dataclass, and `@dataclass`
# resolves its own module out of `sys.modules` while the class body runs.
sys.modules["cdx_execution_notes"] = notes
_SPEC.loader.exec_module(notes)


def _journal(directory: Path, name: str, rows: list[dict]) -> None:
    path = directory / name
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


ANSWERED = {"domain": "example.com", "status": 200, "years": [1998]}


def test_an_unstamped_journal_is_still_counted(tmp_path: Path) -> None:
    """The exact shape that went missing: no `_<UTC>` in the name."""
    _journal(tmp_path, "cdx_discovered.jsonl.gz", [ANSWERED])
    tallies = notes.scan(tmp_path)
    assert sum(t.queries for t in tallies.values()) == 1


def test_it_lands_under_its_own_prefix_rather_than_someone_elses(tmp_path: Path) -> None:
    """A stamped and an unstamped journal must not be merged into one collector."""
    _journal(tmp_path, "cdx_pool_20260816T212501Z.jsonl.gz", [ANSWERED])
    _journal(tmp_path, "cdx_discovered.jsonl.gz", [ANSWERED])
    tallies = notes.scan(tmp_path)
    assert set(tallies) == {"cdx_pool", "cdx_discovered"}
    assert tallies["cdx_pool"].queries == 1
    assert tallies["cdx_discovered"].queries == 1


def test_an_unstamped_journal_contributes_no_span(tmp_path: Path) -> None:
    """It has no timestamp to offer, and inventing one would misreport the window."""
    _journal(tmp_path, "cdx_discovered.jsonl.gz", [ANSWERED])
    assert tallies_span(notes.scan(tmp_path)["cdx_discovered"]) == ("", "")


def tallies_span(tally) -> tuple[str, str]:
    return (tally.first_stamp or "", tally.last_stamp or "")


def test_a_partial_file_is_still_skipped(tmp_path: Path) -> None:
    """Relaxing the name rule must not start reading half-written batches."""
    _journal(tmp_path, "cdx_pool_20260816T212501Z.jsonl.gz.part", [ANSWERED])
    assert notes.scan(tmp_path) == {}
