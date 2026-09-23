"""A dated web link graph's target is annual evidence when it names the registrable itself."""

from collections import Counter
from pathlib import Path

from ark.bulk import ingest_files
from ark.checks import collect_checks
from ark.db import connect, init_db
from ark.evidence_types import MASTER_TYPES, WEB_METHODS
from ark.export import export_all
from ark.sources import SOURCES, parse_ukwa_link_target_bare

BRIEF = Path(__file__).resolve().parents[1] / "docs" / "brief" / "ding" / "project-brief.md"
HIS_SENTENCE = (
    "UK Web Archive host/link graph records may serve as direct annual evidence when their "
    "year association is explicit and documented."
)
XIII = "a dated web link-graph record that identifies the target hostname"


def test_his_sentence_is_in_the_brief_and_the_bare_target_class_is_annual() -> None:
    brief = BRIEF.read_text(encoding="utf-8")
    assert HIS_SENTENCE in brief and XIII in brief
    bare = SOURCES["ukwa_link_target_bare"]
    assert bare.evidence_type in MASTER_TYPES
    assert bare.acquisition_method in WEB_METHODS
    # the collapsed rows name no host, so they stay a candidate
    assert SOURCES["ukwa_link_target"].is_candidate_only


def test_only_a_bare_target_ships_and_the_stored_class_stays_a_candidate(tmp_path: Path) -> None:
    """A `www.` or deeper target dates that host, never the registrable beneath it, so the
    annual half keeps a target only when it IS its registrable, with the host in the value."""
    graph = tmp_path / "host-linkage.tsv"
    graph.write_text(
        "1999|www.source.co.uk|bare-ark-test.com\t3\n"
        "1999|www.source.co.uk|www.www-ark-test.com\t1\n"
        "2000|www.source.co.uk|deep.sub-ark-test.org\t1\n"
        "1997|www.source.co.uk|www.il\t1\n",
        encoding="utf-8",
    )
    stats: Counter = Counter()
    records = list(parse_ukwa_link_target_bare(graph, stats))
    assert [(r.raw, r.year, r.evidence_value) for r in records] == [
        ("bare-ark-test.com", 1999, "host_link_graph:1999 bare-ark-test.com")
    ]
    # a `www.` target, and a truncated one whose registrable is `www` itself
    assert stats["target_unparseable_or_www"] == 2
    assert stats["target_below_its_registrable"] == 1

    conn = connect(":memory:")
    init_db(conn)
    for key in ("ukwa_link_target", "ukwa_link_target_bare"):
        ingest_files(conn, SOURCES[key], [graph], report_dir=tmp_path / "reports")
    assert conn.execute("SELECT domain, assigned_year FROM domain_year").fetchall() == [
        ("bare-ark-test.com", 1999)
    ]

    baseline = tmp_path / "baseline"
    baseline.mkdir()
    for year in range(1996, 2002):
        (baseline / f"{year}.txt").write_text("already-his.com\n")
    (baseline / "candidate_pool.txt").write_text("already-his-candidate.com\n")
    netnew = tmp_path / "netnew"
    export_all(
        conn,
        netnew_dir=netnew,
        candidates_path=tmp_path / "candidates.txt",
        masters_dir=tmp_path / "masters",
        report_dir=tmp_path / "reports",
        provenance_dir=tmp_path / "provenance",
        baseline=baseline,
    )
    assert (netnew / "1999.txt").read_text().split() == ["bare-ark-test.com"]
    claim = (netnew / "candidate_additions.txt").read_text().split()
    assert {"sub-ark-test.org", "www-ark-test.com"} <= set(claim)
    assert "bare-ark-test.com" not in claim
    assert all(r["ok"] for r in collect_checks(conn, netnew))
