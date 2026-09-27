"""Held by him is the exact name in his files: `prepare` reads every line of his release once and
never writes it, and `minus` and `intersect` are set arithmetic that refuses unsorted input."""

import os
from pathlib import Path

import duckdb
import pytest
from his_release import (
    HIS_CANDIDATES,
    HIS_YEARS,
    MARKER,
    WEB_METHOD,
    all_names,
    capture,
    digests,
    stage,
    text,
)
from typer.testing import CliRunner

from ark import held
from ark.cli import app
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.evidence_types import HIS_SOURCE, HIS_TYPE
from ark.ingest import YEARS
from ark.provenance import SHIPPED

# CRLF, a blank line, padding, upper case, a duplicate, a quote, a tab, and one not a host at all
HOSTILE = b'B.com\r\na.com\na.com\n\n  d.com  \nWWW.E.COM \r\nf"quoted,x.com\n\tt.com\nnot a host\n'
HOSTILE_NAMES = ["\tt.com", "a.com", "b.com", "d.com", 'f"quoted,x.com', "not a host", "www.e.com"]


def read(path: Path) -> list[str]:
    return path.read_bytes().decode().splitlines()


def test_a_clean_release_is_held_in_place(tmp_path: Path) -> None:
    clean = {rel: text(sorted(n.lower() for n in names)) for rel, names in HIS_CANDIDATES.items()}
    folder = stage(tmp_path, clean)
    before = digests(folder)
    his = held.prepare(folder)
    assert digests(folder) == before
    assert sorted(p.name for p in his.dir.iterdir()) == [held.ALL, held.CANDIDATES, held.STAMP]
    assert all(his.year(year) == folder / f"{year}.txt" for year in YEARS)
    assert his.marker == MARKER


def test_a_hostile_file_gets_a_sorted_copy_and_his_stays_as_it_was(tmp_path: Path) -> None:
    folder = stage(tmp_path, {"1998.txt": HOSTILE})
    before = digests(folder)
    his = held.prepare(folder)
    assert digests(folder) == before
    assert his.year(1998) == his.dir / "1998.txt"
    assert read(his.year(1998)) == HOSTILE_NAMES
    assert his.counts["1998"] == len(HOSTILE_NAMES)


@pytest.mark.parametrize(
    "data",
    [b"a.com\rb.com\nc.com\n", b"a.com\x01junk\nb.com\n", b"\xef\xbb\xbfa.com\nb.com\n"],
    ids=["bare-cr", "delimiter", "bom"],
)
def test_a_file_comm_would_split_otherwise_gets_a_copy(tmp_path: Path, data: bytes) -> None:
    """Each of these passes `sort -c -u` and reads clean in DuckDB, yet `comm` would see other
    lines than `his_lines` does."""
    folder = stage(tmp_path, {"1999.txt": data})
    his = held.prepare(folder)
    assert his.year(1999) == his.dir / "1999.txt"
    names = duckdb.connect().execute(
        f"SELECT DISTINCT name FROM ({held.his_lines('?')}) WHERE coalesce(name, '') <> '' "
        "ORDER BY 1",
        [str(folder / "1999.txt")],
    )
    assert read(his.year(1999)) == [name for (name,) in names.fetchall()]


def test_all_is_the_union_of_his_six_years(tmp_path: Path) -> None:
    his = held.prepare(stage(tmp_path, {"1998.txt": HOSTILE}))
    expected = {n for y in YEARS if y != 1998 for n in HIS_YEARS[y]} | set(HOSTILE_NAMES)
    assert read(his.all) == sorted(expected)
    assert his.counts["all"] == len(expected)


def test_candidates_cover_every_candidate_file_and_never_the_readme(tmp_path: Path) -> None:
    his = held.prepare(stage(tmp_path))
    expected = {name.lower() for names in HIS_CANDIDATES.values() for name in names}
    assert read(his.candidates) == sorted(expected)
    assert [str(p.relative_to(his.baseline)) for p in his.candidate_files] == list(HIS_CANDIDATES)
    copies = {str(p.relative_to(his.dir)) for p in his.dir.rglob("*") if p.parent != his.dir}
    copies |= {p.name for p in his.dir.glob("candidate_pool*")}
    assert copies == {
        "candidate_pool.txt",
        "candidate_pool_unparsed_format.txt",
        "isc_survey_hostnames/2000-07.txt",
    }, "only the unsorted files are copied"


def test_minus_and_intersect_are_set_arithmetic(tmp_path: Path) -> None:
    his = held.prepare(stage(tmp_path))
    ours = tmp_path / "ours.txt"
    ours.write_bytes(text(sorted(["already-his.com", "early.his.org", "new.com", "zz.net"])))
    assert held.minus(ours, his.year(1996), tmp_path / "net.txt") == 2
    assert read(tmp_path / "net.txt") == ["new.com", "zz.net"]
    assert held.intersect(ours, his.all, tmp_path / "both.txt") == 2
    assert read(tmp_path / "both.txt") == ["already-his.com", "early.his.org"]


def test_his_www_name_does_not_hold_the_bare_name(tmp_path: Path) -> None:
    his = held.prepare(stage(tmp_path))
    ours = tmp_path / "ours.txt"
    ours.write_bytes(text(["rolled.com"]))
    assert held.intersect(ours, his.year(1999), tmp_path / "both.txt") == 0


def test_comm_never_sees_an_unsorted_file(tmp_path: Path) -> None:
    """macOS `comm` exits 0 on unsorted input, so the refusal cannot rest on its exit status."""
    good, bad = tmp_path / "good.txt", tmp_path / "bad.txt"
    good.write_bytes(text(["a.com", "b.com"]))
    bad.write_bytes(text(["b.com", "a.com"]))
    with pytest.raises(held.HeldError, match="not LC_ALL=C sorted"):
        held.minus(bad, good, tmp_path / "out.txt")
    with pytest.raises(held.HeldError, match="not LC_ALL=C sorted"):
        held.intersect(good, bad, tmp_path / "out.txt")
    dupe = tmp_path / "dupe.txt"
    dupe.write_bytes(text(["a.com", "a.com"]))
    with pytest.raises(held.HeldError):
        held.minus(dupe, good, tmp_path / "out.txt")
    assert not (tmp_path / "out.txt").exists()


def test_dump_refuses_what_is_not_our_sorted_lowercase_names(tmp_path: Path) -> None:
    conn = duckdb.connect()
    conn.execute("CREATE TABLE t AS SELECT * FROM (VALUES ('b.com'), ('a.com'), ('C.com')) v(n)")
    assert held.dump(conn, "SELECT n FROM t WHERE n <> 'C.com' ORDER BY n", tmp_path / "ok") == 2
    assert read(tmp_path / "ok") == ["a.com", "b.com"]
    with pytest.raises(held.HeldError, match="not a lowercase name"):
        held.dump(conn, "SELECT n FROM t ORDER BY n", tmp_path / "upper")
    with pytest.raises(held.HeldError, match="not LC_ALL=C sorted"):
        held.dump(conn, "SELECT n FROM t WHERE n <> 'C.com' ORDER BY n DESC", tmp_path / "desc")
    blank = tmp_path / "b"
    with pytest.raises(held.HeldError, match="not a lowercase name"):
        held.dump(conn, "SELECT NULL AS n UNION ALL SELECT 'a.com' ORDER BY 1 NULLS FIRST", blank)
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(("upper", "desc", "b"))]
    assert held.dump(conn, "SELECT n FROM t WHERE false", tmp_path / "empty") == 0


def test_load_refuses_a_release_it_has_not_prepared_or_that_moved(tmp_path: Path) -> None:
    folder = stage(tmp_path)
    with pytest.raises(held.HeldError, match="run uv run ark intake"):
        held.load(folder)
    held.prepare(folder)
    assert held.load(folder).counts == held.prepare(folder).counts
    year = folder / "2000.txt"
    st = year.stat()
    os.utime(year, ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))
    with pytest.raises(held.HeldError, match="run uv run ark intake"):
        held.load(folder)
    held.prepare(folder)
    (folder / "isc_survey_hostnames/2001-01.txt").write_bytes(text(["new.isc-held.net"]))
    with pytest.raises(held.HeldError, match="other files"):
        held.load(folder)


def test_prepare_keeps_only_the_current_release_and_no_stale_part(tmp_path: Path) -> None:
    old = held.HELD_ROOT / "merged260101"
    old.mkdir(parents=True)
    (old / held.STAMP).write_text("{}")
    kept = held.HELD_ROOT / "not-held-sets"
    kept.mkdir()
    (held.HELD_ROOT / MARKER).mkdir()
    (held.HELD_ROOT / MARKER / "all.txt.part").write_text("half")
    his = held.prepare(stage(tmp_path))
    assert not old.exists() and kept.exists()
    assert not list(his.dir.rglob("*.part"))


def test_prepare_never_prunes_its_own_folder_under_another_spelling(tmp_path: Path) -> None:
    folder = stage(tmp_path)
    held.prepare(folder)
    kept = held.HELD_ROOT / MARKER
    (held.HELD_ROOT / "other").mkdir()
    ((held.HELD_ROOT / "other") / held.STAMP).write_text("{}")
    alias = held.HELD_ROOT / "alias"
    alias.symlink_to(kept, target_is_directory=True)
    held.prepare(folder)
    assert kept.is_dir() and (kept / held.STAMP).is_file()
    assert not (held.HELD_ROOT / "other").exists()


def test_the_marker_is_the_folder_name_even_for_a_dot(tmp_path: Path, monkeypatch) -> None:
    folder = stage(tmp_path)
    monkeypatch.chdir(folder)
    assert held.prepare(Path(".")).marker == MARKER
    assert held.load(Path(".")).dir == held.HELD_ROOT / MARKER


def test_an_incomplete_release_is_refused(tmp_path: Path) -> None:
    folder = stage(tmp_path)
    (folder / "candidate_pool.txt").unlink()
    with pytest.raises(held.HeldError, match="candidate_pool.txt"):
        held.prepare(folder)
    with pytest.raises(held.HeldError, match="incomplete"):
        held.prepare(tmp_path / "nothing")


def test_ark_intake_writes_the_held_sets(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    folder = stage(tmp_path)
    result = CliRunner().invoke(app, ["intake", "--baseline", str(folder)])
    assert result.exit_code == 0, result.output
    assert read(held.load(folder).all) == sorted(all_names())


def test_our_domain_year_ships_no_pair_resting_on_his_rows() -> None:
    """A pair citing his row is re-pointed to our own row, or dropped when we have none."""
    conn = connect(":memory:")
    init_db(conn)
    his = ensure_source(conn, HIS_SOURCE, "timestamped")
    cdx = ensure_source(conn, "ia_cdx", "timestamped")
    for name in ("a.com", "b.com", "c.com"):
        add_candidate(conn, name, cdx)
    his_a = record_evidence(conn, "a.com", his, 1999, HIS_TYPE, "1999.txt", None, HIS_SOURCE)
    his_b = record_evidence(conn, "b.com", his, 1998, HIS_TYPE, "1998.txt", None, HIS_SOURCE)
    www = record_evidence(conn, "a.com", cdx, 1999, "cdx_timestamp", "cdx capture 1999 www.a.com")
    ours_a = record_evidence(conn, "a.com", cdx, 1999, "cdx_timestamp", "cdx capture 1999 a.com")
    ours_c = record_evidence(conn, "c.com", cdx, 2000, "cdx_timestamp", "cdx capture 2000 c.com")
    for eid in (his_a, his_b, ours_c):
        assign_year(conn, eid)
    held.our_domain_year(conn)
    rows = conn.execute(
        "SELECT domain, assigned_year, evidence_id FROM our_domain_year ORDER BY 1"
    ).fetchall()
    assert rows == [("a.com", 1999, ours_a), ("c.com", 2000, ours_c)]
    assert www < ours_a
    shipped = conn.execute(f"SELECT domain FROM ({SHIPPED['domain_year']}) ORDER BY 1").fetchall()
    assert shipped == [("a.com",), ("c.com",)]


# Asked of `attested` and `known_years`: ours.com is ours in 1998; his 1997 file holds his.com,
# which the store lacks; his row dates rolled.com (his 1999 file holds www.rolled.com) and
# old.com (from an older release of his); both.com cites his row and we hold a capture of it
# too; www-only.com cites his row and we hold only a capture of www.www-only.com; cand.org is
# a candidate of ours
ASKED = "ours.com his.com rolled.com old.com both.com www-only.com cand.org nobody.net".split()


def _his_row(conn, domain: str, year: int, marker: str = MARKER) -> int:
    his = ensure_source(conn, HIS_SOURCE, "timestamped")
    add_candidate(conn, domain, his)
    row = record_evidence(
        conn, domain, his, year, HIS_TYPE, f"{marker}/{year}.txt", None, HIS_SOURCE
    )
    assign_year(conn, row)
    return row


def _ours(conn, domain: str, year: int, host: str | None = None, assign: bool = True) -> int:
    cdx = ensure_source(conn, "ia_cdx", "timestamped")
    add_candidate(conn, domain, cdx)
    value = capture(host or domain, year)
    row = record_evidence(conn, domain, cdx, year, "cdx_timestamp", value, None, WEB_METHOD)
    if assign:
        assign_year(conn, row)
    return row


@pytest.fixture
def asked_store(his_files: Path) -> duckdb.DuckDBPyConnection:
    stage(his_files.parent, {"1997.txt": text(sorted(HIS_YEARS[1997] + ["his.com"]))})
    held.prepare(his_files)
    conn = connect(":memory:")
    init_db(conn)
    _ours(conn, "ours.com", 1998)
    _his_row(conn, "rolled.com", 1999)
    _his_row(conn, "old.com", 1997, "merged260817-2")
    _his_row(conn, "both.com", 1998)
    _ours(conn, "both.com", 1998, assign=False)
    _his_row(conn, "www-only.com", 1998)
    _ours(conn, "www-only.com", 1998, host="www.www-only.com", assign=False)
    add_candidate(conn, "cand.org", ensure_source(conn, "links", "candidate_only"))
    return conn


def test_attested_is_our_years_plus_his_exact_names(asked_store) -> None:
    """His www.rolled.com attests no rolled.com, and his row dates nothing on its own."""
    assert held.attested(asked_store, ASKED) == {"ours.com", "his.com", "both.com"}


def test_known_years_is_per_year(asked_store) -> None:
    assert held.known_years(asked_store, ASKED) == {
        ("ours.com", 1998),
        ("his.com", 1997),
        ("both.com", 1998),
    }


def test_attested_is_the_names_of_known_years(asked_store) -> None:
    """His all.txt is his six year files merged, so the two answers agree on every name."""
    names = ASKED + ["already-his.com", "early.his.org", "www.rolled.com"]
    known = held.known_years(asked_store, names)
    assert {name for name, _ in known} == held.attested(asked_store, names)
    assert {year for name, year in known if name == "already-his.com"} == set(YEARS)


def test_a_pair_citing_his_row_is_ours_only_by_a_row_of_ours_that_qualifies(
    asked_store, his_files: Path
) -> None:
    stage(his_files.parent, {"1997.txt": text(HIS_YEARS[1997])})
    held.prepare(his_files)
    assert held.attested(asked_store, ["both.com", "www-only.com"]) == {"both.com"}


def test_attested_does_not_change_when_his_rows_leave(asked_store) -> None:
    """Dropping his rows and keeping `our_domain_year` as `domain_year` changes no answer."""
    before = held.attested(asked_store, ASKED), held.known_years(asked_store, ASKED)
    asked_store.execute(f"CREATE TABLE dy2 AS {held.OUR_DOMAIN_YEAR_SQL}")
    asked_store.execute("DELETE FROM domain_year")
    asked_store.execute("INSERT INTO domain_year SELECT * FROM dy2")
    asked_store.execute(f"DELETE FROM evidence WHERE evidence_type = '{HIS_TYPE}'")
    assert asked_store.execute(
        f"SELECT count(*) FROM evidence WHERE evidence_type = '{HIS_TYPE}'"
    ).fetchone() == (0,)
    assert (held.attested(asked_store, ASKED), held.known_years(asked_store, ASKED)) == before


def test_the_pairs_asked_for_are_the_whole_table_on_those_names(asked_store) -> None:
    pairs = "SELECT domain, assigned_year, evidence_id FROM"
    held.our_domain_year(asked_store)
    whole = asked_store.execute(f"{pairs} our_domain_year").fetchall()
    asked = ["both.com", "old.com", "cand.org"]
    asked_store.execute("CREATE TEMP TABLE few AS SELECT unnest(?::VARCHAR[]) AS name", [asked])
    held.our_domain_year(asked_store, "few", "our_few")
    few = asked_store.execute(f"{pairs} our_few").fetchall()
    assert sorted(few) == sorted(row for row in whole if row[0] in asked)
    assert [row[0] for row in few] == ["both.com"]


def test_an_empty_ask_admits_nothing_and_needs_no_release() -> None:
    conn = connect(":memory:")
    init_db(conn)
    assert held.attested(conn, []) == set()
    assert held.known_years(conn, iter(())) == set()


def test_attested_fails_closed_without_his_files() -> None:
    conn = connect(":memory:")
    init_db(conn)
    with pytest.raises(held.HeldError, match="run uv run ark intake"):
        held.attested(conn, ["a.com"])
    with pytest.raises(held.HeldError, match="run uv run ark intake"):
        held.known_years(conn, ["a.com"])
