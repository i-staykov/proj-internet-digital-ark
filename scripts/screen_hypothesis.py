"""Kill a source proposal before it costs a request.

`docs/discovery.md` says the dead-lead register is an input rather than an
afterthought, and that an automated discovery agent will walk straight back into
roughly fifty closed families unless it reads that register first. Reading a
1,500-line document is the cheapest step in the process and also the one most
likely to be skipped, so this does it mechanically.

Two gates, in the order that costs least:

**1. Does it collide with something already closed?** The register is parsed out of
`docs/sources.md` at run time and never copied, because a hand-kept second copy of
those verdicts is how they come to disagree: a snapshot table in that same file
once omitted the round's largest contributor entirely. A collision prints the
verdict that closed it, so the proposer can argue with the measurement rather than
rediscover it.

**2. Does each item carry its own date?** This is the fastest filter available and
it decides what the source can ever be, not just how good it is:

    self-dating       a capture timestamp, a registry creation date, a dated
                      listing. The record is the authority, so no corroboration
                      split, and widening extraction here is NOT safe.
    typed-in-artifact a hostname a human wrote inside a dated artifact. Takes the
                      corroboration split, which is what makes wide extraction
                      safe at all.
    undated           seed-only. It can still be valuable, since the CDX and RDAP
                      engines date candidates, but it scores nothing until they do.

It deliberately does not price anything. Pricing is a sample measured against the
live store, per source, and a generic pricer would have to guess at a parser.
What this removes is the step before that, which is the one that wastes days.

    uv run python scripts/screen_hypothesis.py "shareware CD-ROM ISO catalogues"
    uv run python scripts/screen_hypothesis.py --dating undated "a 1998 link dump"
    uv run python scripts/screen_hypothesis.py --list-closed
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCES_MD = ROOT / "docs" / "sources.md"

DATING = {
    "self": (
        "self-dating: the record is the authority for the year",
        [
            "No corroboration split. The record dates itself.",
            "Widening extraction here is NOT safe: there is no wall behind the pattern,",
            "so a bad match becomes a master claim. Tighten rather than widen.",
        ],
    ),
    "typed": (
        "typed inside a dated artifact: a human wrote the hostname",
        [
            "Takes the corroboration split. Admitted only if another source already",
            "places that domain in an annual file; otherwise the name goes to the pool.",
            "Widening recall IS safe here, because the split and not the pattern is the wall.",
        ],
    ),
    "undated": (
        "undated: no per-item year evidence",
        [
            "Seed-only, and say so plainly rather than counting it as an addition.",
            "It can still pay: the CDX and RDAP engines date candidates, and the",
            "reviewer asked for the pool to be as large as practicable.",
        ],
    ),
}

# Words too common in this domain to discriminate. Without this, 'archive' alone
# collides with two thirds of the register and the tool reads as useless.
STOP = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "in",
    "on",
    "for",
    "from",
    "to",
    "with",
    "by",
    "at",
    "its",
    "it",
    "is",
    "as",
    "that",
    "this",
    "any",
    "all",
    "new",
    "old",
    "other",
    "more",
    "data",
    "dataset",
    "datasets",
    "source",
    "sources",
    "list",
    "lists",
    "index",
    "indexes",
    "page",
    "pages",
    "site",
    "sites",
    "web",
    "internet",
    "historical",
    "history",
    "domain",
    "domains",
    "hostname",
    "hostnames",
    "url",
    "urls",
    "year",
    "years",
    "early",
    "http",
    "https",
    "www",
    "com",
    "net",
    "org",
    "file",
    "files",
    "public",
    "free",
    "open",
    "bulk",
    "collection",
    "collections",
    "archive",
    "archives",
    "archived",
    "crawl",
    "crawls",
    # generic nouns that name no source: "Apache project release announcements"
    # matched "OCLC Web Characterization Project" on `project` alone
    "project",
    "projects",
    "programme",
    "program",
    "record",
    "records",
    "entry",
    "entries",
    "metadata",
    "content",
}


@dataclass(frozen=True)
class Closed:
    """One closed lead: what it was called and the verdict that killed it."""

    name: str
    verdict: str
    line: int

    def tokens(self) -> set[str]:
        return _tokens(self.name)


# A year or a year range says when, never what, so it must not discriminate. Found
# by using the tool: "INET proceedings 1996-2001" collided with "SEC EDGAR filings
# 1996-2001" on nothing but the window, and `1996-2001` occurs in exactly one
# register entry, so the single-rare-token rule fired on it.
_NUMERIC = re.compile(r"^[0-9][0-9.\-]*$")


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9][a-z0-9.\-]{2,}", text.lower())
    kept = {w.strip(".-") for w in words}
    return {w for w in kept if w and w not in STOP and not _NUMERIC.match(w)}


def closed_leads(path: Path = SOURCES_MD) -> list[Closed]:
    """Parse the register out of `docs/sources.md`, never a second copy of it.

    Three shapes carry a verdict in that file and all three are read: rows of the
    `Evaluated and rejected` table, `## ` sections whose heading says rejected,
    and an inline `**Verdict: REJECT ...**` inside any section.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[Closed] = []
    seen: set[str] = set()

    def add(name: str, verdict: str, number: int) -> None:
        # One lead, one entry. NYPW carries both a heading and an inline verdict,
        # and reporting it twice makes a single collision look like two.
        if name and name not in seen:
            seen.add(name)
            out.append(Closed(name, verdict, number))

    in_table = False
    section = ""
    for number, line in enumerate(lines, start=1):
        if line.startswith("## "):
            section = line[3:].strip()
            in_table = section.lower().startswith("evaluated and rejected")
            # the container heading is not itself a lead
            if "reject" in section.lower() and not in_table:
                add(section, "section heading records a rejection", number)
            continue
        if in_table and line.startswith("|") and line.count("|") >= 3:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 2 or cells[0] in {"Source", "---"} or set(cells[0]) <= {"-"}:
                continue
            add(cells[0], cells[1], number)
            continue
        if "Verdict: REJECT" in line:
            add(section or line.strip(), line.strip(" -*"), number)
    return out


def collisions(proposal: str, register: list[Closed], floor: int = 2) -> list[tuple[int, Closed]]:
    """Closed leads sharing at least `floor` discriminating words with the proposal.

    Two words rather than one on purpose. One word matches far too much to be
    read, and zero words would make the check decorative. A single rare word can
    still match, since a token like `ircache` or `geocities` appears in only one
    entry, so `floor` counts overlap and the ranking puts the strongest first.
    """
    want = _tokens(proposal)
    scored = []
    for entry in register:
        shared = want & entry.tokens()
        # a single distinctive token is enough when it is distinctive: any token
        # occurring in exactly one register entry carries the same weight as two
        if len(shared) >= floor or (len(shared) == 1 and _rare(next(iter(shared)), register)):
            scored.append((len(shared), entry))
    return sorted(scored, key=lambda pair: -pair[0])


def _rare(token: str, register: list[Closed]) -> bool:
    return sum(1 for entry in register if token in entry.tokens()) == 1


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("proposal", nargs="*", help="what the source is, in words")
    ap.add_argument(
        "--dating",
        choices=sorted(DATING),
        help="what dates ONE item: self, typed, or undated. If you cannot say, it is undated.",
    )
    ap.add_argument("--list-closed", action="store_true", help="print the whole closed register")
    args = ap.parse_args()

    register = closed_leads()
    if args.list_closed:
        print(f"{len(register)} closed leads in {SOURCES_MD.relative_to(ROOT)}\n")
        for entry in register:
            print(f"  L{entry.line:<5} {entry.name}")
        return

    proposal = " ".join(args.proposal).strip()
    if not proposal:
        raise SystemExit("say what the source is, in words, or pass --list-closed")

    print(f"proposal: {proposal}\n")
    print(f"== gate 1: the closed register ({len(register)} leads) ==")
    hits = collisions(proposal, register)
    if hits:
        for shared, entry in hits[:5]:
            print(f"\n  COLLIDES ({shared} shared terms) with docs/sources.md:{entry.line}")
            print(f"    {entry.name}")
            verdict = re.sub(r"\s+", " ", entry.verdict)
            print(f"    verdict: {verdict[:400]}{'...' if len(verdict) > 400 else ''}")
        if len(hits) > 5:
            print(f"\n  ... and {len(hits) - 5} weaker collisions")
        print("\n  Read the verdict before proceeding. If it is genuinely a different")
        print("  population, say how in one sentence and record that beside the proposal.")
    else:
        print("  no collision. That is not a green light, it is the absence of a red one.")

    print("\n== gate 2: what dates one item ==")
    if args.dating is None:
        print("  NOT STATED. Pass --dating self|typed|undated.")
        print("  If you cannot answer it in one sentence, the source is seed-only and")
        print("  the conversation is over, per docs/discovery.md section 3.")
        sys.exit(2)
    label, notes = DATING[args.dating]
    print(f"  {label}")
    for note in notes:
        print(f"    {note}")

    print("\n== next, and not before ==")
    print("  Price it: sample it, measure against the LIVE store, and report net-new")
    print("  pairs, net-new domains and the mean weight of the net-new part. Bar is")
    print("  ~5,000 net-new pairs and mean weight 0.6 good, below 0.4 needs a volume")
    print("  argument. Label any projection in the same sentence as the number, and")
    print("  fit the saturation curve as well as the line: a 120-archive pilot once")
    print("  projected 1.9M equivalent-English against a true 62,821.")


if __name__ == "__main__":
    main()
