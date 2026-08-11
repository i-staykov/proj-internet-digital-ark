"""Re-ask every source that was closed because something could not be reached.

**The asymmetry this exploits.** A source closed on a *measurement* is finished:
the numbers do not improve by waiting. A source closed on *availability* is not,
and revisiting that class is explicitly part of the task rather than a nicety. The
register's own best case is the Australian Web Archive, where `webarchive.nla.gov.au`
served an anti-bot challenge and `web.archive.org.au` answered normally once
somebody checked the second host, and the family was nearly written off as empty on
the strength of the first result. `data.webarchive.org.uk` was tried as a third host
for the same dataset after two others failed.

**And the register already contains the URLs.** Every verdict names what was tried,
so the re-probe needs no new knowledge: extract the hosts and URLs out of the
verdict prose, ask each one, and report only what has *changed* since the verdict
was written. That makes this the one genuinely autonomous discovery step in the
harness, because it needs judgement neither to generate candidates nor to decide
whether the answer is interesting: a dead host that now answers 200 is interesting
by construction.

**It is deliberately shallow.** One request per URL, HEAD where the server allows
it, honest User-Agent, no crawling and no following of internal links. It answers
"is this reachable now" and nothing else; whether the payload is worth having is a
pricing question for `price_items.py`.

    uv run python scripts/reprobe_closed.py
    uv run python scripts/reprobe_closed.py --json data/reports/reprobe.json
"""

import argparse
import importlib.util
import json
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

_SPEC = importlib.util.spec_from_file_location(
    "screen_hypothesis", ROOT / "scripts" / "screen_hypothesis.py"
)
screen = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(screen)

USER_AGENT = (
    "InternetDigitalArk/1.0 (historical domain research, 1996-2001; "
    "contact ivaylo.staykov@taktile.com)"
)
# Bare hosts and full URLs inside a verdict, in backticks or not. Deliberately
# narrow: a verdict is prose, and a permissive rule turns sentence punctuation into
# hostnames exactly as it does in an OCR'd magazine page.
URL_RE = re.compile(r"https?://[^\s`)\]<>,;\"']+")
# Two labels are enough: the verdicts name `ircache.net` and `vefsafn.is` as often
# as they name a three-label host, and requiring three found 4 URLs across 19 leads.
HOST_RE = re.compile(r"`((?:[a-z0-9][a-z0-9\-]*\.)+[a-z]{2,})`", re.IGNORECASE)
# Several real TLDs are also file extensions, so a backticked `sources.md` or
# `split_usenet.py` parses as a hostname. Filtering by extension loses Moldova and
# Italy, which is the right trade here: this reads prose about tooling constantly
# and a probe of a filename is pure noise.
NOT_A_TLD = {
    "md",
    "py",
    "sh",
    "txt",
    "gz",
    "json",
    "jsonl",
    "csv",
    "tsv",
    "xml",
    "html",
    "htm",
    "zip",
    "tar",
    "log",
    "sql",
    "pdf",
    "docx",
    "cdxj",
    "cdx",
    "mbox",
    "ini",
    "yml",
    "yaml",
    "toml",
    "lock",
    "bak",
    "part",
    "tmp",
    "idx",
    "rdf",
    "arc",
    "warc",
    "bz2",
}
# Hosts that are not the closed source: our own tools, the archive we already use,
# and code-hosting we reach through other means. Probing these says nothing.
SKIP_HOSTS = {
    "web.archive.org",
    "archive.org",
    "github.com",
    "raw.githubusercontent.com",
    "www.isc.org",
    "data.iana.org",
    "rdap.org",
    "doi.org",
}


@dataclass
class Probe:
    lead: str
    line: int
    url: str
    status: str = ""
    detail: str = ""
    changed: bool = False
    predicted: str = ""


# A 200 is only news if the verdict did not already expect one. `ircache.net`
# answers today and the register says so: "now serves a squatted blog". Iceland's
# `vefsafn.is` answers because it always did, and was closed on a measurement of
# 867 projected equivalent-English rather than on reach. Without this the tool
# reports both as revivals, and a re-probe that cries wolf gets switched off.
EXPECTED_ALIVE = (
    "squatted",
    "answers normally",
    "answers in",
    "serves a squatted",
    "serves the same",
    "159-byte stub",
    "soft-404",
    "stub rather than",
    "page has moved",
    "open unauthenticated",
    "genuinely serving",
    "runs an open",
    "is alive",
    "still answers",
    "answers today",
)


def prediction_for(verdict: str, host: str) -> str:
    """The sentence in the verdict that mentions this host, if any.

    Printed beside a revival so the reader can see whether the verdict already
    expected the host to answer. This is what separates "the data came back" from
    "the squatter is still there".
    """
    for sentence in re.split(r"(?<=[.;])\s+", verdict):
        if host.lower() in sentence.lower():
            return sentence.strip()
    return ""


@dataclass
class Lead:
    name: str
    line: int
    verdict: str
    urls: list[str] = field(default_factory=list)


def targets_in(entry) -> list[str]:
    """URLs and bare hosts named in a verdict, deduplicated, ours removed."""
    blob = f"{entry.name} {entry.verdict}"
    found: list[str] = []
    for url in URL_RE.findall(blob):
        found.append(url.rstrip(".,);:"))
    for host in HOST_RE.findall(blob):
        if host.rsplit(".", 1)[-1].lower() in NOT_A_TLD:
            continue
        found.append(f"https://{host}/")
    out: list[str] = []
    for url in found:
        try:
            host = urllib.parse.urlsplit(url).hostname or ""
        except ValueError:
            continue
        if not host or host in SKIP_HOSTS or host.endswith(".local"):
            continue
        if url not in out:
            out.append(url)
    return out[:5]


def ask(url: str, timeout: float = 20.0) -> tuple[str, str]:
    """One shallow request. Returns (status, detail), never raises."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(2048)
            kind = response.headers.get("Content-Type", "?")
            return str(response.status), f"{len(body)}+ bytes, {kind}"
    except urllib.error.HTTPError as exc:
        return str(exc.code), (exc.reason or "")[:60]
    except urllib.error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, socket.gaierror):
            return "DNS", "does not resolve"
        if isinstance(reason, ssl.SSLError):
            return "TLS", str(reason)[:60]
        if isinstance(reason, TimeoutError):
            return "TIMEOUT", ""
        return "ERROR", str(reason)[:60]
    except TimeoutError:
        return "TIMEOUT", ""
    except Exception as exc:  # a probe must never take the run down
        return "ERROR", f"{type(exc).__name__}: {exc}"[:70]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, default=None, help="also write the result as JSON")
    ap.add_argument("--limit", type=int, default=None, help="probe at most this many leads")
    args = ap.parse_args()

    register = screen.closed_leads()
    leads = [
        Lead(e.name, e.line, e.verdict, targets_in(e))
        for e in register
        if e.closed_on == "availability"
    ]
    leads = [lead for lead in leads if lead.urls]
    if args.limit:
        leads = leads[: args.limit]

    n_avail = sum(1 for e in register if e.closed_on == "availability")
    print(f"{len(register)} closed leads, {n_avail} closed on availability,")
    print(f"of which {len(leads)} name a URL that can be re-asked.\n")

    results: list[Probe] = []
    for lead in leads:
        print(f"-- {lead.name[:84]}  (sources.md:{lead.line})")
        for url in lead.urls:
            status, detail = ask(url)
            answers = status.startswith("2") or status in {"301", "302", "303", "307", "308"}
            host = urllib.parse.urlsplit(url).hostname or ""
            predicted = prediction_for(lead.verdict, host)
            foretold = any(sign in (predicted or lead.verdict).lower() for sign in EXPECTED_ALIVE)
            probe = Probe(
                lead.name,
                lead.line,
                url,
                status,
                detail,
                changed=answers and not foretold,
                predicted=predicted[:200],
            )
            results.append(probe)
            if answers and foretold:
                mark = "answers, as the verdict said"
            elif answers:
                mark = "NOW ANSWERS, UNEXPECTED"
            else:
                mark = "still closed"
            print(f"   [{status:>7}] {mark:<28} {url[:62]}")
            if detail:
                print(f"             {detail[:76]}")
            if answers and predicted:
                print(f"             verdict said: {predicted[:70]}")

    revived = [p for p in results if p.changed]
    print("\n== summary ==")
    print(f"  URLs asked        : {len(results)}")
    print(f"  answering now     : {len(revived)}")
    if revived:
        print("\n  Answering today, and their verdict did NOT expect that. Worth PRICING,")
        print("  which is not the same as worth adopting.")
        for probe in revived:
            print(f"    sources.md:{probe.line}  {probe.url[:74]}")
            print(f"      {probe.lead[:84]}")
        expected = [p for p in results if p.status.startswith("2") and not p.changed]
    else:
        expected = [p for p in results if p.status.startswith("2")]
        print("  nothing unexpected came back.")
    if expected:
        print(f"\n  {len(expected)} answered as their verdict predicted, so they are not news:")
        for probe in expected:
            print(f"    {probe.url[:60]}  ({probe.lead[:44]})")
    print("\n  A 200 says the host answers, never that the payload is in window or worth")
    print("  having. Price it against the live store before believing anything.")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps([p.__dict__ for p in results], indent=2) + "\n", encoding="utf-8"
        )
        print(f"\n  wrote {args.json}")


if __name__ == "__main__":
    main()
