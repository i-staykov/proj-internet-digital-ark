"""Crawl the archived web through Wayback replay and write dated link rows.

A page the Archive captured in year Y that links to host H is a dated link row (H, Y): the
capture date of the listing page dates the link. Fixed page lists are bounded by what a
dispatch can carry, so this reader finds its own pages: it starts from seed hosts or URLs,
follows the same-site links that look like link collections, and asks the root of every newly
seen outbound host (snowball). Standard library only, one file, so it runs on any machine.

    python3 wayback_crawl.py SEEDS [SEEDS ...] --year 1997 --out DIR [--threads 2]
        [--interval 1.0] [--minutes 30] [--shard 0/1] [--site-pages 6] [--years 1996-1998]

SEEDS: files of hostnames or URLs, one a line (first field), plain or .gz, or `env:NAME` for
an environment variable holding the list plain or gzip then base64.

Each ask is `https://web.archive.org/web/<year>0701000000id_/<url>`, the unmodified capture
nearest mid-year; the CDX is never asked. The Archive answers a www host with its bare twin
and the reverse, so the real captured URL and stamp are read from the final response (its
`Link rel="original"` and `Memento-Datetime`, else the final path), never assumed. A page is
kept only as a 200 html capture whose real year is in `--years` (default the asked year). A
page that is not a root and whose nearest capture is off-year is left at the redirect, unread.

Outputs under --out, no page bodies:
  rows.jsonl      {"kind": "link", host, year, source, stamp, outbound}: one per (linked host,
                  year), its first linking page and that page's count of outbound hosts; and
                  {"kind": "capture", host, year, stamp, source}: a root read that ended as a
                  200 capture of that exact host in any year, a realness check for free.
  receipts.jsonl  one per ask: url, asked stamp, real stamp, real host, status, bytes, outbound.
  frontier_other.txt  outbound hosts of other shards, the next wave's seeds.
  frontier.txt    this shard's pushes, so a restart resumes: journals are append-only and a
                  URL with a receipt is not asked again.
  stats.json      asked, kept, pages a second, rests, why it stopped.
  <journal>.gz    the four journals packed at the end. A folder holding only the packed ones
                  (an earlier job's artifact) is unpacked first, so a later job goes on from it.

Shards: a host belongs to shard crc32(host without a leading www.) mod n, so parallel jobs
never ask the same host and twins share a job.

Politeness: one kept-alive connection a thread, at least --interval seconds between a
thread's asks, a 429, a 503 or a failed connection rests the whole job (60 s, doubling while
they repeat, 900 s at most) and ten rests in a row end it. The Archive's robots.txt is read
once and a refusal ends the job. Inside the repo the project fetcher supplies the User-Agent
and the robots reader; alone, a User-Agent naming a research crawler.
"""

import argparse
import base64
import email.utils
import gzip
import heapq
import http.client
import importlib.util
import json
import os
import re
import shutil
import signal
import threading
import time
import urllib.parse
import urllib.robotparser
import zlib
from pathlib import Path

ARCHIVE = "web.archive.org"
AGENT = "ArkLinkCrawler/1.0 (research crawler of archived pages for historical hostname research)"
CAP = 1_500_000  # bytes of a page read; a longer one is cut there
WORDS = re.compile(
    r"link|hotlist|bookmark|resource|sites|favorite|favourite|cool|other|related|friends"
    r"|index of|directory|list|top|members|ring",
    re.IGNORECASE,
)
ATAG = re.compile(r"<a\b[^>]*?\bhref\s*=\s*[\"']?([^\"'\s>]+)[^>]*>", re.IGNORECASE)
AEND = re.compile(r"</a|<a\b", re.IGNORECASE)
FRAME = re.compile(
    r"<(?:frame|iframe|area)\b[^>]*?\b(?:src|href)\s*=\s*[\"']?([^\"'\s>]+)", re.IGNORECASE
)
BASE = re.compile(r"<base\b[^>]*?\bhref\s*=\s*[\"']?([^\"'\s>]+)", re.IGNORECASE)
TAG = re.compile(r"<[^>]*>")
HOST = re.compile(
    r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*\.[a-z]{2,}$"
)
REPLAY = re.compile(r"/web/(\d{14})[a-z_]*/(.+)$", re.DOTALL)
ORIGINAL = re.compile(r'<([^>]+)>;\s*rel="original"')
NOT_PAGE = re.compile(
    r"\.(gif|jpe?g|png|bmp|ico|zip|exe|pdf|ps|gz|tar|z|hqx|sit|mov|avi|mpe?g|mp3|wav|au|ra|ram"
    r"|class|css|js|doc|xls|ppt)$",
    re.IGNORECASE,
)
SEED, WORDY, ROOT, PLAIN = 1, 0, 2, 3  # frontier priorities, lowest first
JOURNALS = ("rows.jsonl", "receipts.jsonl", "frontier_other.txt", "frontier.txt")


def host_of(url: str) -> str:
    """The lowercased host of a URL without port, user or trailing dot; "" when not a name."""
    try:
        netloc = urllib.parse.urlsplit(url).netloc
    except ValueError:
        return ""
    host = netloc.rsplit("@", 1)[-1].split(":", 1)[0].lower().rstrip(".")
    return host if len(host) <= 253 and HOST.match(host) else ""


def site(host: str) -> str:
    """A host without its leading www.: the Archive serves the twins as one site."""
    return host[4:] if host.startswith("www.") else host


def shard_of(host: str, n: int) -> int:
    """A stable shard for a host; crc32 rather than hash(), which differs a process."""
    return zlib.crc32(site(host).encode()) % n


def norm(url: str) -> str:
    """One spelling a URL: http, lowercased host, no :80, no fragment; "" when not http."""
    try:
        parts = urllib.parse.urlsplit(url.strip())
        port = parts.port
    except ValueError:
        return ""
    host = host_of(url)
    if parts.scheme.lower() not in ("http", "https") or not host:
        return ""
    if port and port not in (80, 443):
        host += f":{port}"
    return f"http://{host}{parts.path or '/'}" + (f"?{parts.query}" if parts.query else "")


def is_root(url: str) -> bool:
    parts = urllib.parse.urlsplit(url)
    return parts.path in ("", "/") and not parts.query


def links(body: str, page_url: str) -> tuple[list[str], list[tuple[str, bool]]]:
    """A page's outbound hosts and its same-site links, each once, in page order.

    Outbound: an absolute http link whose host is neither the page's host nor its www twin.
    Same-site: (URL, whether its path or anchor text carries a link-collection word); a frame
    counts as wordy, since a frameset root holds nothing itself.
    """
    here = host_of(page_url)
    base = BASE.search(body)
    base_url = urllib.parse.urljoin(page_url, base.group(1)) if base else page_url
    found = [(m.group(1), body[m.end() : m.end() + 160], False) for m in ATAG.finditer(body)]
    found += [(m.group(1), "", True) for m in FRAME.finditer(body)]
    out: dict[str, None] = {}
    same: dict[str, bool] = {}
    for href, tail, frame in found:
        if href[:1] == "#":
            continue
        try:
            url = norm(urllib.parse.urljoin(base_url, href))
        except ValueError:
            continue
        host = host_of(url)
        if not host:
            continue
        if site(host) != site(here):
            if href[:4].lower() == "http":
                out.setdefault(host)
            continue
        parts = urllib.parse.urlsplit(url)
        if url == norm(page_url) or NOT_PAGE.search(parts.path):
            continue
        end = AEND.search(tail)
        text = TAG.sub(" ", tail[: end.start()] if end else tail)
        wordy = frame or bool(WORDS.search(parts.path + "?" + parts.query) or WORDS.search(text))
        same[url] = same.get(url, False) or wordy
    return list(out), list(same.items())


def real_capture(path: str, headers: dict) -> tuple[str, str]:
    """The real (stamp, URL) of a replay answer: the headers first, the final path second."""
    m = REPLAY.search(path)
    stamp, url = (m.group(1), m.group(2)) if m else ("", "")
    original = ORIGINAL.search(headers.get("link", ""))
    if original:
        url = original.group(1)
    try:
        when = email.utils.parsedate_to_datetime(headers.get("memento-datetime", ""))
        stamp = when.strftime("%Y%m%d%H%M%S")
    except (TypeError, ValueError):
        pass
    return stamp, url


def seed_lines(source: str) -> list[str]:
    """The lines of a seed source: a file, a .gz file, or env:NAME (plain or gzip+base64)."""
    if source.startswith("env:"):
        packed = os.environ.get(source[4:], "")
        try:
            return (
                gzip.decompress(base64.b64decode(packed, validate=True))
                .decode("latin-1")
                .split("\n")
            )
        except (ValueError, OSError, EOFError):
            return packed.split("\n")
    raw = Path(source).read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("latin-1").split("\n")


def repo_fetcher():
    """The project fetcher when this file sits in the repo, else None."""
    path = Path(__file__).resolve().parents[3] / "scripts/harness/fetch.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("hf", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Crawl:
    def __init__(self, args: argparse.Namespace) -> None:
        self.out = Path(args.out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.stamp = f"{args.year}0701000000"
        self.years = years_of(args.years or str(args.year))
        self.shard, self.of = (int(x) for x in args.shard.split("/"))
        self.interval, self.site_pages = args.interval, args.site_pages
        self.threads = args.threads
        self.started = time.time()
        self.deadline = self.started + args.minutes * 60
        self.hf = repo_fetcher()
        self.agent = self.hf.USER_AGENT if self.hf else AGENT
        self.robots = None
        self.robots_cache: dict = {}
        self.local = threading.local()
        self.cond = threading.Condition(threading.RLock())
        self.heap: list[tuple[int, int, str]] = []
        self.seq = 0
        self.busy = 0
        self.queued: set[str] = set()  # every URL pushed or asked
        self.asked: set[str] = set()
        self.site_asked: dict[str, int] = {}
        self.site_pushed: dict[str, int] = {}
        self.fails: dict[str, int] = {}
        self.hosts: set[str] = set()  # outbound hosts seen
        self.rows: set[tuple[str, str]] = set()
        self.stop = ""
        self.rest_until = 0.0
        self.n = {"asked": 0, "kept": 0, "rows": 0, "captures": 0, "rests": 0, "rests_row": 0}
        self.n["other"] = 0
        for name in JOURNALS:  # an earlier job's packed journals: go on from them
            plain, packed = self.out / name, self.out / f"{name}.gz"
            if packed.is_file() and not plain.is_file():
                plain.write_bytes(gzip.decompress(packed.read_bytes()))
        self.resume()
        self.resumed = self.n["asked"]
        self.j_rows = open(self.out / "rows.jsonl", "a")
        self.j_receipts = open(self.out / "receipts.jsonl", "a")
        self.j_other = open(self.out / "frontier_other.txt", "a")
        self.j_frontier = open(self.out / "frontier.txt", "a")
        for source in args.seeds:
            for line in seed_lines(source):
                first = line.split()[0] if line.split() else ""
                url = norm(first if "://" in first else f"http://{first}/")
                if url and shard_of(host_of(url), self.of) == self.shard:
                    self.push(SEED, url)

    def resume(self) -> None:
        """Reload the journals: asked URLs, written rows, seen hosts, then the frontier."""
        for line in self.read("receipts.jsonl"):
            r = json.loads(line)
            self.asked.add(r["url"])
            self.queued.add(r["url"])
            self.site_asked[site(host_of(r["url"]))] = (
                self.site_asked.get(site(host_of(r["url"])), 0) + 1
            )
            self.n["asked"] += 1
            self.n["kept"] += bool(r.get("kept"))
        for line in self.read("rows.jsonl"):
            r = json.loads(line)
            self.n["rows" if r["kind"] == "link" else "captures"] += 1
            if r["kind"] == "link":
                self.rows.add((r["host"], r["year"]))
                self.hosts.add(r["host"])
        for line in self.read("frontier_other.txt"):
            self.hosts.add(line)
            self.n["other"] += 1
        for line in self.read("frontier.txt"):
            priority, _, url = line.partition("\t")
            mine = shard_of(host_of(url), self.of) == self.shard  # journals of another split
            if url and url not in self.queued and mine:
                self.queued.add(url)
                self.seq += 1
                heapq.heappush(self.heap, (int(priority), self.seq, url))

    def read(self, name: str) -> list[str]:
        path = self.out / name
        return path.read_text().splitlines() if path.is_file() else []

    def push(self, priority: int, url: str) -> None:
        """Queue a URL once. A site's unasked links are bounded so one site cannot fill it."""
        if url in self.queued:
            return
        where = site(host_of(url))
        if priority in (WORDY, PLAIN):
            if self.site_pushed.get(where, 0) >= 4 * self.site_pages:
                return
            self.site_pushed[where] = self.site_pushed.get(where, 0) + 1
        self.queued.add(url)
        self.seq += 1
        heapq.heappush(self.heap, (priority, self.seq, url))
        self.j_frontier.write(f"{priority}\t{url}\n")

    def pop(self) -> tuple[int, str] | None:
        """The next URL whose site is under --site-pages; a seed is asked whatever the count."""
        while self.heap:
            priority, _, url = heapq.heappop(self.heap)
            where = site(host_of(url))
            if url in self.asked:
                continue
            if priority != SEED and self.site_asked.get(where, 0) >= self.site_pages:
                continue
            self.site_asked[where] = self.site_asked.get(where, 0) + 1
            return priority, url
        return None

    def get(self, path: str) -> tuple[int, dict, bytes]:
        """One GET on this thread's kept-alive connection; the caller handles a failure."""
        conn = getattr(self.local, "conn", None)
        if conn is None:
            conn = self.local.conn = http.client.HTTPSConnection(ARCHIVE, timeout=60)
        try:
            conn.request(
                "GET", path, headers={"User-Agent": self.agent, "Accept-Encoding": "identity"}
            )
            resp = conn.getresponse()
            body = resp.read(CAP + 1)
            if len(body) > CAP:  # the rest is not read, so the connection cannot be kept
                conn.close()
                self.local.conn = None
            return resp.status, {k.lower(): v for k, v in resp.getheaders()}, body[:CAP]
        except Exception:
            conn.close()
            self.local.conn = None
            raise

    def robots_verdict(self, path: str) -> str:
        """allowed, refused or unknown for a path under the Archive's robots.txt: the project
        reader in the repo, else the standard parser on a robots.txt read once. unknown is a
        robots.txt that could not be read: it is read again after a rest."""
        with self.cond:
            if self.hf:
                url = f"https://{ARCHIVE}{path}"
                verdict, _, _ = self.hf.read_robots(url, 60, self.robots_cache)
                if verdict == "unknown":
                    self.robots_cache.clear()
                return verdict
            if self.robots is None:
                status, _, body = self.get("/robots.txt")
                if status != 200 and not (400 <= status < 500 and status != 429):
                    return "unknown"
                self.robots = urllib.robotparser.RobotFileParser()  # a 4xx: no rules, all open
                self.robots.parse(body.decode("latin-1").splitlines() if status == 200 else [])
        return "allowed" if self.robots.can_fetch(self.agent, path) else "refused"

    def rest(self, why: str, retry_after: float = 0.0) -> None:
        """Rest every thread; threads that fail during one rest count as that rest."""
        with self.cond:
            now = time.time()
            if now < self.rest_until:
                return
            self.n["rests"] += 1
            self.n["rests_row"] += 1
            if self.n["rests_row"] >= 10:
                self.stop = "ten rests in a row"
            seconds = max(retry_after, min(60 * 2 ** (self.n["rests_row"] - 1), 900))
            self.rest_until = now + seconds
            print(
                json.dumps({"rest": why, "seconds": seconds, "row": self.n["rests_row"]}),
                flush=True,
            )

    def again(self, priority: int, url: str) -> None:
        """Requeue a URL whose ask got no answer; the third failure is its receipt."""
        with self.cond:
            self.fails[url] = self.fails.get(url, 0) + 1
            if self.fails[url] >= 3:
                self.receipt({"url": url, "asked": self.stamp, "status": 0})
                return
            where = site(host_of(url))
            self.site_asked[where] = max(0, self.site_asked.get(where, 0) - 1)
            self.seq += 1
            heapq.heappush(self.heap, (priority, self.seq, url))

    def receipt(self, row: dict) -> None:
        with self.cond:
            self.asked.add(row["url"])
            self.n["asked"] += 1
            self.n["kept"] += bool(row.get("kept"))
            self.j_receipts.write(json.dumps(row) + "\n")
            self.j_receipts.flush()

    def ask(self, priority: int, url: str) -> None:
        path = f"/web/{self.stamp}id_/" + re.sub(
            r"[^\x21-\x7e]",
            lambda m: urllib.parse.quote(m.group(0).encode("latin-1", "replace")),
            url,
        )
        root, first = is_root(url), path
        try:
            verdict = self.robots_verdict(path)
            if verdict == "refused":
                self.stop = self.stop or "robots refuses"
                return
            if verdict != "allowed":
                raise OSError("robots.txt could not be read")
            status, headers, body = self.fetch(path)
            hops = 0
            while status in (301, 302, 303, 307, 308) and hops < 5:
                target = urllib.parse.urlsplit(
                    urllib.parse.urljoin(f"https://{ARCHIVE}{path}", headers.get("location", ""))
                )
                if target.netloc != ARCHIVE:
                    break
                path = target.path + (f"?{target.query}" if target.query else "")
                near = REPLAY.search(path)
                if near and not root and near.group(1)[:4] not in self.years:
                    break  # an off-year page pays nothing: left unread
                status, headers, body = self.fetch(path)
                hops += 1
        except (http.client.HTTPException, OSError):
            self.rest("no answer")
            self.again(priority, url)
            return
        if status in (429, 503):
            retry = headers.get("retry-after", "")
            self.rest(str(status), float(retry) if retry.isdigit() else 0.0)
            self.again(priority, url)
            return
        with self.cond:
            self.n["rests_row"] = 0
        stamp, real_url = "", ""
        if path != first or "memento-datetime" in headers:  # else the path is only the ask
            stamp, real_url = real_capture(path, headers)
            real_url = norm(real_url) or real_url
        host = host_of(real_url)
        if headers.get("content-encoding", "").lower() == "gzip":
            try:
                body = gzip.decompress(body)
            except (OSError, EOFError):
                body = b""
        kind = headers.get("content-type", "").lower()
        html = "html" in kind or (not kind and b"<a " in body[:20000].lower())
        kept = status == 200 and html and bool(host) and stamp[:4] in self.years
        out, same = links(body.decode("latin-1"), real_url) if kept else ([], [])
        with self.cond:
            if status == 200 and root and host:
                self.n["captures"] += 1
                row = {"kind": "capture", "host": host, "year": stamp[:4], "stamp": stamp}
                row |= {"source": real_url, "asked": host_of(url)}
                self.j_rows.write(json.dumps(row) + "\n")
            for linked in out:
                if (linked, stamp[:4]) not in self.rows:
                    self.rows.add((linked, stamp[:4]))
                    self.n["rows"] += 1
                    row = {"kind": "link", "host": linked, "year": stamp[:4], "source": real_url}
                    self.j_rows.write(
                        json.dumps(row | {"stamp": stamp, "outbound": len(out)}) + "\n"
                    )
                if linked not in self.hosts:
                    self.hosts.add(linked)
                    if shard_of(linked, self.of) == self.shard:
                        self.push(ROOT, f"http://{linked}/")
                    else:
                        self.n["other"] += 1
                        self.j_other.write(linked + "\n")
            for link, wordy in same:  # a redirect can land on another shard's host
                if shard_of(host_of(link), self.of) == self.shard:
                    self.push(WORDY if wordy else PLAIN, link)
        self.receipt(
            {
                "url": url,
                "asked": self.stamp,
                "stamp": stamp,
                "host": host,
                "status": status,
                "bytes": len(body),
                "outbound": len(out),
                "kept": kept,
            }
        )

    def fetch(self, path: str) -> tuple[int, dict, bytes]:
        """A GET asked once more on a fresh connection: an idle kept-alive one is often gone."""
        try:
            return self.get(path)
        except (http.client.HTTPException, OSError):
            return self.get(path)

    def worker(self) -> None:
        next_start = 0.0
        while True:
            with self.cond:
                while True:
                    if self.stop or time.time() >= self.deadline:
                        return
                    item = self.pop()
                    if item:
                        self.busy += 1
                        break
                    if not self.busy:
                        self.stop = "frontier empty"
                        self.cond.notify_all()
                        return
                    self.cond.wait(1.0)
            try:
                while time.time() < max(self.rest_until, next_start) and not self.stop:
                    if time.time() >= self.deadline:
                        break
                    time.sleep(min(1.0, max(0.01, max(self.rest_until, next_start) - time.time())))
                next_start = time.time() + self.interval
                if not self.stop and time.time() < self.deadline:
                    self.ask(*item)
                else:
                    self.again(*item)
            except Exception as error:  # one page's surprise must not end a thread
                self.receipt({"url": item[1], "asked": self.stamp, "status": 0})
                print(json.dumps({"error": repr(error)[:300], "url": item[1]}), flush=True)
            finally:
                with self.cond:
                    self.busy -= 1
                    self.cond.notify_all()

    def stats(self) -> None:
        with self.cond:
            for journal in (self.j_rows, self.j_receipts, self.j_other, self.j_frontier):
                journal.flush()
            seconds = time.time() - self.started
            stats = dict(self.n) | {
                "seconds": round(seconds),
                "asked_before_restart": self.resumed,
                "pages_a_second": round((self.n["asked"] - self.resumed) / max(seconds, 1), 2),
                "frontier": len(self.heap),
                "shard": f"{self.shard}/{self.of}",
                "stopped": self.stop or ("time" if time.time() >= self.deadline else ""),
            }
            (self.out / "stats.json").write_text(json.dumps(stats) + "\n")

    def run(self) -> None:
        workers = [threading.Thread(target=self.worker, daemon=True) for _ in range(self.threads)]
        for w in workers:
            w.start()
        tick = time.time() + 30
        while any(w.is_alive() for w in workers):
            for w in workers:
                w.join(1.0 / len(workers))
            if time.time() >= tick:
                tick = time.time() + 30
                self.stats()
        self.stats()
        for journal in (self.j_rows, self.j_receipts, self.j_other, self.j_frontier):
            journal.close()
        for name in JOURNALS:
            with (
                open(self.out / name, "rb") as src,
                gzip.open(self.out / f"{name}.gz", "wb") as dst,
            ):
                shutil.copyfileobj(src, dst)
        print((self.out / "stats.json").read_text(), end="", flush=True)


def years_of(text: str) -> set[str]:
    """The set of year strings of "1997", "1996-1998" or "1996,1998"."""
    years: set[str] = set()
    for part in text.split(","):
        first, _, last = part.partition("-")
        years |= {str(y) for y in range(int(first), int(last or first) + 1)}
    return years


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("seeds", nargs="+")
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--years", default="")
    p.add_argument("--threads", type=int, default=2)
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--minutes", type=float, default=30.0)
    p.add_argument("--shard", default="0/1")
    p.add_argument("--site-pages", type=int, default=6)
    p.add_argument("--out", required=True)
    crawl = Crawl(p.parse_args())
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: setattr(crawl, "stop", crawl.stop or "signal"))
    crawl.run()


if __name__ == "__main__":
    main()
