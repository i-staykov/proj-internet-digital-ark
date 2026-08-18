"""The InterNIC zone parser, whose whole discipline is which side of an NS record counts.

The Defense Data Network NIC mirrored InterNIC's zone distribution over HTTP and Wayback
captured it, which is how a family this project closed twice for "no in-window zone file
survives" turned out to have one: a complete 18 April 1997 `.org` zone, plus `edu`, `gov`,
`mil`, `root` and `arpa` from the same crawl.

**The owner of an NS record is the delegation; the target is a nameserver.** Getting that
backwards is not hypothetical. The sibling `inaddr.zone.gz` was first claimed at 2,018
net-new pairs and measured at 336, because 99.8% of its right-hand sides were nameserver
names, which are the most-covered names in the store.

Measured on the real files, 2026-08-18: 65,261 delegations, 52,861 already held, 12,400
net-new pairs and 8,871.2 equivalent-English as the self-dating class it is.
"""

import gzip
from collections import Counter
from pathlib import Path

from ark.canonical import to_registrable
from ark.sources import SOURCES

SPEC = SOURCES["internic_zone"]

ZONE = """ORG.\tIN\tSOA\tA.ROOT-SERVERS.NET.\thostmaster.INTERNIC.NET. (
\t\t\t\t1997041800\t;serial
\t\t\t\t10800  ;refresh every 3 hours
\t\t\t\t)
ORG.                      518400 IN  NS    A.ROOT-SERVERS.NET.
A.ROOT-SERVERS.NET.       518400     A     198.41.0.4
EXAMPLE.ORG.              172800     NS    NS1.PROVIDER.NET.
                          172800     NS    NS2.PROVIDER.NET.
SUB.DEEPER.ORG.           172800     NS    NS1.PROVIDER.NET.
OTHER.ORG.                172800     NS    NS.OTHER.ORG.
;End of file.
"""


def write(tmp_path: Path, text: str, name: str = "org.zone.gz") -> Path:
    path = tmp_path / name
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        fh.write(text)
    return path


def parse(path: Path) -> tuple[list, Counter]:
    stats: Counter = Counter()
    return list(SPEC.parse(path, stats)), stats


def test_the_delegation_is_the_owner_and_never_the_nameserver(tmp_path) -> None:
    """`provider.net` appears twice as an NS target and must never be recorded."""
    records, _ = parse(write(tmp_path, ZONE))
    names = {r.raw for r in records}
    assert names == {"example.org", "other.org"}
    assert not any("provider.net" in n for n in names)
    assert "a.root-servers.net" not in names


def test_the_year_comes_from_the_serial_inside_the_file(tmp_path) -> None:
    """Not from the filename and not from the capture. A renamed file still dates itself."""
    records, _ = parse(write(tmp_path, ZONE, name="something-else.gz"))
    assert records
    assert {r.year for r in records} == {1997}
    assert all("serial 1997041800" in r.evidence_value for r in records)


def test_a_deeper_owner_is_skipped_rather_than_truncated(tmp_path) -> None:
    """`sub.deeper.org` must not become `deeper.org`: that is a claim the zone did not make,
    even though it happens to be true."""
    records, stats = parse(write(tmp_path, ZONE))
    assert "deeper.org" not in {r.raw for r in records}
    assert stats["deeper_than_one_label"] == 1


def test_the_apex_is_not_a_delegation(tmp_path) -> None:
    records, stats = parse(write(tmp_path, ZONE))
    assert "org" not in {r.raw for r in records}
    assert stats["apex_delegation"] == 1


def test_a_continuation_line_yields_nothing_and_is_counted(tmp_path) -> None:
    """A second NS line carries the TTL in the owner position. It must be skipped, and the
    skip must be counted, because a silent drop is how a yield figure becomes a lie."""
    _records, stats = parse(write(tmp_path, ZONE))
    assert stats["owner_outside_zone"] >= 1


def test_a_file_dated_outside_the_window_is_skipped_whole(tmp_path) -> None:
    old = ZONE.replace("1997041800", "1993041800")
    records, stats = parse(write(tmp_path, old))
    assert records == []
    assert stats["out_of_window_file"] == 1


def test_a_file_with_no_serial_is_refused_rather_than_guessed(tmp_path) -> None:
    headerless = "\n".join(line for line in ZONE.splitlines() if ";serial" not in line)
    records, stats = parse(write(tmp_path, headerless))
    assert records == []
    assert stats["no_soa_serial"] == 1


def test_the_parser_reports_reverse_dns_and_the_canonicaliser_refuses_it(tmp_path) -> None:
    """The division of labour that keeps both honest. The `arpa` zone from the same crawl
    delegates reverse zones, and the parser's job is to report what the artifact says; the
    canonicaliser's job is to decide what is storable. `.arpa` scores 1.0000, the highest
    weight in the model, so the refusal matters."""
    arpa = ZONE.replace("ORG", "ARPA").replace("EXAMPLE.ARPA.", "IN-ADDR.ARPA.")
    records, _stats = parse(write(tmp_path, arpa, name="arpa.zone.gz"))
    reported = {r.raw for r in records}
    assert "in-addr.arpa" in reported, "the parser reports what the zone delegates"
    assert to_registrable("in-addr.arpa") is None, "and the funnel refuses it"
    # The per-network zones BELOW it are two labels under the apex, so the parser skips them
    # as deeper-than-one-label rather than truncating. That is why the real `arpa.zone.gz`
    # yields exactly one record, `in-addr.arpa`, out of 35 lines rather than a flood.
    assert to_registrable("206.in-addr.arpa") is None


def test_the_class_is_self_dating_and_master_eligible(tmp_path) -> None:
    """`artifact_listing` takes no corroboration split, which is why the pre-split figure is
    the one that would be banked. It is master-eligible, so it cannot date a year until a
    human writes the Decision line, which is ADR-003 working rather than an obstacle."""
    assert SPEC.evidence_type == "artifact_listing"
    assert not SPEC.is_candidate_only
