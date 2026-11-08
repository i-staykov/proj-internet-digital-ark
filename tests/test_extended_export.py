"""The 2002 to 2013 additions: only his same-year file's complement, only by a capture stamped
in that year, and a package of ours alone that verify proves disjoint from his files."""

import bz2
import csv
import gzip
import hashlib
import io
import json
import os
import subprocess
import zipfile
from decimal import Decimal as D
from types import SimpleNamespace

import pytest
from conftest import ROOT, script
from his_release import stage, text

from ark import approvals

HIS = {2002: ["already.com", "his.org"], 2003: ["his.org"]}


def _journal(rows: list[dict]) -> bytes:
    return gzip.compress("".join(json.dumps(r) + "\n" for r in rows).encode())


ROWS = [
    {"url": "http://already.com/", "timestamp": "20020601000000", "status": "200"},
    {"url": "http://new.com/a", "timestamp": "20020301000000", "status": "200"},
    {"url": "http://new.com/", "timestamp": "20020101000000"},  # the earliest: the one quoted
    {"url": "http://old.com/", "timestamp": "20010601000000"},  # the core window, not ours here
    {"url": "http://late.com/", "timestamp": "20140601000000"},  # 2014 on is not hunted
    {"url": "http://err.com/", "timestamp": "20020601000000", "status": "404"},
    {"url": "http://under_score.com/", "timestamp": "20020601000000"},
    {"url": "http://early.eu/", "timestamp": "20030601000000"},  # .eu was delegated in 2005
    {"url": "http://fine.info/", "timestamp": "20030601000000"},  # not the 1996-2001 allowlist
    {"url": "http://www.gone.yu/", "timestamp": "20130601000000"},  # .yu left the root in 2010
]
# Refused whole, as the core refuses them: a status-less row in a family that must carry one,
# after a row that would ship, and an error lane.
REFUSED = {
    "nypw_b.jsonl.gz": [
        {"url": "http://kept.com/", "timestamp": "20020601000000", "status": "200"},
        {"url": "http://nostatus.com/", "timestamp": "20020601000000"},
    ],
    "early_web_nonok_part1.jsonl.gz": [
        {"url": "http://errorpage.com/", "timestamp": "20020601000000"}
    ],
}


@pytest.fixture
def exported(tmp_path, monkeypatch):
    his = stage(tmp_path, {f"{y}.txt": text(names) for y, names in HIS.items()})
    ext = script("round/extended_export.py")
    monkeypatch.setattr(ext, "baseline_dir", lambda: his)
    monkeypatch.setattr(ext, "REVIEWER_EXTENDED_EE_BY_YEAR", {2002: D(4), 2003: D(2)})
    monkeypatch.setattr(ext, "english_weights", lambda: {"com": D("0.5"), "info": D("0.25")})
    monkeypatch.setattr(ext, "CACHE", tmp_path / "cache")
    journal = tmp_path / "raw/ia_cdx_hostnames/a.jsonl.gz"
    journal.parent.mkdir(parents=True)
    journal.write_bytes(_journal(ROWS))
    for name, rows in REFUSED.items():
        (journal.parent / name).write_bytes(_journal(rows))
    globs = {"*": str(tmp_path / "raw/*/*.jsonl*")}
    # a folder that is no capture source in SOURCES, and an approved one awaiting its decision
    other = tmp_path / "raw/ukwa_host_link_graph/law_uk_2014_host.jsonl"
    other.parent.mkdir()
    other.write_text(json.dumps(ROWS[1]) + "\n")
    with pytest.raises(SystemExit, match="ukwa_host_link_graph: not a capture source"):
        ext.export(globs, tmp_path / "out")
    other.unlink()

    def awaiting(source: str, evidence_type: str) -> None:
        raise approvals.NotApproved("awaiting classification")

    monkeypatch.setattr(approvals, "check", awaiting)
    with pytest.raises(SystemExit, match="ia_cdx_hostnames: awaiting classification"):
        ext.export(globs, tmp_path / "out")
    monkeypatch.setattr(approvals, "check", lambda *a: None)
    manifest = ext.export(globs, tmp_path / "out")
    return ext, his, tmp_path / "out", manifest, journal, globs


def test_only_his_same_year_complement_ships_and_each_by_its_own_year(exported):
    ext, _, out, manifest, journal, _ = exported
    assert sorted(manifest["years"]) == ["2002", "2003"]
    assert not list(out.glob("*.txt")), "the export writes additions only"
    for year, added in ((2002, "new.com"), (2003, "fine.info")):
        adds = (out / f"additions/{year}.txt").read_text().split()
        assert adds == [added] and not set(adds) & set(HIS[year])
        entry = manifest["years"][str(year)]
        assert entry["already_in_baseline"] + entry["accepted_new"] == entry["submitted_unique"]
        assert entry["baseline_unique"] + entry["accepted_new"] == entry["merged_unique"]
    assert manifest["years"]["2002"]["already_in_baseline"] == 1
    assert manifest["increment_ee"] == "0.7500"
    assert manifest["years"]["2003"]["growth_pct"] == "12.500000"
    drop = manifest["dropped"]
    assert (drop["outside_window"], drop["error_status"], drop["duplicate"]) == (2, 1, 1)
    assert (drop["invalid_host"], drop["tld_did_not_exist"], drop["journal_refused"]) == (1, 2, 2)
    with (out / "evidence_ledger.csv").open() as fh:
        row = next(r for r in csv.DictReader(fh) if r["host"] == "new.com")
    assert (row["year"], row["method"], row["line"]) == ("2002", "ia_cdx_domain_sweep", "2")
    assert row["timestamp"] == "20020301000000", (
        "a capture with a status outranks a status-less row"
    )
    source = next(i for i in manifest["inputs"] if i["path"] == row["source_file"])
    assert source["sha256"] == hashlib.sha256(journal.read_bytes()).hexdigest()
    assert source["replay"] == "https://web.archive.org/web/{ts}/{url}"
    assert ext.stale(out) == []
    added = journal.with_name("b.jsonl.gz")
    added.write_bytes(_journal(ROWS[:1]))
    assert ext.stale(out), "an added input makes the bank export again"
    assert ext.stale(out, allow_added=True) == [], "and is no reason for the packager to refuse"
    added.unlink()
    journal.write_bytes(_journal(ROWS[:2]))
    assert ext.stale(out), "a changed input makes the export stale"
    assert ext.stale(out, allow_added=True), "for the packager too"


def test_a_second_export_reads_only_the_inputs_that_moved(exported, monkeypatch):
    ext, _, out, manifest, journal, globs = exported
    torn = ext.cache_entry(journal)
    torn.write_bytes(torn.read_bytes()[:20])  # a torn entry is a miss, read again
    (ext.CACHE / "gone.gz").write_bytes(b"")  # no file's: a release run prunes it
    monkeypatch.setattr(ext, "INPUTS", globs)
    assert ext.export(globs, out)["years"] == manifest["years"]
    assert not (ext.CACHE / "gone.gz").exists()
    st = journal.stat()
    journal.write_bytes(b"x" * st.st_size)  # same size and mtime: its cached rows stand
    os.utime(journal, ns=(st.st_atime_ns, st.st_mtime_ns))
    assert ext.export(globs, out)["years"] == manifest["years"]
    journal.write_bytes(_journal(ROWS[:1]))
    assert ext.export(globs, out)["years"] != manifest["years"]


def test_a_decided_fleet_read_joins_and_an_undecided_one_waits(exported, monkeypatch):
    ext, _, out, _, _, _ = exported
    raw = out.parent / "fleet_read"
    for slug, host in (("deep-read", "fleet.com"), ("pending-read", "wait.com")):
        part = raw / slug / f"fleetread_bulk_cdx_file__{slug}_0001.jsonl.gz"
        part.parent.mkdir(parents=True)
        row = {"url": f"http://{host}/", "timestamp": "20030501000000", "status": "200"}
        part.write_bytes(_journal([row]))

    def decided(source: str, evidence_type: str) -> None:
        if source == "fleet_pending_read_hostnames":
            raise approvals.NotApproved("awaiting classification")

    monkeypatch.setattr(approvals, "check", decided)
    manifest = ext.export({"fleetread": str(raw / "*/fleetread_*.jsonl.gz")}, out / "fleet")
    assert (out / "fleet/additions/2003.txt").read_text().split() == ["fleet.com"]
    with (out / "fleet/evidence_ledger.csv").open() as fh:
        (row,) = csv.DictReader(fh)
    assert (row["method"], row["timestamp"]) == ("bulk_cdx_file", "20030501000000")
    (source,) = manifest["inputs"]
    assert (source["source"], source["replay"]) == (
        "fleet_deep_read_hostnames",
        "https://web.archive.org/web/{ts}/{url}",
    )


def _cut(script_name: str, start: str, end: str) -> str:
    body = (ROOT / "scripts/round" / script_name).read_text(encoding="utf-8")
    return "set -euo pipefail\n" + start + body.split(start, 1)[1].split(end, 1)[0]


def test_the_package_ships_ours_alone_and_verify_checks_it_against_his(exported, tmp_path):
    his, out = exported[1], exported[2]
    pack = _cut("package_delivery.sh", "# extended_years/: the", "# ISC candidates must stay")
    check = _cut("verify_delivery.sh", "# --- the extended years", "# --- 5 to 8")
    (tmp_path / "output").mkdir()
    out.rename(tmp_path / "output/extended_years")
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin/uv").write_text("#!/bin/sh\n")  # `--check` is the test above's
    (tmp_path / "bin/uv").chmod(0o755)
    env = {"PATH": f"{tmp_path / 'bin'}:/usr/bin:/bin", "STAGE": "stage"}
    run = lambda body, cwd, **more: subprocess.run(  # noqa: E731
        ["bash", "-c", body], cwd=cwd, env=env | more, capture_output=True, text=True
    )
    done = run(pack, tmp_path)
    assert done.returncode == 0, done.stderr
    shipped = tmp_path / "stage/extended_years"
    for f in (tmp_path / "output/extended_years/additions").glob(
        "*.txt"
    ):  # once, as the brief names it
        assert f.read_bytes() == (shipped / f.name).read_bytes()
    assert list(shipped.glob("*.txt")) and not (shipped / "additions").exists()
    done = run(check, tmp_path / "stage")
    assert "SKIP  2 additions" in done.stdout and "HIS" in done.stdout, done.stdout + done.stderr
    done = run(check, tmp_path / "stage", HIS=str(his))
    assert "PASS  2 additions" in done.stdout, done.stdout + done.stderr
    # one line of his slipped into the additions
    (shipped / "2003.txt").write_bytes(text(["fine.info", "his.org"]))
    done = run(check, tmp_path / "stage", HIS=str(his))
    assert "FAIL" in done.stdout and "repeats 1 lines of" in done.stdout, done.stdout
    (his / "2002.txt").write_bytes(text(HIS[2002] + ["zzz.com"]))
    done = run(check, tmp_path / "stage", HIS=str(his))
    assert "is not the file manifest.json names" in done.stdout, done.stdout
    # a sort that quits before reading his file (more than a pipe holds) FAILs with a reason
    sort = '#!/bin/sh\ncase "$*" in *-S*) exit 2;; esac\nexec /usr/bin/sort "$@"\n'
    (tmp_path / "bin/sort").write_text(sort)
    (tmp_path / "bin/sort").chmod(0o755)
    (his / "2003.txt").write_bytes(text([f"h{i}.com" for i in range(30000)]))
    done = run(check, tmp_path / "stage", HIS=str(his))
    assert "could not be compared" in done.stdout and "Traceback" not in done.stderr, done.stderr


def test_the_end_of_term_reader_keeps_the_earliest_capture_a_host_year_in_the_window():
    eot = script("sources/eot/eot_cdxj.py")
    lines = [
        b'gov,a)/ 20080102000000 {"url": "http://Example.COM:80/", "status": "301"}',
        b'gov,a)/x 20080101000000 {"url": "http://example.com/x", "status": "200"}',
        b'gov,a)/ 20010101000000 {"url": "http://old.gov/", "status": "200"}',
        b'gov,b)/ 20090101000000 {"url": "http://b.gov/", "status": "-"}',
        b'gov,c)/ 20090101000000 {"url": "http://c.gov/\\q", "status": "200"}',
    ]
    keep, broken = eot.earliest(lines)
    assert keep == {("example.com", "2008"): ("20080101000000", "http://example.com/x", "200")}
    assert broken == 1


def test_the_http_archive_reader_dates_a_host_by_its_own_2xx_or_3xx_request_alone():
    har = script("sources/httparchive/har_year.py")

    def row(day, t, action, host, path, code, secure="0"):
        return "\t".join([day, t, "Run_1", "ip", action, host, path, code, *[""] * 38, secure])

    log = [
        row("08/01/2012", "09:56:47", "GET", "www.a.com", "/", "200", secure="1"),
        row("08/01/2012", "09:00:00", "GET", "WWW.A.com", "/x", "301"),
        row("08/01/2012", "08:00:00", "GET", "b.com", "/", "404"),
        row("08/01/2012", "08:00:00", "", "", "http://c.com/", "0"),  # the page launch
        row("08/01/2011", "08:00:00", "GET", "d.com", "/", "200"),  # the agent's clock
        row("08/01/2012", "08:00:00", "GET", "89574,winebusiness.com", "/", "200"),
    ]
    test, outer = io.BytesIO(), io.BytesIO()
    with zipfile.ZipFile(test, "w") as z:
        z.writestr("1_IEWTR.txt.gz", gzip.compress("\n".join(["Date\tTime", *log]).encode()))
    with zipfile.ZipFile(outer, "w", zipfile.ZIP_STORED) as z:
        z.writestr("120801_0_S3K.zip", test.getvalue())
    keep: dict = {}
    for _, blob in har.members(io.BytesIO(outer.getvalue())):
        har.earliest(har.requests(blob), keep, "2012")
    assert keep == {("www.a.com", "2012"): ("20120801090000", "http://WWW.A.com/x", "301")}
    with pytest.raises(ValueError):  # cut inside a header: the zip fails, never the reader
        list(har.members(io.BytesIO(outer.getvalue()[:20])))


def test_the_clueweb_reader_writes_one_status_less_row_a_host_with_its_node_id(tmp_path):
    cw, ex = script("sources/crawl_lists/clueweb.py"), script("round/extended_export.py")
    lines = [
        b"http://a.com/ clueweb09-en0000-00-00000",
        b"http://a.com/x clueweb09-en0000-00-00001",
        b"http://b.com/ clueweb09-en0000-00-00002",
        b"http://a.com/y clueweb09-en0000-01-00000",  # a segment later: the window folds it
        b"http://under_score.com/ clueweb09-en0000-01-00001",
    ]
    stream = io.BytesIO(
        bz2.compress(b"\n".join(lines[:3]) + b"\n") + bz2.compress(b"\n".join(lines[3:]) + b"\n")
    )
    pairs = list(cw.runs(cw.lines(stream)))
    assert pairs == [
        ("http://a.com/", "clueweb09-en0000-00-00000"),
        ("http://b.com/", "clueweb09-en0000-00-00002"),
    ]
    cw.PART = 1
    parts = cw.write_parts(pairs, tmp_path, "clueweb09", "20090101000000")
    rows = [json.loads(gzip.open(p).read()) for p in parts]
    assert [r["node"] for r in rows] == ["clueweb09-en0000-00-00000", "clueweb09-en0000-00-00002"]
    assert rows[0]["timestamp"] == "20090101000000" and "status" not in rows[0]
    assert ex.screen(json.dumps(rows[0]).encode(), strict=False) == (
        None,
        (2009, "a.com", "20090101000000", "1"),
    )
    with pytest.raises(ValueError):  # a stream cut inside a block books nothing
        list(cw.lines(io.BytesIO(bz2.compress(b"http://c.com/ x\n" * 1000)[:-20])))
    # a URL list without node ids, gzipped: the node is the URL's ordinal in the file
    urls = io.BytesIO(gzip.compress(b"http://c.com/\nhttp://c.com/x\nhttp://d.com/\n"))
    assert list(cw.runs(cw.lines(urls, "gzip"))) == [("http://c.com/", "0"), ("http://d.com/", "2")]
    assert ex.capture("crawl_lists", tmp_path / "clueweb12_3.jsonl.gz")[1].endswith("nat.urls.gz")


def test_a_status_less_crawl_list_row_ships_through_the_export_with_its_node_id(
    tmp_path, monkeypatch
):
    ext = script("round/extended_export.py")
    his = stage(tmp_path, {"2009.txt": text(["his.org"])})
    monkeypatch.setattr(ext, "baseline_dir", lambda: his)
    monkeypatch.setattr(ext, "REVIEWER_EXTENDED_EE_BY_YEAR", {2009: D(4)})
    monkeypatch.setattr(ext, "english_weights", lambda: {"com": D("0.5")})
    monkeypatch.setattr(ext, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(approvals, "check", lambda *a: None)
    journal = tmp_path / "raw/crawl_lists/clueweb09_0.jsonl.gz"
    journal.parent.mkdir(parents=True)
    row = {"url": "http://new.com/", "timestamp": "20090101000000", "node": "clueweb09-en0000-00-1"}
    journal.write_bytes(_journal([row]))
    manifest = ext.export({"*": str(tmp_path / "raw/*/*.jsonl*")}, tmp_path / "out")
    assert manifest["years"]["2009"]["accepted_by_method"] == {"crawl_list_node": 1}
    with (tmp_path / "out/evidence_ledger.csv").open() as fh:
        row = next(csv.DictReader(fh))
    assert (row["host"], row["method"], row["line"]) == ("new.com", "crawl_list_node", "1")
    assert row["timestamp"] == "20090101000000"
    assert manifest["inputs"][0]["replay"].endswith("clueweb.urls-docid.bz2")


class _Fetch:
    """A fetch that hands over `body`, writes `reason` as its receipt to `err` and exits `rc`."""

    def __init__(self, body: bytes, rc: int, reason: str = "", err=None):
        self.stdout, self.returncode = io.BytesIO(body), rc
        if err is not None:
            err.write(json.dumps({"reason": reason}).encode())

    def kill(self):
        pass

    def wait(self, timeout=None):
        return self.returncode


def test_a_failed_fetch_counts_a_strike_and_leaves_no_part(tmp_path, monkeypatch):
    cw = script("sources/crawl_lists/clueweb.py")
    monkeypatch.setattr(cw, "OUT", tmp_path)
    monkeypatch.setattr(cw, "fetch", lambda *a: _Fetch(b"", 6))
    (tmp_path / ".clueweb09_0.tmp").write_bytes(b"stale")
    assert cw.read("clueweb09").startswith("clueweb09: not booked, fetch exit 6")
    assert (tmp_path / ".clueweb09.357226562.failed").read_text().count("\n") == 1
    assert not list(tmp_path.glob("*.tmp")) and not list(tmp_path.glob("*.jsonl.gz"))
    assert cw.todo() == ["clueweb09", "clueweb12", "wdc2012"] and cw.failures("clueweb09") == 1


def test_a_prefix_artifact_books_exactly_its_bytes_and_drops_the_cut_tail(tmp_path, monkeypatch):
    cw = script("sources/crawl_lists/clueweb.py")
    monkeypatch.setattr(cw, "OUT", tmp_path)
    prefix = bz2.compress(b"http://a.com/ n0\nhttp://b.com/ n1\n")
    # a multi-block member (over 900 KB of distinct lines), cut inside its second block: the
    # capture ends mid-line, as the real one does
    many = b"".join(b"http://h%07d.com/page n%d\n" % (i, i) for i in range(60_000))
    whole = bz2.compress(many, compresslevel=1)
    cut = whole[: len(whole) * 2 // 3]
    body = prefix + cut
    sha = hashlib.sha256(body).hexdigest()
    monkeypatch.setitem(cw.LISTS, "clueweb09", ("20090101000000", "bz2", len(body), sha))

    class Truncated:  # fetch.py exits 7 once the rest never arrives
        returncode = 7

        def __init__(self):
            self.stdout = io.BytesIO(body + b"more of the capture")

        def kill(self):
            pass

        def wait(self):
            return self.returncode

    monkeypatch.setattr(cw, "fetch", lambda url, max_bytes="14G": Truncated())
    (tmp_path / ".clueweb09.failed").write_text("old definition\n" * 3)
    assert cw.read("clueweb09").startswith(f"clueweb09\t{len(body)}\t")
    receipt = json.loads((tmp_path / f"clueweb09.{len(body)}.receipt").read_text())
    assert (receipt["bytes"], receipt["sha256"]) == (len(body), sha)
    rows = [json.loads(ln) for ln in gzip.open(tmp_path / "clueweb09_0.jsonl.gz", "rt")]
    assert [r["node"] for r in rows[:2]] == ["n0", "n1"] and 1000 < len(rows) < 60_000
    last = rows[-1]["url"]
    assert last.endswith("/page") and last == f"http://h{rows[-1]['node'][1:].zfill(7)}.com/page"
    assert all(r["url"].endswith("/page") for r in rows[2:]), "no mid-line fragment"
    assert not (tmp_path / ".clueweb09.failed").exists() and cw.todo()[0] == "clueweb12"
    monkeypatch.setitem(cw.LISTS, "clueweb09", ("20090101000000", "bz2", len(body) - 1, sha))
    assert "not the prefix's" in cw.read("clueweb09") and cw.failures("clueweb09") == 1


def test_a_host_index_reads_each_host_as_its_own_root_with_its_index_as_node(tmp_path, monkeypatch):
    cw = script("sources/crawl_lists/clueweb.py")
    monkeypatch.setattr(cw, "OUT", tmp_path)
    body = gzip.compress(b"0---0.com\t0\nflickr.com\t1\nunder_score.com\t2\nflickr.com\t3")

    class Whole:
        returncode = 0

        def __init__(self):
            self.stdout = io.BytesIO(body)

        def kill(self):
            pass

        def wait(self):
            return 0

    monkeypatch.setattr(cw, "fetch", lambda url, max_bytes="14G": Whole())
    assert cw.read("wdc2012").startswith(f"wdc2012\t{len(body)}\t")
    rows = [json.loads(ln) for ln in gzip.open(tmp_path / "wdc2012_0.jsonl.gz", "rt")]
    assert [(r["url"], r["node"], r["timestamp"]) for r in rows] == [
        ("http://0---0.com/", "0", "20120127000000"),
        ("http://flickr.com/", "1", "20120127000000"),
    ]
    assert json.loads((tmp_path / "wdc2012.receipt").read_text())["bytes"] == len(body)
    assert "wdc2012" not in cw.todo()
    body = b"not gzip at all"  # a corrupt stream strikes and stays to do
    (tmp_path / "wdc2012.receipt").unlink()
    assert cw.read("wdc2012").startswith("wdc2012: not booked")
    assert cw.failures("wdc2012") == 1 and "wdc2012" in cw.todo()


def test_the_http_archive_reader_counts_new_hosts_within_one_year(tmp_path, monkeypatch):
    har = script("sources/httparchive/har_year.py")
    monkeypatch.setattr(har, "OUT", tmp_path)
    for name, host in (("har_120101", "a.com"), ("har_130101", "b.com")):
        (tmp_path / f"{name}.jsonl.gz").write_bytes(_journal([{"url": f"http://{host}/"}]))
    assert har.seen_so_far(2012) == {"a.com"} and har.seen_so_far(2013) == {"b.com"}
    docs = [
        {"identifier": "httparchive_2013_01", "item_size": 1},  # a monthly: last whatever its size
        {"identifier": "httparchive_2013_12_15_7", "item_size": 9},
        {"identifier": "httparchive_2013_09_19_0", "item_size": 2},  # FIRST already
        {"identifier": "httparchive_2013_07_15_5", "item_size": 3},
    ]
    body = json.dumps({"response": {"docs": docs}}).encode()
    monkeypatch.setattr(
        har,
        "fetch",
        lambda url, max_bytes="1G": SimpleNamespace(stdout=io.BytesIO(body), wait=lambda: 0),
    )
    assert [i for i, _ in har.items()] == [
        *(n for n, _ in har.FIRST),
        "httparchive_2013_07_15_5",
        "httparchive_2013_12_15_7",
        "httparchive_2013_01",
    ]


def test_the_http_archive_reader_counts_what_is_left_offline_and_strikes_no_outage(
    tmp_path, monkeypatch
):
    har = script("sources/httparchive/har_year.py")
    monkeypatch.setattr(har, "OUT", tmp_path)
    monkeypatch.setattr(har, "PAUSE", 0)
    # nothing listed yet: each first item counts one, and so does the unanswered search
    assert har.left() == len(har.FIRST) + 1
    (tmp_path / ".har_items.json").write_text(
        '[["httparchive_2010", 2010], ["httparchive_2011", 2011]]'
    )
    (tmp_path / ".har_httparchive_2010.zips.json").write_text(
        '{"1010.zip": [3, "a"], "1011.zip": [3, "b"]}'
    )
    (tmp_path / "har_1010.jsonl.gz").write_bytes(b"")
    (tmp_path / ".har_1011.failed").write_text("x\n" * 3)
    assert har.left() == 1 and har.zips("httparchive_2011", ask=False) is None
    (tmp_path / ".har_httparchive_2011.zips.json").write_text("{}")
    assert har.left() == 0
    # a dead host or a 5xx: fetch exits 4 or 7, the zip is asked again and strikes nothing
    sha = hashlib.sha1(b"PK\x03\x04").hexdigest()
    cut = "the transfer failed: reset"
    monkeypatch.setattr(har, "fetch", lambda u, m, err: _Fetch(b"PK\x03\x04", 7, cut, err))
    line, keep = har.read("httparchive_2010", 2010, "1012.zip", 4, sha)
    assert line.endswith(f"fetch exit 7, {cut}, asked again after 0 s") and keep == {}
    assert har.failures("1012") == 0 and not list(tmp_path.glob("*1012*"))
    # the zip's own 4xx is the same exit and strikes
    gone = "the server answered 404"
    monkeypatch.setattr(har, "fetch", lambda u, m, err: _Fetch(b"", 7, gone, err))
    line, _ = har.read("httparchive_2010", 2010, "1012.zip", 4, sha)
    assert line.startswith("1012: not booked") and gone in line and har.failures("1012") == 1
    # a whole stream whose sha1 is not the item's strikes
    monkeypatch.setattr(har, "fetch", lambda u, m, err: _Fetch(b"PK\x05\x06", 0, "", err))
    line, _ = har.read("httparchive_2010", 2010, "1012.zip", 4, "not it")
    assert line.startswith("1012: not booked") and har.failures("1012") == 2
    # a stream that is not a stored zip strikes, whatever fetch says of it
    compressed = har.LOCAL.pack(b"PK\x03\x04", 20, 0, 8, 0, 0, 0, 1, 1, 1, 0) + b"xx"
    monkeypatch.setattr(har, "fetch", lambda u, m, err: _Fetch(compressed, 0, "", err))
    line, _ = har.read(
        "httparchive_2010", 2010, "1012.zip", 4, hashlib.sha1(compressed).hexdigest()
    )
    assert "not stored with its size" in line and har.failures("1012") == 3
    # an item's empty file list is answered, never kept: it is asked again next run
    monkeypatch.setattr(har, "fetch", lambda *a: _Fetch(b'{"files": []}', 0))
    assert har.zips("httparchive_2012") == {} and har.zips("httparchive_2012", ask=False) is None


def test_the_end_of_term_reader_counts_what_is_left_by_its_journals_and_strikes(
    tmp_path, monkeypatch
):
    eot = script("sources/eot/eot_cdxj.py")
    monkeypatch.setattr(eot, "OUT", tmp_path)
    for part in list(eot.PARTS)[1:]:
        (tmp_path / f"eot_{part}.jsonl.gz").write_bytes(b"")
    first = next(iter(eot.PARTS))
    (tmp_path / f".eot_{first}.failed").write_text("x\n" * 2)
    assert eot.left() == 1
    (tmp_path / f".eot_{first}.failed").write_text("x\n" * 3)
    assert eot.left() == 0
