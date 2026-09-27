"""Page expansion: link extraction, seed parsing, capture fetching (offline)."""

import pytest

from ark.cdx import RateGovernor
from ark.expand import (
    answered,
    expand_page,
    outbound_domains,
    page_captures_url,
    read_seeds,
    snapshot_url,
    split_by_corroboration,
    unwrap_redirect,
)

PAGE = """
<html><body>
  <a href="http://www.example.com/index.html">absolute</a>
  <a href="http://shop.example.com/">same registered domain as the one above</a>
  <a href="/local/page.html">relative, resolves to the page's own domain</a>
  <a href="#section">fragment only</a>
  <a href="mailto:someone@nowhere.org">not a web link</a>
  <a href="https://other.co.uk/deep/path?q=1">another domain, https</a>
  <a>no href at all</a>
  <a href="http://dir.example.org/">third domain</a>
</body>
"""
# A portal click-tracker's own domain is the page's, so an unwrapped one reads as a self-link.
YAHOO_PAGE = """
<a href="http://srd.yahoo.com/goo/Business/*http://www.example.com/">Example</a>
<a href="http://srd.yahoo.com/goo/Arts/*http://shop.other.co.uk/x">Other</a>
<a href="/dir/More">more</a>
"""
MALFORMED = '<a href="http://ok.com/">unclosed <b> <a href=http://bare.net/>bare attr'


def _expand(fetch, **kwargs) -> list[dict]:
    governor = RateGovernor(delay=0.0, min_delay=0.0, sleep=lambda _seconds: None)
    return expand_page("http://seed.org/", 1996, 2001, fetch, governor, **kwargs)


def _page(*domains: str) -> dict:
    return dict(page_url="http://c/", year=1999, status=200, curated=True, domains=[*domains])


@pytest.mark.parametrize(
    ("page", "url", "found"),
    [
        (PAGE, "http://www.host.com/dir/index.html", ["example.com", "other.co.uk", "example.org"]),
        (PAGE, "http://host.com/a/b.html", ["example.com", "other.co.uk", "example.org"]),
        ('<a href="mailto:a@b.com">m</a><a href="javascript:void(0)">j</a>', "http://p.org/", []),
    ],
    ids=["subdomains-collapse-in-order-self-excluded", "relative-self-link", "mailto-javascript"],
)
def test_outbound_domains_are_the_other_registered_domains(page, url, found) -> None:
    assert outbound_domains(page, url) == found


@pytest.mark.parametrize(
    ("page", "url", "present", "absent"),
    [
        (MALFORMED, "http://page.org/", ["ok.com", "bare.net"], []),
        (YAHOO_PAGE, "http://dir.yahoo.com/b/", ["example.com", "other.co.uk"], ["yahoo.com"]),
    ],
    ids=["malformed-markup", "yahoo-click-tracker-yields-the-target"],
)
def test_outbound_domains_survive_period_markup(page, url, present, absent) -> None:
    found = outbound_domains(page, url)
    assert set(present) <= set(found) and not set(absent) & set(found)


@pytest.mark.parametrize(
    ("url", "target"),
    [
        ("http://srd.yahoo.com/goo/x/*http://www.example.com/", "http://www.example.com/"),
        ("http://count.example/r?url=http%3A%2F%2Fwww.target.org%2Fa", "http://www.target.org/a"),
        ("http://www.example.com/path?q=1", "http://www.example.com/path?q=1"),
        ("https://a.example/x", "https://a.example/x"),
    ],
    ids=["last-scheme-wins", "percent-encoded", "ordinary-url", "scheme-at-position-zero-only"],
)
def test_unwrap_redirect(url, target) -> None:
    assert unwrap_redirect(url) == target


def test_read_seeds_parses_the_directory_assertion() -> None:
    lines = ["http://plain.example/page.html", "http://curated.example/dir.html\tdirectory"]
    lines += ["# a comment", "   ", "http://spaced.example/\tDIRECTORY"]
    assert read_seeds(lines) == [
        ("http://plain.example/page.html", False),
        ("http://curated.example/dir.html", True),
        ("http://spaced.example/", True),
    ]


def test_the_archive_urls_ask_for_original_bytes_in_a_bounded_window() -> None:
    # the id_ modifier is what stops Wayback rewriting the hrefs
    assert snapshot_url("19980101000000", "http://x.com/") == (
        "https://web.archive.org/web/19980101000000id_/http://x.com/"
    )
    url = page_captures_url("http://x.com/", 1996, 2001, limit=3)
    assert "from=1996" in url and "to=2001" in url
    assert "collapse=timestamp%3A4" in url and "limit=3" in url


def test_expand_page_returns_one_record_per_capture_year() -> None:
    stamps, link = "19970101000000\n19990101000000\n", '<a href="http://found.com/">x</a>'
    records = _expand(lambda url: (200, stamps if "cdx/search" in url else link), curated=True)
    assert [r["year"] for r in records] == [1997, 1999]
    assert all(r["domains"] == ["found.com"] and r["curated"] is True for r in records)


def _failed(url: str) -> tuple[int, str]:
    return (200, "19970101000000\n") if "cdx/search" in url else (503, "")


@pytest.mark.parametrize(
    ("fetch", "want", "settled"),
    [
        (_failed, {"status": 503, "timestamp": "19970101000000"}, False),
        (lambda _url: (200, "20080101000000\n"), {"status": 200, "timestamp": None}, True),
    ],
    ids=["failed-page-fetch-is-retried-later", "no-in-window-capture-is-settled"],
)
def test_expand_page_records_a_page_without_domains(fetch, want, settled) -> None:
    [record] = _expand(fetch)
    assert {key: record[key] for key in want} == want and record["domains"] == []
    assert answered(record) is settled


@pytest.mark.parametrize(("status", "real"), [(200, True), (0, False), (504, False)])
def test_answered_requires_a_real_reply(status, real) -> None:
    assert answered({"status": status}) is real


def test_corroboration_keeps_known_names_curated_and_routes_the_rest() -> None:
    # archived HTML carries typos like arvard.edu for harvard.edu, so the split is per name
    curated, unverified = split_by_corroboration(
        [_page("known.com", "arvard.edu", "also-known.org")], known={"known.com", "also-known.org"}
    )
    assert curated[0]["domains"] == ["known.com", "also-known.org"] and curated[0]["curated"]
    assert unverified[0]["domains"] == ["arvard.edu"]
    assert unverified[0]["curated"] is False, "a candidate earns its own year"
    kept = {d for r in curated + unverified for d in r["domains"]}
    assert kept == {"known.com", "arvard.edu", "also-known.org"}, "nothing is discarded"
    curated, unverified = split_by_corroboration([_page("never-seen.example")], known=set())
    assert curated == [] and len(unverified) == 1
