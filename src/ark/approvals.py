"""Which source classes a human has approved for the annual files, and the gate.

**The problem this solves.** The pipeline can measure a source without help, and it
cannot decide whether that source's records belong in the annual files. That is a
judgement about what counts as proof, and the thing being distrusted in an
unattended run is precisely **the agent's own reasoning about its own sources**. An
ADR written by the agent arguing that its find is master evidence is the least
trustworthy artifact in the repository.

So the classification is a human decision, taken from external evidence, recorded
in `docs/approved-sources-list.md`, and **enforced here rather than remembered**.

**Where the quarantine lives, and why it is outside the store.** Collectors already
write journals and never open the database, so "collected but not yet classified"
needs no new state: the journal sits on disk and this gate refuses the ingest. That
is strictly stronger than a flag inside the store, because an unapproved source
**cannot contaminate anything, having never been written**, rather than relying on
every future query to respect a marker. It is also less code.

**What needs approval and what does not.**

- A source whose evidence type is **master-eligible** needs approval, because its
  rows can create a year assignment.
- A source whose evidence type is **candidate-only** does not. A candidate claims
  nothing, the reviewer asked for the pool to be as large as practicable, and
  waiting on a human to grow a pool would stall collection for no gain.

**The decision vocabulary**, one line per request in `docs/approved-sources-list.md`:

    Decision: pending          nobody has looked yet; ingest refuses
    Decision: master           approved for the annual files
    Decision: candidate-only   collect it, but its rows may never date a year
    Decision: rejected         do not ingest at all, and do not re-request

`rejected` binds: the gate refuses it and the request generator refuses to re-open
it, because an agent that forgets a rejection re-proposes it next week.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from ark.evidence_types import MASTER_TYPES

# Module-level rather than a default argument bound at import, so a test can point
# the gate at a fixture file. Production code never reassigns it.
DEFAULT_APPROVALS_PATH = Path("docs/approved-sources-list.md")

DECISIONS = ("pending", "master", "candidate-only", "rejected")
_REQUEST_RE = re.compile(r"^###\s+(?P<source>\S+)\s+/\s+(?P<etype>\S+)\s*$")
_DECISION_RE = re.compile(r"^\s*Decision:\s*(?P<value>[a-z-]+)\s*$", re.IGNORECASE)


class NotApproved(RuntimeError):
    """Raised when a master-eligible ingest has no human approval behind it."""


@dataclass(frozen=True)
class Approval:
    source_name: str
    evidence_type: str
    decision: str
    line: int

    @property
    def may_ingest(self) -> bool:
        return self.decision in ("master", "candidate-only")

    @property
    def may_date_a_year(self) -> bool:
        return self.decision == "master"


def load(path: Path | str | None = None) -> dict[tuple[str, str], Approval]:
    """Parse `docs/approved-sources-list.md`, keyed by (source name, evidence type).

    The file is the single source of truth and is edited by a human: a reviewer
    changes one `Decision:` line. Parsing it rather than keeping a second machine
    file means the record a person reads and the record the gate enforces cannot
    disagree, which is the failure mode `sources.md` already carries a scar from.
    """
    path = Path(path) if path is not None else DEFAULT_APPROVALS_PATH
    if not path.exists():
        return {}
    out: dict[tuple[str, str], Approval] = {}
    key: tuple[str, str] | None = None
    heading_line = 0
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        found = _REQUEST_RE.match(raw)
        if found:
            key = (found.group("source"), found.group("etype"))
            heading_line = number
            continue
        decided = _DECISION_RE.match(raw)
        if decided and key is not None:
            value = decided.group("value").lower()
            if value in DECISIONS:
                out[key] = Approval(key[0], key[1], value, heading_line)
            key = None
    return out


def check(
    source_name: str,
    evidence_type: str,
    path: Path | str | None = None,
) -> None:
    """Raise `NotApproved` unless this class may be ingested. Silent when it may.

    Candidate-only evidence passes without a lookup: it cannot date a year, so a
    human gains nothing by gating it and collection would stall for no reason.
    """
    if evidence_type not in MASTER_TYPES:
        return
    path = Path(path) if path is not None else DEFAULT_APPROVALS_PATH
    approvals = load(path)
    approval = approvals.get((source_name, evidence_type))
    if approval is None:
        raise NotApproved(
            f"{source_name} / {evidence_type} has no entry in {path}.\n"
            f"This evidence type can date a year, so a human must classify it first.\n"
            f"Write the request with:\n"
            f"  uv run python scripts/request_approval.py {source_name} --journal <journal>\n"
            f"then set its `Decision:` line to master, candidate-only or rejected."
        )
    if approval.decision == "pending":
        raise NotApproved(
            f"{source_name} / {evidence_type} is awaiting classification "
            f"({path}:{approval.line}).\n"
            f"The journal is on disk and nothing is lost: ingest again once the "
            f"`Decision:` line says master, candidate-only or rejected."
        )
    if approval.decision == "rejected":
        raise NotApproved(
            f"{source_name} / {evidence_type} was REJECTED by a reviewer "
            f"({path}:{approval.line}).\n"
            f"A rejection binds. Do not re-request it without new external evidence, "
            f"and record that evidence if you do."
        )
    if approval.decision == "candidate-only":
        raise NotApproved(
            f"{source_name} / {evidence_type} is approved as candidate-only "
            f"({path}:{approval.line}), but this spec's evidence type is "
            f"master-eligible.\n"
            f"Point the ingest at the candidate-only spec for this source, or ask "
            f"for the class to be raised to master with fresh evidence."
        )


def pending(path: Path | str | None = None) -> list[Approval]:
    """Everything waiting on a human, for the state document to surface."""
    return sorted(
        (a for a in load(path).values() if a.decision == "pending"),
        key=lambda a: a.line,
    )
