"""No website ever lived under `.arpa` in 1996-2001, and the TLD scores 1.0000.

`.arpa` is the highest weight in the CC-MAIN table, above `.mil` at 0.9981, and the
reviewer's validator accepts `206.in-addr.arpa` as well formed, so junk there is junk in the
top weight, which is law 5's shape. The ARPANET host transition finished in 1990 and every
zone delegated under `.arpa` since is infrastructure, so the rule is the whole TLD.

Guarded twice: `ark.canonical` refuses them at the funnel, so none can arrive, and
`ark.export` filters every destination, because rows stored before the funnel existed are
still there and deleting store rows is a destructive migration this did not need.
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
