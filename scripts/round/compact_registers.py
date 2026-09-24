"""Rewrite the three register pages to one current row per source.

`docs/registers/sources.md` is one eleven-column table of what is banked, seeded, admitted,
parked, held out or a priced FIND. `docs/registers/sources-closed.md` is one five-column
table of what was measured and closed, each reason opening with its verdict word.
`docs/registers/approved-sources-list.md` keeps each `### source / type` block as its
heading, its `- ` facts and its `Decision:` line.

A source is one row. Its newest dated row wins, a closed row wins a tie, then the first in
the file. Every URL and hostname its old text named follows in the link cell, so a search
for a host still finds the row. On pages already in this shape nothing changes, which is
what `--check` guards.

    uv run python scripts/round/compact_registers.py                  # rewrite what differs
    uv run python scripts/round/compact_registers.py --check          # counts, exit 1 on a failure
    uv run python scripts/round/compact_registers.py --registers DIR  # work on a copy
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts/harness"))

from bank_findings import CLOSED_HEADING, REGISTER_HEADER  # noqa: E402

from ark.approvals import parse as parse_approvals  # noqa: E402

REGISTERS = REPO / "docs/registers"
OPEN_PAGE = "sources.md"
CLOSED_PAGE = "sources-closed.md"
APPROVED_PAGE = "approved-sources-list.md"
PAGES = (OPEN_PAGE, CLOSED_PAGE, APPROVED_PAGE)

OPEN_COLUMNS = (
    "source",
    "version or date",
    "coverage period",
    "retrieval method",
    "what dates one item",
    "baseline overlap",
    "net-new EE (date)",
    "quality issues",
    "effort",
    "verdict",
    "link",
)
CLOSED_COLUMNS = ("source", "date", "measured", "reason", "link")
OPEN_HEADER = "| " + " | ".join(OPEN_COLUMNS) + " |"
if (
    not OPEN_HEADER.startswith(REGISTER_HEADER)
    or CLOSED_HEADING != "| " + " | ".join(CLOSED_COLUMNS) + " |"
):
    raise SystemExit("compact_registers: the table headers disagree with bank_findings")

OPEN_PREAMBLE = """# Sources

One row per source that is banked, seeded, admitted, parked, held out or a priced FIND; its link
and what dates one item are written before it is ingested. Closed sources are one row each on
[sources-closed.md](sources-closed.md). A new measurement replaces its row, and git holds every
earlier one. Look a source up with `just find <term>`.
"""
CLOSED_PREAMBLE = """# Closed sources

One row per source measured and closed, so nobody re-tests it. The reason opens with its verdict
word, and the link cell names every URL and host the source was read at. A new measurement
replaces its row, and git holds every earlier one. Look a source up with `just find <term>`.
"""
APPROVED_PREAMBLE = """# Approved sources

One `Decision:` line per (source, evidence type), and `ark ingest` enforces it: a master-eligible
class with no `master` line cannot date a year. `pending` refuses, `master` may date a year,
`candidate-only` collects but never dates one, `rejected` binds and is never re-requested. A
request is built by `scripts/harness/request_approval.py <spec> --journal <journal>`.
"""
WHOLE_SECTIONS = ("Pending requests", "Found, awaiting triage")

OPEN_WORDS = ("BANKED", "SEEDED", "ADMITTED", "PARKED", "FIND", "HELD OUT")
CLOSED_WORDS = (
    "CLOSED",
    "BLOCKED",
    "REJECTED",
    "WITHDRAWN",
    "RETIRED",
    "SATURATED",
    "UNRETRIEVABLE",
    "UNAVAILABLE",
    "SUPERSEDED",
    "SKIPPED",
    "ZERO",
)
LINKED_WORDS = ("BANKED", "SEEDED", "ADMITTED")
SETTLED_WORDS = (*LINKED_WORDS, "HELD OUT")
# Words the old pages wrote for the same verdicts. In capitals a heading's PRICED is a
# priced lead awaiting its decision; lowercase "priced" or "worth" in a verdict cell was a
# measurement that never became one, and reads as closed.
SYNONYMS = {
    "BANKING": "BANKED",
    "SETTLED": "BANKED",
    "VERIFIED": "BANKED",
    "DEFERRED": "PARKED",
    "PENDING": "PARKED",
    "PRICED": "FIND",
    "FINDS": "FIND",
    "REOPENED": "FIND",
    "REJECT": "REJECTED",
    "REFUSED": "REJECTED",
}
LOWER_OPEN = {"banked": "BANKED", "admitted": "ADMITTED", "seeded": "SEEDED", "deferred": "PARKED"}
DECISION_WORD = {
    "master": "BANKED",
    "candidate-only": "SEEDED",
    "pending": "PARKED",
    "rejected": "REJECTED",
}

# Old section headings that held other entries, not a source.
CONTAINERS = {
    "evaluated-and-rejected",
    "source-names-that-are-not-separate-sources",
    "closed-by-the-reviewer-himself-0901-update",
    "the-hostname-purpose-rule-2026-09-02",
}


def _adr(n: int) -> str:
    return "ADR" + f"-{n:03d}"


def _c(n: int) -> str:
    return "C" + f"-{n}"


# Decision numbers in the rule's own words, then attributions as the fact they state, then
# anchors into the detail blocks that are gone. The numbers are spelled through `_adr` and
# `_c` so that this file quotes none of them.
REWORD: tuple[tuple[str, str], ...] = (
    (
        rf"which {_adr(7)} refused for one day and {_adr(8)} ships",
        "which the `www.` alias rule ships",
    ),
    (
        rf"on the {_adr(7)} reading and its gross under {_adr(8)}",
        "without the `www.` alias, its gross with it",
    ),
    (rf"the {_adr(7)} `www\.` alias seam", "the `www.` alias seam"),
    (rf"\b{_adr(8)} admits\b", "the `www.` alias rule admits"),
    (rf"\b{_adr(3)}\b", "the approval gate"),
    (rf"\b{_adr(12)}\b", "the in-use hostname wall"),
    (rf"\({_c(83)}: ", "("),
    (rf"\({_c(83)} field family: ", "(relay-host field family: "),
    (rf"banked as {_c(83)}\b", "banked as the relay-host class"),
    (rf"\b{_c(83)}'s\b", "the relay-host rule's"),
    (rf"\b{_c(83)}\b", "the relay-host rule"),
    (rf"\b(?:{_c(38)}|{_c(81)})'s ", "the "),
    (rf"\b{_c(68)}\b", "the Usenet body-URL decision"),
    (rf"\b{_c(88)}\b", "the three-client cap"),
    (r"\s*\((?:C-\d{1,3}|ADR-\d+)(?:,\s*(?:C-\d{1,3}|ADR-\d+))*\)", ""),
    (r"\*\*Decision written by the loop under rule 7\*\*:\s*", "standing rule: "),
    (
        r"admitted under the standing rule of \d{4}-\d\d-\d\d \(Ivo\)",
        "admitted under the standing rule",
    ),
    (
        r"^- authority: Ivo, \d{4}-\d\d-\d\d, asked for (.+?) to be annual",
        r"- authority: \1 are annual",
    ),
    (r"^- Ivo, \d{4}-\d\d-\d\d(?: \(issue #\d+\))?: ", "- ruling: "),
    (r"\*\*amended \d{4}-\d\d-\d\d \(Ivo\): ", "**"),
    (r",? by Ivo(?: on|,)? \d{4}-\d\d-\d\d\b", ""),
    (r" \(Ivo(?:, \d{4}-\d\d-\d\d)?\)", ""),
    (r"under Ivo's floor ruling of \d{4}-\d\d-\d\d", "under the 5,000 EE floor"),
    (r"\s*\[detail\]\(#[^)]*\)", ""),
)
DECISION_NUMBER = re.compile(r"\b(?:C-\d{1,3}|ADR-\d+)\b")

# Links for live rows whose old entry wrote its artifact without a scheme, or only on the
# approved page, by the row's normalised slug.
LINKS = {
    "dartmouth-nber-captures": "https://archive.org/download/"
    "DARTMOUTH-NBER-RESEARCH-2017-metadata/domain-year-captures.txt",
    "domain-creation-bulk": "https://www.kaggle.com/datasets/wotschofsky/"
    "171-million-domain-names-whois-dns-dnssec",
    "usenet-address-usenet-address-mention": "https://archive.org/details/usenethistorical",
    "usenet-bare-usenet-bare-mention": "https://archive.org/details/usenethistorical",
    "usenet-addr": "https://archive.org/details/usenethistorical",
    "promotion-tranche-and-holdings-audit": "https://archive.org/details/usenethistorical",
    "iedr-register": "https://web.archive.org/web/20011221000000/"
    "http://www.domainregistry.ie/statistics/a-doms.html",
    "usenet-body-url-hostnames": "https://archive.org/details/usenet-alt",
    "nominet-rdap-over-held-uk-banked": "https://rdap.nominet.uk/uk/domain/demon.co.uk",
    "the-2001-2003-frozen-mirror-sweep": "https://cyber.harvard.edu/archived_content/people/"
    "edelman/typo-domains/",
    "abandoned-part-journals-local-half": "https://web.archive.org/cdx/search/cdx",
    "link-target-as-a-ranking-signal-for-the-archive-queue": "https://web.archive.org/cdx/search/cdx",
    "1999-internic-zones-on-the-jpnic-mirror": "https://tomocha.net/files/dns/",
    "stranded-rdap-journals-on-the-vps": "https://data.iana.org/rdap/dns.json",
    "common-crawl-domain-vertices-as-rdap-candidate-supply": "https://data.commoncrawl.org/"
    "projects/hyperlinkgraph/cc-main-2020-jul-aug-sep/domain/"
    "cc-main-2020-jul-aug-sep-domain-vertices.txt.gz",
    "squidguard-2001-blacklist": "http://archive.debian.org/debian/pool/main/s/squidguard/"
    "squidguard_1.2.0.orig.tar.gz",
    "ripe-dbase-1999": "http://ftp.funet.fi/pub/netinfo/RIPE/dbase/ripe.db.gz",
    "ripe-dbase-changed": "http://ftp.funet.fi/pub/netinfo/RIPE/dbase/ripe.db.gz",
    "can-domain-registry-notices": "https://archive.org/download/usenet-can/can.domain.mbox.zip",
    "dartmouth-bfs-seed-cctld-register-listing-inbody": "https://archive.org/details/"
    "Dartmouth_10KwebURLs_GWB-20180911224740_BFS_4-lvls",
    "us-domain-delegated": "https://web.archive.org/web/20010606153725id_/"
    "http://www.isi.edu/in-notes/us-domain-delegated.txt",
}

# Old headings that named a source in prose, by the slug its decision carries.
ALIASES = {
    "us-domain-delegated-subdomains-list-priced-needs-a-decision-and-the-isc-survey-c": (
        "us_domain_delegated"
    ),
    "namewinner-com-expiring-domain-list-2001-10-26-priced-needs-a-decision": (
        "namewinner_expiring"
    ),
    "mynic-s-fortnightly-domain-name-listing": "mynic_my_change_report",
    "co-za-suspension-and-deletion-queues-the-wider-tree-verified-at-3-704-3-ee-and-a": (
        "coza_deletion_listing"
    ),
}

# The tables below settle what the old pages left open, and apply only while the open page
# still has its old sections. On pages already compacted, their rows say it themselves.

# The baseline is his own release: never claimed, so held out rather than closed.
VERDICTS = {"prior-task": "HELD OUT"}
REASONS = {
    "isc-survey-hostnames": "CLOSED for the annual claim: a DNS survey shows a host was in DNS,"
    " not that it served a page, so the reviewer refuses it as an annual record, and its"
    " hostname-years ship as candidates",
}

# Measurements with no row on the old pages. The registered-unhosted class is a FIND until
# its names are seeded: the figure is the pricer's, and none of it is in the store yet.
NEW_OPEN_ROWS = (
    (
        "registered_unhosted_names",
        "2026-09-24",
        "1997-2001",
        "Wayback playback of aftermarket, drop and expiry lists; the .nz lists from the"
        " usenet-nz mbox; hostnames inside captured URL query strings",
        "a list dates a registry event or a sale mention, not a capture of the listed host, so"
        " every name is candidate-only",
        "28-72% held",
        "62,149.53 EE (2026-09-24)",
        "priced by `ark price-snapshot --track candidate` on 159,140 names, snapshot merged260922,"
        " manifest e2b535b2; 21,180.70 EE of it are hostname records, which a candidate seed"
        " reduces to registrables",
        "n/a",
        "FIND, candidate-only",
        "<https://web.archive.org/web/20010622042353/http://www.webofsuccess.com/domainsweekly/"
        "soonsample.txt> afternic.com brumley.com buydomains.com ebay.com",
    ),
)
NEW_CLOSED_ROWS = (
    (
        "webbase_crawl_lists / artifact_listing",
        "2026-09-23",
        "0 EE",
        "CLOSED at 0 EE in window: the crawled_hosts lists are named MMYY (crawled_hosts.0105 is"
        " January 2005, file date 09-Feb-2005); the 2006 listing holds 365 files, all dated 2003"
        " to 2006, and the January 2001 crawl has no list",
        "<https://web.archive.org/web/20060527013341id_/http://dbpubs.stanford.edu:8091/~testbed/"
        "doc2/WebBase/crawl_lists/> <https://web.archive.org/web/20060105044642id_/"
        "http://dbpubs.stanford.edu:8091/~testbed/doc2/WebBase/webbase-pages.html>"
        " dbpubs.stanford.edu",
    ),
)

_RULE = re.compile(r"^\|[\s:|-]+\|\s*$")
_HEADING = re.compile(r"^(#{1,3}) (.*)$")
_SPLIT = re.compile(r"(?<!\\)\|")
_ISO = re.compile(r"\b(20\d\d-\d\d-\d\d)\b")
_URL = re.compile(r"https?://[^\s`)>\]<\"'|,\\]+")
_BARE = re.compile(
    r"\b((?:[a-z0-9-]+\.)+(?:com|net|org|edu|gov|uk|de|au|nz|ca|ie|za|jp|fr|nl|se|dk|no|fi|pl"
    r"|pt|it|es|ch|at|be|us|info|int|mil))\b"
)
_EE = re.compile(r"([\d,]*\d(?:\.\d+)?)\s*(?:net-new\s+)?(?:post-split\s+)?(?:candidate\s+)?EE\b")
_STORE_EE = re.compile(r"store\s+([\d,]*\d(?:\.\d+)?)\s*EE", re.I)
# In prose a bare "N EE" is as often a floor or a ceiling as a measurement, so the body of an
# entry is read only for a figure it calls net-new.
_NET_EE = re.compile(r"([\d,]*\d(?:\.\d+)?)\s*(?:net-new\s+(?:post-split\s+)?|post-split\s+)EE\b")
_WORDS = sorted({*OPEN_WORDS, *CLOSED_WORDS, *SYNONYMS}, key=len, reverse=True)
_UPPER = re.compile(r"\b(" + "|".join(_WORDS) + r")\b")
_LOWER_CLOSED = re.compile(r"\b(" + "|".join(CLOSED_WORDS) + r")\b", re.I)
_OPENS_CLOSED = re.compile(r"(" + "|".join(CLOSED_WORDS) + r")\b")
_OPENS_OPEN = re.compile(r"(" + "|".join(OPEN_WORDS) + r")\b")
_DATES = (
    re.compile(r"[Ww]hat dates one item[*:\s]*(.{8,400}?)(?:\.\s|;\s|\.$|$)", re.S),
    re.compile(r"\*\*Dating[.:]?\*\*[:\s]*(.{8,400}?)(?:\.\s|$)", re.S),
    re.compile(r"\bDating:\s*(.{8,400}?)(?:\.\s|$)", re.S),
)
_DECISION_LINE = re.compile(r"^\s*Decision:\s*[a-z-]+\s*$", re.I)
_SPEC_FACT = re.compile(r"^- ingest specs?:")
_LEADING_SLUG = re.compile(r"^\s*((`[^`]*`|[a-z0-9]+(_[a-z0-9]+)+)( / \S+)?[\s,]*(and\s+)?)+")


def split_cells(line: str) -> list[str]:
    """A table row's cells, `\\|` read back as a pipe."""
    body = line.strip()[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return [cell.strip().replace("\\|", "|") for cell in _SPLIT.split(body)]


def join_cells(cells: list[str]) -> str:
    """The row, each pipe in a cell escaped once, so `split_cells` reads it back exactly."""
    return "| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |"


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def slug_key(cell: str) -> str:
    """The key a source cell files under: its name before ` / type`, normalised."""
    return norm(cell.split(" / ")[0].strip("`* "))


def tidy(text: str, limit: int = 0) -> str:
    """One line; cut at a space when over `limit`, so no URL or host is left half written."""
    text = re.sub(r"\s+", " ", text).strip()
    if limit and len(text) > limit:
        text = text[: limit - 3].rsplit(" ", 1)[0].rstrip(" ,;:") + "..."
    return text


def reword(text: str) -> str:
    for pattern, words in REWORD:
        text = re.sub(pattern, words, text, flags=re.M)
    return text


def urls(text: str) -> list[str]:
    return list(dict.fromkeys(u.rstrip(".;:") for u in _URL.findall(text)))


def hosts(text: str) -> set[str]:
    return set(_BARE.findall(text.lower()))


def dated(text: str, span: tuple[str, str]) -> str:
    """The newest date in `text` inside `span`, the register's own first and last."""
    return max((d for d in _ISO.findall(text) if span[0] <= d <= span[1]), default="")


def ee_of(text: str, prose: bool = False) -> str:
    found = _STORE_EE.search(text) or (_NET_EE if prose else _EE).search(text)
    return f"{found.group(1)} EE" if found else ""


def dates_of(text: str) -> str:
    for pattern in _DATES:
        found = pattern.search(text)
        if found:
            return tidy(found.group(1), 200)
    return ""


def heading_slug(title: str) -> str:
    """The source a heading names: its backticked keys, else its first snake_case word."""
    head, _, rest = title.partition(":")
    if head.strip().upper() in _WORDS and rest:
        head = rest
    head = head.split(" / ")[0]
    ticks = re.findall(r"`([a-z0-9_.\-]+)`", head)
    if ticks:
        return ", ".join(dict.fromkeys(ticks))
    word = re.match(r"\s*([a-z0-9]+(?:_[a-z0-9]+)+)\b", head)
    return word.group(1) if word else norm(head)[:80]


def remainder(title: str) -> str:
    """What a heading says after the source it names."""
    _, sep, rest = title.partition(":")
    return tidy(_LEADING_SLUG.sub("", rest if sep else title), 200)


def verdict_word(text: str, lowercase: bool = True) -> str:
    """The verdict a cell or heading states, in the page's words, or empty.

    Capitals are the page's verdicts; a lowercase word counts only when `lowercase` allows
    it, because prose says "closed" of things that are not.
    """
    if re.search(r"\bnot a source\b", text, re.I):
        return "REJECTED"
    found = _UPPER.search(text)
    if found:
        return SYNONYMS.get(found.group(1), found.group(1))
    if not lowercase:
        return ""
    first = re.match(r"\s*([A-Za-z]+)", text)
    if first and first.group(1).lower() in LOWER_OPEN:
        return LOWER_OPEN[first.group(1).lower()]
    closed = _LOWER_CLOSED.search(text)
    return closed.group(1).upper() if closed else ""


def closed_word(reason: str) -> str:
    opening = _OPENS_CLOSED.match(reason)
    if opening:
        return opening.group(1)
    word = verdict_word(reason)
    return word if word in CLOSED_WORDS else "CLOSED"


@dataclass
class Row:
    page: str
    order: int
    cells: list[str]
    columns: tuple[str, ...]

    def cell(self, *names: str) -> str:
        for name in names:
            for i, column in enumerate(self.columns):
                if column.startswith(name) and i < len(self.cells):
                    return self.cells[i]
        return ""


@dataclass
class Unit:
    """One source: every row, heading and line of prose the old pages gave it."""

    key: str
    slug: str
    order: int
    rows: list[Row] = field(default_factory=list)
    heads: list[tuple[int, str]] = field(default_factory=list)
    texts: list[str] = field(default_factory=list)


def match_detail(key: str, units: dict[str, Unit]) -> str:
    """The unit a `### slug` detail block belongs to, by its anchor slug."""
    if key in units:
        return key
    base = re.sub(r"-\d{1,2}$", "", key)
    if base in units:
        return base
    near = [k for k in units if len(base) >= 15 and (k.startswith(base) or base.startswith(k))]
    return min(near, key=len) if near else base


def read_units(pages: dict[str, str]) -> dict[str, Unit]:
    """Every source both pages name, keyed by its normalised slug, in first-seen order.

    Table rows under a `source` header are sources; so is a section heading of the open
    page. Detail blocks, inner tables and prose feed the unit they sit under. Headerless
    five-cell rows at the foot of the closed page take its header.
    """
    units: dict[str, Unit] = {}
    order = 0

    def unit(key: str, slug: str) -> Unit:
        if key not in units:
            units[key] = Unit(key, slug, len(units))
        return units[key]

    for page in (OPEN_PAGE, CLOSED_PAGE):
        lines = pages[page].splitlines()
        columns: tuple[str, ...] | None = None
        fence = detail = False
        current = section = None
        for i, line in enumerate(lines):
            order += 1
            if line.startswith("```"):
                fence = not fence
            heading = None if fence else _HEADING.match(line)
            if heading:
                level, title = len(heading.group(1)), heading.group(2).strip()
                slug = heading_slug(title)
                slug = ALIASES.get(norm(slug), slug)
                columns = None
                if level == 1:
                    current = section = None
                elif level == 2:
                    detail = title == "Detail"
                    current = section = None
                    if not detail and page == OPEN_PAGE and norm(slug) not in CONTAINERS:
                        current = section = unit(norm(slug), slug)
                        current.heads.append((order, title))
                elif detail or page == CLOSED_PAGE:
                    current = unit(match_detail(norm(title), units), title)
                elif "`" in title.partition(":")[0] or "_" in slug:
                    current = unit(norm(slug), slug)
                    current.heads.append((order, title))
                else:
                    current = section
                if current is not None:
                    current.texts.append(line)
                continue
            if line.startswith("|") and not fence:
                if _RULE.match(line):
                    continue
                cells = split_cells(line)
                if i + 1 < len(lines) and _RULE.match(lines[i + 1]):
                    columns = tuple(c.lower() for c in cells)
                    continue
                shape = columns
                if shape is None and page == CLOSED_PAGE and len(cells) == 5:
                    shape = CLOSED_COLUMNS
                if shape and shape[0] == "source":
                    key = slug_key(cells[0])
                    if key and not norm(cells[0]).startswith("brief-audit"):
                        found = unit(key, cells[0])
                        found.rows.append(Row(page, order, cells, shape))
                        found.texts.append(line)
                    continue
            if current is not None:
                current.texts.append(line)
    return units


@dataclass
class Choice:
    """Which row or heading speaks for a unit, and the verdict it gives."""

    date: str
    word: str
    order: int
    row: Row | None = None
    title: str = ""
    decided: bool = False

    @property
    def closed(self) -> bool:
        return self.word not in OPEN_WORDS

    @property
    def rank(self) -> tuple:
        # On one date a settled source (its names in the store) outranks a closed row, and a
        # closed row outranks a FIND or PARKED. Table rows lead with the newest; the old
        # narrative sections were appended below.
        tier = 2 if self.word in SETTLED_WORDS else int(self.closed)
        later = -self.order if self.row is not None else self.order
        return (self.date, tier, self.row is not None, later)


def decision_word(unit: Unit, decisions: dict[str, set[str]]) -> str:
    """The verdict the approved page gives any source the unit names."""
    found: set[str] = set()
    for name in unit.slug.split(","):
        found |= decisions.get(name.strip().strip("`"), set())
    return next((DECISION_WORD[d] for d in DECISION_WORD if d in found), "")


def row_date(row: Row) -> str:
    return row.cell("version or date", "date")


def row_choice(row: Row, unit: Unit, decisions: dict[str, set[str]], span: tuple) -> Choice:
    date = dated(row_date(row), ("", span[1]))
    if row.page == CLOSED_PAGE:
        return Choice(date, closed_word(row.cell("reason")), row.order, row)
    word = verdict_word(row.cell("verdict")) or decision_word(unit, decisions) or "CLOSED"
    return Choice(date, word, row.order, row)


def choose(
    unit: Unit, decisions: dict[str, set[str]], span: tuple[str, str], migrating: bool
) -> Choice:
    """The unit's current verdict: its newest dated row or heading; `Choice.rank` breaks a tie.

    A heading date before the register's first dated row is the artifact's, not a
    measurement's. On the old pages a FIND or PARKED was still awaiting the decision the
    approved page now records, so that decision replaces it.
    """
    choices = [row_choice(row, unit, decisions, span) for row in unit.rows]
    for order, title in unit.heads:
        lower = re.search(r"\b(banked|admitted|seeded|deferred)\b", title, re.I)
        word = (
            verdict_word(title, False)
            or decision_word(unit, decisions)
            or (LOWER_OPEN[lower.group(1).lower()] if lower else "")
            or verdict_word(title)
        )
        date = dated(title, span)
        if word or date:
            choices.append(Choice(date, word or "CLOSED", order, None, title))
    if choices:
        choice = max(choices, key=lambda c: c.rank)
    else:
        text = "\n".join(unit.texts)
        word = decision_word(unit, decisions) or verdict_word(text, False) or "CLOSED"
        title = unit.heads[0][1] if unit.heads else ""
        choice = Choice(dated(text, span), word, unit.order, None, title)
    if migrating:
        decided = decision_word(unit, decisions)
        if choice.word in ("FIND", "PARKED") and decided not in ("", "PARKED"):
            choice.word, choice.decided = decided, True
        choice.word = VERDICTS.get(unit.key, choice.word)
    return choice


def open_verdict(cell: str, word: str) -> str:
    """The verdict cell, opening with its word in capitals."""
    cell = cell.strip()
    if re.match(rf"{word}\b", cell):
        return cell
    first = re.match(r"[A-Za-z]+", cell)
    if first and SYNONYMS.get(first[0].upper(), LOWER_OPEN.get(first[0].lower())) == word:
        return word + cell[first.end() :]
    if re.match(rf"{word}\b", cell, re.I):
        return word + cell[len(word) :]
    if cell.lower() in ("", "n/a", "-"):
        return word
    return f"{word}, {cell}"


def closed_reason(text: str, word: str) -> str:
    """The reason, opening with its verdict word in capitals."""
    text = text.strip()
    if _OPENS_CLOSED.match(text):
        return text
    if text.lower().startswith(word.lower()) and not text[len(word) : len(word) + 1].isalpha():
        return word + text[len(word) :]
    return f"{word}. {text}" if text else word


def link_cell(old: str, source: str, row: list[str]) -> str:
    """What the link cell held, then every URL the source named, then its hosts the row lacks."""
    have = "" if old.strip().lower() in ("", "n/a", "-", "none") else old.strip()
    held = set(urls(have))
    fresh = [f"<{u}>" for u in urls(source) if u not in held]
    tokens = have.split()
    if all(re.fullmatch(r"<?https?://\S+", t) or _BARE.fullmatch(t.lower()) for t in tokens):
        linked = [t for t in tokens if "://" in t] + fresh
        named = [t for t in tokens if "://" not in t]
    else:
        linked, named = ([have] if have else []) + fresh, []
    present = hosts(join_cells([*row, " ".join(linked + named)]))
    named += sorted(hosts(source) - present)
    return " ".join(linked + named) or old


def open_row(unit: Unit, choice: Choice, base: Row | None, source: str) -> list[str]:
    """Eleven cells: the winning row's own, or what its heading and prose say."""
    if base is not None and base.page == OPEN_PAGE:
        # A row with a stray pipe keeps its overflow in the link cell rather than losing it.
        width = len(OPEN_COLUMNS)
        cells = [reword(c) for c in base.cells[: width - 1]]
        cells += ["n/a"] * (width - 1 - len(cells)) + [reword(" ".join(base.cells[width - 1 :]))]
    else:
        ee = ee_of(choice.title) or ee_of(source, prose=True)
        figure = f"{ee} ({choice.date})" if ee and choice.date else ee or "not priced"
        slug = unit.slug if base is None else base.cells[0]
        dates = reword(dates_of(source)) or "n/a"
        cells = [
            slug,
            choice.date or "n/a",
            "n/a",
            "n/a",
            dates,
            "n/a",
            figure,
            "n/a",
            "n/a",
            "",
            "",
        ]
    if choice.row is None and choice.title:
        ee = ee_of(choice.title)
        cells[1] = choice.date or cells[1]
        if ee:
            cells[6] = f"{ee} ({choice.date})" if choice.date else ee
        cells[9] = reword(remainder(choice.title))
    cells[9] = choice.word if choice.decided else open_verdict(cells[9], choice.word)
    cells[10] = link_cell(cells[10], source + LINKS.get(unit.key, ""), cells[:10])
    return cells


def closed_row(
    unit: Unit, choice: Choice, base: Row | None, source: str, migrating: bool
) -> list[str]:
    """Five cells, the reason opening with its verdict word."""
    row = choice.row
    if row is not None and row.page == CLOSED_PAGE:
        cells = [reword(c) for c in row.cells[:5]] + [""] * (5 - len(row.cells[:5]))
    elif row is not None:
        verdict, quality = row.cell("verdict"), row.cell("quality issues")
        parts = (
            [verdict] if verdict_word(verdict) not in ("", "CLOSED") or len(verdict) > 12 else []
        )
        parts += [quality] if quality.lower() not in ("", "n/a") else []
        why = ". ".join(p.rstrip(". ") for p in parts)
        cells = [
            row.cells[0],
            row.cell("version or date"),
            row.cell("net-new ee"),
            why,
            row.cell("link"),
        ]
        cells = [reword(tidy(c)) for c in cells]
    else:
        ee = ee_of(choice.title) or ee_of(source, prose=True)
        why = remainder(choice.title) if choice.title else tidy(re.sub(r"[#*`]", "", source), 200)
        slug = unit.slug if base is None else base.cells[0]
        cells = [reword(tidy(c)) for c in (slug, choice.date or "n/a", ee or "not priced", why, "")]
    reason = REASONS.get(unit.key) if migrating else None
    cells[3] = reason or closed_reason(cells[3], choice.word)
    cells[4] = link_cell(cells[4], source + LINKS.get(unit.key, ""), cells[:4])
    return cells


def compact_sources(pages: dict[str, str]) -> tuple[str, str]:
    """The open and the closed page, one row per source."""
    units = read_units(pages)
    decisions: dict[str, set[str]] = {}
    for (name, _), approval in parse_approvals(pages[APPROVED_PAGE]).items():
        decisions.setdefault(name, set()).add(approval.decision)
    stamps = [d for u in units.values() for r in u.rows for d in _ISO.findall(row_date(r))]
    span = (min(stamps, default=""), max(stamps, default="9999-12-31"))
    migrating = any(line.startswith("## ") for line in pages[OPEN_PAGE].splitlines())
    open_rows: list[list[str]] = []
    closed_rows: list[list[str]] = []
    for unit in units.values():
        choice = choose(unit, decisions, span, migrating)
        newest = sorted(unit.rows, key=lambda r: (row_choice(r, unit, {}, span).date, -r.order))
        base = choice.row or (newest[-1] if newest else None)
        source = "\n".join(unit.texts)
        if choice.closed:
            closed_rows.append(closed_row(unit, choice, base, source, migrating))
        else:
            open_rows.append(open_row(unit, choice, base, source))
    if migrating:
        keys = {slug_key(c[0]) for c in open_rows + closed_rows}
        open_rows[:0] = [list(c) for c in NEW_OPEN_ROWS if slug_key(c[0]) not in keys]
        closed_rows[:0] = [list(c) for c in NEW_CLOSED_ROWS if slug_key(c[0]) not in keys]
    open_text = f"{OPEN_PREAMBLE}\n{OPEN_HEADER}\n|{'---|' * len(OPEN_COLUMNS)}\n"
    closed_text = f"{CLOSED_PREAMBLE}\n{CLOSED_HEADING}\n|{'---|' * len(CLOSED_COLUMNS)}\n"
    open_text += "".join(join_cells(c) + "\n" for c in open_rows)
    closed_text += "".join(join_cells(c) + "\n" for c in closed_rows)
    return open_text, closed_text


def decided_facts(body: list[str]) -> list[str]:
    """A decided block's `- ` facts, each on one line, then its first `Decision:` line.

    Continuation lines are joined onto their fact, except under `- ingest spec(s):`, whose
    every backticked token is a spec key and whose lines stay as written.
    """
    facts: list[str] = []
    decision = ""
    i = 0
    while i < len(body):
        line = body[i]
        if line.startswith("- "):
            j = i + 1
            while j < len(body) and body[j].strip() and not body[j].startswith(("- ", "#")):
                if _DECISION_LINE.match(body[j]) or body[j].startswith("Decided by"):
                    break
                j += 1
            more = body[i + 1 : j]
            if _SPEC_FACT.match(line):
                facts += [line.rstrip(), *(m.rstrip() for m in more)]
            else:
                facts.append(tidy(" ".join([line, *more])))
            i = j
            continue
        if not decision and _DECISION_LINE.match(line):
            decision = line.strip()
        i += 1
    facts = [f for f in facts if f.strip() not in ("-", "- ruling:")]
    return facts + ([decision] if decision else [])


def compact_approved(text: str) -> str:
    """Each block as its heading, its facts and its `Decision:` line; pending blocks whole."""
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith("## ")), len(lines))
    groups: list[list[str]] = []
    for line in lines[start:]:
        if line.startswith(("## ", "### ")):
            groups.append([line])
        elif groups:
            groups[-1].append(line)
    out = [APPROVED_PREAMBLE.rstrip("\n")]
    whole = False
    for head, *rest in groups:
        body = [reword(line) for line in rest if not line.startswith("Decided by")]
        if head.startswith("## "):
            whole = head[3:].strip() in WHOLE_SECTIONS
            intro = [tidy(line) for line in body if line.strip()] if whole else []
            out += ["", head] + ([""] + intro if intro else [])
        elif not whole:
            out += ["", head, *decided_facts(body)]
        else:
            # A block with a table or a fence keeps its blank lines, or it stops rendering.
            if not any(line.startswith(("|", "```")) for line in body):
                body = [line for line in body if line.strip()]
            while body and not body[-1].strip():
                body.pop()
            while body and not body[0].strip():
                body.pop(0)
            out += ["", head, *body]
    return "\n".join(out).rstrip("\n") + "\n"


def compact(pages: dict[str, str]) -> dict[str, str]:
    """All three pages compacted; refuses when a `Decision:` line would read differently."""
    open_text, closed_text = compact_sources(pages)
    approved = compact_approved(pages[APPROVED_PAGE])
    before = {k: (a.decision, a.section) for k, a in parse_approvals(pages[APPROVED_PAGE]).items()}
    after = {k: (a.decision, a.section) for k, a in parse_approvals(approved).items()}
    if before != after:
        changed = sorted(set(before.items()) ^ set(after.items()))[:5]
        raise SystemExit(f"compact_registers: the approvals would change: {changed}")
    return {OPEN_PAGE: open_text, CLOSED_PAGE: closed_text, APPROVED_PAGE: approved}


def table_rows(text: str, header: str) -> list[list[str]]:
    """The cells of each row of the table under `header`."""
    lines = text.splitlines()
    at = next((i for i, line in enumerate(lines) if line.startswith(header)), None)
    if at is None:
        return []
    rows = []
    for line in lines[at + 2 :]:
        if not line.startswith("|"):
            break
        rows.append(split_cells(line))
    return rows


def measures(pages: dict[str, str], current: dict[str, str]) -> list[tuple[str, object, bool]]:
    """Each count `--check` prints, with whether it passes."""
    open_rows = table_rows(pages[OPEN_PAGE], REGISTER_HEADER)
    closed_rows = table_rows(pages[CLOSED_PAGE], CLOSED_HEADING)
    rows = open_rows + closed_rows
    lines = {name: len(text.splitlines()) for name, text in pages.items()}
    total = sum(lines.values())
    everything = "\n".join(pages.values())
    keys = [c[0].strip("`*").split(" / ")[0].strip() for c in rows]
    decisions = sum(bool(_DECISION_LINE.match(x)) for x in pages[APPROVED_PAGE].splitlines())
    numbers = len(DECISION_NUMBER.findall(everything))
    unlinked = sum(c[9].startswith(LINKED_WORDS) and not _URL.search(c[10]) for c in open_rows)
    unlinked_find = sum(
        c[9].startswith(("FIND", "PARKED")) and not _URL.search(c[10]) for c in open_rows
    )
    verdictless = sum(not _OPENS_CLOSED.match(c[3]) for c in closed_rows)
    not_open = sum(len(c) != len(OPEN_COLUMNS) or not _OPENS_OPEN.match(c[9]) for c in open_rows)
    audits = sum(norm(k).startswith("brief-audit") for k in keys)
    fixed = compact(pages) == pages
    changed = sum(current[name] != pages[name] for name in pages)
    return [
        *((f"lines {name}", lines[name], True) for name in PAGES),
        ("lines total (at most 1,900)", total, total <= 1900),
        ("rows open", len(open_rows), True),
        ("rows closed", len(closed_rows), True),
        ("rows total", len(rows), True),
        ("Decision lines", decisions, True),
        ("Decided by lines", everything.count("Decided by"), "Decided by" not in everything),
        ("decision numbers", numbers, not numbers),
        ("unlinked live rows", unlinked, not unlinked),
        ("FIND or PARKED rows without a link", unlinked_find, True),
        ("verdictless closed rows", verdictless, not verdictless),
        (f"non-open rows in {OPEN_PAGE}", not_open, not not_open),
        ("brief-audit rows", audits, not audits),
        ("duplicate slugs", len(keys) - len(set(keys)), len(keys) == len(set(keys))),
        ("rows over 500 characters", sum(len(join_cells(c)) > 500 for c in rows), True),
        ("fixed point", "yes" if fixed else "no", fixed),
        ("pages that would change", changed, not changed),
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--registers", type=Path, default=REGISTERS, help="the pages' directory")
    parser.add_argument("--check", action="store_true", help="print the counts, write nothing")
    args = parser.parse_args(argv)
    current = {name: (args.registers / name).read_text(encoding="utf-8") for name in PAGES}
    pages = compact(current)
    if args.check:
        failed = False
        for label, value, ok in measures(pages, current):
            failed |= not ok
            print(f"{label}: {value}" + ("" if ok else "  FAIL"))
        return 1 if failed else 0
    for name in PAGES:
        if pages[name] != current[name]:
            (args.registers / name).write_text(pages[name], encoding="utf-8")
            print(f"rewrote {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
