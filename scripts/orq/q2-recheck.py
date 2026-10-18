"""q2-recheck: does the live CDX confirm a uniform sample of our own hostname-year additions?

It reads the extended ledger as it was when this ran, with an `evidence_url` column; the
ledger now names the journal line instead, so it is kept as run, not rerun.

    uv run python scripts/orq/q2-recheck.py [--stop-at 2026-10-13T00:45:00Z]

Draws 300 records from the 1996 to 2001 additions (output/netnew/{Y}.txt and
{Y}_hostnames.txt) and 300 from the 2002 to 2013 additions
(output/extended_years/additions/{Y}.txt), seed 20261012, interleaved at random, and asks
the CDX for each (host, year):

    url=<host>/*&from=<Y>&to=<Y>&filter=statuscode:[23][0-9][0-9]
    &fl=timestamp,original,statuscode&limit=500

"confirmed" when a row's original URL has exactly that host (the SURT key folds www. into
the apex, so the host is parsed from the original field). A full answer of 500 rows with no
exact match is asked once more with filter=original:^https?://<host>(:[0-9]+)?(/|$); an
answer under 500 rows is complete, so no exact match there is "not_found". A throttle,
timeout, refused connect or 5xx is retried (Retry-After, else 60 s doubling, 6 tries) and
never counted as not_found: an exhausted record is "unresolved". A 403 is "blocked" (the
archive withholds the host). One request in flight, starts at least 3 s apart.

Resumable: sample.csv holds the whole sample and each record's outcome, rewritten after
every record; a rerun skips done records. The sample is in random order, so the completed
prefix is a uniform sample. Writes only under docs/orq/results/q2-recheck/.
"""

import argparse
import csv
import email.utils
import http.client
import json
import math
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

TEST_ID = "q2-recheck"
SEED = 20261012
PER_PART = 300
LIMIT = 500
CDX = "https://web.archive.org/cdx/search/cdx"
UA = "internet-digital-ark/1.0 (research; Open Research Questions test)"
GAP, TIMEOUT, TRIES = 3.0, 60, 6
TODO = ("", "unresolved")  # a rerun asks an unresolved record again
OUT = Path("docs/orq/results") / TEST_ID
NETNEW = Path("output/netnew")
EXTENDED = Path("output/extended_years")
EARLY, LATE = "1996 to 2001", "2002 to 2013"
FIELDS = [
    "order", "part", "year", "host", "source_file", "our_method", "our_evidence_url",
    "outcome", "query", "rows", "timestamp", "original", "statuscode", "wayback_url",
    "attempts",
]  # fmt: skip
URLS = ("our_evidence_url", "original", "wayback_url")
SHIPPED = [f for f in FIELDS if f not in URLS]
FULL = OUT / "cache" / "sample.csv"
EXPORT = "2026-10-11"


def utc(t: datetime | None = None) -> str:
    return (t or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")


def early_files():
    for y in range(1996, 2002):
        for name in (f"{y}.txt", f"{y}_hostnames.txt"):
            yield y, NETNEW / name


def late_files():
    for y in range(2002, 2014):
        yield y, EXTENDED / "additions" / f"{y}.txt"


def hosts(path: Path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            h = line.strip().lower()
            if h:
                yield h


def population() -> dict:
    """The export the sample was drawn from; the files have grown since."""
    return {EARLY: 24_679, LATE: 14_140_106}


def our_evidence(sample: list[dict]) -> None:
    """Attach the method and capture URL each record shipped on, from the export's ledgers."""
    want = {(r["host"], r["year"]): r for r in sample}
    for name, key in (
        ("evidence_manifest.csv", "domain"),
        ("hostnames_evidence_manifest.csv", "hostname"),
    ):
        with open(NETNEW / name, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                r = want.get((row[key].lower(), row["assigned_year"]))
                if r and not r["our_method"]:
                    r["our_method"], r["our_evidence_url"] = (
                        row["acquisition_method"],
                        row["evidence_url"],
                    )
    late = {k for k, r in want.items() if r["part"] == LATE}
    with open(EXTENDED / "evidence_ledger.csv", encoding="utf-8", newline="") as f:
        for row in csv.reader(f):
            k = (row[1].lower(), row[0])
            if k in late and not want[k]["our_method"]:
                want[k]["our_method"], want[k]["our_evidence_url"] = row[2], row[6]


def draw() -> list[dict]:
    rng = random.Random(SEED)
    early = [(y, h, p.as_posix()) for y, p in early_files() for h in hosts(p)]
    picked = rng.sample(early, PER_PART)
    reservoir, seen = [], 0
    for y, p in late_files():
        for h in hosts(p):
            seen += 1
            if len(reservoir) < PER_PART:
                reservoir.append((y, h, p.as_posix()))
            elif (j := rng.randrange(seen)) < PER_PART:
                reservoir[j] = (y, h, p.as_posix())
    records = [(EARLY, *r) for r in picked] + [(LATE, *r) for r in reservoir]
    rng.shuffle(records)
    sample = [
        {
            **dict.fromkeys(FIELDS, ""),
            "order": str(i),
            "part": part,
            "year": str(y),
            "host": h,
            "source_file": src,
        }
        for i, (part, y, h, src) in enumerate(records, 1)
    ]
    our_evidence(sample)
    return sample


def save(sample: list[dict]) -> None:
    """The whole record to the git-ignored cache, which a rerun resumes from; the shipped
    sample.csv without the capture URLs, which a rerun of each logged query returns."""
    FULL.parent.mkdir(parents=True, exist_ok=True)
    (FULL.parent / ".gitignore").write_text("*\n", encoding="utf-8")
    for path, fields in ((FULL, FIELDS), (OUT / "sample.csv", SHIPPED)):
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(sample)
        tmp.replace(path)


def exact_host(original: str) -> str | None:
    s = original.strip()
    if "://" not in s[:12]:
        s = "http://" + s
    try:
        h = urllib.parse.urlsplit(s).hostname
    except ValueError:
        return None
    return h.rstrip(".") if h else None


def query_url(host: str, year: str, anchored: bool) -> str:
    q = [
        ("url", f"{host}/*"),
        ("from", year),
        ("to", year),
        ("filter", "statuscode:[23][0-9][0-9]"),
    ]
    if anchored:
        q.append(("filter", "original:^https?://" + re.escape(host) + "(:[0-9]+)?(/|$)"))
    q += [("fl", "timestamp,original,statuscode"), ("limit", str(LIMIT))]
    return CDX + "?" + urllib.parse.urlencode(q, safe="/*:,")


class Abandoned(Exception):
    """The stop time fell inside a back-off: the record is left undone, never counted."""


class Channel:
    def __init__(self, log, stop_at: datetime):
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
                    return (
                        r.status,
                        r.read().decode("utf-8", "replace"),
                        time.monotonic() - t0,
                        attempt,
                    )
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
            if datetime.now(UTC).timestamp() + delay > self.stop_at.timestamp():
                self.line(
                    url, status, secs, "transient, stop time inside back-off, record left undone"
                )
                raise Abandoned
            self.line(url, status, secs, f"transient, retry in {delay:.0f} s")
            time.sleep(delay)
            wait *= 2
        raise AssertionError


def backoff(header: str | None, wait: float) -> float:
    if header:
        if header.strip().isdigit():
            return float(header.strip())
        try:
            return max(0.0, email.utils.parsedate_to_datetime(header).timestamp() - time.time())
        except (TypeError, ValueError):
            pass
    return wait


def rows(body: str) -> list[tuple[str, str, str]]:
    out = []
    for line in body.splitlines():
        parts = line.split(" ")
        if len(parts) >= 3:
            out.append((parts[0], " ".join(parts[1:-1]), parts[-1]))
    return out


def check(ch: Channel, r: dict) -> None:
    host, year, tries = r["host"], r["year"], 0
    for anchored in (False, True):
        url = query_url(host, year, anchored)
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
        hits = sorted(x for x in got if exact_host(x[1]) == host)
        full = len(got) >= LIMIT
        if hits:
            outcome = "confirmed"
        elif full and not anchored:
            outcome = "no exact host in a full answer, anchoring"
        else:
            outcome = "not_found"
        ch.line(url, status, secs, f"{outcome} rows={len(got)}")
        if hits:
            ts, original, code = hits[0]
            wayback = f"https://web.archive.org/web/{ts}/{original}"
            r.update(outcome="confirmed", query=query, rows=str(len(got)), timestamp=ts)
            r.update(original=original, statuscode=code, wayback_url=wayback, attempts=str(tries))
            return
        if outcome == "not_found":
            r.update(outcome="not_found", query=query, rows=str(len(got)), attempts=str(tries))
            return


def wilson(k: int, n: int) -> tuple[float, float]:
    if not n:
        return 0.0, 0.0
    z, p = 1.96, k / n
    mid = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return 100 * (mid - half), 100 * (mid + half)


def pct(k: int, n: int) -> str:
    return f"{100 * k / n:.1f}%" if n else "n/a"


def report(sample: list[dict], pop: dict, command: str) -> dict:
    lines = [
        ln.split(" ")
        for ln in (OUT / "log.txt").read_text(encoding="utf-8").splitlines()
        if ln and ln[0] != "#"
    ]
    done = [r for r in sample if r["outcome"]]
    names = ["confirmed", "not_found", "blocked", "unresolved"]
    outcomes, parts = {}, {}
    for label, part in (("1996_2001", EARLY), ("2002_2013", LATE), ("all", None)):
        sub = [r for r in done if part is None or r["part"] == part]
        c = {k: sum(r["outcome"] == k for r in sub) for k in names}
        c["other"] = len(sub) - sum(c.values())
        parts[label] = (len(sub), c)
        outcomes.update({f"{k}_{label}": v for k, v in c.items()})
    n, c = parts["all"]
    (na, ca), (nb, cb) = parts["1996_2001"], parts["2002_2013"]
    resolved = c["confirmed"] + c["not_found"]
    lo, hi = wilson(c["confirmed"], resolved)
    missing = n - c["confirmed"] - c["unresolved"]
    return {
        "id": TEST_ID,
        "question": "Q2",
        "title": "Live CDX recheck of our year assignments",
        "label": "Tested, not independently verified",
        "command": command,
        "sources": [CDX],
        "population": (
            f"{pop[EARLY]:,} hostname-year additions for {EARLY} "
            f"and {pop[LATE]:,} for {LATE} in our export of {EXPORT}."
        ),
        "sample": (f"{n} of {len(sample)} of our records done, seeded"),
        "query": (
            "url=<host>/*&from=<Y>&to=<Y>&filter=statuscode:[23][0-9][0-9]"
            "&fl=timestamp,original,statuscode&limit=500; exact host parsed from original; "
            "a full answer without a match is asked again with "
            "filter=original:^https?://<host>(:[0-9]+)?(/|$)."
        ),
        "outcomes": outcomes,
        "result": (
            f"{c['confirmed']} of {n} years confirmed ({ca['confirmed']} of {na} for {EARLY}, "
            f"{cb['confirmed']} of {nb} for {LATE}); {c['unresolved']} unresolved"
        ),
        "finding": (
            f"{pct(c['confirmed'], resolved)} of resolved records (95% CI {lo:.1f} to {hi:.1f}%) "
            "carry a same-year exact-host 2xx or 3xx capture that anyone can re-query today. "
            + (
                f"The {missing} without one are listed in sample.csv."
                if missing
                else "A year assigned this way reproduces from the public index alone."
            )
        ),
        "limits": (
            "A capture proves an archived response from that host in that year, not page content. "
            + (
                f"{n} of {len(sample)} drawn records completed before the stop time; "
                "the order is random, so they are a uniform sample."
                if n < len(sample)
                else "The CDX index changes, so a record not found today may have been withdrawn."
            )
        ),
        "started_at": lines[0][0] if lines else "",
        "finished_at": lines[-1][0] if lines else "",
        "requests": len(lines),
        "unresolved": c["unresolved"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--stop-at", default="2026-10-13T00:45:00Z", help="start no record after this UTC time"
    )
    ap.add_argument("--report", action="store_true", help="rewrite result.json, ask nothing")
    args = ap.parse_args()
    stop_at = datetime.strptime(args.stop_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    command = "uv run python scripts/orq/q2-recheck.py"
    OUT.mkdir(parents=True, exist_ok=True)
    pop = population()
    if FULL.exists() or (OUT / "sample.csv").exists():
        with open(FULL if FULL.exists() else OUT / "sample.csv", encoding="utf-8", newline="") as f:
            sample = list(csv.DictReader(f))
    else:
        sample = draw()
        save(sample)
    if args.report:
        result = json.dumps(report(sample, pop, command), indent=2) + "\n"
        (OUT / "result.json").write_text(result, encoding="utf-8")
        return 0
    with open(OUT / "log.txt", "a", encoding="utf-8") as log:
        log.write(f"# run {utc()}: {sum(r['outcome'] in TODO for r in sample)} records to do\n")
        ch = Channel(log, stop_at)
        try:
            for r in sample:
                if r["outcome"] not in TODO:
                    continue
                if datetime.now(UTC) >= stop_at:
                    log.write(f"# stop time {args.stop_at} reached at record {r['order']}\n")
                    break
                try:
                    check(ch, r)
                except Abandoned:
                    break
                save(sample)
        finally:
            save(sample)
            log.flush()
            (OUT / "result.json").write_text(
                json.dumps(report(sample, pop, command), indent=2) + "\n", encoding="utf-8"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
