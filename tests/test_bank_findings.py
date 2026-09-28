"""The scribe's two promises: a fleet figure never reaches the register alone, and a slug gets
one row however many copies of it a drain, or a retried drain, holds."""

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


def lead(incoming: Path, name: str = "a-lead", store: dict | None = None, **over) -> None:
    """A drained lead directory: the prose, the sidecar and, unless None, the store's re-price."""
    (path := incoming / name).mkdir(parents=True)
    (path / "finding.md").write_text(PROSE, encoding="utf-8")
    (path / "finding.json").write_text(json.dumps(SIDECAR | over), encoding="utf-8")
    if store is not None:
        (path / "store_price.json").write_text(json.dumps(store), encoding="utf-8")


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
    """A FIND re-measuring its own FIND row replaces it at the top; a settled row and a closed
    slug stay. A leg artifact's `findings` copy of a lead, and a negative copy of a FIND, are
    the same slug; a negative naming an artifact a closed row names is booked under that row."""
    pages = tmp_path / "registers"
    pages.mkdir()
    old = [
        f"| {s} | d | n/a | n/a | n/a | n/a | 1 EE (d) | n/a | n/a | {v} | n/a |"
        for s, v in (("a-lead", "FIND (pending)"), ("kept", "BANKED"))
    ]
    (pages / "sources.md").write_text(f"{scribe.REGISTER_HEADER}\n|---|\n" + "\n".join(old))
    shut = "| shut / x | d | 0 EE | CLOSED. |  |\n"
    (pages / "sources-closed.md").write_text(f"# Closed\n\n{scribe.CLOSED_HEADING}\n|---|\n{shut}")
    incoming = tmp_path / "incoming"
    lead(incoming, store=PRICED)
    lead(incoming, "findings", store=PRICED)
    for slug, verdict in (("kept", "FIND"), ("shut", "FIND"), ("new", "FIND"), ("neg", "CLOSED")):
        lead(incoming, slug, slug=slug, verdict=verdict)
    lead(incoming, "copy", slug="new", verdict="CLOSED")
    lead(incoming, "neg-twin", slug="neg-twin", verdict="CLOSED")  # neg's artifact, so neg's row
    hypotheses = tmp_path / "gone.md"
    argv = ["bank", str(incoming), "--hypotheses", str(hypotheses), "--registers", str(pages)]
    monkeypatch.setattr(sys, "argv", argv)
    for said in ("2 new rows, 1 replaced, 3 already booked", "0 new rows, 0 replaced, 6 already"):
        assert scribe.main() == 0
        assert f"scribe: {said}" in capsys.readouterr().out
    table = (pages / "sources.md").read_text("utf-8").split("|---|\n")[1]
    assert table.startswith("| a-lead |") and table.count("| a-lead |") == 1
    assert table.count("| new |") == 1 and table.endswith(old[1])
    closed = (pages / "sources-closed.md").read_text("utf-8")
    assert (
        "| neg / unclassified |" in closed and "| new / " not in closed and "neg-twin" not in closed
    )
    assert not hypotheses.exists(), "the hypothesis ledger is gone, and nothing recreates it"
