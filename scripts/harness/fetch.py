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

**Two write roots and no others.** `$ARK_PROBE_DIR`, RAM-backed and private to one run,
is where probe bytes go. `$ARK_FETCH_DEST_ROOT` is the second, set only by `fetch.yaml`
after a human merged a `download` decision, and a file going INTO it is what admits the two
risky content types (a zip, and a body whose type the server will not name) to disk at all.
Anything else exits 2 before a request is made.

**A redirect is a new request and gets the whole check again.** urllib follows none of them
here: each hop reads the robots.txt of the host it points at, so a 302 from a host that
permits us onto a host that disallows us is refused instead of fetched. Five hops maximum.

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
import http.client
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


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Hand every 3xx back to the caller instead of following it.

    **A followed redirect is a request nobody checked robots for.** `urlopen` will take a
    302 from a host that permits us to a host that disallows us and fetch it without ever
    asking the second host, which is the `www.fac.gov` to `app.fac.gov` shape with the
    check silently skipped. Refusing to follow inside urllib is what lets `fetch()` run the
    whole robots check again on each hop.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)

REDIRECTS = {301, 302, 303, 307, 308}
MAX_HOPS = 5


def get(
    url: str, timeout: float, start: int | None = None, end: int | None = None
) -> tuple[int, dict, object]:
    """One request with the honest User-Agent. Returns (status, headers, body stream).

    Headers come back with lower-cased keys. HTTP field names are case-insensitive and a
    plain `dict(response.headers)` is not: a server sending `content-type:` in lower case
    read as unnamed, and a lower-case `content-length` skipped the first cap check.

    `start` and `end` ask for one span of the artifact, which is how a transfer that ended
    early is continued rather than restarted. **The span is bounded on purpose.** An
    open-ended `bytes=N-` past 2 GiB is answered 206 by the archive and then delivers
    nothing at all, while the same byte asked for as `bytes=N-M` comes back with a correct
    `Content-Range`. Measured against the UKWA artifact on 2026-09-11.
    """
    fields = {"User-Agent": USER_AGENT}
    if start is not None:
        fields["Range"] = f"bytes={start}-{end}" if end is not None else f"bytes={start}-"
    request = urllib.request.Request(url, headers=fields)
    try:
        response = _OPENER.open(request, timeout=timeout)  # noqa: S310
        return response.status, _lower(response.headers), response
    except urllib.error.HTTPError as exc:
        return exc.code, _lower(exc.headers or {}), exc


def _lower(headers) -> dict:
    return {str(k).lower(): v for k, v in headers.items()}


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


def _robots_file(url: str, timeout: float) -> tuple[str | None, str]:
    """The host's robots.txt as text, or None with the reason there is none to read.

    A 404 is a host with no rules. Anything else unreadable is fatal, not permissive: the
    rule is to read the terms before the first request, and a guess is not a read.
    """
    parts = urllib.parse.urlsplit(url)
    robots = urllib.parse.urlunsplit((parts.scheme, parts.netloc, "/robots.txt", "", ""))
    try:
        status, _, body = get(robots, timeout)
        with body:
            payload = body.read(512 * 1024).decode("utf-8", "replace")
    except (OSError, http.client.HTTPException) as exc:
        return None, f"robots.txt could not be read: {exc}"
    if status in (404, 410):
        return "", f"the host serves no robots.txt ({status})"
    if status != 200:
        return None, f"robots.txt answered {status}"
    return payload, "read in full"


def read_robots(url: str, timeout: float, cache: dict | None = None) -> tuple[str, float, str]:
    """The verdict for one URL: `allowed`, `refused` or `unknown`, before anything is asked.

    The cache is per host and exists for redirects: a hop to a second host must read that
    host's rules, and a hop within one host must re-match the new PATH against rules
    already in hand rather than fetching them twice.
    """
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(parts.path or "/", safe="/%~+,:@&=$!*()'")
    if parts.query:
        path += "?" + parts.query
    key = (parts.scheme, parts.netloc)
    if cache is None or key not in cache:
        payload = _robots_file(url, timeout)
        if cache is not None:
            cache[key] = payload
    else:
        payload = cache[key]
    text, why = payload
    if text is None:
        return "unknown", 0.0, why
    if not text:
        return "allowed", 0.0, why
    return robots_verdict(text, path)


# ---------------------------------------------------------------- destination


PROBE_ROOT, APPROVED_ROOT = "ARK_PROBE_DIR", "ARK_FETCH_DEST_ROOT"


def allowed_roots() -> list[tuple[str, str]]:
    """The roots this may write under, as (env var name, resolved path)."""
    roots = []
    for name in (PROBE_ROOT, APPROVED_ROOT):
        value = (os.environ.get(name) or "").strip()
        if value:
            roots.append((name, os.path.realpath(value)))
    return roots


def resolve_destination(to: str | None, url: str) -> tuple[str, str | None, str]:
    """(path, the reason there is none, the name of the root it is under).

    `--to` may be a directory, in which case the file is named from the URL. With no `--to`
    the file lands in `$ARK_PROBE_DIR` under the same name. The root is returned because it
    decides more than the path: a zip or an unnamed content type reaches disk only under
    the approved root, and "the approved root is SET" is not the same claim as "this file
    is going into it".
    """
    roots = allowed_roots()
    if not roots:
        return "", f"no {PROBE_ROOT} and no {APPROVED_ROOT}: there is nowhere this may write", ""
    name = os.path.basename(urllib.parse.urlsplit(url).path) or "download.bin"
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:120] or "download.bin"
    default = roots[0][1]
    target = os.path.join(default, name) if to is None else os.path.abspath(os.path.expanduser(to))
    if os.path.isdir(target):
        target = os.path.join(target, name)
    # The parent is resolved, not the target: a file that does not exist yet has no
    # realpath of its own, and a symlinked parent is exactly the escape worth refusing.
    # The target itself may still BE a symlink, which is why the write uses O_NOFOLLOW.
    parent = os.path.realpath(os.path.dirname(target) or ".")
    target = os.path.join(parent, os.path.basename(target))
    if os.path.islink(target):
        return target, f"{target} is a symlink, so where it writes is not where it says", ""
    for env, root in roots:
        if parent == root or parent.startswith(root + os.sep):
            return target, None, env
    return target, f"{target} is outside {' and '.join(root for _, root in roots)}", ""


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


def stream(body, out, cap: int, digest=None, seen: int = 0) -> tuple[int, str, bool]:
    """Copy up to `cap` bytes, hashing as it goes. Returns (bytes, sha256, over the cap).

    `digest` and `seen` carry a transfer that is being continued: the hash has to be taken
    over the whole artifact in order, and the cap counts what is already on disk.
    """
    digest = digest if digest is not None else hashlib.sha256()
    total = 0
    while True:
        chunk = body.read(256 * 1024)
        if not chunk:
            return total, digest.hexdigest(), False
        total += len(chunk)
        if seen + total > cap:
            # Counted twice on purpose: a chunked response has no Content-Length to check,
            # and a wrong one is a lie the first check believes.
            return total, digest.hexdigest(), True
        digest.update(chunk)
        out.write(chunk)


MAX_RESUMES = 200
# Big enough that a 20 GB artifact is tens of rounds, small enough to stay inside
# whatever the far side can count: the wall this exists for is at 2 GiB.
RESUME_CHUNK = 512 * 1024 * 1024


def _append_no_symlink(path: str):
    """Open for appending, refusing to write through a symlink that IS the target."""
    flags = os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW
    return os.fdopen(os.open(path, flags, 0o600), "wb")


def resume(
    url: str,
    path: str,
    have: int,
    declared: int,
    digest,
    cap: int,
    timeout: float,
    sleep=time.sleep,
    opener=None,
) -> tuple[int, str | None]:
    """Continue a transfer that ended early, with `Range`, until the artifact is whole.

    **Why this exists.** The UKWA host-linkage dataset, 20,928,588,915 bytes, ends every
    continuous stream at exactly 2,147,483,648: a 2 GiB wall on the far side, not a flaky
    link, so a retry stops at the same byte for ever. The same server answers 206 for a
    range past it. Measured 2026-09-11, fleet run 34610597166.

    Three refusals, because a resume that guesses is worse than a fetch that fails. A
    server that answers **200 to a Range** has ignored it and is starting over, so taking
    that body would append the artifact to itself. A round that **returns no bytes** is not
    progress and two of them end it. And the **cap still binds**: what is already on disk
    counts towards it, so a resume cannot walk past the ceiling a caller set.

    Returns (bytes now on disk, reason to fail or None).
    """
    opener = opener or get
    stalled = 0
    for _ in range(MAX_RESUMES):
        if have >= declared:
            return have, None
        stop = min(have + RESUME_CHUNK, declared) - 1
        status, headers, body = opener(url, timeout, have, stop)
        with body:
            if status in RETRY_STATUS:
                wait = retry_after_seconds(headers)
                if wait is None:
                    wait = 2.0
                if wait > MAX_SLEEP_SECONDS:
                    return have, f"{status} with Retry-After {wait:.0f}s, longer than we wait"
                sleep(wait)
                continue
            if status == 200:
                return have, (
                    "the server ignored the Range header and answered 200, so the rest "
                    "cannot be appended without duplicating what is already here"
                )
            if status != 206:
                return have, f"the server answered {status} to a range request"
            try:
                with _append_no_symlink(path) as out:
                    got, _, over = stream(body, out, cap, digest, have)
            except (OSError, http.client.HTTPException) as exc:
                return have, f"the transfer failed while resuming: {exc}"
        if over:
            return have + got, f"the artifact passed the {cap} byte cap while resuming"
        have += got
        if got == 0:
            stalled += 1
            if stalled > 1:
                return have, f"the transfer stopped making progress at {have} bytes"
        else:
            stalled = 0
    return have, f"gave up after {MAX_RESUMES} range requests at {have} of {declared} bytes"


def _discard(receipt: dict) -> None:
    """Remove the part-file and stop claiming a path, so a failed fetch leaves nothing."""
    try:
        os.unlink(receipt["path"])
    except OSError:
        pass
    receipt["path"] = None


def _open_no_symlink(path: str):
    """Create or truncate `path`, refusing to write through a symlink that IS the target.

    The parent is already resolved and inside a root; this closes the last hole, where the
    file name itself is a link pointing somewhere else entirely.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW
    return os.fdopen(os.open(path, flags, 0o600), "wb")


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
    approved = False

    if not to_pipe:
        target, why, root = resolve_destination(to, url)
        receipt["path"] = target or None
        if why:
            receipt["reason"] = why
            return USAGE, receipt
        # The claim is "this file is going into the approved root", not "the approved root
        # exists somewhere in the environment": a probe write with the variable set must
        # not inherit a decision that was made about a different directory.
        approved = root == APPROVED_ROOT

    robots_cache: dict = {}
    hops = 0

    while True:
        # **Every hop is checked, not just the first.** urllib follows no redirect here, so
        # a 302 onto a second host reads that host's robots.txt before anything is asked of
        # it, and a 302 within one host re-matches the new path against rules in hand.
        verdict, delay, why = read_robots(url, timeout, robots_cache)
        receipt["url"] = url
        receipt["robots"] = verdict
        receipt["reason"] = why
        if verdict == "refused":
            return ROBOTS_REFUSED, receipt
        if verdict != "allowed":
            return ROBOTS_UNREADABLE, receipt

        for attempt in range(1, ATTEMPTS + 1):
            try:
                status, headers, body = get(url, timeout)
            except (OSError, http.client.HTTPException) as exc:
                receipt["reason"] = f"the request failed: {exc}"
                return HTTP_FAILED, receipt

            if status in RETRY_STATUS and attempt < ATTEMPTS:
                wait = retry_after_seconds(headers)
                if wait is None:
                    wait = min(MAX_SLEEP_SECONDS, max(delay, 2.0) * (2 ** (attempt - 1)))
                body.close()
                if wait > MAX_SLEEP_SECONDS:
                    receipt["reason"] = (
                        f"{status} with Retry-After {wait:.0f}s, longer than we wait"
                    )
                    return HTTP_FAILED, receipt
                print(f"fetch: {status}, waiting {wait:.0f}s as asked", file=sys.stderr, flush=True)
                sleep(wait)
                continue

            if status in REDIRECTS and headers.get("location"):
                body.close()
                hops += 1
                if hops > MAX_HOPS:
                    receipt["reason"] = f"more than {MAX_HOPS} redirects"
                    return HTTP_FAILED, receipt
                nxt = urllib.parse.urljoin(url, headers["location"])
                if urllib.parse.urlsplit(nxt).scheme not in ("http", "https"):
                    receipt["reason"] = f"redirected to {nxt}, which is not http or https"
                    return HTTP_FAILED, receipt
                print(f"fetch: {status} to {nxt}, reading its robots", file=sys.stderr, flush=True)
                url = nxt
                break

            with body:
                if status != 200:
                    receipt["reason"] = f"the server answered {status}"
                    return HTTP_FAILED, receipt

                receipt["content_type"] = headers.get("content-type")
                length = headers.get("content-length")
                declared = int(length) if length and length.strip().isdigit() else None
                if declared is not None and declared > cap:
                    receipt["bytes"] = declared
                    receipt["capped"] = True
                    receipt["reason"] = (
                        f"Content-Length {declared} is over the {cap} byte cap: "
                        "nothing was read, put it in downloads.md"
                    )
                    return OVER_CAP, receipt

                bad = content_type_verdict(receipt["content_type"], to_pipe, approved)
                if bad:
                    receipt["reason"] = bad
                    return BAD_TYPE, receipt

                # **Two ways a body ends early, and neither may read as success.** A dead
                # connection raises `http.client.HTTPException`, which is not an `OSError`,
                # so it used to traceback out with no receipt and a part-file on disk. And
                # a server that hangs up after a short body raises NOTHING at all:
                # `HTTPResponse.read(amt)` returns b"" and the loop calls it EOF, so a
                # truncated corpus banked a sha256 of the part that arrived. The declared
                # length is checked against what was counted, below.
                # The hash is kept as an object rather than a hex string, because a
                # transfer continued with `Range` has to go on hashing where it stopped.
                hasher = hashlib.sha256()
                try:
                    if to_pipe:
                        total, digest, over = stream(body, sys.stdout.buffer, cap, hasher)
                        sys.stdout.buffer.flush()
                    else:
                        os.makedirs(os.path.dirname(receipt["path"]), exist_ok=True)
                        with _open_no_symlink(receipt["path"]) as out:
                            total, digest, over = stream(body, out, cap, hasher)
                except (OSError, http.client.HTTPException) as exc:
                    if not to_pipe:
                        _discard(receipt)
                    receipt["reason"] = f"the transfer failed: {exc}"
                    return HTTP_FAILED, receipt

            # **A short body is continued, not discarded**, once the connection is closed
            # and only for a file: a pipe has already had the bytes and cannot take them
            # twice. A wall on the far side is not a reason to abandon an artifact the
            # server will hand over in pieces.
            short = declared is not None and not over and total < declared
            if short and not to_pipe:
                print(
                    f"fetch: {total} of {declared} bytes, continuing with Range",
                    file=sys.stderr,
                    flush=True,
                )
                total, why = resume(
                    url, receipt["path"], total, declared, hasher, cap, timeout, sleep
                )
                digest = hasher.hexdigest()
                if why is not None:
                    receipt["bytes"] = total
                    _discard(receipt)
                    receipt["reason"] = why
                    return HTTP_FAILED, receipt
                short = total < declared

            if (over or short) and not to_pipe:
                _discard(receipt)

            receipt["bytes"] = total
            receipt["sha256"] = digest
            if declared is not None and not over and total != declared:
                receipt["reason"] = (
                    f"the transfer ended early, {total} of {declared} bytes: "
                    "the sha256 of a part is not the sha256 of the artifact"
                )
                return HTTP_FAILED, receipt
            if over:
                receipt["capped"] = True
                receipt["reason"] = (
                    f"the stream passed the {cap} byte cap and was dropped: put it in downloads.md"
                )
                return OVER_CAP, receipt
            receipt["reason"] = f"fetched {total} bytes"
            return OK, receipt
        else:
            receipt["reason"] = f"still being throttled after {ATTEMPTS} attempts"
            return HTTP_FAILED, receipt
        # Only a redirect leaves the attempt loop without answering, and `url` is the hop.


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
