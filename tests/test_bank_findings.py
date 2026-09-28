"""The scribe's promises: a fleet figure never reaches the register alone, a slug gets one row
however many copies of it a drain, or a retried drain, holds, and a closed row is keyed on the
artifact it names."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "bank_findings", ROOT / "scripts/harness/bank_findings.py"
)
scribe = importlib.util.module_from_spec(_SPEC)
sys.modules["bank_findings"] = scribe
_SPEC.loader.exec_module(scribe)

PROSE = "# a-lead\nverdict: FIND\nee: 9,999\nartifact: https://example.invalid/list\n"
SIDECAR = {
    "slug": "a-lead",
    "run_id": "1741",
    "verdict": "FIND",
    "pricing": {"ee": 4786.0, "track": "annual"},
    "verify": {"status": "confirmed", "reason": "re-ran the command"},
}
PRICED = {"status": "priced", "ee": 4102.5}
JOURNAL = "0123456789abcdef" * 4


def lead(incoming: Path, name="a-lead", store=None, prose=True, **over) -> Path:
    """A drained lead directory: the sidecar, the prose unless not, and the store's re-price."""
    (path := incoming / name).mkdir(parents=True)
    if prose:
        (path / "finding.md").write_text(PROSE, encoding="utf-8")
    (path / "finding.json").write_text(json.dumps(SIDECAR | over), encoding="utf-8")
    if store is not None:
        (path / "store_price.json").write_text(json.dumps(store), encoding="utf-8")
    return path


def scout(incoming: Path, name: str, prose: str, status: str = "closed") -> None:
    """A lead the fleet filed with a scout's prose and no finding."""
    (path := incoming / name).mkdir(parents=True)
    (path / "scout.md").write_text(prose, encoding="utf-8")
    doc = {"status": status, "artifact": {"url": f"https://{name}.invalid/a"}}
    (path / "lead.json").write_text(json.dumps(doc), encoding="utf-8")


@pytest.mark.parametrize(
    ("store", "cell"),
    [
        (PRICED, "fleet 4,786.0 EE, store 4,102.5 EE"),
        ({"status": "no items shipped", "ee": None},
         "fleet 4,786.0 EE, store not re-priced: no items shipped"),
        (None, "fleet 4,786.0 EE, store not re-priced: no store price"),
    ],
    ids=["both-figures", "says-why-not-repriced", "no-store-price-at-all"],
)  # fmt: skip
def test_a_fleet_figure_never_reaches_the_register_alone(tmp_path, store, cell):
    """The sidecar's figure, never the prose's, with the store's beside it or why there is none."""
    lead(tmp_path / "incoming", store=store)
    (finding,) = scribe.findings_in(tmp_path / "incoming")
    row = scribe.register_row(finding, "wave-1")
    assert f"| {cell} (" in row and "9,999" not in row


def test_drains_leave_one_row_per_slug_and_a_retried_drain_writes_nothing(
    tmp_path, monkeypatch, capsys
):
    """A FIND re-measuring its own FIND row replaces it at the top, naming its read; a settled
    row and a closed slug stay. A leg artifact's `findings` copy of a lead, a negative copy of a
    FIND and a loose `<slug> / <class>` file are that slug; a negative naming an artifact a
    closed row names is that row's. A scout is booked closed whatever it says, once closed."""
    pages = tmp_path / "registers"
    pages.mkdir()
    old = [
        f"| {s} | d | n/a | n/a | n/a | n/a | 1 EE (d) | n/a | n/a | {v} | n/a |"
        for s, v in (("a-lead", "FIND (pending)"), ("kept", "BANKED"))
    ]
    (pages / "sources.md").write_text(f"{scribe.REGISTER_HEADER}\n|---|\n" + "\n".join(old))
    shut = "| shut / x | d | 0 EE | CLOSED. |  |\n"
    (pages / "sources-closed.md").write_text(f"# Closed\n\n{scribe.CLOSED_HEADING}\n|---|\n{shut}")
    incoming, named = tmp_path / "incoming", {"artifact": {"url": "https://neg.invalid/x"}}
    read = lead(incoming, store=PRICED)
    clauses = {"size": {"ok": True}, "robots": {"ok": False}}
    standing = {"admitted": False, "policy_version": 3, "clauses": clauses}
    (read / "lead.json").write_text(json.dumps({"status": "read", "standing": standing}))
    (read / "read.json").write_text(json.dumps({"receipt": {"journal_sha256": JOURNAL}}))
    lead(incoming, "findings", store=PRICED)
    for slug, verdict in (("kept", "FIND"), ("shut", "FIND"), ("new", "FIND")):
        lead(incoming, slug, prose=False, slug=slug, verdict=verdict)
    lead(incoming, "copy", prose=False, slug="new", verdict="CLOSED")
    for slug in ("neg", "neg-twin"):
        lead(incoming, slug, prose=False, slug=slug, verdict="CLOSED", **named)
    loose = "# neg / link_source\nverdict: CLOSED\nartifact: <https://loose.invalid/b>\n"
    (incoming / "neg.md").write_text(loose, encoding="utf-8")
    scout(incoming, "says-find", "verdict: FIND, 12,000 EE projected from one page\n")
    scout(incoming, "open", "verdict: FIND\n", status="scouted")
    hypotheses = tmp_path / "gone.md"
    argv = ["bank", str(incoming), "--hypotheses", str(hypotheses), "--registers", str(pages)]
    monkeypatch.setattr(sys, "argv", argv)
    for said in ("3 new rows, 1 replaced, 4 already booked", "0 new rows, 0 replaced, 8 already"):
        assert scribe.main() == 0
        assert f"scribe: {said}" in capsys.readouterr().out
    table = (pages / "sources.md").read_text("utf-8").split("|---|\n")[1]
    assert [scribe.first_cell(r) for r in table.splitlines()] == ["a-lead", "new", "kept"]
    assert table.endswith(old[1]) and scribe._cells(table.splitlines()[0])[9] == (
        "FIND (confirmed); whole read not admitted under standing policy 3: size held; "
        f"robots not held; journal sha256 {JOURNAL}"
    )
    closed = (pages / "sources-closed.md").read_text("utf-8").split("|---|\n")[1].splitlines()
    assert [scribe.closed_key(r) for r in closed] == ["neg", "says-find", "shut"]
    assert not hypotheses.exists(), "the hypothesis ledger is gone, and nothing recreates it"


NAMED = scribe.artifacts({
    "mirror": "| mirror / x | d | 0 EE | CLOSED. | <ftp://ftp.mirror.invalid/pub/netinfo/> |",
    "old": "| old / x | d | 0 EE | CLOSED. | ftp.gone.invalid |",
})  # fmt: skip


@pytest.mark.parametrize(
    ("fetched", "filed", "row"),
    [
        (None, {"host": "ftp.gone.invalid"}, "old"),
        (None, {"url": "https://ftp.gone.invalid/pub/", "host": "ftp.gone.invalid"}, None),
        (None, {"url": "ftp://ftp.mirror.invalid/pub/doc/rfc-index.txt"}, None),
        (None, {"url": "ftp://FTP.mirror.invalid/pub/netinfo"}, "mirror"),
        ("ftp://ftp.mirror.invalid/pub/netinfo/", {"url": "https://filed.invalid/x"}, "mirror"),
    ],
    ids=["no-url-keys-its-host", "a-url-beats-its-host", "one-host-many-artifacts",
         "host-case-and-slash-fold", "the-url-the-leg-fetched-beats-the-scouts"],
)  # fmt: skip
def test_a_closed_row_is_keyed_by_its_artifact_url_and_only_without_one_by_its_host(
    fetched, filed, row
):
    finding = {"fields": {}, "artifact": {"url": fetched}, "lead": {"artifact": filed}}
    assert scribe.named_by(finding, NAMED) == row


@pytest.mark.parametrize(
    ("verdict", "figure"),
    [
        ("CLOSED\n\n## next\n\n    dk-hostmaster domains.txt, 9,702 EE pending\n", "0"),
        ("CLOSED, about 3,000 EE projected, at 276.23 net-new EE measured, against a\n"
         "5,000 EE floor\n", "276.23"),
        ("CLOSED under a 4,000 EE ceiling, family ceiling ~1,000 EE, against the\n"
         "5,000 EE floor and the 2,500 EE candidate floor\n", "0"),
        ("CLOSED, 39.7 EE on one month\nee: 16.8469 candidate, 28 net-new pairs\n", "16.8469"),
    ],
    ids=["another-sources-figure", "measured-beats-projected", "bounds-only", "its-ee-line"],
)  # fmt: skip
def test_a_scout_negatives_figure_is_its_own_never_a_bound_or_another_sources(
    tmp_path, verdict, figure
):
    (path := tmp_path / "scout.md").write_text(f"verdict: {verdict}", encoding="utf-8")
    assert scribe.scout_figure(path) == figure


def test_a_closed_row_never_exceeds_the_register_line_limit():
    """The reason is trimmed after its verdict word, never the slug or the link."""
    lens = "candidate-bulk exit 3, robots refused, " + "a very long explanation " * 40
    url = "http://example.invalid/cdx?url=*.example.org/*&" + "fl=original&" * 30
    finding = {"slug": "a-lead", "verdict": "CLOSED", "ee": "0", "fields": {"artifact": url}}
    row = scribe.closed_row(finding | {"lead": {"lens": lens}}, "wave-1")
    assert len(row) <= scribe.ROW_LIMIT and row.startswith("| a-lead / unclassified |")
    assert row.endswith(f"| CLOSED. | <{url}> |")
