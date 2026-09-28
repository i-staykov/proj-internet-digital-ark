"""orq.py on a fixture fleet and a fixture release: labels, Q1 membership, cost, refusals,
the template's own checks, and a whole build that reads neither the store nor private/.

Loaded by path, like the other script tests: `scripts/` is not a package.
"""

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

import pytest

from ark.english_share import weight_of

REPO = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("orq", REPO / "scripts/round/orq.py")
orq = importlib.util.module_from_spec(_SPEC)
# Registered before exec: the dataclasses read their own module back for its annotations.
sys.modules["orq"] = orq
_SPEC.loader.exec_module(orq)

SHA = "a" * 64
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
    return {
        "run_id": run_id,
        "artifact": {"url": "https://example.org/a.txt", "host": "example.org", "sha256": sha},
        "extraction": {"script": "extract.py", "items": 3, "years": years or {}},
        "pricing": {
            "snapshot_marker": "merged260922",
            "manifest_sha": "b" * 64,
            "cmd": cmd,
            "ee": 1.5,
            "track": "candidate",
        },
        "verdict": "FIND",
        "verify": {"status": status} if status else None,
    }


def verify(run_id="22", sha=SHA, status="confirmed", ee=1.5):
    return {
        "run_id": run_id,
        "artifact": {"sha256": sha},
        "pricing": {"ee": ee, "manifest_sha": "b" * 64},
        "verify": {"status": status},
    }


def lead(
    fleet, slug, lens="pre-1996", wdoi="", sample="", found=None, checked=None, code="x = 1\n"
):
    """One lead as the fleet lays it out: leads/<slug>.json and leads/<slug>/."""
    folder = fleet / "leads" / slug
    folder.mkdir(parents=True, exist_ok=True)
    doc = {
        "slug": slug,
        "lens": lens,
        "status": "closed",
        "what_dates_one_item": wdoi,
        "sample_record": sample,
        "artifact": {"url": f"https://example.org/{slug}", "host": "example.org"},
    }
    (fleet / "leads" / f"{slug}.json").write_text(json.dumps(doc))
    (folder / "scout.md").write_text(f"scouted {slug}\n")
    if found is not None:
        (folder / "finding.json").write_text(json.dumps(found))
        if code is not None:
            (folder / "extract.py").write_text(code)
    if checked is not None:
        (folder / "verify.json").write_text(json.dumps(checked))


def test_text_years_reads_every_shape_the_leads_use():
    assert orq.text_years("[01/Jul/1995:00:00:01 -0400]") == {1995}
    assert orq.text_years("; 17-May-95 and 23-Jul-92") == {1995, 1992}
    assert orq.text_years("pub/hosts/19950517/HOSTS.TXT") == {1995}
    assert orq.text_years("computer.html 20010124010300 http://x") == {2001}
    assert orq.text_years("417,108 items, 417108 in all") == set()


def test_q1_drops_only_a_lead_whose_every_dated_record_postdates_1995(tmp_path):
    """DDN's years are empty and its editions are stamped `17-May-95`: a literal reading of
    "all postdate 1995" drops it. Only non-empty years all after 1995, with no earlier year
    in the lead's own date texts, leave Q1."""
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
    (fleet / "leads" / "_dealer").mkdir()

    tests, excluded, seen = orq.q1(fleet)

    assert excluded == ["ia-like"]
    assert seen == 5
    assert [t.id for t in tests] == ["ddn-like", "rscott-like", "scout-only", "usenet-like"]
    assert tests[0].runs == [("price", "11"), ("verify", "22")]


def test_labels_are_computed_from_the_record(tmp_path):
    fleet = tmp_path / "fleet"
    lead(fleet, "validated", found=finding(), checked=verify())
    lead(fleet, "broken-code", found=finding(), checked=verify(), code="def f(:\n")
    lead(fleet, "kept-as-txt", found=finding(), checked=verify(), code=None)
    (fleet / "leads/kept-as-txt/extract.py.txt").write_text("def f(:\n")
    lead(fleet, "no-verify", found=finding(status=None))
    lead(fleet, "verify-pending", found=finding(status=None), checked=verify(status="pending"))
    lead(fleet, "other-bytes", found=finding(), checked=verify(sha="c" * 64))
    lead(fleet, "no-sha", found=finding(sha=None), checked=verify(sha=None))
    lead(fleet, "no-command", found=finding(cmd=" "), checked=verify())
    lead(fleet, "verify-no-bytes", found=finding(), checked=verify(sha=None))
    lead(fleet, "verify-other-figure", found=finding(), checked=verify(ee=1.6))
    lead(fleet, "copied-opinion-only", found=finding())
    lead(fleet, "scouted")

    got = {t.id: (t.label, t.gaps) for t in orq.q1(fleet)[0]}

    assert got["validated"] == (orq.VALIDATED, [])
    assert got["scouted"] == (
        orq.PENDING,
        ["closed at the scout leg, before any extractor ran: closed"],
    )
    expect = {
        "broken-code": "extract.py does not compile",
        "kept-as-txt": "kept as extract.py.txt",
        "no-verify": "no verify",
        "verify-pending": "verify pending",
        "other-bytes": "different bytes",
        "no-sha": "no artifact sha256",
        "no-command": "no pricing command",
        "verify-no-bytes": "recorded no bytes of its own",
        "verify-other-figure": "printed a different figure",
        "copied-opinion-only": "recorded no bytes of its own",
    }
    for slug, gap in expect.items():
        label, gaps = got[slug]
        assert label == orq.TESTED and any(gap in g for g in gaps), (slug, gaps)
    # compile() and never py_compile: nothing is written into the fleet checkout
    assert not list(fleet.rglob("__pycache__"))


def test_cost_is_the_ledgers_and_a_run_it_does_not_hold_is_not_recorded(tmp_path):
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
    assert orq.cost(held, "13", "a") == gone  # another lead's line
    assert orq.cost(held, "14", "a") == gone  # a legacy line costs no run
    assert orq.cost(held, "99", "a") == gone
    assert orq.ledger(tmp_path / "before-the-ledger") == {}

    test = orq.Test("Q1", "a", orq.VALIDATED, [], [("price", "11"), ("verify", "99")])
    rows = orq.tests_rows([test], held)
    assert [(r["run_id"], r["tokens_in_plus_out"]) for r in rows] == [
        ("11", "1200"),
        ("99", orq.NOT_RECORDED),
    ]


def test_seven_day_points_are_the_fleet_readers_not_the_stored_move(tmp_path):
    """Slots collect out of order, so a stored move can reach back past an earlier leg: the
    fleet's own `points` takes the move again over the whole ledger."""
    fleet = tmp_path / "fleet"
    (fleet / "ledger").mkdir(parents=True)
    (fleet / "scripts").mkdir()
    (fleet / "scripts/ledger.py").write_text(
        "def read(root):\n    return ['every line']\n\n\n"
        "def points(lines):\n    assert lines == ['every line']\n    return {'11': 3.0}\n"
    )
    line = {"kind": "leg", "run_id": "11", "slug": "a", "seven_day_delta": 5.0}
    (fleet / "ledger/2026-09.jsonl").write_text(json.dumps(line) + "\n")
    assert orq.cost(orq.ledger(fleet), "11", "a")[2] == "3"


def test_each_experiment_record_keeps_its_own_label_command_and_result(tmp_path):
    fleet = tmp_path / "fleet"
    folder = fleet / "experiments" / "year-pair-continuity"
    folder.mkdir(parents=True)
    base = {"method": "year-pair-continuity", "question": "q", "output_sha256": SHA}
    first = {"run_id": "41", "command": "echo a", "result": "first", "label": orq.PENDING}
    second = {"run_id": "42", "command": "echo b", "result": "second", "label": orq.VALIDATED}
    (folder / "41.json").write_text(json.dumps(base | first))
    (folder / "42.json").write_text(json.dumps(base | second))

    got = [(t.runs, t.label, t.command, t.result) for t in orq.experiments(fleet)]

    assert got == [
        ([("experiment", "41")], orq.PENDING, "echo a", "first"),
        ([("experiment", "42")], orq.VALIDATED, "echo b", "second"),
    ]
    assert orq.experiments(tmp_path / "no-experiments") == []


def test_the_q1_table_counts_the_records_dated_inside_the_window():
    early = orq.Test("Q1", "early", orq.VALIDATED, [], [], finding=finding(years={"1995": 5}))
    late = orq.Test("Q1", "late", orq.TESTED, [], [], finding=finding(years={"1996": 3, "2002": 1}))
    header, _, first, second = orq.q1_table([early, late]).splitlines()
    assert "| dated 1996 to 2001 |" in header
    assert first.startswith("| `early` | Validated | FIND | 3 | 0 | 1.5 | candidate |")
    assert second.startswith("| `late` | Tested, not independently verified | FIND | 3 | 3 |")


def test_a_fleet_with_changes_under_what_is_read_is_refused(tmp_path):
    fleet = tmp_path / "fleet"
    lead(fleet, "a-lead")

    # The hook runs this suite with GIT_DIR and GIT_INDEX_FILE naming the repository being
    # committed; left in, `git init` here would rewrite that repository.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

    def git(*args):
        subprocess.run(["git", "-C", str(fleet), *args], check=True, capture_output=True, env=env)

    git("init", "-q")
    git("add", "leads")
    who = ["-c", "user.name=t", "-c", "user.email=t@example.org", "-c", "commit.gpgsign=false"]
    git(*who, "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "fixture")

    assert re.fullmatch(r"[0-9a-f]{40}", orq.fleet_head(fleet))
    assert orq.fleet_head(fleet / "leads") == ""  # not the top of a checkout
    (fleet / "leads/a-lead.json").write_text("{}")
    with pytest.raises(orq.Refusal, match="uncommitted"):
        orq.fleet_head(fleet)


def test_a_fleet_file_that_does_not_parse_is_named_never_skipped(tmp_path):
    fleet = tmp_path / "fleet"
    lead(fleet, "fine")
    (fleet / "leads/torn.json").write_text('{"slug": "torn", "lens": "pre-')
    orq.BROKEN.clear()
    tests, _, _ = orq.q1(fleet)
    assert [t.id for t in tests] == ["fine"]
    assert orq.BROKEN == [str(fleet / "leads/torn.json")]


def test_the_inputs_come_from_the_environment_only_when_asked(monkeypatch):
    monkeypatch.setenv("HIS", "/nowhere/his")
    assert orq.inputs()["HIS"] != "/nowhere/his"
    assert orq.inputs(from_env=True)["HIS"] == "/nowhere/his"


def test_reads_refuse_private_and_the_store():
    for path in (
        orq.REPO / "private" / "anything.md",
        orq.OWNER / "private" / "anything.md",
        orq.REPO / "data" / "ark.duckdb",
        orq.REPO / "data" / "ark.duckdb.wal",
    ):
        with pytest.raises(orq.Refusal):
            orq.read_bytes(path)


def test_the_folders_never_go_under_submissions_and_a_preview_never_under_output(tmp_path):
    # An existing, tracked round folder: were the guard gone, a stage there would be accepted.
    with pytest.raises(orq.Refusal, match="under submissions/"):
        orq.target(orq.REPO / "submissions" / "phase-10", None)
    with pytest.raises(orq.Refusal, match="under submissions/"):
        orq.target(None, orq.REPO / "submissions" / "x")
    with pytest.raises(orq.Refusal, match="under output/"):
        orq.target(None, orq.REPO / "output" / "orq")
    with pytest.raises(orq.Refusal, match="no stage at"):
        orq.target(tmp_path / "no-such-stage", None)
    stage = tmp_path / "stage"
    stage.mkdir()
    assert orq.target(stage, None) == stage.resolve()
    assert orq.target(None, tmp_path / "a" / "preview").is_dir()


def test_copied_text_naming_private_or_a_home_directory_is_refused():
    home = "/" + "Users" + "/someone/notes.txt"
    for text in ("see private/handoff.md", f"a traceback in {home}"):
        with pytest.raises(orq.Refusal):
            orq.clean(text, "fixture")
    assert orq.clean("site.com/home/whats-new/", "fixture")


def test_the_template_types_no_figure_and_asks_his_questions_under_six_headings():
    template, brief = orq.TEMPLATE.read_text(), orq.BRIEF.read_text()
    orq.check_template(template, brief)

    assert orq.stray_digits("## Q1. before 1996\n`1999.txt` and [FIRST_YEAR]\n") == []
    assert orq.stray_digits("fine\nprose with 44.1% in it\n") == [2]
    for broken in (
        template + "\nWe found twelve hosts, 12 of them new.\n",
        template.replace("### Limitations\n", "### Caveats\n", 1),
        template.replace("acquired at scale?", "acquired?", 1),
    ):
        with pytest.raises(orq.Refusal):
            orq.check_template(broken, brief)


def test_an_unfilled_token_is_refused_and_a_value_is_never_read_as_a_token():
    with pytest.raises(orq.Refusal):
        orq.fill("[FIRST] and [SECOND]", {"FIRST": "x"})
    assert orq.fill("[FIRST]", {"FIRST": "a record carrying [SECOND]"}) == (
        "a record carrying [SECOND]"
    )


def test_every_q2_anchor_resolves_and_every_command_has_a_parser():
    rows = orq.q2_rows(orq.TEMPLATE.read_text())
    assert {row.id for row in rows if row.command} == set(orq.PARSERS)
    for row in rows:
        assert re.fullmatch(r"\S+:\d+", orq.resolve_anchor(row.anchor)), row.anchor
    with pytest.raises(orq.Refusal):
        orq.resolve_anchor("docs/lore/laws.md#a phrase no law holds")
    with pytest.raises(orq.Refusal):
        orq.q2_rows("| `q2-x` | `a | b` | `f#p` | [T] |\n")


def test_a_missing_input_is_caught_before_a_process_substitution_hides_it(tmp_path):
    his = tmp_path / "his"
    his.mkdir()
    (his / "1999.txt").write_text("a\n")
    names = {"HIS": str(his), "NETNEW": "", "CDX": "", "AUDIT": ""}
    command = 'wc -l < <(LC_ALL=C comm -12 "$HIS/1999.txt" "$HIS/2000.txt")'
    assert orq.missing_inputs(command, names) == ["$HIS/2000.txt"]
    assert orq.missing_inputs('sort -m "$HIS"/199[6-9].txt', names) == []
    assert orq.missing_inputs('sort -m "$HIS"/200[01].txt', names) == ["$HIS/200[01].txt"]


def test_the_parsers_read_what_the_commands_print():
    values, result = orq._continuity("  7699146\n 17443336\n")
    assert values["PCT"] == "44.1"
    assert result == "7,699,146 of 17,443,336 names (44.1%)"
    assert orq._overlap("       0\n")[0] == {"COUNT": "0"}


def fixture_audit(path: Path) -> Path:
    audit = {
        "families": {
            "a": {"rows": {"2xx": 90, "4xx": 8, "5xx": 2}},
            "b": {"rows": {"2xx": 100}},
        },
        "shipped": {"s": {"rows": 10, "ok": 7, "retract": 1, "repoint": 2}},
    }
    path.write_text(json.dumps(audit))
    return path


def fixture_cdx(cdx: Path, his: Path) -> None:
    """One year-fill lane in two shards stamped two hours apart: three names, a host he
    holds, one he does not, and one captured only the year before."""
    cdx.mkdir(parents=True, exist_ok=True)
    shards = {
        "cdx_yearfill_a_20260923T060000Z_0001.jsonl.gz": [
            {"domain": "held.com", "status": 200, "hosts": {"www.held.com": "20010101000000"}},
            {"domain": "new.org", "status": 200, "hosts": {"new.org": "20010505000000"}},
        ],
        "cdx_yearfill_a_20260923T080000Z_0002.jsonl.gz": [
            {"domain": "old.net", "status": 200, "hosts": {"old.net": "20000101000000"}},
        ],
    }
    for name, rows in shards.items():
        with gzip.open(cdx / name, "wt") as handle:
            handle.write("".join(json.dumps(row) + "\n" for row in rows))
    (his / "2001.txt").write_text("held.com\nwww.held.com\n")


def test_the_status_share_and_the_year_fill_are_read_again_from_their_files(tmp_path):
    values, result = orq._status_share(
        orq.measure_status_share({"AUDIT": str(fixture_audit(tmp_path / "audit.json"))})
    )
    assert values["FOURXX_PCT"] == "4.00" and values["FIVEXX_PCT"] == "1.00"
    assert (values["SHIPPED"], values["RETRACT"], values["REPOINT"]) == ("10", "1", "2")
    assert "a 8.00%, b 0.00%" in result

    his = tmp_path / "his"
    his.mkdir()
    fixture_cdx(tmp_path / "cdx", his)
    out = orq.measure_yearfill_kill({"CDX": str(tmp_path / "cdx"), "HIS": str(his)})
    values, result = orq._yearfill(out)
    ee = weight_of("new.org")
    assert (values["NAMES"], values["HOSTS"], values["HELD"], values["NOT_HIS"]) == (
        "3",
        "2",
        "1",
        "1",
    )
    assert values["EE"] == f"{ee:,.4f}" and values["RATE"] == f"{ee / Decimal(2):.2f}"
    assert values["FLOOR"] == f"{orq.kill_floor():,}"  # read from the register row
    assert "host\ta\tnew.org\t" in out

    (tmp_path / "cdx/cdx_yearfill_a_20260923T080000Z_0002.jsonl.gz").unlink()
    with pytest.raises(orq.Refusal, match="one shard"):
        orq.measure_yearfill_kill({"CDX": str(tmp_path / "cdx"), "HIS": str(his)})


def fixture_release(root: Path) -> dict[str, str]:
    his, netnew = root / "his", root / "netnew"
    his.mkdir()
    netnew.mkdir()
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
    lead(
        fleet,
        "ddn-like",
        wdoi="17-May-95",
        sample="HOST : x.mil :",
        found=finding(),
        checked=verify(),
    )
    ia = finding(run_id="31", years={"2001": 3})
    lead(fleet, "ia-like", wdoi="20010124010300", found=ia, checked=verify(run_id="32"))
    lead(fleet, "scout-only")
    (fleet / "ledger").mkdir()
    line = {"kind": "leg", "run_id": "11", "slug": "ddn-like", "tokens_in_plus_out": 1200}
    (fleet / "ledger/2026-09.jsonl").write_text(json.dumps(line) + "\n")
    variables = fixture_release(tmp_path)
    import duckdb

    monkeypatch.setattr(duckdb, "connect", lambda *a, **k: pytest.fail("the build opened a store"))
    real_run = orq._run

    def run(command, env):
        # A `--measure` row runs in this process, so the store trap and the audit hook see it.
        if "--measure" in command:
            measure = re.search(r"--measure (\S+)", command)[1]
            return orq.Run(command, 0, orq.MEASURES[measure](env), "", 0.0)
        return real_run(command, env)

    monkeypatch.setattr(orq, "_run", run)
    out = tmp_path / "out"
    out.mkdir()
    OPENED.clear()
    WATCH[0] = True
    try:
        done = orq.build(out, fleet, variables)
    finally:
        WATCH[0] = False

    assert done["excluded"] == ["ia-like"]
    en, zh = out / orq.EN, out / orq.ZH
    assert sorted(p.name for p in out.iterdir()) == sorted([orq.EN, orq.ZH])
    with (en / "tests.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["label"] for row in rows} <= set(orq.LABELS)
    assert not any(row["id"] == "ia-like" for row in rows)
    ddn = {row["leg"]: row for row in rows if row["id"] == "ddn-like"}
    assert ddn["price"]["label"] == orq.VALIDATED
    assert ddn["price"]["tokens_in_plus_out"] == "1200"
    assert ddn["verify"]["tokens_in_plus_out"] == orq.NOT_RECORDED
    for row in rows:
        for column in ("evidence", "code", "logs", "sample"):
            assert not row[column] or (en / row[column]).exists(), (row["id"], column)
    assert (en / "code/ddn-like/extract.py").read_text() == "x = 1\n"
    for name in (orq.TXT["Q1"], orq.TXT["Q2"]):
        lines = {line.strip() for line in (zh / name).read_text(encoding="utf-8").splitlines()}
        assert set(orq.HEADINGS) <= lines, name
    assert (zh / orq.README).read_text(encoding="utf-8").strip()
    with zipfile.ZipFile(en / orq.DOCX) as docx:
        xml = docx.read("word/document.xml").decode("utf-8")
    text = re.sub(r"<[^>]+>", "", xml)
    assert "discovered and acquired at scale?" in text and "determined more accurately?" in text
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


# --- the wiring: verify.sh's E1 and package_delivery.sh's fleet guard -------------------

NO_GIT_ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def e1_block() -> str:
    """verify.sh's E1 check, cut out by its own markers: the whole script fails on a stage
    that holds only the two folders, so its exit status alone proves nothing."""
    text = (REPO / "scripts/round/verify_delivery.sh").read_text(encoding="utf-8")
    block = text.split("# --- 9 (E1)", 1)[1]
    return block[block.index("python3 - <<'PY'") : block.index("\nPY\n") + 4]


def fixture_stage(root: Path) -> Path:
    """The two folders as orq.py lays them out, by hand, so E1 runs without pandoc."""
    en, zh = root / orq.EN, root / orq.ZH
    (en / "evidence/a-lead").mkdir(parents=True)
    (en / "evidence/a-lead/scout.md").write_text("scouted\n")
    zh.mkdir()
    q1, q2 = (
        "How can historical web data from before 1996 be discovered and acquired at scale?",
        "How can the year in which a website existed be determined more accurately?",
    )
    # the first question split across two runs, as Word splits a heading
    half = len(q1) // 2
    xml = (
        '<w:document><w:body><w:p><w:r><w:t xml:space="preserve">'
        f"{q1[:half]}</w:t></w:r><w:r><w:t>{q1[half:]}</w:t></w:r></w:p>"
        f"<w:p><w:r><w:t>{q2}</w:t></w:r></w:p></w:body></w:document>"
    )
    with zipfile.ZipFile(en / orq.DOCX, "w") as docx:
        docx.writestr("word/document.xml", xml)
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


def title_only(docx: Path) -> None:
    with zipfile.ZipFile(docx, "w") as z:
        z.writestr("word/document.xml", "<w:p><w:r><w:t>Only a title</w:t></w:r></w:p>")


def run_e1(stage: Path) -> subprocess.CompletedProcess:
    # verify.sh sets `fail` from the block and exits with it, so the block runs the same way
    script = f'fail=0\n{e1_block()}\nexit "$fail"\n'
    return subprocess.run(
        ["bash", "-c", script], cwd=stage, capture_output=True, text=True, env=NO_GIT_ENV
    )


def test_e1_passes_both_folders_and_fails_on_any_one_gap(tmp_path):
    """The verdict names the constants verify.sh must carry literally, since nothing from the
    repository is importable inside an archive: they are orq.py's own."""
    text = e1_block()
    for literal in (*orq.HEADINGS, *orq.LABELS, orq.EN, orq.ZH, orq.DOCX):
        assert literal in text, literal
    parts = orq.split(orq.TEMPLATE.read_text(encoding="utf-8"))
    for question in ("Q1", "Q2"):
        assert parts[question].splitlines()[0].split(". ", 1)[1].strip() in text

    done = run_e1(fixture_stage(tmp_path / "good"))
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.startswith(f"{'E1 open research questions':<46} PASS")
    assert "WARN  no screenshots/" in done.stdout

    breaks = {
        "folder gone": lambda s: shutil.rmtree(s / orq.ZH),
        "other folder gone": lambda s: shutil.rmtree(s / orq.EN),
        "docx unreadable": lambda s: (s / orq.EN / orq.DOCX).write_bytes(b"not a zip"),
        "question missing": lambda s: title_only(s / orq.EN / orq.DOCX),
        "one heading short": lambda s: (s / orq.ZH / orq.TXT["Q2"]).write_text("Limitations\n"),
        "a fourth label": lambda s: (s / orq.EN / "tests.csv").write_text(
            "question,id,label\nQ1,a,Probably fine\n"
        ),
        "a named file gone": lambda s: shutil.rmtree(s / orq.EN / "evidence"),
        "private text": lambda s: (s / orq.ZH / orq.README).write_text("see private/notes\n"),
        "a link": lambda s: (s / orq.ZH / "linked.txt").symlink_to(s / orq.ZH / orq.README),
    }
    for name, broken in breaks.items():
        stage = fixture_stage(tmp_path / name.replace(" ", "-"))
        broken(stage)
        done = run_e1(stage)
        assert done.returncode == 1 and " FAIL " in done.stdout, (name, done.stdout)


def fleet_guard() -> str:
    text = (REPO / "scripts/round/package_delivery.sh").read_text(encoding="utf-8")
    block = text.split("# The fleet checkout ships", 1)[1]
    end = block.index("# The reproduction note is quoted")
    return "set -euo pipefail\n# The fleet checkout ships" + block[:end]


def commit_fleet(fleet: Path, when: str) -> None:
    fleet.mkdir(parents=True)
    (fleet / "leads").mkdir()
    (fleet / "leads/a.json").write_text("{}")
    env = NO_GIT_ENV | {"GIT_COMMITTER_DATE": when, "GIT_AUTHOR_DATE": when}
    who = ["-c", "user.name=t", "-c", "user.email=t@example.org", "-c", "commit.gpgsign=false"]
    for args in (
        ["init", "-q"],
        ["add", "leads"],
        [*who, "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "fixture"],
        ["update-ref", "refs/remotes/origin/main", "HEAD"],
    ):
        subprocess.run(["git", "-C", str(fleet), *args], check=True, capture_output=True, env=env)


def run_guard(cwd: Path, fleet: Path) -> subprocess.CompletedProcess:
    env = NO_GIT_ENV | {"ARK_FLEET": str(fleet)}
    return subprocess.run(
        ["bash", "-c", fleet_guard()], cwd=cwd, capture_output=True, text=True, env=env
    )


def test_packaging_refuses_a_fleet_that_is_not_a_checkout_or_predates_the_newest_drain(
    tmp_path,
):
    repo = tmp_path / "repo"
    (repo / "data/fleet_findings/banked/20260923T1006Z").mkdir(parents=True)
    (repo / "data/fleet_findings/banked/20260904T1544Z_dups").mkdir()
    stale, fresh, ahead = tmp_path / "stale", tmp_path / "fresh", tmp_path / "ahead"
    commit_fleet(stale, "2026-09-09T22:34:17Z")
    commit_fleet(fresh, "2026-09-24T22:08:15Z")
    commit_fleet(ahead, "2026-09-24T22:08:15Z")
    # a branch commit on top of main, as a fleet worktree on an unmerged branch holds
    (ahead / "leads/b.json").write_text("{}")
    who = ["-c", "user.name=t", "-c", "user.email=t@example.org", "-c", "commit.gpgsign=false"]
    for args in (["add", "leads"], [*who, "-c", "core.hooksPath=/dev/null", "commit", "-qm", "b"]):
        subprocess.run(
            ["git", "-C", str(ahead), *args], check=True, capture_output=True, env=NO_GIT_ENV
        )
    (tmp_path / "plain").mkdir()
    worktree = tmp_path / "linked"
    subprocess.run(
        ["git", "-C", str(fresh), "worktree", "add", "-q", "--detach", str(worktree)],
        check=True,
        capture_output=True,
        env=NO_GIT_ENV,
    )

    for fleet, why in (
        (tmp_path / "plain", "not the top of a fleet checkout"),
        (fresh / "leads", "not the top of a fleet checkout"),
        (ahead, "is not on the fleet's origin/main"),
        (stale, "committed 20260909T2234Z, before the newest banked drain 20260923T1006Z"),
    ):
        done = run_guard(repo, fleet)
        assert done.returncode == 1 and why in done.stderr, (fleet, done.stderr)
    for fleet in (fresh, worktree):
        done = run_guard(repo, fleet)
        assert done.returncode == 0, (fleet, done.stderr)
    # no banked drain at all: nothing to be older than
    shutil.rmtree(repo / "data")
    assert run_guard(repo, stale).returncode == 0


def test_verify_declares_the_verdicts_it_prints():
    """Packaging compares the reproduction note's count against this, so it must be true."""
    text = (REPO / "scripts/round/verify_delivery.sh").read_text(encoding="utf-8")
    labels = set(re.findall(r'\bsay\(\s*"([^"]+)"', text))
    labels |= set(re.findall(r'\bsay "([^"]+)"', text))
    labels |= set(re.findall(r"print\(f\"\{'([^']+)':<46\}", text))
    labels |= set(re.findall(r'^LABEL = "([^"]+)"', text, re.M))
    assert "verify_isc_candidates.py" in text  # it prints the ISC verdict itself
    labels.add("ISC candidates")
    declared = int(re.search(r"^VERDICTS=(\d+)$", text, re.M)[1])
    assert len(labels) == declared, sorted(labels)


def count_check() -> str:
    text = (REPO / "scripts/round/package_delivery.sh").read_text(encoding="utf-8")
    block = text.split("# The reproduction note is quoted", 1)[1]
    end = block.index("# The export stamp")
    return "set -euo pipefail\n# The reproduction note is quoted" + block[:end]


def test_packaging_refuses_a_reproduction_note_naming_another_verdict_count(tmp_path):
    (tmp_path / "scripts/round").mkdir(parents=True)
    (tmp_path / "docs/round").mkdir(parents=True)
    (tmp_path / "scripts/round/verify_delivery.sh").write_text("fail=0\nVERDICTS=14\n")
    note = tmp_path / "docs/round/reproduction.txt"
    for said, code in (
        ("all thirteen `verify.sh` verdicts pass", 1),
        ("all fourteen `verify.sh` verdicts pass", 0),
        ("every `verify.sh` verdict passes", 0),
    ):
        note.write_text(f"Before sending, {said} (26 seconds).\n")
        done = subprocess.run(
            ["bash", "-c", count_check()], cwd=tmp_path, capture_output=True, text=True
        )
        assert done.returncode == code, (said, done.stderr)
    # the shipped note names no count, so a new verdict can never leave it stale
    assert "`verify.sh` verdicts" not in (REPO / "docs/round/reproduction.txt").read_text()
