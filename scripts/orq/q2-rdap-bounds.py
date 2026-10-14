"""Q2 test q2-rdap-bounds: can a registration date bound or assign a year?

    uv run python scripts/orq/q2-rdap-bounds.py

Our 1996 to 2001 additions hold no .com or .net registrable, so the population is his
release's 1996 to 2001 .com and .net registrables, each a year his evidence rule already
established. Draws 200 record-years uniformly with seed 20261012 and asks Verisign RDAP
(`https://rdap.verisign.com/<tld>/v1/domain/<name>`) for the registration event date. At most
one request per second. A throttle (429 or 403), timeout, refused connect or 5xx is retried
(Retry-After, else 60 s doubling, 6 tries) and never counted as "not registered now".

Resumable: the sample is fixed in sample.csv on the first run; a rerun skips decided records
and retries unresolved ones. Writes only under docs/orq/results/q2-rdap-bounds/.
"""

import argparse
import csv
import datetime
import json
import os
import random
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from ark.baseline import baseline_dir

TEST_ID = "q2-rdap-bounds"
SEED = 20261012
EXPORT = "2026-10-11"  # the export whose 1996 to 2001 additions held no .com or .net
SIZE = 200
GAP = 1.1  # seconds between RDAP requests
TRIES = 6
TIMEOUT = 30
UA = "InternetDigitalArk/1.0 (historical domain research)"
OUT = Path("docs/orq/results") / TEST_ID
NAME = re.compile(rb"^[a-z0-9-]+\.(com|net)$")
RDAP = "https://rdap.verisign.com/{tld}/v1/domain/{name}"
TERMS = "https://www.verisign.com/domain-names/registration-data-access-protocol/terms-service/index.xhtml"

ON_OR_BEFORE = "registered on or before the record's year"
AFTER = "registered after the record's year"
GONE = "not registered now"
NO_DATE = "no registration date"
UNRESOLVED = "unresolved"
OUTCOMES = (ON_OR_BEFORE, AFTER, GONE, NO_DATE, UNRESOLVED)
FIELDS = (
    "year",
    "domain",
    "rdap_url",
    "status",
    "registration_date",
    "gap_years",
    "outcome",
    "tries",
)


def now() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def population(release: Path):
    """(year, name) for every .com and .net line of his 1996 to 2001 files, in file order."""
    for year in range(1996, 2002):
        with open(release / f"{year}.txt", "rb") as fh:
            for line in fh:
                line = line.strip().lower()
                if NAME.match(line):
                    yield year, line.decode()


def load_or_draw(release: Path) -> tuple[list[dict], int]:
    path, meta = OUT / "sample.csv", OUT / "population.json"
    if path.exists() and meta.exists():
        with open(path, encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh)), json.loads(meta.read_text())["records"]
    size = sum(1 for _ in population(release))
    wanted = set(random.Random(SEED).sample(range(size), SIZE))
    rows = []
    for i, (year, name) in enumerate(population(release)):
        if i in wanted:
            row = dict.fromkeys(FIELDS, "")
            tld = name.rsplit(".", 1)[1]
            row.update(year=year, domain=name, rdap_url=RDAP.format(tld=tld, name=name))
            rows.append(row)
    meta.write_text(json.dumps({"records": size}) + "\n")
    save(rows)
    return rows, size


def save(rows: list[dict]) -> None:
    tmp = OUT / "sample.csv.tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, OUT / "sample.csv")


_last = [0.0]


def log(url: str, status, seconds: float, outcome: str) -> None:
    with open(OUT / "log.txt", "a", encoding="utf-8") as fh:
        fh.write(f"{now()}\t{url}\t{status}\t{seconds:.2f}\t{outcome}\n")


def request(url: str):
    wait = GAP - (time.monotonic() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rdap+json"})
    start = time.monotonic()
    try:
        try:
            resp = urllib.request.urlopen(req, timeout=TIMEOUT)
        except urllib.error.HTTPError as err:
            resp = err
        status, headers, body, error = resp.getcode(), resp.headers, resp.read(1 << 20), None
    except Exception as exc:  # network failure: timeout, refused, reset
        status, headers, body, error = f"ERR:{type(exc).__name__}", None, b"", exc
    _last[0] = time.monotonic()
    return status, headers, body, error, _last[0] - start


def backoff(headers, attempt: int) -> float:
    retry = headers.get("Retry-After") if headers else None
    if retry and retry.strip().isdigit():
        return float(retry)
    return 60.0 * 2 ** (attempt - 1)


def ask(row: dict) -> None:
    url = row["rdap_url"]
    for attempt in range(1, TRIES + 1):
        status, headers, body, error, secs = request(url)
        row["tries"], row["status"] = attempt, status
        if error is None and status not in (403, 429) and status < 500:
            break
        log(url, status, secs, "retry" if attempt < TRIES else UNRESOLVED)
        if attempt == TRIES:
            row["outcome"] = UNRESOLVED
            return
        time.sleep(backoff(headers, attempt))
    if status == 404:
        row["outcome"] = GONE
    elif status == 200:
        events = json.loads(body).get("events", [])
        date = next((e["eventDate"] for e in events if e.get("eventAction") == "registration"), "")
        row["registration_date"] = date
        if not date:
            row["outcome"] = NO_DATE
        else:
            gap = int(date[:4]) - int(row["year"])
            row["gap_years"] = gap
            row["outcome"] = AFTER if gap > 0 else ON_OR_BEFORE
    else:
        row["outcome"] = f"HTTP {status}"
    log(url, status, secs, row["outcome"])


def report(rows: list[dict], size: int, started: str) -> None:
    counts = {o: sum(r["outcome"] == o for r in rows) for o in OUTCOMES}
    for r in rows:
        if r["outcome"] not in counts:
            counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    counts = {k: v for k, v in counts.items() if v}
    n = len(rows)
    after, gone = counts.get(AFTER, 0), counts.get(GONE, 0)
    gaps = [int(r["gap_years"]) for r in rows if r["outcome"] == AFTER]
    median = statistics.median(gaps) if gaps else 0
    with open(OUT / "log.txt", encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    requests, finished = len(lines), lines[-1].split("\t")[0]
    result = {
        "id": TEST_ID,
        "question": "Q2",
        "title": "Can a registration date bound a year?",
        "label": "Tested, not independently verified",
        "command": "uv run python " + " ".join(sys.argv),
        "sources": ["https://rdap.verisign.com/com/v1/domain/<name>", TERMS],
        "population": (
            f"Your merge261008-3 1996.txt to 2001.txt .com and .net registrables: {size:,} "
            f"record-years (our export of {EXPORT} holds none for 1996 to 2001)."
        ),
        "sample": f"{n} .com and .net record-years, seeded",
        "query": (
            "GET https://rdap.verisign.com/<tld>/v1/domain/<name>; compare the year of its "
            "registration event with the record year; 404 is not registered now."
        ),
        "outcomes": counts,
        "result": (
            f"{after} of {n} ({100 * after / n:.0f}%) registered after the record's year; "
            f"{gone} not registered now"
        ),
        "finding": (
            "Today's registration date can neither assign nor bound a past year: "
            f"for {100 * after / n:.0f}% of sampled record-years it falls after the year your "
            f"files prove, by a median {median:g} years."
        ),
        "limits": (
            "Historical WHOIS, which could show earlier registrations, is Pending validation. "
            "Verisign's terms bar high-volume automated queries, so this suits samples, not bulk."
        ),
        "started_at": started,
        "finished_at": finished,
        "requests": requests,
        "unresolved": counts.get(UNRESOLVED, 0),
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=1, ensure_ascii=False))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--release", type=Path, default=baseline_dir(), help="his release folder")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    prior = OUT / "result.json"
    started = json.loads(prior.read_text())["started_at"] if prior.exists() else now()
    rows, size = load_or_draw(args.release)
    for row in rows:
        if row["outcome"] and row["outcome"] != UNRESOLVED:
            continue
        ask(row)
        save(rows)
        print(f"{row['year']} {row['domain']}: {row['outcome']}", flush=True)
    report(rows, size, started)
    return 0


if __name__ == "__main__":
    sys.exit(main())
