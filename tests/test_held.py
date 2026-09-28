"""His release in, held by exact name: intake takes a release once, `prepare` reads every line
of his and writes none, `minus` and `intersect` are `LC_ALL=C comm` set arithmetic, every module
asking whether a name is dated asks `held`, and a seed queues only what nothing dates."""

import ast
import contextlib
import csv
import importlib.util
import json
import os
import re
import shutil
import stat
import struct
import subprocess
import sys
import zipfile
from functools import cache
from pathlib import Path

import duckdb
import pytest
from his_release import HIS_CANDIDATES, HIS_YEARS, MARKER, WEB_METHOD, capture, digests, stage, text
from typer.testing import CliRunner

from ark import held
from ark import work_queue as wq
from ark.audit import write_audit
from ark.bulk import BulkRecord, SourceSpec
from ark.cli import app
from ark.db import add_candidate, assign_year, connect, ensure_source, init_db, record_evidence
from ark.ingest import YEARS
from ark.seed import seed_from_file
from ark.seed_pool import combine_parts, write_source_part

ROOT = Path(__file__).resolve().parents[1]
# CRLF, a blank line, padding, upper case, a duplicate, a quote, a tab, and one not a host at all
HOSTILE = b'B.com\r\na.com\na.com\n\n  d.com  \nWWW.E.COM \r\nf"quoted,x.com\n\tt.com\nnot a host\n'
HOSTILE_NAMES = ["\tt.com", "a.com", "b.com", "d.com", 'f"quoted,x.com', "not a host", "www.e.com"]
# a bare CR, the read delimiter and a BOM: each passes `sort -c -u` and reads clean in DuckDB,
# yet `comm` would see other lines than `his_lines` does
COMM_SPLITS = {1997: b"a.com\rb.com\n", 1999: b"a.com\x01x\n", 2000: b"\xef\xbb\xbfa.com\n"}


def read(path: Path) -> list[str]:
    return path.read_bytes().decode().splitlines()


def _store() -> duckdb.DuckDBPyConnection:
    conn = connect(":memory:")
    init_db(conn)
    return conn


def test_prepare_holds_a_clean_file_in_place_and_a_sorted_copy_of_any_other(tmp_path) -> None:
    files = {"1998.txt": HOSTILE} | {f"{y}.txt": data for y, data in COMM_SPLITS.items()}
    folder = stage(tmp_path, files)
    before = digests(folder)
    his = held.prepare(folder)
    assert digests(folder) == before and his.marker == MARKER
    assert read(his.year(1998)) == HOSTILE_NAMES and his.counts["1998"] == len(HOSTILE_NAMES)
    for year in COMM_SPLITS:
        lines = f"SELECT DISTINCT name FROM ({held.his_lines('?')}) WHERE name <> '' ORDER BY 1"
        names = duckdb.connect().execute(lines, [str(folder / f"{year}.txt")]).fetchall()
        assert read(his.year(year)) == [name for (name,) in names]
    copies = {str(p.relative_to(his.dir)) for p in his.dir.rglob("*") if p.is_file()}
    copied = {f"{y}.txt" for y in (1997, 1998, 1999, 2000)} | {"isc_survey_hostnames/2000-07.txt"}
    copied |= {"candidate_pool.txt", "candidate_pool_unparsed_format.txt"}
    assert copies - {held.ALL, held.CANDIDATES, held.STAMP} == copied, "what comm would misread"
    union = sorted({name for y in YEARS for name in read(his.year(y))})
    assert read(his.all) == union and his.counts["all"] == len(union)
    expected = {name.lower() for names in HIS_CANDIDATES.values() for name in names}
    assert read(his.candidates) == sorted(expected), "every candidate file, never the README"
    assert [str(p.relative_to(folder)) for p in his.candidate_files] == list(HIS_CANDIDATES)


def test_minus_and_intersect_are_set_arithmetic(tmp_path: Path, his_files: Path) -> None:
    """By exact name: his www.rolled.com does not hold rolled.com."""
    his = held.load(his_files)
    ours = tmp_path / "ours.txt"
    ours.write_bytes(text(["already-his.com", "early.his.org", "new.com", "rolled.com", "zz.net"]))
    assert held.minus(ours, his.year(1996), tmp_path / "net.txt") == 3
    assert read(tmp_path / "net.txt") == ["new.com", "rolled.com", "zz.net"]
    assert held.intersect(ours, his.all, tmp_path / "both.txt") == 2
    assert read(tmp_path / "both.txt") == ["already-his.com", "early.his.org"]


def test_comm_never_sees_an_unsorted_file(tmp_path: Path) -> None:
    """macOS `comm` exits 0 on unsorted input, so the refusal cannot rest on its exit status."""
    good, bad, dupe = tmp_path / "good", tmp_path / "bad", tmp_path / "dupe"
    good.write_bytes(text(["a.com", "b.com"]))
    bad.write_bytes(text(["b.com", "a.com"]))
    dupe.write_bytes(text(["a.com", "a.com"]))
    for comm, names, against in ((held.minus, bad, good), (held.intersect, good, bad)):
        with pytest.raises(held.HeldError, match="not LC_ALL=C sorted"):
            comm(names, against, tmp_path / "out.txt")
    with pytest.raises(held.HeldError, match="not LC_ALL=C sorted"):
        held.minus(dupe, good, tmp_path / "out.txt")
    assert not (tmp_path / "out.txt").exists()


def test_dump_refuses_what_is_not_our_sorted_lowercase_names(tmp_path: Path) -> None:
    conn = duckdb.connect()
    conn.execute("CREATE TABLE t AS SELECT * FROM (VALUES ('b.com'), ('a.com'), ('C.com')) v(n)")
    assert held.dump(conn, "SELECT n FROM t WHERE n <> 'C.com' ORDER BY n", tmp_path / "ok") == 2
    assert read(tmp_path / "ok") == ["a.com", "b.com"]
    for query, match in (
        ("SELECT n FROM t ORDER BY n", "not a lowercase name"),
        ("SELECT n FROM t WHERE n <> 'C.com' ORDER BY n DESC", "not LC_ALL=C sorted"),
        ("SELECT NULL AS n UNION ALL SELECT 'a.com' ORDER BY 1 NULLS FIRST", "not a lowercase"),
    ):
        with pytest.raises(held.HeldError, match=match):
            held.dump(conn, query, tmp_path / "refused")
    assert not list(tmp_path.glob("refused*"))
    assert held.dump(conn, "SELECT n FROM t WHERE false", tmp_path / "empty") == 0


def test_load_refuses_a_release_it_has_not_prepared_or_that_moved(his_files: Path) -> None:
    """And `prepare` refuses an incomplete release."""
    isc = his_files / "isc_survey_hostnames/2001-01.txt"
    isc.write_bytes(text(["new.isc-held.net"]))
    with pytest.raises(held.HeldError, match="other files"):
        held.load(his_files)
    isc.unlink()
    st = (year := his_files / "2000.txt").stat()
    os.utime(year, ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))
    with pytest.raises(held.HeldError, match="changed since .* run uv run ark intake"):
        held.load(his_files)
    (held.HELD_ROOT / MARKER / held.STAMP).unlink()
    with pytest.raises(held.HeldError, match="no held sets .* run uv run ark intake"):
        held.load(his_files)
    (his_files / "candidate_pool.txt").unlink()
    with pytest.raises(held.HeldError, match="incomplete, missing: .*candidate_pool.txt"):
        held.prepare(his_files)


def test_prepare_keeps_only_the_current_release_and_no_stale_part(his_files: Path) -> None:
    """Another spelling of its own folder, as on a case-insensitive disk, is never pruned."""
    old, kept, alias = (held.HELD_ROOT / n for n in ("merged260101", "not-held-sets", "alias"))
    old.mkdir()
    kept.mkdir()
    (old / held.STAMP).write_text("{}")
    (held.HELD_ROOT / MARKER / "all.txt.part").write_text("half")
    alias.symlink_to(held.HELD_ROOT / MARKER, target_is_directory=True)
    his = held.prepare(his_files)
    assert not old.exists() and kept.exists() and (alias / held.STAMP).is_file()
    assert not list(his.dir.rglob("*.part"))


def test_ark_intake_writes_the_held_sets_even_from_a_dot(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(stage(tmp_path))
    result = CliRunner().invoke(app, ["intake", "--baseline", "."])
    assert result.exit_code == 0, result.output
    his = held.load(Path("."))
    assert his.dir == held.HELD_ROOT / MARKER
    assert read(his.all) == sorted({name for names in HIS_YEARS.values() for name in names})


def test_the_audit_rows_each_line_of_his_corrected_or_dropped(tmp_path: Path) -> None:
    for year in YEARS:
        extra = "www.corrected.com\n$garbage$\n" if year == 1996 else ""
        (tmp_path / f"{year}.txt").write_text(f"clean.com\n{extra}", encoding="utf-8")
    stats = write_audit(tmp_path, tmp_path / "audit.csv")
    assert stats == {"lines": 8, "unchanged": 6, "corrected": 1, "dropped": 1}
    corrected, dropped = csv.DictReader((tmp_path / "audit.csv").open(encoding="utf-8"))
    want = ["www.corrected.com", "corrected.com", "www prefix removed", "valid", "1996.txt", "1996"]
    assert list(corrected.values()) == want
    assert dropped["original"] == "$garbage$" and dropped["normalized"] == ""
    assert dropped["result"] == "dropped" and dropped["reason"]


def _ours(conn, domain: str, year: int, host: str | None = None, assign: bool = True) -> None:
    cdx = ensure_source(conn, "ia_cdx", "timestamped")
    add_candidate(conn, domain, cdx)
    value = capture(host or domain, year)
    row = record_evidence(conn, domain, cdx, year, "cdx_timestamp", value, None, WEB_METHOD)
    if assign:
        assign_year(conn, row)


def test_a_name_is_dated_by_a_pair_of_ours_or_an_exact_line_of_his(his_files: Path) -> None:
    """ours.com is ours in 1998; already-his.com is his every year and not in the store; his
    www.rolled.com is not rolled.com; early.his.org is ours in 1998 and his in 1996; a capture
    of www.www-only.com dates no pair of www-only.com; cand.org is a candidate of ours."""
    conn = _store()
    _ours(conn, "ours.com", 1998)
    _ours(conn, "early.his.org", 1998)
    _ours(conn, "www-only.com", 1998, host="www.www-only.com", assign=False)
    add_candidate(conn, "cand.org", ensure_source(conn, "links", "candidate_only"))
    asked = (
        "ours.com already-his.com rolled.com early.his.org www-only.com cand.org new.net".split()
    )
    assert held.attested(conn, asked) == {"ours.com", "already-his.com", "early.his.org"}
    pairs = {("ours.com", 1998), ("early.his.org", 1996), ("early.his.org", 1998)}
    assert held.known_years(conn, asked) == pairs | {("already-his.com", y) for y in YEARS}
    extra = ["held-candidate.com", "www.rolled.com"]
    known = {"ours.com", "early.his.org", "www-only.com", "cand.org", "already-his.com", *extra}
    assert held.known_names(conn, asked + extra) == known
    for name in ("Foo.com", " foo.com", "foo.com\n", "a\nb.com", "a\tb.com", ""):
        for ask in (held.attested, held.known_years):
            with pytest.raises(ValueError, match="not a lowercase name"):
                ask(conn, ["ok.com", name])


def test_attested_and_known_names_fail_closed_without_his_files() -> None:
    """An empty ask admits nothing and needs no release; any other ask needs one."""
    conn = _store()
    assert held.attested(conn, []) == set() and held.known_years(conn, iter(())) == set()
    for ask in (held.attested, held.known_years, held.known_names):
        with pytest.raises(held.HeldError, match="run uv run ark intake"):
            ask(conn, ["a.com"])


# **The call-site scan.** A module that reads `domain` or `domain_year` imports `ark.held`, and
# no lane asks those tables whether a name is dated, so no lane misses a name only his files
# date. It reads the source and never imports it: some scripts open the store at import.

# `old.domain_year` too, and never `domain_language`, `new_domain_year` or a `domain(` call
_TABLE = r"(?:\w+\.)?domain(?:_year)?(?![\w.(])"
# rule A: any read of the two tables
READS = re.compile(rf"(?<!delete )\b(?:from|join)\s+{_TABLE}", re.I)
# rule B, a read that asks whether a name is there: [NOT] EXISTS (SELECT 1 FROM t ...),
# x [NOT] IN (SELECT domain FROM t), the set itself fetched, JOIN t x ON, FROM t WHERE domain =
MEMBERSHIP = re.compile(
    "|".join(
        [
            rf"\bexists\s*\(\s*select\b[^()]*?\bfrom\s+{_TABLE}",
            rf"\bin\s*\(\s*select\s+(?:distinct\s+)?(?:\w+\.)?domain\s+from\s+{_TABLE}",
            rf"(?:^|\()\s*select\s+(?:distinct\s+)?(?:\w+\.)?domain"
            rf"(?:\s*,\s*(?:\w+\.)?assigned_year)?\s+from\s+{_TABLE}",
            rf"\bjoin\s+{_TABLE}\s+(?:as\s+)?\w+\s+on\b",
            rf"\bfrom\s+{_TABLE}(?:\s+(?:as\s+)?\w+)?\s+where\s+(?:\w+\.)?domain\s*(?:=|in\b)",
        ]
    ),
    re.I,
)
# Modules that read the tables without importing held, each for a reason that is not a test
# of whether a name is dated
ALLOWED = {
    "src/ark/db.py": "add_candidates registers a name; it cannot import held, which imports it",
    "src/ark/provenance.py": "writes and loads the store's tables whole",
    "src/ark/provenance_trace.py": "ships alone as trace.py, importing only the standard library",
    "scripts/harness/audit_residual.py": "a freshness mark over the store's candidates",
}
# The lanes: each splits what it read into dated and candidate by whether a name is dated
LANES = ["src/ark/bulk.py", "src/ark/hostnames.py", "scripts/engines/split_expansion_journal.py"]
LANES += [
    f"scripts/sources/{rel}.py"
    for rel in """blocklists/split_chastity blocklists/split_junkfilter directories/split_tucows
    directories/split_urlmerchant mail_corpora/collect_enron mail_corpora/collect_mailing_lists
    mail_corpora/split_fac mail_corpora/split_jeb_mail registries/split_cctld_capture
    registries/split_granitecanyon trade_press/split_trade_press usenet/split_rtfm_faqs
    usenet/split_usenet usenet/split_usenet_addresses usenet/split_usenet_whois
    usenet/project_usenet_bare usenet/measure_usenet_yield usenet/split_uucp_maps""".split()
]
# Statements in a lane that match rule B and leave no name only his files date, keyed by a
# substring only that statement holds
LANE_STATEMENTS_EXEMPT = {
    ("src/ark/bulk.py", "FROM _source_names WHERE name NOT IN (SELECT domain FROM domain_year)"): (
        "the store's half of `held.attested`, for millions of names; `held.minus` takes his next"
    ),
}


@cache
def _tree(rel: str) -> ast.Module:
    return ast.parse((ROOT / rel).read_text(encoding="utf-8"), filename=rel)


@cache
def strings(rel: str) -> list[tuple[int, str]]:
    """Every string the module holds but its docstrings, as `(line, text)` with whitespace
    collapsed. Adjacent literals arrive merged, and an f-string reads `{}` for each hole."""
    kinds = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    skip = {
        id(node.body[0].value)
        for node in ast.walk(_tree(rel))
        if isinstance(node, kinds) and node.body and isinstance(node.body[0], ast.Expr)
    }
    out = []
    for node in ast.walk(_tree(rel)):
        if isinstance(node, ast.JoinedStr):
            skip |= {id(value) for value in node.values}
            parts = [v.value if isinstance(v, ast.Constant) else "{}" for v in node.values]
            out.append((node.lineno, "".join(parts)))
        elif isinstance(node, ast.Constant) and type(node.value) is str and id(node) not in skip:
            out.append((node.lineno, node.value))
    return [(line, " ".join(value.split())) for line, value in out]


def imports_held(rel: str) -> bool:
    """`import ark.held`, `from ark import held` or `from ark.held import ...`, a lazy one too.
    Held itself defines the test, so it passes it."""
    for node in ast.walk(_tree(rel)):
        if isinstance(node, ast.Import):
            dotted = {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            dotted = {node.module, *(f"{node.module}.{a.name}" for a in node.names)}
        else:
            continue
        if "ark.held" in dotted:
            return True
    return rel == "src/ark/held.py"


def hits(rel: str, rule: re.Pattern) -> list[tuple[int, str]]:
    return [(line, value) for line, value in strings(rel) if rule.search(value)]


def test_every_module_reading_the_tables_imports_held() -> None:
    modules = [p for top in ("src", "scripts") for p in sorted((ROOT / top).rglob("*.py"))]
    modules = [str(path.relative_to(ROOT)) for path in modules]
    offenders = [
        f"{rel}:{','.join(str(line) for line, _ in found)}"
        for rel in modules
        if (found := hits(rel, READS)) and not imports_held(rel) and rel not in ALLOWED
    ]
    assert offenders == [], f"import ark.held, or add the module to ALLOWED: {offenders}"
    stale = [rel for rel in ALLOWED if not hits(rel, READS) or imports_held(rel)]
    assert stale == [], f"these no longer need ALLOWED: {stale}"


def test_no_lane_asks_the_tables_whether_a_name_is_dated() -> None:
    def exempt(rel: str, value: str) -> bool:
        return any(path == rel and key in value for path, key in LANE_STATEMENTS_EXEMPT)

    failures = [f"{rel}: does not import ark.held" for rel in LANES if not imports_held(rel)]
    failures += [
        f"{rel}:{line}: {value[:120]}"
        for rel in LANES
        for line, value in hits(rel, MEMBERSHIP)
        if not exempt(rel, value)
    ]
    assert failures == [], failures
    for rel, key in LANE_STATEMENTS_EXEMPT:  # each exemption covers one statement rule B sees
        (statement,) = [value for _, value in strings(rel) if key in value]
        assert MEMBERSHIP.search(statement), f"{rel}: {key!r} needs no exemption"


def test_split_chastity_dates_what_we_or_his_files_date(tmp_path, his_files, monkeypatch) -> None:
    """The scan cannot see which question a lane asks. already-his.com is dated by his files
    alone, his www.rolled.com dates no rolled.com, and cand.org, only listed by us, is undated."""
    path = ROOT / "scripts/sources/blocklists/split_chastity.py"
    spec = importlib.util.spec_from_file_location("split_chastity", path)
    spec.loader.exec_module(lane := importlib.util.module_from_spec(spec))
    conn = _store()
    _ours(conn, "ours.com", 2001)
    add_candidate(conn, "cand.org", ensure_source(conn, "links", "candidate_only"))
    (src := tmp_path / "db" / "adult").mkdir(parents=True)
    (src / "domains").write_text("ours.com\nalready-his.com\nrolled.com\ncand.org\nnovel.net\n")
    monkeypatch.setattr(lane, "SRC", src.parent)
    monkeypatch.setattr(lane, "connect_read_only_patiently", lambda _path: conn)
    monkeypatch.setattr(sys, "argv", ["split_chastity.py", "--write", "--out", str(tmp_path)])
    assert lane.main() == 0
    cand, dated = (p.read_text().split() for p in sorted(tmp_path.glob("chastity-*.txt")))
    assert dated == ["already-his.com", "ours.com"]
    assert cand == ["cand.org", "novel.net", "rolled.com"]


# **Intake** takes a release in one command; `releases.py` fills its table from disk, keeps every
# cell and byte-verifies each tree. His calculator is stubbed at two EE per line.

_SPEC = importlib.util.spec_from_file_location("intake", ROOT / "scripts/round/intake.py")
_SPEC.loader.exec_module(intake := importlib.util.module_from_spec(_SPEC))
releases = intake.releases
LINES = {1996: 3, 1997: 0, 1998: 5, 1999: 1, 2000: 2, 2001: 1234}
ZITE = "".join(f"zite{i}.com\n" for i in range(3))  # 1996.txt's length, other bytes
NEW = "merged261231"  # a date no real release uses, so no assertion reads a real row
STAMP = (2026, 12, 31, 10, 31, 0)
PHASE7 = "feedback-phase-7/Domain_Data_Collection_Task 3/merged260830"
ZIP7 = "feedback-phase-7/Domain_Data_Collection_Task_0831_UpdateV2.zip"
VERIFIED = "byte-verified against their zips, deletable once the off-site copy exists: "
PATHS = {"page": "releases.md", "feedback": "feedback", "archive": "archive", "legacy": "legacy"}
BENCH = {"baseline-json": "baseline.json", "rounds-page": "rounds.md", "calculator": "ee.py"}
CALCULATOR = """import json, sys
n = sum(1 for line in open(sys.argv[1]) if line.strip())
out = open(sys.argv[sys.argv.index("--output-dir") + 1] + "/summary.json", "w")
out.write(json.dumps({"equivalent_english_domains": f"{2 * n:.4f}"}))
"""


def _tree_on_disk(where: Path) -> Path:
    where.mkdir(parents=True)
    for y in YEARS:
        (where / f"{y}.txt").write_text("".join(f"site{i}.com\n" for i in range(LINES[y])))
    (where / "candidate_pool.txt").write_text("x.com\n")
    return where


def _zip(tree: Path, path: Path, wrap: str = "", method: int = zipfile.ZIP_STORED) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        for f in sorted(tree.iterdir()):
            info = zipfile.ZipInfo(f"{wrap}{tree.name}/{f.name}", STAMP)
            zf.writestr(info, f.read_bytes(), method)
    return path


def _his_zip(tmp_path: Path, name: str = "Task_0903.zip", note: str | None = None) -> Path:
    staged = _tree_on_disk(tmp_path / "staging" / name / NEW)
    if note is not None:
        (staged / "note.txt").write_text(note)
    return _zip(staged, tmp_path / "incoming" / name, "Domain_Data_Collection_Task/")


def _bench(tmp_path: Path) -> Path:
    """A release beside his zip, one without, a blank page, round 7 unwritten; his zip."""
    feedback = tmp_path / "feedback"
    _zip(_tree_on_disk(feedback / PHASE7), feedback / ZIP7, "Domain_Data_Collection_Task 3/")
    (feedback / "feedback-phase-7/note.docx").write_bytes(b"not a release")
    _tree_on_disk(feedback / "feedback-phase-4/merged260810")
    blank = releases.render_table([releases.blank_row(m) for m in releases.RELEASES])
    (tmp_path / "releases.md").write_text(f"{releases.BEGIN}\n{blank}\n{releases.END}\n")
    for copy, tracked in (("baseline.json", "data"), ("rounds.md", "docs/registers")):
        lines = (ROOT / tracked / copy).read_text(encoding="utf-8").splitlines(keepends=True)
        (tmp_path / copy).write_text("".join(x for x in lines if not x.startswith("| 7 |")))
    (tmp_path / "ee.py").write_text(CALCULATOR)
    return _his_zip(tmp_path)


@pytest.fixture
def run(monkeypatch, capsys, tmp_path):
    """A script's main() over the tmp layout, printing; `stops` matches the exit it must raise."""

    def run(script, *flags: str, stops: str | None = None) -> str:
        paths = PATHS | (BENCH if script is intake else {})
        argv = [f"--{flag}={tmp_path / name}" for flag, name in paths.items()]
        monkeypatch.setattr(sys, "argv", [script.__name__, *argv, *flags])
        with pytest.raises(SystemExit, match=stops) if stops else contextlib.nullcontext():
            script.main()
        return capsys.readouterr().out

    return run


def _rows(tmp_path: Path) -> dict[str, dict[str, str]]:
    return {r["marker"]: r for r in releases.split_page((tmp_path / "releases.md").read_text())[1]}


def _snapshot(tmp_path: Path) -> list[str]:
    return [(tmp_path / name).read_text() for name in ("baseline.json", "releases.md", "rounds.md")]


# Zip members verify_trees refuses: a path read as another, a second copy, a symlink
UNSAFE = {
    "above": "../merged260830/stray.txt",
    "dot": "merged260830/./stray.txt",
    "absolute": "/merged260830/stray.txt",
    "backslash": "merged260830/sub\\stray.txt",
    "duplicate": "wrapper/merged260830/1996.txt",
    "symlink-member": "merged260830/link",
}


@pytest.mark.filterwarnings("ignore:Duplicate name")
@pytest.mark.parametrize("case", [*UNSAFE, "file", "parent", "linked-extra", "payload"])
def test_verify_trees_refuses_an_unsafe_member_a_symlink_or_a_bad_payload(tmp_path, capsys, case):
    """No tree verifies against a member read as another path, a symlink or a corrupt stream."""
    parent = tmp_path / "extracted"
    tree = _tree_on_disk(parent / "merged260830")
    archive = _zip(tree, tmp_path / "release.zip", method=zipfile.ZIP_DEFLATED)
    elsewhere = tmp_path / "elsewhere"
    if member := UNSAFE.get(case):
        info = zipfile.ZipInfo(member, STAMP)
        if case == "symlink-member":  # the member's bytes sit on disk, so only its type refuses it
            info.create_system, info.external_attr = 3, (stat.S_IFLNK | 0o644) << 16
            (tree / "link").write_bytes(b"extra\n")
        with zipfile.ZipFile(archive, "a") as zf:
            data = (tree / "1996.txt").read_bytes() if case == "duplicate" else b"extra\n"
            zf.writestr(info, data)
    elif case == "payload":  # same size and CRC-32, so only reading the stream catches it
        with zipfile.ZipFile(archive) as zf:
            info = zf.getinfo(f"{tree.name}/1996.txt")
        payload = bytearray(archive.read_bytes())
        sizes = struct.unpack_from("<HH", payload, info.header_offset + 26)
        payload[info.header_offset + 30 + sum(sizes)] |= 0b110
        archive.write_bytes(payload)
    elif case == "linked-extra":
        elsewhere.mkdir()
        (tree / "extra").symlink_to(elsewhere, target_is_directory=True)
    else:  # his file itself, or a folder above it
        linked = tree / "1996.txt" if case == "file" else parent
        linked.rename(elsewhere)
        linked.symlink_to(elsewhere, target_is_directory=linked == parent)
    assert releases.verify_trees({tree.name: [tree]}, {tree.name: [archive]}) is False
    out = capsys.readouterr().out
    assert out.splitlines()[-1] == VERIFIED + "none"
    assert "unsafe" in out or not member


def test_verify_trees_claims_each_copy_that_matches_its_zip_and_writes_nothing(run, tmp_path):
    """A marker newer than RELEASES is verified too, and every copy of a tree, each by CRC-32."""
    feedback = tmp_path / "feedback"
    future, shallow = (_tree_on_disk(feedback / m) for m in ("merged270101", "merged260830"))
    deep = _tree_on_disk(feedback / "duplicate/nested/merged260830")
    _zip(future, feedback / "future.zip")
    _zip(shallow, feedback / "release.zip")
    assert releases.find_trees(feedback, {})[shallow.name] == [shallow, deep]
    last = run(releases, "--verify-trees").splitlines()[-1]
    assert all(str(tree) in last for tree in (future, shallow, deep))
    (deep / "1996.txt").write_text(ZITE)
    (future / "1998.txt").unlink()
    (shallow / "stray.txt").write_text("extra\n")
    assert run(releases, "--verify-trees", stops="^1$").splitlines()[-1] == VERIFIED + "none"
    assert not (tmp_path / "releases.md").exists()


@pytest.mark.skipif(shutil.which("zstd") is None, reason="zstd not installed")
def test_zstd_packs_the_zipless_tree_and_hashes_it(run, tmp_path):
    """Only the tree named by the marker goes in, rooted at the marker."""
    _bench(tmp_path)
    run(releases, "--zstd")
    target = tmp_path / "archive/merged260810.tar.zst"
    row = _rows(tmp_path)["merged260810"]
    assert (row["artifact"], row["sha256"]) == (target.name, digests(target.parent)[target.name])
    tar = subprocess.run(["zstd", "-dc", str(target)], capture_output=True, check=True).stdout
    listed = subprocess.run(["tar", "-tf", "-"], input=tar, capture_output=True, check=True)
    names = {line.strip("/") for line in listed.stdout.decode().split()}
    assert "merged260810/2001.txt" in names
    assert all(n == "merged260810" or n.startswith("merged260810/") for n in names)


def test_a_release_and_a_verdict_go_in_once_with_one_command(run, tmp_path):
    """A dry run or a wrong sha256 writes nothing; a repeat changes no byte; a second zip stops;
    a table cell outlives its zip."""
    his = _bench(tmp_path)
    # His packer's stamp dates a release when it falls on the marker's day; else only the day does.
    assert intake.released_at(his, NEW, None) == "2026-12-31 10:31"
    assert intake.released_at(his, "merged260830", None) == "2026-08-30 00:00"
    assert intake.released_at(his, NEW, "2026-12-31 09:04") == "2026-12-31 09:04"
    with zipfile.ZipFile(empty := tmp_path / "empty.zip", "w") as zf:
        zf.writestr("readme.txt", "nothing here")
    with pytest.raises(SystemExit):
        intake.marker_of(empty, None)
    before = _snapshot(tmp_path)
    run(intake, str(his), "--dry-run")
    run(intake, str(his), "--sha256", "0" * 64, stops="sha256 is")
    assert _snapshot(tmp_path) == before
    assert not list((tmp_path / "feedback").rglob(NEW))
    assert not (tmp_path / "feedback" / his.name).exists()

    mail = ["--mail", str(ROOT / "tests/fixtures/verdict_round7.txt"), "--round", "7"]
    run(intake, str(his), *mail, "--received=2026-09-02 05:50")
    written = json.loads((tmp_path / "baseline.json").read_text())
    tracked = json.loads((ROOT / "data/baseline.json").read_text())
    current = written["current"]
    assert (current["marker"], current["released_at"]) == (NEW, "2026-12-31 10:31")
    assert current["directory"].endswith(f"Domain_Data_Collection_Task/{NEW}")
    assert current["reviewer_pairs"] == sum(LINES.values())
    assert current["reviewer_ee_by_year"]["2001"] == "2468.0000"
    assert current["reviewer_ee"] == f"{2 * sum(LINES.values())}.0000"
    # The round fields and the ledger are separate decisions, left where they were.
    assert all(current[k] == tracked["current"][k] for k in ("round_label", "round_since"))
    assert (written["rounds"], written["original"]) == (tracked["rounds"], tracked["original"])
    rows = _rows(tmp_path)
    assert rows[NEW]["2001"] == "1,234" and rows[NEW]["artifact"] == his.name
    assert rows[NEW]["sha256"] == digests(his.parent)[his.name]
    assert [rows["merged260830"][str(y)] for y in YEARS] == ["3", "0", "5", "1", "2", "1,234"]
    assert rows["merged260830"]["sha256"] == digests(tmp_path / "feedback")[ZIP7]
    assert rows["merged260810"]["sha256"] == "pending", "a zip-less tree has no artifact yet"
    assert rows["merged260902-3"]["released"] == "2026-09-02"
    assert all(rows[m]["sha256"] == "none" for m in releases.NOT_RECEIVED)
    round7 = [x for x in (tmp_path / "rounds.md").read_text().splitlines() if x.startswith("| 7 |")]
    assert any("1,456,458.1029" in map(str.strip, line.split("|")) for line in round7)

    before = _snapshot(tmp_path)
    run(intake, str(his))
    run(intake, str(_his_zip(tmp_path, "Task_0903_v2.zip", "repacked\n")), stops="already recorded")
    (tmp_path / "feedback" / ZIP7).unlink()
    run(releases)
    assert _snapshot(tmp_path) == before


# **Seeding.** `ark seed` queues only the names nothing dates, `ark seed-pool` ships the raw
# hostnames and URLs held evidence names, and the work queue hands out what was queued.

TASK = "cdx_verify"


def test_seed_queues_all_but_a_name_ours_or_his_already_date(tmp_path, his_files) -> None:
    """ours.com is dated by our evidence and already-his.com by his files alone; known.com is
    on file but undated, so it is queued; his www.rolled.com dates no rolled.com."""
    conn = _store()
    sid = ensure_source(conn, "wayback_cdx", "timestamped")
    for name in ("ours.com", "known.com"):
        add_candidate(conn, name, sid)
    assign_year(conn, record_evidence(conn, "ours.com", sid, 1997, "cdx_timestamp", "x"))
    seeds, queue = tmp_path / "seeds.txt", wq.connect_queue(":memory:")
    names = "already-his.com ours.com known.com fresh.org www.fresh.org rolled.com $garbage$ x.net"
    seeds.write_text("\n".join(names.split()) + "\n", encoding="utf-8")
    stats = seed_from_file(conn, queue, seeds, limit=7)
    assert (stats["lines"], stats["invalid"], stats["already_candidate"]) == (7, 1, 1)
    assert (stats["already_confirmed_baseline"], stats["already_confirmed_own_evidence"]) == (1, 1)
    assert (stats["new_candidates"], stats["enqueued"]) == (2, 3)
    queued = sorted(row["key"] for row in queue.execute("SELECT key FROM fetch_state"))
    assert queued == ["fresh.org", "known.com", "rolled.com"]
    assert conn.execute("SELECT count(*) FROM domain_year").fetchone()[0] == 1


def _pool(tmp_path: Path, key: str, *records: str | tuple[str, int], conn=None) -> tuple:
    """Write source `key`'s part from its records, a raw value or (raw, year), then combine."""
    pairs = [(r, 1998) if isinstance(r, str) else r for r in records]
    rows = [BulkRecord(raw=r, year=y, evidence_value=f"{y}0101000000") for r, y in pairs]
    spec = SourceSpec(key, key, "cdx_timestamp", "test", lambda _path, _stats: iter(rows))
    stats = write_source_part(spec, [tmp_path / "input"], parts_dir=tmp_path / "parts")
    return stats, combine_parts(conn, seed_dir=tmp_path / "seeds", parts_dir=tmp_path / "parts")


def test_the_pool_ships_each_in_window_raw_name_beneath_a_domain(tmp_path, his_files) -> None:
    """A raw value that is its domain adds nothing; a URL keeps its commas; the list a crawler
    reads holds a seed once; a rerun replaces only its own source's rows. The pool counts the
    domains his files lack by exact name, and never one ours could not be."""
    url = "http://books.example.co.uk/news/0,6109,393333,00.html"
    early, late = ("a.ex.com", 1995), ("c.ex.com", 2002)
    www = [("www.example.com", 1997), ("www.example.com", 2000)]
    stats, result = _pool(tmp_path, "first", "example.com", early, *www, late, url)
    assert (stats["no_extra_granularity"], stats["seeds"], result["seeds"]) == (1, 3, 2)
    table = f"read_csv_auto('{tmp_path / 'seeds' / 'download_seeds.csv'}')"
    rows = duckdb.connect().execute(f"SELECT seed, domain, year, source FROM {table}").fetchall()
    want = [(url, "example.co.uk", 1998, "first")]
    assert rows == want + [(seed, "example.com", year, "first") for seed, year in www]
    _pool(tmp_path, "second", "b.ex.org")
    _, result = _pool(tmp_path, "first", "c.ex.net")
    assert (tmp_path / "seeds" / "download_seeds.txt").read_text() == "b.ex.org\nc.ex.net\n"
    assert result["parts"] == 2
    empty = combine_parts(seed_dir=tmp_path / "s", parts_dir=tmp_path / "p")
    assert empty == {"parts": 0, "seeds": 0} and not (tmp_path / "s").exists()
    # his 1999 file holds `www.rolled.com`, not `rolled.com`
    (tmp_path / "parts" / "odd.csv").write_text("seed,domain,year\nx.Odd.com,Odd.com,1998\n")
    records = ("www.already-his.com", "www.rolled.com")
    _, result = _pool(tmp_path, "third", *records, conn=duckdb.connect())
    assert (result["domains"], result["domains_not_in_his_files"]) == (5, 3)


def test_the_queue_hands_out_each_name_once_and_recovers_a_crash() -> None:
    queue = wq.connect_queue(":memory:")
    assert wq.enqueue(queue, TASK, ["a.com", "b.com"]) == 2
    assert wq.enqueue(queue, TASK, ["a.com", "c.com"]) == 1
    (done,) = wq.claim(queue, TASK, limit=1)
    assert wq.counts(queue, TASK) == {"pending": 2, "in_flight": 1}
    wq.mark_done(queue, TASK, done)
    wq.enqueue(queue, TASK, [done])  # a finished key cannot be re-enqueued back to pending
    (failed,) = wq.claim(queue, TASK, limit=1)
    wq.mark_failed(queue, TASK, failed, http_status=404)  # final, with no retry time
    assert wq.counts(queue, TASK) == {"pending": 1, "done": 1, "failed": 1}
    # a crash leaves the last claim in flight: the reset returns it, its attempts kept
    (retried,) = wq.claim(queue, TASK)
    assert wq.reset_in_flight(queue) == 1
    assert wq.claim(queue, TASK) == [retried]
    row = "SELECT attempts FROM fetch_state WHERE task_type = ? AND key = ?"
    assert queue.execute(row, (TASK, retried)).fetchone()["attempts"] == 2
    wq.mark_failed(queue, TASK, retried, http_status=429, retry_after_s=3600)
    assert wq.counts(queue, TASK) == {"pending": 1, "done": 1, "failed": 1}
    assert wq.claim(queue, TASK) == [], "pending again, but not before its retry time"
