#!/usr/bin/env python3
"""The output-unit standard used for the Internet Digital Ark annual files.

One rule: a record in an annual master file must be a REGISTERED DOMAIN, that is
a name consisting of one label plus a public suffix. `example.com`, `example.co.uk`
and `example.com.br` conform. `www.example.com`, `foo.example.com` and
`member.tripod.com` do not, because each carries a label to the left of the
registered domain.

This is our reading of rule 8 of the task brief:

    "By default, the final domain files should use registered domains as the
     output unit rather than full hostnames or user paths on hosting platforms.
     Unless otherwise explicitly required, output should therefore favor
     registered domains rather than `www.example.com`, `foo.example.com`, or
     specific user paths on platforms such as GeoCities or Tripod."

The program classifies every line of a domain list as CONFORMING, NOT CONFORMING
or UNPARSED, and reports the equivalent-English weight of each group using the
weights shipped with the equivalent-English calculator, so the size of the
question is stated in the metric that decides the score.

    python registrable_unit.py <file-or-directory> [more...] --model q2_tld_top_langs.json

Python 3.9 or later. No third-party packages. The Public Suffix List is bundled
next to this file so the result is identical on every machine and offline.

Only the ICANN section of the Public Suffix List is used. The PRIVATE section is
deliberately ignored, because a name delegated by a hosting company to its
customer is not a registered domain: that is exactly the population in question.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
PSL_PATH = HERE / "public_suffix_list.dat"
MODEL_PATH = HERE / "q2_tld_top_langs.json"
YEARS = tuple(f"{year}.txt" for year in range(1996, 2002))

# ccTLDs of the 1996-2001 web that have since been retired and no longer appear
# in the Public Suffix List: Yugoslavia, Netherlands Antilles, Burma,
# Czechoslovakia, East Germany, Great Britain, East Timor, US minor outlying
# islands, Zaire. Without these, a name such as `ac.yu` has no known suffix and
# would be reported as unparsed rather than judged.
HISTORICAL_SUFFIXES = (
    "yu",
    "ac.yu",
    "co.yu",
    "edu.yu",
    "gov.yu",
    "org.yu",
    "an",
    "com.an",
    "edu.an",
    "net.an",
    "org.an",
    "bu",
    "cs",
    "dd",
    "gb",
    "tp",
    "um",
    "zr",
    "com.zr",
)

# Underscores occur in real 1996-2001 subdomains, so they are tolerated while
# parsing, but the registered label itself must be strictly valid DNS.
_LABEL = re.compile(r"^[a-z0-9_]([a-z0-9_-]*[a-z0-9_])?$")
_STRICT_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
_SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*://")
_PORT = re.compile(r":\d+$")
# A reverse-DNS zone is not a website and never was. `.arpa` also carries the
# highest English weight in the model, so leaving these in would concentrate
# junk at weight 1.0000.
_REVERSE_DNS = (".in-addr.arpa", ".ip6.arpa")


def load_public_suffixes(path: Path) -> tuple[set[str], set[str], set[str]]:
    """Return (normal rules, wildcard rules, exception rules) from the ICANN section."""
    normal: set[str] = set()
    wildcard: set[str] = set()
    exception: set[str] = set()
    inside = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("// ===BEGIN ICANN DOMAINS==="):
            inside = True
            continue
        if stripped.startswith("// ===END ICANN DOMAINS==="):
            inside = False
            continue
        if not inside or not stripped or stripped.startswith("//"):
            continue
        rule = stripped.split()[0].lower()
        if rule.startswith("!"):
            exception.add(rule[1:])
        elif rule.startswith("*."):
            wildcard.add(rule[2:])
        else:
            normal.add(rule)
    normal.update(HISTORICAL_SUFFIXES)
    return normal, wildcard, exception


def public_suffix(labels: list[str], rules: tuple[set[str], set[str], set[str]]) -> int | None:
    """Return how many right-hand labels form the public suffix, or None if unknown.

    Implements the Public Suffix List matching algorithm: an exception rule wins
    over every other rule; otherwise the most specific matching rule applies,
    where a wildcard label matches exactly one label. Candidates are built from
    the right so each file is scanned once per label rather than once per label
    squared.
    """
    normal, wildcard, exception = rules
    best: int | None = None
    candidate = ""
    for length in range(1, len(labels) + 1):
        label = labels[len(labels) - length]
        candidate = label if not candidate else f"{label}.{candidate}"
        if candidate in exception:
            # An exception rule's own leftmost label belongs to the registrant.
            return length - 1
        if candidate in normal and (best is None or length > best):
            best = length
        # A rule `*.foo.bar` matches `anything.foo.bar`, so a wildcard match
        # claims one more label than the rule names, and only if one is available.
        if length < len(labels) and candidate in wildcard and (best is None or length + 1 > best):
            best = length + 1
    if best is None:
        # An unlisted single-label suffix is not a known public suffix.
        return None
    return min(best, len(labels))


def to_registrable(raw: str, rules: tuple[set[str], set[str], set[str]]) -> tuple[str | None, str]:
    """Reduce a host or URL to its registered domain.

    Returns (registered domain, reason). The reason is empty on success and
    names the defect otherwise. This is the single funnel every domain from
    every source passes through before it can enter one of our annual files.
    """
    host = unquote(raw).strip().lower()
    if not host:
        return None, "empty line"
    host = _SCHEME.sub("", host)
    host = host.removeprefix("//")
    host = re.split(r"[/?#]", host, maxsplit=1)[0]
    host = host.rsplit("@", maxsplit=1)[-1]
    host = _PORT.sub("", host)
    # Strip stray separator punctuation, never a leading hyphen: that would
    # alter the name itself.
    host = host.strip(".,")
    if not host:
        return None, "empty line"
    if _IPV4.match(host):
        return None, "ip address, not a domain"
    if host.endswith(_REVERSE_DNS) or host in {"in-addr.arpa", "ip6.arpa"}:
        return None, "reverse-dns zone, not a website"
    labels = host.split(".")
    if not all(_LABEL.match(label) for label in labels):
        return None, "invalid hostname syntax"
    suffix_length = public_suffix(labels, rules)
    if suffix_length is None:
        return None, "no known public suffix"
    if suffix_length >= len(labels):
        return None, "bare public suffix, not a registered domain"
    registered_label = labels[-suffix_length - 1]
    if not _STRICT_LABEL.match(registered_label):
        return None, "invalid character in registered label"
    return ".".join(labels[-suffix_length - 1 :]), ""


def load_weights(path: Path) -> dict[str, Decimal]:
    """English shares from the calculator's own model file, keyed by TLD."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    tlds, langs, shares = raw["tld"], raw["lang"], raw["perc_of_tld"]
    if not len(tlds) == len(langs) == len(shares):
        raise ValueError("the model's tld, lang and perc_of_tld lists differ in length")
    return {
        str(tld).lower(): Decimal(str(pct)) / Decimal("100")
        # No `strict=`: this file ships to a reviewer whose Python version is
        # unknown, and the length check above already covers what strict would.
        for tld, lang, pct in zip(tlds, langs, shares)  # noqa: B905
        if tld and lang == "eng"
    }


def survey(path: Path, rules, weights: dict[str, Decimal], sample_size: int) -> dict:
    """Classify every line of one file.

    The examples are drawn by reservoir sampling with a fixed seed, not taken
    from the head of the file. These lists are sorted, so their first lines are
    percent-encoded and punctuation-led oddities that are not representative of
    the population being counted.
    """
    conforming = not_conforming = unparsed = 0
    ee_conforming = ee_not = Decimal(0)
    samples: list[str] = []
    parents: Counter[str] = Counter()
    seen: set[str] = set()
    rng = random.Random(20260831)
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            host = line.strip().lower()
            if not host or host in seen:
                continue
            seen.add(host)
            registered, _ = to_registrable(host, rules)
            weight = weights.get(host.rsplit(".", 1)[-1], Decimal(0))
            if registered is None:
                unparsed += 1
            elif registered == host:
                conforming += 1
                ee_conforming += weight
            else:
                not_conforming += 1
                ee_not += weight
                parents[registered] += 1
                if len(samples) < sample_size:
                    samples.append(f"{host}\t{registered}")
                else:
                    slot = rng.randrange(not_conforming)
                    if slot < sample_size:
                        samples[slot] = f"{host}\t{registered}"
    total = conforming + not_conforming + unparsed
    return {
        "file": str(path),
        "records": total,
        "conforming": conforming,
        "not_conforming": not_conforming,
        "unparsed": unparsed,
        "not_conforming_share_pct": (f"{100 * not_conforming / total:.4f}" if total else "0"),
        "equivalent_english_conforming": f"{ee_conforming:.4f}",
        "equivalent_english_not_conforming": f"{ee_not:.4f}",
        "_samples": samples,
        "_parents": parents.most_common(25),
    }


def targets(given: list[Path]) -> list[Path]:
    found: list[Path] = []
    for path in given:
        if path.is_dir():
            year_files = [path / name for name in YEARS if (path / name).is_file()]
            found.extend(year_files if year_files else sorted(path.glob("*.txt")))
        elif path.is_file():
            found.append(path)
        else:
            print(f"skipping {path}: not found", file=sys.stderr)
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify a domain list by output unit.")
    parser.add_argument("paths", nargs="+", type=Path, help="files, or directories of YYYY.txt")
    parser.add_argument("--psl", type=Path, default=PSL_PATH)
    parser.add_argument("--model", type=Path, default=MODEL_PATH)
    parser.add_argument("--out", type=Path, default=HERE / "results")
    parser.add_argument("--samples", type=int, default=40)
    args = parser.parse_args()

    rules = load_public_suffixes(args.psl)
    weights = load_weights(args.model)
    args.out.mkdir(parents=True, exist_ok=True)

    columns = [
        "file",
        "records",
        "conforming",
        "not_conforming",
        "unparsed",
        "not_conforming_share_pct",
        "equivalent_english_conforming",
        "equivalent_english_not_conforming",
    ]
    rows = []
    header = f"{'file':<58}{'records':>12}{'not conforming':>16}{'share':>9}{'EE':>14}"
    print(header)
    print("-" * len(header))
    for path in targets(args.paths):
        row = survey(path, rules, weights, args.samples)
        rows.append(row)
        label = str(path)
        if len(label) > 56:
            label = "..." + label[-53:]
        print(
            f"{label:<58}{row['records']:>12,}{row['not_conforming']:>16,}"
            f"{float(row['not_conforming_share_pct']):>8.2f}%"
            f"{float(row['equivalent_english_not_conforming']):>14,.2f}"
        )
        if row["_samples"]:
            stem = str(path).replace("/", "_").replace("\\", "_").lstrip("._")
            (args.out / f"samples_{stem}").write_text(
                "# a random sample of the records that are not registered domains\n"
                "# record\tits registered domain\n" + "\n".join(sorted(row["_samples"])) + "\n",
                encoding="utf-8",
            )
            (args.out / f"parents_{stem}").write_text(
                "# the registered domains under which those records sit, most frequent first\n"
                "# count\tregistered domain\n"
                + "\n".join(f"{count}\t{parent}" for parent, count in row["_parents"])
                + "\n",
                encoding="utf-8",
            )

    with (args.out / "summary.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in columns})

    total_records = sum(row["records"] for row in rows)
    total_not = sum(row["not_conforming"] for row in rows)
    total_ee = sum(Decimal(row["equivalent_english_not_conforming"]) for row in rows)
    print("-" * len(header))
    share = 100 * total_not / total_records if total_records else 0
    print(
        f"{'TOTAL':<58}{total_records:>12,}{total_not:>16,}{share:>8.2f}%{float(total_ee):>14,.2f}"
    )
    print(f"\nwrote {args.out / 'summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
