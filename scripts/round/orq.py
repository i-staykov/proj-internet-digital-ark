"""Build the two Open Research Questions folders every submission ships.

His brief asks for them in two places. Section IV-A puts the two open questions and asks
for a folder `Open Research Questions` holding `Open Research Questions.docx`, with code,
source links, execution logs, result samples and screenshots beside it, and every
untested idea labelled "Pending validation". Section X asks for a second folder,
`开放性研究问题`, of plain-text answers covering the proposed approaches, completed
related work or tests, preliminary technical-feasibility findings, preliminary
practical-operability findings, limitations and next steps. Both are built here from
one template, `docs/orq/orq.template.md`, so they cannot say different things.

    uv run python scripts/round/orq.py --preview DIR [--fleet DIR]
    uv run python scripts/round/orq.py --stage DIR [--fleet DIR]
    uv run python scripts/round/orq.py --measure ID

`--stage` writes into a package stage and refuses one under `submissions/`. `--preview`
writes anywhere else, and refuses `output/` too, so a look at the document never lands
in a delivery. `--fleet` defaults to `$ARK_FLEET`, else `~/Documents/GitHub/ark-fleet`.

**Every figure is computed at build time, never typed.** The template carries prose and
`[TOKEN]`s. A digit anywhere else in it, outside a heading or a code span, is refused, and
so is a token the build cannot fill, so a stale number cannot hide in the prose.

**Q1 is the fleet's pre-1996 lens**: every `leads/*.json` whose `lens` is `pre-1996`. A lead
leaves Q1 only when all its dated records postdate 1995: its extraction years (the keys
with a count in `finding.json` and `verify.json`) are non-empty and all 1996 or later, and
neither `what_dates_one_item` nor `sample_record` names a year before 1996. Those two
texts date records as four-digit years (`[01/Jul/1995:` included), as `YYYYMMDD` and CDX
stamps, and as `dd-Mon-yy` (`17-May-95`). An empty `years` is no evidence of lateness: the
DDN host table has none, and its editions are stamped only as `17-May-95` and the like.

**The labels are his words, computed from the fleet's files.** "Validated": the finding
records its artifact's sha256, `extract.py` compiles, the finding records the command that
priced it, and an independent verify leg confirmed it with the same bytes. "Tested, not
independently verified": a finding exists and one of those fails, and `tests.csv` says
which. "Pending validation": no finding, or a proposed approach nothing has run. A Q2
command re-run by this build is "Tested, not independently verified": it ran, and nothing
independent has run it again. A fleet experiment keeps the label its re-run gave it.

**Q2 is the template's Q2 table.** Each row's command is exactly what runs, concurrently,
at every build, with `$HIS`, `$NETNEW`, `$CDX` and `$AUDIT` naming its inputs. `--measure`
is the part of a command too long for a table cell.

**Cost is the fleet ledger's.** A test's run_ids (the price leg's in `finding.json`, the
verify leg's in `verify.json`, an experiment's own) are looked up among the `leg` and
`read` lines of `ledger/YYYY-MM.jsonl`, and a leg's seven-day points are the fleet's own
`ledger.points`. A run no line holds is "not recorded", which is every run before the
ledger began.

**It never reads `private/` or the store**: every file it opens from this repository or
the fleet goes through `read_bytes`, which refuses both, and a Q2 command reads only what
`$HIS`, `$NETNEW`, `$CDX` and `$AUDIT` name. Fleet evidence is copied into the folders,
never linked, and a copy that names `private/` or a home directory stops the build.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_report_docx import to_docx  # noqa: E402

TEMPLATE = REPO / "docs/orq/orq.template.md"
BRIEF = REPO / "docs/brief/ding/project-brief.md"
# In a worktree, data/ is a link into the checkout that owns it, whose private/ must be
# refused as well as this tree's.
OWNER = (REPO / "data").resolve().parent
FORBIDDEN = tuple(dict.fromkeys((REPO / "private", OWNER / "private")))
NETNEW = REPO / "output/netnew"
CDX = REPO / "data/raw/cdx"
AUDIT = REPO / "data/audit/status_audit.json"
SCREENSHOTS = REPO / "data/orq/screenshots"
DEFAULT_FLEET = Path.home() / "Documents/GitHub/ark-fleet"

EN = "Open Research Questions"
ZH = "开放性研究问题"
DOCX = f"{EN}.docx"
TXT = {"Q1": "Q1_pre1996_discovery.txt", "Q2": "Q2_year_assignment.txt"}
README = "README.txt"

VALIDATED = "Validated"
TESTED = "Tested, not independently verified"
PENDING = "Pending validation"
LABELS = (VALIDATED, TESTED, PENDING)
# Section X's six, in its order. His text has them lowercase inside one sentence.
HEADINGS = (
    "Proposed approaches",
    "Completed related work or tests",
    "Preliminary technical-feasibility findings",
    "Preliminary practical-operability findings",
    "Limitations",
    "Next steps",
)
LENS = "pre-1996"
FIRST_YEAR, LAST_YEAR = 1996, 2001
NOT_RECORDED = "not recorded"
# A lane under this many net-new EE per client-hour after two hours is killed.
KILL_FLOOR = 300

PLACEHOLDER = re.compile(r"\[([A-Z][A-Z0-9_]+)\]")
SHA256 = re.compile(r"[0-9a-f]{64}")
CODE_SPAN = re.compile(r"`[^`]*`")
HOME = re.compile(r"(?<![A-Za-z0-9._-])/(?:Users|home)/[A-Za-z0-9._-]+/")
_MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
_YEAR = re.compile(r"(?<!\d)(1[89]\d\d|20\d\d)(?!\d)")
_STAMP = re.compile(
    r"(?<!\d)(1[89]\d\d|20\d\d)(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])(?:\d{6})?(?!\d)"
)
_DMY = re.compile(rf"(?<!\d)\d{{1,2}}-(?:{_MONTHS})-(\d\d)(?!\d)", re.I)
_JOURNAL = re.compile(r"^cdx_yearfill_([a-z0-9]+)_(\d{8}T\d{6}Z)_\d+\.jsonl\.gz$")

TESTS_FIELDS = (
    "question",
    "id",
    "label",
    "label_reason",
    "leg",
    "run_id",
    "tokens_in_plus_out",
    "duration_s",
    "seven_day_delta",
    "evidence",
    "code",
    "logs",
    "sample",
)
SOURCES_FIELDS = ("question", "id", "kind", "name", "url", "sha256", "bytes", "anchor")


class Refusal(Exception):
    """The build stops here and writes nothing into the target."""


# --- reading ----------------------------------------------------------------------------


def _forbidden(path: Path) -> str:
    resolved = Path(path).resolve()
    for root in FORBIDDEN:
        root = root.resolve()
        if resolved == root or root in resolved.parents:
            return "private/"
    if resolved.name.startswith("ark.duckdb"):
        return "the store"
    return ""


def read_bytes(path: Path) -> bytes:
    """Every read of a file goes through here, and none reaches private/ or the store."""
    why = _forbidden(path)
    if why:
        raise Refusal(f"{path} is {why}, which the research questions never read")
    return Path(path).read_bytes()


def read_text(path: Path) -> str:
    return read_bytes(path).decode("utf-8")


def _json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        doc = json.loads(read_text(path))
    except (ValueError, UnicodeDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def _dig(doc: dict | None, *keys):
    for key in keys:
        if not isinstance(doc, dict):
            return None
        doc = doc.get(key)
    return doc


def clean(text: str, origin: str) -> str:
    """Text bound for the folders, refused when it names private/ or a home directory."""
    if "private/" in text:
        raise Refusal(f"{origin} names private/, which never ships")
    if HOME.search(text):
        raise Refusal(f"{origin} names a home directory, which never ships")
    return text


# --- Q1: the fleet's pre-1996 lens -----------------------------------------------------


def text_years(text: str) -> set[int]:
    """Every year a free-text date field names, in the shapes the leads use."""
    years = {int(y) for y in _YEAR.findall(text)}
    years |= {int(y) for y in _STAMP.findall(text)}
    years |= {(1900 if int(yy) >= 70 else 2000) + int(yy) for yy in _DMY.findall(text)}
    return years


def extraction_years(*docs: dict | None) -> set[int]:
    """The years an extraction counted at least one item in, over finding and verify."""
    out = set()
    for doc in docs:
        years = _dig(doc, "extraction", "years")
        if not isinstance(years, dict):
            continue
        for key, count in years.items():
            number = isinstance(count, (int, float)) and not isinstance(count, bool)
            if number and count > 0 and str(key).isdigit():
                out.add(int(key))
    return out


def postdates(lead: dict, finding: dict | None, verify: dict | None) -> bool:
    """Whether every dated record of a pre-1996 lead is 1996 or later, so it is not Q1's."""
    years = extraction_years(finding, verify)
    if not years or min(years) < FIRST_YEAR:
        return False
    text = " ".join(str(lead.get(k) or "") for k in ("what_dates_one_item", "sample_record"))
    return not any(y < FIRST_YEAR for y in text_years(text))


def compiles(path: Path) -> str:
    """ "" when the file compiles as Python, else why not. compile() rather than
    py_compile, which would write a .pyc into the fleet checkout."""
    try:
        compile(read_text(path), path.name, "exec", dont_inherit=True)
    except (SyntaxError, ValueError, UnicodeDecodeError) as exc:
        return f"{type(exc).__name__}: {exc}".splitlines()[0]
    return ""


def label_of(
    folder: Path, lead: dict, finding: dict | None, verify: dict | None
) -> tuple[str, list[str]]:
    """A fleet test's label and, when it is not Validated, what it lacks."""
    if finding is None:
        why = lead.get("closed_reason") or lead.get("blocked_on") or lead.get("status")
        return PENDING, [f"closed at the scout leg, before any extractor ran: {why}"]
    gaps = []
    sha = _dig(finding, "artifact", "sha256")
    if not (isinstance(sha, str) and SHA256.fullmatch(sha)):
        gaps.append("no artifact sha256")
    code = folder / "extract.py"
    if code.is_file():
        error = compiles(code)
        if error:
            gaps.append(f"extract.py does not compile ({error})")
    elif (folder / "extract.py.txt").is_file():
        gaps.append("extract.py was kept as extract.py.txt because it does not compile")
    else:
        gaps.append("no extract.py")
    command = _dig(finding, "pricing", "cmd")
    if not (isinstance(command, str) and command.strip()):
        gaps.append("no pricing command")
    status = _dig(verify, "verify", "status") or _dig(finding, "verify", "status")
    if status != "confirmed":
        gaps.append(f"verify {status}" if status else "no verify")
    else:
        again = _dig(verify, "artifact", "sha256")
        if not (isinstance(again, str) and SHA256.fullmatch(again)):
            gaps.append("the verify leg recorded no bytes of its own")
        elif again != sha:
            gaps.append("the verify leg fetched different bytes")
    return (TESTED if gaps else VALIDATED), gaps


@dataclass
class Test:
    question: str
    id: str
    label: str
    gaps: list[str]
    runs: list[tuple[str, str]]
    lead: dict = field(default_factory=dict)
    finding: dict | None = None
    verify: dict | None = None
    command: str = ""
    result: str = ""
    anchor: str = ""
    seconds: float | None = None
    run: Run | None = None
    record: Path | None = None
    evidence: str = ""
    code: str = ""
    logs: str = ""
    sample: str = ""


def q1(fleet: Path) -> tuple[list[Test], list[str], int]:
    """The Q1 tests, the pre-1996 leads left out as postdating 1995, and the lens's size."""
    tests, excluded, seen = [], [], 0
    for path in sorted((fleet / "leads").glob("*.json")):
        slug = path.stem
        if slug.startswith("_"):
            continue
        lead = _json(path)
        if not lead or lead.get("lens") != LENS:
            continue
        seen += 1
        folder = fleet / "leads" / slug
        finding, verify = _json(folder / "finding.json"), _json(folder / "verify.json")
        if postdates(lead, finding, verify):
            excluded.append(slug)
            continue
        label, gaps = label_of(folder, lead, finding, verify)
        runs = [
            (leg, str(doc["run_id"]))
            for leg, doc in (("price", finding), ("verify", verify))
            if doc and doc.get("run_id") not in (None, "")
        ]
        tests.append(Test("Q1", slug, label, gaps, runs, lead, finding, verify))
    return tests, excluded, seen


# --- cost: the fleet ledger ------------------------------------------------------------


def ledger(fleet: Path) -> dict[str, list[dict]]:
    """The fleet ledger's `leg` and `read` lines by run_id. None before the ledger began.

    A leg line's seven-day points are the fleet's own `ledger.points`, kept on the line as
    `_points`. The stored `seven_day_delta` is only the move known when the line was
    collected, and slots collect out of order, so the ledger's readers charge `points`."""
    out: dict[str, list[dict]] = {}
    for path in sorted((fleet / "ledger").glob("*.jsonl")):
        for text in read_text(path).splitlines():
            try:
                line = json.loads(text) if text.strip() else None
            except ValueError:
                continue
            if not isinstance(line, dict) or line.get("kind") not in ("leg", "read"):
                continue
            if line.get("run_id") not in (None, ""):
                out.setdefault(str(line["run_id"]), []).append(line)
    moves = fleet_points(fleet) if out else None
    for line in (line for held in out.values() for line in held):
        if line.get("kind") == "leg" and moves is not None:
            line["_points"] = moves.get(str(line["run_id"]))
        else:
            line["_points"] = line.get("seven_day_delta")
    return out


def fleet_points(fleet: Path) -> dict | None:
    """`points` from the fleet's own scripts/ledger.py, standard library only, or None for a
    checkout that predates it."""
    script = fleet / "scripts/ledger.py"
    if not script.is_file():
        return None
    spec = importlib.util.spec_from_file_location("fleet_ledger_for_orq", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "points"):
        return None
    return module.points(module.read(fleet))


def _number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _seconds(line: dict) -> float | None:
    if _number(line.get("duration_s")) is not None:
        return _number(line.get("duration_s"))
    try:
        started = datetime.strptime(str(line.get("started")), "%Y-%m-%dT%H:%M:%SZ")
        ended = datetime.strptime(str(line.get("ended")), "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return (ended - started).total_seconds()


def _total(values: list[float | None]) -> str:
    known = [v for v in values if v is not None]
    if not known:
        return "none"
    total = sum(known)
    return f"{total:.3f}".rstrip("0").rstrip(".") if total % 1 else str(int(total))


def cost(lines: dict[str, list[dict]], run_id: str, slug: str) -> tuple[str, str, str]:
    """(tokens, seconds, seven-day points) of one run, or "not recorded" three times. A
    held line that carries no figure says "none", as a leg the governor skipped does.

    A line that names a slug must name this one: before the Leg workflow one run_id covered
    a whole wave of leads."""
    held = [line for line in lines.get(run_id, []) if line.get("slug") in (None, "", slug)]
    if not held:
        return NOT_RECORDED, NOT_RECORDED, NOT_RECORDED
    return (
        _total([_number(line.get("tokens_in_plus_out")) for line in held]),
        _total([_seconds(line) for line in held]),
        _total([_number(line.get("_points")) for line in held]),
    )


# --- Q2: the template's table, run at every build ---------------------------------------


@dataclass
class Row:
    id: str
    command: str
    anchor: str
    result: str


def q2_rows(template: str) -> list[Row]:
    """The Q2 table: `id` | `command` or none | `file#phrase` | [TOKEN] or text."""
    rows = []
    for line in template.splitlines():
        if not line.startswith("| `q2-"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 4 or not re.fullmatch(r"`q2-[a-z0-9-]+`", cells[0]):
            raise Refusal(f"a Q2 row needs four cells and no | inside one: {line[:60]}")
        command = cells[1]
        if command == "none":
            command = ""
        elif re.fullmatch(r"`[^`]+`", command):
            command = command[1:-1]
        else:
            raise Refusal(f"Q2 row {cells[0]}: the command is one code span or none")
        if not re.fullmatch(r"`[^`#]+#[^`]+`", cells[2]):
            raise Refusal(f"Q2 row {cells[0]}: the anchor is one `file#phrase` code span")
        rows.append(Row(cells[0][1:-1], command, cells[2][1:-1], cells[3]))
    ids = [row.id for row in rows]
    if len(set(ids)) != len(ids):
        raise Refusal("the Q2 table repeats an id")
    return rows


def resolve_anchor(anchor: str) -> str:
    """`file#phrase` as `file:line`, refused when the phrase is not in the file."""
    name, phrase = anchor.split("#", 1)
    path = REPO / name
    if not path.is_file():
        raise Refusal(f"anchor {anchor}: no file {name}")
    for number, line in enumerate(read_text(path).splitlines(), 1):
        if phrase in line:
            return f"{name}:{number}"
    raise Refusal(f"anchor {anchor}: the phrase is not in {name}")


def inputs() -> dict[str, str]:
    """What the Q2 commands read, as the variables they name it by."""
    from ark.baseline import baseline_dir

    cwd = os.getcwd()
    try:
        os.chdir(REPO)
        his = baseline_dir().resolve()
    finally:
        os.chdir(cwd)
    return {
        "HIS": os.environ.get("HIS") or str(his),
        "NETNEW": os.environ.get("NETNEW") or str(NETNEW),
        "CDX": os.environ.get("CDX") or str(CDX),
        "AUDIT": os.environ.get("AUDIT") or str(AUDIT),
    }


@dataclass
class Run:
    command: str
    code: int
    stdout: str
    stderr: str
    seconds: float


_NAMED = re.compile(r"\$(HIS|NETNEW|CDX|AUDIT)\"?((?:/[^\s\"'()]+)?)")


def missing_inputs(command: str, variables: dict[str, str]) -> list[str]:
    """Every `$VAR/path` a command names that is not there. A process substitution hides
    its own failure, so `wc -l < <(comm A B)` prints 0 when A is gone: checked first."""
    gone = []
    for var, rest in _NAMED.findall(command):
        path = Path(variables[var] + rest)
        if any(ch in rest for ch in "*?["):
            found = list(path.parent.glob(path.name))
        else:
            found = [path] if path.exists() else []
        if not found:
            gone.append(f"${var}{rest}")
    return gone


def _run(command: str, env: dict[str, str]) -> Run:
    start = time.monotonic()
    done = subprocess.run(
        ["bash", "-o", "pipefail", "-c", command],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
    )
    return Run(command, done.returncode, done.stdout, done.stderr, time.monotonic() - start)


def start_measures(rows: list[Row], variables: dict[str, str]) -> dict[str, Future]:
    """Every Q2 command at once: the whole build has two minutes, and the slowest command
    alone takes about half of that."""
    env = {**os.environ, **variables, "LC_ALL": "C"}
    pool = ThreadPoolExecutor(max_workers=max(1, sum(1 for row in rows if row.command)))
    futures = {row.id: pool.submit(_run, row.command, env) for row in rows if row.command}
    pool.shutdown(wait=False)
    return futures


def _numbers(out: str) -> list[int]:
    return [int(x) for x in out.split()]


def _pct(part: float, whole: float, places: int = 2) -> str:
    return f"{100 * part / whole:.{places}f}" if whole else "0"


def _continuity(out: str) -> tuple[dict[str, str], str]:
    shared, base = _numbers(out)
    pct = _pct(shared, base, 1)
    values = {"SHARED": f"{shared:,}", "BASE": f"{base:,}", "PCT": pct}
    return values, f"{shared:,} of {base:,} names ({pct}%)"


def _overlap(out: str) -> tuple[dict[str, str], str]:
    (count,) = _numbers(out)
    return {"COUNT": f"{count:,}"}, f"{count:,} names"


def _rows_of(out: str, kind: str) -> list[list[str]]:
    return [line.split("\t")[1:] for line in out.splitlines() if line.startswith(kind + "\t")]


def _status_share(out: str) -> tuple[dict[str, str], str]:
    families = {name: [int(x) for x in rest] for name, *rest in _rows_of(out, "family")}
    rows, c4, c5 = families.pop("all")
    shipped = [[int(x) for x in rest] for _, *rest in _rows_of(out, "shipped")]
    by_family = ", ".join(
        f"{name} {_pct(f4, total)}%" for name, (total, f4, _) in sorted(families.items())
    )
    values = {
        "ROWS": f"{rows:,}",
        "FOURXX_PCT": _pct(c4, rows),
        "FIVEXX_PCT": _pct(c5, rows),
        "ERROR_PCT": _pct(c4 + c5, rows),
        "FAMILIES": by_family,
        "SHIPPED": f"{sum(s[0] for s in shipped):,}",
        "RETRACT": f"{sum(s[1] for s in shipped):,}",
        "REPOINT": f"{sum(s[2] for s in shipped):,}",
    }
    result = (
        f"{values['FOURXX_PCT']}% of {rows:,} raw CDX rows answered 4xx and "
        f"{values['FIVEXX_PCT']}% 5xx ({by_family} 4xx)"
    )
    return values, result


def _yearfill(out: str) -> tuple[dict[str, str], str]:
    lanes = _rows_of(out, "lane")
    names = sum(int(lane[1]) for lane in lanes)
    hosts = sum(int(lane[2]) for lane in lanes)
    held = sum(int(lane[3]) for lane in lanes)
    fresh = sum(int(lane[4]) for lane in lanes)
    ee = sum((Decimal(lane[5]) for lane in lanes), Decimal(0))
    rate = max((Decimal(lane[5]) / Decimal(lane[6]) for lane in lanes), default=Decimal(0))
    values = {
        "NAMES": f"{names:,}",
        "HOSTS": f"{hosts:,}",
        "HELD": f"{held:,}",
        "NOT_HIS": f"{fresh:,}",
        "EE": f"{ee:,.4f}",
        "RATE": f"{rate:.2f}",
        "FLOOR": f"{KILL_FLOOR:,}",
        "LANES": str(len(lanes)),
    }
    result = (
        f"{names:,} names queried in {len(lanes)} lanes, {hosts:,} hosts with a {LAST_YEAR} "
        f"capture, {held:,} already his, {fresh:,} not his, {ee:,.4f} EE, at most {rate:.2f} "
        f"EE a client-hour against a floor of {KILL_FLOOR:,}"
    )
    return values, result


# How each Q2 command's output becomes figures. A row with a command and no entry here,
# or an entry with no row, is refused: the table and this file must agree.
PARSERS = {
    "q2-continuity-1999-2000": _continuity,
    "q2-continuity-2000-2001": _continuity,
    "q2-pool-his": _overlap,
    "q2-pool-ours": _overlap,
    "q2-status-share": _status_share,
    "q2-yearfill-kill": _yearfill,
}


def token_prefix(row_id: str) -> str:
    return row_id.removeprefix("q2-").replace("-", "_").upper()


# --- the parts of a command too long for a table cell ----------------------------------


def measure_status_share(env: dict[str, str]) -> str:
    """Raw CDX rows by status per family, and the shipped records a 4xx or 5xx moved, from
    the status audit's summary: re-reading the raw CDX takes hours."""
    audit = json.loads(read_text(Path(env["AUDIT"])))
    lines, total = [], [0, 0, 0]
    for name, family in sorted((audit.get("families") or {}).items()):
        counts = family.get("rows") or {}
        row = [sum(int(v) for v in counts.values()), int(counts.get("4xx", 0))]
        row.append(int(counts.get("5xx", 0)))
        total = [a + b for a, b in zip(total, row, strict=True)]
        lines.append("\t".join(["family", name, *map(str, row)]))
    lines.append("\t".join(["family", "all", *map(str, total)]))
    for name, shipped in sorted((audit.get("shipped") or {}).items()):
        row = [int(shipped.get(k, 0)) for k in ("rows", "retract", "repoint")]
        lines.append("\t".join(["shipped", name, *map(str, row)]))
    return "\n".join(lines) + "\n"


def measure_yearfill_kill(env: dict[str, str]) -> str:
    """The CDX year-fill lanes, read again from their journals: per lane the names queried,
    the hosts with a capture in the last year, how many of those his file holds, the rest
    and their EE, and the lane's hours from its first shard's name stamp to its last's. The
    last shard ran on past its stamp, so those hours are too few and the rate an upper
    bound, read from the journals' names alone. Then one line per host he does not hold."""
    from ark.english_share import weight_of

    cdx, his = Path(env["CDX"]), Path(env["HIS"]) / f"{LAST_YEAR}.txt"
    lanes: dict[str, dict] = {}
    for path in sorted(cdx.glob("cdx_yearfill_*.jsonl.gz")):
        match = _JOURNAL.match(path.name)
        if not match:
            continue
        lane = lanes.setdefault(match[1], {"names": set(), "hosts": set(), "stamps": []})
        lane["stamps"].append(datetime.strptime(match[2], "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC))
        with gzip.open(io.BytesIO(read_bytes(path)), "rt", encoding="utf-8") as handle:
            for text in handle:
                record = json.loads(text)
                lane["names"].add(record["domain"])
                for host, stamp in (record.get("hosts") or {}).items():
                    if str(stamp).startswith(str(LAST_YEAR)):
                        lane["hosts"].add(host)
    if not lanes:
        raise Refusal(f"no year-fill journals in {cdx}")
    every = sorted(set().union(*(lane["hosts"] for lane in lanes.values())), key=str.encode)
    done = subprocess.run(
        ["comm", "-12", "-", str(his)],
        input="".join(host + "\n" for host in every),
        capture_output=True,
        text=True,
        env={**os.environ, "LC_ALL": "C"},
        check=True,
    )
    held = set(done.stdout.split())
    lines, fresh_lines = [], []
    for name, lane in sorted(lanes.items()):
        fresh = sorted(lane["hosts"] - held)
        ee = sum((weight_of(host) for host in fresh), Decimal(0))
        began, ended = min(lane["stamps"]), max(lane["stamps"])
        if ended == began:
            raise Refusal(f"year-fill lane {name} has one shard, so its names give no hours")
        hours = Decimal(str(round((ended - began).total_seconds() / 3600, 4)))
        row = [len(lane["names"]), len(lane["hosts"]), len(lane["hosts"] & held), len(fresh)]
        stamps = [f"{t:%Y-%m-%dT%H:%M:%SZ}" for t in (began, ended)]
        lines.append("\t".join(["lane", name, *map(str, row), f"{ee:.4f}", str(hours), *stamps]))
        fresh_lines += ["\t".join(["host", name, host, f"{weight_of(host):.4f}"]) for host in fresh]
    return "\n".join(lines + fresh_lines) + "\n"


MEASURES = {"q2-status-share": measure_status_share, "q2-yearfill-kill": measure_yearfill_kill}


# --- the template ----------------------------------------------------------------------


def stray_digits(template: str) -> list[int]:
    """Lines of the template with a digit outside a heading, a code span or a token."""
    bad = []
    for number, line in enumerate(template.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        if re.search(r"\d", PLACEHOLDER.sub("", CODE_SPAN.sub("", line))):
            bad.append(number)
    return bad


def check_template(template: str, brief: str) -> None:
    """Refuse a template that could ship a typed figure, drop a heading or misquote him."""
    bad = stray_digits(template)
    if bad:
        raise Refusal(f"{TEMPLATE.name}: a digit outside a token on line(s) {bad}")
    for question in ("Q1", "Q2"):
        section = split(template).get(question)
        if section is None:
            raise Refusal(f"{TEMPLATE.name}: no ## {question}. section")
        asked = section.splitlines()[0].split(". ", 1)[-1].strip()
        if asked not in brief:
            raise Refusal(f"{TEMPLATE.name}: {question} is not his question: {asked}")
        found = [line[4:].strip() for line in section.splitlines() if line.startswith("### ")]
        if tuple(found) != HEADINGS:
            raise Refusal(f"{TEMPLATE.name}: {question} needs exactly the six headings, in order")


def split(markdown: str) -> dict[str, str]:
    """The title and preamble as "head", each `## Qn.` section by "Qn", the rest as "tail"."""
    parts: dict[str, str] = {"head": "", "tail": ""}
    key = "head"
    for line in markdown.splitlines(keepends=True):
        if line.startswith("## "):
            match = re.match(r"## (Q\d)\. ", line)
            key = match[1] if match else "tail"
            parts.setdefault(key, "")
        parts[key] += line
    return parts


def fill(template: str, values: dict[str, str]) -> str:
    """Every token replaced in one pass, so a value is never read as a token itself. A
    token without a value is refused, as fill_report.py refuses one."""
    missing = sorted({t for t in PLACEHOLDER.findall(template) if not values.get(t)})
    if missing:
        raise Refusal(f"{TEMPLATE.name}: unfilled token(s) {', '.join(missing)}")
    return PLACEHOLDER.sub(lambda m: values[m[1]], template)


# --- building ---------------------------------------------------------------------------


def _table(header: list[str], rows: list[list[str]]) -> str:
    """A pipe table whose separator dashes follow each column's longest cell: pandoc sizes
    the .docx columns from them."""
    widths = [max(len(cell) for cell in column) for column in zip(header, *rows, strict=True)]
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(":" + "-" * w for w in widths) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


def _figure(value) -> str:
    number = _number(value)
    if number is None:
        return ""
    return f"{number:,.4f}".rstrip("0").rstrip(".") if number % 1 else f"{int(number):,}"


def q1_table(tests: list[Test]) -> str:
    rows = []
    for test in tests:
        if test.finding is None:
            continue
        pricing = test.finding.get("pricing") or {}
        manifest = str(pricing.get("manifest_sha") or "")[:12]
        years = _dig(test.finding, "extraction", "years") or {}
        dated = sum(
            count
            for year, count in years.items()
            if str(year).isdigit() and FIRST_YEAR <= int(year) <= LAST_YEAR and _number(count)
        )
        rows.append(
            [
                f"`{test.id}`",
                test.label,
                str(test.finding.get("verdict") or ""),
                _figure(_dig(test.finding, "extraction", "items")),
                _figure(dated),
                _figure(pricing.get("ee")),
                str(pricing.get("track") or ""),
                str(pricing.get("snapshot_marker") or ""),
                f"`{manifest}`" if manifest else "",
            ]
        )
    window = f"dated {FIRST_YEAR} to {LAST_YEAR}"
    header = ["test", "label", "verdict", "items", window, "EE", "track", "snapshot", "manifest"]
    return _table(header, rows) if rows else "No pre-1996 lead has been tested yet."


def _write(path: Path, text: str, origin: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(clean(text, origin), encoding="utf-8")


def copy_q1(test: Test, fleet: Path, root: Path) -> None:
    """The fleet's own record of a lead, copied in: evidence, code, the label's checks and
    a sample record."""
    folder = fleet / "leads" / test.id
    evidence = root / "evidence" / test.id
    _write(evidence / "lead.json", read_text(fleet / "leads" / f"{test.id}.json"), test.id)
    for path in sorted(folder.iterdir()) if folder.is_dir() else []:
        if not path.is_file():
            continue
        target = root / "code" / test.id if path.name.startswith("extract.py") else evidence
        _write(target / path.name, read_text(path), f"{test.id}/{path.name}")
    test.evidence = f"evidence/{test.id}/"
    if (root / "code" / test.id).is_dir():
        test.code = f"code/{test.id}/"
    code_gap = [gap for gap in test.gaps if "extract.py" in gap]
    verify = _dig(test.verify, "verify") or _dig(test.finding, "verify") or {}
    checks = [
        f"label: {test.label}",
        f"artifact sha256: {_dig(test.finding, 'artifact', 'sha256') or 'none'}",
        f"extract.py: {code_gap[0] if code_gap else 'compiles'}",
        f"pricing command: {_dig(test.finding, 'pricing', 'cmd') or 'none'}",
        f"verify: {verify.get('status') or 'none'}",
        f"verify reason: {verify.get('reason') or 'none'}",
        *(f"missing: {gap}" for gap in test.gaps),
    ]
    if test.finding is None:
        checks = [f"label: {test.label}", *(f"missing: {gap}" for gap in test.gaps)]
    _write(root / "logs" / test.id / "checks.txt", "\n".join(checks) + "\n", f"{test.id} checks")
    test.logs = f"logs/{test.id}/"
    sample = [
        f"sample_record: {test.lead.get('sample_record') or 'none'}",
        f"what_dates_one_item: {test.lead.get('what_dates_one_item') or 'none'}",
    ]
    _write(root / "samples" / f"{test.id}.txt", "\n".join(sample) + "\n", f"{test.id} sample")
    test.sample = f"samples/{test.id}.txt"


def copy_q2(test: Test, run: Run, root: Path, variables: dict[str, str]) -> None:
    logs = root / "logs" / test.id
    _write(logs / "command.txt", f"{run.command}\n", f"{test.id} command")
    _write(logs / "stdout.txt", run.stdout, f"{test.id} stdout")
    if run.stderr.strip():
        _write(logs / "stderr.txt", run.stderr, f"{test.id} stderr")
    _write(logs / "seconds.txt", f"{run.seconds:.1f}\n", f"{test.id} seconds")
    test.logs = f"logs/{test.id}/"
    hosts = [line.split("\t")[2] for line in run.stdout.splitlines() if line.startswith("host\t")]
    if hosts:
        _write(root / "samples" / f"{test.id}.txt", "\n".join(hosts) + "\n", f"{test.id} sample")
        test.sample = f"samples/{test.id}.txt"
    inputs_of = {
        "q2-status-share": [Path(variables["AUDIT"])],
        "q2-yearfill-kill": sorted(Path(variables["CDX"]).glob("cdx_yearfill_*.jsonl.gz")),
    }.get(test.id, [])
    for path in inputs_of:
        target = root / "evidence" / test.id / path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        data = read_bytes(path)
        if path.suffix != ".gz":
            clean(data.decode("utf-8"), f"{test.id}/{path.name}")
        target.write_bytes(data)
        test.evidence = f"evidence/{test.id}/"


def experiments(fleet: Path) -> list[Test]:
    """The fleet's Q2 experiments, one test per record, each keeping the label its clean
    re-run gave it: Validated only when that re-run printed the bytes its scout recorded."""
    tests = []
    for path in sorted((fleet / "experiments").glob("*/*.json")):
        record = _json(path)
        if not record:
            continue
        label = VALIDATED if record.get("label") == VALIDATED else PENDING
        runs = [("experiment", str(record["run_id"]))] if record.get("run_id") else []
        test = Test("Q2", path.parent.name, label, [], runs)
        if label == PENDING:
            test.gaps = ["no clean re-run printed the recorded bytes"]
        test.command = str(record.get("command") or "")
        test.result = str(record.get("result") or "")
        test.record = path
        tests.append(test)
    return tests


def _git(fleet: Path, *args: str) -> str:
    """git over the fleet alone. Under a git hook GIT_DIR and GIT_INDEX_FILE name the
    repository being committed, and `-C` does not override them, so every GIT_ variable is
    dropped."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    done = subprocess.run(["git", "-C", str(fleet), *args], capture_output=True, text=True, env=env)
    return done.stdout.strip() if done.returncode == 0 else ""


def fleet_head(fleet: Path) -> str:
    """The fleet commit the folders are built from, refused when the checkout holds changes
    under what is read, since the commit would not hold them. "" when the fleet is not the
    top of a git checkout."""
    top = _git(fleet, "rev-parse", "--show-toplevel")
    if not top or Path(top).resolve() != fleet.resolve():
        return ""
    if _git(fleet, "status", "--porcelain", "--", "leads", "ledger", "experiments"):
        raise Refusal(f"{fleet} has uncommitted changes under leads/, ledger/ or experiments/")
    return _git(fleet, "rev-parse", "HEAD")


def _sha(path: Path) -> str:
    return hashlib.sha256(read_bytes(path)).hexdigest()


def register_line(slug: str) -> str:
    for name in ("docs/registers/sources.md", "docs/registers/sources-closed.md"):
        path = REPO / name
        if path.is_file():
            for number, line in enumerate(read_text(path).splitlines(), 1):
                if slug in line:
                    return f"{name}:{number}"
    return ""


def _csv(rows: list[dict], fields: tuple[str, ...]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def tests_rows(tests: list[Test], lines: dict[str, list[dict]]) -> list[dict]:
    rows = []
    for test in tests:
        base = {
            "question": test.question,
            "id": test.id,
            "label": test.label,
            "label_reason": "; ".join(test.gaps),
            "evidence": test.evidence,
            "code": test.code,
            "logs": test.logs,
            "sample": test.sample,
        }
        if test.seconds is not None:
            rows.append(
                base
                | {
                    "leg": "rerun",
                    "tokens_in_plus_out": "0",
                    "duration_s": f"{test.seconds:.1f}",
                    "seven_day_delta": "0",
                }
            )
        elif not test.runs:
            rows.append(base)
        for leg, run_id in test.runs:
            tokens, seconds, points = cost(lines, run_id, test.id)
            rows.append(
                base
                | {
                    "leg": leg,
                    "run_id": run_id,
                    "tokens_in_plus_out": tokens,
                    "duration_s": seconds,
                    "seven_day_delta": points,
                }
            )
    return rows


def sources_rows(
    q1_tests: list[Test], q2_tests: list[Test], variables: dict[str, str]
) -> list[dict]:
    rows = []
    for test in q1_tests:
        artifact = _dig(test.finding, "artifact") or test.lead.get("artifact") or {}
        rows.append(
            {
                "question": "Q1",
                "id": test.id,
                "kind": "artifact",
                "name": str(artifact.get("host") or ""),
                "url": str(artifact.get("url") or ""),
                "sha256": str(_dig(test.finding, "artifact", "sha256") or ""),
                "bytes": str(artifact.get("bytes") or ""),
                "anchor": register_line(test.id),
            }
        )
    his = Path(variables["HIS"])
    for test in q2_tests:
        row = {"question": "Q2", "id": test.id, "kind": "rerun" if test.command else "proposal"}
        rows.append(row | {"name": test.command, "anchor": test.anchor})
        for var, rest in _NAMED.findall(test.command):
            if var != "HIS" or not rest:
                continue
            for path in sorted(his.glob(rest.lstrip("/"))):
                name = f"{his.name}/{path.name}"
                if not any(r["name"] == name and r["id"] == test.id for r in rows):
                    rows.append(row | {"kind": "his release", "name": name})
        if test.id == "q2-pool-ours":
            path = Path(variables["NETNEW"]) / "candidate_additions.txt"
            if path.is_file():
                rows.append(
                    row
                    | {
                        "kind": "our file",
                        "name": "output/netnew/candidate_additions.txt",
                        "sha256": _sha(path),
                        "bytes": str(path.stat().st_size),
                    }
                )
    return rows


def build(root: Path, fleet: Path, variables: dict[str, str] | None = None) -> dict:
    """Write both folders under `root`, replacing any earlier build of them there."""
    started = time.monotonic()
    if not (fleet / "leads").is_dir():
        raise Refusal(f"{fleet} holds no leads/: not a fleet checkout")
    template = read_text(TEMPLATE)
    check_template(template, read_text(BRIEF))
    rows = q2_rows(template)
    commanded = {row.id for row in rows if row.command}
    if commanded != set(PARSERS):
        raise Refusal(f"the Q2 table and PARSERS disagree: {sorted(commanded ^ set(PARSERS))}")
    variables = variables or inputs()
    for row in rows:
        gone = missing_inputs(row.command, variables)
        if gone:
            raise Refusal(f"{row.id} reads what is not there: {', '.join(gone)}")
    futures = start_measures(rows, variables)

    head = fleet_head(fleet)
    q1_tests, excluded, lens_size = q1(fleet)
    lines = ledger(fleet)
    q2_tests = []
    values: dict[str, str] = {}
    for row in rows:
        test = Test("Q2", row.id, PENDING, [], [], anchor=resolve_anchor(row.anchor))
        test.command = row.command
        if row.command:
            run = futures[row.id].result()
            if run.code != 0:
                tail = (run.stderr.strip().splitlines() or ["no output"])[-1]
                raise Refusal(f"{row.id} exited {run.code}: {tail}")
            if run.stderr.strip() and "--measure" not in row.command:
                raise Refusal(f"{row.id} wrote to stderr: {run.stderr.strip().splitlines()[-1]}")
            try:
                figures, result = PARSERS[row.id](run.stdout)
            except (ValueError, KeyError, ZeroDivisionError) as exc:
                raise Refusal(f"{row.id} printed what it should not: {exc}") from exc
            prefix = token_prefix(row.id)
            values |= {f"{prefix}_{key}": value for key, value in figures.items()}
            years = re.findall(r"\d{4}", row.id)
            if len(years) == 2:
                values |= {f"{prefix}_FROM": years[0], f"{prefix}_TO": years[1]}
            test.label, test.seconds, test.result, test.run = TESTED, run.seconds, result, run
            test.gaps = ["re-run by this build, never by an independent leg"]
        else:
            test.gaps = ["proposed, never run"]
            test.result = PENDING
        if PLACEHOLDER.fullmatch(row.result):
            values[PLACEHOLDER.fullmatch(row.result)[1]] = test.result
        q2_tests.append(test)
    q2_tests += experiments(fleet)

    every = q1_tests + q2_tests
    counts = {label: sum(1 for t in every if t.label == label) for label in LABELS}
    tested = [t for t in q1_tests if t.finding is not None]
    validated = [t for t in q1_tests if t.label == VALIDATED]
    shots = sorted(p for p in SCREENSHOTS.glob("*.png")) if SCREENSHOTS.is_dir() else []
    exp = [t for t in q2_tests if t.record]
    values |= {
        "BUILT_AT": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "FLEET_COMMIT": head[:12] or "not a git checkout",
        "RELEASE": Path(variables["HIS"]).name,
        "FIRST_YEAR": str(FIRST_YEAR),
        "LAST_YEAR": str(LAST_YEAR),
        "YEAR_BEFORE_LAST": str(LAST_YEAR - 1),
        "LABEL_COUNTS": "; ".join(f"{counts[label]} {label}" for label in LABELS),
        "Q1_LENS_LEADS": str(lens_size),
        "Q1_EXCLUDED_COUNT": str(len(excluded)),
        "Q1_EXCLUDED": ", ".join(f"`{s}`" for s in excluded) or "none",
        "Q1_MEMBERS": str(len(q1_tests)),
        "Q1_TESTED": str(len(tested)),
        "Q1_VALIDATED": str(len(validated)),
        "Q1_VALIDATED_LIST": ", ".join(f"`{t.id}`" for t in validated) or "none",
        "Q1_TESTED_ONLY": str(sum(1 for t in q1_tests if t.label == TESTED)),
        "Q1_PENDING": str(sum(1 for t in q1_tests if t.label == PENDING)),
        "Q1_TESTS_TABLE": q1_table(q1_tests),
        "Q2_EXPERIMENTS": (
            "\n".join(
                f"- `{t.id}` run `{t.runs[0][1] if t.runs else 'none'}`, {t.label}: {t.result} "
                f"Command: `{t.command}`"
                for t in exp
            )
            if exp
            else "No fleet experiment has landed yet."
        ),
        "SCREENSHOTS": (
            f"{len(shots)} screenshots of the tested sources' pages"
            if shots
            else "none cached for this build"
        ),
    }
    markdown = fill(template, values)

    work = Path(tempfile.mkdtemp(prefix=".orq-", dir=root))
    try:
        en, zh = work / EN, work / ZH
        en.mkdir()
        zh.mkdir()
        for test in q1_tests:
            copy_q1(test, fleet, en)
        for test in q2_tests:
            if test.run is not None:
                copy_q2(test, test.run, en, variables)
            elif test.record is not None:
                name = test.record.name
                _write(en / "evidence" / test.id / name, read_text(test.record), name)
                test.evidence = f"evidence/{test.id}/"
        if shots:
            (en / "screenshots").mkdir()
            for path in shots:
                (en / "screenshots" / path.name).write_bytes(read_bytes(path))
        _write(en / "tests.csv", _csv(tests_rows(every, lines), TESTS_FIELDS), "tests.csv")
        _write(
            en / "sources.csv",
            _csv(sources_rows(q1_tests, q2_tests, variables), SOURCES_FIELDS),
            "sources.csv",
        )
        to_docx(clean(markdown, DOCX), en / DOCX)
        parts = split(markdown)
        title = parts["head"].splitlines()[0]
        texts = {
            TXT["Q1"]: f"{title}\n\n{parts['Q1']}",
            TXT["Q2"]: f"{title}\n\n{parts['Q2']}",
            README: parts["head"] + parts["tail"],
        }
        for name, text in texts.items():
            plain(clean(text, name), zh / name)
        for path in work.rglob("*"):
            if path.is_file() and path.suffix in (".txt", ".csv", ".md", ".json", ".py"):
                clean(path.read_text(encoding="utf-8"), str(path.relative_to(work)))
        for name in (EN, ZH):
            final = root / name
            if final.exists():
                shutil.rmtree(final)
            (work / name).rename(final)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return {
        "seconds": round(time.monotonic() - started, 1),
        "fleet_commit": head,
        "counts": counts,
        "excluded": excluded,
        "screenshots": len(shots),
    }


def plain(markdown: str, out: Path) -> None:
    """Markdown to plain text through pandoc, unwrapped so a heading stays on one line."""
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as handle:
        handle.write(markdown)
        staged = Path(handle.name)
    try:
        subprocess.run(
            [
                "pandoc",
                "--from=markdown-smart",
                "--to=plain",
                "--wrap=none",
                "-o",
                str(out),
                str(staged),
            ],
            check=True,
        )
    finally:
        staged.unlink(missing_ok=True)


def target(stage: Path | None, preview: Path | None) -> Path:
    """Where the folders go. Never under submissions/; a preview never under output/ either."""
    chosen = Path(stage or preview).expanduser()
    resolved = chosen.resolve()
    banned = [REPO / "submissions", OWNER / "submissions"]
    if preview is not None:
        banned += [REPO / "output", OWNER / "output"]
    for root in dict.fromkeys(p.resolve() for p in banned):
        if resolved == root or root in resolved.parents:
            where = "submissions/" if root.name == "submissions" else "output/"
            raise Refusal(f"{chosen} is under {where}, which this never writes")
    if stage is not None and not resolved.is_dir():
        raise Refusal(f"no stage at {chosen}")
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--stage", type=Path, help="a package stage to write the folders into")
    where.add_argument("--preview", type=Path, help="a scratch directory, never output/")
    where.add_argument("--measure", choices=sorted(MEASURES), help="print one Q2 measure")
    parser.add_argument(
        "--fleet",
        type=Path,
        default=Path(os.environ.get("ARK_FLEET") or DEFAULT_FLEET).expanduser(),
        help="the fleet checkout (default $ARK_FLEET, else ~/Documents/GitHub/ark-fleet)",
    )
    args = parser.parse_args(argv)
    try:
        if args.measure:
            sys.stdout.write(MEASURES[args.measure](inputs()))
            return 0
        root = target(args.stage, args.preview)
        done = build(root, args.fleet.resolve())
    except Refusal as exc:
        print(f"orq: refusing: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"orq: {exc.filename} is not installed or missing", file=sys.stderr)
        return 1
    counts = ", ".join(f"{n} {label}" for label, n in done["counts"].items())
    print(f"wrote {root / EN} and {root / ZH} in {done['seconds']} s")
    print(f"  fleet {done['fleet_commit'] or 'not a git checkout'}: {counts}")
    if done["excluded"]:
        print(f"  left out of Q1 as postdating 1995: {', '.join(done['excluded'])}")
    if not done["screenshots"]:
        print(f"  no screenshots cached in {SCREENSHOTS.relative_to(REPO)}: verify warns")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
