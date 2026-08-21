"""Do the Wayback CDX endpoint's bulk options work for us?

**The question that decides everything.** This project is bounded by ~17,500
per-domain queries a day. The CDX API also accepts `matchType=domain`, which
returns every capture under a whole TLD, and `pageSize`/`page` for pagination.
If a TLD-level query is allowed, one request replaces a million.

The register records `url=*.mil/...` and `url=mil&matchType=domain` returning
**HTTP 403 "This type of CDX query requires authorization"**. That was 2026-08-18
and it was tested on `.mil`. This re-tests the shape systematically, because a
403 on one TLD is not a policy about all of them, and because the register also
records that `collapse` and `filter` change what is allowed.

Every request here is one CDX call with `limit` set small, so the cost is a
handful of queries rather than a sweep.

    uv run python scripts/cdx_bulk_probe.py
"""

import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "InternetDigitalArk/1.0 (+historical domain research; ivaylo.staykov@gmail.com)"
BASE = "https://web.archive.org/cdx/search/cdx"

# Each probe is (label, params). The control must succeed or nothing below means
# anything: a 403 during a general outage is not evidence about the query shape.
PROBES = (
    ("CONTROL single domain", {"url": "bbc.co.uk", "limit": 2}),
    ("domain matchType, .uk", {"url": "uk", "matchType": "domain", "limit": 2}),
    ("domain matchType, co.uk", {"url": "co.uk", "matchType": "domain", "limit": 2}),
    ("prefix matchType, co.uk", {"url": "co.uk/", "matchType": "prefix", "limit": 2}),
    ("host matchType", {"url": "bbc.co.uk", "matchType": "host", "limit": 2}),
    ("wildcard path", {"url": "bbc.co.uk/*", "limit": 2}),
    (
        "domain + from/to",
        {"url": "uk", "matchType": "domain", "from": "1996", "to": "2001", "limit": 2},
    ),
    ("domain + collapse", {"url": "uk", "matchType": "domain", "collapse": "urlkey", "limit": 2}),
    ("domain + fl", {"url": "uk", "matchType": "domain", "fl": "original", "limit": 2}),
    (
        "pageSize on a domain",
        {"url": "bbc.co.uk", "matchType": "domain", "pageSize": 1, "page": 0},
    ),
    (
        "showNumPages on a domain",
        {"url": "bbc.co.uk", "matchType": "domain", "showNumPages": "true"},
    ),
    ("showNumPages on a TLD", {"url": "uk", "matchType": "domain", "showNumPages": "true"}),
)


def probe(params: dict) -> tuple[str, str]:
    url = f"{BASE}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=90) as fh:
            body = fh.read(400).decode("utf-8", "replace").strip()
            return "200", body.splitlines()[0][:90] if body else "(empty)"
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read(200).decode("utf-8", "replace").strip().replace("\n", " ")[:80]
        except Exception:
            pass
        return f"HTTP{exc.code}", detail
    except Exception as exc:  # noqa: BLE001
        return f"ERR:{type(exc).__name__}", ""


def main() -> None:
    ok = False
    for attempt in range(5):
        status, _ = probe(dict(PROBES[0][1]))
        if status == "200":
            ok = True
            break
        print(f"  control attempt {attempt + 1}: {status}, waiting")
        time.sleep(60)
    if not ok:
        sys.exit("control never passed; nothing below would mean anything")

    print(f"{'probe':<28}{'status':<10}first line or error")
    for label, params in PROBES:
        status, body = probe(params)
        print(f"{label:<28}{status:<10}{body}")
        time.sleep(3)

    print(
        "\nA 200 on any TLD-level shape would replace roughly a million per-domain\n"
        "queries with one request, which is the only thing that changes this\n"
        "project's timeline. A 403 confirms the register and closes it again."
    )


if __name__ == "__main__":
    main()
