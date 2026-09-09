"""The only download path a fleet leg has: robots, cap, hash, receipt.

    uv run python scripts/harness/fetch.py URL [--max-bytes 1G] [--to PATH]
    uv run python scripts/harness/fetch.py URL --to -            # stream to a pipe

**Why one program instead of a paragraph in a brief.** Every rule below was bought.
`tomocha.net` disallows ClaudeBot at line 51 of 61 and a ten-line read of its robots.txt
cost a breach and 1,623 EE, so the whole file is read and a by-name group is honoured
wherever it sits. `www.fac.gov` permits everything while every data file it links sits on
`app.fac.gov`, which is `Disallow: /`, so the host that is asked is the host in the
download URL and never the host of the landing page. A researcher shard's own heredoc
reached 5.68 GB resident on a 7.9 GB box shared with the collectors, so bytes are counted
twice, once by `Content-Length` and once by the stream, and the cap is a cap either way.
An agent that types its own `curl` gets none of that and forgets a different rule each
time; there is one implementation and the brief points at it.

**It never extracts anything.** No `unzip`, no `tar x`, no `gunzip` to disk: an archive is
read in-stream by Python, which is what `--to -` is for. That is not this program's taste,
it is what keeps a 50 GB CDXJ off a disk the collectors need.

**Three writes are possible and no others.** `$ARK_PROBE_DIR`, RAM-backed and private to
one run, is where probe bytes go. `$ARK_FETCH_DEST_ROOT` is the second root, set only by
`fetch.yaml` after a human merged a `download` decision, and it is what admits the two
risky content types (a zip, and a body whose type the server will not name) to disk at
all. Anything else exits 2 before a request is made.

Exit codes, because the caller is a workflow and a workflow reads numbers:

    0  fetched, receipt on stdout
    2  usage, or a destination outside the allowed roots
    3  robots refuses this path, by name or by `*`; the artifact was never asked for
    4  robots could not be read, so nothing may be assumed; the artifact was never asked
    5  over the cap, by `Content-Length` or by the stream
    6  the content type is not on the allowlist
    7  the server did not serve it: HTTP error, or the network failed

The receipt is one JSON line: `url, bytes, sha256, content_type, robots`, plus the path it
landed on and whether the cap stopped it. With `--to -` the payload owns stdout and the
receipt goes to stderr; every other invocation prints the receipt on stdout, success or
failure, so a workflow always has something to record.
"""

import argparse
import email.utils
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = (
    "InternetDigitalArk/1.0 (historical domain research, 1996-2001; "
    "contact ivaylo.staykov@taktile.com)"
)

# **The names this project answers to, and it answers to all of them.** A host that
# disallows any one of these has refused us: the crawler identity is not a costume to
# change until a robots.txt lets us in. `docs/lore/traps.md` lists the sixteen hosts that
# already refuse us this way, and `upenn`, `uoc` and `umu` name five of these together in
# one group, which is why the list is a set rather than a guess about which name matters.
OUR_ROBOT_NAMES = frozenset(
    {
        "internetdigitalark",
        "claudebot",
        "claude-user",
        "claude-code",
        "claude-searchbot",
        "claude-web",
        "anthropic-ai",
        "anthropic",
    }
)

# Types a leg may write to disk unattended. Everything here is either text or a stream
# format Python reads without unpacking it first.
ALLOWED_TYPES = (
    "text/",
    "message/rfc822",
    "application/json",
    "application/x-ndjson",
    "application/jsonl",
    "application/xml",
    "application/csv",
    "application/x-csv",
    "application/gzip",
    "application/x-gzip",
    "application/x-gunzip",
    "application/gzipped",
    "application/mbox",
    "application/x-mbox",
    "application/cdx",
    "application/x-cdx",
    "application/cdxj",
    "application/x-cdxj",
)
# A zip, and a body whose type the server will not name. Both are readable in-stream, and
# both are exactly the shape the download backlog exists for, so they are admitted only
# when a human has already said yes: either the payload goes to a pipe, or the destination
# root is the one `fetch.yaml` sets after a `download` PR merged.
RISKY_TYPES = (
    "application/zip",
    "application/x-zip-compressed",
    "application/octet-stream",
    "binary/octet-stream",
    "",
)

RETRY_STATUS = {429, 503, 504}
ATTEMPTS = 4
# A `Retry-After` of an hour is a refusal for now, not a nap: the leg has a ceiling and the
# wave runs again in twenty minutes. Longer than this and the fetch fails, which is what
# puts the lead back in the queue rather than burning its budget asleep.
MAX_SLEEP_SECONDS = 300

OK, USAGE, ROBOTS_REFUSED, ROBOTS_UNREADABLE, OVER_CAP, BAD_TYPE, HTTP_FAILED = 0, 2, 3, 4, 5, 6, 7

SIZE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([kmgt]?)i?b?\s*$", re.IGNORECASE)
UNIT = {"": 1, "k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}


def parse_size(text: str) -> int:
    """`1G`, `1GiB`, `1500m` and `1073741824` all mean the same thing. Binary units."""
    match = SIZE.match(text)
    if not match:
        raise ValueError(f"not a size: {text!r}")
    value = float(match.group(1)) * UNIT[match.group(2).lower()]
    if value < 1:
        raise ValueError("a cap under one byte fetches nothing")
    return int(value)


def get(url: str, timeout: float) -> tuple[int, dict, object]:
    """One request with the honest User-Agent. Returns (status, headers, body stream)."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        response = urllib.request.urlopen(request, timeout=timeout)  # noqa: S310
        return response.status, dict(response.headers), response
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers or {}), exc


def retry_after_seconds(headers: dict, now: float | None = None) -> float | None:
    """`Retry-After` as the RFC allows it: a count of seconds, or an HTTP date."""
    raw = next((v for k, v in headers.items() if k.lower() == "retry-after"), None)
    if raw is None:
        return None
    raw = raw.strip()
    if raw.isdigit():
        return float(raw)
    try:
        when = email.utils.parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    return max(0.0, when.timestamp() - (now if now is not None else time.time()))


# ---------------------------------------------------------------- robots


def robots_groups(text: str) -> list[tuple[set[str], list[tuple[str, str]]]]:
    """Every group in the file as (agent names, [(directive, value)]).

    Consecutive `User-agent` lines open one group together, as the standard says, and a
    directive after a rule starts the next group. Nothing here stops early: a group at line
    51 of 61 binds exactly as hard as the group at line 1.
    """
    groups: list[tuple[set[str], list[tuple[str, str]]]] = []
    agents: set[str] = set()
    rules: list[tuple[str, str]] = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field, value = field.strip().lower(), value.strip()
        if field in ("user-agent", "useragent"):
            if rules:
                groups.append((agents, rules))
                agents, rules = set(), []
            agents.add(value.lower())
        elif field in ("disallow", "allow", "crawl-delay"):
            rules.append((field, value))
    if agents or rules:
        groups.append((agents, rules))
    return groups


def _matches(pattern: str, path: str) -> bool:
    """robots path matching: a prefix, with `*` any run and `$` an anchor at the end."""
    if not pattern:
        return False
    anchored = pattern.endswith("$")
    body = pattern[:-1] if anchored else pattern
    expr = "".join(".*" if ch == "*" else re.escape(ch) for ch in body)
    return re.match(expr + ("$" if anchored else ""), path) is not None


def robots_verdict(text: str, path: str) -> tuple[str, float, str]:
    """`allowed` or `refused` for this path, the crawl delay, and the reason in words.

    **Stricter than the standard on purpose.** RFC 9309 says the most specific matching
    group wins, so a by-name group that permits would shadow a `*` group that refuses. Here
    a refusal in EITHER the by-name groups or the `*` group refuses the fetch. The cost of
    the strict reading is a lead that goes to the register unread; the cost of the loose one
    is a breach, and the register already carries one.
    """
    worst = ("allowed", "no group in this file refuses the path")
    delay = 0.0
    for agents, rules in robots_groups(text):
        named = agents & OUR_ROBOT_NAMES
        if not named and "*" not in agents:
            continue
        best: tuple[tuple[int, int], str, str] | None = None
        for field, value in rules:
            if field == "crawl-delay":
                try:
                    delay = max(delay, float(value))
                except ValueError:
                    pass
                continue
            if field == "disallow" and value == "":
                continue  # an empty Disallow permits everything, per the standard
            if _matches(value, path):
                # Longest match wins inside a group, and `allow` wins a tie of equal length.
                rank = (len(value), 0 if field == "disallow" else 1)
                if best is None or rank > best[0]:
                    best = (rank, field, value)
        if best and best[1] == "disallow":
            who = ", ".join(sorted(named)) if named else "*"
            worst = ("refused", f"`User-agent: {who}` has `Disallow: {best[2]}`")
    return worst[0], delay, worst[1]


def read_robots(url: str, timeout: float) -> tuple[str, float, str]:
    """The whole robots.txt of the host in the DOWNLOAD url, before anything else is asked.

    A 404 is a host with no rules and is `allowed`. Anything else unreadable is `unknown`
    and fails closed: the rule is to read the terms before the first request, and a guess
    is not a read.
    """
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(parts.path or "/", safe="/%~+,:@&=$!*()'")
    if parts.query:
        path += "?" + parts.query
    robots = urllib.parse.urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
    try:
        status, _, body = get(robots, timeout)
        payload = body.read(512 * 1024).decode("utf-8", "replace")
        body.close()
    except OSError as exc:
        return "unknown", 0.0, f"robots.txt could not be read: {exc}"
    if status in (404, 410):
        return "allowed", 0.0, f"the host serves no robots.txt ({status})"
    if status != 200:
        return "unknown", 0.0, f"robots.txt answered {status}"
    return robots_verdict(payload, path)


# ---------------------------------------------------------------- destination


def allowed_roots() -> list[str]:
    roots = []
    for name in ("ARK_PROBE_DIR", "ARK_FETCH_DEST_ROOT"):
        value = (os.environ.get(name) or "").strip()
        if value:
            roots.append(os.path.realpath(value))
    return roots


def resolve_destination(to: str | None, url: str) -> tuple[str, str | None]:
    """The absolute path to write, or an explanation of why there is none.

    `--to` may be a directory, in which case the file is named from the URL. With no `--to`
    the file lands in `$ARK_PROBE_DIR` under the same name.
    """
    roots = allowed_roots()
    if not roots:
        return "", "no ARK_PROBE_DIR and no ARK_FETCH_DEST_ROOT: there is nowhere this may write"
    name = os.path.basename(urllib.parse.urlsplit(url).path) or "download.bin"
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120] or "download.bin"
    target = os.path.join(roots[0], name) if to is None else os.path.abspath(os.path.expanduser(to))
    if os.path.isdir(target):
        target = os.path.join(target, name)
    # The parent is resolved, not the target: a file that does not exist yet has no
    # realpath of its own, and a symlinked parent is exactly the escape worth refusing.
    parent = os.path.realpath(os.path.dirname(target) or ".")
    target = os.path.join(parent, os.path.basename(target))
    if not any(parent == root or parent.startswith(root + os.sep) for root in roots):
        return target, f"{target} is outside {' and '.join(roots)}"
    return target, None


# ---------------------------------------------------------------- the fetch


def content_type_verdict(header: str | None, to_pipe: bool, approved: bool) -> str | None:
    """None when the type may be written, else the reason it may not."""
    kind = (header or "").split(";", 1)[0].strip().lower()
    if kind and kind.startswith(ALLOWED_TYPES):
        return None
    if kind in RISKY_TYPES:
        if to_pipe or approved:
            return None
        return (
            f"content type {kind or 'unnamed'} is readable in-stream only: pass `--to -`, or "
            "put the artifact in downloads.md and let a download decision fetch it"
        )
    return f"content type {kind or 'unnamed'} is not on the allowlist"


def stream(body, out, cap: int) -> tuple[int, str, bool]:
    """Copy up to `cap` bytes, hashing as it goes. Returns (bytes, sha256, over the cap)."""
    digest = hashlib.sha256()
    total = 0
    while True:
        chunk = body.read(256 * 1024)
        if not chunk:
            return total, digest.hexdigest(), False
        total += len(chunk)
        if total > cap:
            # Counted twice on purpose: a chunked response has no Content-Length to check,
            # and a wrong one is a lie the first check believes.
            return total, digest.hexdigest(), True
        digest.update(chunk)
        out.write(chunk)


def fetch(url: str, cap: int, to: str | None, timeout: float, sleep=time.sleep) -> tuple[int, dict]:
    receipt = {
        "url": url,
        "bytes": 0,
        "sha256": None,
        "content_type": None,
        "robots": "unknown",
        "path": None,
        "capped": False,
    }
    to_pipe = to == "-"

    if not to_pipe:
        target, why = resolve_destination(to, url)
        receipt["path"] = target or None
        if why:
            receipt["reason"] = why
            return USAGE, receipt

    verdict, delay, why = read_robots(url, timeout)
    receipt["robots"] = verdict
    receipt["reason"] = why
    if verdict == "refused":
        return ROBOTS_REFUSED, receipt
    if verdict != "allowed":
        return ROBOTS_UNREADABLE, receipt

    for attempt in range(1, ATTEMPTS + 1):
        try:
            status, headers, body = get(url, timeout)
        except OSError as exc:
            receipt["reason"] = f"the request failed: {exc}"
            return HTTP_FAILED, receipt

        if status in RETRY_STATUS and attempt < ATTEMPTS:
            wait = retry_after_seconds(headers)
            if wait is None:
                wait = min(MAX_SLEEP_SECONDS, max(delay, 2.0) * (2 ** (attempt - 1)))
            body.close()
            if wait > MAX_SLEEP_SECONDS:
                receipt["reason"] = f"{status} with Retry-After {wait:.0f}s, longer than we wait"
                return HTTP_FAILED, receipt
            print(f"fetch: {status}, waiting {wait:.0f}s as asked", file=sys.stderr, flush=True)
            sleep(wait)
            continue

        with body:
            if status != 200:
                receipt["reason"] = f"the server answered {status}"
                return HTTP_FAILED, receipt

            receipt["content_type"] = headers.get("Content-Type")
            length = headers.get("Content-Length")
            if length and length.strip().isdigit() and int(length) > cap:
                receipt["bytes"] = int(length)
                receipt["capped"] = True
                receipt["reason"] = (
                    f"Content-Length {int(length)} is over the {cap} byte cap: "
                    "nothing was read, put it in downloads.md"
                )
                return OVER_CAP, receipt

            approved = bool(os.environ.get("ARK_FETCH_DEST_ROOT"))
            bad = content_type_verdict(receipt["content_type"], to_pipe, approved)
            if bad:
                receipt["reason"] = bad
                return BAD_TYPE, receipt

            if to_pipe:
                total, digest, over = stream(body, sys.stdout.buffer, cap)
                sys.stdout.buffer.flush()
            else:
                os.makedirs(os.path.dirname(receipt["path"]), exist_ok=True)
                with open(receipt["path"], "wb") as out:
                    total, digest, over = stream(body, out, cap)
                if over:
                    os.unlink(receipt["path"])
                    receipt["path"] = None

        receipt["bytes"] = total
        receipt["sha256"] = digest
        if over:
            receipt["capped"] = True
            receipt["reason"] = (
                f"the stream passed the {cap} byte cap and was dropped: put it in downloads.md"
            )
            return OVER_CAP, receipt
        receipt["reason"] = f"fetched {total} bytes"
        return OK, receipt

    receipt["reason"] = f"still being throttled after {ATTEMPTS} attempts"
    return HTTP_FAILED, receipt


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("url", help="the artifact, and the host whose robots.txt is read")
    ap.add_argument("--max-bytes", default="1G", help="the cap, binary units (default 1G)")
    ap.add_argument("--to", default=None, help="a file, a directory, or - for stdout")
    ap.add_argument("--timeout", type=float, default=60.0, help="per-request seconds")
    args = ap.parse_args(argv)

    scheme = urllib.parse.urlsplit(args.url).scheme
    if scheme not in ("http", "https"):
        print(f"fetch: {args.url}: only http and https", file=sys.stderr)
        return USAGE
    try:
        cap = parse_size(args.max_bytes)
    except ValueError as exc:
        print(f"fetch: {exc}", file=sys.stderr)
        return USAGE

    code, receipt = fetch(args.url, cap, args.to, args.timeout)
    line = json.dumps(receipt)
    print(line, file=sys.stderr if args.to == "-" else sys.stdout, flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
