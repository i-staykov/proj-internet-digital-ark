"""His release is read whole: every line of every year is accounted for, per year, against the
file on disk. His files are his truth, so a line lost to parsing is a record of his we would
re-offer him, or drop from what we ship back."""

import subprocess
from pathlib import Path

import duckdb
import pytest

from ark.baseline import baseline_dir
from ark.canonical import to_registrable
from ark.db import connect, init_db
from ark.export import his_lines, load_his_annual_files
from ark.ingest import YEARS, ingest_year_file

# CRLF, a blank line, padding, upper case, a line with a quote, one that is not a host at all
HOSTILE = b'a.com\r\nWWW.B.COM \r\n  c.co.uk\n\nd"quoted.com\nnot a host\n'


def _hostile_release(tmp_path: Path) -> Path:
    release = tmp_path / "release"
    release.mkdir()
    for year in YEARS:
        (release / f"{year}.txt").write_bytes(HOSTILE)
    return release


def test_the_export_reads_every_nonblank_line_of_every_year(tmp_path: Path) -> None:
    conn = duckdb.connect()
    load_his_annual_files(conn, _hostile_release(tmp_path))
    for year in YEARS:
        names = [
            n
            for (n,) in conn.execute(
                "SELECT name FROM his_annual WHERE year = ? AND name IS NOT NULL ORDER BY name",
                [year],
            ).fetchall()
        ]
        assert names == sorted(["a.com", "www.b.com", "c.co.uk", 'd"quoted.com', "not a host"])


def test_the_store_ingest_accounts_for_every_line_per_year(tmp_path: Path) -> None:
    """The store keeps his release at registrable grain, so the count to compare is not the
    row count but the ingest's own accounting: every line is ok, rejected or blank, and every
    ok line's registrable is assigned that year."""
    release = _hostile_release(tmp_path)
    conn = connect(":memory:")
    init_db(conn)
    for year in YEARS:
        path = release / f"{year}.txt"
        stats = ingest_year_file(conn, path, year, report_path=tmp_path / f"report_{year}.csv")
        lines = path.read_bytes().count(b"\n")
        assert stats["lines"] == lines
        assert stats["ok"] + stats["rejected"] + stats["blank"] == lines
        expected = {
            to_registrable(raw.strip())
            for raw in path.read_text().splitlines()
            if raw.strip() and to_registrable(raw.strip())
        }
        held = {
            d
            for (d,) in conn.execute(
                "SELECT domain FROM domain_year WHERE assigned_year = ?", [year]
            ).fetchall()
        }
        assert held == expected


RELEASE = baseline_dir()


@pytest.mark.skipif(
    not all((RELEASE / f"{year}.txt").is_file() for year in YEARS),
    reason="his release is not on disk here",
)
def test_his_real_release_is_read_whole_per_year() -> None:
    """Against the files on disk: the loader the export's diffs use reads exactly the non-blank
    lines of each of his six files, and no file carries a carriage return a line-oriented
    `comm` would read as part of the name."""
    conn = duckdb.connect()
    for year in YEARS:
        path = RELEASE / f"{year}.txt"
        nonblank = int(
            subprocess.run(
                ["grep", "-c", "[^[:space:]]", str(path)],
                capture_output=True,
                text=True,
                env={"LC_ALL": "C"},
            ).stdout.strip()
            or 0
        )
        read = conn.execute(f"SELECT count(name) FROM ({his_lines('?')})", [str(path)]).fetchone()[
            0
        ]
        assert read == nonblank, f"{year}: read {read:,} of {nonblank:,} lines"
        carriage = subprocess.run(
            ["grep", "-c", "\r", str(path)], capture_output=True, text=True, env={"LC_ALL": "C"}
        ).stdout.strip()
        assert carriage == "0", f"{year}.txt carries CR line endings"
