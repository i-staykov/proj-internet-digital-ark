"""The hostname pricer runs the ingest's funnel and differences against our pairs and his files.

Written with the 26 `keep_until_priced` corpora in view: every one was priced at registrable
grain and never at hostname grain, and the only tool that could answer took the write lock.
"""

import gzip
import importlib.util
import json
from pathlib import Path

from his_release import HIS_YEARS, text

from ark import held
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence

_SPEC = importlib.util.spec_from_file_location(
    "price_hostnames",
    Path(__file__).resolve().parent.parent / "scripts/pricing/price_hostnames.py",
)
ph = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ph)


def _journal(path: Path, rows: list[tuple[str, str]]) -> Path:
    with gzip.open(path, "wt") as fh:
        for url, ts in rows:
            fh.write(json.dumps({"url": url, "timestamp": ts}) + "\n")
    return path


def _store():
    conn = connect(":memory:")
    init_db(conn)
    cdx = ensure_source(conn, "ia_cdx_hostnames", "timestamped")
    add_candidate(conn, "held.com", cdx)
    eid = record_evidence(conn, "held.com", cdx, 1999, "cdx_timestamp", "cdx capture x")
    assign_year(conn, eid)
    conn.execute(
        "INSERT INTO hostname_year (hostname, parent_domain, assigned_year, evidence_id) "
        "VALUES ('old.held.com', 'held.com', 1999, ?)",
        [eid],
    )
    return conn


def test_funnel_matches_the_ingest(tmp_path: Path, his_files: Path) -> None:
    journal = _journal(
        tmp_path / "x.jsonl.gz",
        [
            ("http://new.held.com/a", "19990301000000"),  # net-new hostname year
            ("http://new.held.com/b", "19990101000000"),  # same host-year, earlier stamp
            ("http://old.held.com/", "19990101000000"),  # already in the store
            ("http://www.held.com/", "19990101000000"),  # the parent's own site
            ("http://held.com/", "19990101000000"),  # a registrable row, not a hostname
            ("http://a.fresh.org/", "20010101000000"),  # parent not held
            ("http://fresh.org/", "20010601000000"),  # a registrable row, its pair net-new
            ("http://x.example.com/", "19950101000000"),  # out of window
            ("http://bad_host.example.com/", "19990101000000"),  # underscore, refused
        ],
    )
    seen, counts = ph.read_rows([journal], items=False, head=None)
    rows, pairs = ph.funnel(seen, counts)
    assert counts["out_of_window"] == 1 and counts["no_host"] == 1
    assert counts["registrable_row"] == 2 and counts["www_of_parent"] == 1
    assert rows == [
        ("a.fresh.org", "fresh.org", 2001),
        ("new.held.com", "held.com", 1999),
        ("old.held.com", "held.com", 1999),
    ]
    # the registrable half: only a row naming the registrable itself dates it, so
    # `www.held.com` and `a.fresh.org` date no registrable
    assert pairs == [("fresh.org", 2001), ("held.com", 1999)]

    # his 2001 file already lists it
    (his_files / "2001.txt").write_bytes(text(sorted([*HIS_YEARS[2001], "a.fresh.org"])))
    priced = ph.price(_store(), rows, pairs, held.prepare(his_files))
    assert priced["candidates"] == 3
    assert priced["registrable_candidates"] == 2
    assert priced["in_store"] == 1
    assert priced["in_baseline_only"] == 1
    assert priced["netnew_hostname_years"] == 1
    assert priced["netnew_by_year"] == {1999: 1}
    assert priced["netnew_ee"] > 0
    # fresh.org/2001 is a registrable-year the ingest would assign; held.com/1999 is held
    assert priced["parent_pairs_netnew"] == 1


def test_held_is_our_pair_or_his_exact_name(tmp_path: Path, his_files: Path) -> None:
    """His 1999 file lists `www.rolled.com`, which holds neither `rolled.com` nor its hosts:
    both are net-new. A name his file holds in any year makes its parent held."""
    conn = _store()
    journal = _journal(
        tmp_path / "z.jsonl.gz",
        [
            ("http://sub.rolled.com/", "19990101000000"),
            ("http://www.deep.his-host.net/", "20010101000000"),  # his file holds the bare name
            ("http://new.already-his.com/", "19990101000000"),
            ("http://rolled.com/", "19990101000000"),  # net-new: his `www.` is another name
            ("http://his-host.net/", "20010101000000"),  # net-new: his line is `deep.`
            ("http://already-his.com/", "19990101000000"),  # his file holds it
            ("http://held.com/", "19990101000000"),  # our pair
        ],
    )
    seen, counts = ph.read_rows([journal], items=False, head=None)
    rows, pairs = ph.funnel(seen, counts)
    priced = ph.price(conn, rows, pairs, held.load())
    assert sorted(priced["netnew_rows"]) == [
        ("new.already-his.com", 1999, False),
        ("sub.rolled.com", 1999, False),
        ("www.deep.his-host.net", 2001, True),
    ]
    assert priced["www_of_held_name"] == 1
    # already-his.com is his in every year; rolled.com and his-host.net are held by no one
    assert priced["parent_held_share"] == 1 / 3
    assert priced["registrable_candidates"] == 4
    assert priced["parent_pairs_netnew"] == 2


def test_items_mode_takes_a_year_and_several_hosts(tmp_path: Path) -> None:
    items = tmp_path / "items.jsonl"
    items.write_text(
        json.dumps({"item": "p1", "year": 2000, "text": "ftp.held.com mail.held.com"})
        + "\n"
        + json.dumps({"item": "p2", "date": "12 Mar 1994", "text": "gone.held.com"})
        + "\n"
    )
    seen, counts = ph.read_rows([items], items=True, head=None)
    assert counts["undated_or_out_of_window"] == 1
    assert sorted(seen) == [("ftp.held.com", 2000), ("mail.held.com", 2000)]


def test_head_cuts_each_file(tmp_path: Path) -> None:
    journal = _journal(
        tmp_path / "y.jsonl.gz", [(f"http://h{i}.held.com/", "19990101000000") for i in range(10)]
    )
    seen, counts = ph.read_rows([journal], items=False, head=3)
    assert counts["lines"] == 3 and counts["head_cut_files"] == 1


def test_an_error_capture_dates_no_hostname_year(tmp_path: Path) -> None:
    """A fleet read keeps its 4xx and 5xx rows for the candidate track; the store price of
    its annual half counts only captures that answered."""
    journal = tmp_path / "fleetread_bulk_cdx_file__x_0001.jsonl.gz"
    with gzip.open(journal, "wt") as fh:
        for url, ts, status in (
            ("http://ok.fresh.org/", "19990101000000", "200"),
            ("http://moved.fresh.org/", "19990101000000", "301"),
            ("http://gone.fresh.org/", "19990101000000", "404"),
            ("http://down.fresh.org/", "19990101000000", "503"),
        ):
            fh.write(json.dumps({"url": url, "timestamp": ts, "status": status}) + "\n")
    seen, counts = ph.read_rows([journal], items=False, head=None)
    assert counts["error_status"] == 2
    assert sorted(host for host, _ in seen) == ["moved.fresh.org", "ok.fresh.org"]
