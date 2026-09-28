"""Bulk loader: evidence routing per type, one row per subject, year and class, audit rows."""

import csv
import gzip
import json
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest
from his_release import HIS_YEARS, stage, text

from ark import held
from ark.bulk import BulkRecord, SourceSpec, ingest_files
from ark.checks import collect_checks
from ark.db import connect, init_db
from ark.evidence_types import qualifies_sql
from ark.sources import SOURCES, parse_early_web_cdx
from ark.work_queue import connect_queue


def _fresh_db() -> duckdb.DuckDBPyConnection:
    conn = connect(":memory:")
    init_db(conn)
    return conn


def _toy_parser(records: list[BulkRecord]):
    def parse(path: Path, stats: Counter) -> Iterator[BulkRecord]:
        stats["lines"] += len(records)
        yield from records

    return parse


def _spec(
    records: list[BulkRecord], evidence_type: str = "artifact_listing", method: str = "test"
) -> SourceSpec:
    return SourceSpec(
        key="toy",
        source_name="toy_source",
        evidence_type=evidence_type,
        acquisition_method=method,
        parse=_toy_parser(records),
    )


def _line_parse(path: Path, stats: Counter) -> Iterator[BulkRecord]:
    """Content-sensitive toy parser: one 1996 record per non-blank line."""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            stats["lines"] += 1
            yield BulkRecord(raw=line.strip(), year=1996, evidence_value=line.strip())


def _line_spec(evidence_type: str = "artifact_listing") -> SourceSpec:
    return SourceSpec(
        key="lines",
        source_name="line_source",
        evidence_type=evidence_type,
        acquisition_method="test",
        parse=_line_parse,
    )


def _touch(tmp_path: Path) -> Path:
    path = tmp_path / "toy.txt"
    path.write_text("unused, the toy parser ignores file contents\n", encoding="utf-8")
    return path


def test_master_type_creates_year_rows(tmp_path: Path) -> None:
    conn = _fresh_db()
    records = [
        BulkRecord(raw="http://www.example.com/", year=1997, evidence_value="artifact-1997"),
        BulkRecord(raw="other.org", year=1998, evidence_value="artifact-1998"),
    ]

    summary = ingest_files(conn, _spec(records), [_touch(tmp_path)], report_dir=tmp_path)

    assert summary["files_ingested"] == 1
    assert summary["evidence_rows"] == 2
    assert summary["year_rows"] == 2
    rows = conn.execute(
        "SELECT dy.domain, dy.assigned_year, e.evidence_type FROM domain_year dy "
        "JOIN evidence e ON dy.evidence_id = e.evidence_id ORDER BY dy.domain"
    ).fetchall()
    assert rows == [
        ("example.com", 1997, "artifact_listing"),
        ("other.org", 1998, "artifact_listing"),
    ]


def test_candidate_only_never_assigns_years(tmp_path: Path, his_files: Path) -> None:
    conn = _fresh_db()
    queue_conn = connect_queue(":memory:")
    records = [BulkRecord(raw="linked.com", year=1999, evidence_value="link-1999")]

    summary = ingest_files(
        conn, _spec(records, "link_target"), [_touch(tmp_path)], queue_conn, report_dir=tmp_path
    )

    # provenance is stored, but the candidate-only type must not reach masters
    assert conn.execute("SELECT count(*) FROM evidence").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM domain_year").fetchone()[0] == 0
    assert summary["enqueued"] == 1
    queued = queue_conn.execute("SELECT key, status FROM fetch_state").fetchall()
    assert [(row["key"], row["status"]) for row in queued] == [("linked.com", "pending")]
    # the source itself is registered as candidate_only
    kind = conn.execute("SELECT kind FROM source WHERE name = 'toy_source'").fetchone()[0]
    assert kind == "candidate_only"


def test_the_unassigned_queue_skips_a_name_his_files_hold(tmp_path: Path, his_files: Path) -> None:
    """His 1996 file holds once-his.org, mentioned here in 1999: any year of his settles it.
    His www.rolled.com settles no rolled.com, and a pair of ours settles ours.org."""
    stage(his_files.parent, {"1996.txt": text(sorted(HIS_YEARS[1996] + ["once-his.org"]))})
    held.prepare(his_files)
    conn = _fresh_db()
    queue_conn = connect_queue(":memory:")
    ingest_files(
        conn,
        _spec([BulkRecord(raw="ours.org", year=1998, evidence_value="listing-1998")]),
        [_touch(tmp_path)],
        report_dir=tmp_path,
    )
    records = [
        BulkRecord(raw=name, year=1999, evidence_value=f"link {name}")
        for name in ("once-his.org", "linked.com", "rolled.com", "ours.org")
    ]
    links = SourceSpec(
        key="links",
        source_name="links_source",
        evidence_type="link_target",
        acquisition_method="test",
        parse=_toy_parser(records),
    )

    summary = ingest_files(conn, links, [_touch(tmp_path)], queue_conn, report_dir=tmp_path)

    assert summary["enqueued"] == 2
    keys = queue_conn.execute("SELECT key FROM fetch_state ORDER BY key").fetchall()
    assert [row["key"] for row in keys] == ["linked.com", "rolled.com"]


def test_the_unassigned_queue_fails_closed_without_his_files(tmp_path: Path) -> None:
    """The evidence commits, then the queue refuses to guess: a re-run after `ark intake`
    queues it, as the recovery test shows."""
    conn = _fresh_db()
    queue_conn = connect_queue(":memory:")
    records = [BulkRecord(raw="linked.com", year=1999, evidence_value="link")]
    with pytest.raises(held.HeldError, match="run uv run ark intake"):
        ingest_files(
            conn, _spec(records, "link_target"), [_touch(tmp_path)], queue_conn, report_dir=tmp_path
        )
    assert conn.execute("SELECT count(*) FROM evidence").fetchone() == (1,)
    assert queue_conn.execute("SELECT count(*) FROM fetch_state").fetchone()[0] == 0


def test_ingest_is_idempotent_per_file(tmp_path: Path) -> None:
    conn = _fresh_db()
    records = [BulkRecord(raw="example.com", year=1996, evidence_value="a")]
    spec = _spec(records)
    path = _touch(tmp_path)

    first = ingest_files(conn, spec, [path], report_dir=tmp_path)
    second = ingest_files(conn, spec, [path], report_dir=tmp_path)

    assert first["files_ingested"] == 1
    assert second["files_skipped"] == 1
    assert "files_ingested" not in second
    assert conn.execute("SELECT count(*) FROM evidence").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM ingested_file").fetchone()[0] == 1


def test_earliest_capture_wins_within_file(tmp_path: Path) -> None:
    conn = _fresh_db()
    records = [
        BulkRecord(
            raw="example.com", year=1998, evidence_value="19981201000000", evidence_url="late"
        ),
        BulkRecord(
            raw="www.example.com", year=1998, evidence_value="19980301000000", evidence_url="early"
        ),
    ]

    ingest_files(conn, _spec(records, "cdx_timestamp"), [_touch(tmp_path)], report_dir=tmp_path)

    # method `test` is no web method, so neither row ships and the lowest value wins
    value, url = conn.execute("SELECT evidence_value, evidence_url FROM evidence").fetchone()
    assert value == "19980301000000"
    assert url == "early"


def test_a_capture_of_the_exact_domain_wins_over_a_lower_value(tmp_path: Path) -> None:
    """A host-less value and a `www.` capture both sort first, but only a capture of the
    domain itself ships, so the earliest of those is the row kept."""
    conn = _fresh_db()
    records = [
        BulkRecord(raw="x.com", year=2001, evidence_value="cdx capture 2001", evidence_url="a"),
        BulkRecord(
            raw="www.x.com",
            year=2001,
            evidence_value="cdx capture 20010101000000 www.x.com",
            evidence_url="b",
        ),
        BulkRecord(
            raw="x.com",
            year=2001,
            evidence_value="cdx capture 20010201000000 status 404 x.com",
            evidence_url="c",
        ),
        BulkRecord(
            raw="x.com",
            year=2001,
            evidence_value="cdx capture 20010401000000 x.com",
            evidence_url="d",
        ),
        BulkRecord(
            raw="x.com",
            year=2001,
            evidence_value="cdx capture 20010301000000 x.com",
            evidence_url="e",
        ),
    ]
    spec = _spec(records, "cdx_timestamp", method="ia_cdx_collapsed_query")

    ingest_files(conn, spec, [_touch(tmp_path)], report_dir=tmp_path)

    assert conn.execute("SELECT evidence_value, evidence_url FROM evidence").fetchall() == [
        ("cdx capture 20010301000000 x.com", "e")
    ]


def test_same_source_pair_not_duplicated_across_files(tmp_path: Path) -> None:
    conn = _fresh_db()
    records = [BulkRecord(raw="example.com", year=1996, evidence_value="x")]
    path_a = tmp_path / "a.txt"
    path_b = tmp_path / "b.txt"
    path_a.write_text("unused\n", encoding="utf-8")
    path_b.write_text("unused\n", encoding="utf-8")

    ingest_files(conn, _spec(records), [path_a], report_dir=tmp_path)
    ingest_files(conn, _spec(records), [path_b], report_dir=tmp_path)

    # second file carries the same (domain, year): no second evidence row
    assert conn.execute("SELECT count(*) FROM evidence").fetchone()[0] == 1


def test_re_ingesting_a_file_or_a_second_source_repeating_a_pair_adds_no_row(
    tmp_path: Path,
) -> None:
    """The ledger skips a file it knows by name; the store's own key catches the rest: the same
    bytes under another name, and another source repeating a name, year and class. Another class
    is another row."""
    conn = _fresh_db()
    first = tmp_path / "first.txt"
    first.write_text("example.com\nother.org\n", encoding="utf-8")
    copy = tmp_path / "copy.txt"
    copy.write_text(first.read_text(encoding="utf-8"), encoding="utf-8")
    assert ingest_files(conn, _line_spec(), [first], report_dir=tmp_path)["evidence_rows"] == 2

    again = ingest_files(conn, _line_spec(), [copy], report_dir=tmp_path)
    second = SourceSpec(
        key="second",
        source_name="second_source",
        evidence_type="artifact_listing",
        acquisition_method="test",
        parse=_line_parse,
    )
    repeated = ingest_files(conn, second, [first], report_dir=tmp_path)
    other_class = SourceSpec(
        key="dated",
        source_name="dated_source",
        evidence_type="dated_directory",
        acquisition_method="test",
        parse=_line_parse,
    )
    another = ingest_files(conn, other_class, [first], report_dir=tmp_path)

    assert [run["evidence_rows"] for run in (again, repeated, another)] == [0, 0, 2]
    assert conn.execute("SELECT count(*) FROM evidence").fetchone()[0] == 4
    assert conn.execute("SELECT count(*) FROM domain_year").fetchone()[0] == 2


def test_every_row_names_its_file_and_record(tmp_path: Path) -> None:
    """`record <n>` counts every record the parser yielded, dropped ones included, so the
    number finds the record in the file; a parser that knows its line says so instead."""
    conn = _fresh_db()
    records = [
        BulkRecord(raw="early.com", year=1995, evidence_value="a"),
        BulkRecord(raw="example.com", year=1997, evidence_value="b"),
        BulkRecord(raw="other.org", year=1998, evidence_value="c", location="line 40"),
    ]

    ingest_files(conn, _spec(records), [_touch(tmp_path)], report_dir=tmp_path)

    rows = conn.execute(
        "SELECT domain, source_file, record_location FROM evidence ORDER BY domain"
    ).fetchall()
    assert rows == [("example.com", "toy.txt", "record 2"), ("other.org", "toy.txt", "line 40")]


def test_a_capture_of_a_host_below_the_domain_dates_no_domain(tmp_path: Path) -> None:
    """The row is kept, about `sub.example.com`, and no year of example.com rests on it: a year
    of the registrable comes only from a row that names it."""
    conn = _fresh_db()
    stamp = "19990101000000"
    records = [
        BulkRecord(
            raw="sub.example.com",
            year=1999,
            evidence_value=stamp,
            evidence_url=f"https://web.archive.org/web/{stamp}/http://sub.example.com/",
        )
    ]

    summary = ingest_files(
        conn,
        _spec(records, "cdx_timestamp", "bulk_cdx_file"),
        [_touch(tmp_path)],
        report_dir=tmp_path,
    )

    assert (summary["evidence_rows"], summary["year_rows"]) == (1, 0)
    assert conn.execute("SELECT domain FROM evidence").fetchall() == [("example.com",)]
    assert conn.execute("SELECT count(*) FROM domain_year").fetchone()[0] == 0
    # and the gate agrees the row owes example.com no year
    results = {r["name"]: r for r in collect_checks(conn, tmp_path / "netnew")}
    assert results["nothing_earned_is_left_unassigned"]["ok"]


def test_an_exact_capture_joins_a_host_less_row_and_nothing_joins_an_exact_one(
    tmp_path: Path,
) -> None:
    """`cdx capture <year>` names no host and ships nothing, so a later journal's stamp for
    the same pair is admitted beside it, and the pair moves onto it. A capture of another host
    adds nothing, and once an exact row is held no second one joins."""
    conn = _fresh_db()
    journals = [
        [
            {"domain": "x.com", "status": 200, "years": [2001], "strategy": "suffix_sweep"},
            {"domain": "y.com", "status": 200, "years": [2001], "strategy": "suffix_sweep"},
        ],
        [
            {
                "domain": "x.com",
                "status": 200,
                "years": [2001],
                "stamps": {"2001": "20010301000000"},
            },
            {
                "domain": "y.com",
                "status": 200,
                "years": [2001],
                "hosts": {"www.y.com": "20010101000000"},
            },
        ],
        [{"domain": "x.com", "status": 200, "years": [2001], "stamps": {"2001": "20010101000000"}}],
    ]
    paths = []
    for index, records in enumerate(journals):
        path = tmp_path / f"cdx_suffix_{index}.jsonl"
        path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
        paths.append(path)

    summary = ingest_files(conn, SOURCES["cdx_snapshot"], paths, report_dir=tmp_path)

    assert (summary["evidence_rows"], summary["repointed"]) == (3, 1)
    rows = conn.execute(
        f"""
        SELECT e.domain, e.evidence_value, {qualifies_sql("e", "e.domain")},
               e.evidence_id = dy.evidence_id
        FROM evidence e JOIN domain_year dy ON dy.domain = e.domain
        ORDER BY e.domain, e.evidence_id
        """
    ).fetchall()
    assert rows == [
        ("x.com", "cdx capture 2001", False, False),
        ("x.com", "cdx capture 20010301000000 x.com", True, True),
        ("y.com", "cdx capture 2001", False, True),
    ]


def test_audit_csv_has_drops_and_corrections(tmp_path: Path) -> None:
    conn = _fresh_db()
    records = [
        BulkRecord(raw="http://www.example.com/page", year=1996, evidence_value="a"),
        BulkRecord(raw="$garbage$", year=1996, evidence_value="b"),
    ]

    summary = ingest_files(conn, _spec(records), [_touch(tmp_path)], report_dir=tmp_path)

    assert summary["rejected"] == 1
    assert summary["corrected"] == 1
    with (tmp_path / "toy_audit.csv").open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == ["original", "normalized", "reason", "result", "source_file", "year"]
    results = {row[0]: row[3] for row in rows[1:]}
    assert results["$garbage$"] == "dropped"
    assert results["http://www.example.com/page"] == "valid"


def test_run_metrics_written_per_file_and_per_run(tmp_path: Path) -> None:
    conn = _fresh_db()
    records = [BulkRecord(raw="example.com", year=1996, evidence_value="a")]

    ingest_files(conn, _spec(records), [_touch(tmp_path)], report_dir=tmp_path)

    sources = {
        row[0]
        for row in conn.execute(
            "SELECT source FROM run_metrics WHERE command = 'ingest'"
        ).fetchall()
    }
    assert sources == {"toy:toy.txt", "toy"}


def test_unknown_evidence_type_rejected() -> None:
    with pytest.raises(ValueError, match="unknown evidence type"):
        _spec([], evidence_type="not_a_type")


def test_ledger_hit_with_different_content_fails_loudly(tmp_path: Path) -> None:
    conn = _fresh_db()
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    (dir_a / "part.txt").write_text("first.com\n", encoding="utf-8")
    (dir_b / "part.txt").write_text("second.org\n", encoding="utf-8")

    ingest_files(conn, _line_spec(), [dir_a / "part.txt"], report_dir=tmp_path)
    summary = ingest_files(conn, _line_spec(), [dir_b / "part.txt"], report_dir=tmp_path)

    # same name, same source, different bytes: an error, never a silent skip
    assert summary["files_failed"] == 1
    domains = {row[0] for row in conn.execute("SELECT domain FROM domain").fetchall()}
    assert domains == {"first.com"}


def test_corrupt_file_does_not_abort_the_run(tmp_path: Path) -> None:
    conn = _fresh_db()
    good_line = "com,example)/ 19970601120000 http://example.com:80/ text/html 200 B - - 9 f.arc.gz"
    bad = tmp_path / "a_bad.cdx.gz"
    good = tmp_path / "b_good.cdx.gz"
    bad.write_bytes(gzip.compress(b"x" * 4096)[:20])
    good.write_bytes(gzip.compress((good_line + "\n").encode("utf-8")))
    spec = SourceSpec(
        key="toy_cdx",
        source_name="toy_cdx",
        evidence_type="cdx_timestamp",
        acquisition_method="test",
        parse=parse_early_web_cdx,
    )

    summary = ingest_files(conn, spec, [bad, good], report_dir=tmp_path)

    assert summary["files_failed"] == 1
    assert summary["files_ingested"] == 1
    ledgered = [row[0] for row in conn.execute("SELECT file_name FROM ingested_file").fetchall()]
    assert ledgered == ["b_good.cdx.gz"]
    # no audit rows from the failed file reach the CSV
    audit_text = (tmp_path / "toy_cdx_audit.csv").read_text(encoding="utf-8")
    assert "a_bad" not in audit_text


def test_multi_file_single_call_aggregates(tmp_path: Path) -> None:
    conn = _fresh_db()
    (tmp_path / "one.txt").write_text("a-site.com\n", encoding="utf-8")
    (tmp_path / "two.txt").write_text("b-site.org\n", encoding="utf-8")

    summary = ingest_files(
        conn, _line_spec(), [tmp_path / "two.txt", tmp_path / "one.txt"], report_dir=tmp_path
    )

    assert summary["files_ingested"] == 2
    assert summary["evidence_rows"] == 2
    assert summary["year_rows"] == 2
    # booleans never leak into the aggregated summary
    assert "skipped" not in summary


def test_audit_header_written_once_across_runs(tmp_path: Path) -> None:
    conn = _fresh_db()
    records = [BulkRecord(raw="http://www.example.com/x", year=1996, evidence_value="a")]
    path = _touch(tmp_path)

    ingest_files(conn, _spec(records), [path], report_dir=tmp_path)
    ingest_files(conn, _spec(records), [path], report_dir=tmp_path)

    with (tmp_path / "toy_audit.csv").open(encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert sum(1 for row in rows if row[0] == "original") == 1


def test_empty_file_still_gets_a_ledger_row(tmp_path: Path) -> None:
    conn = _fresh_db()
    summary = ingest_files(conn, _spec([]), [_touch(tmp_path)], report_dir=tmp_path)

    assert summary["files_ingested"] == 1
    name, rows = conn.execute("SELECT file_name, record_rows FROM ingested_file").fetchone()
    assert (name, rows) == ("toy.txt", 0)


def test_null_url_on_earliest_capture_stays_null(tmp_path: Path) -> None:
    conn = _fresh_db()
    records = [
        BulkRecord(raw="example.com", year=1998, evidence_value="19980101000000"),
        BulkRecord(
            raw="www.example.com", year=1998, evidence_value="19981201000000", evidence_url="late"
        ),
    ]

    ingest_files(conn, _spec(records, "cdx_timestamp"), [_touch(tmp_path)], report_dir=tmp_path)

    # value and url must come from the same staged row, even when url is NULL
    value, url = conn.execute("SELECT evidence_value, evidence_url FROM evidence").fetchone()
    assert value == "19980101000000"
    assert url is None


def test_out_of_window_record_is_counted_not_fatal(tmp_path: Path) -> None:
    conn = _fresh_db()
    records = [
        BulkRecord(raw="fine.com", year=1996, evidence_value="a"),
        BulkRecord(raw="early.com", year=1995, evidence_value="b"),
    ]

    summary = ingest_files(conn, _spec(records), [_touch(tmp_path)], report_dir=tmp_path)

    assert summary["files_ingested"] == 1
    assert summary["out_of_window"] == 1
    assert conn.execute("SELECT count(*) FROM evidence").fetchone()[0] == 1


def test_candidate_enqueue_recovers_after_queue_loss(tmp_path: Path, his_files: Path) -> None:
    conn = _fresh_db()
    queue_conn = connect_queue(":memory:")
    records = [BulkRecord(raw="linked.com", year=1999, evidence_value="link")]
    spec = _spec(records, "link_target")
    path = _touch(tmp_path)

    first = ingest_files(conn, spec, [path], queue_conn, report_dir=tmp_path)
    # simulate the crash window: queue rows lost after the file committed
    queue_conn.execute("DELETE FROM fetch_state")
    second = ingest_files(conn, spec, [path], queue_conn, report_dir=tmp_path)

    assert first["enqueued"] == 1
    assert second["files_skipped"] == 1
    # the re-run repairs the queue from durable evidence rows
    assert second["enqueued"] == 1
