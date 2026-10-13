"""q1-usenet-www-announce: the web hosts 1994 to 1995 Usenet named; does his list hold them?

    uv run python scripts/orq/q1-usenet-www-announce.py

Source: the Internet Archive's Usenet Historical Collection, item usenet-comp, one mbox.zip per
group: comp.infosystems.www.announce (moderated new-site announcements), comp.infosystems.www
(the pre-split group, which carried the 1994 announcements) and comp.infosystems.www.providers.
Each zip is fetched whole into memory, checked against the md5 the item's metadata lists, and
read in-stream; no raw byte is written to disk. A post counts once (by Message-ID) when its
Date header year is 1994 or 1995. Every http(s) URL in its body gives a host, quoted lines and
the announce moderator's footer excluded: lowercased, port and userinfo dropped, valid DNS
labels, an ICANN suffix of the vendored public suffix list, a gTLD of 1994 or a two-letter
ccTLD (so no placeholder like www.foo). Address literals and the rest are counted apart.
A host's year is the post's Date year; its locator is the Message-ID of its first post.

Each distinct host is diffed against his 1996 to 2001 annual files with LC_ALL=C comm, as an
exact hostname and as its registrable name. A throttle, timeout, refused connect, 5xx or a
checksum mismatch is retried (Retry-After, else 60 s doubling, 6 tries) and never read as an
empty group: an exhausted group is "unresolved". Resumable: a group whose records file in
cache/ is complete is not fetched again; hosts are derived from those records on every run.
Writes only under docs/orq/results/q1-usenet-www-announce/.
"""

import csv
import email.utils
import hashlib
import http.client
import io
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

TEST_ID = "q1-usenet-www-announce"
SEED = 20261012
SAMPLE_SIZE = 200
YEARS = (1994, 1995)
ITEM = "usenet-comp"
GROUPS = (
    "comp.infosystems.www.announce",
    "comp.infosystems.www",
    "comp.infosystems.www.providers",
)
UA = "internet-digital-ark/1.0 (research; Open Research Questions test)"
TIMEOUT, TRIES, FIRST_WAIT = 120, 6, 60.0
OUT = Path("docs/orq/results") / TEST_ID
HIS = baseline_dir()  # his release, in the repository or a delivery
HIS_YEARS = range(1996, 2002)
PSL = Path("src/ark/data/public_suffix_list.dat")
# retired ccTLDs of the period, as src/ark/canonical.py adds them
HISTORICAL = {"yu", "ac.yu", "co.yu", "edu.yu", "gov.yu", "org.yu", "an", "com.an", "edu.an"}
HISTORICAL |= {"net.an", "org.an", "bu", "cs", "dd", "gb", "tp", "um", "zr", "com.zr"}
URL = re.compile(rb"(?i)\bhttps?://([^\s/<>\"'()\[\]{}|\\^`]+)")
GTLD_1994 = {"com", "edu", "gov", "mil", "net", "org", "int"}  # .arpa names no website
STRICT = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")  # the registered label
LABEL = re.compile(r"^[a-z0-9_]([a-z0-9_-]{0,61}[a-z0-9_])?$")
IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
FOOTER = re.compile(rb"(?i)infosystems\.www\.announce|c\.i\.w\.announce|www-announce@|moderator")
DOTS = re.compile(rb"^\s*(\. ){10,}")  # the announce moderator's footer rule, " . . . ."
SEPARATOR = re.compile(rb"^From -?\d+\s*$")
RECORD_FIELDS = ["group", "message_id", "date", "year", "url"]
HOST_FIELDS = [
    "host", "registrable", "year", "first_date", "posts", "group", "message_id", "url",
    "in_his_1996", "his_years", "registrable_his_years", "outcome",
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


def get(url: str, md5: str | None = None) -> bytes | None:
    """The body, or None once 6 tries failed (the caller records it unresolved)."""
    wait = FIRST_WAIT
    for attempt in range(1, TRIES + 1):
        hop, retry_after = url, None
        try:
            for _ in range(5):
                if not allowed(hop):
                    log(hop, "-", 0, "robots_refused")
                    return None
                t0 = time.time()
                req = urllib.request.Request(hop, headers={"User-Agent": UA})
                try:
                    with OPEN.open(req, timeout=TIMEOUT) as r:
                        body = r.read()
                        status = r.status
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
                    break
                log(hop, str(status), time.time() - t0, f"ok {len(body)} bytes")
                return body
        except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
            log(hop, type(e).__name__, 0, f"error try {attempt}")
        if attempt < TRIES:
            time.sleep(wait_for(retry_after, wait))
            wait *= 2
    return None


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


def clean_host(raw: bytes) -> tuple[str | None, str]:
    """(host, "") or (None, reason)."""
    s = raw.decode("latin-1").lower().rsplit("@", 1)[-1]
    s = re.sub(r":\d*$", "", s).strip(".,;:!?*")
    if IPV4.match(s) or s.startswith("["):
        return None, "address"
    if not s or len(s) > 253 or not all(LABEL.match(x) for x in s.split(".")) or "." not in s:
        return None, "invalid"
    reg = registrable(s)
    if reg is None:
        return None, "no_suffix"
    if not STRICT.match(reg.split(".")[0]):
        return None, "invalid"
    if not (s.rsplit(".", 1)[-1] in GTLD_1994 or len(s.rsplit(".", 1)[-1]) == 2):
        return None, "tld_after_1995"
    return s, ""


def post_date(value: str) -> tuple[str, int] | None:
    m = re.match(r"\s*(\d{4})/(\d\d)/(\d\d)", value)  # the Deja News form, 1995/12/29
    if m:
        return f"{m[1]}-{m[2]}-{m[3]}", int(m[1])
    try:
        d = email.utils.parsedate_to_datetime(value)
        return d.strftime("%Y-%m-%d"), d.year
    except (TypeError, ValueError, IndexError):
        return None


def posts(mbox: bytes):
    """Yield (headers dict, body lines) per post; a post starts at a 'From <number>' line
    after a blank line, the export's separator."""
    lines = mbox.split(b"\n")
    start, prev_blank = None, True
    for i, line in enumerate(lines + [b"From 0"]):
        if prev_blank and SEPARATOR.match(line):
            if start is not None:
                yield split_post(lines[start:i])
            start = i + 1
        prev_blank = not line.strip()


def split_post(block: list[bytes]) -> tuple[dict[str, str], list[bytes]]:
    headers: dict[str, str] = {}
    last = None
    for n, line in enumerate(block):
        if not line.strip():
            return headers, block[n + 1 :]
        if line[:1] in (b" ", b"\t") and last:
            headers[last] += " " + line.strip().decode("latin-1")
            continue
        name, _, value = line.decode("latin-1").partition(":")
        last = name.strip().lower()
        headers.setdefault(last, value.strip())
    return headers, []


def body_urls(body: list[bytes]) -> list[bytes]:
    """Unquoted body lines; the last signature block is dropped when it is the moderator's
    (it opens with a dotted rule or names the group, its address or the moderator)."""
    cut = len(body)
    for n in range(len(body) - 1, -1, -1):
        if body[n].rstrip(b"\r") == b"-- ":
            if FOOTER.search(b"\n".join(body[n:])) or DOTS.match(b"".join(body[n + 1 : n + 2])):
                cut = n
            break
    text = b"\n".join(x for x in body[:cut] if not x.lstrip().startswith(b">"))
    return [m.group(0) for m in URL.finditer(text)]


def extract(group: str, zbytes: bytes) -> list[dict]:
    """One row per URL of each post dated in YEARS, and one url-less row for a post with none."""
    rows = []
    zf = zipfile.ZipFile(io.BytesIO(zbytes))
    for member in zf.namelist():
        for headers, body in posts(zf.read(member)):
            dated = post_date(headers.get("date", ""))
            if not dated or dated[1] not in YEARS:
                continue
            mid = headers.get("message-id", "").split("#")[0].strip()
            if not mid:
                continue
            base = {"group": group, "message_id": mid, "date": dated[0], "year": dated[1]}
            urls = body_urls(body)
            for url in urls:
                rows.append({**base, "url": url.decode("latin-1")})
            if not urls:
                rows.append({**base, "url": ""})
    return rows


def metadata_md5() -> dict[str, str] | None:
    raw = get(f"https://archive.org/metadata/{ITEM}")
    if raw is None:
        return None
    return {f["name"]: f.get("md5") for f in json.loads(raw)["files"]}


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


def main() -> None:
    # the per-post records are a resume cache, kept out of git by their own .gitignore
    (OUT / "cache").mkdir(parents=True, exist_ok=True)
    (OUT / "cache" / ".gitignore").write_text("*\n", encoding="utf-8")
    started = utc()
    if (OUT / "log.txt").exists():  # a resumed run starts where log.txt starts
        started = (OUT / "log.txt").read_text(encoding="utf-8").split("\t", 1)[0] or started
    md5s, unresolved, records = None, [], []
    for group in GROUPS:
        path = OUT / "cache" / f"records-{group}.csv"
        if not (path.exists() and path.read_text(encoding="utf-8").endswith("#complete\n")):
            md5s = md5s or metadata_md5()
            name = f"{group}.mbox.zip"
            url = f"https://archive.org/download/{ITEM}/{urllib.parse.quote(name)}"
            zbytes = get(url, md5s.get(name)) if md5s and md5s.get(name) else None
            if zbytes is None:
                unresolved.append(group)
                continue
            with open(path, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=RECORD_FIELDS)
                w.writeheader()
                w.writerows(extract(group, zbytes))
                f.write("#complete\n")
        with open(path, encoding="utf-8") as f:
            records += list(csv.DictReader(x for x in f if not x.startswith("#")))
    # a crossposted post is one post: counted once, by Message-ID, under its first group
    first_group: dict[str, str] = {}
    for r in records:
        first_group.setdefault(r["message_id"], r["group"])
    records = [r for r in records if first_group[r["message_id"]] == r["group"]]
    # a URL counts once per post, however often the post or the URL repeats
    records = list({(r["message_id"], r["url"]): r for r in records}.values())
    for r in records:
        raw = URL.match(r["url"].encode("latin-1")) if r["url"] else None
        r["host"], r["skipped"] = clean_host(raw.group(1)) if raw else (None, "")
    stats: dict[str, int] = {}

    def bump(key: str) -> None:
        stats[key] = stats.get(key, 0) + 1

    year_of = {r["message_id"]: r["year"] for r in records}
    for mid, y in year_of.items():
        bump(f"posts_{y}")
        bump(f"posts_{first_group[mid]}")
    for mid in {r["message_id"] for r in records if r["host"]}:
        bump(f"posts_with_url_{year_of[mid]}")
    for r in records:
        if r["host"]:
            bump("urls")
        elif r["skipped"]:
            bump(f"urls_skipped_{r['skipped']}")
    hosts: dict[str, dict] = {}
    by_year: dict[int, set[str]] = {y: set() for y in YEARS}
    for r in sorted((r for r in records if r["host"]), key=lambda r: (r["date"], r["message_id"])):
        by_year[int(r["year"])].add(r["host"])
        h = hosts.get(r["host"])
        if h is None:
            hosts[r["host"]] = h = {
                "host": r["host"], "registrable": registrable(r["host"]), "year": r["year"],
                "first_date": r["date"], "posts": set(), "group": r["group"],
                "message_id": r["message_id"], "url": r["url"],
            }  # fmt: skip
        h["posts"].add(r["message_id"])
    names = sorted(hosts)
    regs = sorted({h["registrable"] for h in hosts.values()})
    held = {y: comm_hits(sorted(set(names) | set(regs)), y) for y in HIS_YEARS}
    outcomes = dict.fromkeys(
        ["host_in_his_1996", "host_in_his_1997_2001_only", "registrable_only", "in_none"], 0
    )
    for name in names:
        h = hosts[name]
        h["posts"] = len(h["posts"])
        h["his_years"] = " ".join(str(y) for y in HIS_YEARS if name in held[y])
        h["registrable_his_years"] = " ".join(
            str(y) for y in HIS_YEARS if h["registrable"] in held[y]
        )
        h["in_his_1996"] = "yes" if name in held[1996] else "no"
        if name in held[1996]:
            h["outcome"] = "host_in_his_1996"
        elif h["his_years"]:
            h["outcome"] = "host_in_his_1997_2001_only"
        elif h["registrable_his_years"]:
            h["outcome"] = "registrable_only"
        else:
            h["outcome"] = "in_none"
        outcomes[h["outcome"]] += 1
    with open(OUT / "cache" / "hosts.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HOST_FIELDS)
        w.writeheader()
        w.writerows(hosts[n] for n in names)
    sample = sorted(random.Random(SEED).sample(names, min(SAMPLE_SIZE, len(names))))
    # A Message-ID names its poster, so the shipped sample locates each post by the ID's
    # sha256 instead; the IDs themselves stay in cache/hosts.csv.
    fields = [f if f != "message_id" else "message_id_sha256" for f in HOST_FIELDS]
    with open(OUT / "sample.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for n in sample:
            row = dict(hosts[n])
            mid = row.pop("message_id")
            row["message_id_sha256"] = hashlib.sha256(mid.encode()).hexdigest()
            w.writerow(row)
    for y in YEARS:
        stats[f"hosts_{y}"] = len(by_year[y])
        stats[f"hosts_{y}_in_his_1996"] = len(by_year[y] & held[1996])
    for g in GROUPS:
        named = {r["host"] for r in records if r["host"] and r["group"] == g}
        stats[f"hosts_{g}"] = len(named)
        stats[f"hosts_{g}_in_his_1996"] = len(named & held[1996])
    total = len(names)
    share = outcomes["host_in_his_1996"] / total if total else 0.0
    outcomes.update(stats)
    outcomes.update({
        "hosts": total, "registrables": len(regs),
        "registrable_in_his_1996": sum(1 for g in regs if g in held[1996]),
        "registrable_in_none": sum(1 for g in regs if not any(g in held[y] for y in HIS_YEARS)),
        "unresolved_groups": len(unresolved),
    })  # fmt: skip
    posts_n = sum(stats.get(f"posts_{y}", 0) for y in YEARS)
    log = OUT / "log.txt"
    requests = len(log.read_text(encoding="utf-8").splitlines()) if log.exists() else 0
    result = {
        "id": TEST_ID,
        "question": "Q1",
        "title": "Usenet web announcements",
        "label": "Tested, not independently verified",
        "command": f"uv run python scripts/orq/{TEST_ID}.py",
        "sources": [f"https://archive.org/details/{ITEM}"]
        + [f"https://archive.org/download/{ITEM}/{g}.mbox.zip" for g in GROUPS],
        "population": f"every post dated {YEARS[0]} or {YEARS[-1]} in {', '.join(GROUPS)} "
        f"(Usenet Historical Collection item {ITEM})",
        "sample": f"all {posts_n:,} posts, {YEARS[0]} to {YEARS[-1]}",
        "query": "host of every http(s) URL in each post's unquoted body, year from its Date "
        "header; exact host and registrable name diffed by LC_ALL=C comm against your "
        "1996 to 2001 files",
        "outcomes": outcomes,
        "result": f"{total:,} hosts, {share:.1%} in your 1996 file",
        "finding": f"Your 1996 file already holds {share:.0%} of the web hosts that Usenet's web "
        f"groups named in {YEARS[0]} to {YEARS[-1]}.",
        "limits": "A post dates a mention, not a capture, so nothing here can enter an annual "
        "file. Discussion groups name hosts in examples; only the announce group is "
        "announcement-only.",
        "started_at": started,
        "finished_at": finished(requests),
        "requests": requests,
        "unresolved": len(unresolved),
    }
    (OUT / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("result", "unresolved", "requests")}, indent=2))


if __name__ == "__main__":
    main()
