"""Seeds both ways: `ark seed` queues only the names nothing dates, `ark seed-pool` ships the raw
hostnames and URLs held evidence names, and the work queue hands out what was queued."""

import csv
from pathlib import Path

import duckdb
from his_release import HIS_YEARS, stage, text

from ark import held
from ark import work_queue as wq
from ark.bulk import BulkRecord, SourceSpec
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.seed import seed_from_file
from ark.seed_pool import combine_parts, write_source_part

TASK = "cdx_verify"


def _store() -> duckdb.DuckDBPyConnection:
    conn = connect(":memory:")
    init_db(conn)
    return conn


def _seed(tmp_path: Path, conn: duckdb.DuckDBPyConnection, lines: str, **kw) -> tuple[dict, object]:
    queue = wq.connect_queue(":memory:")
    (tmp_path / "seeds.txt").write_text(lines, encoding="utf-8")
    return seed_from_file(conn, queue, tmp_path / "seeds.txt", **kw), queue


def test_seed_funnel(tmp_path: Path, his_files: Path) -> None:
    conn = _store()
    add_candidate(conn, "known.com", ensure_source(conn, "wayback_cdx", "timestamped"))
    lines = "fresh.org\nwww.fresh.org\nknown.com\n$garbage$\nother.net\n"
    stats, queue = _seed(tmp_path, conn, lines)
    assert (stats["lines"], stats["invalid"]) == (5, 1)
    # known.com is on file but unproven, so it is queued rather than dismissed
    assert (stats["already_candidate"], stats["already_confirmed_baseline"]) == (1, 0)
    # fresh.org and its www variant collapse into one new candidate
    assert (stats["new_candidates"], stats["enqueued"]) == (2, 3)
    assert wq.counts(queue, TASK) == {"pending": 3}
    # candidates are registered but unverified: no year rows
    assert conn.execute("SELECT count(*) FROM domain_year").fetchone()[0] == 0


def test_seed_skips_only_domains_with_a_confirmed_year(tmp_path: Path, his_files: Path) -> None:
    """ours.com is dated by our evidence; base.com only by his 1997 file, which alone settles it."""
    conn = _store()
    sid = ensure_source(conn, "wayback_cdx", "timestamped")
    add_candidate(conn, "ours.com", sid)
    evidence = record_evidence(conn, "ours.com", sid, 1997, "cdx_timestamp", "19970101000000")
    assign_year(conn, evidence)
    stage(his_files.parent, {"1997.txt": text(sorted(HIS_YEARS[1997] + ["base.com"]))})
    held.prepare(his_files)
    stats, _ = _seed(tmp_path, conn, "base.com\nours.com\nnew.com\n")
    # the two confirmed ones are counted apart, and neither is re-queued
    confirmed = (stats["already_confirmed_baseline"], stats["already_confirmed_own_evidence"])
    assert confirmed == (1, 1) and stats["already_candidate"] == 0
    assert (stats["new_candidates"], stats["enqueued"]) == (1, 1)


def test_his_www_form_confirms_no_bare_name(tmp_path: Path, his_files: Path) -> None:
    """His 1999 file holds www.rolled.com: the exact name rolled.com is not his, so it is queued."""
    stats, _ = _seed(tmp_path, _store(), "rolled.com\n")
    assert stats["already_confirmed_baseline"] == 0
    assert (stats["new_candidates"], stats["enqueued"]) == (1, 1)


def test_seed_limit(tmp_path: Path, his_files: Path) -> None:
    stats, _ = _seed(tmp_path, _store(), "a.com\nb.com\nc.com\n", limit=2)
    assert (stats["lines"], stats["new_candidates"]) == (2, 2)


def _pool(tmp_path: Path, key: str, *records: str | tuple[str, int], conn=None) -> tuple:
    """Write source `key`'s part from its records, a raw value or (raw, year), then combine."""
    pairs = [(r, 1998) if isinstance(r, str) else r for r in records]
    rows = [BulkRecord(raw=r, year=y, evidence_value=f"{y}0101000000") for r, y in pairs]
    spec = SourceSpec(key, key, "cdx_timestamp", "test", lambda _path, _stats: iter(rows))
    stats = write_source_part(spec, [tmp_path / "input"], parts_dir=tmp_path / "parts")
    return stats, combine_parts(conn, seed_dir=tmp_path / "seeds", parts_dir=tmp_path / "parts")


def test_a_raw_value_that_is_already_the_domain_is_not_a_seed(tmp_path: Path) -> None:
    # the annual files already carry it, so it adds nothing to a download list
    stats, result = _pool(tmp_path, "s", "example.com")
    assert (stats["no_extra_granularity"], stats["seeds"], result["seeds"]) == (1, 0, 0)


def test_a_subdomain_is_a_seed_carrying_its_registered_domain(tmp_path: Path) -> None:
    _, result = _pool(tmp_path, "s", "shop.example.com")
    (row,) = csv.DictReader((tmp_path / "seeds" / "download_seeds.csv").open())
    want = {"seed": "shop.example.com", "domain": "example.com", "year": "1998", "source": "s"}
    assert row == want and result["domains"] == 1


def test_out_of_window_years_never_reach_the_pool(tmp_path: Path) -> None:
    _, result = _pool(tmp_path, "s", ("a.ex.com", 1995), ("b.ex.com", 1999), ("c.ex.com", 2002))
    assert result["seeds"] == 1
    assert (tmp_path / "seeds" / "download_seeds.txt").read_text() == "b.ex.com\n"


def test_the_same_seed_in_two_years_is_two_rows_but_one_download(tmp_path: Path) -> None:
    # the table keeps each year it was seen; the list a crawler consumes holds the URL once
    _, result = _pool(tmp_path, "s", ("www.example.com", 1997), ("www.example.com", 2000))
    assert (result["rows"], result["seeds"]) == (2, 1)


def test_rerunning_one_source_replaces_only_its_own_rows(tmp_path: Path) -> None:
    _pool(tmp_path, "first", "a.ex.com")
    _pool(tmp_path, "second", "b.ex.org")
    _, result = _pool(tmp_path, "first", "c.ex.net")
    assert (tmp_path / "seeds" / "download_seeds.txt").read_text() == "b.ex.org\nc.ex.net\n"
    assert result["parts"] == 2


def test_a_url_containing_commas_survives_the_round_trip(tmp_path: Path) -> None:
    # a reader that sniffs quoting from the first rows still gets 4 columns: the seed is quoted
    url = "http://books.example.co.uk/news/0,6109,393333,00.html"
    _pool(tmp_path, "s", url)
    table = f"read_csv_auto('{tmp_path / 'seeds' / 'download_seeds.csv'}')"
    rows = duckdb.connect().execute(f"SELECT seed, domain FROM {table}").fetchall()
    assert rows == [(url, "example.co.uk")]


def test_an_empty_pool_reports_itself_rather_than_writing_files(tmp_path: Path) -> None:
    result = combine_parts(seed_dir=tmp_path / "s", parts_dir=tmp_path / "p")
    assert result == {"parts": 0, "seeds": 0}
    assert not (tmp_path / "s" / "download_seeds.txt").exists()


def test_it_counts_the_domains_his_files_lack(tmp_path: Path, his_files: Path) -> None:
    """By exact name: his 1999 file holds `www.rolled.com`, not `rolled.com`, so of four domains
    rolled.com and fresh.org are not his. A name ours could never be is left out of the count."""
    (tmp_path / "parts").mkdir()
    (tmp_path / "parts" / "odd.csv").write_text("seed,domain,year\nx.Odd.com,Odd.com,1998\n")
    records = ("www.already-his.com", "www.rolled.com", "shop.fresh.org")
    _, result = _pool(tmp_path, "s", *records, conn=duckdb.connect())
    assert (result["domains"], result["domains_not_in_his_files"]) == (4, 2)


def test_the_queue_hands_out_each_name_once_and_recovers_a_crash() -> None:
    queue = wq.connect_queue(":memory:")
    assert wq.enqueue(queue, TASK, ["a.com", "b.com"]) == 2
    assert wq.enqueue(queue, TASK, ["a.com", "c.com"]) == 1
    (done,) = wq.claim(queue, TASK, limit=1)
    assert wq.counts(queue, TASK) == {"pending": 2, "in_flight": 1}
    wq.mark_done(queue, TASK, done)
    # a finished key cannot be re-enqueued back to pending
    wq.enqueue(queue, TASK, [done])
    (failed,) = wq.claim(queue, TASK, limit=1)
    wq.mark_failed(queue, TASK, failed, http_status=404)
    # a failure without a retry time is final
    assert wq.counts(queue, TASK) == {"pending": 1, "done": 1, "failed": 1}
    # a crash leaves the last claim in flight: the reset returns it, its attempts kept
    wq.claim(queue, TASK)
    assert wq.reset_in_flight(queue) == 1
    (key,) = wq.claim(queue, TASK)
    row = "SELECT attempts FROM fetch_state WHERE task_type = ? AND key = ?"
    assert queue.execute(row, (TASK, key)).fetchone()["attempts"] == 2


def test_a_retry_after_failure_waits_for_its_retry_time() -> None:
    queue = wq.connect_queue(":memory:")
    wq.enqueue(queue, TASK, ["a.com"])
    (key,) = wq.claim(queue, TASK)
    wq.mark_failed(queue, TASK, key, http_status=429, retry_after_s=3600)
    # pending again, but not handed out until the hour has passed
    assert wq.counts(queue, TASK) == {"pending": 1}
    assert wq.claim(queue, TASK) == []
