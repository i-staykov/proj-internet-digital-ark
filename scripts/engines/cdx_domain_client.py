"""Ask the CDX index for every capture under each registrable of a list, one client, one share.

`matchType=domain` over a registrable, 2xx and 3xx, root URLs only (the walker's anchored filter:
`netcom.ca`'s 1996 to 2013 roots came in one 35 s request, 1,414 rows, where 15,000 unfiltered rows
named 6 host-years), no collapse (laws), paged by resume key and reduced here to the earliest row of
each (host, year). The rows go out as the walker's journals,
`walk_dom-<registrable>_<stamp>.jsonl.gz`, 1996 to 2001 under `<data>/raw/cdx_suffix/` (the hostname
ingest banks them) and 2002 to 2013 under `<data>/raw/extended/ia_cdx_hostnames/`, so a capture the
bank lacks ships as an addition. A registrable over `--farm` host-years writes under
`<data>/raw/cdx_domain/farm/` instead: one under the VM's address answered 302,142 for 1996 to 2001,
a wildcard farm, so a hand read decides before any of it banks.

One request at a time, `--interval` apart. A 429 or 503 rests `Retry-After` or a minute; a refused
connection or a connect timeout 30 s doubling to 15 min, and a 15 minute rest ends the run, since
the address is refused. A domain's 502, 504, cut stream or read timeout is its scan outlasting the
gateway, not the address (homestead.com, kataweb.it and uku.fi cut at 75 to 135 s on three runner
addresses while the next one answered): asked again twice, then booked as `heavy.txt` for a paged
walk, as is a domain that drew six 503s. Every request is a `log.tsv` row (stamp, registrable,
status, seconds, rows, host-years 1996 to 2001, 2002 to 2013), so a rate carries its waits.
`done.txt` keeps the answered registrables, so a restart resumes; one the deadline cuts banks
nothing and is asked again. `--urlkey` asks a pattern in place of the roots, a finder for a page
reader: its rows go out whole as `hits/<registrable>.txt.gz` beside the log and none banks.

    python3 scripts/engines/cdx_domain_client.py LIST --share 0/8 --data DIR [--seconds 3300]
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://web.archive.org/cdx/search/cdx"
UA = "InternetDigitalArk/1.0 (+historical domain research)"
FIRST, SPLIT, LAST = 1996, 2002, 2013
ROOT = r"^[^/]*\)/$"
ROWS, CAP = 20000, 40  # rows a request, requests a registrable
HEAVY = {"HTTP502", "HTTP504", "IncompleteRead", "TimeoutError", "RemoteDisconnected"}


def host_of(original: str) -> str:
    rest = original.split("://", 1)[-1]
    host = urllib.parse.urlsplit("http://" + rest).hostname or ""
    return host.lower().rstrip(".")


def ask(reg: str, key: str | None, rows: int, a: argparse.Namespace) -> str:
    q = [("url", reg), ("matchType", "domain"), ("from", str(FIRST)), ("to", str(a.last))]
    q += [("filter", "statuscode:[23][0-9][0-9]")]
    # the index matches a filter from the key's start, so a finder's pattern is wrapped
    q += [] if a.any_url else [("filter", "urlkey:" + (f".*({a.urlkey})" if a.urlkey else ROOT))]
    q += [("fl", "timestamp,original,statuscode")]
    q += [("limit", str(rows)), ("showResumeKey", "true")] + ([("resumeKey", key)] if key else [])
    req = urllib.request.Request(BASE + "?" + urllib.parse.urlencode(q), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=a.timeout) as fh:
        return fh.read().decode("utf-8", "replace")


def split(body: str) -> tuple[list[str], str | None]:
    """The rows and the resume key: a page with more ends in a blank line and the key."""
    lines = body.rstrip("\n").split("\n") if body.strip() else []
    if len(lines) >= 2 and not lines[-2].strip():
        return lines[:-2], lines[-1].strip()
    return lines, None


def write(folder: Path, name: str, rows: list) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / f".{name}.tmp"
    with gzip.GzipFile(tmp, "wb", mtime=0) as raw, io.TextIOWrapper(raw) as fh:
        for ts, url, st in sorted(rows):
            fh.write(json.dumps({"url": url, "timestamp": ts, "status": st}) + "\n")
    os.replace(tmp, folder / f"{name}.jsonl.gz")


class Client:
    def __init__(self, a: argparse.Namespace):
        self.a, self.state = a, a.data / "raw/cdx_domain" / a.name
        self.state.mkdir(parents=True, exist_ok=True)
        done = self.state / "done.txt"
        self.done = set(done.read_text().split()) if done.exists() else set()
        self.log = open(self.state / "log.tsv", "a", buffering=1)
        self.last, self.refused, self.end = 0.0, 0, float("inf")

    def rest(self, seconds: float, why: str) -> None:
        self.log.write(f"# pause {round(seconds)} s: {why}\n")
        time.sleep(seconds)

    def domain(self, reg: str) -> bool:
        """Ask one registrable to its end or `CAP`; False once the address is refused."""
        keep: dict = {}
        hits: list = []
        key, tries, throttled, requests, status = None, 0, 0, 0, "200"
        while requests < CAP and time.time() < self.end:  # a deadline ends a big domain too
            time.sleep(max(0.0, self.last + self.a.interval - time.time()))
            self.last, t0 = time.time(), time.time()
            requests += 1
            n = 0
            try:
                body = ask(reg, key, ROWS, self.a)
                status = "200"
            except urllib.error.HTTPError as exc:
                status = f"HTTP{exc.code}"
                after = exc.headers.get("Retry-After") if exc.headers else None
            except urllib.error.URLError as exc:  # no connection: the address
                status = f"URLError:{type(exc.reason).__name__}"
            except Exception as exc:  # noqa: BLE001  a cut stream or a read timeout: the domain
                status = type(exc).__name__
            if status == "200":
                self.refused = 0
                lines, key = split(body)
                for ln in lines:
                    f = ln.split(" ")
                    host = host_of(f[1]) if len(f) >= 3 else ""
                    if host == reg or host.endswith("." + reg):
                        n += 1
                        if self.a.urlkey:
                            hits.append(" ".join(f[:3]))
                        y = f[0][:4]
                        if (host, y) not in keep or f[0] < keep[(host, y)][0]:
                            keep[(host, y)] = tuple(f[:3])
            p1 = sum(FIRST <= int(y) < SPLIT for _, y in keep if y.isdigit())
            row = [time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(t0)), reg, status]
            row += [round(time.time() - t0, 1), n, p1, len(keep) - p1]
            self.log.write("\t".join(map(str, row)) + "\n")
            if status == "200":
                if not key:
                    break
                continue
            requests -= 1  # an unanswered request asks nothing of the index
            if status in ("HTTP429", "HTTP503"):
                try:
                    wait = float(after or 60)
                except ValueError:
                    wait = 60.0
                self.rest(min(wait, 900.0), status)
                throttled += 1
            if status in HEAVY or throttled >= 6:
                tries += status in HEAVY
                if tries >= 3 or throttled >= 6:
                    with open(self.state / "heavy.txt", "a") as fh:
                        fh.write(f"{reg}\n")
                    break
            elif status.startswith("HTTP"):
                if status not in ("HTTP429", "HTTP503"):
                    break  # the domain's own answer (400, 403, 404): booked
            else:
                self.refused += 1
                wait = min(900.0, 30.0 * 2 ** min(self.refused - 1, 5))
                if wait >= 900:
                    return False
                self.rest(wait, status)
        if time.time() >= self.end and (key or status != "200"):  # cut by the deadline: none banks
            self.log.write(f"# cut {reg} {requests} requests\n")
            return True
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        name = f"walk_dom-{reg}_{stamp}"
        core = [v for (_, y), v in keep.items() if y.isdigit() and int(y) < SPLIT]
        ext = [v for (_, y), v in keep.items() if y.isdigit() and SPLIT <= int(y) <= LAST]
        raw = self.a.data / "raw"
        if self.a.urlkey:  # a finder's rows: out whole for the reader, none banks
            core = ext = []
            (self.state / "hits").mkdir(exist_ok=True)
            with gzip.open(self.state / "hits" / f"{reg}.txt.gz", "wt") as fh:
                fh.writelines(h + "\n" for h in hits)
        elif len(keep) > self.a.farm:  # a wildcard farm, not that many sites: a hand read first
            raw = self.a.data / "raw/cdx_domain/farm"
            self.log.write(f"# farm {reg} {len(keep)} host-years held\n")
        if core:
            write(raw / "cdx_suffix", name, core)
        if ext:
            write(raw / "extended/ia_cdx_hostnames", name, ext)
        with open(self.state / "done.txt", "a") as fh:
            fh.write(f"{reg}\n")
        self.log.write(f"# done {reg} {status} {requests} requests {len(core)} {len(ext)}\n")
        return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("list", type=Path, help="one registrable a line, in the order to ask")
    ap.add_argument("--share", default="0/1", help="i/n: this client asks every n-th line from i")
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--name", default="", help="state folder; the list's stem and share if empty")
    ap.add_argument("--interval", type=float, default=3.0, help="seconds between starts")
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--last", type=int, default=LAST, help="the last year asked")
    ap.add_argument("--farm", type=int, default=1000, help="host-years a registrable banks")
    ap.add_argument("--any-url", action="store_true", help="every URL, not the roots alone")
    ap.add_argument("--urlkey", default="", help="a pattern found anywhere in the urlkey: hits out")
    ap.add_argument("--seconds", type=float, default=0, help="stop after this many; 0 runs out")
    a = ap.parse_args()
    i, n = map(int, a.share.split("/"))
    a.name = a.name or f"{'find_' if a.urlkey else ''}{a.list.stem}_{i}of{n}"
    regs = [ln.split("#")[0].strip().lower() for ln in a.list.read_text().splitlines()]
    regs = [r for k, r in enumerate(x for x in regs if x) if k % n == i]
    client = Client(a)
    client.end = time.time() + a.seconds if a.seconds else float("inf")
    for reg in regs:
        if time.time() >= client.end:
            break
        if reg not in client.done and not client.domain(reg):
            client.log.write("# exit: the address is refused\n")
            break


if __name__ == "__main__":
    main()
