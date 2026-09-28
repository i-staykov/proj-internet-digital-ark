"""The hosts two banked blocklists name, kept at hostname grain; every case id names its list."""

import io
import tarfile
from pathlib import Path

import duckdb
import his_release
import pytest

from ark import held
from ark import hostnames as hn
from ark.db import add_candidate, assign_year, ensure_source, init_db, record_evidence

SQUIDGUARD = "# This list was compiled in 0:00:20 on 2001.12.18 15:04:29.\n# by squidGuardRobot\n"
SQUIDGUARD += (
    "members.tripod.com\ntripod.com\n10.1.2.3\nunder_score.tripod.com\npages.example.org/x\n"
)
CHASTITY = {
    "adult/domains": "a.tripod.com\nb.novel.com\n",
    "adult/urls": "c.tripod.com/x\n",
    "adult/domains.20011124.diff": "+d.tripod.com\n-e.tripod.com\n",
    "mail/domains": "f.tripod.com\n",
}
TAR, V = "chastity-list_0.5.orig.tar.gz", "chastity-list:20011214 adult/domains host "


def chastity(tmp_path: Path, mtime: int = 1008288000) -> Path:
    with tarfile.open(path := tmp_path / TAR, "w:gz") as tar:
        for name, text in CHASTITY.items():
            info = tarfile.TarInfo(f"chastity-list-0.5/db/{name}")
            info.size, info.mtime = len(text.encode()), mtime
            tar.addfile(info, io.BytesIO(text.encode()))
    return path


def q(conn, sql: str) -> list:
    return conn.execute(sql).fetchall()


# fmt: off
LISTS = [  # (list, parent dated by, hosts written, one row, parents held, id)
    # the robot's compile stamp dates the list; a URL's path is stripped, an address dropped,
    # and a listed host dates itself, never tripod.com
    ("squidguard", None, ["members.tripod.com", "pages.example.org"],
     ("members.tripod.com", "tripod.com", 2001, "artifact_listing",
      "squidguard:adult/domains@20011218 host members.tripod.com", "line 3"),
     ["example.org", "tripod.com"], "squidguard"),
    # the tar member's header dates the member and a diff keeps its additions; the split keeps a
    # host under a parent dated by a pair of ours (tripod.com in 2001); b.novel.com is parked
    ("chastity", "store", ["a.tripod.com", "c.tripod.com", "d.tripod.com"],
     ("d.tripod.com", "tripod.com", 2001, "dated_directory", V + "d.tripod.com",
      "chastity-list-0.5/db/adult/domains.20011124.diff:line 1"), ["tripod.com"], "chastity"),
    # or under a parent named exactly in his files: his 2001 file holds novel.com, and
    # www.tripod.com, which dates no tripod.com
    ("chastity", "his", ["b.novel.com"],
     ("b.novel.com", "novel.com", 2001, "dated_directory", V + "b.novel.com",
      "chastity-list-0.5/db/adult/domains:line 2"), ["novel.com"], "chastity-his_file"),
]


@pytest.mark.parametrize("kind,dated,hosts,row,parents", [
    pytest.param(*c[:5], id=c[5]) for c in LISTS
])
# fmt: on
def test_field_wall_and_funnel(tmp_path, his_files, kind, dated, hosts, row, parents) -> None:
    init_db(conn := duckdb.connect(":memory:"))
    if kind == "squidguard":
        (path := tmp_path / "squidguard-adult-domains").write_text(SQUIDGUARD)
    else:
        path = chastity(tmp_path)
    if dated == "his":
        names = his_release.HIS_YEARS[2001] + ["novel.com", "www.tripod.com"]
        his_release.stage(his_files.parent, {"2001.txt": his_release.text(sorted(names))})
        held.prepare(his_files)
    elif dated == "store":
        source = ensure_source(conn, "squidguard_2001", "timestamped")
        add_candidate(conn, "tripod.com", source)
        v = "squidguard:adult/domains@20011218"
        assign_year(conn, record_evidence(conn, "tripod.com", source, 2001, "artifact_listing", v))
    years = q(conn, "SELECT domain, assigned_year FROM domain_year")
    stats = hn.ingest_blocklist_hostnames(conn, path)
    assert stats["hostname_year_rows"] == len(hosts)
    cols = "hostname, parent_domain, assigned_year, evidence_type, evidence_value, record_location"
    got = q(conn, f"SELECT {cols}, source_file FROM hostname_year JOIN evidence USING(evidence_id)")
    assert sorted(r[0] for r in got) == hosts and row in [r[:6] for r in got]
    assert {r[6] for r in got} == {path.name}
    assert q(conn, "SELECT domain, assigned_year FROM domain_year") == years
    assert sorted(d for (d,) in q(conn, "SELECT domain FROM domain")) == parents
    assert hn.ingest_blocklist_hostnames(conn, path)["skipped"] is True
    assert q(conn, "SELECT record_rows FROM ingested_file") == [(len(hosts),)]


def test_wall_a_member_stamped_outside_the_window_writes_nothing(tmp_path) -> None:
    init_db(conn := duckdb.connect(":memory:"))
    stats = hn.ingest_blocklist_hostnames(conn, chastity(tmp_path, mtime=1033171200))
    assert stats["out_of_window_member"] == 3  # the mail list is skipped first
    assert q(conn, "SELECT count(*) FROM hostname_year") == [(0,)]
