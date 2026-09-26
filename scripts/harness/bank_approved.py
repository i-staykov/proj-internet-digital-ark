"""Ingest every source class a human has newly approved, and nothing else.

**The problem this solves is a handover, not a computation.** A priced request can
sit at `pending` for hours or days while its journal waits on disk. When the answer
finally comes it is one word, and what has to happen next is mechanical: find the
spec, find the file, check nothing has read it already, ingest. Doing that by hand
at the end of a round, from a request block written days earlier, is how the wrong
file gets ingested under the right name.

**It refuses rather than guesses.** A class still `pending` is reported and skipped,
so this is safe to run early and often; that matters because the recipe that calls
it also ships the round, and a human should be able to rehearse the evening without
either banking something unapproved or being told the run failed.

**It reads three machine-readable lines out of the request block**, which is what
makes an approval merged from a phone bank something:

    - ingest spec: `some_spec`
    - journal: `data/raw/some/some.jsonl.gz`
    - refetch: https://host/path (then `uv run ark ingest some_spec <journal>`)

A corpus the fleet read whole carries one line instead, naming the directory its journal
parts were pulled into. It banks under its own source, its registrable half first and its
hostname records last, so a red gate's rollback of that source takes all of it back:

    - ingest: ark ingest-hostnames data/raw/fleet_read/<slug>/

The journal path is the file the measured figures were computed from, so a reviewer
who approved those figures approved that file. The refetch URL is the way back to
those bytes when the priced journal never reached this machine, which is the normal
case for a source the fleet priced elsewhere: the block is approved, the store is
here, and without the URL the merge banks nothing.

**A block it cannot bank is LOUD.** Silence is the failure mode this exists to
prevent: an approval that banks nothing looks exactly like an approval that banked.
So an approved class with no journal, no refetch and nothing already ingested is
printed under a banner naming what it lacked, and `--strict` turns that into a
non-zero exit for a human rehearsal. The unattended bank still exits 0, because
banking the other classes matters more than the exit status.

    uv run python scripts/harness/bank_approved.py          # report only
    uv run python scripts/harness/bank_approved.py --write  # refetch and ingest
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from ark.approvals import load  # noqa: E402
from ark.cdx import USER_AGENT  # noqa: E402
from ark.db import connect_read_only_patiently  # noqa: E402
from ark.evidence_types import MASTER_TYPES  # noqa: E402
from ark.hostnames import (  # noqa: E402
    FLEETREAD,
    FLEETREAD_REGISTRABLES,
    fleet_read_registrables_tag,
    fleet_read_source,
)
from ark.sources import SOURCES  # noqa: E402

APPROVALS = ROOT / "docs/registers/approved-sources-list.md"
DB = ROOT / "data/ark.duckdb"

_SPEC_LINE = re.compile(r"^- ingest specs?: (.+)$", re.M)
# The first whitespace-free token after the label, backticks stripped. Several live
# blocks write a parenthetical after the path ("19 of the 20 in-window captures"),
# and an anchored pattern read those as having no journal line at all.
_JOURNAL_LINE = re.compile(r"^- journals?: `?([^`\s]+)`?", re.M)
_REFETCH_LINE = re.compile(r"^- refetch: (.+)$", re.M)
_HOSTNAMES_LINE = re.compile(r"^- ingest: `?ark ingest-hostnames ([^`\s]+?)/?`?\s*$", re.M)
# The parts a fleet read writes, one source per lead (`ark.hostnames.fleet_read_source`).
READ_PARTS = "fleetread_*.jsonl.gz"
CONVERTER = "scripts/engines/cdx_suffix_convert.py"
_URL = re.compile(r"https?://[^\s`)]+")
_BACKTICKED = re.compile(r"`([^`]+)`")

# What a fetched artifact must not be. A wall or an interstitial answers with a
# perfectly plausible byte count, which is why the check is on content.
_HTML_HEAD = (b"<!doctype", b"<html", b"<?xml")
_HTML_SUFFIXES = (".html", ".htm", ".xml")


class RefetchFailed(RuntimeError):
    """The refetch URL did not yield the artifact, so nothing is ingested."""


@dataclass(frozen=True)
class Request:
    """The machine-readable half of one request block."""

    source_name: str
    evidence_type: str
    specs: tuple[str, ...] = ()
    journal: str = ""
    refetch: str = ""
    hostnames_dir: str = ""

    @property
    def label(self) -> str:
        return f"{self.source_name} / {self.evidence_type}"


@dataclass
class Plan:
    """What one run would do, before it does any of it.

    `blocked` is the loud list and stays short by construction: a class whose block
    never named bankable bytes is a documented state, not a failure, and goes to
    `notes` instead. Mixing the two is how a banner stops being read.
    """

    waiting: list[Request] = field(default_factory=list)
    ready: list[tuple[str, Path]] = field(default_factory=list)
    reads: list[tuple[str, Path]] = field(default_factory=list)
    done: list[tuple[str, str]] = field(default_factory=list)
    refetch: list[tuple[str, str, Path]] = field(default_factory=list)
    blocked: list[tuple[str, str]] = field(default_factory=list)
    notes: list[tuple[str, str]] = field(default_factory=list)


def block_for(text: str, source_name: str, evidence_type: str) -> str:
    """The request block for one class, or empty if it has none."""
    heading = f"### {source_name} / {evidence_type}"
    if heading not in text:
        return ""
    body = text.split(heading, 1)[1]
    return body.split("\n### ", 1)[0]


def spec_keys(line: str) -> tuple[str, ...]:
    """Candidate spec keys on an `- ingest spec:` line.

    Every backticked token, because the live blocks write prose around the key
    ("`ripe_dbase_1999`, reading `*dn:` and nothing else") and a comma split reads
    that prose as spec names. Which candidates are real is the registry's answer,
    not this parser's.
    """
    quoted = tuple(m.group(1).strip() for m in _BACKTICKED.finditer(line))
    return quoted or tuple(s.strip() for s in line.split(",") if s.strip())


def request_in(text: str, source_name: str, evidence_type: str) -> Request:
    """Parse the three lines out of one class's block."""
    block = block_for(text, source_name, evidence_type)
    specs = _SPEC_LINE.search(block)
    journal = _JOURNAL_LINE.search(block)
    refetch = _REFETCH_LINE.search(block)
    url = _URL.search(refetch.group(1)) if refetch else None
    hostnames = _HOSTNAMES_LINE.search(block)
    return Request(
        source_name=source_name,
        evidence_type=evidence_type,
        specs=spec_keys(specs.group(1)) if specs else (),
        journal=journal.group(1).strip() if journal else "",
        refetch=url.group(0) if url else "",
        hostnames_dir=hostnames.group(1).strip() if hostnames else "",
    )


def read_parts(path: Path, source_name: str) -> tuple[list[Path], str]:
    """The parts a complete read's receipt names, each on disk and each `source_name`'s,
    else why not. A `fleetread_` file the receipt does not name refuses the directory."""
    try:
        receipt = json.loads((path / "receipt.json").read_text(encoding="utf-8"))
        names = [str(part["name"]) for part in receipt["parts"]] if receipt["complete"] else []
    except (OSError, ValueError, KeyError, TypeError):
        names = []
    if not names or not all((path / name).is_file() for name in names):
        return [], "no complete read"
    if {p.name for p in path.glob(READ_PARTS)} != set(names):
        return [], "a part on disk is not the receipt's, or a named part is not a part"
    try:
        sources = {fleet_read_source(Path(name)) for name in names}
    except ValueError as exc:
        return [], str(exc)
    if {source for source, _ in sources} != {source_name}:
        return [], f"its parts are not all {source_name}'s"
    return [path / name for name in names], ""


def plan_read(request: Request, plan: Plan, root: Path, read: Callable[[str], set[str]]) -> None:
    """A fleet read's directory: bankable until every part its receipt names is in the ledger.

    The pull writes a directory only after the receipt said complete and every part matched
    its sha256. The hostname records bank last, so a part in the ledger means the registrable
    half before it banked too, and a bank that stopped part way runs again.
    """
    path = under(root, request.hostnames_dir)
    if path is None:
        plan.blocked.append(
            (request.label, f"read directory escapes the repository: {request.hostnames_dir}")
        )
        return
    parts, why = read_parts(path, request.source_name)
    if not parts:
        plan.blocked.append((request.label, f"{why} in {request.hostnames_dir} on this machine"))
        return
    banked = read(request.source_name)
    if all(part.name in banked for part in parts):
        plan.done.append((request.label, f"{len(parts)} part(s) of {path.name}"))
    else:
        plan.reads.append((request.label, path))


def under(root: Path, written: str) -> Path | None:
    """The journal path, or None if it points outside the repository.

    A request block arrives by pull request now, so the path in it is text somebody
    else wrote and `../..` in it must not become a write.
    """
    path = (root / written).resolve()
    return path if path.is_relative_to(root.resolve()) else None


def files_read(source_name: str) -> set[str]:
    """File names the ledger says this source has already been ingested from."""
    conn = connect_read_only_patiently(DB)
    try:
        rows = conn.execute(
            "SELECT file_name FROM ingested_file WHERE source_name = ?", [source_name]
        ).fetchall()
    finally:
        conn.close()
    return {row[0] for row in rows}


def plan_bank(
    text: str,
    approvals: dict,
    *,
    root: Path = ROOT,
    read: Callable[[str], set[str]],
    specs: dict = SOURCES,
) -> Plan:
    """Sort every master-eligible class into banked, bankable, refetchable or blocked.

    Pure apart from `read` and the filesystem check, so the run that reports and the
    run that acts read the same state, and running it twice over an unchanged tree
    plans exactly the same thing.
    """
    plan = Plan()
    for (source_name, evidence_type), approval in sorted(approvals.items()):
        if evidence_type not in MASTER_TYPES:
            continue
        if not block_for(text, source_name, evidence_type):
            continue  # decided before this mechanism existed; nothing to bank
        request = request_in(text, source_name, evidence_type)
        if approval.decision == "pending":
            plan.waiting.append(request)
            continue
        if approval.decision != "master":
            continue
        if request.hostnames_dir:
            plan_read(request, plan, root, read)
            continue

        keys = [key for key in request.specs if key in specs]
        if not keys:
            plan.notes.append((request.label, "no registered ingest spec, so nothing to bank"))
            continue
        # The heading names the ark source, and a spec key can name another, so ask
        # the ledger under both spellings before calling anything unbanked.
        already = set(read(source_name))
        for key in keys:
            already |= read(specs[key].source_name)

        if not request.journal:
            # Older blocks name their journals in prose. Nothing to bank once the
            # class has rows; loud while it has none.
            if already:
                plan.done.append((request.label, "no `- journal:` line, already ingested"))
            else:
                plan.blocked.append((request.label, "no `- journal:` line and no rows banked"))
            continue

        path = under(root, request.journal)
        if path is None:
            plan.blocked.append(
                (request.label, f"journal path escapes the repository: {request.journal}")
            )
            continue
        for key in keys:
            if path.name in already:
                # Checked before existence on purpose: a priced journal can be
                # deleted once its rows are in the store, and that is not a gap.
                plan.done.append((key, path.name))
            elif path.is_file():
                plan.ready.append((key, path))
            elif request.refetch:
                plan.refetch.append((key, request.refetch, path))
            else:
                plan.blocked.append(
                    (
                        request.label,
                        f"journal {request.journal} is not on this machine and the block"
                        " carries no `- refetch:` line",
                    )
                )
    return plan


def download(
    url: str,
    dest: Path,
    timeout: float = 300.0,
    opener: Callable = urllib.request.urlopen,
) -> int:
    """Stream one artifact to `dest` and return the bytes written.

    Writes a `.part` file and renames, so a truncated download is never a journal.
    A throttle is reported with its `Retry-After` and not slept through: the block
    stays a reason for the trigger, and the next bank asks again.
    """
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        raise RefetchFailed(f"not an http URL: {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    written, head = 0, b""
    try:
        with opener(request, timeout=timeout) as response, part.open("wb") as out:
            while chunk := response.read(1 << 20):
                head = head or chunk[:64].lower()
                out.write(chunk)
                written += len(chunk)
    except urllib.error.HTTPError as exc:
        part.unlink(missing_ok=True)
        wait = (exc.headers.get("Retry-After", "") if exc.headers else "") or "unstated"
        raise RefetchFailed(f"HTTP {exc.code}, Retry-After {wait}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        part.unlink(missing_ok=True)
        raise RefetchFailed(str(exc)) from exc
    if written == 0:
        part.unlink(missing_ok=True)
        raise RefetchFailed("the response was empty")
    if dest.suffix.lower() not in _HTML_SUFFIXES and head.startswith(_HTML_HEAD):
        part.unlink(missing_ok=True)
        raise RefetchFailed("the response is a page, not the artifact")
    part.replace(dest)
    return written


def run_refetches(
    items: list[tuple[str, str, Path]],
    fetch: Callable[[str, Path], int] = download,
) -> list[str]:
    """Fetch each absent journal from its `- refetch:` URL. One report line each."""
    lines = []
    for key, url, path in items:
        try:
            size = fetch(url, path)
        except RefetchFailed as exc:
            lines.append(f"  refetch FAILED for {key}: {exc}")
        else:
            lines.append(f"  refetched {path.name} for {key}: {size:,} bytes from {url}")
    return lines


def read_commands(path: Path, source_name: str, state: Path) -> list[list[str]]:
    """A whole read banks in three steps, every ingest under the read's own source:
    the exact-host converter, which leaves out error captures, writes its registrables under
    a tag named after the journal's sha256; they bank; then the parts bank as hostname
    records. The converter keeps its state in `state`, never the sweep's, so a retry reads
    the parts again."""
    parts, why = read_parts(path, source_name)
    if not parts:
        raise ValueError(f"{path}: {why}")
    receipt = json.loads((path / "receipt.json").read_text(encoding="utf-8"))
    found = FLEETREAD.match(parts[0].name)
    assert found is not None  # read_parts matched every name
    tag = fleet_read_registrables_tag(
        found.group("method"), found.group("slug"), str(receipt.get("journal_sha256") or "")
    )
    if not FLEETREAD_REGISTRABLES.match(Path(converted(tag)).name):
        raise ValueError(f"{path}: the receipt has no journal_sha256 to name its registrables")
    rel = path.relative_to(ROOT)
    return [
        [
            "uv",
            "run",
            "python",
            CONVERTER,
            "--glob",
            f"{rel}/{READ_PARTS}",
            "--tag",
            tag,
            "--state",
            str(state),
        ],
        ["uv", "run", "ark", "ingest", source_name, converted(tag)],
        ["uv", "run", "ark", "ingest", source_name, *(str(p.relative_to(ROOT)) for p in parts)],
    ]


def skip_reason(command: list[str]) -> str:
    """Why a read's step does not run: its registrables are already converted, from a bank
    that stopped after the converter, or the converter found none."""
    if CONVERTER in command:
        tag = command[command.index("--tag") + 1]
        return "its registrables are already converted" if (ROOT / converted(tag)).is_file() else ""
    if FLEETREAD_REGISTRABLES.match(Path(command[-1]).name) and not (ROOT / command[-1]).is_file():
        return "the read holds no exact-host registrable, nothing to convert"
    return ""


def converted(tag: str) -> str:
    """Where the converter writes a tag's registrables."""
    return f"data/raw/cdx/cdx_suffix_{tag}.jsonl.gz"


def report(plan: Plan, banner_limit: int = 10) -> None:
    """Everything the run decided, with the unbankable under a banner."""
    for request in plan.waiting:
        print(f"  still pending, not banked: {request.label}  ({request.journal})")
    for key, what in plan.done:
        print(f"  already banked: {key}  {what}")
    for key, url, path in plan.refetch:
        print(f"  journal absent for {key}: {path.name}, refetching from {url}")
    for label, path in plan.reads:
        print(f"  whole read ready for {label}: {path.relative_to(ROOT)}")
    if plan.notes:
        names = ", ".join(label for label, _ in plan.notes[:6])
        more = f" and {len(plan.notes) - 6} more" if len(plan.notes) > 6 else ""
        print(f"  no registered spec, nothing to bank ({len(plan.notes)}): {names}{more}")
    if not plan.blocked:
        return
    print(f"\n!! APPROVED AND NOT BANKED: {len(plan.blocked)}")
    for label, lacked in plan.blocked[:banner_limit]:
        print(f"!!   {label}: {lacked}")
    if len(plan.blocked) > banner_limit:
        print(f"!!   and {len(plan.blocked) - banner_limit} more")
    print("!! An approval that banks nothing is worse than a pending one: it reads as done.")
    print("!! Add the missing line to the block, or put the journal on this machine.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="run the refetches and ingests")
    ap.add_argument(
        "--strict", action="store_true", help="exit 1 if an approved class could not be banked"
    )
    args = ap.parse_args()

    text = APPROVALS.read_text(encoding="utf-8")
    approvals = load(APPROVALS)
    read = lru_cache(maxsize=None)(files_read)

    plan = plan_bank(text, approvals, root=ROOT, read=read)
    if plan.refetch and args.write:
        for line in run_refetches(plan.refetch):
            print(line)
        read.cache_clear()
        plan = plan_bank(
            text, approvals, root=ROOT, read=read
        )  # once: the bytes either came or did not
    report(plan)

    if not plan.ready and not plan.reads:
        print("nothing newly approved to bank.")
        if plan.blocked and args.strict:
            raise SystemExit(1)
        return

    jobs = [
        (key, [["uv", "run", "ark", "ingest", key, str(path.relative_to(ROOT))]])
        for key, path in plan.ready
    ]
    with tempfile.TemporaryDirectory() as scratch:
        for label, path in plan.reads:
            source_name = label.split(" / ", 1)[0]
            state = Path(scratch) / f"{path.name}.convert.tsv"
            jobs.append((label, read_commands(path, source_name, state)))
        for key, commands in jobs:
            for command in commands:
                if not args.write:
                    print("  would run: " + " ".join(command))
                    continue
                if why := skip_reason(command):
                    print(f"  {key}: {why}")
                    continue
                print("== " + " ".join(command))
                result = subprocess.run(command, cwd=ROOT, check=False)
                if result.returncode != 0:
                    raise SystemExit(f"ingest failed for {key}; stopping before anything else runs")

    if not args.write:
        print("\ndry run. Pass --write to refetch and ingest.")
    if plan.blocked and args.strict:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
