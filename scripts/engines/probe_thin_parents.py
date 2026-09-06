"""Price one CDX query against a registrable we hold but have NO hostnames under.

**The idea being tested (Ivo, 2026-09-06).** The platform sweep goes after parents with
thousands of subdomains, because one answer carries thousands of records. That queue is
finite and its head is already walked. Beneath it sits a much larger population: 10,029,609
registrables we hold with zero hostname records. Each is worth little on its own, but there
are ten million of them and each costs exactly one request.

What decides it is yield per request, so this measures that and nothing else. It asks the
same `matchType=domain` question the sweep asks, over 1996-2001, and counts the distinct
hosts that come back and are not already held. It writes no records: the point is a price.

    uv run python scripts/engines/probe_thin_parents.py --domains <file> [--delay 2.0]

One archive client. Run it only when a slot is free.
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from ark.cdx import USER_AGENT  # noqa: E402
from ark.english_share import english_weights  # noqa: E402

CDX = "http://web.archive.org/cdx/search/cdx"


def hosts_under(domain: str, delay: float, timeout: int = 90) -> tuple[set[str], str]:
    """Distinct hosts with an in-window capture under `domain`, and a status word."""
    query = {
        "url": domain,
        "matchType": "domain",
        "from": "1996",
        "to": "2001",
        "fl": "timestamp,original",
        "collapse": "urlkey",
        "limit": "20000",
    }
    url = f"{CDX}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        # honour the archive's own pacing rather than pressing on
        if exc.code in (429, 503, 504):
            wait = int(exc.headers.get("Retry-After", 30) or 30)
            time.sleep(min(wait, 120))
            return set(), f"throttled_{exc.code}"
        return set(), f"http_{exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError):
        return set(), "network"

    hosts: set[str] = set()
    for line in body.splitlines():
        fields = line.split()
        if len(fields) < 2:
            continue
        original = fields[1]
        host = original.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0].lower()
        if host.endswith("." + domain) or host == domain:
            hosts.add(host)
    time.sleep(delay)
    return hosts, "ok"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domains", type=Path, required=True)
    ap.add_argument("--delay", type=float, default=2.0)
    args = ap.parse_args()

    names = [d.strip() for d in args.domains.read_text().splitlines() if d.strip()]
    weights = english_weights()

    started = time.time()
    total_hosts = 0
    total_ee = 0.0
    answered = 0
    empty = 0
    failures: dict[str, int] = {}
    per_domain: list[tuple[str, int]] = []

    for name in names:
        hosts, status = hosts_under(name, args.delay)
        if status != "ok":
            failures[status] = failures.get(status, 0) + 1
            continue
        answered += 1
        # the bare registrable is already held; only hosts BENEATH it are new records
        beneath = {h for h in hosts if h != name}
        if not beneath:
            empty += 1
        total_hosts += len(beneath)
        tld = name.rsplit(".", 1)[-1]
        total_ee += len(beneath) * float(weights.get(tld, 0.0))
        per_domain.append((name, len(beneath)))

    elapsed = max(time.time() - started, 1e-9)
    rate = answered / elapsed * 3600 if answered else 0.0

    print(f"domains asked      : {len(names):,}")
    print(f"answered           : {answered:,}   empty: {empty:,}")
    if failures:
        print(f"failures           : {failures}")
    print(f"hosts beneath found: {total_hosts:,}")
    if answered:
        print(f"hosts per answer   : {total_hosts / answered:.2f}")
        print(f"EE in the sample   : {total_ee:,.2f}")
        print(f"EE per answer      : {total_ee / answered:.4f}")
        print(f"queries per hour   : {rate:,.0f} at {args.delay}s delay")
        print(f"=> EE per client-hour: {total_ee / answered * rate:,.0f}")
    top = sorted(per_domain, key=lambda kv: -kv[1])[:8]
    if top:
        print("richest in the sample:")
        for name, n in top:
            print(f"   {name:<38} {n:>6} hosts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
