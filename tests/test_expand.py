"""Page expansion: link extraction, seed parsing, capture fetching (offline)."""

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


def _no_sleep(_seconds: float) -> None:
    return None


def _gov() -> RateGovernor:
    return RateGovernor(delay=0.0, min_delay=0.0, sleep=_no_sleep)


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


def test_outbound_domains_collapses_and_excludes_the_page_itself() -> None:
    found = outbound_domains(PAGE, "http://www.host.com/dir/index.html")
    # subdomains collapse to one registered domain, order preserved, self excluded
    assert found == ["example.com", "other.co.uk", "example.org"]


def test_outbound_domains_excludes_the_page_domain_even_via_a_relative_link() -> None:
    # the relative link resolves to host.com, which must not be reported
    assert "host.com" not in outbound_domains(PAGE, "http://host.com/a/b.html")


def test_outbound_domains_survives_malformed_markup() -> None:
    broken = '<a href="http://ok.com/">unclosed <b> <a href=http://bare.net/>bare attr'
    found = outbound_domains(broken, "http://page.org/")
    assert "ok.com" in found and "bare.net" in found


def test_mailto_and_javascript_links_are_ignored() -> None:
    page = '<a href="mailto:a@b.com">m</a><a href="javascript:void(0)">j</a>'
    assert outbound_domains(page, "http://page.org/") == []


def test_read_seeds_parses_the_directory_assertion() -> None:
    seeds = read_seeds(
        [
            "http://plain.example/page.html",
            "http://curated.example/dir.html\tdirectory",
            "# a comment",
            "   ",
            "http://spaced.example/\tDIRECTORY",
        ]
    )
    assert seeds == [
        ("http://plain.example/page.html", False),
        ("http://curated.example/dir.html", True),
        ("http://spaced.example/", True),
    ]


def test_snapshot_url_asks_for_the_original_bytes() -> None:
    # the id_ modifier is what stops Wayback rewriting the hrefs
    assert snapshot_url("19980101000000", "http://x.com/") == (
        "https://web.archive.org/web/19980101000000id_/http://x.com/"
    )


def test_page_captures_url_bounds_the_window_and_collapses_years() -> None:
    url = page_captures_url("http://x.com/", 1996, 2001, limit=3)
    assert "from=1996" in url and "to=2001" in url
    assert "collapse=timestamp%3A4" in url and "limit=3" in url


def test_expand_page_returns_one_record_per_capture_year() -> None:
    def fetch(url: str) -> tuple[int, str]:
        if "cdx/search" in url:
            return 200, "19970101000000\n19990101000000\n"
        return 200, '<a href="http://found.com/">x</a>'

    records = expand_page("http://seed.org/", 1996, 2001, fetch, _gov(), curated=True)

    # a page captured in two years evidences its entries in each year separately
    assert [r["year"] for r in records] == [1997, 1999]
    assert all(r["domains"] == ["found.com"] for r in records)
    assert all(r["curated"] is True for r in records)


def test_expand_page_records_a_failed_page_fetch_without_domains() -> None:
    def fetch(url: str) -> tuple[int, str]:
        return (200, "19970101000000\n") if "cdx/search" in url else (503, "")

    records = expand_page("http://seed.org/", 1996, 2001, fetch, _gov())
    assert len(records) == 1
    assert records[0]["status"] == 503
    assert records[0]["domains"] == []
    # a failure is not an answer, so a later round retries the page
    assert answered(records[0]) is False


def test_expand_page_reports_a_page_with_no_in_window_captures() -> None:
    records = expand_page(
        "http://seed.org/", 1996, 2001, lambda _u: (200, "20080101000000\n"), _gov()
    )
    assert records[0]["timestamp"] is None
    assert records[0]["domains"] == []
    # settled: the archive answered, it simply holds nothing in window
    assert answered(records[0]) is True


def test_answered_requires_a_real_reply() -> None:
    assert answered({"status": 200}) is True
    assert answered({"status": 0}) is False
    assert answered({"status": 504}) is False


def test_corroboration_split_keeps_known_names_curated_and_routes_the_rest() -> None:
    records = [
        {
            "page_url": "http://cat.example/",
            "year": 1998,
            "status": 200,
            "curated": True,
            "domains": ["known.com", "arvard.edu", "also-known.org"],
        },
    ]
    curated, unverified = split_by_corroboration(records, known={"known.com", "also-known.org"})

    # the page is a curated catalogue either way; the split is about each NAME,
    # because archived HTML carries typos like arvard.edu for harvard.edu
    assert curated[0]["domains"] == ["known.com", "also-known.org"]
    assert curated[0]["curated"] is True
    assert unverified[0]["domains"] == ["arvard.edu"]
    # candidate-only, so it must earn its own year rather than take the page's
    assert unverified[0]["curated"] is False


def test_corroboration_split_discards_nothing() -> None:
    records = [
        {
            "page_url": "http://c/",
            "year": 1999,
            "status": 200,
            "curated": True,
            "domains": ["a.com", "b.com", "c.com"],
        }
    ]
    curated, unverified = split_by_corroboration(records, known={"b.com"})
    kept = {d for r in curated + unverified for d in r["domains"]}
    assert kept == {"a.com", "b.com", "c.com"}


def test_a_page_with_no_corroborated_names_yields_no_curated_record() -> None:
    records = [
        {
            "page_url": "http://c/",
            "year": 1999,
            "status": 200,
            "curated": True,
            "domains": ["never-seen.example"],
        }
    ]
    curated, unverified = split_by_corroboration(records, known=set())
    assert curated == []
    assert len(unverified) == 1


# Portal click-trackers of the period. Yahoo's is the one that mattered: left
# unhandled it does not degrade the extraction, it zeroes it, because the
# wrapper's domain is also the page's own domain and every entry is discarded as
# a self-link.
YAHOO_PAGE = """
<a href="http://srd.yahoo.com/goo/Business/*http://www.example.com/">Example</a>
<a href="http://srd.yahoo.com/goo/Arts/*http://shop.other.co.uk/x">Other</a>
<a href="/dir/More">more</a>
"""


def test_a_yahoo_style_wrapper_yields_the_target_not_the_redirector() -> None:
    found = outbound_domains(YAHOO_PAGE, "http://dir.yahoo.com/Business/index.html")

    assert "example.com" in found
    assert "other.co.uk" in found
    assert "yahoo.com" not in found


def test_unwrap_takes_the_last_scheme_because_the_wrapper_starts_with_one() -> None:
    assert (
        unwrap_redirect("http://srd.yahoo.com/goo/x/*http://www.example.com/")
        == "http://www.example.com/"
    )


def test_unwrap_handles_a_percent_encoded_target() -> None:
    assert (
        unwrap_redirect("http://count.example.net/r?url=http%3A%2F%2Fwww.target.org%2Fa")
        == "http://www.target.org/a"
    )


def test_unwrap_leaves_an_ordinary_url_alone() -> None:
    plain = "http://www.example.com/path?q=1"
    assert unwrap_redirect(plain) == plain


def test_unwrap_does_not_fire_on_a_scheme_at_position_zero_only() -> None:
    """A bare URL must not be truncated to itself by an off-by-one."""
    assert unwrap_redirect("https://a.example/x") == "https://a.example/x"
