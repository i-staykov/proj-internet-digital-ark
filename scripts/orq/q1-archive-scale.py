"""q1-archive-scale: how much pre-1996 material do archive.org collections hold outside Wayback?

    uv run python scripts/orq/q1-archive-scale.py

Part 1 counts items with archive.org's advancedsearch (rows=0, numFound) for each collection
in COLLECTIONS: all items, items with any date, items dated 1990-01-01 to 1995-12-31, and of
those the items whose title, subject or description names an Internet term (TERMS). The
search can answer a false count under load, so each count is asked until two consecutive
answers agree (at most 6 asks), else it is "unresolved".

Part 2 reads one disc: World of Internet (USD035), item wointernet, uploaded as internet.zip.
The served member listing is fetched and parsed. The zip is read in place by HTTP Range, 1 MB
blocks, 3 at a time: its central directory, then every member with a text-like extension
outside the ONLINE and BBS client-software folders; zipfile checks each member's CRC-32, and
a member that also sniffs as text (no NUL, 95% printable in its first 4 KB) is read. Two host
kinds: "url", the host of a scheme://host reference (http, https, ftp, gopher, telnet, wais);
"named", a bare dotted name not touching "@" (so no mail address) and not a Usenet group,
ending in a 1994 gTLD with 2 or more labels or a ccTLD with 3 or more. Both need a registrable
name under the vendored public suffix list; .arpa (pre-DNS names, reverse zones) and .ps
(delegated in 2000; PostScript file names here) are left out. A host's date is the earliest
member mtime naming it ("existed by"); the disc's bound is its latest member mtime. Hosts are
diffed against his 1996 to 2001 files with LC_ALL=C comm, as hostnames and registrable names.

A throttle, timeout, refused connect or 5xx is retried (Retry-After, else
60 s doubling, 6 tries) and never read as zero. Resumable: finished counts are kept in
counts.csv and the disc's hosts in cache/hosts.csv (kept out of git; sample.csv ships).
Writes only under docs/orq/results/q1-archive-scale/.
"""

import concurrent.futures
import csv
import email.utils
import hashlib
import html
import http.client
import json
import os
import random
import re
import socket
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from ark.baseline import baseline_dir

TEST_ID = "q1-archive-scale"
SEED = 20261012
SAMPLE_SIZE = 200
UA = "internet-digital-ark/1.0 (research; Open Research Questions test)"
TIMEOUT, TRIES, FIRST_WAIT, GAP = 120, 6, 60.0, 1.0
OUT = Path("docs/orq/results") / TEST_ID
HOSTS = OUT / "cache" / "hosts.csv"  # every disc host; regenerable, so kept out of git
HIS = baseline_dir()  # his release, in the repository or a delivery
HIS_YEARS = range(1996, 2002)
PSL = Path("src/ark/data/public_suffix_list.dat")
SEARCH = "https://archive.org/advancedsearch.php"
COLLECTIONS = [
    "cdromimages", "cdbbsarchive", "cdromsoftware", "walnutcreekcdrom", "usenethistorical",
    "giganews", "usenet", "ftpsites", "archiveteam_ftp", "softwarelibrary",
]  # fmt: skip
TERMS = '(internet OR www OR "world wide web" OR gopher OR usenet OR ftp OR html)'
COUNTS = {
    "items": "collection:{c}",
    "dated": "collection:{c} AND date:[* TO *]",
    "dated_1990_1995": "collection:{c} AND date:[1990-01-01 TO 1995-12-31]",
    "dated_1990_1995_internet": "collection:{c} AND date:[1990-01-01 TO 1995-12-31] AND "
    f"(title:{TERMS} OR subject:{TERMS} OR description:{TERMS})",
}
DISC, DISC_FILE = "wointernet", "internet.zip"
HISTORICAL = {"yu", "ac.yu", "co.yu", "edu.yu", "gov.yu", "org.yu", "an", "com.an", "edu.an"}
HISTORICAL |= {"net.an", "org.an", "bu", "cs", "dd", "gb", "tp", "um", "zr", "com.zr"}
# .arpa is left out: its names on the disc are pre-DNS hosts and reverse zones, never websites
GTLD_1994 = {"com", "edu", "gov", "mil", "net", "org", "int"}
NOT_1994 = {"ps"}  # delegated in 2000; on this disc only PostScript file names end in it
USENET_ROOTS = {"comp", "rec", "soc", "sci", "alt", "misc", "talk", "bit", "biz", "clari", "gnu"}
USENET_ROOTS |= {"bionet", "vmsnet", "k12", "news"}
URL = re.compile(rb"(?i)\b(?:https?|ftp|gopher|telnet|wais)://([^\s/<>\"'()\[\]{}|\\^`]+)")
NAMED = re.compile(rb"(?<![@\w.-])((?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,4})(?![\w@-]|\.\w)")
LABEL = re.compile(r"^[a-z0-9_]([a-z0-9_-]{0,61}[a-z0-9_])?$")
IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
TEXT_EXT = {"", "TXT", "DOC", "ASC", "HTM", "HTML", "1", "FAQ", "LST", "LIS", "NFO", "ME", "INF"}
SKIP_DIRS = {"ONLINE", "BBS"}
PRINTABLE = set(range(32, 127)) | {9, 10, 12, 13}
HOST_FIELDS = [
    "host", "registrable", "kind", "existed_by", "files", "first_file", "offset",
    "his_years", "registrable_his_years", "outcome",
]  # fmt: skip


def utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def finished(requests: int) -> str:
    """Now, or the last result's time when this run asked nothing new: a rerun on a full
    cache rewrites the wording only."""
    prior = OUT / "result.json"
    if prior.exists():
        doc = json.loads(prior.read_text(encoding="utf-8"))
        if doc.get("requests") == requests and doc.get("finished_at"):
            return doc["finished_at"]
    return utc()


def log(url: str, status: str, seconds: float, outcome: str) -> None:
    with open(OUT / "log.txt", "a", encoding="utf-8") as f:
        f.write(f"{utc()}\t{url}\t{status}\t{seconds:.1f}\t{outcome}\n")


ROBOTS: dict[str, urllib.robotparser.RobotFileParser] = {}


def allowed(url: str) -> bool:
    """The robots.txt of the host actually asked, read once per host."""
    host = urllib.parse.urlsplit(url).netloc
    if host not in ROBOTS:
        # read here, not by RobotFileParser.read(), which has no timeout and can hang forever
        url_txt, rp, t0 = (
            f"https://{host}/robots.txt",
            urllib.robotparser.RobotFileParser(),
            time.time(),
        )
        req = urllib.request.Request(url_txt, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                rp.parse(r.read().decode("utf-8", "replace").splitlines())
            log(url_txt, "200", time.time() - t0, "robots")
        except urllib.error.HTTPError as e:
            log(url_txt, str(e.code), time.time() - t0, "robots")
            if e.code in (401, 403):
                rp.disallow_all = True
            elif e.code == 429 or e.code >= 500:
                raise
            else:
                rp.allow_all = True
        ROBOTS[host] = rp
    return ROBOTS[host].can_fetch(UA, url)


def wait_for(header: str | None, wait: float) -> float:
    if header and header.strip().isdigit():
        return float(header.strip())
    if header:
        try:
            return max(0.0, email.utils.parsedate_to_datetime(header).timestamp() - time.time())
        except (TypeError, ValueError):
            pass
    return wait


class Opener(urllib.request.HTTPRedirectHandler):
    """Hand every redirect back, so the next hop's robots.txt is read before it is asked."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPEN = urllib.request.build_opener(Opener)
socket.setdefaulttimeout(TIMEOUT)  # no socket read waits longer than this, robots.txt included


FINAL: dict[str, str] = {}  # url -> the hop that served it, so a range request skips the 302


def get(
    url: str, md5: str | None = None, tries: int = TRIES, span: tuple[int, int] | None = None
) -> bytes | None:
    """The body (bytes span[0] to span[1] when given), or None once the tries failed (the
    caller records it unresolved). A transfer cut short keeps its bytes and the next try asks
    for the rest by Range."""
    wait, body, final = FIRST_WAIT, bytearray(), FINAL.get(url)
    for attempt in range(1, tries + 1):
        hop, retry_after = final or url, None
        try:
            for _ in range(5):
                if not allowed(hop):
                    log(hop, "-", 0, "robots_refused")
                    return None
                time.sleep(GAP)
                t0 = time.time()
                headers = {"User-Agent": UA}
                if span:
                    headers["Range"] = f"bytes={span[0] + len(body)}-{span[1]}"
                elif body and hop == final:
                    headers["Range"] = f"bytes={len(body)}-"
                req = urllib.request.Request(hop, headers=headers)
                try:
                    with OPEN.open(req, timeout=TIMEOUT) as r:
                        final, status = hop, r.status
                        if status != 206:
                            if span:
                                log(hop, str(status), time.time() - t0, "range ignored")
                                return None
                            body = bytearray()
                        while chunk := r.read(1 << 20):
                            body += chunk
                except urllib.error.HTTPError as e:
                    if e.code in (301, 302, 303, 307, 308):
                        log(hop, str(e.code), time.time() - t0, "redirect")
                        hop = urllib.parse.urljoin(hop, e.headers["Location"])
                        continue
                    retry_after = e.headers.get("Retry-After")
                    log(hop, str(e.code), time.time() - t0, f"error try {attempt}")
                    if e.code == 429 or e.code >= 500:
                        break
                    return None
                if md5 and hashlib.md5(body).hexdigest() != md5:
                    log(hop, str(status), time.time() - t0, f"md5 mismatch try {attempt}")
                    body, final = bytearray(), None
                    break
                rng = f" range {span[0]}-{span[1]}" if span else ""
                log(hop, str(status), time.time() - t0, f"ok {len(body)} bytes{rng}")
                FINAL[url] = final
                return bytes(body)
        except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
            log(hop, type(e).__name__, 0, f"error try {attempt}, {len(body)} bytes kept")
        final = None  # a failing hop is not asked again; the next try follows the 302 afresh
        FINAL.pop(url, None)
        if attempt < tries:
            time.sleep(wait_for(retry_after, wait))
            wait *= 2
    return None


def count(query: str) -> int | None:
    """numFound once two consecutive answers agree, else None (unresolved)."""
    url = (
        SEARCH
        + "?"
        + urllib.parse.urlencode({"q": query, "fl[]": "identifier", "rows": "0", "output": "json"})
    )
    last = None
    for _ in range(TRIES):
        body = get(url)
        if body is None:
            return None
        try:
            n = int(json.loads(body)["response"]["numFound"])
        except (ValueError, KeyError, TypeError):
            n = None
        if n is not None and n == last:
            return n
        last = n
    return None


def part1() -> list[dict]:
    """One row per collection and count; a resumed run asks only what is missing or unresolved."""
    path, fields = OUT / "counts.csv", ["collection", "count", "query", "value"]
    state = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            state = {(r["collection"], r["count"]): r for r in csv.DictReader(f)}
    for c in COLLECTIONS:
        for name, template in COUNTS.items():
            row = state.get((c, name))
            if row is None or row["value"] == "unresolved":
                n = count(template.format(c=c))
                state[(c, name)] = {"collection": c, "count": name, "query": template.format(c=c),
                                    "value": "unresolved" if n is None else str(n)}  # fmt: skip
                with open(path, "w", encoding="utf-8", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=fields)
                    w.writeheader()
                    w.writerows(state.values())
    return [state[(c, n)] for c in COLLECTIONS for n in COUNTS]


def load_psl() -> tuple[set[str], set[str], set[str]]:
    rules, wild, exc = set(HISTORICAL), set(), set()
    for line in PSL.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if "BEGIN PRIVATE DOMAINS" in line:
            break
        if not line or line.startswith("//"):
            continue
        rule = line.split()[0]
        if not rule.isascii():
            continue
        if rule.startswith("!"):
            exc.add(rule[1:])
        elif rule.startswith("*."):
            wild.add(rule[2:])
        else:
            rules.add(rule)
    return rules, wild, exc


RULES, WILD, EXC = load_psl()


def registrable(host: str) -> str | None:
    labels = host.split(".")
    for i in range(len(labels)):
        cand = ".".join(labels[i:])
        if cand in EXC:
            i += 1
        elif not (cand in RULES or ".".join(labels[i + 1 :]) in WILD):
            continue
        return ".".join(labels[i - 1 :]) if i >= 1 else None
    return None


def valid(s: str) -> bool:
    return (
        bool(s)
        and len(s) <= 253
        and "." in s
        and not IPV4.match(s)
        and all(LABEL.match(x) for x in s.split("."))
        and registrable(s) is not None
    )


def url_host(raw: bytes) -> str | None:
    s = raw.decode("latin-1").lower().rsplit("@", 1)[-1]
    s = re.sub(r":\d*$", "", s).strip(".,;:!?*")
    return s if valid(s) and s.rsplit(".", 1)[-1] not in NOT_1994 | {"arpa"} else None


def named_host(raw: bytes) -> str | None:
    s = raw.decode("latin-1").lower()
    labels = s.split(".")
    if labels[0] in USENET_ROOTS or not valid(s):
        return None
    tld = labels[-1]
    if tld in NOT_1994:
        return None
    if tld in GTLD_1994 and len(labels) >= 2:
        return s
    if len(tld) == 2 and len(labels) >= 3:
        return s
    return None


def day(info: zipfile.ZipInfo) -> str:
    y, m, d = info.date_time[:3]
    return f"{y:04d}-{m:02d}-{d:02d}"


def candidate(name: str) -> bool:
    """A member worth reading: a text-like extension, outside the folders of online-service and
    BBS client software (CompuServe, GEnie, BBS), whose extensionless files are binaries."""
    parts = name.upper().split("/")
    if len(parts) > 2 and parts[2] in SKIP_DIRS:
        return False
    base = parts[-1]
    return (base.rsplit(".", 1)[-1] if "." in base else "") in TEXT_EXT


def is_text(data: bytes) -> bool:
    head = data[:4096]
    if not head or b"\0" in head:
        return False
    return sum(1 for b in head if b in PRINTABLE or b >= 160) >= 0.95 * len(head)


def listing() -> list[tuple[str, str, int]] | None:
    """(member, mtime, size) for each file the served listing names."""
    body = get(f"https://archive.org/download/{DISC}/{DISC_FILE}/")
    if body is None:
        return None
    text = body.decode("utf-8", "replace")
    row = r'<tr><td><a href="[^"]+">([^<]+)</a><td>[^<]*<td>([^<]*)<td id="size">(\d+)'
    rows = re.findall(row, text)
    return [(html.unescape(n), t, int(s)) for n, t, s in rows]


def comm_hits(names: list[str], year: int) -> set[str]:
    """Lines of `names` (C-sorted, unique) present in his file for `year`, by LC_ALL=C comm."""
    tmp = OUT / "names.tmp"
    tmp.write_text("".join(n + "\n" for n in names), encoding="ascii")
    out = subprocess.run(
        ["comm", "-12", str(tmp), str(HIS / f"{year}.txt")],
        capture_output=True, text=True, env={**os.environ, "LC_ALL": "C"}, check=True,
    )  # fmt: skip
    tmp.unlink()
    return set(out.stdout.split())


class RangeFile:
    """The remote zip as a seekable file for zipfile. Only the BLOCK-sized blocks that hold the
    members to read are fetched, by HTTP Range, WORKERS at a time; zipfile checks each
    member's CRC-32 as it reads it."""

    BLOCK, WORKERS = 1 << 20, 3

    def __init__(self, url: str, size: int):
        self.url, self.size, self.pos, self.blocks = url, size, 0, {}

    def prefetch(self, spans: list[tuple[int, int]]) -> None:
        last = (self.size - 1) // self.BLOCK
        need = {i for a, b in spans for i in range(a // self.BLOCK, b // self.BLOCK + 1)}
        need = sorted(i for i in need if i <= last)
        need = [i for i in need if i not in self.blocks]
        with concurrent.futures.ThreadPoolExecutor(self.WORKERS) as pool:
            for i, data in zip(need, pool.map(self.fetch, need), strict=True):
                if data is not None:
                    self.blocks[i] = data

    def fetch(self, i: int) -> bytes | None:
        start = i * self.BLOCK
        return get(self.url, span=(start, min(self.size, start + self.BLOCK) - 1))

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = 0) -> int:
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def read(self, n: int | None = -1) -> bytes:
        end = self.size if n is None or n < 0 else min(self.size, self.pos + n)
        out = bytearray()
        while self.pos < end:
            i = self.pos // self.BLOCK
            if i not in self.blocks:
                data = self.fetch(i)
                if data is None:
                    raise OSError(f"block {i} unresolved")
                self.blocks[i] = data
            off = self.pos - i * self.BLOCK
            take = self.blocks[i][off : off + end - self.pos]
            if not take:
                raise OSError(f"block {i} short")
            out += take
            self.pos += len(take)
        return bytes(out)


def part2() -> dict:
    """The disc: hosts.csv plus its counts in disc.json; both are kept for a resumed run."""
    if (OUT / "cache" / "disc.json").exists() and HOSTS.exists():
        return json.loads((OUT / "cache" / "disc.json").read_text(encoding="utf-8"))
    meta = get(f"https://archive.org/metadata/{DISC}")
    served = listing()
    if meta is None or served is None:
        return {"unresolved": 1}
    meta = json.loads(meta)
    size = int(next(f["size"] for f in meta["files"] if f["name"] == DISC_FILE))
    remote = RangeFile(f"https://archive.org/download/{DISC}/{DISC_FILE}", size)
    try:
        zf = zipfile.ZipFile(remote)
    except (OSError, zipfile.BadZipFile):
        return {"unresolved": 1}
    members = [i for i in zf.infolist() if not i.is_dir()]
    chosen = [i for i in members if candidate(i.filename)]
    chosen.sort(key=lambda i: i.header_offset)
    # local header, name and extra field fit in 64 KB beyond the central directory's offset
    remote.prefetch([(i.header_offset, i.header_offset + i.compress_size + 65536) for i in chosen])
    hosts: dict[str, dict] = {}
    files_read = unread = 0
    for info in chosen:
        try:
            data = zf.read(info)
        except (OSError, zipfile.BadZipFile, EOFError):
            unread += 1
            continue
        if not is_text(data):
            continue
        files_read += 1
        stamp = day(info)
        found = [(m, "url", url_host(m.group(1))) for m in URL.finditer(data)]
        found += [(m, "named", named_host(m.group(1))) for m in NAMED.finditer(data)]
        for m, kind, host in found:
            if host is None:
                continue
            h = hosts.get(host)
            # the locator is the member and the byte offset of the name in it; no text is kept,
            # since the lists around a name carry people's names and addresses
            if h is None:
                hosts[host] = h = {
                    "host": host, "registrable": registrable(host), "kind": kind,
                    "existed_by": stamp, "files": set(), "first_file": info.filename,
                    "offset": m.start(1),
                }  # fmt: skip
            if kind == "url":
                h["kind"] = "url"
            if stamp < h["existed_by"]:
                h["existed_by"], h["first_file"], h["offset"] = stamp, info.filename, m.start(1)
            h["files"].add(info.filename)
    names = sorted(hosts)
    regs = sorted({h["registrable"] for h in hosts.values()})
    held = {y: comm_hits(sorted(set(names) | set(regs)), y) for y in HIS_YEARS}
    outcomes = dict.fromkeys(
        ["host_in_his_1996", "host_in_his_1997_2001_only", "registrable_only", "in_none"], 0
    )
    for name in names:
        h = hosts[name]
        h["files"] = len(h["files"])
        h["his_years"] = " ".join(str(y) for y in HIS_YEARS if name in held[y])
        h["registrable_his_years"] = " ".join(
            str(y) for y in HIS_YEARS if h["registrable"] in held[y]
        )
        if name in held[1996]:
            h["outcome"] = "host_in_his_1996"
        elif h["his_years"]:
            h["outcome"] = "host_in_his_1997_2001_only"
        elif h["registrable_his_years"]:
            h["outcome"] = "registrable_only"
        else:
            h["outcome"] = "in_none"
        outcomes[h["outcome"]] += 1
    with open(HOSTS, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HOST_FIELDS)
        w.writeheader()
        w.writerows(hosts[n] for n in names)
    url_names = [n for n in names if hosts[n]["kind"] == "url"]
    # the disc's host tables (SRI-NIC HOSTS.TXT and domain index), a lens already measured
    tables = [n for n in names if "/MAPS/NETINFO/" in hosts[n]["first_file"].upper()]
    mtimes = sorted(day(i) for i in members)
    disc = {
        "disc_date_metadata": meta["metadata"].get("date", ""),
        "disc_latest_member_mtime": mtimes[-1],
        "disc_earliest_member_mtime": mtimes[0],
        "listing_files": len(served),
        "zip_files": len(members),
        "candidate_files": len(chosen),
        "files_read": files_read,
        "bytes_fetched": sum(len(b) for b in remote.blocks.values()),
        "hosts": len(names),
        "url_hosts": len(url_names),
        "url_hosts_in_his_1996": sum(1 for n in url_names if n in held[1996]),
        "host_table_hosts": len(tables),
        "host_table_hosts_in_his_1996": sum(1 for n in tables if n in held[1996]),
        "registrables": len(regs),
        "registrable_in_his_1996": sum(1 for g in regs if g in held[1996]),
        "registrable_in_none": sum(1 for g in regs if not any(g in held[y] for y in HIS_YEARS)),
        **outcomes,
        "unresolved": unread,
    }
    (OUT / "cache" / "disc.json").write_text(json.dumps(disc, indent=2) + "\n", encoding="utf-8")
    return disc


def main() -> None:
    (OUT / "cache").mkdir(parents=True, exist_ok=True)
    (OUT / "cache" / ".gitignore").write_text("*\n", encoding="utf-8")
    started = utc()
    if (OUT / "log.txt").exists():  # a resumed run starts where log.txt starts
        started = (OUT / "log.txt").read_text(encoding="utf-8").split("\t", 1)[0] or started
    counts = part1()
    disc = part2()
    names = []
    if HOSTS.exists():
        with open(HOSTS, encoding="utf-8") as f:
            hosts = {r["host"]: r for r in csv.DictReader(f)}
        names = sorted(hosts)
        sample = sorted(random.Random(SEED).sample(names, min(SAMPLE_SIZE, len(names))))
        with open(OUT / "sample.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=HOST_FIELDS)
            w.writeheader()
            w.writerows(hosts[n] for n in sample)
    value = {(r["collection"], r["count"]): r["value"] for r in counts}
    unresolved = sum(1 for r in counts if r["value"] == "unresolved") + disc.get("unresolved", 0)
    outcomes = {f"{c}.{k}": value[(c, k)] for c in COLLECTIONS for k in COUNTS}
    outcomes = {k: int(v) if v.isdigit() else v for k, v in outcomes.items()}
    outcomes.update({f"disc.{k}": v for k, v in disc.items() if k != "unresolved"})

    def total(k: str) -> int:
        return sum(int(value[(c, k)]) for c in COLLECTIONS if value[(c, k)].isdigit())

    share = disc.get("host_in_his_1996", 0) / disc["hosts"] if disc.get("hosts") else 0.0
    table_share = disc.get("host_table_hosts", 0) / max(1, disc.get("hosts", 0))
    usenet = ("usenethistorical", "giganews", "usenet")
    usenet_dated, usenet_items = (sum(int(value[c, k]) for c in usenet) for k in ("dated", "items"))
    log = OUT / "log.txt"
    requests = len(log.read_text(encoding="utf-8").splitlines()) if log.exists() else 0
    result = {
        "id": TEST_ID,
        "question": "Q1",
        "title": "Pre-1996 items on archive.org",
        "label": "Tested, not independently verified",
        "command": f"uv run python scripts/orq/{TEST_ID}.py",
        "sources": [
            SEARCH,
            f"https://archive.org/details/{DISC}",
            f"https://archive.org/download/{DISC}/{DISC_FILE}/",
        ],  # fmt: skip
        "population": f"items of {len(COLLECTIONS)} archive.org collections "
        f"({', '.join(COLLECTIONS)}); the text members of one 1994 disc, {DISC}/{DISC_FILE}",
        "sample": f"{len(COLLECTIONS)} collections; one 1994 disc, its "
        f"{disc.get('files_read', 0):,} text files read",
        "query": "advancedsearch numFound for collection:<c> with date:[1990-01-01 TO 1995-12-31] "
        "and Internet terms in title, subject or description; disc hosts by URL and dotted-name "
        "rules, diffed by LC_ALL=C comm against your 1996 to 2001 files",
        "outcomes": outcomes,
        "result": f"{total('dated_1990_1995'):,} items dated 1990 to 1995; disc: "
        f"{disc.get('hosts', 0):,} hosts, {share:.0%} in your 1996 file",
        "finding": f"Only {usenet_dated} of {usenet_items:,} Usenet items on archive.org carry a "
        f"date, so a file's own headers must date it; {table_share:.0%} of the 1994 disc's hosts "
        "come from its copy of the host tables.",
        "limits": "Counts are item metadata, not content; one disc is no coverage estimate. Bare "
        "names include host-table entries and file-name noise: candidates at best.",
        "started_at": started,
        "finished_at": finished(requests),
        "requests": requests,
        "unresolved": unresolved,
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("result", "unresolved", "requests")}, indent=2))


if __name__ == "__main__":
    main()
