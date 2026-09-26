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


def verify(run_id="22", sha=SHA, status="confirmed"):
    return {"run_id": run_id, "artifact": {"sha256": sha}, "verify": {"status": status}}


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
    held = orq.ledger(fleet)
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
            return orq.Run(command, 0, orq.MEASURES[command.split()[-1]](env), "", 0.0)
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

    (Path(variables["HIS"]) / "2000.txt").unlink()
    with pytest.raises(orq.Refusal, match="2000.txt"):
        orq.build(out, fleet, variables)
    assert (en / orq.DOCX).is_file()  # a refused build leaves the last one standing
