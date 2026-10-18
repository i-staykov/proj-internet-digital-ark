"""Q2 test q2-capture-content: is a cited 2xx or 3xx capture really a website?

It reads the extended ledger as it was when this ran, with an `evidence_url` column; the
ledger now names the journal line instead, so it is kept as run, not rerun.

    uv run python scripts/orq/q2-capture-content.py [--evidence-dir DIR]

Draws 75 records from the 1996 to 2001 additions (registrable and hostname) and 75 from the
2002 to 2013 additions, uniformly with seed 20261012, takes each record's cited capture from
its evidence row, fetches the raw capture `https://web.archive.org/web/<ts>id_/<original>`
and classifies it. Wayback's own timestamp hops (a 3xx without `Memento-Datetime`) are
followed; a captured 3xx is the record's answer. The served `Memento-Datetime` must fall in
the record's year. A throttle, timeout, refused connect or 5xx is retried (Retry-After,
else 60 s doubling, 6 tries) and never counted as an outcome other than "unresolved".

Resumable: the sample is fixed in sample.csv on the first run; a rerun skips decided records
and retries unresolved ones. Writes only under docs/orq/results/q2-capture-content/.
"""

import argparse
import csv
import datetime
import email.utils
import gzip
import html
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

TEST_ID = "q2-capture-content"
SEED = 20261012
PER_PART = 75
EXPORT = "2026-10-11"  # the export the sample was drawn from
GAP = 3.0  # seconds between web.archive.org requests
TRIES = 6
TIMEOUT = 60
CAP = 1 << 20  # bytes read per capture
UA = "InternetDigitalArk/1.0 (historical domain research)"
OUT = Path("docs/orq/results") / TEST_ID
NETNEW = Path("output/netnew")
LEDGER = Path("output/extended_years/evidence_ledger.csv")
REPLAY = re.compile(r"^(?:https?://web\.archive\.org)?/web/(\d{4,14})(?:[a-z]{2}_)?/(.+)$")

# Markers, matched lowercase. A title match decides; a body match decides only on a short page.
PLACEHOLDER = (
    "under construction",
    "coming soon",
    "launching soon",
    "under development",
    "future home of",
    "domain for sale",
    "domain is for sale",
    "domain name is for sale",
    "domain may be for sale",
    "buy this domain",
    "purchase this domain",
    "parked domain",
    "domain parking",
    "this domain is parked",
    "parked free",
    "parked by",
    "has been registered by",
    "domain has been registered",
    "reserved for future use",
    "it works!",
    "test page for the apache",
    "apache http server test page",
    "welcome to nginx",
    "iis windows server",
    "internet information services",
    "default web site page",
    "cpanel",
    "placeholder page",
    "holding page",
    "temporary page",
    "check back soon",
    "site is being built",
    "welcome to your new website",
    "sponsored listings",
    "related searches",
)
ERROR_TEXT = (
    "not found",
    "error 404",
    "http 404",
    "403 forbidden",
    "forbidden",
    "access denied",
    "the requested url",
    "cannot be found",
    "could not be found",
    "does not exist",
    "no such file",
    "bad request",
    "internal server error",
    "service unavailable",
    "account suspended",
    "account has been suspended",
    "suspended",
    "no such domain",
    "no website configured",
    "temporarily unavailable",
    "bandwidth limit exceeded",
    "has expired",
)
PLACEHOLDER_WORDS = 300  # a body marker counts only under this many visible words
ERROR_WORDS = 100
SCRIPT_REDIRECT = re.compile(
    r"(?:window|document|top|self)\.location(?:\.href)?\s*=\s*|location\.replace\(\s*"
)
SCRIPT_TARGET = re.compile(r"[\"']([^\"']+)[\"']")
META_REFRESH = re.compile(r"<meta[^>]+http-equiv\s*=\s*[\"']?refresh[^>]*>", re.I | re.S)
REFRESH_URL = re.compile(r"url\s*=\s*['\"]?([^'\">\s]+)", re.I)
LINK = re.compile(r"<(a|area)\s[^>]*href\s*=|<(i?frame)\s[^>]*src\s*=", re.I)
HTML_SNIFF = re.compile(r"<\s*(!doctype html|html|head|body|title|frameset|table|p|a)\b", re.I)

OUTCOMES = (
    "site content",
    "placeholder",
    "redirect",
    "error text in a 2xx",
    "non-HTML",
    "empty HTML",
    "captured error status",
    "replay year mismatch",
    "not replayable",
    "unresolved",
)
FIELDS = (
    "part",
    "year",
    "kind",
    "host",
    "cited_timestamp",
    "original_url",
    "replay_url",
    "status",
    "memento_datetime",
    "served_original",
    "content_type",
    "bytes",
    "words",
    "links",
    "title",
    "marker",
    "redirect_to",
    "redirect_scope",
    "outcome",
    "tries",
)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def now() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ sample


def part_a(evidence_dir: Path) -> tuple[list[dict], int]:
    """Every 1996 to 2001 addition, in file order, with its cited capture."""
    records = []
    for year in range(1996, 2002):
        for kind, name in (("registrable", f"{year}.txt"), ("hostname", f"{year}_hostnames.txt")):
            with open(NETNEW / name, encoding="utf-8") as fh:
                records += [(kind, line.strip(), year) for line in fh if line.strip()]
    rng = random.Random(SEED)
    picked = [records[i] for i in sorted(rng.sample(range(len(records)), PER_PART))]
    cited = {}
    for name, key in (
        ("evidence_manifest.csv", "domain"),
        ("hostnames_evidence_manifest.csv", "hostname"),
    ):
        with open(evidence_dir / name, encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                cited[(row[key], int(row["assigned_year"]))] = row["evidence_url"]
    out = []
    for kind, host, year in picked:
        url = cited.get((host, year))
        if url is None:
            sys.exit(f"no evidence row for {host} {year} in {evidence_dir}")
        out.append(record("1996-2001", year, kind, host, url))
    return out, len(records)


def part_b() -> tuple[list[dict], int]:
    """A uniform draw over the ledger's rows: one row per 2002 to 2013 addition."""
    with open(LEDGER, "rb") as fh:
        rows = sum(1 for _ in fh) - 1
    rng = random.Random(SEED)
    wanted = set(rng.sample(range(rows), PER_PART))
    out = []
    with open(LEDGER, "rb") as fh:
        header = next(csv.reader([fh.readline().decode()]))
        for i, line in enumerate(fh):
            if i in wanted:
                row = dict(zip(header, next(csv.reader([line.decode()])), strict=True))
                out.append(
                    record(
                        "2002-2013", int(row["year"]), "hostname", row["host"], row["evidence_url"]
                    )
                )
    return out, rows


def record(part: str, year: int, kind: str, host: str, evidence_url: str) -> dict:
    match = REPLAY.match(evidence_url)
    if not match:
        sys.exit(f"not a replay url: {evidence_url}")
    ts, original = match.groups()
    row = dict.fromkeys(FIELDS, "")
    row.update(
        part=part, year=year, kind=kind, host=host, cited_timestamp=ts, original_url=original
    )
    row["replay_url"] = f"https://web.archive.org/web/{ts}id_/{original}"
    return row


def load_or_draw(evidence_dir: Path) -> tuple[list[dict], dict]:
    path = OUT / "sample.csv"
    meta_path = OUT / "population.json"
    if path.exists() and meta_path.exists():
        with open(path, encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh)), json.loads(meta_path.read_text())
    a, size_a = part_a(evidence_dir)
    b, size_b = part_b()
    meta = {"1996-2001": size_a, "2002-2013": size_b}
    meta_path.write_text(json.dumps(meta) + "\n")
    save(a + b)
    return a + b, meta


def save(rows: list[dict]) -> None:
    for row in rows:  # the deliverable carries no en or em dash, quoted titles included
        row["title"] = row["title"].replace("\u2013", "-").replace("\u2014", "-")
    tmp = OUT / "sample.csv.tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, OUT / "sample.csv")


# ------------------------------------------------------------------ fetch

_last = [0.0]


def log(url: str, status, seconds: float, outcome: str) -> None:
    with open(OUT / "log.txt", "a", encoding="utf-8") as fh:
        fh.write(f"{now()}\t{url}\t{status}\t{seconds:.2f}\t{outcome}\n")


def request(url: str):
    wait = GAP - (time.monotonic() - _last[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    start = time.monotonic()
    try:
        try:
            resp = OPENER.open(req, timeout=TIMEOUT)
        except urllib.error.HTTPError as err:
            resp = err
        body = resp.read(CAP)
        status, headers = resp.getcode(), resp.headers
        error = None
    except Exception as exc:  # network failure: timeout, refused, reset
        status, headers, body, error = f"ERR:{type(exc).__name__}", None, b"", exc
    _last[0] = time.monotonic()
    return status, headers, body, error, _last[0] - start


def transient(status, headers, error) -> bool:
    if error is not None:
        return True
    memento = headers.get("Memento-Datetime")
    return status == 429 or (status >= 500 and not memento)


def backoff(headers, attempt: int) -> float:
    retry = headers.get("Retry-After") if headers else None
    if retry and retry.strip().isdigit():
        return float(retry)
    return 60.0 * 2 ** (attempt - 1)


def fetch(url: str) -> tuple:
    """The served response after Wayback timestamp hops, or None after TRIES transient fails."""
    tries = 0
    for _hop in range(4):
        for attempt in range(1, TRIES + 1):
            tries += 1
            status, headers, body, error, secs = request(url)
            if not transient(status, headers, error):
                break
            log(url, status, secs, "retry" if attempt < TRIES else "unresolved")
            if attempt == TRIES:
                return None, tries
            time.sleep(backoff(headers, attempt))
        location = headers.get("Location", "")
        hop = 300 <= status < 400 and not headers.get("Memento-Datetime")
        if hop and _hop < 3 and REPLAY.match(location):
            log(url, status, secs, "timestamp hop")
            url = urllib.parse.urljoin(url, location)
            continue
        break
    return (url, status, headers, body, secs), tries


# ------------------------------------------------------------------ classify


def decode(headers, body: bytes) -> str:
    enc = (headers.get("Content-Encoding") or "").lower()
    try:
        if "gzip" in enc:
            body = gzip.decompress(body)
        elif "deflate" in enc:
            body = zlib.decompress(body)
    except Exception:
        pass
    return body.decode("utf-8", "replace")


def visible(text: str) -> tuple[str, str]:
    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    title = html.unescape(re.sub(r"\s+", " ", title.group(1))).strip() if title else ""
    body = re.sub(r"(?is)<(script|style)\b.*?</\1>|<!--.*?-->", " ", text)
    body = html.unescape(re.sub(r"<[^>]+>", " ", body))
    return title, re.sub(r"\s+", " ", body).strip()


def unwrap(location: str) -> str:
    match = REPLAY.match(location)
    return match.group(2) if match else location


def scope(row: dict) -> str:
    """Whether a redirect stays on the record's own host."""
    if row["outcome"] != "redirect":
        return ""
    if not row["redirect_to"]:
        return "unknown"
    target = urllib.parse.urlsplit(urllib.parse.urljoin(row["original_url"], row["redirect_to"]))
    return "same host" if (target.hostname or "") == row["host"].lower() else "other host"


def first(markers, text: str) -> str:
    return next((m for m in markers if m in text), "")


def classify(row: dict, served) -> None:
    url, status, headers, body, _ = served
    row["replay_url"] = url
    row["status"] = status
    memento = headers.get("Memento-Datetime", "")
    row["memento_datetime"] = memento
    original = re.search(r"<([^>]+)>;\s*rel=\"original\"", headers.get("Link", ""))
    row["served_original"] = original.group(1) if original else ""
    row["content_type"] = headers.get("Content-Type", "")
    row["bytes"] = len(body)
    if not memento:
        row["outcome"] = "not replayable"
        return
    if email.utils.parsedate_to_datetime(memento).year != int(row["year"]):
        row["outcome"] = "replay year mismatch"
        return
    if 300 <= status < 400:
        row["redirect_to"] = unwrap(headers.get("Location", ""))
        row["outcome"] = "redirect"
        return
    if status >= 400:
        row["outcome"] = "captured error status"
        return
    text = decode(headers, body)
    if "html" not in row["content_type"].lower() and not HTML_SNIFF.search(text[:4096]):
        row["outcome"] = "non-HTML"
        return
    title, words_text = visible(text)
    words = len(re.findall(r"\w+", words_text))
    links = len(LINK.findall(text))
    row.update(title=title[:80], words=words, links=links)
    low_title, low_body = title.lower(), words_text.lower()
    refresh = META_REFRESH.search(text)
    target = REFRESH_URL.search(refresh.group(0)) if refresh else None
    if target:
        row.update(outcome="redirect", marker="meta refresh", redirect_to=unwrap(target.group(1)))
    elif words < 20 and (script := SCRIPT_REDIRECT.search(text)):
        target = SCRIPT_TARGET.match(text, script.end())
        row.update(outcome="redirect", marker="script redirect")
        row["redirect_to"] = unwrap(target.group(1)) if target else ""
    elif marker := first(PLACEHOLDER, low_title) or (
        words < PLACEHOLDER_WORDS and first(PLACEHOLDER, low_body)
    ):
        row.update(outcome="placeholder", marker=marker)
    elif marker := first(ERROR_TEXT, low_title) or (
        words < ERROR_WORDS and first(ERROR_TEXT, low_body)
    ):
        row.update(outcome="error text in a 2xx", marker=marker)
    elif words >= 10 or links >= 1:
        row["outcome"] = "site content"
    else:
        row["outcome"] = "empty HTML"


# ------------------------------------------------------------------ report


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.0f}%" if d else "0%"


def report(rows: list[dict], meta: dict, started: str) -> None:
    def tally(part=None):
        sel = [r for r in rows if part in (None, r["part"])]
        return {
            o: sum(r["outcome"] == o for r in sel)
            for o in OUTCOMES
            if any(r["outcome"] == o for r in sel)
        }

    for row in rows:
        row["redirect_scope"] = scope(row)
    save(rows)
    total, a, b = tally(), tally("1996-2001"), tally("2002-2013")
    n = len(rows)
    site = total.get("site content", 0)
    other_year = total.get("replay year mismatch", 0)
    unresolved = total.get("unresolved", 0)
    weak = n - site - other_year - unresolved
    with open(OUT / "log.txt", encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    requests, finished = len(lines), lines[-1].split("\t")[0]
    result = {
        "id": TEST_ID,
        "question": "Q2",
        "title": "Is a cited capture a website?",
        "label": "Tested, not independently verified",
        "command": "uv run python " + " ".join(sys.argv),
        "sources": ["https://web.archive.org/web/<timestamp>id_/<original>"],
        "population": (
            f"Our export of {EXPORT}: {meta['1996-2001']:,} records 1996 to 2001 (registrable "
            f"and hostname), {meta['2002-2013']:,} records 2002 to 2013, each with its cited "
            "capture."
        ),
        "sample": f"{n} of our records, seeded",
        "query": (
            "GET /web/<ts>id_/<original>, Wayback timestamp hops followed; "
            "the Memento-Datetime year must equal the record year."
        ),
        "outcomes": total,
        "outcomes_by_part": {"1996-2001": a, "2002-2013": b},
        "result": (
            f"{site} of {n} ({pct(site, n)}) show site content; {other_year} from another year"
        ),
        "finding": (
            f"A 2xx or 3xx status alone does not make a capture a website: {weak} of {n} cited "
            "captures are redirects, placeholders, empty pages or error text."
        ),
        "limits": (
            "Markers are simple string tests on the first 1 MB, so keyword pages of wildcard "
            "hosts pass as site content. Redirect targets are not fetched or judged."
        ),
        "started_at": started,
        "finished_at": finished,
        "requests": requests,
        "unresolved": unresolved,
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=1, ensure_ascii=False))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--evidence-dir",
        type=Path,
        default=NETNEW,
        help="where evidence_manifest.csv and hostnames_evidence_manifest.csv are",
    )
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    prior = OUT / "result.json"
    started = json.loads(prior.read_text())["started_at"] if prior.exists() else now()
    rows, meta = load_or_draw(args.evidence_dir)
    for row in rows:
        if row["outcome"] and row["outcome"] != "unresolved":
            continue
        served, tries = fetch(row["replay_url"])
        row["tries"] = tries
        if served is None:
            row["outcome"] = "unresolved"
        else:
            classify(row, served)
            row["redirect_scope"] = scope(row)
            log(served[0], served[1], served[4], row["outcome"])
        save(rows)
        print(f"{row['part']} {row['year']} {row['host']}: {row['outcome']}", flush=True)
    report(rows, meta, started)
    return 0


if __name__ == "__main__":
    sys.exit(main())
