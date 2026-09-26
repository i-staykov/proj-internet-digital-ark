"""Held by him is the exact name in his files: `prepare` reads every line of his release once and
never writes it, and `minus` and `intersect` are set arithmetic that refuses unsorted input."""

import os
from pathlib import Path

import duckdb
import pytest
from his_release import HIS_CANDIDATES, HIS_YEARS, MARKER, all_names, digests, stage, text
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
    assert not [*tmp_path.glob("upper*"), *tmp_path.glob("desc*")]
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
