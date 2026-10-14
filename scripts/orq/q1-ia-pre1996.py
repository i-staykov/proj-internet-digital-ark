"""q1-ia-pre1996: does the Internet Archive CDX hold captures stamped before 1996?

    uv run python scripts/orq/q1-ia-pre1996.py [--stop-at 2026-10-13T00:45:00Z] [--report]

The hosts are every web server named in CERN's list of WWW servers as of 3 November 1992
(Servers.html and its test-server page UnstableServers.html, W3C's copy of the CERN
hypertext of that date), plus info.cern.ch, www.w3.org and www.ncsa.uiuc.edu. Each page is
fetched once (robots.txt read first) and kept beside the results. Each host is asked:

    url=<host>/*&to=1995&fl=timestamp,original,statuscode&limit=50

"pre1996_capture" when a row's original URL has exactly that host (parsed from original,
since the SURT key folds www. into the apex); a full answer of 50 rows without one is asked
again with filter=original:^https?://<host>(:[0-9]+)?(/|$). "neighbour_only" when rows came
back for a folded neighbour only, "none" when no row came back. A throttle, timeout, refused
connect or 5xx is retried (Retry-After, else 60 s doubling, 6 tries) and never counted as
none: an exhausted host is "unresolved"; a 403 is "blocked". One request in flight, starts
at least 3 s apart. Resumable through sample.csv. Writes only under
docs/orq/results/q1-ia-pre1996/.
"""

import argparse
import csv
import email.utils
import http.client
import json
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import UTC, datetime
from pathlib import Path

TEST_ID = "q1-ia-pre1996"
SEED = 20261012
LIMIT = 50
CDX = "https://web.archive.org/cdx/search/cdx"
UA = "internet-digital-ark/1.0 (research; Open Research Questions test)"
GAP, TIMEOUT, TRIES = 3.0, 60, 6
TODO = ("", "unresolved")  # a rerun asks an unresolved host again
OUT = Path("docs/orq/results") / TEST_ID
BASE = "https://www.w3.org/History/19921103-hypertext/hypertext/DataSources/WWW/"
PAGES = ["Servers.html", "UnstableServers.html"]
ADDED = ["info.cern.ch", "www.w3.org", "www.ncsa.uiuc.edu"]
FIELDS = [
    "order", "host", "named_in", "outcome", "query", "rows", "exact_rows", "timestamp",
    "original", "statuscode", "wayback_url", "attempts",
]  # fmt: skip


def utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def source(page: str) -> str:
    """The page as kept beside the results; fetched once, after its robots.txt allows it."""
    path = OUT / f"source-{page}"
    if not path.exists():
        robots = urllib.robotparser.RobotFileParser("https://www.w3.org/robots.txt")
        robots.read()
        if not robots.can_fetch(UA, BASE + page):
            raise SystemExit(f"robots.txt disallows {BASE + page}")
        req = urllib.request.Request(BASE + page, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            path.write_bytes(r.read())
    return path.read_text(encoding="iso-8859-1")


def host_of(url: str) -> str | None:
    s = url.strip()
    if s.startswith("//"):
        s = "http:" + s
    elif "://" not in s[:12]:
        s = "http://" + s
    try:
        h = urllib.parse.urlsplit(s).hostname
    except ValueError:
        return None
    return h.rstrip(".") if h else None


def listed_hosts() -> list[tuple[str, str]]:
    """Every absolute or network-path href in the server list proper (after its first <DL>:
    the note above it, linking later directories, was added after 1992)."""
    named: dict[str, str] = {}
    for page in PAGES:
        html = source(page)
        start = html.upper().find("<DL>")
        body = html[start:] if start >= 0 else html
        for href in re.findall(r'href="([^"]+)"', body, flags=re.I):
            if href.startswith(("http://", "//")) and (h := host_of(href)):
                named.setdefault(h, page)
    for h in ADDED:
        named.setdefault(h, "added")
    return list(named.items())[:150]


def draw() -> list[dict]:
    hosts = listed_hosts()
    random.Random(SEED).shuffle(hosts)
    return [
        {**dict.fromkeys(FIELDS, ""), "order": str(i), "host": h, "named_in": page}
        for i, (h, page) in enumerate(hosts, 1)
    ]


def save(sample: list[dict]) -> None:
    tmp = OUT / "sample.csv.tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(sample)
    tmp.replace(OUT / "sample.csv")


def query_url(host: str, anchored: bool) -> str:
    q = [("url", f"{host}/*"), ("to", "1995")]
    if anchored:
        q.append(("filter", "original:^https?://" + re.escape(host) + "(:[0-9]+)?(/|$)"))
    q += [("fl", "timestamp,original,statuscode"), ("limit", str(LIMIT))]
    return CDX + "?" + urllib.parse.urlencode(q, safe="/*:,")


class Abandoned(Exception):
    """The stop time fell inside a back-off: the host is left undone, never counted."""


def backoff(header: str | None, wait: float) -> float:
    if header:
        if header.strip().isdigit():
            return float(header.strip())
        try:
            return max(0.0, email.utils.parsedate_to_datetime(header).timestamp() - time.time())
        except (TypeError, ValueError):
            pass
    return wait


class Channel:
    def __init__(self, log, stop_at: datetime | None):
        self.log, self.stop_at, self.last = log, stop_at, 0.0

    def line(self, url: str, status, secs: float, outcome: str) -> None:
        self.log.write(f"{utc()} {url} {status} {secs:.2f} {outcome}\n")
        self.log.flush()

    def get(self, url: str) -> tuple[int | None, str, float, int]:
        """(status, body, seconds, tries); status None after TRIES transient failures."""
        wait = 60.0
        for attempt in range(1, TRIES + 1):
            if (pause := self.last + GAP - time.monotonic()) > 0:
                time.sleep(pause)
            self.last = t0 = time.monotonic()
            retry_after = None
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                    body = r.read().decode("utf-8", "replace")
                    return r.status, body, time.monotonic() - t0, attempt
            except urllib.error.HTTPError as e:
                if e.code != 429 and e.code < 500:
                    return e.code, "", time.monotonic() - t0, attempt
                status, retry_after = e.code, e.headers.get("Retry-After")
            except (urllib.error.URLError, TimeoutError, http.client.HTTPException, OSError) as e:
                cause = getattr(e, "reason", e)
                status = f"{type(cause).__name__}:{str(cause).replace(' ', '_')[:60]}"
            secs = time.monotonic() - t0
            if attempt == TRIES:
                self.line(url, status, secs, "unresolved")
                return None, "", secs, attempt
            delay = backoff(retry_after, wait)
            if self.stop_at and time.time() + delay > self.stop_at.timestamp():
                self.line(url, status, secs, "transient, stop time inside back-off, left undone")
                raise Abandoned
            self.line(url, status, secs, f"transient, retry in {delay:.0f} s")
            time.sleep(delay)
            wait *= 2
        raise AssertionError


def rows(body: str) -> list[tuple[str, str, str]]:
    out = []
    for line in body.splitlines():
        parts = line.split(" ")
        if len(parts) >= 3:
            out.append((parts[0], " ".join(parts[1:-1]), parts[-1]))
    return out


def check(ch: Channel, r: dict) -> None:
    host, tries, seen = r["host"], 0, 0
    for anchored in (False, True):
        url = query_url(host, anchored)
        status, body, secs, n = ch.get(url)
        tries += n
        query = "anchored" if anchored else "prefix"
        if status is None:
            r.update(outcome="unresolved", query=query, attempts=str(tries))
            return
        if status != 200:
            outcome = "blocked" if status == 403 else f"rejected_{status}"
            ch.line(url, status, secs, outcome)
            r.update(outcome=outcome, query=query, attempts=str(tries))
            return
        got = rows(body)
        seen = max(seen, len(got))
        hits = sorted(x for x in got if host_of(x[1]) == host and x[0][:4] < "1996")
        if hits:
            outcome = "pre1996_capture"
        elif len(got) >= LIMIT and not anchored:
            outcome = "no exact host in a full answer, anchoring"
        else:
            outcome = "neighbour_only" if seen else "none"
        ch.line(url, status, secs, f"{outcome} rows={len(got)}")
        if outcome.startswith("no exact"):
            continue
        r.update(outcome=outcome, query=query, rows=str(len(got)), exact_rows=str(len(hits)))
        r.update(attempts=str(tries))
        if hits:
            ts, original, code = hits[0]
            r.update(timestamp=ts, original=original, statuscode=code)
            r.update(wayback_url=f"https://web.archive.org/web/{ts}/{original}")
        return


def report(sample: list[dict], command: str) -> dict:
    lines = [
        ln.split(" ")
        for ln in (OUT / "log.txt").read_text(encoding="utf-8").splitlines()
        if ln and ln[0] != "#"
    ]
    done = [r for r in sample if r["outcome"]]
    names = ["pre1996_capture", "neighbour_only", "none", "blocked", "unresolved"]
    outcomes = {k: sum(r["outcome"] == k for r in done) for k in names}
    outcomes["other"] = len(done) - sum(outcomes.values())
    hits = sorted((r["timestamp"], r["host"]) for r in done if r["outcome"] == "pre1996_capture")
    years: dict[str, int] = {}
    for ts, _ in hits:
        years[ts[:4]] = years.get(ts[:4], 0) + 1
    k, n = outcomes["pre1996_capture"], len(done)
    earliest = f", earliest {hits[0][0][:4]}" if hits else ""
    added = sum(r["named_in"] == "added" for r in sample)
    resolved = n - outcomes["unresolved"]
    listed = sum(r["named_in"] != "added" and r["outcome"] != "unresolved" for r in done)
    spread = ", ".join(f"{y}: {c}" for y, c in sorted(years.items())) or "none"
    return {
        "id": TEST_ID,
        "question": "Q1",
        "title": "IA captures before 1996",
        "label": "Tested, not independently verified",
        "command": command,
        "sources": [BASE + p for p in PAGES] + [CDX],
        "population": (
            f"{len(sample)} hosts: the web servers named in CERN's November 1992 server list, "
            "plus info.cern.ch, www.w3.org and www.ncsa.uiuc.edu."
        ),
        "sample": f"{len(sample)} early servers, {len(sample) - added} from CERN's 1992 list",
        "query": (
            "url=<host>/*&to=1995&fl=timestamp,original,statuscode&limit=50; exact host parsed "
            "from original; a full answer without a match is asked again with "
            "filter=original:^https?://<host>(:[0-9]+)?(/|$)."
        ),
        "outcomes": outcomes,
        "result": (
            f"{k} of {resolved} have a capture before 1996{earliest} "
            f"({outcomes['unresolved']} unresolved)"
        ),
        "finding": (
            f"The Internet Archive holds captures before 1996 for only {k} of {resolved} early "
            f"web servers (by first year: {spread})."
            if k
            else "The Internet Archive holds no capture before 1996 even for the web's first "
            f"servers: none of {resolved} early servers, {listed} of them on CERN's 1992 list, "
            "has one."
        ),
        "limits": (
            "The list is small and CERN-centred, a census of one dated source, not a sample "
            "of the pre-1996 web. A stamp dates the capture, not the content."
        ),
        "started_at": lines[0][0] if lines else "",
        "finished_at": lines[-1][0] if lines else "",
        "requests": len(lines),
        "unresolved": outcomes["unresolved"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--stop-at", help="start no host after this UTC time")
    ap.add_argument("--report", action="store_true", help="rewrite result.json, ask nothing")
    args = ap.parse_args()
    stop_at = None
    command = "uv run python scripts/orq/q1-ia-pre1996.py"
    if args.stop_at:
        stop_at = datetime.strptime(args.stop_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        command += f" --stop-at {args.stop_at}"
    OUT.mkdir(parents=True, exist_ok=True)
    if (OUT / "sample.csv").exists():
        with open(OUT / "sample.csv", encoding="utf-8", newline="") as f:
            sample = list(csv.DictReader(f))
    else:
        sample = draw()
        save(sample)
    if args.report:
        result = json.dumps(report(sample, command), indent=2) + "\n"
        (OUT / "result.json").write_text(result, encoding="utf-8")
        return 0
    with open(OUT / "log.txt", "a", encoding="utf-8") as log:
        log.write(f"# run {utc()}: {sum(r['outcome'] in TODO for r in sample)} hosts to do\n")
        ch = Channel(log, stop_at)
        try:
            for r in sample:
                if r["outcome"] not in TODO:
                    continue
                if stop_at and datetime.now(UTC) >= stop_at:
                    log.write(f"# stop time {args.stop_at} reached at host {r['order']}\n")
                    break
                try:
                    check(ch, r)
                except Abandoned:
                    break
                save(sample)
        finally:
            save(sample)
            result = json.dumps(report(sample, command), indent=2) + "\n"
            (OUT / "result.json").write_text(result, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
