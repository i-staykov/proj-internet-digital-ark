"""orq.py on a fixture fleet and release: Q1 membership, labels, cost, refusals, a build that
reads neither the store nor private/, and the stage's checks in verify.sh and packaging."""

import csv
import gzip
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from ark.english_share import weight_of

REPO = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("orq", REPO / "scripts/round/orq.py")
orq = sys.modules["orq"] = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(orq)

SHA = "a" * 64
NO_GIT_ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
WHO = ["-c", "user.name=t", "-c", "user.email=t@example.org", "-c", "commit.gpgsign=false"]
# Every file this process opens while a build runs, seen through the interpreter's own audit
# hook so no read path can hide from it. A hook cannot be removed, so it records only while
# the list is armed.
OPENED: list[str] = []
WATCH = [False]


def _record(event, args):
    if event == "open" and WATCH[0] and isinstance(args[0], (str, bytes, os.PathLike)):
        OPENED.append(os.fsdecode(args[0]))


sys.addaudithook(_record)


def finding(run_id="11", years=None, sha=SHA, cmd="uv run ark price-snapshot", status="confirmed"):
    doc = {"run_id": run_id, "verdict": "FIND", "verify": {"status": status} if status else None}
    doc["artifact"] = {"url": "https://example.org/a.txt", "host": "example.org", "sha256": sha}
    doc["extraction"] = {"script": "extract.py", "items": 3, "years": years or {}}
    doc["pricing"] = {"manifest_sha": "b" * 64, "cmd": cmd, "ee": 1.5, "track": "candidate"}
    return doc


def verify(run_id="22", sha=SHA, status="confirmed", ee=1.5):
    doc = {"run_id": run_id, "artifact": {"sha256": sha}, "verify": {"status": status}}
    return doc | {"pricing": {"ee": ee, "manifest_sha": "b" * 64}}


def lead(fleet, slug, lens="pre-1996", wdoi="", sample="", found=None, checked=None, code="x=1"):
    """One lead as the fleet lays it out: leads/<slug>.json and leads/<slug>/."""
    folder = fleet / "leads" / slug
    folder.mkdir(parents=True, exist_ok=True)
    doc = {"slug": slug, "lens": lens, "status": "closed", "what_dates_one_item": wdoi}
    doc |= {"sample_record": sample, "artifact": {"url": f"https://example.org/{slug}"}}
    (fleet / "leads" / f"{slug}.json").write_text(json.dumps(doc))
    (folder / "scout.md").write_text(f"scouted {slug}\n")
    if found is not None:
        (folder / "finding.json").write_text(json.dumps(found))
        if code is not None:
            (folder / "extract.py").write_text(code)
    if checked is not None:
        (folder / "verify.json").write_text(json.dumps(checked))


def git(where: Path, *args: str, **env: str) -> None:
    run = ["git", "-C", str(where), *args]
    subprocess.run(run, check=True, capture_output=True, env=NO_GIT_ENV | env)


def bash(script: str, cwd: Path, **env: str) -> subprocess.CompletedProcess:
    env = NO_GIT_ENV | env
    return subprocess.run(["bash", "-c", script], cwd=cwd, capture_output=True, text=True, env=env)


def commit(where: Path, message: str = "fixture", **env: str) -> None:
    git(where, "add", "leads")
    git(where, *WHO, "-c", "core.hooksPath=/dev/null", "commit", "-qm", message, **env)


def test_q1_drops_only_a_lead_whose_every_dated_record_postdates_1995(tmp_path):
    """DDN's years are empty and its editions are stamped `17-May-95`: a literal reading of
    "all postdate 1995" drops it. Only non-empty years all after 1995, with no earlier year
    in the lead's own date texts, leave Q1. A file that does not parse is named."""
    for text, years in (
        ("[01/Jul/1995:00:00:01 -0400] pub/hosts/19930517/HOSTS.TXT", {1995, 1993}),
        ("; 17-May-95 and 23-Jul-92, computer.html 20010124010300", {1995, 1992, 2001}),
        ("417,108 items, 417108 in all", set()),
    ):
        assert orq.text_years(text) == years, text
    fleet = tmp_path / "fleet"
    stamps = "each edition carries one header stamp: 17-May-95, 23-Jul-92"
    lead(fleet, "ddn-like", wdoi=stamps, found=finding(years={}), checked=verify())
    ia = finding(years={"2000": 5, "2001": 3, "1995": 0})
    lead(fleet, "ia-like", wdoi="x.html 20010124010300", sample="20010123203900", found=ia)
    lead(fleet, "rscott-like", wdoi="DOMAIN SUMMARY 13-Aug-95", found=finding(years={"1996": 4}))
    later = finding(years={"1996": 1, "2001": 9})
    lead(fleet, "usenet-like", wdoi="a Date: header of 1995 or later", found=later)
    lead(fleet, "scout-only")
    lead(fleet, "another-lens", lens="custodian-capture-indexes")
    (fleet / "leads/_dealer").mkdir()
    (fleet / "leads/torn.json").write_text('{"slug": "torn", "lens": "pre-')
    orq.BROKEN.clear()
    tests, excluded, seen = orq.q1(fleet)
    assert (excluded, seen) == (["ia-like"], 5)
    assert [t.id for t in tests] == ["ddn-like", "rscott-like", "scout-only", "usenet-like"]
    assert tests[0].runs == [("price", "11"), ("verify", "22")]
    assert orq.BROKEN == [str(fleet / "leads/torn.json")]
    # The table counts only the records dated inside the window.
    early = orq.Test("Q1", "early", orq.VALIDATED, [], [], finding=finding(years={"1995": 5}))
    late = orq.Test("Q1", "late", orq.TESTED, [], [], finding=finding(years={"1996": 3, "2002": 1}))
    _, _, first, second = orq.q1_table([early, late]).splitlines()
    assert first.startswith("| `early` | Validated | FIND | 3 | 0 | 1.5 | candidate |")
    assert second.startswith("| `late` | Tested, not independently verified | FIND | 3 | 3 |")


def test_labels_are_computed_from_the_record(tmp_path):
    fleet = tmp_path / "fleet"
    lead(fleet, "validated", found=finding(), checked=verify())
    lead(fleet, "scouted")
    tested = (
        ("broken-code", finding(), verify(), "def f(:\n", "extract.py does not compile"),
        ("kept-as-txt", finding(), verify(), None, "kept as extract.py.txt"),
        ("no-verify", finding(status=None), None, "", "no verify"),
        ("verify-pending", finding(status=None), verify(status="pending"), "", "verify pending"),
        ("other-bytes", finding(), verify(sha="c" * 64), "", "different bytes"),
        ("no-sha", finding(sha=None), verify(sha=None), "", "no artifact sha256"),
        ("no-command", finding(cmd=" "), verify(), "", "no pricing command"),
        ("verify-no-bytes", finding(), verify(sha=None), "", "recorded no bytes of its own"),
        ("verify-other-figure", finding(), verify(ee=1.6), "", "printed a different figure"),
        ("copied-opinion-only", finding(), None, "", "recorded no bytes of its own"),
    )
    for slug, found, checked, code, _ in tested:
        lead(fleet, slug, found=found, checked=checked, code="x=1" if code == "" else code)
    (fleet / "leads/kept-as-txt/extract.py.txt").write_text("def f(:\n")
    got = {t.id: (t.label, t.gaps) for t in orq.q1(fleet)[0]}
    assert got["validated"] == (orq.VALIDATED, [])
    scouted = ["closed at the scout leg, before any extractor ran: closed"]
    assert got["scouted"] == (orq.PENDING, scouted)
    for slug, *_, gap in tested:
        label, gaps = got[slug]
        assert label == orq.TESTED and any(gap in g for g in gaps), (slug, gaps)
    # compile() and never py_compile: nothing is written into the fleet checkout
    assert not list(fleet.rglob("__pycache__"))


def test_cost_is_the_ledgers_and_a_run_it_does_not_hold_is_not_recorded(tmp_path):
    """Slots collect out of order, so the seven-day move is the fleet reader's `points`, never
    the stored one, and each experiment record keeps its own label, command and result."""
    fleet = tmp_path / "fleet"
    (fleet / "ledger").mkdir(parents=True)
    lines = [
        {"kind": "leg", "run_id": "11", "slug": "a", "tokens_in_plus_out": 1200},
        {"kind": "read", "run_id": "12", "slug": "a", "tokens_in_plus_out": 0},
        {"kind": "leg", "run_id": "13", "slug": "b", "tokens_in_plus_out": 7},
        {"kind": "legacy", "row": 1, "line": "x", "run_id": "14"},
    ]
    lines[0] |= {"duration_s": 300, "seven_day_delta": 0.5}
    lines[1] |= {"started": "2026-09-25T10:00:00Z", "ended": "2026-09-25T10:02:30Z"}
    body = "".join(json.dumps(line) + "\n" for line in lines) + "not json\n"
    (fleet / "ledger/2026-09.jsonl").write_text(body)
    orq.BROKEN.clear()
    held = orq.ledger(fleet)
    assert orq.BROKEN == [f"{fleet / 'ledger/2026-09.jsonl'}:5"]  # named, never skipped
    gone = (orq.NOT_RECORDED,) * 3
    assert orq.cost(held, "11", "a") == ("1200", "300", "0.5")
    assert orq.cost(held, "12", "a") == ("0", "150", "none")
    for run_id in ("13", "14", "99"):  # another lead's line, a legacy line, no line
        assert orq.cost(held, run_id, "a") == gone, run_id
    assert orq.ledger(tmp_path / "before-the-ledger") == {}
    test = orq.Test("Q1", "a", orq.VALIDATED, [], [("price", "11"), ("verify", "99")])
    rows = [(r["run_id"], r["tokens_in_plus_out"]) for r in orq.tests_rows([test], held)]
    assert rows == [("11", "1200"), ("99", orq.NOT_RECORDED)]
    (fleet / "scripts").mkdir()
    (fleet / "scripts/ledger.py").write_text(
        "def read(root):\n    return ['every line']\n\n\n"
        "def points(lines):\n    assert lines == ['every line']\n    return {'11': 3.0}\n"
    )
    assert orq.cost(orq.ledger(fleet), "11", "a")[2] == "3"
    folder = fleet / "experiments/year-pair-continuity"
    folder.mkdir(parents=True)
    base = {"method": "year-pair-continuity", "question": "q", "output_sha256": SHA}
    for run_id, label in (("41", orq.PENDING), ("42", orq.VALIDATED)):
        record = {"run_id": run_id, "command": f"echo {run_id}", "result": run_id, "label": label}
        (folder / f"{run_id}.json").write_text(json.dumps(base | record))
    assert [(t.runs, t.label, t.command, t.result) for t in orq.experiments(fleet)] == [
        ([("experiment", "41")], orq.PENDING, "echo 41", "41"),
        ([("experiment", "42")], orq.VALIDATED, "echo 42", "42"),
    ]


def test_reads_refuse_private_and_the_store_as_do_text_and_folders(tmp_path, monkeypatch):
    reads = [orq.REPO / "private/a.md", orq.OWNER / "private/a.md", orq.REPO / "data/ark.duckdb"]
    for path in [*reads, orq.REPO / "data/ark.duckdb.wal"]:
        with pytest.raises(orq.Refusal):
            orq.read_bytes(path)
    for text in ("see private/handoff.md", "a traceback in /" + "Users/someone/notes.txt"):
        with pytest.raises(orq.Refusal):
            orq.clean(text, "fixture")
    assert orq.clean("site.com/home/whats-new/", "fixture")
    # An existing, tracked round folder: were the guard gone, a stage there would be accepted.
    for stage, preview, where in (
        (orq.REPO / "submissions/phase-10", None, "under submissions/"),
        (None, orq.REPO / "submissions/x", "under submissions/"),
        (None, orq.REPO / "output/orq", "under output/"),
        (tmp_path / "no-such-stage", None, "no stage at"),
    ):
        with pytest.raises(orq.Refusal, match=where):
            orq.target(stage, preview)
    (stage := tmp_path / "stage").mkdir()
    assert orq.target(stage, None) == stage.resolve()
    assert orq.target(None, tmp_path / "a/preview").is_dir()
    # A stray variable in a shell never moves a build; a build hands its own over.
    monkeypatch.setenv("HIS", "/nowhere/his")
    assert orq.inputs()["HIS"] != "/nowhere/his" and orq.inputs(True)["HIS"] == "/nowhere/his"


TEMPLATE, BRIEF = orq.TEMPLATE.read_text(), orq.BRIEF.read_text()


@pytest.mark.parametrize(
    "refused",
    [
        lambda: orq.check_template(TEMPLATE + "12 of them\n", BRIEF),
        lambda: orq.check_template(TEMPLATE.replace(f"### {orq.HEADINGS[0]}\n", "### X\n"), BRIEF),
        lambda: orq.check_template(TEMPLATE.replace("## Q1. ", "## Q1. Not ", 1), BRIEF),
        lambda: orq.fill("[FIRST] and [SECOND]", {"FIRST": "x"}),
    ],
    ids=["a-typed-figure", "a-heading-off-section-x", "a-question-not-his", "an-unfilled-token"],
)
def test_a_build_refuses_what_would_ship_unchecked(refused):
    """build() runs both on every build; the shipped template passes, and a value is never
    read as a token."""
    orq.check_template(TEMPLATE, BRIEF)
    assert orq.fill("[FIRST]", {"FIRST": "a [SECOND]", "SECOND": "b"}) == "a [SECOND]"
    with pytest.raises(orq.Refusal):
        refused()


def fixture_audit(path: Path) -> Path:
    families = {"a": {"rows": {"2xx": 90, "4xx": 8, "5xx": 2}}, "b": {"rows": {"2xx": 100}}}
    shipped = {"s": {"rows": 10, "ok": 7, "retract": 1, "repoint": 2}}
    path.write_text(json.dumps({"families": families, "shipped": shipped}))
    return path


def fixture_cdx(cdx: Path, his: Path) -> None:
    """One year-fill lane in two shards: a host he holds, one he does not, one a year early."""
    cdx.mkdir(parents=True, exist_ok=True)
    shards = {
        "060000Z_0001": [("held.com", "www.held.com", "2001"), ("new.org", "new.org", "2001")]
    }
    shards["080000Z_0002"] = [("old.net", "old.net", "2000")]
    for shard, rows in shards.items():
        with gzip.open(cdx / f"cdx_yearfill_a_20260923T{shard}.jsonl.gz", "wt") as handle:
            for domain, host, year in rows:
                row = {"domain": domain, "status": 200, "hosts": {host: f"{year}0101000000"}}
                handle.write(json.dumps(row) + "\n")
    (his / "2001.txt").write_text("held.com\nwww.held.com\n")


def test_every_q2_command_has_a_parser_and_is_read_again_from_its_files(tmp_path):
    rows = orq.q2_rows(orq.TEMPLATE.read_text())
    assert {row.id for row in rows if row.command} == set(orq.PARSERS)
    for row in rows:
        assert re.fullmatch(r"\S+:\d+", orq.resolve_anchor(row.anchor)), row.anchor
    with pytest.raises(orq.Refusal):
        orq.resolve_anchor("docs/lore/laws.md#a phrase no law holds")
    with pytest.raises(orq.Refusal):
        orq.q2_rows("| `q2-x` | `a | b` | `f#p` | [T] |\n")
    # A process substitution hides a missing input, so it is caught first.
    (his := tmp_path / "his").mkdir()
    (his / "1999.txt").write_text("a\n")
    names = {"HIS": str(his), "NETNEW": "", "CDX": "", "AUDIT": ""}
    command = 'wc -l < <(LC_ALL=C comm -12 "$HIS/1999.txt" "$HIS/2000.txt")'
    assert orq.missing_inputs(command, names) == ["$HIS/2000.txt"]
    assert orq.missing_inputs('sort -m "$HIS"/199[6-9].txt', names) == []
    assert orq.missing_inputs('sort -m "$HIS"/200[01].txt', names) == ["$HIS/200[01].txt"]
    assert orq._overlap("       0\n")[0] == {"COUNT": "0"}
    assert orq._continuity("  7699146\n 17443336\n")[0]["PCT"] == "44.1"
    audit = fixture_audit(tmp_path / "audit.json")
    values, result = orq._status_share(orq.measure_status_share({"AUDIT": str(audit)}))
    assert (values["FOURXX_PCT"], values["FIVEXX_PCT"]) == ("4.00", "1.00")
    assert (values["SHIPPED"], values["RETRACT"], values["REPOINT"]) == ("10", "1", "2")
    assert "a 8.00%, b 0.00%" in result
    fixture_cdx(tmp_path / "cdx", his)
    out = orq.measure_yearfill_kill({"CDX": str(tmp_path / "cdx"), "HIS": str(his)})
    values, _ = orq._yearfill(out)
    ee = weight_of("new.org")
    counts = (values["NAMES"], values["HOSTS"], values["HELD"], values["NOT_HIS"])
    assert counts == ("3", "2", "1", "1") and "host\ta\tnew.org\t" in out
    assert values["EE"] == f"{ee:,.4f}" and values["RATE"] == f"{ee / Decimal(2):.2f}"
    assert values["FLOOR"] == f"{orq.kill_floor():,}"  # read from the register row
    (tmp_path / "cdx/cdx_yearfill_a_20260923T080000Z_0002.jsonl.gz").unlink()
    with pytest.raises(orq.Refusal, match="one shard"):
        orq.measure_yearfill_kill({"CDX": str(tmp_path / "cdx"), "HIS": str(his)})


def fixture_release(root: Path) -> dict[str, str]:
    (his := root / "his").mkdir()
    (netnew := root / "netnew").mkdir()
    annual = {1996: "a.com", 1997: "a.com", 1998: "b.com", 1999: "b.com\nc.com", 2000: "b.com"}
    for year, names in annual.items():
        (his / f"{year}.txt").write_text(names + "\n")
    (his / "candidate_pool.txt").write_text("z.com\n")
    (netnew / "candidate_additions.txt").write_text("y.com\n")
    fixture_cdx(root / "cdx", his)
    audit = fixture_audit(root / "audit.json")
    return {"HIS": str(his), "NETNEW": str(netnew), "CDX": str(root / "cdx"), "AUDIT": str(audit)}


@pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc writes the docx and the .txt")
def test_a_build_writes_both_folders_and_reads_neither_the_store_nor_private(tmp_path, monkeypatch):
    fleet = tmp_path / "fleet"
    ddn = {"wdoi": "17-May-95", "sample": "HOST : x.mil :", "found": finding(), "checked": verify()}
    lead(fleet, "ddn-like", **ddn)
    ia = finding(run_id="31", years={"2001": 3})
    lead(fleet, "ia-like", wdoi="20010124010300", found=ia, checked=verify(run_id="32"))
    lead(fleet, "scout-only")
    (fleet / "ledger").mkdir()
    line = {"kind": "leg", "run_id": "11", "slug": "ddn-like", "tokens_in_plus_out": 1200}
    (fleet / "ledger/2026-09.jsonl").write_text(json.dumps(line) + "\n")
    variables = fixture_release(tmp_path)
    monkeypatch.setattr(duckdb, "connect", lambda *a, **k: pytest.fail("the build opened a store"))
    real_run = orq._run

    def run(command, env):
        # A `--measure` row runs in this process, so the store trap and the audit hook see it.
        if "--measure" in command:
            measure = re.search(r"--measure (\S+)", command)[1]
            return orq.Run(command, 0, orq.MEASURES[measure](env), "", 0.0)
        return real_run(command, env)

    monkeypatch.setattr(orq, "_run", run)
    (out := tmp_path / "out").mkdir()
    OPENED.clear()
    WATCH[0] = True
    try:
        done = orq.build(out, fleet, variables)
    finally:
        WATCH[0] = False
    assert done["excluded"] == ["ia-like"]
    en = out / orq.EN
    assert sorted(p.name for p in out.iterdir()) == sorted([orq.EN, orq.ZH])
    with (en / "tests.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["label"] for row in rows} <= set(orq.LABELS)
    assert not any(row["id"] == "ia-like" for row in rows)
    ddn = {row["leg"]: row for row in rows if row["id"] == "ddn-like"}
    assert (ddn["price"]["label"], ddn["price"]["tokens_in_plus_out"]) == (orq.VALIDATED, "1200")
    assert ddn["verify"]["tokens_in_plus_out"] == orq.NOT_RECORDED
    for row in rows:
        for column in ("evidence", "code", "logs", "sample"):
            assert not row[column] or (en / row[column]).exists(), (row["id"], column)
    assert (en / "code/ddn-like/extract.py").read_text() == "x=1"
    for name in (orq.TXT["Q1"], orq.TXT["Q2"]):
        lines = {line.strip() for line in (out / orq.ZH / name).read_text().splitlines()}
        assert set(orq.HEADINGS) <= lines, name
    assert (out / orq.ZH / orq.README).read_text().strip()
    with zipfile.ZipFile(en / orq.DOCX) as docx:
        text = re.sub(r"<[^>]+>", "", docx.read("word/document.xml").decode("utf-8"))
    assert "1 of 2 names (50.0%)" in text  # his 1999 against his 2000, from the fixture
    opened = [Path(p).resolve() for p in OPENED]
    assert (fleet / "leads/ddn-like/finding.json").resolve() in opened  # the hook sees reads
    assert (tmp_path / "audit.json").resolve() in opened  # and the measures' reads
    assert not any(p.name.startswith("ark.duckdb") for p in opened)
    forbidden = [root.resolve() for root in orq.FORBIDDEN]
    assert not any(root == p or root in p.parents for p in opened for root in forbidden)
    (fleet / "leads/torn.json").write_text("{")
    with pytest.raises(orq.Refusal, match="not one JSON object: leads/torn.json"):
        orq.build(out, fleet, variables)
    (fleet / "leads/torn.json").unlink()
    (Path(variables["HIS"]) / "2000.txt").unlink()
    with pytest.raises(orq.Refusal, match="2000.txt"):
        orq.build(out, fleet, variables)
    assert (en / orq.DOCX).is_file()  # a refused build leaves the last one standing


def block(script: str, start: str, end: str, prefix: str = "set -euo pipefail\n") -> str:
    """One marked block of a round script, to run alone: the whole script needs a release."""
    text = (REPO / "scripts/round" / script).read_text(encoding="utf-8")
    return prefix + start + text.split(start, 1)[1].split(end, 1)[0]


def fixture_stage(root: Path) -> Path:
    """The two folders as orq.py lays them out, by hand, so E1 runs without pandoc."""
    en, zh = root / orq.EN, root / orq.ZH
    (en / "evidence/a-lead").mkdir(parents=True)
    (en / "evidence/a-lead/scout.md").write_text("scouted\n")
    zh.mkdir()
    parts = orq.split(orq.TEMPLATE.read_text(encoding="utf-8"))
    q1, q2 = (parts[q].splitlines()[0].split(". ", 1)[1].strip() for q in ("Q1", "Q2"))
    half = len(q1) // 2  # the first question split across two runs, as Word splits a heading
    xml = f"<w:p><w:r><w:t>{q1[:half]}</w:t></w:r><w:r><w:t>{q1[half:]}</w:t></w:r></w:p>"
    xml += f"<w:p><w:r><w:t>{q2}</w:t></w:r></w:p>"
    docx(en / orq.DOCX, f"<w:document><w:body>{xml}</w:body></w:document>")
    rows = [
        {"question": "Q1", "id": "a-lead", "label": orq.VALIDATED, "evidence": "evidence/a-lead/"},
        {"question": "Q2", "id": "q2-x", "label": orq.PENDING},
    ]
    with (en / "tests.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=orq.TESTS_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    for name in (orq.TXT["Q1"], orq.TXT["Q2"]):
        (zh / name).write_text("\n\n".join(("Q", *orq.HEADINGS)) + "\n", encoding="utf-8")
    (zh / orq.README).write_text("the folders\n", encoding="utf-8")
    return root


def docx(path: Path, xml: str) -> None:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", xml)


def test_e1_passes_both_folders_and_fails_on_any_one_gap(tmp_path):
    """The stage is built from orq.py's own constants, which verify.sh carries literally."""
    # verify.sh sets `fail` from the block and exits with it, so the block runs the same way
    e1 = block("verify_delivery.sh", "# --- 9 (E1)", "\nPY\n", prefix="fail=0\n")
    e1 += '\nPY\nexit "$fail"\n'
    done = bash(e1, fixture_stage(tmp_path / "good"))
    assert done.returncode == 0, done.stdout + done.stderr
    en, zh, labels = Path(orq.EN), Path(orq.ZH), "question,id,label\nQ1,a,Fine\n"
    breaks = {
        "folder gone": lambda s: shutil.rmtree(s / zh),
        "other folder gone": lambda s: shutil.rmtree(s / en),
        "docx unreadable": lambda s: (s / en / orq.DOCX).write_bytes(b"not a zip"),
        "question missing": lambda s: docx(s / en / orq.DOCX, "<w:p><w:t>A title</w:t></w:p>"),
        "one heading short": lambda s: (s / zh / orq.TXT["Q2"]).write_text("Limitations\n"),
        "a fourth label": lambda s: (s / en / "tests.csv").write_text(labels),
        "a named file gone": lambda s: shutil.rmtree(s / en / "evidence"),
        "private text": lambda s: (s / zh / orq.README).write_text("see private/notes\n"),
        "a link": lambda s: (s / zh / "linked.txt").symlink_to(s / zh / orq.README),
    }
    for name, broken in breaks.items():
        broken(stage := fixture_stage(tmp_path / name.replace(" ", "-")))
        done = bash(e1, stage)
        assert done.returncode == 1 and " FAIL " in done.stdout, (name, done.stdout)


def test_a_stale_or_dirty_fleet_is_refused(tmp_path):
    guard = block("package_delivery.sh", "# The fleet checkout ships", "# The reproduction note")
    repo, fleet, linked = tmp_path / "repo", tmp_path / "fleet", tmp_path / "linked"
    (repo / "data/fleet_findings/banked/20260923T1006Z").mkdir(parents=True)
    (repo / "data/fleet_findings/banked/20260904T1544Z_dups").mkdir()
    (fleet / "leads").mkdir(parents=True)
    (fleet / "leads/a.json").write_text("{}")
    fresh = "2026-09-24T22:08:15Z"
    git(fleet, "init", "-q")
    commit(fleet, GIT_COMMITTER_DATE=fresh, GIT_AUTHOR_DATE=fresh)
    git(fleet, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(fleet, "worktree", "add", "-q", "--detach", str(linked))
    (plain := tmp_path / "plain").mkdir()
    for checkout in (fleet, linked):
        assert bash(guard, repo, ARK_FLEET=str(checkout)).returncode == 0, checkout
    # a branch commit on top of main, as a fleet worktree on an unmerged branch holds
    (linked / "leads/b.json").write_text("{}")
    commit(linked, "b")
    # the same fleet committed again before the newest banked drain
    stale = "2026-09-09T22:34:17Z"
    amend = [*WHO, "-c", "core.hooksPath=/dev/null", "commit", "-q", "--amend", "--no-edit"]
    git(fleet, *amend, GIT_COMMITTER_DATE=stale, GIT_AUTHOR_DATE=stale)
    git(fleet, "update-ref", "refs/remotes/origin/main", "HEAD")
    for checkout, why in (
        (plain, "not the top of a fleet checkout"),
        (fleet / "leads", "not the top of a fleet checkout"),
        (linked, "is not on the fleet's origin/main"),
        (fleet, "committed 20260909T2234Z, before the newest banked drain 20260923T1006Z"),
    ):
        done = bash(guard, repo, ARK_FLEET=str(checkout))
        assert done.returncode == 1 and why in done.stderr, (checkout, done.stderr)
    shutil.rmtree(repo / "data")  # no banked drain at all: nothing to be older than
    assert bash(guard, repo, ARK_FLEET=str(fleet)).returncode == 0
    # orq builds from the commit, so changes under what it reads are refused too.
    assert re.fullmatch(r"[0-9a-f]{40}", orq.fleet_head(fleet))
    assert orq.fleet_head(plain) == orq.fleet_head(fleet / "leads") == "", "not a checkout's top"
    (fleet / "leads/a.json").write_text("[]")
    with pytest.raises(orq.Refusal, match="uncommitted"):
        orq.fleet_head(fleet)


def test_packaging_refuses_a_note_naming_another_verdict_count_than_verify_declares(tmp_path):
    text = (REPO / "scripts/round/verify_delivery.sh").read_text(encoding="utf-8")
    said = "|".join(
        (r'\bsay\(?\s*"([^"]+)"', r"print\(f\"\{'([^']+)':<46\}", r'^LABEL = "([^"]+)"')
    )
    labels = {label for found in re.findall(said, text, re.M) for label in found if label}
    assert "verify_isc_candidates.py" in text  # it prints the ISC verdict itself
    declared = int(re.search(r"^VERDICTS=(\d+)$", text, re.M)[1])
    assert len(labels | {"ISC candidates"}) == declared, sorted(labels)
    check = block("package_delivery.sh", "# The reproduction note is quoted", "# The export stamp")
    (tmp_path / "scripts/round").mkdir(parents=True)
    (tmp_path / "docs/round").mkdir(parents=True)
    (tmp_path / "scripts/round/verify_delivery.sh").write_text("fail=0\nVERDICTS=14\n")
    for said, code in (
        ("all thirteen `verify.sh` verdicts pass", 1),
        ("all fourteen `verify.sh` verdicts pass", 0),
        ("every `verify.sh` verdict passes", 0),
    ):
        (tmp_path / "docs/round/reproduction.txt").write_text(f"Before sending, {said}.\n")
        assert bash(check, tmp_path).returncode == code, said
    # the shipped note names no count, so a new verdict can never leave it stale
    assert "`verify.sh` verdicts" not in (REPO / "docs/round/reproduction.txt").read_text()
