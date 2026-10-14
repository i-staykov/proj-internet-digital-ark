"""q2-isc-promotion: Ding's ISC / CDX experiment, rerun at four nested evidence levels.

Population: his 1996-ISC.txt and 1997-ISC.txt, one hostname-year record per line, the year
being the file's. A seeded uniform reservoir sample of records is queried in shuffled order,
so any completed prefix is itself a uniform sample.

Levels, each a subset of the one before:
  L1  any CDX row 1996 to 2013 under host/* (his definition, 48 of 1,800 = 2.6667%)
  L2  a row whose original host is exactly the hostname (the SURT urlkey folds www.)
  L3  L2 and stamped in the survey year
  L4  L3 and status 2xx or 3xx: direct year-specific website evidence, promotable

A throttle, timeout, refused connect, unparseable 200 or 5xx is never a "no capture": it backs
off (Retry-After, else 60 s doubling) up to 6 tries, then the record is "unresolved". Resumable:
sample.csv is the state, log.txt is appended, done records are skipped, unresolved ones are
retried after the pending ones. Writes only under docs/orq/results/<id>/.
"""

from __future__ import annotations

import argparse
import csv
import http.client
import json
import math
import os
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from ark.baseline import baseline_dir

TEST_ID = "q2-isc-promotion"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "orq" / "results" / TEST_ID
SEED = 20261012
SIZE = 1200
YEARS = (1996, 1997)
CDX = "https://web.archive.org/cdx/search/cdx"
UA = "internet-digital-ark/1.0 (research; Open Research Questions test)"
LIMIT = 2000
GAP_S = 3.0
TIMEOUT_S = 60
TRIES = 6
DING = (48, 1800)
STATUS_OK = re.compile(r"^[23][0-9][0-9]$")
FIELDS = [
    "order", "hostname", "year", "outcome", "l1", "l2", "l3", "l4", "rows", "exact_rows",
    "exact_years", "evidence_level", "evidence_timestamp", "evidence_original",
    "evidence_status", "requests",
]  # fmt: skip
OUTCOMES = [
    "promotable_l4",
    "same_year_not_2xx_3xx",
    "other_years_only",
    "folded_host_only",
    "no_capture",
    "unresolved",
]


class Unresolved(Exception):
    """Six tries ended in a transient error, or the server refused the query as malformed."""


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm(host: str) -> str:
    return host.strip().lower().rstrip(".")


def host_of(original: str) -> str | None:
    """Exact host of a CDX `original`: lowercase, no port, no trailing dot; None if not a URL."""
    s = original.strip()
    if "://" not in s:
        head = s.split("/", 1)[0]
        if ":" in head and not head.rsplit(":", 1)[1].isdigit():
            return None  # dns:, filedesc: and the like name no web host
        s = "http://" + s
    try:
        h = urllib.parse.urlsplit(s).hostname
    except ValueError:
        return None
    return norm(h) if h else None


def population() -> tuple[list[tuple[str, int]], dict[int, int]]:
    """Algorithm R over every record of both files, then a seeded shuffle for query order."""
    rng = random.Random(SEED)
    res: list[tuple[str, int]] = []
    seen = 0
    per_year: dict[int, int] = {}
    isc = baseline_dir() / "isc_survey_hostnames"  # his release, repository or delivery
    for year in YEARS:
        n = 0
        with open(isc / f"{year}-ISC.txt", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                host = norm(line)
                if not host:
                    continue
                n += 1
                if seen < SIZE:
                    res.append((host, year))
                else:
                    j = rng.randrange(seen + 1)
                    if j < SIZE:
                        res[j] = (host, year)
                seen += 1
        per_year[year] = n
    rng.shuffle(res)
    return res, per_year


class Client:
    """One request in flight, starts at least GAP_S apart, every request logged."""

    def __init__(self, log_path: Path):
        self.log = open(log_path, "a", encoding="utf-8")
        self.last = 0.0
        self.count = 0

    def _line(self, url: str, status: str, secs: float, outcome: str) -> None:
        self.log.write(f"{now()}\t{url}\t{status}\t{secs:.2f}\t{outcome}\n")
        self.log.flush()

    def rows(self, params: list[tuple[str, str]]) -> list[list[str]]:
        q = "&".join(f"{k}={urllib.parse.quote(v, safe='/*,:')}" for k, v in params)
        url = f"{CDX}?{q}"
        for attempt in range(1, TRIES + 1):
            wait = self.last + GAP_S - time.time()
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            self.count += 1
            retry_after = None
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                    body = r.read().decode("utf-8", errors="replace").strip()
                secs = time.time() - self.last
                try:
                    data = json.loads(body) if body else []
                except json.JSONDecodeError:
                    status, why = "200", "unparseable"
                else:
                    rows = [row for row in data[1:] if len(row) >= 3]
                    self._line(url, "200", secs, f"rows={len(rows)}")
                    return rows
            except urllib.error.HTTPError as e:
                secs = time.time() - self.last
                status = str(e.code)
                if e.code != 429 and e.code < 500:
                    self._line(url, status, secs, "rejected")
                    raise Unresolved(f"http {e.code}") from e
                why = "throttled" if e.code == 429 else "server_error"
                retry_after = e.headers.get("Retry-After") if e.headers else None
            except (OSError, ValueError, http.client.HTTPException) as e:  # timeouts, resets
                secs = time.time() - self.last
                status, why = "-", f"net_error:{type(e).__name__}"
            if attempt == TRIES:
                self._line(url, status, secs, f"{why};unresolved")
                raise Unresolved(why)
            backoff = 60 * 2 ** (attempt - 1)
            if retry_after and retry_after.strip().isdigit():
                backoff = min(int(retry_after), 1800)
            self._line(url, status, secs, f"{why};retry_in={backoff}s")
            time.sleep(backoff)
        raise Unresolved("unreachable")


def exact_filter(host: str) -> str:
    return "original:(?i)^([a-z]+://)?([^/@]*@)?" + re.escape(host) + r"\.?(:[0-9]+)?([/?#].*)?$"


def classify(cli: Client, host: str, year: int) -> dict:
    """The main query, plus anchored follow-ups only when 2,000 rows left a level undecided."""
    rows = cli.rows(
        [
            ("url", f"{host}/*"),
            ("from", "1996"),
            ("to", "2013"),
            ("fl", "timestamp,original,statuscode"),
            ("limit", str(LIMIT)),
            ("output", "json"),
        ]
    )
    exact = [r for r in rows if host_of(r[1]) == host]
    l3 = [r for r in exact if r[0][:4] == str(year)]
    l4 = [r for r in l3 if STATUS_OK.match(r[2])]
    rec = {
        "l1": bool(rows),
        "l2": bool(exact),
        "l3": bool(l3),
        "l4": bool(l4),
        "rows": len(rows),
        "exact_rows": len(exact),
        "exact_years": ";".join(sorted({r[0][:4] for r in exact})),
    }
    ev: tuple[str, list[str]] = ("", ["", "", ""])
    for name, hits in (("L1", rows), ("L2", exact), ("L3", l3), ("L4", l4)):
        if hits:
            ev = (name, hits[0])
    if len(rows) >= LIMIT and not rec["l4"]:
        base = [("url", f"{host}/*"), ("fl", "timestamp,original,statuscode"), ("limit", "1")]
        flt = ("filter", exact_filter(host))
        yr = [("from", str(year)), ("to", str(year))]
        ok = ("filter", "statuscode:[23][0-9][0-9]")
        hit = cli.rows(base + yr + [ok, flt, ("output", "json")])
        if hit:
            rec.update(l2=True, l3=True, l4=True)
            ev = ("L4", hit[0])
        if not rec["l3"]:
            hit = cli.rows(base + yr + [flt, ("output", "json")])
            if hit:
                rec.update(l2=True, l3=True)
                ev = ("L3", hit[0])
        if not rec["l2"]:
            hit = cli.rows(base + [("from", "1996"), ("to", "2013"), flt, ("output", "json")])
            if hit:
                rec["l2"] = True
                ev = ("L2", hit[0])
    rec.update(
        evidence_level=ev[0],
        evidence_timestamp=ev[1][0],
        evidence_original=ev[1][1],
        evidence_status=ev[1][2],
    )
    if rec["l4"]:
        rec["outcome"] = "promotable_l4"
    elif rec["l3"]:
        rec["outcome"] = "same_year_not_2xx_3xx"
    elif rec["l2"]:
        rec["outcome"] = "other_years_only"
    elif rec["l1"]:
        rec["outcome"] = "folded_host_only"
    else:
        rec["outcome"] = "no_capture"
    return rec


def wilson(k: int, n: int) -> list[float]:
    if not n:
        return [0.0, 0.0]
    z, p = 1.959964, k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(100 * max(0.0, c - h), 4), round(100 * min(1.0, c + h), 4)]


def two_prop_p(k1: int, n1: int, k2: int, n2: int) -> float:
    if not n1 or not n2:
        return 1.0
    p = (k1 + k2) / (n1 + n2)
    se = math.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    return 1.0 if se == 0 else round(math.erfc(abs(k1 / n1 - k2 / n2) / se / math.sqrt(2)), 4)


def write_csv(path: Path, recs: list[dict]) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in recs:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    os.replace(tmp, path)


def log_stats(log_path: Path) -> tuple[int, int, float]:
    """Requests, transient errors and mean seconds of a 200 answer, read back from log.txt."""
    lines = [ln.rstrip("\n").split("\t") for ln in open(log_path, encoding="utf-8")]
    ok = [float(f[3]) for f in lines if len(f) == 5 and f[2] == "200" and f[4].startswith("rows=")]
    bad = sum(len(f) == 5 and ("retry_in" in f[4] or "unresolved" in f[4]) for f in lines)
    return len(lines), bad, (sum(ok) / len(ok) if ok else 0.0)


def write_result(recs: list[dict], per_year: dict[int, int], meta: dict, log_path: Path) -> None:
    """result.json from the counts in recs and log.txt; never typed by hand."""
    requests, transient, mean_s = log_stats(log_path)
    done = [r for r in recs if r["outcome"] not in ("", "pending")]
    unres = sum(r["outcome"] == "unresolved" for r in done)
    res = [r for r in done if r["outcome"] != "unresolved"]
    n = len(res)
    lv = {k: sum(str(r[k]) == "True" for r in res) for k in ("l1", "l2", "l3", "l4")}
    share = {k: round(100 * v / n, 4) if n else 0.0 for k, v in lv.items()}
    outcomes = {o: sum(r["outcome"] == o for r in done) for o in OUTCOMES}
    pop = sum(per_year.values())
    p = two_prop_p(lv["l1"], n, *DING)
    shown = " and ".join(f"{y}-ISC.txt ({per_year[y]:,})" for y in YEARS)
    matches = "reproduces your any-capture rate within error"
    if p < 0.05:
        matches = "differs from your any-capture rate"
    promote = f"none of {n:,} records has" if not lv["l4"] else f"only {lv['l4']} of {n:,} have"
    result = {
        "id": TEST_ID,
        "question": "Q2",
        "title": "ISC survey names to year evidence",
        "label": "Tested, not independently verified",
        "command": meta["command"],
        "sources": [
            "https://web.archive.org/cdx/search/cdx",
            "https://web.archive.org/web/19961112172542id_/http://nw.com/zone/9607.hosts/uk.gz",
        ],
        "population": f"Your {shown}: {pop:,} hostname-year records, year from the file.",
        "sample": f"{len(done):,} of {SIZE:,} records done, seeded",
        "query": f"{CDX}?url=<host>/*&from=1996&to=2013&fl=timestamp,original,statuscode"
        f"&limit={LIMIT}&output=json; at {LIMIT} rows, anchored original and status filters"
        " for the survey year settle open levels.",
        "outcomes": outcomes,
        "levels": {
            k.upper(): {"count": v, "share_pct": share[k], "wilson95_pct": wilson(v, n)}
            for k, v in lv.items()
        },
        "n_resolved": n,
        "ding_l1": {"count": DING[0], "n": DING[1], "share_pct": 2.6667, "two_sided_p": p},
        "result": f"{lv['l4']} of {n:,} with a 2xx/3xx capture in their year; any capture"
        f" {share['l1']:.2f}% (yours 2.67%)",
        "finding": f"Repeating your ISC experiment {matches} (p = {p:.2f}), yet {promote} a 2xx"
        " or 3xx capture of its host in its survey year: discovery-only evidence rarely becomes"
        " direct.",
        "limits": f"{len(done):,} of {SIZE:,} records finished by the stop time, CDX averaging"
        f" {mean_s:.1f} s an answer with {transient} transient errors; a finished prefix is"
        " uniform. No CDX row does not prove no website, and L4 checks status, not content.",
        "per_year": {str(y): per_year[y] for y in YEARS},
        "started_at": meta["started_at"],
        "finished_at": meta.get("finished_at", ""),
        "requests": requests,
        "transient_errors": transient,
        "unresolved": unres,
    }
    tmp = OUT / "result.json.tmp"
    tmp.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, OUT / "result.json")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--stop-at", help="UTC time after which no record starts")
    args = ap.parse_args()
    stop, command = math.inf, f"uv run python scripts/orq/{TEST_ID}.py"
    if args.stop_at:
        stop = datetime.strptime(args.stop_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        stop, command = stop.timestamp(), f"{command} --stop-at {args.stop_at}"
    OUT.mkdir(parents=True, exist_ok=True)
    sample_csv, meta_path = OUT / "sample.csv", OUT / "result.json"
    per_year: dict[int, int] = {}
    if sample_csv.exists():
        with open(sample_csv, newline="", encoding="utf-8") as fh:
            recs = list(csv.DictReader(fh))
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        per_year = {int(k): v for k, v in meta.get("per_year", {}).items()}
    if not sample_csv.exists() or not per_year:
        sample, per_year = population()
        recs = [
            {"order": i + 1, "hostname": h, "year": y, "outcome": "pending"}
            for i, (h, y) in enumerate(sample)
        ]
        write_csv(sample_csv, recs)
        meta = {}
    meta.setdefault("started_at", now())
    meta["command"] = command
    log_path = OUT / "log.txt"
    cli = Client(log_path)

    def save() -> None:
        write_csv(sample_csv, recs)
        write_result(recs, per_year, meta, log_path)

    todo = [r for r in recs if r["outcome"] == "pending"]
    todo += [r for r in recs if r["outcome"] == "unresolved"]
    streak = 0
    for r in todo:
        if time.time() >= stop:
            print(f"stop time {args.stop_at} reached")
            break
        before = cli.count
        try:
            r.update(classify(cli, r["hostname"], int(r["year"])))
            streak = 0
        except Unresolved:
            r["outcome"] = "unresolved"
            streak += 1
        r["requests"] = cli.count - before
        meta["finished_at"] = now()
        save()
        if streak >= 3:
            print("three records unresolved in a row: stopping, rerun to resume")
            break
    save()
    done = sum(r["outcome"] not in ("", "pending") for r in recs)
    print(f"{done} of {len(recs)} records done; see {OUT.relative_to(ROOT)}/result.json")


if __name__ == "__main__":
    main()
