"""No website ever lived under `.arpa` in 1996-2001, and the TLD scores 1.0000.

Found 2026-08-18 by a hunt lens that noticed `.arpa` entering the metric at weight 1. The
store held 63 assigned pairs across 18 reverse-DNS zones, harvested out of Usenet `From:`
headers and out of the reviewer's own baseline, and all six shipped annual files carried them.

The weight is why it matters more than 63 rows should. `.arpa` is **1.0000** in the CC-MAIN
model, the highest value in the whole table, above `.mil` at 0.9981, so this was junk
concentrated in the top weight, which is exactly the shape law 5 describes. The reviewer's own
validator accepts `206.in-addr.arpa` as a well-formed domain, so his side would have scored it.

Narrowing to `in-addr` and `ip6` left exactly one survivor in the annual files, `ignore.arpa`
in 2000, a literal placeholder. So the rule is the whole TLD: the ARPANET host transition
finished in 1990, and every zone delegated under `.arpa` since is infrastructure (`in-addr`,
`ip6`, `e164`, `uri`, `urn`, `iris`).

Guarded in two places on purpose. `ark.canonical` refuses them at the funnel every domain from
every source passes through, so none can arrive. `ark.export` filters them from every
destination, because the ones already stored predate the funnel and deleting store rows is a
destructive migration this did not need.
"""

from ark.canonical import reject_reason, to_registrable


def test_a_reverse_dns_zone_is_not_a_registrable_domain() -> None:
    assert to_registrable("206.in-addr.arpa") is None
    assert reject_reason("206.in-addr.arpa") == "reverse-dns zone, not a website"


def test_a_deep_reverse_dns_name_is_refused_too() -> None:
    """The shape actually found in Usenet headers, a full four-octet PTR name."""
    assert to_registrable("129-109-170-195.in-addr.arpa") is None


def test_the_ipv6_reverse_zone_is_refused() -> None:
    assert to_registrable("8.b.d.0.1.0.0.2.ip6.arpa") is None


def test_the_bare_reverse_zones_are_refused() -> None:
    assert to_registrable("in-addr.arpa") is None
    assert to_registrable("ip6.arpa") is None


def test_a_real_domain_still_passes_the_funnel() -> None:
    """The guard must not cost anything outside `.arpa`."""
    assert to_registrable("foo.com") == "foo.com"
    assert to_registrable("206.example.com") == "example.com"


def test_arpa_carries_the_highest_weight_in_the_model() -> None:
    """The reason this is worth a guard rather than a note: it is not a rounding error, it is
    the top of the weight table, above .mil."""
    from ark.english_share import weight_of

    assert weight_of("x.arpa") == 1
    assert weight_of("x.arpa") > weight_of("x.mil") > weight_of("x.uk")


def test_the_export_filter_names_the_whole_tld_not_the_reverse_dns_shape() -> None:
    """Pinned because the narrow rule was tried first and let `ignore.arpa` through."""
    from ark.export import _NOT_REVERSE_DNS

    assert "'%.arpa'" in _NOT_REVERSE_DNS
    assert "in-addr" not in _NOT_REVERSE_DNS
