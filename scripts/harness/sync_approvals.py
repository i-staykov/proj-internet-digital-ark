"""Turn every source waiting on a human into one issue and one mergeable pull request.

**Why a pull request is the approval.** The register's `Decision:` line is what the ingest
gate reads, so approving a source means editing one line of one file. That is a one-tap merge
on a phone, it is auditable afterwards, and it cannot be misread: nothing is approved until
the line changes, and the line changes only by merging. Ivo asked for exactly this rather than
for a reply he then has to remember to act on (2026-09-08).

**Why the reasoning lives elsewhere.** The pull request carries the one-line diff and nothing
else, because the project repository is public. The measurement, the condition that failed and
the terms question go in the private fleet issue that links to it.

**The filing floor is the bar, not a token.** Four issues sat open for a week at four and five
figures and were closed unread, because a source under the bar is not worth a decision (Ivo,
2026-09-08). Below it the register block is the whole record.

    uv run python scripts/harness/sync_approvals.py [--dry-run] [--floor 5000]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from ark import approvals  # noqa: E402

REGISTER = REPO / "docs/registers/approved-sources-list.md"
PROJECT = "i-staykov/proj-internet-digital-ark"
FLEET = "i-staykov/ark-fleet"
# The fleet's other asks for the owner carry this label too, so an open issue under it is
# this script's only when its title is one `Request.title` writes, which `_TITLE` matches.
LABEL = "needs-owner"
_TITLE = re.compile(r"^Approve (.+)\? [\d,]+ EE$")
# The standing bar for a lead worth a decision.
DEFAULT_FLOOR = 5_000.0
_POTENTIAL = re.compile(r"^-\s*potential:\s*([\d,\.]+)", re.M)
# The reasons `fleet_request.py` writes into a block the standing rule parks.
_PARKED = re.compile(r"^-\s*parked:\s*(.+)$", re.M)
# Which of the four conditions of the standing rule a human can actually settle. 1 is the
# evidence class and 3 is the terms: both are judgements only Ivo makes. 2 is a missing stamp
# and 4 is a missing ingest, which are WORK, and an issue asking him to approve work he has
# not been given is noise. Those stay in the register until the work is done.
HUMAN_CONDITIONS = ("1", "3")
# The sentence that says what is BLOCKING, which is the only place a condition number means
# "failed". Reading the whole block inverts it: one block says conditions 1 to 3 hold and only
# 4 does not, so the numbers near the word "condition" are as often the passing ones.
_FAILED = re.compile(r"[^\n]*conditions?[^\n]*(?:fail|not held|cannot be evaluated)[^\n]*", re.I)


def failed_conditions(block: str) -> set[str]:
    """The condition numbers the block's own blocking sentence names."""
    sentence = _FAILED.search(block)
    return set(re.findall(r"\b([1-4])\b", sentence.group(0))) if sentence else set()


@dataclass(frozen=True)
class Request:
    source: str
    etype: str
    line: int
    potential: float
    failed: str
    block: str

    @property
    def slug(self) -> str:
        return re.sub(r"[^a-z0-9]+", "-", self.source.lower()).strip("-")

    @property
    def branch(self) -> str:
        return f"approve/{self.slug}"

    @property
    def title(self) -> str:
        return f"Approve {self.source}? {self.potential:,.0f} EE"


def blocks(text: str) -> dict[str, str]:
    """Each request block, keyed by its source name."""
    out: dict[str, str] = {}
    for chunk in re.split(r"\n(?=### )", text):
        if not chunk.startswith("### "):
            continue
        head = chunk[4:].split("\n", 1)[0]
        out[head.split("/")[0].strip()] = chunk
    return out


def requests(floor: float) -> list[Request]:
    """Pending sources at or above the floor, with the figures their block carries."""
    text = REGISTER.read_text(encoding="utf-8")
    by_source = blocks(text)
    out: list[Request] = []
    for approval in approvals.pending(REGISTER):
        block = by_source.get(approval.source_name, "")
        found = _POTENTIAL.search(block)
        potential = float(found.group(1).replace(",", "")) if found else 0.0
        if potential < floor:
            continue
        reason = _FAILED.search(block)
        parked = _PARKED.search(block)
        numbers = failed_conditions(block)
        if numbers and not numbers & set(HUMAN_CONDITIONS):
            continue
        out.append(
            Request(
                source=approval.source_name,
                etype=approval.evidence_type,
                line=approval.line,
                potential=potential,
                failed=(
                    f"parked by the standing rule: {parked.group(1).strip()}"
                    if parked
                    else reason.group(0).strip(" *")
                    if reason
                    else "not stated in the block"
                ),
                block=block,
            )
        )
    return out


def gh(args: list[str], check: bool = True) -> str:
    done = subprocess.run(["gh", *args], capture_output=True, text=True)
    if check and done.returncode:
        raise RuntimeError(f"gh {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout.strip()


def open_prs() -> dict[str, str]:
    """Branch name to pull request number, for the approval branches already out."""
    rows = json.loads(
        gh(
            [
                "pr",
                "list",
                "--repo",
                PROJECT,
                "--state",
                "open",
                "--json",
                "number,headRefName",
                "--limit",
                "100",
            ]
        )
        or "[]"
    )
    return {r["headRefName"]: str(r["number"]) for r in rows}


def open_issues() -> dict[str, str]:
    """Issue title to number, for every open issue under the label, this script's and others'.

    The limit sits far past the open asks, because the label is shared. A title search would
    narrow it, but it reads GitHub's index, which can lag an issue just filed, and a run that
    misses its own issue files it twice.
    """
    rows = json.loads(
        gh(
            [
                "issue",
                "list",
                "--repo",
                FLEET,
                "--state",
                "open",
                "--label",
                LABEL,
                "--json",
                "number,title",
                "--limit",
                "1000",
            ]
        )
        or "[]"
    )
    return {r["title"]: str(r["number"]) for r in rows}


def live_register() -> str:
    """The register as `origin/live` holds it, which is what an approval branch starts from."""
    rel = REGISTER.relative_to(REPO).as_posix()
    return subprocess.run(
        ["git", "show", f"origin/live:{rel}"], cwd=REPO, check=True, capture_output=True, text=True
    ).stdout


def approve_line(request: Request, text: str) -> str | None:
    """`text`, a register, with this one source's pending decision flipped, or None when the
    source has no pending block in it.

    The text is live's copy, never the checkout's. A bank writes a block and runs this before
    it pushes, so the checkout's copy holds that block and the bank's other register edits,
    and a pull request built from it would carry all of them rather than one line.
    """
    lines = text.splitlines(keepends=True)
    head = re.compile(rf"###\s+{re.escape(request.source)}\s+/\s+{re.escape(request.etype)}\s*")
    start = next((i for i, line in enumerate(lines) if head.fullmatch(line.rstrip("\n"))), None)
    if start is None:
        return None
    for index in range(start + 1, len(lines)):
        if lines[index].startswith("### "):
            break
        if lines[index].startswith("Decision: pending"):
            lines[index] = "Decision: master\n"
            return "".join(lines)
    return None


def raise_pr(request: Request, dry_run: bool) -> str | None:
    """One branch, one line changed, one pull request whose merge is the approval. None when
    live holds no pending block for the source yet: the run after the push files it.

    Built in a throwaway worktree so the checkout this runs in is never touched: the fleet
    calls this from a clone it is also using for other work.
    """
    if dry_run:
        return f"would open {request.branch}"
    flipped = approve_line(request, live_register())
    if flipped is None:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp) / "approve"
        subprocess.run(
            ["git", "worktree", "add", "-q", "-b", request.branch, str(tree), "origin/live"],
            cwd=REPO,
            check=True,
            capture_output=True,
        )
        try:
            (tree / REGISTER.relative_to(REPO)).write_text(flipped, encoding="utf-8")
            subprocess.run(["git", "add", str(REGISTER.relative_to(REPO))], cwd=tree, check=True)
            subprocess.run(
                [
                    "git",
                    "commit",
                    "-q",
                    "--no-verify",
                    "-m",
                    f"Approve {request.source} for the annual master",
                ],
                cwd=tree,
                check=True,
            )
            subprocess.run(
                ["git", "push", "-q", "-u", "origin", request.branch], cwd=tree, check=True
            )
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(tree)],
                cwd=REPO,
                check=False,
                capture_output=True,
            )
    body = (
        f"Approving {request.source} for the annual master.\n\n"
        f"Measured potential: {request.potential:,.0f} equivalent-English net-new.\n\n"
        "**Merging this grants the approval.** It flips the one `Decision:` line the ingest "
        "gate reads and changes nothing else. No ingest happens on merge; the next bank does "
        "that.\n\nClose it unmerged to leave the source pending.\n"
    )
    return gh(
        [
            "pr",
            "create",
            "--repo",
            PROJECT,
            "--base",
            "live",
            "--head",
            request.branch,
            "--title",
            f"Approve {request.source}",
            "--body",
            body,
        ]
    )


def raise_issue(request: Request, pr_url: str, dry_run: bool) -> str:
    body = (
        f"**{request.source}** / {request.etype}, measured {request.potential:,.0f} EE net-new.\n\n"
        f"Blocked on: {request.failed}\n\n"
        f"### Approve from your phone\n\nMerge {pr_url}. That flips the `Decision:` line the "
        "ingest gate reads, and nothing else. Close it unmerged to leave the source pending.\n\n"
        "<details><summary>The register block, verbatim</summary>\n\n"
        f"```\n{request.block.strip()}\n```\n\n</details>\n"
    )
    if dry_run:
        return f"would file, labelled {LABEL}: {request.title}"
    return gh(
        [
            "issue",
            "create",
            "--repo",
            FLEET,
            "--title",
            request.title,
            "--label",
            LABEL,
            "--body",
            body,
        ]
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="say what it would do, change nothing")
    ap.add_argument(
        "--floor", type=float, default=DEFAULT_FLOOR, help="EE below which nothing is filed"
    )
    args = ap.parse_args(argv)

    wanted = requests(args.floor)
    prs, issues = ({}, {}) if args.dry_run else (open_prs(), open_issues())
    decided = {a.source_name for a in approvals.load(REGISTER).values() if a.decision != "pending"}
    # Keyed on the source, not the whole title: the title carries the potential, and a block
    # re-priced since its issue was filed is still the one ask.
    asked = {own.group(1): title for title in issues if (own := _TITLE.match(title))}

    for request in wanted:
        if request.source in asked:
            print(f"open already: {asked[request.source]}")
            continue
        pr = prs.get(request.branch) or raise_pr(request, args.dry_run)
        if pr is None:
            print(f"not on live yet: {request.title}, filed on the run after the push")
            continue
        print(f"pull request: {pr}")
        print(f"issue: {raise_issue(request, pr, args.dry_run)}")

    for title, number in issues.items():
        own = _TITLE.match(title)
        if not own:
            continue  # another ask under the shared label, never this script's to close
        source = own.group(1)
        if source in decided:
            if args.dry_run:
                print(f"would close #{number}: {source} is decided")
                continue
            gh(
                [
                    "issue",
                    "close",
                    number,
                    "--repo",
                    FLEET,
                    "--comment",
                    f"Decided in the register: {source} is no longer pending.",
                ]
            )
            print(f"closed #{number}: {source}")

    if not wanted:
        print(f"nothing pending at or above {args.floor:,.0f} EE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
