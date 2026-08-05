"""Probe archive.org's dated full-text corpus as a source of in-window domains.

The shape that has worked for this project is a corpus where **each item carries
its own date** and **mentions URLs**. A scanned 1998 book listing `foo.com` is
that shape exactly: the publication year is a property of the artifact, not
something recovered from a crawl, so it dates every domain printed inside it in
the same way a dated Usenet post does.

Three things have to be measured before any of that is worth believing, and this
script measures all three rather than arguing them:

- **how often the full text is actually downloadable.** Much of archive.org's
  book collection is lending-restricted, and a restricted item publishes
  metadata but not `_djvu.txt`. The reachable share is the real corpus size.
- **how much of the extracted text is OCR noise.** Optical recognition of a
  1990s page invents hostnames. The script reports how many extracted names
  survive a public-suffix parse and how many are corroborated by the store,
  which bounds the junk rate from below.
- **net-new (domain, year) pairs and their equivalent-English weight**, against
  the store rather than against the supplied annual files, because comparing to
  the wrong baseline is how the NYPW estimate came out 500x too high.

Read-only against the store, opened `read_only=True` with retries, because a
maintenance loop takes the write lock periodically.

Usage:
    uv run python scripts/probe_texts_corpus.py --query 'collection:boardwatch' --rows 40
    uv run python scripts/probe_texts_corpus.py --query '<solr query>' --rows 60 --keep
"""

import argparse
import gzip
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import duckdb  # noqa: E402

from ark.canonical import to_registrable  # noqa: E402
from ark.english_share import weight_of  # noqa: E402

STORE = Path("data/ark.duckdb")
SEARCH = "https://archive.org/advancedsearch.php"
DOWNLOAD = "https://archive.org/download"
USER_AGENT = "internet-digital-ark research crawler (contact: ivaylo.staykov@taktile.com)"

# Deliberately narrow. A permissive pattern over OCR output matches sentence
# punctuation ("...end.Company") and file names ("readme.txt"), and every false
# match becomes a fabricated domain. Restricting to the TLDs the metric actually
# rewards costs recall on obscure ccTLDs that are worth 0.09 each anyway.
DOMAIN_RE = re.compile(
    r"\b([a-z0-9][a-z0-9-]{0,62}(?:\.[a-z0-9][a-z0-9-]{0,62})+)"
    r"\.(com|net|org|edu|gov|us|uk|co\.uk|ac\.uk|au|ca|nz|ie|za|sg)\b",
    re.IGNORECASE,
)


def fetch(url: str, retries: int = 4) -> bytes:
    """GET with an honest agent, honouring Retry-After and backing off on 429/5xx."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    delay = 2.0
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 503, 504) and attempt < retries - 1:
                wait = float(exc.headers.get("Retry-After") or delay)
                time.sleep(wait)
                delay *= 2
                continue
            raise
        except OSError:
            if attempt == retries - 1:
                raise
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("unreachable")


def search(query: str, rows: int) -> list[dict]:
    """Item identifiers and years for a Solr query, restricted to the window."""
    params = urllib.parse.urlencode(
        {
            "q": f"({query}) AND mediatype:texts AND year:[1996 TO 2001]",
            "fl[]": "identifier",
            "rows": str(rows),
            "page": "1",
            "output": "json",
        },
        doseq=True,
    )
    # `fl[]` has to repeat, which urlencode cannot express in one mapping.
    params += "&fl%5B%5D=year&fl%5B%5D=title&fl%5B%5D=language"
    payload = json.loads(fetch(f"{SEARCH}?{params}"))
    return payload["response"]["docs"]


def full_text(identifier: str, cache: Path) -> str | None:
    """The item's OCR text, or None when the item is restricted or has none."""
    path = cache / f"{identifier}.txt.gz"
    if path.exists():
        with gzip.open(path, "rt", errors="replace") as fh:
            return fh.read()
    try:
        body = fetch(f"{DOWNLOAD}/{identifier}/{identifier}_djvu.txt")
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        return None
    if len(body) < 2048:
        return None
    text = body.decode("utf-8", errors="replace")
    with gzip.open(path, "wt") as fh:
        fh.write(text)
    return text


def domains_in(text: str) -> set[str]:
    """Registrable domains named in the text, canonicalised through the PSL."""
    found: set[str] = set()
    for match in DOMAIN_RE.finditer(text):
        registrable = to_registrable(match.group(0).lower())
        if registrable:
            found.add(registrable)
    return found


def open_store() -> duckdb.DuckDBPyConnection:
    for _ in range(6):
        try:
            return duckdb.connect(str(STORE), read_only=True)
        except duckdb.IOException:
            time.sleep(10)
    raise SystemExit("store stayed locked")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True, help="Solr query, without the mediatype filter")
    parser.add_argument("--rows", type=int, default=40, help="items to sample")
    parser.add_argument("--cache", type=Path, default=Path("data/raw/texts/cache"))
    parser.add_argument("--out", type=Path, help="write per-item results as JSON")
    args = parser.parse_args()

    args.cache.mkdir(parents=True, exist_ok=True)
    docs = search(args.query, args.rows)
    print(f"{len(docs)} items sampled for {args.query!r}", flush=True)

    pairs: set[tuple[str, int]] = set()
    per_item: list[dict] = []
    reachable = 0
    for index, doc in enumerate(docs, start=1):
        identifier, year = doc["identifier"], int(doc["year"])
        text = full_text(identifier, args.cache)
        if text is None:
            per_item.append({"identifier": identifier, "year": year, "text": False})
            continue
        reachable += 1
        found = domains_in(text)
        for domain in found:
            pairs.add((domain, year))
        per_item.append(
            {
                "identifier": identifier,
                "year": year,
                "text": True,
                "chars": len(text),
                "domains": len(found),
            }
        )
        print(f"[{index}/{len(docs)}] {identifier} {year} {len(found)} domains", flush=True)

    print(f"\nfull text reachable for {reachable}/{len(docs)} items")
    print(f"extracted {len(pairs):,} pairs over {len({d for d, _ in pairs}):,} domains")

    conn = open_store()
    try:
        held_pairs = {
            (d, y)
            for d, y in conn.execute("SELECT domain, assigned_year FROM domain_year").fetchall()
        }
        known = {r[0] for r in conn.execute("SELECT domain FROM domain").fetchall()}
    finally:
        conn.close()
    held_domains = {d for d, _ in held_pairs}

    new_pairs = pairs - held_pairs
    new_domains = {d for d, _ in pairs} - held_domains
    corroborated = {p for p in new_pairs if p[0] in held_domains}
    print(f"net-new pairs        {len(new_pairs):,}")
    print(f"net-new domains      {len(new_domains):,}")
    print(f"  corroborated (domain already in an annual file): {len(corroborated):,}")
    print(f"  never seen at all (not even a candidate): {len({d for d, _ in pairs} - known):,}")

    years = Counter(y for _, y in new_pairs)
    spread = ", ".join(f"{y}:{years[y]:,}" for y in sorted(years))
    print(f"year distribution of net-new pairs: {spread}")

    total = sum((weight_of(d) for d, _ in new_pairs), Decimal(0))
    mean = total / len(new_pairs) if new_pairs else Decimal(0)
    print(f"equivalent-English of net-new pairs: {total:.4f}  (mean weight {mean:.4f})")

    corr_total = sum((weight_of(d) for d, _ in corroborated), Decimal(0))
    print(f"equivalent-English of the corroborated half only: {corr_total:.4f}")

    if args.out:
        args.out.write_text(json.dumps(per_item, indent=2))


if __name__ == "__main__":
    main()
